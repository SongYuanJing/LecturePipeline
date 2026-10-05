"""Phase 2a: manual, code-only tagged Releases updates. No runtime or data migration."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile

import download_components as downloads
from update_state import atomic, idle_sessions, idle_workers, journal, locked, recover

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = 'SongYuanJing/LecturePipeline'
API = 'https://api.github.com/repos/'+REPOSITORY+'/releases'
MANIFEST = 'LecturePipeline-update.json'
RUNTIME_FILES = ('runtime/asr/component.json', 'runtime/document/component.json',
    'launcher/pyav-manifest.json', 'launcher/ctranslate2-manifest.json',
    'launcher/model-manifest.json', 'launcher/cuda-manifest.json')


def version(value):
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?', value)
    if not match:
        raise ValueError('Unsupported release version: '+str(value))
    pre = match[4]
    identifiers = pre.split('.') if pre else []
    if any(not x or (x.isdigit() and len(x)>1 and x[0]=='0') for x in identifiers):
        raise ValueError('Invalid prerelease version')
    return (*map(int, match.group(1,2,3)), (0, tuple((0,int(x)) if x.isdigit() else (1,x) for x in identifiers)) if pre else (1,))


def releases():
    rows = []
    for page in range(1, 6):
        request = urllib.request.Request(API+'?per_page=100&page='+str(page), headers={
            'Accept':'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28',
            'User-Agent':'LecturePipeline-updater'})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(4_000_001)
        if len(raw)>4_000_000:
            raise ValueError('Release metadata too large')
        items = json.loads(raw)
        if not isinstance(items,list):
            raise ValueError('Invalid GitHub Releases response')
        rows.extend(items)
        if len(items)<100:
            return rows
    raise ValueError('Release listing limit reached; no incomplete discovery used')


def discover(current, rows):
    candidates = []
    for row in rows:
        tag = row.get('tag_name','')
        if row.get('draft') or not tag.startswith('v'):
            continue
        try:
            key = version(tag[1:])
        except ValueError:
            continue
        if '-' not in current and (row.get('prerelease') or '-' in tag):
            continue
        if key > version(current):
            candidates.append((key,row))
    return max(candidates, key=lambda x:x[0])[1] if candidates else None


def asset(release, name):
    downloads.filename(name)
    found = [a for a in release.get('assets',[]) if a.get('name')==name]
    if len(found)!=1:
        raise ValueError('Release asset missing/duplicated: '+name)
    value = found[0]
    expected = 'https://github.com/'+REPOSITORY+'/releases/download/'+release['tag_name']+'/'+name
    if value.get('browser_download_url')!=expected or value.get('state')!='uploaded':
        raise ValueError('Expected tagged repository asset')
    digest = value.get('digest','') or ''
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):
        raise ValueError('GitHub asset SHA-256 digest required: '+name)
    if type(value.get('size')) is not int or not 0<value['size']<=2_000_000_000:
        raise ValueError('Invalid asset size')
    return dict(url=expected,name=name,sha256=digest[7:],bytes=value['size'])


def runtime_contract(root):
    return {name:downloads.digest(Path(root)/name) for name in RUNTIME_FILES}


def obtain(root, item, progress):
    return downloads.fetch(item['url'],item['sha256'],item['name'],Path(root)/'cache/updates',
        limit=item['bytes'],expected_size=item['bytes'],progress=progress)


def manifest(root, release, progress):
    pin = asset(release, MANIFEST)
    if pin['bytes']>1_000_000:
        raise ValueError('Update manifest too large')
    value = json.loads(obtain(root,pin,progress).read_text(encoding='utf8'))
    app_version = release['tag_name'][1:]; version(app_version)
    required = dict(schema_version=1, repository=REPOSITORY, tag=release['tag_name'],
        app_version=app_version,platform='win-x64',updater_protocol=1,
        config_schema_version=1,migration_required=False)
    if any(value.get(k)!=v for k,v in required.items()):
        raise ValueError('Incompatible release manifest; runtime/data migration is not supported')
    if value.get('runtime_contract') != runtime_contract(root):
        raise ValueError('Update requires a different private runtime/components; current install preserved')
    item = asset(release, value['artifact']['name'])
    if value['artifact'] != {k:item[k] for k in ('name','bytes','sha256')}:
        raise ValueError('Manifest/GitHub artifact identity mismatch')
    return value, item


def safe_path(root, name):
    path = PurePosixPath(name)
    if ('\\' in name or path.is_absolute() or not path.parts or
            any(p in ('.','..') or p.endswith(('.', ' ')) or ':' in p for p in path.parts)):
        raise ValueError('Unsafe version archive path')
    for part in path.parts:
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise ValueError('Reserved archive path')
    target = (Path(root)/str(path)).resolve()
    if Path(root).resolve() not in target.parents:
        raise ValueError('Archive path escapes version')
    return target


def verify_version(app, expected):
    release = json.loads((app/'release.json').read_text(encoding='utf8'))
    if (release.get('app_version')!=expected or release.get('updater_protocol')!=1
            or release.get('config_schema_version')!=1 or release.get('migration_required') is not False):
        raise ValueError('Incompatible version contract')
    files = release['files']
    if not {'pipeline_config.py','gui_v1.8/app.py'}<=files.keys():
        raise ValueError('Missing application entry points')
    actual = {p.relative_to(app).as_posix() for p in app.rglob('*') if p.is_file()}
    if actual != set(files)|{'release.json'}:
        raise ValueError('Version file inventory mismatch')
    for name, pin in files.items():
        if downloads.digest(safe_path(app,name))!=pin:
            raise ValueError('Version SHA256 mismatch: '+name)


def stage(root, archive, app_version):
    root=Path(root); (root/'versions').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage-',dir=root/'versions') as temporary:
        app=Path(temporary); seen=set(); size=0
        with zipfile.ZipFile(archive) as bundle:
            if len(bundle.infolist())>10000:
                raise ValueError('Too many version files')
            for entry in bundle.infolist():
                if entry.is_dir():continue
                path=safe_path(app,entry.filename); key=entry.filename.casefold()
                if key in seen or (entry.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('Duplicate/symlink version entry')
                seen.add(key); size+=entry.file_size
                if size>256*1024*1024:
                    raise ValueError('Version exceeds code-only size limit')
                path.parent.mkdir(parents=True,exist_ok=True)
                with bundle.open(entry) as source,path.open('xb') as output:
                    shutil.copyfileobj(source,output)
        verify_version(app,app_version)
        health(root,app)
        destination=root/'versions'/app_version
        if destination.exists():
            verify_version(destination,app_version)
            if (destination/'release.json').read_bytes()!=(app/'release.json').read_bytes():
                raise ValueError('Existing version differs; preserved')
        else:
            app.rename(destination)
        return destination


def health(root, app):
    result=subprocess.run([str(Path(root)/'runtime/asr/python.exe'),'-B','-X','utf8',
        str(Path(root)/'launcher/update_health.py'),str(app)],capture_output=True,text=True,
        encoding='utf8',errors='replace',timeout=90,creationflags=0x08000000 if os.name=='nt' else 0)
    if result.returncode:
        raise RuntimeError('Staged health failed: '+(result.stderr or result.stdout)[-1500:])
    if json.loads(result.stdout).get('ok') is not True:
        raise RuntimeError('Staged health did not confirm readiness')


def first_launch(root, state):
    env=dict(os.environ,LP_UPDATE_TOKEN=state['token'])
    process=subprocess.Popen([str(root/'runtime/asr/pythonw.exe'),'-B','-X','utf8',
        str(root/'launcher/launch.py'),'gui'],env=env,cwd=root)
    receipt=root/'run'/('update-ready-'+state['token']+'.json')
    try:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('New GUI exited before readiness')
            if receipt.exists():
                ready=json.loads(receipt.read_text(encoding='utf8'))
                if ready!=dict(token=state['token'],version=state['next']['app_version'],pid=process.pid):
                    raise RuntimeError('Invalid first-launch receipt')
                # Catch failures immediately following Tk initialization.
                time.sleep(2)
                if process.poll() is not None:raise RuntimeError('New GUI failed after initialization')
                return process.pid
            time.sleep(0.1)
        raise RuntimeError('New GUI readiness timeout')
    except BaseException:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
        raise
    finally:receipt.unlink(missing_ok=True)


def apply(root, release, progress=print):
    root=Path(root).resolve()
    with locked(root/'run/update.lock'):
        recover(root)
        with idle_sessions(root),idle_workers(root):
            current=json.loads((root/'current.json').read_text(encoding='utf8'))
            if version(release['tag_name'][1:])<=version(current['app_version']):
                return dict(status='no-update',current=current['app_version'])
            value,item=manifest(root,release,progress)
            progress('Скачать / проверить версию…');archive=obtain(root,item,progress)
            progress('Stage / health check…');destination=stage(root,archive,value['app_version'])
            state=dict(previous=base64.b64encode((root/'current.json').read_bytes()).decode(),
                next=dict(app_version=value['app_version'],path=destination.relative_to(root).as_posix()),token=uuid.uuid4().hex)
            atomic(journal(root),state)
            try:
                atomic(root/'current.json',state['next'])
                progress('Первый запуск новой версии…');pid=first_launch(root,state)
                journal(root).unlink()
                return dict(status='updated',previous=current['app_version'],current=value['app_version'],application_pid=pid)
            except BaseException:
                atomic(root/'current.json',base64.b64decode(state['previous']))
                journal(root).unlink(missing_ok=True)
                raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('check','apply','recover'))
    parser.add_argument('--tag')
    args=parser.parse_args()
    if args.command=='recover':
        with locked(ROOT/'run/update.lock'):print(json.dumps(dict(recovered=recover(ROOT))))
        return
    from launch import app_root
    app_root(ROOT)
    current=json.loads((ROOT/'current.json').read_text())['app_version']
    rows=releases()
    if args.command=='check':
        release=discover(current,rows)
        print(json.dumps(dict(current=current,tag=release['tag_name'] if release else None,
            status='available' if release else 'no-update'),ensure_ascii=False));return
    found=[r for r in rows if r.get('tag_name')==args.tag and not r.get('draft')]
    if len(found)!=1:raise ValueError('Specify an existing tagged release from CheckUpdates')
    print(json.dumps(apply(ROOT,found[0]),ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as exc:print('Update failed; previous version retained: '+str(exc),file=sys.stderr);raise SystemExit(1)
