"""Private runtime import boundary; never consults user Python or Codex."""
import json,os,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
import site
import import_pyav,import_ctranslate2
for module in (import_pyav,import_ctranslate2):
 component=module.component_path(root)
 if component.exists() and module.valid(root):
  site.addsitedir(str(component))
try:
 current=json.loads((root/'current.json').read_text(encoding='utf8'))
 app=(root/current['path']).resolve()
 if (root/'versions').resolve() not in app.parents:raise ValueError('Invalid version root')
 if (root/'config/config.json').exists():os.environ.setdefault('LECTURE_CONFIG',str(root/'config/config.json'))
 sys.path[:0]=[str(app),str(app/'gui_v1.8'),str(app/'dialogue_v1.6')]
except FileNotFoundError:
 pass
