"""Narrow, fail-closed reader for the inspected v2 MATLAB table serialization.

SciPy exposes these tables as opaque MCOS objects. Its MAT5 array reader can
decode the nested subsystem without executing MATLAB code. This adapter supports
ONLY the two observed layouts (one calibration table; two module tables and four
scalar cell-name strings), not arbitrary MATLAB objects. Private SciPy API use is
intentional and version-pinned. Raw Excel comparisons independently verify the
module numeric mapping. See reports/PARSER_NOTES.md.
"""
from io import BytesIO
import re

import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.io.matlab._mio5 import MatFile5Reader

MODULE_COLUMNS = [
    "Test_Times", "Step_Times", "Step_Index", "Cycle_Index", "VoltageV", "CurrentA",
    *[f"TemperatureC_Cell_{i}" for i in range(1, 5)], "Ambient_TemperatureC",
    *[f"CurrentA_Cell_{i}" for i in range(1, 5)],
]
HALL_COLUMNS = ["Test_Times", "Step_Times", "Step_Index", "Cycle_Index", "CurrentA",
                "HallVoltage", "PowerSupplyVoltage", "CellTempData", "AmbientTempData"]


def scalar_string(value):
    a = np.asarray(value)
    if a.dtype != np.dtype("uint64") or a.ndim != 1 or len(a) < 6:
        raise ValueError("Unsupported MCOS scalar string")
    if list(a[:4]) != [1, 2, 1, 1] or int(a[4]) not in (2, 3):
        raise ValueError("Unsupported cell-name string header")
    text = a[5:].astype("<u8").tobytes().decode("utf-16le")[:int(a[4])]
    if not re.fullmatch(r"(?:[PF][1-9][0-9]?|Y1|GS3)", text):
        raise ValueError(f"Unexpected cell identity: {text!r}")
    return text


def table_pool(blob):
    outer = loadmat(BytesIO(blob), simplify_cells=True)
    if "__function_workspace__" not in outer:
        raise ValueError("Missing MATLAB MCOS subsystem")
    work = outer["__function_workspace__"].tobytes()
    if work[:8] != b"\x00\x01IM\x00\x00\x00\x00":
        raise ValueError("Unsupported subsystem endian/version")
    stream = BytesIO(work)
    reader = MatFile5Reader(stream, byte_order="<", struct_as_record=False, squeeze_me=True)
    reader.initialize_read()
    stream.seek(8)
    header, next_position = reader.read_var_header()
    if header.mclass != 2 or list(header.dims) != [1, 1] or next_position > len(work):
        raise ValueError("Unexpected MCOS root")
    root = reader.read_var_array(header)
    mcos = getattr(root, "MCOS", None)
    if mcos is None or mcos.shape != (1,):
        raise ValueError("Missing MCOS wrapper")
    item = mcos[0]
    if item["s1"] != b"MCOS" or item["s2"] != b"FileWrapper__":
        raise ValueError("Unsupported MCOS wrapper")
    pool = item["arr"]
    if len(pool) not in (11, 22):
        raise ValueError(f"Uninspected MCOS layout: {len(pool)} slots")
    names = list(pool[7])
    expected = HALL_COLUMNS if len(pool) == 11 else MODULE_COLUMNS
    if names != expected or pool[3] != 2 or pool[6] != len(expected):
        raise ValueError("MCOS table labels/dimensions differ from inspected schema")
    if len(pool[2]) != len(expected):
        raise ValueError("MCOS column count mismatch")
    n = int(pool[4])
    if n <= 0 or any(np.asarray(c).shape != (n,) for c in pool[2]):
        raise ValueError("MCOS columns are not equal-length numeric vectors")
    if any(np.asarray(c).dtype.kind not in "fiu" for c in pool[2]):
        raise ValueError("Non-numeric MCOS measurement column")
    return pool


def module_mat(blob, metadata_only=False):
    pool = table_pool(blob)
    if len(pool) != 22 or list(pool[18]) != [f"Position_{i}" for i in range(1, 5)]:
        raise ValueError("Missing four-position cell-name table")
    if pool[14] != 2 or pool[15] != 1 or pool[17] != 4:
        raise ValueError("Unexpected cell-name table dimensions")
    refs = np.asarray(pool[13].tolist())
    expected = np.array([[3707764736, 2, 1, 1, i, 2] for i in range(3, 7)], dtype=np.uint32)
    if not np.array_equal(refs, expected):
        raise ValueError("Uninspected cell-name object-reference ordering")
    cells = [scalar_string(v) for v in pool[9:13]]
    if len(set(cells)) != 4:
        raise ValueError("Duplicate cell identity within a module")
    return (None if metadata_only else pd.DataFrame(dict(zip(pool[7], pool[2])))), cells


def hall_mat(blob):
    pool = table_pool(blob)
    if len(pool) != 11:
        raise ValueError("Expected one calibration table")
    return pd.DataFrame(dict(zip(pool[7], pool[2])))


def cell_mat(blob, protocol):
    d = loadmat(BytesIO(blob), simplify_cells=True)
    voltage = "OCV" if protocol == "pseudo_ocv" else "VoltageData"
    names = ["TimeData", "CurrentData", voltage, "TempData"]
    if protocol == "hppc_ms":
        names += ["StepIndex", "CycleIndex"]
    if any(k not in d for k in names):
        raise ValueError("Missing characterization array")
    arrays = {k: np.asarray(d[k]) for k in names}
    if any(a.ndim != 1 for a in arrays.values()) or len({len(a) for a in arrays.values()}) != 1:
        raise ValueError("Characterization array shape mismatch")
    return pd.DataFrame(arrays)
