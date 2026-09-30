"""Fast regression runner. Requires a disposable configured candidate, never defaults to production."""
import argparse,os,sys,unittest,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--pattern',default='test*.py');a=p.parse_args()
repo=Path(__file__).resolve().parent.parent
os.environ['LECTURE_CONFIG']=str(a.config.resolve());os.environ['PACKAGING_REPO']=str(repo)
d=json.loads(a.config.read_text(encoding='utf-8-sig'));app=(a.config.parent/d['install_root']).resolve()
sys.path[:0]=[str(repo/'tests'),str(app),str(app/'dialogue_v1.6'),str(app/'gui_v1.8')]
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(repo/'tests'),pattern=a.pattern))
raise SystemExit(0 if result.wasSuccessful() else 1)
