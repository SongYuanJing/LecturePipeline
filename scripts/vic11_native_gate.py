"""Disposable Windows/Tk/filesystem date gate; ASR and AI text are fixtures.

No scheduler changes, production access or fake clock. Output retained in a new
mkdtemp directory. Run with the document/test Python and installed python-docx.
"""
from datetime import datetime, timedelta, timezone
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
from test_local_finalize import fixture, dump
import ai_queue as aq
import ai_finalize
import course_setup
import human_ux as ux
import lecture_dates
from lecture_inbox import Inbox, bind
from courses import CoursePanel
import tkinter as tk
from tkinter import ttk

base=Path(tempfile.mkdtemp(prefix='LP-vic11-'))
print('Disposable gate:',base,flush=True)
c=fixture(base);os.environ['LECTURE_CONFIG']=str(c.path)
source=base/'Audio 课程';source.mkdir()
c=bind(c,'SUBJECT',source,base/'Results 课程',settle=10,poll=5)
today=datetime.now(timezone(timedelta(hours=8))).date()
yesterday=(today-timedelta(days=1)).isoformat();older=(today-timedelta(days=2)).isoformat()
names=[f'Yesterday_{yesterday}.wav','Unknown.wav',f'Consistent_{yesterday}_1.wav',f'Consistent_{yesterday}_2.wav',f'Conflict_{yesterday}_1.wav',f'Conflict_{yesterday}_2.wav',f'Conflict_{older}_3.wav']
for name in names:
    with wave.open(str(source/name),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000)
    os.utime(source/name,(1,1))

def snapshot(paths):
    return {str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns) for p in paths}
original=snapshot(source.iterdir());config=snapshot([c.path])
root=tk.Tk();root.title('Lecture Pipeline · VIC-11 disposable date gate')
root.tk.call('tk','scaling',192/72);root.geometry('1200x850')
app=SimpleNamespace(root=root,config=lambda:c,control=lambda fn:fn(),refresh=lambda:None)
frame=ttk.Frame(root);frame.pack(fill='both',expand=True);panel=CoursePanel(app,frame)
events=[];inbox=Inbox(c)

def scan_for(seconds):
    end=time.monotonic()+seconds
    while True:
        result=inbox.scan();panel.render(course_setup.view(c),'Disposable gate');root.update()
        events.append(dict(at=datetime.now(timezone.utc).isoformat(),items=[dict(id=r['id'],status=r['status'],date=r.get('lecture_date')) for r in panel.data['items']]))
        if time.monotonic()>=end:return result
        until=time.monotonic()+5
        while time.monotonic()<until:root.update();time.sleep(.05)

try:
    scan_for(25)
    rows=panel.data['items'];unknown=next(r for r in rows if r['name']=='Unknown.wav')
    assert unknown['status']=='review' and unknown['lecture_date'] is None
    conflicts=[r for r in rows if r['name'].startswith('conflict')]
    assert len(conflicts)==2 and all(r['status']=='review' and not r.get('lecture_key') for r in conflicts)
    accepted=[r for r in rows if r.get('lecture_key')]
    assert len(accepted)==2 and all(r['lecture_date']==yesterday for r in accepted)
    assert all(datetime.fromisoformat(r['imported_at']).astimezone(timezone(timedelta(hours=8))).date()==today for r in accepted)
    # Actual review widgets and callback, with no replacement of the service.
    panel.items.selection_set(unknown['id']);panel.detail();root.update()
    assert 'не определена' in panel.details.get()
    panel.resolve();root.update()
    dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
    entry=next(w for w in dialog.winfo_children() if isinstance(w,ttk.Entry));entry.insert(0,older)
    save=next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Сохранить')
    assert save.winfo_rooty()+save.winfo_height()<=dialog.winfo_rooty()+dialog.winfo_height()
    save.invoke();root.update();scan_for(20)
    corrected=Inbox(c).load()['sources'][unknown['id']]
    assert corrected['lecture_date']==older and corrected['lecture_date_source']=='explicit' and corrected['date_override']
    assert corrected['date_evidence'][0]['lecture_date'] is None
    assert corrected['lecture_key'].endswith(older)
    # Real READY -> raw publishing -> packet -> finalizer, fixture transcript/AI.
    p=ux.pipeline(c);subject=c.subjects()['SUBJECT'];outputs=[]
    for key,parts in p.collect_lectures(subject['audio_dir']).items():
        with patch.object(p,'transcribe_one',return_value=([(0,1,'测试内容')],SimpleNamespace(language='zh'))),patch.object(p,'safe_print'):
            p.process_lecture(object(),'SUBJECT',subject,key,parts,aq.read(c.state),c.state,base/'gate.log')
        manifest=aq.read(subject['raw_dir']/key/(key+'_manifest.json'));metadata=lecture_dates.metadata(manifest)
        identity=c.active+'/SUBJECT/'+key;task=aq.refresh(c)['tasks'][identity]
        packet=aq.verify_packet(Path(task['source_packet']).parent)
        assert all(packet['task'][field]==metadata[field] for field in lecture_dates.FIELDS)
        word=aq.module(c);block=dict(text='Тест',basis='transcript',refs=[dict(start='1:1',end='1:1')])
        content=dict(schema_version=1,input_hashes=packet['input_hashes'],title='Тест',organization={k:dict(status='not_found',items=[]) for k in word.ORG},summary=[block],notes=[block],definitions=[block],formulas=[],emphasis=[block],uncertainties=[],part_review=[dict(part=i+1,status='usable',note='fixture') for i in range(len(parts))],vocabulary=[])
        answer=base/(key+'.json');dump(answer,content);result=ai_finalize.finalize(c,identity,answer)
        from docx import Document
        assert 'Дата лекции: '+metadata['lecture_date'] in '\n'.join(x.text for x in Document(result['word']).paragraphs)
        records=aq.read(c.ai_state)['processed'].values()
        record=next(r for r in records if r['lecture_id']==key)
        assert all(record[field]==metadata[field] for field in lecture_dates.FIELDS)
        outputs.append(dict(key=key,metadata=metadata,word=result['word']))
    assert len(outputs)==3
    # Completed identity is immutable: UI disables edit; service refuses it.
    panel.render(course_setup.view(c),'Disposable gate');panel.items.selection_set(unknown['id']);panel.resolve();root.update()
    dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
    save=next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Сохранить')
    assert save.instate(['disabled']);dialog.destroy()
    before=Inbox(c).load()
    try:Inbox(c).review(unknown['id'],lecture_date=yesterday)
    except ValueError:pass
    else:raise AssertionError('Published date mutation accepted')
    assert before==Inbox(c).load()
    files=list(subject['audio_dir'].glob('*.READY.json'))+list(subject['raw_dir'].rglob('*'))+list(subject['ready_dir'].rglob('*'))
    files=[f for f in files if f.is_file()];sealed=snapshot(files)
    root.destroy();root=tk.Tk();root.withdraw()
    inbox=Inbox(c);inbox.scan();root.update()
    assert sealed==snapshot(files) and original==snapshot(source.iterdir()) and config==snapshot([c.path])
    after=inbox.load()
    for section in ('sources','groups'):
        assert before[section]==after[section]
    evidence=dict(status='PASS',path=str(base),today=str(today),yesterday=yesterday,outputs=outputs,events=events,
                  completed_edit='UI disabled; service rejected without mutation',restart='fresh Inbox and Tk; same metadata, keys, READY/raw/Word hashes and mtime',
                  original_sources_unchanged=True,config_unchanged=True,checks=8,
                  substitutions=['Whisper transcription','AI content'],real=['Windows filesystem','real monotonic wait','Tk widgets/callback','Inbox','READY','raw publisher','AI packet','Word finalizer'],
                  scheduler='not used',settle_seconds=10,poll_seconds=5)
    dump(base/'evidence.json',evidence)
    print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)
finally:
    try:root.destroy()
    except tk.TclError:pass
