"""Explicit one-task local finalize. External AI content is never rewritten.

Resumable orchestration over Word AI, AI queue and the unchanged H3 publisher.
No watcher, network, ASR invocation or chat dependency.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,sys,uuid
from pathlib import Path
# Private _pth runtimes do not add the script directory automatically.
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ai_queue as queue
import atomic_publish
import dictionary_merge as dictionary
import source_provenance as provenance
from pipeline_config import Config,need,read,child

def batch_for(content,bundle,source):
 terms=[]
 for item in content['vocabulary']:
  term={k:v for k,v in item.items() if k in ('chinese','pinyin','russian','note','entry_id','sense_id')}
  term['occurrences']=sum(s['text'].count(item['chinese']) for s in bundle['segments']);terms.append(term)
 return dict(schema_version=1,source=source,terms=terms)

def outputs(out,word):
 report=read(out/'processing_report.json')
 for name,h in report['output_hashes'].items():need(queue.sha(word.local_file(out,name))==h,'Output changed: '+name)
 word.validate_docx(out/'lecture.docx');return report

def finalize(c,identity,content_path):
 c.assert_current();tasks=queue.load_queue(c)['tasks'];need(identity in tasks,'Unknown AI task')
 task=tasks[identity];need(task['workspace']==c.active,'Select the task workspace explicitly first')
 subjects=c.subjects();need(task['subject_code'] in subjects,'Unknown/disabled subject')
 subject=subjects[task['subject_code']];lecture=task['lecture_key']
 source_dir=child(subject['raw_dir'],lecture);manifest=child(source_dir,lecture+'_manifest.json')
 need(Path(task['manifest']).resolve()==manifest,'Task manifest outside configured lecture')
 portable=queue.verify_packet(Path(task['source_packet']).parent);word=queue.module(c)
 need(portable['task']['id']==identity,'Packet belongs to another task')
 actual=word.read_bundle(manifest)
 need({Path(p).name:h for p,h in actual['input_hashes'].items()}==portable['input_hashes'],'Source differs from packet')
 content=read(content_path);word.validate_content(content,portable) # no writes before this point
 out=child(subject['ready_dir'],lecture)
 home=c.queue_home/'finalize'/hashlib.sha256(identity.encode()).hexdigest()[:24]
 home.mkdir(parents=True,exist_ok=True)
 with atomic_publish.transaction_lock(home/'controller'):
  c.assert_current();task=queue.load_queue(c)['tasks'][identity]
  atomic_publish.recover(c.ai_state,home/'state-transactions',word.validate_state)
  atomic_publish.recover(c.dictionary,home/'dictionary-transactions',dictionary.validate_workbook)
  if task['status']=='completed':
   need(queue.sha(task['ai_content'])==task['ai_content_sha256'] and read(task['ai_content'])==content,'Completed task has a different AI result')
   outputs(out,word)
   b=read(out/'vocabulary_batch.json');book=dictionary.Book(c.dictionary.read_bytes());book.validate()
   need(book.metadata().get('source:'+provenance.key(b['source']))==dictionary.digest(dictionary.canonical(b).encode()),'Completed dictionary ledger missing')
   record=read(c.ai_state)['processed'].get(provenance.key(b['source']),{})
   need(record.get('vocabulary_status')=='merged','Completed ai_state inconsistent')
   return dict(status='completed',idempotent=True,word=str(out/'lecture.docx'))
  need(task['status'] in ('waiting_ai','ai_result_ready','building','vocabulary_pending'),'Task needs explicit failure/source review')
  if task['status']!='waiting_ai':need(queue.sha(task['ai_content'])==task['ai_content_sha256'] and read(task['ai_content'])==content,'Different AI result during finalize')
  packet_dir=home/'prepared'
  try:
   if task['status']=='waiting_ai':task=queue.accept_result(c,identity,content_path)
   if not packet_dir.exists():
    need(task['status']=='ai_result_ready','Missing prepared packet; recovery requires review')
    stage=home/('prepare-'+uuid.uuid4().hex)
    queue.prepare_build(c,identity,None,stage)
    stage.rename(packet_dir)
   packet=read(packet_dir/'source_packet.json');rebased=read(packet_dir/'ai_content.json')
   need({**rebased,'input_hashes':portable['input_hashes']}==content,'Prepared content differs from external result')
   word.verify_inputs(packet);provenance.verify(packet['source'],actual)
   source_key=provenance.key(packet['source']);batch=batch_for(rebased,packet,packet['source'])
   # Preview the existing merge before publishing Word/state. Ambiguity fails closed.
   dictionary.merge(c.dictionary.read_bytes(),batch)
   if task['status']=='ai_result_ready':
    task=queue.transition(c,identity,'building',dict(prepared_packet=str(packet_dir/'source_packet.json')))
   if not out.exists():
    need(task['status']=='building','Missing committed Word output; manual recovery required')
    word.build(packet_dir/'source_packet.json',packet_dir/'ai_content.json',out)
   report=outputs(out,word)
   need(read(out/'ai_content.json')==rebased and read(out/'vocabulary_batch.json')==batch,'Existing output belongs to another result')
   need(report['source']==packet['source'] and not report['pilot'],'Word provenance mismatch')
   if task['status']=='building':task=queue.transition(c,identity,'vocabulary_pending',dict(processing_report=str(out/'processing_report.json')))
   state=read(c.ai_state);record=state['processed'].get(source_key)
   if record is None:
    receipt=dict(report_sha256=queue.sha(out/'processing_report.json'),local_validation='schema_refs_docx_v1',source_key=source_key)
    queue.atomic(home/'word-review.json',receipt)
    word.commit(out,c.ai_state,home/'word-review.json',home/'state-transactions')
   else:
    need(record.get('output_docx_local_path')==str(out/'lecture.docx') and record.get('output_provenance',{}).get('sha256')==queue.sha(out/'lecture.docx'),'Existing ai_state does not match finalized output')
   # Recover any interrupted H3 transaction using its own stable backup root.
   old=c.dictionary.read_bytes();merged,merge_report=dictionary.merge(old,batch)
   transaction_path=home/'dictionary-transaction.json'
   if merged!=old:
    transaction=atomic_publish.publish(c.dictionary,dictionary.digest(old),lambda data:dictionary.merge(data,batch)[0],dictionary.validate_workbook,home/'dictionary-transactions')
    queue.atomic(transaction_path,transaction)
   elif not transaction_path.exists():
    # A crash may follow committed replacement but precede controller checkpoint.
    matches=[]
    for p in (home/'dictionary-transactions').glob('*/transaction.json'):
     r=read(p)
     if r.get('status')=='committed' and r.get('after')==queue.sha(c.dictionary):matches.append(r)
    need(len(matches)==1,'Dictionary already merged without a unique transaction receipt; review required')
    queue.atomic(transaction_path,matches[0])
   transaction=read(transaction_path)
   need(transaction['after']==queue.sha(c.dictionary),'Dictionary changed after finalize transaction; review required')
   old=c.ai_state.read_bytes()
   def finish_state(data):
    value=json.loads(data.decode('utf-8-sig'));entry=value['processed'][source_key]
    entry['vocabulary_status']='merged';entry['vocabulary_batch_sha256']=queue.sha(out/'vocabulary_batch.json')
    entry['dictionary_provenance']=dict(kind='local',path=str(c.dictionary),sha256=transaction['after'],transaction=str(transaction_path))
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')
   atomic_publish.publish(c.ai_state,atomic_publish.sha(old),finish_state,word.validate_state,home/'state-transactions')
   c.assert_current();word.verify_inputs(packet)
   queue.transition(c,identity,'completed',dict(dictionary_transaction=str(transaction_path),vocabulary_batch=str(out/'vocabulary_batch.json'),processing_report=str(out/'processing_report.json')))
   queue.atomic(home/'result.json',dict(status='completed',word=str(out/'lecture.docx'),dictionary=merge_report))
   return dict(status='completed',idempotent=False,word=str(out/'lecture.docx'),dictionary=merge_report)
  except Exception as exc:
   queue.atomic(home/'last-error.json',dict(task=identity,error=str(exc),recoverable=True))
   raise

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--task',required=True);p.add_argument('--content',required=True);a=p.parse_args()
 try:result=finalize(Config(a.config),a.task,Path(a.content))
 except Exception as exc:print('AI finalize failed: '+str(exc),file=sys.stderr);return 2
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
