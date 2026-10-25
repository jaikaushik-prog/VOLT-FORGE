"""Generate actual adapter responses in a new, disposable software-test project."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from voltforge.project import Project
from evidence_context import build_context, context_digest


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


def generate(out):
    out = Path(out).resolve()
    if not out.is_relative_to(ROOT / "tmp") or out.exists():
        raise ValueError("Choose a new output directory under repository tmp/")
    out.mkdir(parents=True)
    examples = out / "examples"
    examples.mkdir()
    project = Project.create_reference(out / "working_project")

    def load(current):
        project.apply_edit("A0", dict(target="scenario", id="module", property="load_profile",
            value=[dict(start_s=0., end_s=2., current_A=current)], unit="A,s",
            source="Declared two-second software fixture; not experimental evidence", classification="assumed"),
            project.inspect()["revision_id"])

    checks = []

    def capture(name, **selection):
        before = hashes(project.path)
        request = dict(variant_id="A0", run_id=None, component_id="module", limit=2)
        request.update(selection)
        response = build_context(project.path, **request)
        assert hashes(project.path) == before, "Read-only adapter changed the project"
        if response["status"] == "ok":
            assert response["result"]["context_id"] == context_digest(response["result"])
        save(examples / (name + ".json"), dict(call="build_context", arguments=request, response=response))
        checks.append(dict(example=name, status=response["status"], read_only=True,
                           project_index_sha256=before["project.json"]))
        return response

    load(14.55)
    capture("01_configuration")
    complete = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    capture("02_current_cell", run_id=complete["run_id"], component_id="cell_1")
    project.create_variant("A0", "A1", "Inherited evidence example", project.inspect()["revision_id"])
    capture("03_inherited", variant_id="A1", run_id=complete["run_id"])
    load(100000.)
    capture("04_outdated", run_id=complete["run_id"])
    failed = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    capture("05_failed_partial", run_id=failed["run_id"])
    capture("06_unsupported", component_id="temperature")
    save(out / "receipt.json", dict(schema="voltforge.backend_context_examples/1", checks=checks,
        fixture="LG frozen-v2 software-only shortened load and deliberate out-of-domain failure",
        experimental_validation="awaiting suitable measurements",
        examples_sha256=hashes(examples)))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    print(generate(parser.parse_args().out))
