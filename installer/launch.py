"""Stable launcher boundary. Worker processes outlive the GUI."""
import json,os,runpy,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def app_root(root=ROOT):
 current=json.loads((root/'current.json').read_text(encoding='utf8'));app=(root/current['path']).resolve()
 if (root/'versions').resolve() not in app.parents:raise ValueError('Invalid current version path')
 manifest=json.loads((app/'release.json').read_text(encoding='utf8'))
 if manifest['app_version']!=current['app_version']:raise ValueError('Version manifest mismatch')
 for name,h in manifest['files'].items():
  p=(app/name).resolve()
  if app not in p.parents or hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('Release checksum mismatch: '+name)
 return app
def run():
 state=ROOT/'bootstrap-state.json'
 if state.exists() and json.loads(state.read_text(encoding='utf8')).get('status')!='ready':
  raise RuntimeError('Установка не завершена. Запустите Setup.exe и нажмите Retry. Проверенные файлы сохранены.')
 mode=sys.argv[1] if len(sys.argv)>1 else 'gui';app=app_root();cfg=ROOT/'config/config.json'
 if mode=='gui' and not cfg.exists():
  from setup_gui import first_run
  if not first_run(ROOT):return 0
 if mode!='gui' and (ROOT/'launcher/pyav-manifest.json').exists():
  from component_status import require_components
  require_components(ROOT)
 if not cfg.exists():raise RuntimeError('First run: execute Setup.cmd and choose a data root. No existing data is modified automatically.')
 os.environ['LP_APP_VERSION']=json.loads((app/'release.json').read_text(encoding='utf8'))['app_version']
 os.environ['LECTURE_CONFIG']=str(cfg);os.environ['PYTHONNOUSERSITE']='1'
 sys.path[:0]=[str(app),str(app/'gui_v1.8'),str(app/'dialogue_v1.6')]
 from pipeline_config import Config,require_preflight
 c=Config(cfg)
 if c.install!=app:raise ValueError('Config/current version mismatch; no automatic migration')
 if mode=='preflight':
  from pipeline_config import preflight
  result=preflight(c);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ok'] else 2
 if mode!='gui':require_preflight(c)
 entry={'gui':'gui_v1.8/app.py','lecture':'lecture_worker.py','dialogue':'dialogue_v1.6/dialogue_worker.py'}[mode]
 sys.argv=[str(app/entry)]+(['--config',str(cfg)] if mode in ('gui','dialogue') else [])
 runpy.run_path(str(app/entry),run_name='__main__');return 0
def main():
 from update_state import launch_session
 with launch_session(ROOT):return run()
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'logs/launch-error.txt').write_text(str(e),encoding='utf8')
  if (len(sys.argv)<2 or sys.argv[1]=='gui') and not os.environ.get('LP_UPDATE_TOKEN'):
   import tkinter as tk
   from tkinter import messagebox
   r=tk.Tk();r.withdraw();messagebox.showerror('Lecture Pipeline',str(e));r.destroy()
  else:print(str(e),file=sys.stderr)
  raise SystemExit(2)
