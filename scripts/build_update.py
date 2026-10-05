"""Build code-only update artifacts locally. Never creates a tag or publishes a release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'installer'))
import updater


def build(source, base, output, app_version):
    updater.version(app_version)
    output.mkdir(parents=True,exist_ok=False)
    files={p.relative_to(source).as_posix():p.read_bytes() for p in sorted(source.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='release.json'}
    release=dict(manifest_schema_version=1,updater_protocol=1,app_version=app_version,
        config_schema_version=1,migration_required=False,
        files={name:hashlib.sha256(data).hexdigest() for name,data in files.items()})
    files['release.json']=(json.dumps(release,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    archive=output/('LecturePipeline-app-'+app_version+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as stream:
        for name,data in sorted(files.items()):
            item=zipfile.ZipInfo(name,(2026,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
            stream.writestr(item,data)
    manifest=dict(schema_version=1,repository=updater.REPOSITORY,tag='v'+app_version,
        app_version=app_version,platform='win-x64',updater_protocol=1,config_schema_version=1,
        migration_required=False,runtime_contract=updater.runtime_contract(base),
        artifact=dict(name=archive.name,bytes=archive.stat().st_size,sha256=updater.downloads.digest(archive)))
    (output/updater.MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    print(json.dumps(build(REPO/'src/app',args.base,args.out,args.version),indent=2))
