"""Read-only checkpoint history scan. Report locations/rules, never matched secrets."""
import json
from pathlib import Path
import re
import subprocess

REPO=Path(__file__).resolve().parents[1]
BASE='fe69c9bf1304537e4257d41f12fee1035816a60e'
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO)
objects=git('rev-list','--objects',BASE+'..HEAD').decode('utf8').splitlines()
names={line.split(' ',1)[0]:line.split(' ',1)[1] for line in objects if ' ' in line}
proc=subprocess.run(['git','cat-file','--batch'],cwd=REPO,input=('\n'.join(names)+'\n').encode(),capture_output=True,check=True)
data=proc.stdout;offset=0;blobs=[]
while offset<len(data):
    end=data.index(b'\n',offset);header=data[offset:end].decode().split();offset=end+1
    sha,kind,size=header;size=int(size);body=data[offset:offset+size];offset+=size+1
    if kind=='blob':blobs.append((names[sha],body,sha))
for line in git('status','--porcelain','--untracked-files=all').decode('utf8').splitlines():
    name=line[3:]
    p=REPO/name
    if p.is_file():blobs.append((name,p.read_bytes(),'working-tree'))
patterns={
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'access_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{32,})',
 'cloud_access_key':rb'AKIA[0-9A-Z]{16}',
 'credential_url':rb'https?://[^\s/:]+:[^\s/@]+@',
 'personal_home':rb'[A-Za-z]:[\\/]+Users[\\/]+(?!Public\b|<|%)[A-Za-z][A-Za-z0-9_.-]+[\\/]',
}
findings=[]
for name,body,sha in blobs:
    for rule,pattern in patterns.items():
        if re.search(pattern,body):findings.append(dict(path=name,rule=rule,blob=sha))
tracked=git('ls-files','-z').decode('utf8').split('\0')
forbidden={'.wav','.mp3','.m4a','.docx','.xlsx','.exe','.dll','.pyd','.pyc','.zip','.png','.jpg'}
hygiene=[n for n in tracked if n and (Path(n).suffix.lower() in forbidden or any(p in {'__pycache__','.venv','node_modules'} for p in Path(n).parts))]
report=dict(base=BASE,head=git('rev-parse','HEAD').decode().strip(),history_blobs=len(blobs),findings=findings,tracked_artifact_findings=hygiene,
 scope='All new history blobs since remote development checkpoint plus modified/untracked working files; pattern scan and manual review, not a proof of no secret',
 status='PASS' if not findings and not hygiene else 'REVIEW')
print(json.dumps(report,ensure_ascii=False,indent=2))
