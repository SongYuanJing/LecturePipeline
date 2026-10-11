"""Disposable dedup policy and actual Tk reopen gate; no scheduler/source cleanup."""
import copy,json,os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'src/app'),str(REPO/'src/app/gui_v1.8')]
from test_local_finalize import fixture,dump
from pipeline_config import Config
from lecture_inbox import Inbox,bind
import human_ux as ux
import course_setup
import tkinter as tk
from tkinter import ttk
from courses import CoursePanel

base=Path(tempfile.mkdtemp(prefix='LP-vic12-policy-'));c=fixture(base)
source=base/'Audio 课程';source.mkdir();c=bind(c,'SUBJECT',source,base/'Results',settle=10,poll=5)
os.environ['LECTURE_CONFIG']=str(c.path)
original=source/'Lecture20261010.wav';original.write_bytes(b'fixture-one')
ticks=[0];producer=Inbox(c,monotonic=lambda:ticks[0])
def settle():
    for _ in range(8):ticks[0]+=5;producer.scan()
settle();first=producer.load();key=next(iter(first['sources'].values()))['lecture_key']
(source/'Copy20261010.wav').write_bytes(original.read_bytes());settle()
rows=producer.load()['sources'];assert any('duplicate_source' in r.get('error','') for r in rows.values())
original.write_bytes(b'changed-generation');settle()
rows=producer.load()['sources'];assert any('changed_source' in r.get('error','') for r in rows.values())
assert [r['lecture_key'] for r in rows.values() if r.get('lecture_key')]==[key]
data=copy.deepcopy(c.data);second=copy.deepcopy(data['workspaces'][c.active]['subjects'][0]);second.pop('inbox');second.update(subject_code='SECOND',folder='SECOND')
data['workspaces'][c.active]['subjects'].append(second);dump(c.path,data);c=Config(c.path)
for field in ('audio_dir','raw_dir','ready_dir'):c.subjects()['SECOND'][field].mkdir(parents=True)
second_key=ux.add_lecture(c,'SECOND','2026-10-10',1,[source/'Copy20261010.wav'])
assert second_key==key
before={p:p.read_bytes() for p in [c.path,c.worker_home/'inbox.json',*c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json'),*c.subjects()['SECOND']['audio_dir'].glob('*.READY.json')]}
for _ in range(2):
    root=tk.Tk();root.title('VIC-12 disposable reopen');root.tk.call('tk','scaling',192/72)
    app=SimpleNamespace(root=root,config=lambda:c,refresh=lambda:None)
    frame=ttk.Frame(root);frame.pack();panel=CoursePanel(app,frame);panel.render(course_setup.view(c),'Disposable');root.update();root.destroy()
assert all(p.read_bytes()==value for p,value in before.items())
result=dict(status='PASS',path=str(base),same_course_copy='review',changed_generation='review',original_key=key,cross_course_key=second_key,courses_independent=True,gui_reopen_count=2,gui_state_unchanged=True,rows=list(rows.values()))
dump(base/'evidence.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
