"""Additive local provenance; legacy Drive identifiers retain their meaning."""
import hashlib,json,re
from pathlib import Path

DRIVE_FIELDS=('source_file_id','manifest_file_id','output_docx_file_id','vocabulary_bank_file_id')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def key(source):
 if source.get('provenance',{}).get('kind')=='local':
  p=source['provenance'];raw=Path(p['raw_path']).resolve()
  if source.get('source_key')!=raw.as_uri() or not p.get('workspace'):raise ValueError('Invalid local source identity')
  for name in ('raw_sha256','manifest_sha256'):
   if not re.fullmatch('[0-9a-f]{64}',p.get(name,'')):raise ValueError('Invalid local provenance hash')
  return source['source_key']
 value=source.get('source_file_id')
 if not isinstance(value,str) or not value.strip():raise ValueError('Missing source_file_id or explicit local provenance')
 return value

def local(bundle,workspace):
 if not isinstance(workspace,str) or not workspace.strip():raise ValueError('Local provenance requires workspace')
 raw=Path(bundle['raw_path']).resolve();manifest=Path(bundle['manifest_path']).resolve()
 return dict(source_key=raw.as_uri(),provenance=dict(kind='local',workspace=workspace,raw_path=str(raw),raw_sha256=digest(raw),manifest_path=str(manifest),manifest_sha256=digest(manifest)))

def verify(source,bundle):
 key(source)
 if source.get('provenance',{}).get('kind')=='local':
  expected=local(bundle,source['provenance']['workspace'])
  if source['source_key']!=expected['source_key'] or source['provenance']!=expected['provenance']:raise ValueError('Local source provenance changed')

def drive_fields(receipt,required=False):
 result={}
 for name in DRIVE_FIELDS:
  if required or name in receipt:
   value=receipt.get(name)
   if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9_-]{10,}',value) is None:raise ValueError('Supply real Drive ID: '+name)
   result[name]=value
 return result
