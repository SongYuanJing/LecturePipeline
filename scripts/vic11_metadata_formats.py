"""Tiny disposable PyAV container metadata audit, not recording provenance."""
import json
from pathlib import Path
import tempfile
import av

base=Path(tempfile.mkdtemp(prefix='LP-vic11-media-'))
results=[]
for suffix,format,codec in [('m4a','mp4','aac'),('mp4','mp4','aac'),('mov','mov','aac'),
                            ('wav','wav','pcm_s16le'),('mp3','mp3','libmp3lame'),
                            ('aac','adts','aac'),('flac','flac','flac'),
                            ('ogg','ogg','libopus'),('opus','opus','libopus')]:
    p=base/('fixture.'+suffix)
    try:
        with av.open(str(p),'w',format=format) as output:
            output.metadata['creation_time']='2020-01-02T03:04:05Z'
            output.metadata['date']='1999-12-31'
            stream=output.add_stream(codec,rate=48000);stream.layout='mono'
            frame=av.AudioFrame(format='fltp',layout='mono',samples=4800);frame.sample_rate=48000
            for plane in frame.planes:plane.update(bytes(plane.buffer_size))
            for packet in stream.encode(frame):output.mux(packet)
            for packet in stream.encode(None):output.mux(packet)
        with av.open(str(p)) as source:
            results.append(dict(suffix=suffix,format=source.format.name,metadata=dict(source.metadata),
                                streams=[dict(s.metadata) for s in source.streams]))
    except Exception as error:results.append(dict(suffix=suffix,error=str(error)))
result=dict(pyav=av.__version__,path=str(base),injected_creation_time='2020-01-02T03:04:05Z',
            injected_date='1999-12-31',files=results,trust='none: generated tags are not recording timestamps')
(base/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
