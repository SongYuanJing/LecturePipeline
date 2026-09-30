"""Explicit verified optional CUDA import; no driver/global PATH changes."""
import argparse,json,shutil
from pathlib import Path
from launch import ROOT
from import_model import sha

def install(source,root=ROOT):
 spec=json.loads((root/'launcher/cuda-manifest.json').read_text(encoding='utf8'));dest=root/'runtime/cuda/v1.3'
 if dest.exists():
  if all((dest/n).is_file() and sha(dest/n)==h for n,h in spec['files'].items()):return 'Existing CUDA component verified'
  raise ValueError('Existing CUDA component invalid; not overwritten')
 for n,h in spec['files'].items():
  if sha(source/n)!=h:raise ValueError('CUDA source hash mismatch: '+n)
 pending=dest.with_name('v1.3.pending');pending.mkdir(parents=True)
 for n,h in spec['files'].items():
  shutil.copy2(source/n,pending/n)
  if sha(pending/n)!=h:raise ValueError('CUDA copied hash mismatch: '+n)
 shutil.copy2(root/'launcher/cuda-manifest.json',pending/'component.json');pending.rename(dest)
 return 'Imported private CUDA; driver unchanged'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args();print(install(a.source))
