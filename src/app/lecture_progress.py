"""Disposable observations, never processing/recovery authority. No GUI dependencies."""
import logging
import math
import time
import uuid
from datetime import datetime

STAGES={'preparing':'Подготовка','asr':'Распознавание','publishing':'Публикация расшифровки'}


def positive(value):
    try:
        value=float(value)
        return value if math.isfinite(value) and value>0 else None
    except (ValueError,TypeError,OverflowError):return None


def media_duration(path):
    """Header metadata only, once per local part; unavailable is a valid result."""
    try:
        import av
        with av.open(str(path)) as container:
            streams=list(container.streams.audio)
            if not streams:return None
            stream=streams[0]
            if stream.duration is not None and stream.time_base is not None:
                return positive(float(stream.duration*stream.time_base))
            return positive(container.duration/av.time_base) if container.duration is not None else None
    except Exception:return None


class Tracker:
    def __init__(self,identity,durations,publish,*,clock=time.monotonic,wall=time.time):
        self.identity=identity;self.durations=[positive(d) for d in durations]
        self.publish=publish;self.clock=clock;self.wall=wall;self.token=uuid.uuid4().hex
        self.start=clock();self.last_write=-math.inf;self.part=0;self.processed=0.;self.backend=None
        self.rate=None;self.sample=None;self.evidence_start=None;self.evidence_audio=0.;self.child=None
        self.last_advance=None

    def begin(self,index):
        self.part=index;self.processed=0.;self.child=None
        self.emit('preparing',force=True)

    def observe(self,value):
        try:
            backend=value.get('backend');child=value.get('session')
            if self.child!=child or self.backend!=backend:
                # Device fallback/new child must not reuse speed from the failed attempt.
                self.rate=None;self.sample=None;self.evidence_start=None;self.evidence_audio=0.;self.processed=0.
                self.last_advance=None
                self.child=child;self.backend=backend
            duration=positive(value.get('audio_duration_sec'))
            if duration:self.durations[self.part-1]=duration
            observed=positive(value.get('processed_audio_sec')) or 0.
            limit=self.durations[self.part-1]
            if observed>self.processed:self.last_advance=self.clock()
            self.processed=max(self.processed,min(observed,limit) if limit else observed)
            stage='asr' if value.get('phase') in ('transcribe','asr_complete') else 'preparing'
            now=self.clock()
            if stage=='asr':
                if self.evidence_start is None:self.evidence_start=now;self.evidence_audio=self.processed
                if self.sample is not None:
                    old_time,old_audio=self.sample;dt=now-old_time;da=self.processed-old_audio
                    if dt>=1:
                        speed=max(0.,da/dt);alpha=1-math.exp(-dt/30.)
                        self.rate=speed if self.rate is None else self.rate+alpha*(speed-self.rate)
                        self.sample=(now,self.processed)
                else:self.sample=(now,self.processed)
            self.emit(stage)
        except Exception:logging.exception('ASR progress observation unavailable')

    def complete_part(self,duration):
        duration=positive(duration)
        if duration:self.durations[self.part-1]=duration;self.processed=duration
        self.emit('asr',force=True)

    def emit(self,stage,force=False):
        now=self.clock()
        if not force and now-self.last_write<1:return
        self.last_write=now
        known=bool(self.durations) and all(d is not None for d in self.durations)
        total=sum(self.durations) if known else None
        processed=sum(self.durations[:self.part-1])+self.processed if known and self.part else None
        fraction=min(1.,max(0.,processed/total)) if total else None
        eta=None
        if (stage=='asr' and fraction is not None and 0.05<=fraction<1 and
            self.evidence_start is not None and now-self.evidence_start>=20 and
            self.last_advance is not None and now-self.last_advance<=15 and
            self.processed-self.evidence_audio>=30 and self.rate and self.rate>0):
            candidate=(total-processed)/self.rate
            if math.isfinite(candidate):eta=max(0.,candidate)
        code,key=self.identity.split('/',1)
        value=dict(schema=1,identity=self.identity,course_id=code,lecture_key=key,attempt=self.token,
                   stage=stage,active=True,part_index=self.part or None,part_count=len(self.durations),
                   processed_audio_seconds=processed,total_audio_seconds=total,
                   percent=100*fraction if fraction is not None and stage=='asr' else None,
                   elapsed_seconds=max(0.,now-self.start),eta_seconds=eta,eta_available=eta is not None,
                   updated_at=self.wall(),backend=self.backend)
        try:self.publish(value)
        except Exception:logging.exception('Progress publication failed; processing continues')


def live(value,worker,job,row,now=None):
    """Fail closed on stale/legacy observations; committed catalog stages win."""
    now=time.time() if now is None else now
    try:
        if not isinstance(value,dict) or value.get('schema')!=1:return None
        if row['status'] not in ('asr','publishing') or job.get('phase') not in ('transcribing','publishing'):return None
        if worker.get('worker')!='RUNNING' or value.get('worker_started_at')!=worker.get('started_at'):return None
        heartbeat=datetime.fromisoformat(worker['heartbeat']).timestamp()
        if not 0<=now-heartbeat<=90 or not 0<=now-value['updated_at']<=10:return None
        if value['identity']!=row['id'] or value.get('job_token')!=job.get('token'):return None
        if not value.get('active') or not value.get('attempt'):return None
        if value['part_count']!=row['parts'] or not 1<=value['part_index']<=value['part_count']:return None
        if value['stage'] not in STAGES:return None
        for field in ('percent','processed_audio_seconds','total_audio_seconds','eta_seconds','elapsed_seconds'):
            n=value.get(field)
            if n is not None and (not isinstance(n,(int,float)) or not math.isfinite(n) or n<0):return None
        if value.get('percent') is not None and value['percent']>100:return None
        return dict(value,stale=False)
    except (ValueError,TypeError,KeyError,OverflowError):return None


def clock_text(seconds):
    if seconds is None:return '—'
    s=int(seconds);return f'{s//3600:d}:{s//60%60:02d}:{s%60:02d}'


def presentation(value):
    if not value:return dict(compact='',details='',fraction=None)
    stage=STAGES[value['stage']];part=f"{value['part_index']}/{value['part_count']}"
    percent=value.get('percent');eta=value.get('eta_seconds')
    estimate=('~'+str(max(1,math.ceil(eta/60)))+' мин') if eta is not None else 'рассчитывается…'
    compact=part+(f' · {percent:.0f}%' if percent is not None else ' · —')
    if eta is not None:compact+=' · ETA ASR '+estimate
    details=f'Этап: {stage}\nЧасть: {part}\nASR: '+(f'{percent:.1f}%' if percent is not None else '—')
    details+='\nОбработано: '+clock_text(value.get('processed_audio_seconds'))+' / '+clock_text(value.get('total_audio_seconds'))
    details+='\nETA ASR: '+(estimate if value['stage']=='asr' else '—')
    return dict(compact=compact,details=details,fraction=percent/100 if percent is not None else None)
