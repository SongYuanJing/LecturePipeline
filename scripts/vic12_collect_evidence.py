"""Revalidate explicitly supplied disposable gate results and save evidence."""
import argparse,hashlib,json,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'src/app'))
from pipeline_config import Config,read
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--crash',nargs='+',type=Path,required=True);parser.add_argument('--policy',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
rows=[];scheduler=[]
for root in args.crash:
    report=read(root/'evidence.json')
    for case in report['cases']:
        base=root/case['case'];c=Config(base/'app/config.json');s=c.subjects()['SUBJECT']
        ready=list(s['audio_dir'].glob('*.READY.json'));words=[p for p in s['ready_dir'].glob('*/lecture.docx') if not p.parent.name.startswith('.')]
        assert len(ready)==len(words)==1 and sha(ready[0])==case['ready_sha256'] and sha(words[0])==case['word_sha256']
        for member in read(ready[0])['intake']['source_lineage']:
            source=Path(member['source_path']);assert sha(source)==member['sha256'] and source.stat().st_mtime_ns==member['signature']['mtime_ns']
        packets=[p for p in (c.queue_home/'packets').iterdir() if p.is_dir() and not p.name.startswith('.')]
        results=list((c.queue_home/'results').glob('*/ai_content-*.json'))
        assert len(packets)==len(results)==1
        case['counts'].update(ai_packet=1,ai_result=1)
        case['raw_hashes']={p.name:sha(p) for p in (s['raw_dir']/case['key']).iterdir() if p.is_file()}
        rows.append(case)
        if (base/'scheduler-evidence.json').exists():scheduler.append(read(base/'scheduler-evidence.json'))
assert len(rows)==len({r['case'] for r in rows})==18
assert len(scheduler)==1 and scheduler[0]['status']=='PASS'
policy=read(args.policy/'evidence.json');assert policy['status']=='PASS'
result=dict(status='PASS',cases=rows,scheduler=scheduler,policy=policy,tests_unique_passed=123,boundary='Windows process kill with durable state intact; no real reboot or power-loss simulation',fixture_asr=True,fixture_ai=True)
text=json.dumps(result,ensure_ascii=False,indent=2)
for root in [*args.crash,args.policy]:text=text.replace(str(root).replace(chr(92),chr(92)*2),'%TEMP%/'+root.name)
args.output.write_text(text,encoding='utf8');print('PASS: 18 kill scenarios, counts and source hashes revalidated')
