from pathlib import Path
import json, sys
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    raise SystemExit("Usage: python replay.py RUN_ID")
manifest = json.loads((root / "export_manifest.json").read_text(encoding="utf-8"))
if sys.argv[1] not in manifest["run_software"]:
    raise SystemExit("Run is not in this export")
sid = manifest["run_software"][sys.argv[1]]
sys.path.insert(0, str(root / "software" / sid / "src"))
from voltforge.project.replay import replay
print(json.dumps(replay(root, sys.argv[1]), indent=2, allow_nan=False))
