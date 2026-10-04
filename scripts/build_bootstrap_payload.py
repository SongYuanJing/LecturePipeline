"""Build source-only payload; private runtime is fetched by Setup from pinned release."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_package import VERSION

def build(repo, output):
    files = {}
    for source, prefix in ((repo/'src/app', 'versions/'+VERSION), (repo/'installer', 'launcher')):
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and path.name != 'uninstall.py':
                files[prefix+'/'+path.relative_to(source).as_posix()] = path.read_bytes()
    def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    prefix = 'versions/'+VERSION+'/'
    files[prefix+'release.json'] = encoded(dict(manifest_schema_version=1,app_version=VERSION,
        config_schema_version=1,migration_required=False,
        files={n[len(prefix):]:hashlib.sha256(v).hexdigest() for n,v in files.items() if n.startswith(prefix)}))
    files['current.json'] = encoded(dict(app_version=VERSION,path='versions/'+VERSION))
    files['launcher/config.example.json'] = (repo/'config.example.json').read_bytes()
    for path in sorted((repo/'components').glob('*-manifest.json')):
        files['launcher/'+path.name] = path.read_bytes()
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output/'application.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,value)
    (output/'application.json').write_bytes(encoded(dict(app_version=VERSION,
        files={n:hashlib.sha256(v).hexdigest() for n,v in files.items()})))
    print('Source payload bytes:',(output/'application.zip').stat().st_size)

if __name__=='__main__':
    repo=Path(__file__).resolve().parents[1]
    build(repo,repo/'bootstrap/payload')
