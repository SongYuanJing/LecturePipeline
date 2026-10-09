"""Explicit disposable Windows intake gate; real polling/files/locks/imports.

No ASR inference is required: verifies the handoff to the existing worker's
READY/verified_inputs contract using generated PCM audio, not user recordings.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_local_finalize import fixture,dump,APP
from pipeline_config import Config
from lecture_inbox import Inbox,bind
import human_ux as ux


def main():
    if os.name!='nt':raise RuntimeError('Windows gate required')
    gate=Path(os.environ['TEMP'])/('LP-inbox-'+time.strftime('%Y%m%d-%H%M%S'))
    gate.mkdir(exist_ok=False);c=fixture(gate)
    d=c.data;first=d['workspaces'][c.active]['subjects'][0]
    first.update(subject_code='microeconomics_2026',subject_name='中级微观经济学')
    second=dict(first,subject_code='econometrics_2026',subject_name='计量经济学',folder='econometrics')
    d['workspaces'][c.active]['subjects'].append(second);dump(c.path,d);c=Config(c.path)
    for subject in c.subjects().values():
        for k in ('audio_dir','raw_dir','ready_dir'):subject[k].mkdir(parents=True,exist_ok=True)
    for code in c.subjects():
        source=gate/(code+' Audio 课程');source.mkdir()
        c=bind(c,code,source,gate/(code+' Results 课程'),gate/(code+' Archive'),settle=10,poll=5)
    p=ux.pipeline(c);inbox=Inbox(c);start=time.monotonic()
    def scan():
        value=inbox.scan();print(json.dumps([(x['course_id'],Path(x['source_path']).name,x['status']) for x in value['sources']],ensure_ascii=False),flush=True);return value
    audio=io.BytesIO()
    with wave.open(audio,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(b'\0\0'*16000)
    payload=audio.getvalue();courses=c.courses();source=courses['microeconomics_2026']['source_audio_folder']
    slow=source/'3- 2026_09_11_1.wav';other=source/'微观2026_10_09_1.wav'
    other.write_bytes(payload)
    (courses['econometrics_2026']['source_audio_folder']/'微观2026_10_09_1.wav').write_bytes(payload)
    (source/'unfamiliar.wav').write_bytes(payload)
    with slow.open('wb') as writer:
        writer.write(payload[:100]);writer.flush();scan();time.sleep(5)
        writer.write(payload[100:]);writer.flush();scan();time.sleep(5);scan();time.sleep(5)
        during=scan()
        assert not any(x['source_path']==str(slow) and x['status']=='queued' for x in during['sources'])
    time.sleep(5);scan();time.sleep(5);scan();time.sleep(5);scan()
    # Part-hinted sources now also require the VIC-22 group quiet window.
    time.sleep(5);scan();time.sleep(5);after=scan()
    queued=[x for x in after['sources'] if x['status']=='queued'];assert len(queued)==3
    assert sum(x['course_id']=='microeconomics_2026' for x in queued)==2
    assert next(x for x in queued if x['source_path']==str(slow))['lecture_date']=='2026-09-11'
    unknown=next(x for x in after['sources'] if x['source_path'].endswith('unfamiliar.wav'))
    assert unknown['status']=='review' and unknown['lecture_date'] is None
    # Real existing worker READY validation and immutable input snapshot.
    from lecture_worker import Worker
    worker=Worker(c.worker_home,stable_seconds=0)
    for row in queued:
        subject=c.subjects()[row['course_id']];key=row['lecture_key'];parts=p.collect_lectures(subject['audio_dir'])[key]
        worker.stable_ready(subject,key,parts,set())
        assert worker.stable_ready(subject,key,parts,set())[0] is not None
        with p.verified_inputs(subject,key,parts) as copies:
            assert len(copies)==1 and copies[0].read_bytes()==payload
    def managed():
        return {str(p):dict(sha256=ux.sha(p),mtime_ns=p.stat().st_mtime_ns)
                for s in c.subjects().values() for p in s['audio_dir'].iterdir() if p.suffix.lower() in ('.wav','.json')}
    before=managed();time.sleep(5);scan();assert managed()==before
    result=subprocess.run([sys.executable,'-B','-X','utf8',str(APP/'lecture_inbox.py'),'--config',str(c.path),'scan'],
                          capture_output=True,text=True,encoding='utf8',timeout=30)
    assert result.returncode==0,result.stderr
    assert managed()==before
    manual=gate/'manual.wav';manual.write_bytes(payload)
    code='microeconomics_2026';key=ux.add_lecture(c,code,'2026-10-08',ux.next_number(c,code),[manual])
    p.read_ready(c.subjects()[code],key,p.collect_lectures(c.subjects()[code]['audio_dir'])[key])
    assert slow.read_bytes()==payload and other.read_bytes()==payload and manual.read_bytes()==payload
    assert all(not x['archive_audio_folder'].exists() for x in courses.values())
    evidence=dict(gate='%TEMP%/'+gate.name,platform='Windows',seconds=time.monotonic()-start,
        while_copying_not_queued=True,paused_open_writer_not_queued=True,queued_count=3,
        courses=[dict(course_id=x['course_id'],display_name=x['display_name']) for x in courses.values()],
        sources=[{k:r[k] for k in ('course_id','lecture_key','lecture_date','lecture_date_source','imported_at','part_hint')} for r in queued],
        unknown_date=unknown['lecture_date'],unknown_status=unknown['status'],
        repeated_scan_unchanged=True,real_process_restart_unchanged=True,existing_worker_ready_accepted=True,
        existing_verified_input_snapshot=True,manual_import_key=key,original_sources_unchanged=True,archive_untouched=True,
        transport='Generated PCM fixtures; native filesystem/locking/import/READY. No ASR, AI or network.')
    dump(gate/'evidence.json',evidence)
    print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
