"""Verify the combined engineering handoff and preserved prior evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(folder))

from demonstrate_copilot_handoff import require, sha, verify_saved, write
from verify_p45b_local_dynamics import verify as verify_physics


def check_artifacts(receipt, key, replacements=None):
    replacements = replacements or {}
    for name, expected in receipt[key].items():
        path = ROOT / replacements.get(name, name)
        require(sha(path) == expected, "Preservation failure: " + name)
    return len(receipt[key])


def verify(tests):
    previous = json.loads((ROOT / "reports/p45b_identifiability_v1/verification.json").read_text())
    preserved = check_artifacts(previous, "artifacts", {"README.md": "reports/parallel_engineering_v1/previous/README.md"})
    backend = json.loads((ROOT / "reports/backend_context_v1/verification.json").read_text())
    backend_count = check_artifacts(backend, "artifacts_sha256")
    copilot = json.loads((ROOT / "reports/copilot_contract_v1/verification.json").read_text())
    copilot_count = check_artifacts(copilot, "implementation_and_receipt_sha256")
    demo = verify_saved(ROOT / "reports/parallel_engineering_v1/demo_001")
    physics = verify_physics(ROOT / "reports/p45b_local_dynamics_v1/run_001")
    suites = ET.parse(tests).getroot().findall("testsuite")
    require(bool(suites), "Missing JUnit test suites")
    for suite in suites:
        require(all(int(suite.get(key, "0")) == 0 for key in ("failures", "errors", "skipped")), "Incomplete or failing tests")
    passed = sum(int(suite.get("tests")) for suite in suites)
    require(passed > 0, "No tests recorded")
    # Capture new source/report artifacts and the living README only after the
    # agents and orchestrator have completed their documentation. Do not change
    # old receipts or replace a failed/incomplete attempt.
    folders = ["reports/backend_context_v1", "reports/copilot_contract_v1",
               "reports/p45b_local_dynamics_v1", "reports/parallel_engineering_v1"]
    files = [p for folder in folders for p in (ROOT / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts
             and p != ROOT / "reports/parallel_engineering_v1/verification.json"]
    names = ["README.md", "configs/ae_p45b_local_dynamics_v1.json",
             "scripts/ae_p45b_local_dynamics.py", "scripts/verify_p45b_local_dynamics.py",
             "scripts/evidence_context.py", "scripts/copilot_contract.py",
             "scripts/demonstrate_copilot_handoff.py", "scripts/verify_parallel_engineering.py",
             "tests/test_evidence_context.py", "tests/test_copilot_contract.py",
             "tests/test_ae_p45b_local_dynamics.py"]
    files += [ROOT / name for name in names]
    return dict(schema="voltforge.parallel_engineering_verification/1", status="passed",
                tests=dict(passed=passed, receipt=str(tests.resolve().relative_to(ROOT)), sha256=sha(tests)),
                previous_stage_artifacts_preserved=preserved,
                backend_receipt_artifacts_checked=backend_count,
                copilot_receipt_artifacts_checked=copilot_count,
                integration=demo, electrical_diagnostics=physics,
                frozen_models_changed=False, new_measurement_outcomes_opened=0,
                experimental_module_validation="awaiting suitable measurements",
                artifacts_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", type=Path, default=ROOT / "reports/parallel_engineering_v1/pytest.xml")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(any(out.is_relative_to(ROOT / name) for name in ("tmp", "reports/parallel_engineering_v1")),
            "Choose a new path under tmp/ or reports/parallel_engineering_v1/")
    require(not out.exists(), "Use a new verification path")
    receipt = verify(args.tests)
    write(out, receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != "artifacts_sha256"}, indent=2))


if __name__ == "__main__":
    main()
