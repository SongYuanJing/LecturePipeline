"""Bounded real ASR observer qualification; reuse an existing private runtime read-only.

Run with that runtime's python, --supplier-root and --audio (disposable speech WAV).
No download, setup, production configuration or Task Scheduler access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import wave

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src/app'),str(REPO/'tests')]
from test_lecture_catalog import fixture,dump
from lecture_progress import Tracker,media_duration


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--supplier-root',type=Path,required=True);parser.add_argument('--audio',type=Path,required=True)
    args=parser.parse_args();base=Path(tempfile.mkdtemp(prefix='LP-vic14-asr-'));c=fixture(base)
    os.environ['LECTURE_CONFIG']=str(c.path);os.environ['HF_HUB_OFFLINE']='1'
    os.environ['HF_HUB_CACHE']=str(args.supplier_root/'models/huggingface/hub')
    from lecture_asr import ProductionWhisperModel
    import lecture_pipeline as p
    root=args.supplier_root/'runtime/cuda/v1.3'
    key='01_2026-10-12';cfg=c.subjects()['ECON'];audio=cfg['audio_dir']/(key+'_1.wav')
    with wave.open(str(args.audio),'rb') as source:
        params=source.getparams();frames=source.readframes(params.nframes)
    # At least 35 seconds to exercise more than a single decoder window.
    repeats=max(1,int(35/(params.nframes/params.framerate))+1)
    with wave.open(str(audio),'wb') as out:out.setparams(params);out.writeframes(frames*repeats)
    cfg.update(prompt='',hotwords='',default_language='en')
    ready=dict(version=1,lecture=key,expected_parts=1,files=[dict(name=audio.name,size=audio.stat().st_size,sha256=p.digest(audio))])
    dump(p.ready_path(cfg,key),ready)
    observations=[]
    model=ProductionWhisperModel(runtime_dir=root,allow_cpu_fallback=False)
    started=time.perf_counter();baseline,info=model.transcribe(str(audio),language='en',initial_prompt='',hotwords='')
    baseline=[(x.start,x.end,x.text) for x in baseline];baseline_s=time.perf_counter()-started
    t=Tracker('ECON/'+key,[media_duration(audio)],lambda v:observations.append(dict(v)))
    state=dict(version=1,lectures={});started=time.perf_counter()
    p.process_lecture(model,'ECON',cfg,key,[audio],state,c.state,base/'pipeline.log',progress=t)
    instrumented_s=time.perf_counter()-started
    expected=p.bounded_segments(baseline,info.duration)
    expected_srt=base/'expected.srt';p.write_srt(expected_srt,expected)
    actual=cfg['raw_dir']/key/(audio.stem+'.srt')
    assert actual.read_bytes()==expected_srt.read_bytes(),'Instrumentation changed segment/text flow'
    p.committed_raw(cfg,key,state['lectures']['ECON/'+key])
    assert model.last_run['actual_device']=='cuda'
    measured=[v['processed_audio_seconds'] for v in observations if v['percent'] is not None]
    assert measured and measured==sorted(measured) and measured[-1]==info.duration
    assert any(0<v<info.duration for v in measured),measured
    dump(base/'evidence.json',dict(status='PASS',base=str(base),actual_device=model.last_run['actual_device'],
         duration=info.duration,metadata_duration=media_duration(audio),baseline_seconds=baseline_s,instrumented_seconds=instrumented_s,
         equal_srt=True,segments=len(expected),raw_committed=True,observations=observations,
         audio_sha256=p.digest(audio),source_timeline='faster-whisper 1.2.1 restore_speech_timestamps',
         scope='Real large-v3/CTranslate2/PyAV/CUDA, no ASR fixtures; synthetic English speech; not ETA quality'))
    print('VIC14_NATIVE_PASS '+str(base),flush=True)


if __name__=='__main__':main()
