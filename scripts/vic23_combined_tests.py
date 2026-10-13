"""One practical combined run on a fresh disposable configuration; no setup/download."""
import argparse,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'tests'),str(REPO/'src/app'),str(REPO/'src/app/gui_v1.8'),str(REPO/'src/app/dialogue_v1.6'),str(REPO/'installer')]
from test_local_finalize import fixture,dump
parser=argparse.ArgumentParser();parser.add_argument('--python311',required=True);args=parser.parse_args()
base=Path(tempfile.mkdtemp(prefix='LP-vic23-tests-'));c=fixture(base)
d=c.data;d['task_prefix']='LP-0123456789ab';dump(c.path,d);(c.home/'logs').mkdir(exist_ok=True)
os.environ.update(LECTURE_CONFIG=str(c.path),PACKAGING_REPO=str(REPO))
abi=['test_ctranslate2_component','test_component_staging']
modules=sorted(p.stem for p in (REPO/'tests').glob('test*.py') if p.stem not in abi+['test_packaging'])
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
def walk(s):
 for test in s:
  if isinstance(test,unittest.TestSuite):yield from walk(test)
  else:yield test
cases=list(walk(suite))
started=time.perf_counter()
with (base/'combined.log').open('w',encoding='utf8') as log:
 result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
identity=unittest.TestCase.id # Some legacy fixtures assign a string to self.id.
env=dict(os.environ,PYTHONPATH=os.pathsep.join(str(REPO/p) for p in ('tests','src/app','installer','scripts')))
child=subprocess.run([args.python311,'-B','-X','utf8','-m','unittest',*abi,'-v'],env=env,capture_output=True,text=True,encoding='utf8')
(base/'abi.log').write_text(child.stdout+child.stderr,encoding='utf8')
abi_count=unittest.defaultTestLoader.loadTestsFromNames(abi).countTestCases()
report=dict(root=str(base),total=result.testsRun+abi_count,distinct=len({identity(t) for t in cases})+abi_count,
 passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped)+(abi_count if child.returncode==0 else 0),
 failures=[(identity(t),msg) for t,msg in result.failures],errors=[(identity(t),msg) for t,msg in result.errors],skipped=[(identity(t),reason) for t,reason in result.skipped],
 abi_count=abi_count,abi_exit=child.returncode,excluded='test_packaging requires installed release layout; no release built for VIC-23',
 seconds=time.perf_counter()-started,status='PASS' if result.wasSuccessful() and child.returncode==0 else 'FAIL')
dump(base/'evidence.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
raise SystemExit(0 if report['status']=='PASS' else 1)
