"""Send the four audit prompts through the AI route and print what each one produced."""
import json,sys,tempfile,time
from pathlib import Path
from voltforge.project import Project
from voltforge.studio.store import Studio
from voltforge.studio.copilot import Copilot
PROMPTS=['Build me a four cell battery in series using Samsung 30T cells for a small power tool drawing 5 amps for 10 minutes in a 30 degree workshop.', 'Make a two by two battery with Samsung 30T cells.', 'Build a four cell parallel LG M50T pack.', 'Create a three cell series battery.']
root=Path(tempfile.mkdtemp(prefix='vf-ai-'))/'project';Project.create_reference(root);studio=Studio(root);c=Copilot(studio);c.provider='Codex'
print('provider',c.provider,flush=True)
for p in PROMPTS:
    t=time.time()
    try:
        r=c.chat([dict(role='user',content=p)])
        prop=r.get('proposal')
        print(json.dumps(dict(prompt=p,seconds=round(time.time()-t),draft=bool(prop),cells=prop and prop['cell_count'],changes=prop and prop['changes'][:5],note=r['message'][-140:] if not prop else None)),flush=True)
    except Exception as e:print(json.dumps(dict(prompt=p,error=str(e)[:200])),flush=True)
