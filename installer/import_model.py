"""Explicit verified offline import. No download manager, no model substitution."""
import argparse,hashlib,json,shutil
from pathlib import Path
from launch import ROOT
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def install(source,root=ROOT):
 spec=json.loads((root/'launcher/model-manifest.json').read_text(encoding='utf8'));dest=root/'models/huggingface/hub/models--Systran--faster-whisper-large-v3';snap=dest/'snapshots'/spec['revision']
 if snap.exists():
  if all((snap/n).is_file() and sha(snap/n)==h for n,h in spec['files'].items()):return 'Existing model verified; no copy'
  raise ValueError('Existing model invalid; not overwritten')
 if source is None:raise ValueError('Model missing: provide the verified offline large-v3 snapshot folder')
 for name,h in spec['files'].items():
  if sha(source/name)!=h:raise ValueError('Source model hash mismatch: '+name)
 # mkdir is the existing exclusive staging claim. Do not append to the 40-char
 # revision: that can exceed MAX_PATH although the published snapshot fits.
 pending=snap.parent/'.model.pending';pending.mkdir(parents=True)
 for n,h in spec['files'].items():
  shutil.copy2(source/n,pending/n)
  if sha(pending/n)!=h:raise ValueError('Copied model hash mismatch: '+n)
 pending.rename(snap);(dest/'refs').mkdir(exist_ok=True);(dest/'refs/main').write_text(spec['revision'],encoding='ascii')
 return 'Imported verified large-v3'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path,nargs='?');a=p.parse_args();print(install(a.source))
