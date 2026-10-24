"""Standalone cross-check: no voltforge imports, SciPy MAT reader, or audit CSVs.

MAT5 numeric values are decoded from tags using struct/zlib. Excel values are
read directly from zipped worksheet XML. This script accesses only the two
already-open M1 runs and sensor calibration files. No measurement is corrected.
"""
import argparse
import hashlib
from io import BytesIO
import itertools
import json
from pathlib import Path
import posixpath
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import zlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = ["M1_NMC_Unaged_R0_T25", "M1_NMC_Unaged_R3_T25"]
TYPES = {1:"i1", 2:"u1", 3:"<i2", 4:"<u2", 5:"<i4", 6:"<u4", 7:"<f4", 9:"<f8", 12:"<i8", 13:"<u8"}


def tags(blob):
    offset = 0
    while offset < len(blob):
        if len(blob)-offset < 8:
            raise ValueError("Truncated MAT tag")
        a, size = struct.unpack_from("<II", blob, offset)
        small, kind = a >> 16, a & 65535
        if small:
            if small > 4:
                raise ValueError("Invalid small MAT tag")
            yield kind, blob[offset+4:offset+4+small]
            offset += 8
        else:
            if offset+8+size > len(blob):
                raise ValueError("MAT payload outside file")
            yield kind, blob[offset+8:offset+8+size]
            offset += 8 + (size if kind == 15 else (size+7)//8*8)


def matrix(payload):
    if not payload:
        return None
    parts = list(tags(payload))
    flags = struct.unpack_from("<I", parts[0][1])[0]
    cls = flags & 255
    if flags & 0x800:
        raise ValueError("Complex arrays unsupported")
    if cls == 17:  # opaque: name, type system, class, actual array
        return {"opaque_class": parts[3][1].decode(), "value": matrix(parts[4][1])}
    dims = np.frombuffer(parts[1][1], dtype="<i4")
    shape = tuple(int(v) for v in dims)
    if cls == 1:
        return [matrix(p) for k,p in parts[3:] if k == 14]
    if cls == 2:
        width = struct.unpack("<i", parts[3][1])[0]
        names = [parts[4][1][i:i+width].split(b"\0")[0].decode() for i in range(0,len(parts[4][1]),width)]
        values = [matrix(p) for k,p in parts[5:] if k == 14]
        if int(np.prod(dims)) == 0:
            return {}
        if len(values) != len(names):
            raise ValueError("Only scalar structs supported")
        return dict(zip(names, values))
    if cls == 4:
        kind,p = parts[3]
        encoding = {1:"utf-8", 4:"utf-16le", 16:"utf-8", 17:"utf-16le", 18:"utf-32le"}.get(kind)
        if encoding is None:
            raise ValueError("Unsupported character encoding")
        return p.decode(encoding)
    if len(parts) < 4:
        return np.empty(shape)
    kind,p = parts[3]
    if kind not in TYPES:
        raise ValueError(f"Unsupported MAT numeric type {kind}")
    return np.frombuffer(p, dtype=TYPES[kind]).reshape(shape, order="F").ravel(order="F")


def top_arrays(blob):
    for kind,payload in tags(blob):
        if kind == 15:
            yield from top_arrays(zlib.decompress(payload))
        elif kind == 14:
            yield matrix(payload)
        else:
            raise ValueError("Unexpected top-level MAT element")


def independent_table(blob):
    if blob[126:128] != b"IM":
        raise ValueError("Expected little-endian MAT5")
    work = [a for a in top_arrays(blob[128:]) if isinstance(a,np.ndarray) and a.dtype == np.uint8 and len(a)>1000]
    if len(work) != 1 or work[0].tobytes()[:8] != b"\x00\x01IM\0\0\0\0":
        raise ValueError("Expected one MCOS subsystem")
    root = next(top_arrays(work[0].tobytes()[8:]))
    wrapper = root["MCOS"]
    if wrapper["opaque_class"] != "FileWrapper__":
        raise ValueError("Unsupported wrapper")
    pool = wrapper["value"]
    # Identify a unique cell vector of numeric channel vectors and matching labels.
    numeric = [x for x in pool if isinstance(x,list) and len(x) in (9,15)
               and all(isinstance(v,np.ndarray) and v.dtype.kind in "fiu" and len(v)>100 for v in x)]
    labels = [x for x in pool if isinstance(x,list) and all(isinstance(v,str) for v in x)
              and x and x[0] == "Test_Times"]
    if len(numeric) != 1 or len(labels) != 1 or len(numeric[0]) != len(labels[0]):
        raise ValueError("Unrecognized numeric-table schema")
    if len({len(v) for v in numeric[0]}) != 1 or len(set(labels[0])) != len(labels[0]):
        raise ValueError("Unequal channel lengths or duplicate headers")
    return dict(zip(labels[0], numeric[0]))


def raw_xml(blob):
    ns = {"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(blob)) as z:
        shared = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(x.itertext()) for x in shared.findall("s:si", ns)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = next(s for s in wb.find("s:sheets",ns) if s.attrib["name"] == "Data")
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(x.attrib["Target"] for x in rels if x.attrib["Id"] == rid)
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/"+target)
        headers, columns, source_rows = {}, {}, []
        for _,row in ET.iterparse(z.open(path), events=("end",)):
            if row.tag != "{"+ns["s"]+"}row":
                continue
            values = {}
            for c in row:
                col = "".join(v for v in c.attrib["r"] if v.isalpha())
                v = c.find("s:v",ns)
                value = None if v is None else v.text
                values[col] = strings[int(value)] if c.attrib.get("t") == "s" else (float(value) if value is not None else np.nan)
            if not headers:
                headers = values
                columns = {v:[] for v in headers.values()}
            else:
                source_rows.append(int(row.attrib["r"]))
                for col,name in headers.items():
                    columns[name].append(values.get(col,np.nan))
            row.clear()
    return {k:np.asarray(v) for k,v in columns.items()}, np.asarray(source_rows)


def stats(x):
    x = np.asarray(x)
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite input: do not silently reduce the residual population")
    return {"mean_A":float(np.mean(x)), "rms_A":float(np.sqrt(np.mean(x*x))), "max_abs_A":float(np.max(abs(x)))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path)
    p.add_argument("--output",type=Path,default=Path("reports/reconciliation"))
    args = p.parse_args()
    archives = list(Path.cwd().glob("Full factorial*.zip"))
    archive = args.archive or (archives[0] if len(archives)==1 else None)
    if archive is None:
        raise ValueError("Pass --archive")
    args.output.mkdir(parents=True, exist_ok=True)
    result = {"implementation":"struct/zlib MAT5 + direct XLSX XML; no voltforge/SciPy/pandas readers",
              "runs":{}, "accessed_members":[], "calibrations":{}}
    with ZipFile(archive) as z:
        def read(base):
            matches = [n for n in z.namelist() if n.endswith("/"+base)]
            if len(matches)!=1:
                raise ValueError(base)
            b = z.read(matches[0])
            result["accessed_members"].append({"member":matches[0],"sha256":hashlib.sha256(b).hexdigest()})
            return b
        hall = {}
        for i in range(1,9):
            h = independent_table(read(f"H{i}_Calibration.mat"))
            x,y = h["HallVoltage"],h["CurrentA"]
            slope,intercept = np.linalg.lstsq(np.column_stack([x,np.ones(len(x))]),y,rcond=None)[0]
            hall[i] = (float(slope),float(intercept))
            result["calibrations"][str(i)] = dict(slope_A_per_V=float(slope),intercept_A=float(intercept),
                calibration_residual=stats(slope*x+intercept-y))
        for run in RUNS:
            raw,rows = raw_xml(read(run+".xlsx"))
            mat = independent_table(read(run+".mat"))
            t,cur,step = raw["Test_Time(s)"],raw["Current(A)"],raw["Step_Index"]
            comparisons = {}
            pairs = [("Test_Time(s)","Test_Times"),("Step_Time(s)","Step_Times"),("Step_Index","Step_Index"),
                     ("Cycle_Index","Cycle_Index"),("Voltage(V)","VoltageV"),("Current(A)","CurrentA")]
            for i in range(1,6):
                label = next(k for k in raw if k.startswith("Aux_Temperature(") and k.endswith(f"_{i}"))
                pairs.append((label,f"TemperatureC_Cell_{i}" if i<5 else "Ambient_TemperatureC"))
            for a,b in pairs:
                comparisons[a+" -> "+b] = {"equal":bool(np.array_equal(raw[a],mat[b])),
                                           "max_abs_difference":float(np.max(abs(raw[a]-mat[b])))}
            if not all(x["equal"] for x in comparisons.values()):
                raise ValueError("Independent channel/time agreement failed")
            branches = np.column_stack([mat[f"CurrentA_Cell_{i}"] for i in range(1,5)])
            # Minimal residual in source polarity, then one global sign conversion.
            residual = -(branches.sum(axis=1)-cur)
            dis = step == 5
            sign_checks = {str(signs):stats(-(branches[dis] @ np.asarray(signs)-cur[dis]))
                           for signs in itertools.product([1,-1],repeat=4)}
            lag_checks = {str(lag):stats(-(branches.sum(axis=1)[max(lag,0):len(t)+min(lag,0)]-
                cur[max(-lag,0):len(t)+min(-lag,0)])) for lag in range(-10,11)}
            mapping_matrix = [[stats(-(slope*raw[f"Aux_Voltage(V)_{i}"]+intercept-mat[f"CurrentA_Cell_{i}"]))["rms_A"]
                               for slope,intercept in hall.values()] for i in range(1,5)]
            q = raw["Discharge_Capacity(Ah)"][dis]
            report = dict(rows=len(t), source_discharge_rows=[int(rows[dis][0]),int(rows[dis][-1])],
                timestamp_check=dict(backwards=int(np.sum(np.diff(t)<0)),duplicates=int(np.sum(np.diff(t)==0)),
                    minimum_interval_s=float(np.min(np.diff(t))),median_interval_s=float(np.median(np.diff(t))),
                    maximum_interval_s=float(np.max(np.diff(t))),intervals_above_provisional_1_5s=int(np.sum(np.diff(t)>1.5))),
                column_labels=list(mat), shared_channels=comparisons, source_sign="positive charge; step 5 module and all four branches negative",
                discharge_source_sign_confirmed=bool(np.all(cur[dis]<0) and np.all(branches[dis]<0)),
                full=stats(residual), discharge=stats(residual[dis]),
                by_step={str(int(s)):stats(residual[step==s]) for s in np.unique(step)},
                sign_hypotheses=sign_checks, time_shift_samples=lag_checks,
                branch_unit_factor_hypotheses={str(f):stats(-(f*branches[dis].sum(axis=1)-cur[dis])) for f in [0.001,1,1000]},
                permutation_note="Any permutation of the four branches leaves their sum unchanged; cannot explain this residual.",
                author_branch_vs_candidate_H1_to_H8_RMS_A=mapping_matrix,
                nominal_sensor_mapping="M1 local positions 1..4 -> H1..H4 per article; H5..H8 tested as mislabelling hypotheses only, no reassignment",
                module_discharge_integral_Ah=float(np.trapz(-cur[dis],t[dis])/3600),
                raw_cycler_discharge_capacity_increment_Ah=float(q[-1]-q[0]),
                raw_cycler_capacity_caveat="Same cycler, not an independent current reference",
                wall_minus_test_elapsed_max_abs_s=float(np.max(abs((raw["Date_Time"]-raw["Date_Time"][0])*86400-(t-t[0])))))
            result["runs"][run] = report
            np.savetxt(args.output/(run+"_residual.csv"),np.column_stack([rows,np.arange(1,len(rows)+1),t,-cur,-branches.sum(axis=1),residual]),
                delimiter=",",header="source_xlsx_row,source_mat_row,time_s,module_discharge_A,branch_sum_discharge_A,residual_A",comments="")
            fig,axes = plt.subplots(2,1,figsize=(10,6),layout="constrained")
            axes[0].plot(t/3600,-cur,label="Module reference (uncertain)",lw=1)
            axes[0].plot(t/3600,-branches.sum(axis=1),label="Author Hall sum (uncertain)",lw=.8)
            axes[0].set(ylabel="Discharge current [A]",title=run+" | independent byte/XML calculation")
            axes[0].legend();axes[1].plot(t/3600,residual,lw=.7,color="#a13d2d")
            axes[1].axhline(0,color="black",lw=.6);axes[1].set(xlabel="Elapsed time [h]",ylabel="Branch sum - module [A]")
            fig.savefig(args.output/(run+"_independent.png"),dpi=150);plt.close(fig)
            print(run,report["discharge"],flush=True)
    (args.output/"independent_results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
