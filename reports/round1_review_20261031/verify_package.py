"""Verify review-package bytes; no scientific or software acceptance claim."""
from pathlib import Path
import hashlib
import json


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    failures = []
    for name, expected in manifest["artifacts_sha256"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(f"Missing or invalid path: {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"Changed: {name}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(json.dumps({"status": "review_package_bytes_verified",
                      "files": len(manifest["artifacts_sha256"]),
                      "reviewed_source_commit": manifest["reviewed_source_commit"],
                      "meaning": "Package integrity only; not model or module validation"}, indent=2))


if __name__ == "__main__":
    main()
