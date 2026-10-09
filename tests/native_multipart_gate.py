"""Explicit Windows-only disposable multipart gate; no production or model access."""
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
import human_ux as ux
from lecture_inbox import Inbox,bind


def main():
    if os.name!='nt':raise RuntimeError('Windows gate required')
    gate=Path(os.environ['TEMP'])/('LP-multipart-'+time.strftime('%Y%m%d-%H%M%S'))
    gate.mkdir(exist_ok=False);c=fixture(gate)
    source=gate/'课程 微观 Audio';source.mkdir()
    c=bind(c,'SUBJECT',source,gate/'Results 课程',gate/'Archive',settle=10,poll=5)
    p=ux.pipeline(c);subject=c.subjects()['SUBJECT'];inbox=Inbox(c);start=time.monotonic()
    originals={}
    def audio(name,value):
        stream=io.BytesIO()
        with wave.open(stream,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
            out.writeframes(value.to_bytes(2,'little',signed=True)*16000)
        path=source/name;path.write_bytes(stream.getvalue());originals[path]=ux.sha(path)
        return path
    def scan(n=1):
        for _ in range(n):
            time.sleep(5);r=inbox.scan()
            print(json.dumps([(g['session_stem'],g['status']) for g in r['groups']],ensure_ascii=False),flush=True)
        return r
    def ready():return list(subject['audio_dir'].glob('*.READY.json'))
    def restart_process():
        r=subprocess.run([sys.executable,'-B','-X','utf8',str(APP/'lecture_inbox.py'),'--config',str(c.path),'scan'],
            capture_output=True,text=True,encoding='utf8',timeout=30)
        assert r.returncode==0,r.stderr
        return json.loads(r.stdout)
    audio('微观2026_10_09_1.wav',100);inbox.scan();scan(2)
    assert not ready(),'part1 was published without group quiet window'
    audio('微观2026_10_09_2.wav',200);scan(2);assert not ready()
    restart_process();inbox=Inbox(c)
    audio('微观2026_10_09_3.wav',300)
    for stem in ('A','B'):
        for part in (1,2):audio(f'{stem}-2026_10_09_{part}.wav',part)
    for part in (1,3):audio(f'Missing-2026_10_09_{part}.wav',part)
    inbox.scan();scan(3);assert not ready(),'group published before post-restart settle'
    after=scan();assert len(ready())==3
    groups=after['groups'];main_group=next(g for g in groups if g['session_stem'].startswith('微观'))
    assert main_group['status']=='queued'
    assert next(g for g in groups if g['session_stem'].startswith('missing'))['status']=='review'
    assert len({g['lecture_key'] for g in groups if g['status']=='queued'})==3
    from lecture_worker import Worker
    worker=Worker(c.worker_home,stable_seconds=0);manifests=[]
    for group in groups:
        if group['status']!='queued':continue
        key=group['lecture_key'];parts=p.collect_lectures(subject['audio_dir'])[key]
        manifest=p.read_ready(subject,key,parts);expected=[Path(m['source_path']) for m in manifest['intake']['members']]
        assert [m['part_hint'] for m in manifest['intake']['members']]==list(range(1,len(parts)+1))
        worker.stable_ready(subject,key,parts,set())
        assert worker.stable_ready(subject,key,parts,set())[0] is not None
        with p.verified_inputs(subject,key,parts) as copies:
            assert [ux.sha(x) for x in copies]==[ux.sha(x) for x in expected]
        manifests.append(dict(lecture_key=key,expected_parts=manifest['expected_parts'],
            source_names=[x.name for x in expected],managed_names=[x.name for x in parts],
            sha256=[ux.sha(x) for x in parts]))
    def snapshot():
        return {x.name:[ux.sha(x),x.stat().st_mtime_ns] for x in subject['audio_dir'].iterdir() if x.is_file()}
    before=snapshot();restart_process();inbox=Inbox(c);after_restart=scan();assert snapshot()==before
    assert next(g for g in after_restart['groups'] if g['session_stem'].startswith('missing'))['status']=='review'
    manual=[audio('ManualFirst.wav',41),audio('ManualSecond.wav',42)]
    key=ux.add_lecture(c,'SUBJECT','2026-10-08',ux.next_number(c,'SUBJECT'),list(reversed(manual)))
    parts=p.collect_lectures(subject['audio_dir'])[key]
    assert [ux.sha(x) for x in parts]==[ux.sha(x) for x in reversed(manual)]
    assert p.read_ready(subject,key,parts)['expected_parts']==2
    assert all(path.exists() and ux.sha(path)==digest for path,digest in originals.items())
    assert not (gate/'Archive').exists()
    evidence=dict(gate='%TEMP%/'+gate.name,platform='Windows 11 x64',seconds=time.monotonic()-start,
        unicode_course_folder=True,early_part_not_published=True,restart_during_accumulation=True,
        automatic_lecture_count=3,main_group_parts=3,ordered_ready_manifests=manifests,
        existing_worker_ready_accepted=True,verified_input_snapshots_match=True,
        restart_rescan_sha_mtime_unchanged=True,same_date_separate_sessions=True,
        missing_part_review=True,manual_multipart_preserves_order=True,originals_unchanged=True,archive_untouched=True,
        scope='Generated PCM; real Windows filesystem, locks, ingestion, READY, worker acceptance. No ASR inference or AI.')
    dump(gate/'evidence.json',evidence);print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
