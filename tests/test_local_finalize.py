import copy,json,sys,tempfile,unittest,importlib.util,shutil
from pathlib import Path
from unittest.mock import patch
REPO=Path(__file__).resolve().parent.parent;APP=REPO/'src/app'
sys.path[:0]=[str(APP),str(APP/'word_ai_v1.5'),str(REPO/'installer')]
import ai_queue as aq
import ai_finalize as f
import lecture_ai as word
import dictionary_merge as dm
import source_provenance as provenance
from pipeline_config import Config
from create_dictionary import create

def dump(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def fixture(base):
 home=base/'app';home.mkdir();shutil.copytree(APP,home/'code');data=base/'data';data.mkdir();d=json.loads((REPO/'config.example.json').read_text())
 d.update(install_root='code',application_home='.',data_root=str(data));d['runtimes'].update(document_python=sys.executable,asr_python=sys.executable)
 cfg=home/'config.json';dump(cfg,d);c=Config(cfg)
 for s in c.subjects().values():
  for key in ('audio_dir','raw_dir','ready_dir'):s[key].mkdir(parents=True)
 dump(c.state,dict(version=1,lectures={}));dump(c.ai_state,dict(schema_version=1,processed={}))
 create(c.dictionary,APP);return c
def lecture(c,key='01_2030-01-01',empty=False):
 code=next(iter(c.subjects()));s=c.subjects()[code];folder=s['raw_dir']/key;folder.mkdir()
 (folder/'part.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\n测试内容\n',encoding='utf8')
 (folder/(key+'_raw.txt')).write_text('[00:00 - 00:01] 测试内容\n',encoding='utf8')
 dump(folder/(key+'_manifest.json'),dict(lecture=key,subject_code=code,subject=s['title'],sources=[dict(name='part.wav')],outputs=[dict(source='part.wav',srt='part.srt')],combined_txt=key+'_raw.txt'))
 state=aq.read(c.state);state['lectures'][code+'/'+key]=dict(status='completed');dump(c.state,state)
 identity=c.active+'/'+code+'/'+key;q=aq.refresh(c);packet=aq.verify_packet(Path(q['tasks'][identity]['source_packet']).parent)
 block=dict(text='Тестовое объяснение',basis='transcript',refs=[dict(start='1:1',end='1:1')])
 content=dict(schema_version=1,input_hashes=packet['input_hashes'],title='Тест',organization={k:dict(status='not_found',items=[]) for k in word.ORG},summary=[block],notes=[block],definitions=[block],formulas=[],emphasis=[block],uncertainties=[],part_review=[dict(part=1,status='usable',note='Reviewed')],vocabulary=[] if empty else [dict(chinese='测试',pinyin='ceshi',russian='тест',refs=block['refs'])])
 path=c.home/(key+'.json');dump(path,content);return identity,path,folder

class LocalFinalizeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.c=fixture(self.base)
 def test_local_end_to_end_and_idempotent(self):
  identity,p,folder=lecture(self.c);before={str(x):x.read_bytes() for x in folder.iterdir()}
  result=f.finalize(self.c,identity,p);self.assertEqual(result['status'],'completed');word.validate_docx(result['word'])
  state=aq.read(self.c.ai_state);key,record=next(iter(state['processed'].items()));self.assertTrue(key.startswith('file:///'));self.assertNotIn('source_file_id',record);self.assertEqual(record['vocabulary_status'],'merged')
  saved=(self.c.ai_state.read_bytes(),self.c.dictionary.read_bytes(),(self.c.queue_home/'queue.json').read_bytes())
  self.assertTrue(f.finalize(self.c,identity,p)['idempotent']);self.assertEqual(saved,(self.c.ai_state.read_bytes(),self.c.dictionary.read_bytes(),(self.c.queue_home/'queue.json').read_bytes()))
  self.assertTrue(all(Path(n).read_bytes()==v for n,v in before.items()))
 def test_invalid_answer_no_mutation(self):
  identity,p,folder=lecture(self.c);content=aq.read(p);content['notes'][0]['refs'][0]['quote']='not in source';dump(p,content)
  before={n:n.read_bytes() for n in (self.c.ai_state,self.c.dictionary,self.c.queue_home/'queue.json')}
  with self.assertRaisesRegex(ValueError,'Quote'):f.finalize(self.c,identity,p)
  self.assertTrue(all(n.read_bytes()==v for n,v in before.items()));self.assertFalse((self.c.queue_home/'finalize').exists())
 def test_empty_vocabulary_completed(self):
  identity,p,_=lecture(self.c,empty=True);f.finalize(self.c,identity,p)
  self.assertEqual(dm.Book(self.c.dictionary.read_bytes()).validate()['words'],0);self.assertTrue(f.finalize(self.c,identity,p)['idempotent'])
 def test_manual_fields_and_second_lecture(self):
  identity,p,_=lecture(self.c);f.finalize(self.c,identity,p);b=dm.Book(self.c.dictionary.read_bytes());row=next(iter(b.entries().values()))[0]
  for col,v in [('A','Выучено'),('D','ручной перевод'),('G','ручная заметка')]:b.put(dm.MAIN,f'{col}{row}',v)
  self.c.dictionary.write_bytes(b.save()) # disposable user's manual edit
  identity,p,_=lecture(self.c,'02_2030-01-01');f.finalize(self.c,identity,p);b=dm.Book(self.c.dictionary.read_bytes());v=b.values(dm.MAIN,row)
  self.assertEqual((v[0],v[3],v[6]),('Выучено','ручной перевод','ручная заметка'));self.assertEqual(v[5],2);self.assertEqual(len(b.entries()),1)
 def test_existing_unrelated_word_not_overwritten(self):
  identity,p,_=lecture(self.c);out=next(iter(self.c.subjects().values()))['ready_dir']/'01_2030-01-01';out.mkdir();(out/'lecture.docx').write_bytes(b'keep')
  with self.assertRaises(Exception):f.finalize(self.c,identity,p)
  self.assertEqual((out/'lecture.docx').read_bytes(),b'keep');self.assertEqual(aq.read(self.c.ai_state)['processed'],{})
 def test_resume_after_dictionary_failure(self):
  identity,p,_=lecture(self.c)
  with patch.object(dm,'validate_workbook',side_effect=ValueError('injected validation failure')):
   with self.assertRaisesRegex(ValueError,'injected'):f.finalize(self.c,identity,p)
  self.assertEqual(aq.load_queue(self.c)['tasks'][identity]['status'],'vocabulary_pending')
  self.assertEqual(f.finalize(self.c,identity,p)['status'],'completed')
 def test_resume_after_completed_transition_failure(self):
  identity,p,_=lecture(self.c);original=aq.transition
  def fail(c,i,status,evidence):
   if status=='completed':raise RuntimeError('interrupted before queue checkpoint')
   return original(c,i,status,evidence)
  with patch.object(aq,'transition',side_effect=fail),self.assertRaises(RuntimeError):f.finalize(self.c,identity,p)
  before=self.c.dictionary.read_bytes();f.finalize(self.c,identity,p);self.assertEqual(before,self.c.dictionary.read_bytes())
 def test_recover_interrupted_h3_dictionary_publish(self):
  identity,p,_=lecture(self.c);original=f.atomic_publish.publish
  def interrupted(target,*args,**kw):
   if Path(target)==self.c.dictionary:
    def checkpoint(name):
     if name=='before_postverify':raise RuntimeError('interrupted dictionary postverify')
    kw['checkpoint']=checkpoint
   return original(target,*args,**kw)
  with patch.object(f.atomic_publish,'publish',side_effect=interrupted),self.assertRaises(RuntimeError):f.finalize(self.c,identity,p)
  self.assertEqual(aq.load_queue(self.c)['tasks'][identity]['status'],'vocabulary_pending')
  self.assertEqual(f.finalize(self.c,identity,p)['status'],'completed')
  self.assertEqual(dm.Book(self.c.dictionary.read_bytes()).validate()['occurrences'],1)
 def test_same_task_controller_serialized(self):
  import hashlib
  identity,p,_=lecture(self.c);home=self.c.queue_home/'finalize'/hashlib.sha256(identity.encode()).hexdigest()[:24];home.mkdir(parents=True)
  with f.atomic_publish.transaction_lock(home/'controller'),self.assertRaises(OSError):f.finalize(self.c,identity,p)
  self.assertEqual(aq.load_queue(self.c)['tasks'][identity]['status'],'waiting_ai')
 def test_source_change_rejected(self):
  identity,p,folder=lecture(self.c);(folder/'part.srt').write_text('changed')
  with self.assertRaises(ValueError):f.finalize(self.c,identity,p)
  self.assertEqual(aq.load_queue(self.c)['tasks'][identity]['status'],'waiting_ai')
 def test_wrong_subject_scope(self):
  identity,p,_=lecture(self.c)
  with self.assertRaises(ValueError):f.finalize(self.c,identity.replace('/','/WRONG/',1),p)
 def test_drive_compatibility(self):
  identity,p,folder=lecture(self.c);manifest=next(folder.glob('*manifest.json'));packet=self.base/'drive-packet'
  b=word.prepare(manifest,self.c.ai_state,'FIXTURE_SOURCE_123',packet);content=aq.read(p);content['input_hashes']=b['input_hashes'];dump(self.base/'drive-content.json',content)
  out=self.base/'drive-word';word.build(packet/'source_packet.json',self.base/'drive-content.json',out)
  receipt=dict(report_sha256=aq.sha(out/'processing_report.json'),content_reviewed=True,all_pages_visually_checked=True,source_file_id='FIXTURE_SOURCE_123',manifest_file_id='FIXTURE_MANIFEST_123',output_docx_file_id='FIXTURE_DOCX_123',vocabulary_bank_file_id='FIXTURE_BANK_123')
  dump(self.base/'review.json',receipt);word.commit(out,self.c.ai_state,self.base/'review.json',self.base/'backups');record=aq.read(self.c.ai_state)['processed']['FIXTURE_SOURCE_123']
  for k in provenance.DRIVE_FIELDS:self.assertEqual(record[k],receipt[k])
  data,report=dm.merge(self.c.dictionary.read_bytes(),aq.read(out/'vocabulary_batch.json'));self.assertEqual(report['added'],1)
 def test_legacy_drive_missing_ids_rejected(self):
  with self.assertRaisesRegex(ValueError,'Drive ID'):provenance.drive_fields({},required=True)
 def test_fake_local_identity_rejected(self):
  with self.assertRaises(ValueError):provenance.key(dict(source_key='local-123',provenance=dict(kind='local',raw_path=str(self.base/'x'),workspace='s')))

if __name__=='__main__':unittest.main()

