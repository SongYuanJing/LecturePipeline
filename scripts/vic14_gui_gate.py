"""Disposable real Tk gate with deterministic live progress; no real worker/ASR."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime,timezone
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'src/app'),str(REPO/'src/app/gui_v1.8')]
from test_lecture_catalog import fixture,add,dump,fingerprints
from lecture_catalog import build
from lecture_progress import Tracker


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--auto-close',action='store_true');args=parser.parse_args()
    base=Path(tempfile.mkdtemp(prefix='LP-vic14-gui-'));c=fixture(base)
    ident=add(c,'ECON','01_2026-10-12','ready',8)
    other=add(c,'RESEARCH','01_2026-10-11','ready',1)
    add(c,'MICRO','01_2026-10-10','waiting_ai',1);add(c,'MICRO','02_2026-10-09','done',1)
    dump(c.worker_home/'worker_jobs.json',dict(jobs={i:dict(phase='transcribing',token='token') for i in (ident,other)}))
    dump(c.dialogue_home/'status.json',dict(worker='STOPPED',files={}))
    dump(c.dialogue_home/'dialogue_state.json',dict(jobs={}))
    (c.dialogue_root/'00 — Входящие аудио').mkdir(parents=True)
    stamp=datetime.now(timezone.utc).isoformat();observations={};ticks=[0.];writes=[0]
    def receive(v):observations[v['identity']]=dict(v,worker_started_at=stamp,job_token='token')
    tracker=Tracker(ident,[600]*8,receive,clock=lambda:ticks[0]);tracker.begin(3)
    for n in range(151):ticks[0]=float(n);tracker.observe(dict(session='one',backend='cuda',phase='transcribe',processed_audio_sec=n*2))
    def publish():
        now=time.time();observations[ident]['updated_at']=now
        observations[other]=dict(observations[ident],identity=other,course_id='RESEARCH',lecture_key='01_2026-10-11',part_index=1,part_count=1,processed_audio_seconds=12.,total_audio_seconds=100.,percent=12.,eta_seconds=None,eta_available=False)
        dump(c.worker_home/'worker_status.json',dict(worker='RUNNING',started_at=stamp,heartbeat=datetime.now(timezone.utc).isoformat(),lectures={i:dict(status='TRANSCRIBING',detail='Disposable progress simulation',progress=v) for i,v in observations.items()}));writes[0]+=1
    publish()
    def durable():
        # GUI startup creates its local empty log; neither log nor the fixture's
        # changing worker observation is durable lecture/config authority.
        excluded={str((c.worker_home/'worker_status.json').relative_to(base)),
                  str((c.install/'logs/gui/gui.log').relative_to(base)),'evidence.json'}
        return {k:v for k,v in fingerprints(base).items() if k not in excluded}
    before=durable();started=time.perf_counter();snapshot=build(c);refresh=time.perf_counter()-started
    import tkinter as tk
    from app import App
    from dpi import enable_system_dpi
    import adapter
    enable_system_dpi();root=tk.Tk();os.environ['LECTURE_CONFIG']=str(c.path)
    class Controls:
        def __init__(self,c):pass
        def states(self):return {k:dict(running=(k=='lecture'),enabled=False) for k in ('lecture','dialogue')}
    errors=[];root.report_callback_exception=lambda typ,value,tb:errors.append(str(value))
    report=dict(base=str(base),refresh_seconds=refresh,fixture_scheduler=True,fixture_progress=True)
    with patch.object(adapter,'Controls',Controls),patch.object(adapter,'preflight',lambda c:dict(ok=True,checks=[])):
        app=App(root,c.path);root.title('VIC-14 disposable progress · 200%');root.geometry('1900x1400')
        app.tabs.select(app.pages['Лекции'])
        def tick():
            ticks[0]+=2;tracker.observe(dict(session='one',backend='cuda',phase='transcribe',processed_audio_sec=min(550,ticks[0]*2)))
            publish();root.after(2000,tick)
        def check():
            if app.busy:root.after(100,check);return
            try:
                assert round(float(root.tk.call('tk','scaling'))*72)==192
                panel=app.catalog;assert len(panel.rows)==4
                rows={r['id']:r for r in app.view['catalog']['items']}
                assert rows[ident]['progress']['eta_available']
                assert rows[other]['progress']['eta_seconds'] is None
                assert all(r['progress'] is None for r in rows.values() if r['status'] in ('done','waiting_ai'))
                first=next(i for i,r in panel.rows.items() if r['id']==ident)
                panel.table.selection_set(first);root.update();panel.detail.yview_moveto(1);root.update()
                old=(panel.table.selection(),panel.detail.yview()[0])
                ticks[0]+=2;tracker.observe(dict(session='one',backend='cuda',phase='transcribe',processed_audio_sec=ticks[0]*2));publish()
                panel.render(build(c),c);root.update()
                assert panel.table.selection()==old[0] and abs(panel.detail.yview()[0]-old[1])<.035
                panel.detail.yview_moveto(0)
                report.update(widget_status='PASS',dpi=192,selection_scroll_retained=True,rows=4)
                dump(base/'evidence.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
                root.after(2000,tick)
                if args.auto_close:root.after(8000,app.close)
            except Exception:
                import traceback
                report.update(widget_status='FAIL',error=traceback.format_exc());dump(base/'evidence.json',report);app.close()
        root.after(300,check);root.mainloop()
    after=durable()
    report['changed_files']=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
    dump(base/'evidence.json',report)
    assert before==after,'Unexpected durable mutation: '+str(report['changed_files'])
    assert not errors,errors
    report.update(post_interaction_config_data_unchanged=True,callback_errors=errors,fixture_status_writes=writes[0])
    dump(base/'evidence.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
