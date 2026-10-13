"""Fresh disposable integration gate; ASR and Scheduler are explicit fixtures.

Real services own intake, READY, raw, AI packet, Word, vocabulary and catalog.
Run without arguments, then --gui <printed root> for native inspection/reopen.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import wave

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'src/app'),str(REPO/'src/app/gui_v1.8')]
from test_local_finalize import fixture,dump
from test_course_setup import FixtureControls,manager
from pipeline_config import Config
import course_setup as cs
from lecture_inbox import Inbox
import lecture_catalog as catalog

def fingerprints(base):
    return {p.relative_to(base).as_posix():[hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns]
            for p in base.rglob('*') if p.is_file() and not p.name.endswith('.lock')}

def integrate(drive=False):
    base=Path(tempfile.mkdtemp(prefix='LP-vic23-integration-'));c=fixture(base)
    source_root=base
    if drive:
        allowed=Path('G:/Мой диск/test').resolve(strict=True)
        source_root=allowed/base.name
        assert source_root.parent==allowed and not source_root.exists()
        source_root.mkdir()
    codes=[];source_files=[]
    for i,name in enumerate(('А Экономика 经济','Б Исследование 研究','В Проверка 待审核')):
        mapping=cs.recommended(source_root/name)
        code=cs.save_course(c,manager(c),name,mapping,create=True);codes.append(code);c=Config(c.path)
        parts=([None],[3,1,2],[1,3])[i]
        for part in parts:
            p=Path(mapping['source_audio_folder'])/('课程2026_10_12'+('' if part is None else '_'+str(part))+'.wav')
            with wave.open(str(p),'wb') as wav:
                wav.setparams((1,2,16000,0,'NONE','not compressed'))
                wav.writeframes(bytes([i+1,part or 0])*16000)
            source_files.append(p)
    d=c.data
    for s in d['workspaces'][c.active]['subjects']:
        if 'inbox' in s:s['inbox'].update(settle_seconds=10,poll_seconds=5)
    dump(c.path,d);c=Config(c.path);os.environ['LECTURE_CONFIG']=str(c.path)
    original={str(p):[hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns] for p in source_files}
    ticks=[0]
    def scan():
        producer=Inbox(c,monotonic=lambda:ticks[0])
        for _ in range(8):ticks[0]+=5;producer.scan()
    scan()
    ready=[p for s in c.subjects().values() for p in s['audio_dir'].glob('*.READY.json')]
    assert len(ready)==2,ready
    documents=[json.loads(p.read_text(encoding='utf8')) for p in ready]
    assert sorted(d['expected_parts'] for d in documents)==[1,3]
    multi=next(d for d in documents if d['expected_parts']==3)
    assert [m['part_hint'] for m in multi['intake']['members']]==[1,2,3]
    assert all(d['intake']['lecture_date']=='2026-10-12' for d in documents)
    ready_before={str(p):p.read_bytes() for p in ready};scan()
    assert ready_before=={str(p):p.read_bytes() for s in c.subjects().values() for p in s['audio_dir'].glob('*.READY.json')}
    before=catalog.build(c);assert len(before['items'])==2 and before['pending'],before
    import lecture_pipeline as p
    import importlib
    importlib.reload(p) # Worker startup reloads the config committed by Course setup.
    import lecture_worker as w
    import ai_queue as aq
    import ai_finalize
    calls=[]
    def recognize(*a,**kw):
        calls.append(str(a));return [(0,1,'测试内容。 Учебный пример.')],SimpleNamespace(language='zh',duration=1)
    with patch.object(p,'WhisperModel',return_value=object()),patch.object(p,'transcribe_one',recognize),patch.object(p,'safe_print'),patch.object(aq,'refresh',return_value={}):
        worker=w.Worker(c.worker_home,stable_seconds=0)
        for _ in range(2):worker.cycle()
        assert len(calls)==4,calls
        worker=w.Worker(c.worker_home,stable_seconds=0) # Stop/start: fresh service object, durable jobs reused.
        for _ in range(2):worker.cycle()
        assert len(calls)==4,'Repeated ASR after restart'
    q=aq.refresh(c);assert len(q['tasks'])==2,q
    results=[]
    for i,(identity,task) in enumerate(q['tasks'].items()):
        packet=aq.verify_packet(Path(task['source_packet']).parent);word=aq.module(c)
        block=dict(text='Учебный пример 测试',basis='transcript',refs=[dict(start='1:1',end='1:1')])
        content=dict(schema_version=1,input_hashes=packet['input_hashes'],title='Пример 课程',organization={k:dict(status='not_found',items=[]) for k in word.ORG},summary=[block],notes=[block],definitions=[block],formulas=[],emphasis=[block],uncertainties=[],part_review=[dict(part=n+1,status='usable',note='fixture') for n in range(len(packet['manifest']['outputs']))],vocabulary=[])
        answer=base/f'answer-{i}.json';dump(answer,content);aq.accept_result(c,identity,answer)
        result=ai_finalize.finalize(c,identity,answer);word.validate_docx(result['word']);results.append(result['word'])
        protected={str(x):[hashlib.sha256(x.read_bytes()).hexdigest(),x.stat().st_mtime_ns] for x in (Path(result['word']),c.dictionary,c.ai_state)}
        assert ai_finalize.finalize(c,identity,answer)['idempotent']
        assert protected=={str(x):[hashlib.sha256(x.read_bytes()).hexdigest(),x.stat().st_mtime_ns] for x in (Path(result['word']),c.dictionary,c.ai_state)}
    final=catalog.build(c);assert len(final['items'])==2 and all(r['status']=='done' for r in final['items']),final
    assert len(final['pending'])==1,final['pending']
    assert all(r['progress'] is None for r in final['items'])
    assert original=={str(p):[hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns] for p in source_files}
    snapshot=fingerprints(base)
    for _ in range(3):assert catalog.build(c)==final
    assert snapshot==fingerprints(base),'Catalog read mutation'
    report=dict(status='PASS',base=str(base),source_root=str(source_root),bounded_drive=drive,codes=codes,source_count=len(source_files),source_unchanged=True,ready_count=2,parts=[1,3],asr_fixture_calls=len(calls),worker_restart_no_repeat=True,producer_restart_no_repeat=True,word_count=len(results),word_idempotent=True,catalog=final,fixture_asr=True,fixture_scheduler=True)
    dump(base/'integration-evidence.json',report);print(str(base),flush=True)

def gui(base,scroll_check=False):
    assert base.resolve().parent==Path(tempfile.gettempdir()).resolve() and base.name.startswith('LP-vic23-integration-')
    c=Config(base/'app/config.json');os.environ['LECTURE_CONFIG']=str(c.path)
    # Complete the disposable inactive Dialogue environment before observation.
    for path,value in ((c.dialogue_home/'status.json',dict(worker='STOPPED',files={})),
                       (c.dialogue_home/'dialogue_state.json',dict(jobs={}))):
        if not path.exists():dump(path,value)
    for name in ('00 — Входящие аудио','01 — Расшифровки','02 — Word','99 — Служебное'):
        (c.dialogue_root/name).mkdir(parents=True,exist_ok=True)
    import tkinter as tk
    import adapter
    from app import App
    from dpi import enable_system_dpi
    def durable():
        return {k:v for k,v in fingerprints(base).items() if not k.startswith('gui-evidence') and k!='app/logs/gui/gui.log'}
    before=durable();errors=[];checks={};enable_system_dpi();root=tk.Tk()
    root.report_callback_exception=lambda typ,value,tb:errors.append(str(value))
    with patch.object(adapter,'Controls',FixtureControls),patch.object(adapter,'preflight',lambda c:dict(ok=True,checks=[])):
        app=App(root,c.path);root.title('VIC-23 disposable integration · 200%');root.geometry('1900x1400')
        app.tabs.select(app.pages['Лекции']);dpi=round(float(root.tk.call('tk','scaling'))*72)
        def check_scroll():
            if app.busy:root.after(100,check_scroll);return
            try:
                assert dpi==192,dpi
                panel=app.catalog;data=copy.deepcopy(panel.data)
                assert len(data['items'])==2 and len(data['pending'])==1
                panel.table.selection_set('0');root.update()
                panel.table.xview_moveto(.5);panel.table.yview_moveto(.5)
                panel.detail.yview_moveto(.4);root.update()
                selection=panel.table.selection();table=(panel.table.xview(),panel.table.yview())
                middle=panel.detail.yview();panel.render(copy.deepcopy(data),c);root.update()
                assert panel.detail.yview()==middle
                panel.detail.yview_moveto(1);root.update()
                assert panel.detail.yview()[1]==1
                # View-only progress text tests wrapping without inventing durable
                # worker state or modifying a completed lecture's authorities.
                for repeats in (1,30,2,40):
                    changed=copy.deepcopy(data)
                    changed['items'][0]['progress_view']=dict(compact='GUI fixture',details=('Тест переноса строки / 中文进度 · '*repeats))
                    panel.render(changed,c);root.update()
                    assert panel.table.selection()==selection
                    assert (panel.table.xview(),panel.table.yview())==table
                    assert panel.detail.yview()[1]==1,panel.detail.yview()
                    assert 'Тест переноса строки' in panel.detail.get('1.0','end')
                panel.render(data,c);root.update()
                assert panel.detail.yview()[1]==1
                checks.update(selection=True,details=True,middle_scroll=True,bottom_reflow=True,table_scroll=True,view_only_progress_fixture=True)
                print('SCROLL_CHECK_PASS',flush=True)
            except Exception as e:
                errors.append(str(e));app.close()
        if scroll_check:root.after(300,check_scroll)
        root.mainloop()
    after=durable();changed=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
    report=dict(status='PASS' if not changed and not errors and (not scroll_check or checks) else 'FAIL',dpi=dpi,callback_errors=errors,changed_files=changed,scroll_checks=checks,
                catalog_source_sha256=hashlib.sha256((REPO/'src/app/gui_v1.8/catalog.py').read_bytes()).hexdigest(),fingerprinted_files=len(before))
    dump(base/('gui-evidence-'+str(time.time_ns())+'.json'),report);print(json.dumps(report),flush=True)
    assert not changed and not errors,report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gui',type=Path);parser.add_argument('--drive',action='store_true');parser.add_argument('--scroll-check',action='store_true');args=parser.parse_args()
    gui(args.gui,args.scroll_check) if args.gui else integrate(args.drive)
