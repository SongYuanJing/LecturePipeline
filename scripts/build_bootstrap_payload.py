"""Build source-only payload; private runtime is fetched by Setup from pinned release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_package import VERSION

def build(repo, output, *, version=VERSION, desktop_bin=None):
    if desktop_bin and version == VERSION:
        raise ValueError('Unified DEV must not reuse accepted beta.4 identity')
    files = {}
    for source, prefix in ((repo/'src/app', 'versions/'+version), (repo/'installer', 'launcher')):
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and path.name != 'uninstall.py':
                files[prefix+'/'+path.relative_to(source).as_posix()] = path.read_bytes()
    if desktop_bin:
        ui = repo/'src/gui_web'
        prefix = 'versions/'+version+'/gui_web/'
        for name in ('readonly_host.py','readonly_snapshot.py','desktop_runner.py'):
            files[prefix+name] = (ui/name).read_bytes()
        for path in sorted((ui/'web').iterdir()):
            if path.is_file():files[prefix+'web/'+path.name] = path.read_bytes()
        for path in sorted(Path(desktop_bin).iterdir()):
            if path.is_file():files[prefix+'native/'+path.name] = path.read_bytes()
        for name in ('LecturePipelineDesktop.exe','LecturePipelineDesktop.exe.config','Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll','WebView2Loader.dll','LecturePipeline-A-dark.ico','LecturePipeline-A-light.ico'):
            if prefix+'native/'+name not in files:raise ValueError('Missing desktop component: '+name)
    def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    prefix = 'versions/'+version+'/'
    files[prefix+'release.json'] = encoded(dict(manifest_schema_version=1,updater_protocol=1,app_version=version,
        config_schema_version=1,migration_required=False,distribution_status='dev' if desktop_bin else 'beta',
        files={n[len(prefix):]:hashlib.sha256(v).hexdigest() for n,v in files.items() if n.startswith(prefix)}))
    files['current.json'] = encoded(dict(app_version=version,path='versions/'+version))
    files['launcher/config.example.json'] = (repo/'config.example.json').read_bytes()
    for name,command in (('CheckUpdates','check'),('Update','apply --tag')):
        files[name+'.cmd']=('@echo off\r\n"%~dp0runtime\\asr\\python.exe" -B -X utf8 "%~dp0launcher\\updater.py" '+command+' %*\r\n').encode('ascii')
    if desktop_bin:
        for name,mode in (('Lecture Pipeline.vbs','dashboard'),('Lecture Pipeline DEV.vbs','dashboard'),('Lecture Pipeline (Tk).vbs','gui')):
            files[name]=('Set fso=CreateObject("Scripting.FileSystemObject")\r\nroot=fso.GetParentFolderName(WScript.ScriptFullName)\r\nSet sh=CreateObject("WScript.Shell")\r\nsh.Run Chr(34) & root & "\\runtime\\asr\\pythonw.exe" & Chr(34) & " -B -X utf8 " & Chr(34) & root & "\\launcher\\launch.py" & Chr(34) & " '+mode+'", 0, False\r\n').encode('ascii')
    for path in sorted((repo/'components').glob('*-manifest.json')):
        files['launcher/'+path.name] = path.read_bytes()
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output/'application.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,value)
    (output/'application.json').write_bytes(encoded(dict(app_version=version,
        files={n:hashlib.sha256(v).hexdigest() for n,v in files.items()})))
    print('Source payload bytes:',(output/'application.zip').stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path)
    parser.add_argument('--version',default=VERSION)
    parser.add_argument('--desktop-bin',type=Path)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    build(repo,args.out or repo/'bootstrap/payload',version=args.version,desktop_bin=args.desktop_bin)
