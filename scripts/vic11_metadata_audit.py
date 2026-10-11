"""Read-only PyAV metadata audit; writes nothing. Supply explicit test files."""
import json
from pathlib import Path
import sys
import av

rows=[]
for name in sys.argv[1:]:
    p=Path(name);before=p.stat()
    with av.open(str(p)) as container:
        row=dict(file=p.name,format=container.format.name,container=dict(container.metadata),
                 streams=[dict(type=s.type,metadata=dict(s.metadata)) for s in container.streams])
    after=p.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    rows.append(row)
print(json.dumps(dict(pyav=av.__version__,policy='evidence_only_not_recording_time',files=rows),ensure_ascii=False,indent=2))
