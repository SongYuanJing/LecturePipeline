"""Build private components from explicit, verified local CPython inputs.

No venv, registry dependency, downloads or personal paths in emitted manifests.
"""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def copy_tree(source,dest):
 shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc','site-packages','test','tests'),dirs_exist_ok=True)
def build(base,site,dest,version,packages=None):
 if dest.exists():raise ValueError('Runtime destination already exists')
 dest.mkdir(parents=True)
 for folder in ('Lib','DLLs','tcl'):copy_tree(base/folder,dest/folder)
 for p in base.iterdir():
  if p.is_file() and (p.suffix.lower()=='.dll' or p.name in ('python.exe','pythonw.exe','LICENSE.txt')):shutil.copy2(p,dest/p.name)
 target=dest/'Lib/site-packages';target.mkdir()
 for p in site.iterdir():
  if p.name=='__pycache__' or p.suffix in ('.pyc','.pth'):continue
  if packages and not any(p.name.lower().startswith(n) for n in packages):continue
  if p.is_dir():shutil.copytree(p,target/p.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','tests'))
  else:shutil.copy2(p,target/p.name)
 (dest/('python'+version+'._pth')).write_text('Lib\nDLLs\nLib/site-packages\n../../launcher\nimport site\n',encoding='ascii')
 code='import sys,json,importlib.metadata as m;print(json.dumps({"version":sys.version,"packages":{d.metadata["Name"]:d.version for d in m.distributions()}}))'
 observed=json.loads(subprocess.check_output([str(dest/'python.exe'),'-B','-c',code],text=True))
 files={p.relative_to(dest).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 manifest=dict(schema_version=1,component='cpython-'+version,observed=observed,files=files)
 (dest/'component.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 return dict(files=len(files),bytes=sum(x['bytes'] for x in files.values()),**observed)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--asr-base',type=Path,required=True);p.add_argument('--asr-site',type=Path,required=True);p.add_argument('--document-base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 result={'asr':build(a.asr_base,a.asr_site,a.out/'asr','311'),'document':build(a.document_base,a.document_base/'Lib/site-packages',a.out/'document','312',('docx','python_docx','lxml','openpyxl','et_xmlfile','typing_extensions'))}
 (a.out/'runtime-summary.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
