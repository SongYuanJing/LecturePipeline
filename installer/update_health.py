"""Read-only staged-code health in the existing private Python. No config projection file."""
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parent.parent
app=Path(sys.argv[1]).resolve()
if (root/'versions').resolve() not in app.parents:
    raise ValueError('Health requires a staged/versioned application')
sys.path[:0]=[str(app),str(app/'gui_v1.8'),str(app/'dialogue_v1.6')]
for path in app.rglob('*.py'):
    compile(path.read_bytes(),str(path),'exec')
from pipeline_config import Config, preflight
import app as gui
result=preflight(Config(root/'config/config.json',code_root=app),probe_gpu=False)
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result['ok'] else 2)
