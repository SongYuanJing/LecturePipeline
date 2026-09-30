"""Minimal explicit first-run bootstrap. Fresh workspace only, no silent adoption."""
import argparse,json,os,re,subprocess,uuid
from pathlib import Path
from launch import ROOT,app_root
def validate_runtimes(root):
 """Fail before creating user data if a package/native prerequisite is missing."""
 if (root/'launcher/pyav-manifest.json').exists():
  from component_status import require_components
  require_components(root)
 for kind,imports in (('asr','import tkinter,ctranslate2,faster_whisper,av'),('document','import docx,openpyxl,lxml.etree')):
  try:
   result=subprocess.run([str(root/'runtime'/kind/'python.exe'),'-B','-c',imports],capture_output=True,text=True,timeout=30,creationflags=0x08000000)
   if result.returncode:raise RuntimeError(result.stderr.strip()[-800:])
  except (OSError,subprocess.SubprocessError,RuntimeError) as exc:
   raise RuntimeError(kind+' runtime unavailable. Restore the complete package; for missing MSVC DLLs install the official Microsoft Visual C++ v14 x64 Redistributable. User data has not been initialized. '+str(exc)) from exc

def configure(root,data,workspace,subject,*,workspace_name=None,subject_name=None,language="zh"):
 if not data.is_absolute():raise ValueError('Выберите абсолютную папку данных')
 root=root.resolve();data=data.resolve();app=app_root(root)
 if root==data or root in data.parents or data in root.parents:raise ValueError('User data and application root must be separate')
 if not re.fullmatch('[A-Za-z0-9_-]+',workspace) or not re.fullmatch('[A-Za-z0-9_-]+',subject):raise ValueError('Workspace and subject IDs: letters, digits, - or _')
 if language not in ('zh','en','auto'):raise ValueError('Invalid lecture language')
 cfg=root/'config/config.json';wr=data/workspace
 if cfg.exists() or (data/'dictionary/vocabulary.xlsx').exists() or (data/'dialogue').exists() or (wr.exists() and any(wr.iterdir())):raise ValueError('Existing configuration/workspace: explicit migration required; nothing overwritten')
 validate_runtimes(root)
 template=json.loads((root/'launcher/config.example.json').read_text(encoding='utf8'))
 template.update(install_root=os.path.relpath(app,cfg.parent),application_home='..',data_root=str(data),active_workspace=workspace,task_prefix='LP-'+uuid.uuid4().hex[:12])
 w=template['workspaces'].pop('semester-1');w.update(name=workspace_name or workspace,folder=workspace,worker_home='run/workspaces/'+workspace);w['subjects'][0].update(subject_code=subject,subject_name=subject_name or subject,folder=subject,default_language=language)
 template['workspaces']={workspace:w};template['hidden_tasks']=[]
 for folder in ('audio','raw','word'):(wr/subject/folder).mkdir(parents=True,exist_ok=True)
 def new_json(p,obj):
  p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():raise FileExistsError(p)
  p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
 new_json(wr/'system/state.json',{'version':1,'lectures':{}});new_json(wr/'system/ai_state.json',{'schema_version':1,'processed':{}})
 for name in ('00 — Входящие аудио','01 — Расшифровки','02 — Word','99 — Служебное'):(data/'dialogue'/name).mkdir(parents=True,exist_ok=True)
 for name in ('logs/lecture','logs/gui','run/dialogue','run/ai_queue','run/workspaces/'+workspace):(root/name).mkdir(parents=True,exist_ok=True)
 new_json(root/'run/dialogue/dialogue_state.json',{'schema_version':1,'mode':'dialogue','jobs':{}})
 book=data/'dictionary/vocabulary.xlsx'
 if not book.exists():
  subprocess.run([str(root/'runtime/document/python.exe'),'-B',str(root/'launcher/create_dictionary.py'),str(book),str(app)],check=True,creationflags=0x08000000)
 else:raise ValueError('Existing dictionary: use explicit adoption, never overwrite')
 new_json(cfg,template);return cfg
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path);p.add_argument('--workspace',default='semester-1');p.add_argument('--subject',default='SUBJECT');a=p.parse_args()
 data=a.data_root or Path(input('Absolute data root (outside application): ').strip().strip('"'))
 if not data.is_absolute():raise SystemExit('Absolute path required')
 try:cfg=configure(ROOT,data,a.workspace,a.subject)
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:raise SystemExit('First run failed: '+str(exc))
 print('Config created: '+str(cfg));print('Run Preflight.cmd, then Integrate.cmd explicitly to create shortcuts/tasks. Workers are not started automatically.')
