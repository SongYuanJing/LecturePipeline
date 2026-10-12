"""Deterministic observation-rate benchmark with real local atomic writes."""
import json
from pathlib import Path
import sys
import tempfile
import time
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'src/app'))
from lecture_progress import Tracker
from ai_queue import atomic

base=Path(tempfile.mkdtemp(prefix='LP-vic14-overhead-'))
ticks=[0.];writes=[]
def publish(value):
    started=time.perf_counter()
    atomic(base/'worker_status.json',dict(worker='RUNNING',lectures={value['identity']:dict(progress=value)}))
    writes.append(dict(at=ticks[0],seconds=time.perf_counter()-started))
tracker=Tracker('ECON/01_2026-10-12',[600],publish,clock=lambda:ticks[0],wall=lambda:ticks[0])
tracker.begin(1);started=time.perf_counter();cpu=time.process_time()
for n in range(100000):
    ticks[0]=n/1000
    tracker.observe(dict(phase='transcribe',session='fixture',backend='cuda',processed_audio_sec=n/500))
report=dict(callbacks=100000,simulated_seconds=ticks[0],writes=len(writes),
            wall_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
            atomic_write_seconds=sum(w['seconds'] for w in writes),minimum_write_interval=min(b['at']-a['at'] for a,b in zip(writes,writes[1:])),
            base=str(base))
assert report['writes']==100 and report['minimum_write_interval']>=1
(base/'evidence.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
