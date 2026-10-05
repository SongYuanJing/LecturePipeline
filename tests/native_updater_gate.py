"""Explicit Windows-only disposable gate. Fixture transport only; health/GUI are real.

Run with development Python: --prepare <new-name-under-TEMP> <qualified-base>.
The base is read-only; only immutable runtime/model files are hardlinked. New
config, empty Word/vocabulary/workspace data are created in the disposable root.
"""
import base64,ctypes,hashlib,io,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'installer'),str(REPO/'scripts')]
import build_update


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def snapshot(root,data):
    return {('config' if p==root/'config/config.json' else 'data/'+p.relative_to(data).as_posix()):
        dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns) for p in [root/'config/config.json',*sorted(data.rglob('*'))] if p.is_file()}


def window(pid,close=False):
    user=ctypes.windll.user32;matches=[]
    callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
    @callback
    def visit(hwnd,_):
        owner=ctypes.c_ulong();user.GetWindowThreadProcessId(ctypes.c_void_p(hwnd),ctypes.byref(owner))
        if owner.value==pid:
            buf=ctypes.create_unicode_buffer(512);user.GetWindowTextW(ctypes.c_void_p(hwnd),buf,512)
            if buf.value.startswith('Lecture Pipeline · '):
                matches.append(buf.value)
                if close:user.PostMessageW(ctypes.c_void_p(hwnd),0x10,0,0)
        return True
    user.EnumWindows(visit,0)
    return matches


def prepare(name,source):
    if not name.startswith('LP2a-') or Path(name).name!=name:raise ValueError('Disposable gate name required')
    gate=Path(os.environ['TEMP']).resolve()/name;gate.mkdir(exist_ok=False)
    root=gate/'Программа 课程';root.mkdir();source=Path(source).resolve()
    for part in ('runtime','models'):
        shutil.copytree(source/part,root/part,copy_function=os.link)
    shutil.copytree(REPO/'installer',root/'launcher',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(REPO/'config.example.json',root/'launcher/config.example.json')
    for path in (REPO/'components').glob('*-manifest.json'):shutil.copy2(path,root/'launcher'/path.name)
    inventory=json.loads((source/'package-manifest.json').read_text(encoding='utf8'))
    files={n:h for n,h in inventory['files'].items() if n.startswith(('runtime/asr/','runtime/document/'))}
    files.update({p.relative_to(root).as_posix():sha(p) for p in (root/'launcher').rglob('*') if p.is_file()})
    (root/'package-manifest.json').write_text(json.dumps(dict(manifest_schema_version=1,files=files)))
    build_update.build(REPO/'src/app',root,gate/'baseline-artifact','1.9.5-beta.1')
    app=root/'versions/1.9.5-beta.1';app.mkdir(parents=True)
    with zipfile.ZipFile(next((gate/'baseline-artifact').glob('*.zip'))) as z:z.extractall(app)
    (root/'current.json').write_text(json.dumps(dict(app_version='1.9.5-beta.1',path='versions/1.9.5-beta.1')))
    data=gate/'Данные 课程'
    subprocess.run([str(root/'runtime/asr/python.exe'),'-B','-X','utf8',str(root/'launcher/setup.py'),
        '--data-root',str(data),'--device-mode','cpu'],check=True)
    subprocess.run([str(root/'runtime/document/python.exe'),'-B','-c',
        "from docx import Document;import sys;d=Document();d.add_paragraph('Disposable fixture lecture');d.save(sys.argv[1])",
        str(data/'semester-1/SUBJECT/word/fixture.docx')],check=True)
    subprocess.run([str(root/'runtime/asr/python.exe'),'-B','-X','utf8',str(Path(__file__)), '--run',str(gate)],check=True)


def run(gate):
    assert gate.parent==Path(os.environ['TEMP']).resolve() and gate.name.startswith('LP2a-')
    root=gate/'Программа 课程';data=gate/'Данные 课程'
    sys.path.insert(0,str(root/'launcher'))
    # build_update imported the development module; reload from the installed shell.
    for name in ('updater','update_state','download_components'):sys.modules.pop(name,None)
    import updater as u
    import update_state as state
    before=snapshot(root,data);evidence=dict(gate='%TEMP%/'+gate.name,transport='disposable in-memory HTTP fixture; real downloader, health subprocess and GUI',events=[])
    payload={};requests=[];interrupted=set()
    class Response(io.BytesIO):
        def __init__(self,url,headers=None):
            offset=int((headers or {}).get('Range','bytes=0-')[6:-1]);requests.append(dict(name=url.rsplit('/',1)[-1],offset=offset))
            super().__init__(payload[url][offset:]);self.url=url;self.status=206 if offset else 200
            self.fail=url.endswith('fixture.1.zip') and url not in interrupted
            if self.fail:interrupted.add(url)
            self.headers={'Content-Length':str(len(payload[url])-offset),'ETag':'"fixture"'}
            if offset:self.headers['Content-Range']=f'bytes {offset}-{len(payload[url])-1}/{len(payload[url])}'
        def geturl(self):return self.url
        def read(self,size):
            if self.fail and self.tell():raise TimeoutError('deliberate fixture interruption')
            return super().read(min(size,65536))
    def release(number,broken=None):
        version='1.9.6-fixture.'+str(number);src=gate/('source-'+str(number))
        shutil.copytree(REPO/'src/app',src,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if broken=='health':(src/'fixture_broken.py').write_text('syntax error !!!')
        if broken=='launch':(src/'gui_v1.8/adapter.py').write_text("raise RuntimeError('fixture GUI initialization failure')\n")
        out=gate/('release-'+str(number));build_update.build(src,root,out,version)
        row=dict(tag_name='v'+version,draft=False,prerelease=True,assets=[])
        for path in out.iterdir():
            url='https://github.com/'+u.REPOSITORY+'/releases/download/'+row['tag_name']+'/'+path.name
            payload[url]=path.read_bytes();row['assets'].append(dict(name=path.name,state='uploaded',size=path.stat().st_size,digest='sha256:'+sha(path),browser_download_url=url))
        return row
    def close(pid):
        title=window(pid,True);assert title,'Main GUI was not found'
        for _ in range(100):
            if not window(pid):break
            time.sleep(.1)
        time.sleep(.3)
        return title
    def log(message):evidence['events'].append(message);print(message,flush=True)
    with patch.object(u.downloads,'open_url',side_effect=lambda url,headers=None:Response(url,headers)):
        good=release(1);start=time.monotonic();result=u.apply(root,good,log)
        evidence['switch']=dict(result,seconds=time.monotonic()-start,window=window(result['application_pid']))
        assert evidence['switch']['window']==['Lecture Pipeline · 1.9.6-fixture.1']
        previous=(root/'current.json').read_bytes()
        try:u.apply(root,release(2,'launch'),log)
        except RuntimeError:evidence['live_gui_blocks_switch']=True
        else:raise AssertionError('Live GUI failed to block switch')
        close(result['application_pid'])
        # Reuse the already built failed-launch release contract.
        bad=dict(tag_name='v1.9.6-fixture.2',draft=False,prerelease=True,assets=[])
        for path in (gate/'release-2').iterdir():
            url='https://github.com/'+u.REPOSITORY+'/releases/download/'+bad['tag_name']+'/'+path.name
            bad['assets'].append(dict(name=path.name,state='uploaded',size=path.stat().st_size,digest='sha256:'+sha(path),browser_download_url=url))
        try:
            unexpected=u.apply(root,bad,log)
        except RuntimeError as exc:evidence['failed_first_launch']=str(exc)
        else:
            close(unexpected['application_pid']);raise AssertionError('Broken GUI initialization was accepted')
        assert (root/'current.json').read_bytes()==previous
        evidence['first_launch_rollback_exact']=True
        try:u.apply(root,release(3,'health'),log)
        except RuntimeError as exc:evidence['staged_health_failure']=str(exc)[-500:]
        else:raise AssertionError('Broken stage accepted')
        assert (root/'current.json').read_bytes()==previous
        evidence['staged_failure_pointer_unchanged']=True
        state.atomic(state.journal(root),dict(previous=base64.b64encode(previous).decode(),token='fixture-crash'))
        state.atomic(root/'current.json',dict(app_version='1.9.6-fixture.2',path='versions/1.9.6-fixture.2'))
        with state.locked(root/'run/update.lock'):assert state.recover(root)
        evidence['crash_recovery_exact']=(root/'current.json').read_bytes()==previous
        with patch.object(u.downloads,'open_url',side_effect=AssertionError('Unexpected network')):
            assert u.apply(root,good,log)['status']=='no-update'
            value,item=u.manifest(root,good,log);u.obtain(root,item,log)
        evidence['verified_cache_reused']=True
    assert snapshot(root,data)==before
    evidence['config_data_unchanged']=True;evidence['preserved_files']=before
    evidence['old_version_retained']=(root/'versions/1.9.5-beta.1').is_dir()
    evidence['current']=json.loads(previous)
    evidence['download_requests']=requests
    assert any(r['offset']==65536 for r in requests),'Small update ZIP did not resume'
    process=subprocess.Popen([str(root/'runtime/asr/pythonw.exe'),'-B','-X','utf8',str(root/'launcher/launch.py'),'gui'])
    deadline=time.monotonic()+45
    while not window(process.pid) and time.monotonic()<deadline and process.poll() is None:time.sleep(.1)
    evidence['recovered_gui']=close(process.pid);process.wait(timeout=10)
    assert evidence['recovered_gui']==['Lecture Pipeline · 1.9.6-fixture.1']
    assert snapshot(root,data)==before
    text=json.dumps(evidence,ensure_ascii=False,indent=2).replace(str(root),'%INSTALL%').replace(str(gate),'%GATE%')
    (gate/'evidence.json').write_text(text+'\n',encoding='utf8')
    print('NATIVE UPDATER GATE PASSED',flush=True)


if __name__=='__main__':
    if sys.argv[1]=='--prepare':prepare(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=='--run':run(Path(sys.argv[2]).resolve())
    else:raise SystemExit('Explicit --prepare or --run required')
