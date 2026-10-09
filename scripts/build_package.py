"""Deterministic portable ZIP from source and validated private components. No download."""
import argparse,hashlib,json,shutil,zipfile,sys
from pathlib import Path
VERSION='1.9.7-beta.2'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from public_exclusions import forbidden,check,check_zip
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def build(repo,components,out):
 if out.exists():raise ValueError('Use a new output root')
 out.mkdir(parents=True);app=out/'versions'/VERSION
 shutil.copytree(repo/'src/app',app,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 write(app/'release.json',dict(manifest_schema_version=1,updater_protocol=1,app_version=VERSION,baseline='v1.8.1',distribution_status='beta',config_schema_version=1,data_schema_version={'lecture':1,'dialogue':1,'ai_state':1,'dictionary':'1.4'},migration_required=False,files={p.relative_to(app).as_posix():sha(p) for p in sorted(app.rglob('*')) if p.is_file()}))
 shutil.copytree(repo/'installer',out/'launcher',ignore=shutil.ignore_patterns('__pycache__','*.pyc','uninstall.py'))
 for name in ('config.example.json',):shutil.copy2(repo/name,out/'launcher'/name)
 for name in ('model-manifest.json','cuda-manifest.json','pyav-manifest.json','ctranslate2-manifest.json'):
  if (repo/'components'/name).exists():shutil.copy2(repo/'components'/name,out/'launcher'/name)
 for kind in ('asr','document'):
  source=components/kind;m=json.loads((source/'component.json').read_text())
  for name,info in m['files'].items():
   if sha(source/name)!=info['sha256']:raise ValueError('Runtime hash mismatch: '+name)
  shutil.copytree(source,out/'runtime'/kind)
  if kind=='asr':
   private=out/'runtime'/kind
   for p in sorted(private.rglob('*'),key=lambda p:len(p.parts),reverse=True):
    if p.is_file() and forbidden(p.relative_to(out).as_posix()):p.unlink()
   for p in sorted(private.rglob('*'),key=lambda p:len(p.parts),reverse=True):
    if p.is_dir() and not any(p.iterdir()):p.rmdir()
   # Replace source-component inventory: it must describe shipped files only.
   write(private/'component.json',dict(kind='asr-thin',files={p.relative_to(private).as_posix():{'sha256':sha(p)} for p in private.rglob('*') if p.is_file() and p.name!='component.json'}))
 write(out/'current.json',dict(app_version=VERSION,path='versions/'+VERSION))
 for name,script in [('Setup','setup.py'),('Preflight','launch.py preflight'),('CheckUpdates','updater.py check'),('Update','updater.py apply --tag'),('ImportModel','import_model.py'),('ImportPyAV','import_pyav.py'),('ImportCTranslate2','import_ctranslate2.py'),('ImportCUDA','import_cuda.py'),('Components','component_status.py'),('DownloadComponents','download_components.py')]:
  entry,*args=script.split();(out/(name+'.cmd')).write_text('@echo off\r\n"%~dp0runtime\\asr\\python.exe" -B -X utf8 "%~dp0launcher\\'+entry+'" '+ ' '.join(args)+' %*\r\n',encoding='ascii')
 for name,script in [('Integrate','Integrate.ps1'),('Uninstall','Uninstall.ps1')]:
  (out/(name+'.cmd')).write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\\'+script+'" %*\r\n',encoding='ascii')
 (out/'Lecture Pipeline.vbs').write_text('Set fso=CreateObject("Scripting.FileSystemObject")\r\nroot=fso.GetParentFolderName(WScript.ScriptFullName)\r\nSet sh=CreateObject("WScript.Shell")\r\nsh.Run Chr(34) & root & "\\runtime\\asr\\pythonw.exe" & Chr(34) & " -B -X utf8 " & Chr(34) & root & "\\launcher\\launch.py" & Chr(34) & " gui", 0, False\r\n',encoding='ascii')
 if (repo/'docs').exists():shutil.copytree(repo/'docs',out/'docs')
 if (repo/'third_party').exists():shutil.copytree(repo/'third_party',out/'third_party')
 for name in ('README.md','PACKAGING.md','CHANGELOG.md','THIRD_PARTY_NOTICES.md','ARCHITECTURE.md','DEVELOPMENT_PLAYBOOK.md','BACKLOG.md'):
  if (repo/name).exists():shutil.copy2(repo/name,out/name)
 check(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
 write(out/'package-manifest.json',dict(manifest_schema_version=1,app_version=VERSION,files={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}))
 archive=out.parent/(out.name+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(out.rglob('*')):
   if p.is_file():
    info=zipfile.ZipInfo(p.relative_to(out).as_posix(),(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(info,p.read_bytes())
 check_zip(archive)
 result=dict(app_version=VERSION,archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(json.loads((out/'package-manifest.json').read_text())['files']))
 write(archive.with_suffix('.sha256.json'),result);print(json.dumps(result));return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--components',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(Path(__file__).resolve().parent.parent,a.components,a.out)
