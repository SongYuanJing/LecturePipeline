"""Test-only Windows subprocess kill harness. No production failpoint switches.

ASR/AI are fixtures; real durable services, filesystem and child termination.
Every parent run owns a new Temp root; original source files are never removed.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import wave

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'src/app'),str(REPO/'src/app/gui_v1.8')]

def child(base,action,point,serve=False):
    os.environ['LECTURE_CONFIG']=str(base/'app/config.json')
    from pipeline_config import Config
    import lecture_pipeline as p
    import lecture_worker as w
    import lecture_inbox as inbox_module
    import ai_queue as aq
    import ai_finalize
    c=Config(os.environ['LECTURE_CONFIG'])
    def hit(name):
        if point!=name:return
        aq.atomic(base/'hit.json',dict(point=name,pid=os.getpid()))
        while True:time.sleep(.1)  # Parent uses TerminateProcess, no finally cleanup.
    with ExitStack() as stack:
        queue_atomic=aq.atomic
        def handoff_atomic(path,value):
            result=queue_atomic(path,value)
            if Path(path).name.startswith('.manual-handoff-') and value.get('lecture_key'):hit('reservation')
            return result
        stack.enter_context(patch.object(aq,'atomic',handoff_atomic))
        original=inbox_module.Inbox.save
        def save(obj,state):
            original(obj,state)
            if any(r.get('lecture_key') for section in ('sources','groups') for r in state.get(section,{}).values()):hit('reservation')
        stack.enter_context(patch.object(inbox_module.Inbox,'save',save))
        import human_ux as ux
        copying=ux.shutil.copy2;copied=0
        def copy(src,dest,*a,**kw):
            nonlocal copied
            result=copying(src,dest,*a,**kw)
            if Path(dest).parent.name.startswith('.ingest-'):
                copied+=1
                if copied==2:hit('mid_copy')
            return result
        stack.enter_context(patch.object(ux.shutil,'copy2',copy))
        prepare=p.prepare_ready
        def ready(*a,**kw):
            hit('copy');result=prepare(*a,**kw);hit('ready');return result
        stack.enter_context(patch.object(p,'prepare_ready',ready))
        state_save=p.save_state
        def state(path,value):
            if Path(path).name=='state.json' and 'worker_spool' in str(path):hit('spool_commit')
            if Path(path)==c.state and value.get('lectures'):hit('raw_publication')
            return state_save(path,value)
        stack.enter_context(patch.object(p,'save_state',state))
        atomic=w.atomic_json
        def worker_atomic(path,value):
            result=atomic(path,value)
            if Path(path).name=='publish.json':hit('publish_plan')
            return result
        stack.enter_context(patch.object(w,'atomic_json',worker_atomic))
        def recognize(*a,**kw):
            with (base/'asr-calls.txt').open('a') as f:f.write('call\n');f.flush();os.fsync(f.fileno())
            hit('during_asr')
            return [(0,1,'测试内容')],SimpleNamespace(language='zh')
        stack.enter_context(patch.object(p,'WhisperModel',return_value=object()))
        stack.enter_context(patch.object(p,'transcribe_one',recognize))
        stack.enter_context(patch.object(p,'safe_print'))
        bundle=aq.bundle
        def bundled(*a,**kw):
            result=bundle(*a,**kw);hit('ai_packet');return result
        stack.enter_context(patch.object(aq,'bundle',bundled))
        persist=aq.persist
        def persisted(config,q):
            if any(t['status']=='ai_result_ready' for t in q['tasks'].values()):hit('ai_result')
            return persist(config,q)
        stack.enter_context(patch.object(aq,'persist',persisted))
        transition=aq.transition
        def transitioned(*a,**kw):
            result=transition(*a,**kw)
            if a[2]=='completed':hit('completion')
            return result
        stack.enter_context(patch.object(aq,'transition',transitioned))
        module=aq.module
        def word_module(config):
            word=module(config);build=word.build;render=word.render_word
            def rendered(*a,**kw):
                result=render(*a,**kw);hit('during_word');return result
            def built(*a,**kw):
                result=build(*a,**kw);hit('word_publication');return result
            word.render_word=rendered;word.build=built;return word
        stack.enter_context(patch.object(aq,'module',word_module))
        if action=='inbox':
            if base.name.startswith('manual-'):
                ux.add_lecture(c,'SUBJECT','2026-10-10',ux.next_number(c,'SUBJECT'),sorted((base/'Audio 课程').glob('*.wav')))
            else:
                ticks=[0];producer=inbox_module.Inbox(c,monotonic=lambda:ticks[0])
                for _ in range(8):ticks[0]+=5;producer.scan()
        elif action=='worker':
            worker=w.Worker(c.worker_home,stable_seconds=0)
            # AI indexing is exercised separately at its own crash boundary.
            with patch.object(aq,'refresh',return_value={}):
                for _ in range(2):worker.cycle()
                while serve:worker.cycle();time.sleep(1)
        else:
            q=aq.refresh(c);assert len(q['tasks'])==1,q
            identity,task=next(iter(q['tasks'].items()))
            if action=='ai':return
            answer=base/'answer.json'
            if not answer.exists():
                packet=aq.verify_packet(Path(task['source_packet']).parent);word=aq.module(c)
                block=dict(text='Fixture',basis='transcript',refs=[dict(start='1:1',end='1:1')])
                content=dict(schema_version=1,input_hashes=packet['input_hashes'],title='Fixture',organization={k:dict(status='not_found',items=[]) for k in word.ORG},summary=[block],notes=[block],definitions=[block],formulas=[],emphasis=[block],uncertainties=[],part_review=[dict(part=i+1,status='usable',note='fixture') for i in range(len(packet['manifest']['outputs']))],vocabulary=[])
                aq.atomic(answer,content)
            if action=='result':
                if task['status']=='waiting_ai':aq.accept_result(c,identity,answer)
            elif action=='final':ai_finalize.finalize(c,identity,answer)


def run(base,action,point='',serve=False):
    log=base/(action+'-'+(point or 'normal')+'.log')
    with log.open('w',encoding='utf8') as output:
        proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--child',str(base),'--action',action,'--point',point],stdout=output,stderr=subprocess.STDOUT)
        if point:
            end=time.monotonic()+45
            while not (base/'hit.json').exists() and proc.poll() is None and time.monotonic()<end:time.sleep(.05)
            assert (base/'hit.json').exists(),log.read_text(encoding='utf8')
            marker=json.loads((base/'hit.json').read_text());assert marker['pid']==proc.pid
            proc.kill();proc.wait(timeout=10)
            assert proc.returncode!=0
            return dict(point=point,pid=proc.pid,exit_code=proc.returncode)
        assert proc.wait(timeout=60)==0,log.read_text(encoding='utf8')

def snapshot(paths):
    return {str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns) for p in paths if p.is_file()}

def parent(only=None):
    from test_local_finalize import fixture
    from lecture_inbox import bind
    import ai_queue as aq
    root=Path(tempfile.mkdtemp(prefix='LP-vic12-'));print('Gate root:',root,flush=True)
    results=[]
    cases=[('single-reservation','inbox','reservation',1),('multipart-reservation','inbox','reservation',4),
           ('multipart-midcopy','inbox','mid_copy',4),('multipart-copy','inbox','copy',4),
           ('single-ready','inbox','ready',1),('multipart-ready','inbox','ready',4),
           ('asr','worker','during_asr',1),('spool','worker','spool_commit',1),
           ('plan','worker','publish_plan',1),('raw','worker','raw_publication',1),
           ('packet','ai','ai_packet',1),('result','result','ai_result',1),
           ('word-stage','final','during_word',1),('word','final','word_publication',1),
           ('complete','final','completion',1),('manual-reservation','inbox','reservation',1),
           ('manual-midcopy','inbox','mid_copy',4),('manual-ready','inbox','ready',1)]
    if only:cases=[case for case in cases if case[0] in only.split(',')]
    actions=['inbox','worker','ai','result','final']
    for name,action,point,count in cases:
        base=root/name;base.mkdir();c=fixture(base);source=base/'Audio 课程';source.mkdir()
        c=bind(c,'SUBJECT',source,base/'Results 课程',settle=10,poll=5)
        if name.startswith('manual-'):
            from pipeline_config import Config
            data=c.data;data['workspaces'][c.active]['subjects'][0]['inbox']['enabled']=False
            aq.atomic(c.path,data);c=Config(c.path)
        for n in range(1,count+1):
            filename=f'Test20261010_{n}.wav' if count>1 else 'Test20261010.wav'
            with wave.open(str(source/filename),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(bytes([n,0])*1600)
        original=snapshot(source.iterdir());config=snapshot([c.path])
        for stage in actions[:actions.index(action)]:run(base,stage)
        killed=run(base,action,point)
        if name.startswith('manual-'):
            reserved=sorted({aq.read(p)['lecture_key'] for p in c.subjects()['SUBJECT']['audio_dir'].glob('.manual-handoff-*.json')})
        else:
            journal=json.loads((c.worker_home/'inbox.json').read_text(encoding='utf8'))
            reserved=sorted({r['lecture_key'] for section in ('sources','groups') for r in journal.get(section,{}).values() if r.get('lecture_key')})
        for stage in actions[actions.index(action):]:run(base,stage)
        s=c.subjects()['SUBJECT'];ready=list(s['audio_dir'].glob('*.READY.json'));raw=list(s['raw_dir'].glob('*/*_manifest.json'));words=[p for p in s['ready_dir'].glob('*/lecture.docx') if not p.parent.name.startswith('.')]
        assert len(ready)==len(raw)==len(words)==1,(name,ready,raw,words)
        r=json.loads(ready[0].read_text(encoding='utf8'));assert reserved==[r['lecture']] and len(r['files'])==count
        final=snapshot([*ready,*s['raw_dir'].rglob('*'),*s['ready_dir'].rglob('*')])
        for stage in actions:run(base,stage)
        assert final==snapshot([*ready,*s['raw_dir'].rglob('*'),*s['ready_dir'].rglob('*')]),name
        assert original==snapshot(source.iterdir()) and config==snapshot([c.path])
        q=aq.load_queue(c);assert len(q['tasks'])==1 and next(iter(q['tasks'].values()))['status']=='completed'
        state=json.loads(c.state.read_text(encoding='utf8'));ai=json.loads(c.ai_state.read_text(encoding='utf8'))
        assert len(state['lectures'])==len(ai['processed'])==1
        calls=len((base/'asr-calls.txt').read_text().splitlines());assert calls==count+(1 if point=='during_asr' else 0),(name,calls)
        results.append(dict(case=name,killed=killed,key=r['lecture'],parts=count,asr_calls=calls,ready_sha256=hashlib.sha256(ready[0].read_bytes()).hexdigest(),word_sha256=hashlib.sha256(words[0].read_bytes()).hexdigest(),counts=dict(ready=1,raw=1,ai_job=1,ai_completion=1,word=1,state=1),sources_unchanged=True,replay_unchanged=True))
        aq.atomic(root/'evidence.json',dict(status='RUNNING',root=str(root),cases=results))
        print(name,'PASS',flush=True)
    aq.atomic(root/'evidence.json',dict(status='PASS',root=str(root),cases=results,fixture_asr=True,fixture_ai=True,real_process_kill=True))
    print('PASS',root,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=Path);parser.add_argument('--action');parser.add_argument('--point',default='');parser.add_argument('--serve',action='store_true');parser.add_argument('--only');a=parser.parse_args()
    if a.child:child(a.child,a.action,a.point,a.serve)
    else:parent(a.only)
