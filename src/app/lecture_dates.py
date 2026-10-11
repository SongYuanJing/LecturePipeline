"""Additive session dates. Never infer recording time from filesystem clocks.

Embedded container creation tags are evidence only, not trusted recording time.
Published lecture keys are immutable; corrections require a separate migration.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import re

FIELDS=('lecture_date','lecture_date_source','lecture_date_raw','imported_at',
        'recorded_at','recorded_at_source','date_resolution','date_evidence','date_override')
PATTERN=re.compile(r'(?<!\d)(\d{4})[_-]?(\d{2})[_-]?(\d{2})(?!\d)')

def day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('Дата: YYYY-MM-DD')
    return date.fromisoformat(value).isoformat()

def timestamp(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.utcoffset() is None:raise ValueError('Timestamp requires timezone offset')
    return parsed.astimezone(timezone.utc).isoformat()

def filename(name):
    evidence=[]
    for m in PATTERN.finditer(Path(name).stem):
        try:value=date(*map(int,m.groups())).isoformat()
        except ValueError:continue
        evidence.append(dict(value=value,raw=m[0],source='filename'))
    values={e['value'] for e in evidence}
    return dict(lecture_date=next(iter(values)) if len(values)==1 else None,
                lecture_date_source='filename' if len(values)==1 else 'unknown',
                lecture_date_raw=evidence[0]['raw'] if len(values)==1 else None,
                date_resolution='conflict' if len(values)>1 else 'resolved' if values else 'unknown',
                date_evidence=evidence,date_override=False,recorded_at=None,recorded_at_source='unknown')

def resolve(members, *, override=None, imported_at=None, same_session=True):
    """Members must already belong to one session; this does not group files."""
    rows=[filename(r) if isinstance(r,str) else r for r in members]
    evidence=[dict(lecture_date=r.get('lecture_date'),source=r.get('lecture_date_source','legacy'),
                   raw=r.get('lecture_date_raw'),filename_hints=r.get('date_evidence',[]) if r.get('lecture_date_source')=='filename' else []) for r in rows]
    explicit={r['lecture_date'] for r in rows if r.get('lecture_date') and r.get('lecture_date_source')=='explicit'}
    known={r['lecture_date'] for r in rows if r.get('lecture_date')}
    value=None;source='unknown';raw=None;status='unknown'
    if override is not None:
        value=day(override);source='explicit';raw=override;status='resolved'
    elif explicit:
        if len(explicit)==1:value=day(next(iter(explicit)));source='explicit';raw=value;status='resolved'
        else:status='conflict'
    elif len(known)>1 or any(r.get('date_resolution')=='conflict' for r in rows):status='conflict'
    elif known and (same_session or all(r.get('lecture_date') for r in rows)):
        value=day(next(iter(known)));source='filename' if all(r.get('lecture_date_source')=='filename' for r in rows if r.get('lecture_date')) else 'legacy'
        raw=next((r.get('lecture_date_raw') for r in rows if r.get('lecture_date')),None);status='resolved'
    return dict(lecture_date=value,lecture_date_source=source,lecture_date_raw=raw,
                imported_at=timestamp(imported_at) if imported_at else None,
                recorded_at=None,recorded_at_source='unknown',date_resolution=status,date_evidence=evidence,
                date_override=source=='explicit')

def metadata(manifest):
    """Read legacy records without migration or invented timestamp/provenance."""
    source=manifest.get('intake',manifest)
    result={k:source.get(k) for k in FIELDS}
    if 'lecture_date' not in source:
        key=manifest.get('lecture','')
        try:result['lecture_date']=day(key.split('_',1)[1])
        except (ValueError,IndexError):pass
    result['lecture_date_source']=source.get('lecture_date_source') or ('legacy' if result['lecture_date'] else 'unknown')
    result['recorded_at_source']=source.get('recorded_at_source') or ('legacy' if result['recorded_at'] else 'unknown')
    return result

def describe(record):
    m=metadata(record)
    labels={'filename':'Из имени файла','explicit':'Указана пользователем','legacy':'Старая запись; источник неизвестен','unknown':'Не определён'}
    return f"Дата лекции: {m['lecture_date'] or 'не определена'} · Источник: {labels.get(m['lecture_date_source'],m['lecture_date_source'])}"
