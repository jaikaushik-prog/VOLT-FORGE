"""CLI: inventory once, then audit a predeclared development subset."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .archive import Archive, locate_archive, run_factors, sha256_file
from .inspection import inspect_module, inspect_cell, series_stats, time_audit, discharge_current
from .matlab import module_mat, hall_mat
from .plots import module_plots


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def validate_splits(splits, runs):
    seen = set()
    ids = {r["run_id"] for r in runs}
    for group in ["calibration", "development_validation", "final_assessment", "quarantine"]:
        members = splits[group]
        if len(set(members)) != len(members) or seen.intersection(members):
            raise ValueError("Split groups are not disjoint whole experiments")
        if not set(members).issubset(ids):
            raise ValueError("Split refers to missing experiments")
        seen.update(members)
    allowed = set(splits["calibration"] + splits["development_validation"])
    if not set(splits["initial_inspection"]).issubset(allowed):
        raise ValueError("Initial inspection would expose reserved/quarantined signals")
    for r in runs:
        if r["run_id"] in seen - set(splits["quarantine"]):
            if r["chemistry"] != "NMC" or r["ageing_label"] != "Unaged" or any(c in ("Y1", "GS3") for c in r["cells"]):
                raise ValueError("Split includes an aged or non-NMC module")


def inventory(root, archive, splits):
    reports = root / "reports"
    provenance = archive.provenance()
    records = archive.inventory()
    for record in records:
        record.update(source_url=provenance["source_url"], doi=provenance["doi"], version=2,
                      access_date=provenance["access_date"], archive_sha256=provenance["sha256"])
    by_name = {r["basename"]: r for r in records}
    runs = []
    article = pd.read_csv(root / "configs/nmc_article_table5.csv").set_index("run_id")
    for member in sorted(archive.names):
        if "/Processed_data/" not in member:
            continue
        stem = Path(member).stem
        row = run_factors(stem)
        _, cells = module_mat(archive.zip.read(member), metadata_only=True)
        row["cells"] = cells
        row["raw_member"] = archive.find(stem + ".xlsx")
        row["processed_member"] = member
        row["metadata_source"] = "Data_processed.Cells_name.Position_1..4; filenames for experimental factors"
        row["raw_sha256"] = by_name[stem + ".xlsx"]["sha256"]
        row["processed_sha256"] = by_name[stem + ".mat"]["sha256"]
        row["ageing_conflict"] = row["ageing_label"] == "Unaged" and any(c in ("Y1", "GS3") for c in cells)
        row["test_no_article"] = None
        if stem in article.index:
            a = article.loc[stem]
            row["test_no_article"] = int(a.test_no)
            row["article_cells_match"] = cells == [a[f"position_{i}"] for i in range(1, 5)]
        runs.append(row)
        by_name[stem + ".mat"]["content_inspection"] = "cell_identity_metadata_only; signals not audited except explicitly selected runs"
    validate_splits(splits, runs)
    observed = [(r["chemistry"], r["ageing_label"], r["interconnect_mohm"], r["ambient_setpoint_C"]) for r in runs]
    axes = {"chemistry": sorted({r["chemistry"] for r in runs}),
            "ageing_label": sorted({r["ageing_label"] for r in runs}),
            "interconnect_mohm": sorted({r["interconnect_mohm"] for r in runs}),
            "ambient_setpoint_C": sorted({r["ambient_setpoint_C"] for r in runs})}
    expected_count = int(np.prod([len(v) for v in axes.values()]))
    summary = dict(files=len(records), uncompressed_bytes=sum(r["bytes"] for r in records),
        counts_by_extension=dict(Counter(Path(r["basename"]).suffix for r in records)),
        module_experiments=len(runs), nmc_experiments=sum(r["chemistry"] == "NMC" for r in runs),
        factor_levels=axes, complete_filename_factorial=len(set(observed)) == len(observed) == expected_count,
        factorial_warning="Completeness by labels does not resolve the ageing conflict in row 32.",
        characterization_cells=sorted({Path(r["basename"]).stem.split("_")[-1] for r in records if r["basename"].startswith("OCVDis_")}),
        ageing_conflicts=[r["run_id"] for r in runs if r["ageing_conflict"]])
    bindings = {g: [{k:r[k] for k in ("run_id", "cells", "raw_sha256", "processed_sha256")}
                   for name in splits[g] for r in runs if r["run_id"] == name]
                for g in ("calibration", "development_validation", "final_assessment", "quarantine")}
    lock = dict(archive_sha256=provenance["sha256"], config_sha256=sha256_file(root / "configs/splits.json"), groups=bindings)
    lock_path = root / "configs/splits.lock.json"
    if lock_path.exists() and json.loads(lock_path.read_text()) != lock:
        raise ValueError("Frozen split binding changed. Review and explicitly version the manifest before proceeding.")
    dump(reports / "provenance.json", provenance)
    dump(reports / "file_inventory.json", records)
    dump(reports / "run_inventory.json", runs)
    dump(reports / "inventory_summary.json", summary)
    dump(lock_path, lock)
    pd.DataFrame([{**{k:v for k,v in r.items() if k != "cells"},
                   **{f"position_{i}":c for i,c in enumerate(r["cells"],1)}} for r in runs]).to_csv(reports / "run_inventory.csv", index=False)
    print(json.dumps(summary, indent=2))


def verify_lock(root, archive):
    lock_path = root / "configs/splits.lock.json"
    if not lock_path.exists():
        raise ValueError("Run inventory first to freeze archive and split hashes")
    lock = json.loads(lock_path.read_text())
    if lock["archive_sha256"] != sha256_file(archive.path) or lock["config_sha256"] != sha256_file(root / "configs/splits.json"):
        raise ValueError("Archive or frozen split manifest changed")


def sensor_audit(archive, sensor):
    frame = hall_mat(archive.read(f"H{sensor}_Calibration.mat"))
    x, y, vs = (frame[c].to_numpy() for c in ("HallVoltage", "CurrentA", "PowerSupplyVoltage"))
    models = {}
    for name, feature in [("hall_V", x), ("hall_over_supply", x/vs), ("hall_minus_half_supply_V", x-vs/2)]:
        finite = np.isfinite(feature) & np.isfinite(y)
        slope, intercept = np.polyfit(feature[finite], y[finite], 1)
        models[name] = dict(slope=float(slope), intercept=float(intercept),
            residual_A=series_stats(slope*feature+intercept-y))
    report = dict(sensor=sensor, timestamp=time_audit(frame.Test_Times, .1),
        channels={c:series_stats(frame[c]) for c in frame},
        exploratory_linear_maps=models,
        warning="OLS reconstructions are derived diagnostics, not the authors' undocumented processing code or an instrument uncertainty budget.")
    return report


def compare_calibration(frame, sensor_reports, module):
    comparisons = {}
    for position in range(1,5):
        sensor = position if module == "M1" else position+4
        report = sensor_reports[sensor]
        x, vs = frame[f"hall_{position}_V"].to_numpy(), frame.hall_supply_V.to_numpy()
        author = frame[f"branch_{position}_A"].to_numpy()
        comparisons[str(position)] = dict(sensor=sensor, models={})
        for name, feature in [("hall_V", x), ("hall_over_supply", x/vs), ("hall_minus_half_supply_V", x-vs/2)]:
            model = report["exploratory_linear_maps"][name]
            derived = discharge_current(model["slope"]*feature + model["intercept"], "charge")
            comparisons[str(position)]["models"][name] = dict(
                derived_minus_author_A=series_stats(derived-author))
    return comparisons


def write_dictionary(root, module_reports):
    records = []
    for run, report in module_reports.items():
        for source in report["metadata"]["raw_headers"]:
            records.append(dict(run_id=run, source_container="raw Excel Data sheet", source_field=source,
                missing_rows=report["raw_missing_values"][source],
                values=report["raw_missing_values"][source] < report["timestamp"]["rows"]))
    dump(root / "reports/actual_raw_columns.json", records)


def audit(root, archive, splits, selected):
    verify_lock(root, archive)
    if not selected:
        selected = splits["initial_inspection"]
    allowed = set(splits["calibration"] + splits["development_validation"])
    if not set(selected).issubset(allowed):
        raise ValueError("Signal audit restricted to declared calibration/development runs; final/quarantined runs remain closed")
    provenance = json.loads((root / "reports/provenance.json").read_text())
    inventory = {r["basename"]: r for r in json.loads((root / "reports/file_inventory.json").read_text())}
    reports, all_cells, sensors = {}, set(), {}
    for run in selected:
        for sensor in (range(1,5) if run.startswith("M1_") else range(5,9)):
            if sensor not in sensors:
                sensors[sensor] = sensor_audit(archive, sensor)
        frame, report = inspect_module(archive, run)
        report["raw_source"] = inventory[run+".xlsx"]
        report["author_processed_source"] = inventory[run+".mat"]
        report["calibration_reconstruction_comparison"] = compare_calibration(frame, sensors, run[:2])
        reports[run] = report
        all_cells.update(report["cells"])
        out = root / "data/processed" / run
        out.mkdir(parents=True, exist_ok=True)
        frame.to_csv(out / "module.csv", index=False)
        dump(out / "provenance.json", dict(data_class="derived_from_measurements", run_id=run,
            archive_sha256=provenance["sha256"], raw_sha256=inventory[run+".xlsx"]["sha256"],
            author_processed_sha256=inventory[run+".mat"]["sha256"],
            conversions="Seconds, volts and Celsius unchanged; all currents multiplied by -1 for positive discharge.",
            branch_source="Author-calibrated measured currents, not independently validated calibration",
            source_rows="source_xlsx_row: 1-based Data worksheet including header; source_mat_row: 1-based Data_processed.Data row",
            source_retrieval_url=provenance["source_url"], dataset_doi=provenance["doi"], cells=report["cells"]))
        module_plots(frame, run, report["cells"], root / "reports/plots")
        print(f"Audited {run}: {len(frame)} rows; cells {report['cells']}", flush=True)
    char_reports = []
    for cell in sorted(all_cells):
        for protocol in ("pseudo_ocv", "hppc_ms"):
            frame, report = inspect_cell(archive, cell, protocol)
            report["source"] = inventory[report["source_file"]]
            out = root / "data/processed/characterization"
            out.mkdir(parents=True, exist_ok=True)
            frame.to_csv(out / f"{cell}_{protocol}.csv", index=False)
            char_reports.append(report)
    capacities = {r["cell_id"]:r.get("observed_discharge_integral_Ah") for r in char_reports if r["protocol"] == "pseudo_ocv"}
    for report in reports.values():
        values = [capacities[c] for c in report["cells"]]
        report["sum_separate_cell_C20_integrals_Ah"] = sum(values) if all(v is not None for v in values) else None
        report["capacity_comparison_caveat"] = "Different rates, 23C cell characterization versus 25C module setpoint, and different charging protocols; discrepancy prompts investigation, not an automatic rescaling."
    dump(root / "reports/module_audit.json", reports)
    dump(root / "reports/characterization_audit.json", char_reports)
    dump(root / "reports/hall_calibration_audit.json", sensors)
    write_dictionary(root, reports)
    dump(root / "reports/audit_scope.json", dict(audited_runs=selected, characterized_cells=sorted(all_cells),
        sensors=list(sensors), final_assessment_signals_inspected=False,
        data_class="measured data and explicitly identified derived diagnostics; no synthetic measured results",
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version, archive_sha256=provenance["sha256"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "audit", "all"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--runs", nargs="+")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    archive = Archive(args.archive or locate_archive(root))
    try:
        splits = json.loads((root / "configs/splits.json").read_text())
        if args.command in ("inventory", "all"):
            inventory(root, archive, splits)
        if args.command in ("audit", "all"):
            audit(root, archive, splits, args.runs)
    finally:
        archive.close()


if __name__ == "__main__":
    main()
