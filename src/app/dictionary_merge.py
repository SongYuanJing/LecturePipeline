"""Dictionary-only v1.4. Targeted OOXML merge; never reads/writes ASR or ai_state.

Python standard library only. Unchanged ZIP parts and existing manual cells are
retained; artifact-generated initial layout is not regenerated during updates.
"""
from __future__ import annotations
import argparse,copy,ctypes,datetime,hashlib,io,json,math,os,re,sys,uuid,zipfile,unicodedata
from contextlib import contextmanager
from pathlib import Path,PurePosixPath
from xml.dom import minidom
import atomic_publish
import source_provenance as provenance_identity

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
MAIN='词汇总库';PROV='Источники';META='Служебный'
HEAD=['Выучено','中文','Pinyin','Русский','Предмет','Встречалось','Примечание','ID слова']
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(value):return ' '.join(unicodedata.normalize('NFC',str(value or '')).strip().split()).casefold()
def text(node):return ''.join(n.data if n.nodeType in (n.TEXT_NODE,n.CDATA_SECTION_NODE) else text(n) for n in node.childNodes)
def elements(node,tag):return list(node.getElementsByTagNameNS(NS,tag))
def make(doc,tag):return doc.createElementNS(NS,(doc.documentElement.prefix+':' if doc.documentElement.prefix else '')+tag)
def child(node,tag):return next((n for n in node.childNodes if n.nodeType==n.ELEMENT_NODE and n.localName==tag),None)
def integer(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or int(value)!=value:raise ValueError('occurrences must be a nonnegative integer')
    return int(value)

class Book:
    def __init__(self,data):
        self.original=data
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.infos=z.infolist();self.parts={i.filename:z.read(i.filename) for i in self.infos};assert z.testzip() is None
        self.docs={};self.changed=set();self.rowcache={};self.cellcache={}
        self.strings=[text(s) for s in elements(minidom.parseString(self.parts['xl/sharedStrings.xml']),'si')] if 'xl/sharedStrings.xml' in self.parts else []
        rel=minidom.parseString(self.parts['xl/_rels/workbook.xml.rels'])
        targets={n.getAttribute('Id'):n.getAttribute('Target') for n in rel.documentElement.childNodes if n.nodeType==n.ELEMENT_NODE}
        wb=self.doc('xl/workbook.xml');self.sheets={}
        for s in elements(wb,'sheet'):
            target=targets[s.getAttributeNS(REL,'id')]
            path=target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl')/target)
            self.sheets[s.getAttribute('name')]=path
        for name in (MAIN,PROV,META):
            if name not in self.sheets:raise ValueError('Not a migrated v1.4 dictionary: '+name)
        if self.values(MAIN,4)[:8]!=HEAD:raise ValueError('Dictionary headers changed; refusing positional merge')
        if self.metadata().get('schema_version')!='1.4':raise ValueError('Unsupported dictionary schema')
    def doc(self,path):
        if path not in self.docs:self.docs[path]=minidom.parseString(self.parts[path])
        return self.docs[path]
    def sheet(self,name):return self.doc(self.sheets[name])
    def rows(self,name):return elements(self.sheet(name),'sheetData')[0].getElementsByTagNameNS(NS,'row')
    def cell_value(self,c):
        if c is None:return None
        typ=c.getAttribute('t');v=child(c,'v')
        if typ=='inlineStr':return text(child(c,'is')) if child(c,'is') is not None else ''
        if v is None:return None
        raw=text(v)
        if typ=='s':return self.strings[int(raw)]
        if typ=='b':return raw=='1'
        if typ in ('str','e'):return raw
        try:return float(raw) if '.' in raw or 'e' in raw.lower() else int(raw)
        except ValueError:return raw
    def row(self,name,number,create=False):
        if name not in self.rowcache:self.rowcache[name]={int(r.getAttribute('r')):r for r in self.rows(name)}
        found=self.rowcache[name].get(number)
        if found is None and create:
            doc=self.sheet(name);found=make(doc,'row');found.setAttribute('r',str(number));elements(doc,'sheetData')[0].appendChild(found)
            self.rowcache[name][number]=found
        return found
    def cell(self,name,address,create=False):
        if (name,address) in self.cellcache:return self.cellcache[name,address]
        n=int(re.search(r'\d+',address)[0]);r=self.row(name,n,create)
        if r is None:return None
        found=next((c for c in elements(r,'c') if c.getAttribute('r')==address),None)
        if found is None and create:
            found=make(self.sheet(name),'c');found.setAttribute('r',address);r.appendChild(found)
        if found is not None:self.cellcache[name,address]=found
        return found
    def values(self,name,number):
        return [self.cell_value(self.cell(name,f'{c}{number}')) for c in ('ABCDEFGH' if name==MAIN else 'ABCDEFGHIJKLM' if name==PROV else 'AB')]
    def put(self,name,address,value):
        if isinstance(value,str) and len(value)>32767:raise ValueError('Excel cell text exceeds 32767 characters')
        doc=self.sheet(name);c=self.cell(name,address,True)
        for n in list(c.childNodes):c.removeChild(n)
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            if not math.isfinite(value):raise ValueError('Non-finite cell')
            c.setAttribute('t','n');v=make(doc,'v');v.appendChild(doc.createTextNode(str(value)));c.appendChild(v)
        else:
            c.setAttribute('t','inlineStr');s=make(doc,'is');t=make(doc,'t');t.setAttribute('xml:space','preserve');t.appendChild(doc.createTextNode('' if value is None else str(value)));s.appendChild(t);c.appendChild(s)
        self.changed.add(self.sheets[name])
    def append(self,name,values):
        number=max([int(r.getAttribute('r')) for r in self.rows(name)]+[0])+1
        previous=self.row(name,number-1);new=self.row(name,number,True)
        if previous is not None:
            for k in ('ht','customHeight','s','customFormat'):
                if previous.hasAttribute(k):new.setAttribute(k,previous.getAttribute(k))
        for col,value in zip('ABCDEFGHIJKLM',values):
            self.put(name,f'{col}{number}',value)
            old=self.cell(name,f'{col}{number-1}')
            if old is not None and old.hasAttribute('s'):self.cell(name,f'{col}{number}').setAttribute('s',old.getAttribute('s'))
        dim=elements(self.sheet(name),'dimension')
        if dim:dim[0].setAttribute('ref',f'A1:{"H" if name==MAIN else "M" if name==PROV else "B"}{number}')
        if name==MAIN:
            self.expand_main_table(number)
        return number
    def expand_main_table(self,number):
        for path in self.parts:
            if path.startswith('xl/tables/') and path.endswith('.xml'):
                doc=self.doc(path)
                if doc.documentElement.getAttribute('name')=='VocabularyBank':
                    last=max(number,int(re.search(r'\d+$',doc.documentElement.getAttribute('ref'))[0]))
                    doc.documentElement.setAttribute('ref',f'A4:H{last}')
                    for node in elements(doc,'autoFilter'):node.setAttribute('ref',f'A4:H{last}')
                    self.changed.add(path)
    def ensure_row_height(self,number):
        def lines(value,budget):
            total=0
            for paragraph in str(value or '').split('\n'):
                used=0;count=1
                for word in paragraph.split():
                    width=sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 0 if unicodedata.combining(c) else 1 for c in word)
                    if used and used+1+width>budget:count+=1;used=0
                    if width>budget:count+=(width-1)//budget;used=width%budget or budget
                    else:used+=width+(1 if used else 0)
                total+=count
            return total
        needed=min(409,max(46,10+14*max(lines(v,w) for v,w in zip(self.values(MAIN,number)[:7],[13,18,20,28,25,14,42]))))
        row=self.row(MAIN,number)
        if float(row.getAttribute('ht') or 0)<needed:
            row.setAttribute('ht',str(needed));row.setAttribute('customHeight','1');self.changed.add(self.sheets[MAIN])
    def metadata(self):return {self.values(META,int(r.getAttribute('r')))[0]:self.values(META,int(r.getAttribute('r')))[1] for r in self.rows(META) if int(r.getAttribute('r'))>1}
    def entries(self):
        entries={}
        for r in self.rows(MAIN):
            n=int(r.getAttribute('r'))
            if n<5:continue
            v=self.values(MAIN,n)
            if not any(x is not None and x!='' for x in v):continue
            if not v[1] or not v[7]:raise ValueError(f'Row {n} lacks Chinese or stable ID; use the merge tool to add new words')
            if v[7] in entries:raise ValueError('Duplicate entry ID')
            integer(v[5]);entries[v[7]]=(n,v)
        return entries
    def provenance(self):return [self.values(PROV,int(r.getAttribute('r'))) for r in self.rows(PROV) if int(r.getAttribute('r'))>1]
    def adopt_manual_rows(self):
        known={(norm(self.values(MAIN,int(r.getAttribute('r')))[1]),norm(self.values(MAIN,int(r.getAttribute('r')))[2]),norm(self.values(MAIN,int(r.getAttribute('r')))[3]))
               for r in self.rows(MAIN) if int(r.getAttribute('r'))>=5 and self.values(MAIN,int(r.getAttribute('r')))[7]}
        for r in list(self.rows(MAIN)):
            n=int(r.getAttribute('r'));v=self.values(MAIN,n)
            if n<5 or v[7] or not any(x is not None and x!='' for x in v):continue
            if not v[1] or not v[2] or not v[3]:raise ValueError('Manual new row requires Chinese, pinyin, translation')
            identity=(norm(v[1]),norm(v[2]),norm(v[3]))
            if identity in known:raise ValueError('Manual duplicate requires review; fields left intact')
            known.add(identity);key='w_'+uuid.uuid4().hex[:24];count=integer(0 if v[5] in (None,'') else v[5])
            self.put(MAIN,f'H{n}',key);self.put(MAIN,f'F{n}',count)
            self.expand_main_table(n)
            self.ensure_row_height(n)
            self.append(PROV,[key,'manual','manual:'+key,v[1],v[2],v[3],count,v[4],None,None,None,None,canonical(dict(manual_row=n,values=v))])
    def validate(self):
        entries=self.entries();totals={k:0 for k in entries};events=set()
        for p in self.provenance():
            if p[0] not in entries or p[2] in events:raise ValueError('Missing entry or duplicate provenance event')
            if norm(p[3])!=norm(entries[p[0]][1][1]):raise ValueError('Chinese/ID mismatch; possible partial-range sort')
            events.add(p[2]);totals[p[0]]+=integer(p[6]);json.loads(p[12])
        for k,(n,v) in entries.items():
            if totals[k]!=v[5]:raise ValueError(f'Counter/provenance mismatch at row {n}; no overwrite')
        if not any(d.getAttribute('sqref')=='A5:A1048576' for d in elements(self.sheet(MAIN),'dataValidation')):raise ValueError('Status validation must cover future rows')
        return dict(words=len(entries),unique_chinese=len({norm(v[1]) for n,v in entries.values()}),occurrences=sum(totals.values()),provenance=len(events))
    def save(self):
        if not self.changed:return self.original
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            for info in self.infos:z.writestr(info,self.docs[info.filename].toxml(encoding='utf-8') if info.filename in self.changed else self.parts[info.filename])
        result=buf.getvalue();Book(result).validate();return result

def merge(data,batch):
    b=Book(data);b.adopt_manual_rows();before=b.validate();meta=b.metadata()
    if batch.get('schema_version')!=1:raise ValueError('Batch schema_version must be 1')
    source=batch['source'];terms=batch['terms']
    for key in ('source_signature','subject_code','subject','lecture_id','source_file_name'):
        if not isinstance(source.get(key),str) or not source[key].strip():raise ValueError('Required source field: '+key)
    source_id=provenance_identity.key(source);batch_hash=digest(canonical(batch).encode())
    baseline=json.loads(meta['baseline_ai_state'])['processed']
    if source_id in baseline or any(source_id==r.get('source_file_id') for r in baseline.values()):return b.save(),dict(status='already_processed_legacy',**before)
    if any(source['subject_code']==r.get('subject_code') and source['lecture_id']==r.get('lecture_id') for r in baseline.values()):return b.save(),dict(status='already_processed_legacy_lecture',**before)
    ledger_key='source:'+source_id
    if ledger_key in meta:
        if meta[ledger_key]!=batch_hash:raise ValueError('Previously merged source changed; review required, no recount')
        return b.save(),dict(status='already_merged',**before)
    if not isinstance(terms,list):raise ValueError('terms must be a list')
    entries=b.entries();provenance=b.provenance();seen=set();added=updated=0
    for term in terms:
        word=term.get('chinese');py=term.get('pinyin');ru=term.get('russian');count=integer(term.get('occurrences'))
        if not isinstance(word,str) or not word.strip():raise ValueError('Chinese term is required')
        candidates=[k for k,(n,v) in entries.items() if norm(v[1])==norm(word)]
        key=term.get('entry_id');sense=term.get('sense_id')
        if sense:
            if not isinstance(sense,str):raise ValueError('sense_id must be a stable string')
            sense_key='w_'+digest((norm(word)+'\0sense\0'+sense).encode())[:24]
            if key and key!=sense_key:raise ValueError('entry_id conflicts with sense_id')
            key=sense_key
        if key:
            if key not in entries and not sense:raise ValueError('Unknown entry_id')
            if key in entries and key not in candidates:raise ValueError('entry_id does not match Chinese')
        elif candidates:
            matches={p[0] for p in provenance if p[0] in candidates and norm(p[4])==norm(py) and norm(p[5])==norm(ru)}
            if len(matches)!=1:raise ValueError('Ambiguous meaning: '+word+'; provide existing entry_id or distinct sense_id')
            key=next(iter(matches))
        else:key='w_'+digest(canonical([norm(word),norm(py),norm(ru)]).encode())[:24]
        if key in seen:raise ValueError('Duplicate term within batch; aggregate occurrences first')
        seen.add(key)
        if key not in entries:
            if not isinstance(py,str) or not py.strip() or not isinstance(ru,str) or not ru.strip():raise ValueError('New term requires pinyin and russian')
            if candidates and not sense:raise ValueError('Distinct sense_id required for a new meaning')
            v=['Не выучено',word,py,ru,source['subject'],count,term.get('note'),key]
            n=b.append(MAIN,v);entries[key]=(n,v);added+=1
        else:
            n,v=entries[key]
            # Never write A/B/C/D/G: even blanked manual values are intentional.
            subjects=[s.strip() for s in str(v[4] or '').split(';') if s.strip()]
            if source['subject'] not in subjects:subjects.append(source['subject'])
            b.put(MAIN,f'E{n}','; '.join(subjects));b.put(MAIN,f'F{n}',integer(v[5])+count)
            entries[key]=(n,b.values(MAIN,n));updated+=1
        b.ensure_row_height(n)
        b.append(PROV,[key,'event',source_id+':'+key,word,py,ru,count,source['subject'],source['lecture_id'],source_id,source['source_signature'],source['source_file_name'],canonical(dict(source=source,term=term))])
    b.append(META,[ledger_key,batch_hash]);result=b.save()
    return result,dict(status='merged',added=added,updated=updated,**Book(result).validate())

def finish_migration(data):
    b=Book(data);doc=b.sheet(MAIN)
    for n,v in b.entries().values():b.ensure_row_height(n)
    # Split exported grouped column declarations; hide only stable ID column H.
    cols=elements(doc,'cols')[0]
    for c in list(elements(cols,'col')):
        lo,hi=int(c.getAttribute('min')),int(c.getAttribute('max'))
        if lo<=8<=hi:
            for start,end,hidden in [(lo,7,False),(8,8,True),(9,hi,False)]:
                if start>end:continue
                n=c.cloneNode(True);n.setAttribute('min',str(start));n.setAttribute('max',str(end))
                if hidden:n.setAttribute('hidden','1')
                cols.insertBefore(n,c)
            cols.removeChild(c)
    b.changed.add(b.sheets[MAIN])
    for s in elements(b.doc('xl/workbook.xml'),'sheet'):
        if s.getAttribute('name')==META:s.setAttribute('state','hidden')
    b.changed.add('xl/workbook.xml');return b.save()

@contextmanager
def exclusive(path):
    with atomic_publish.exclusive(path) as f:yield f

def validate_workbook(data,*,legacy_restore=False):
    if legacy_restore:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if z.testzip() is not None:raise ValueError('Invalid rollback workbook')
    else:Book(data).validate()
    try:
        from openpyxl import load_workbook
    except ImportError:
        # Reuse the installed document runtime; never install a second runtime.
        import subprocess
        from pipeline_config import Config
        python=Config().runtime('document_python','.venv/Scripts/python.exe')
        code='import sys,io;from openpyxl import load_workbook;w=load_workbook(io.BytesIO(sys.stdin.buffer.read()));w.close()'
        r=subprocess.run([str(python),'-B','-c',code],input=data,capture_output=True,timeout=60,creationflags=0x08000000 if os.name=='nt' else 0)
        if r.returncode:raise ValueError('openpyxl validation failed: '+r.stderr.decode('utf8',errors='replace'))
    else:
        w=load_workbook(io.BytesIO(data));w.close()

def publish(path,result,expected,backup_dir,*,legacy_restore=False):
    validate=lambda data:validate_workbook(data,legacy_restore=legacy_restore)
    receipt=atomic_publish.publish(path,expected,lambda old:result,validate,backup_dir)
    return str(receipt['backup']) if receipt else None

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--book',type=Path,required=True);ap.add_argument('--batch',type=Path);ap.add_argument('--apply',action='store_true');ap.add_argument('--find');ap.add_argument('--backup-dir',type=Path,default=Path(__file__).parent/'dictionary_backups')
    args=ap.parse_args();data=args.book.read_bytes()
    if args.find is not None:
        print(canonical([dict(entry_id=k,chinese=v[1],pinyin=v[2],russian=v[3],subject=v[4]) for k,(n,v) in Book(data).entries().items() if norm(v[1])==norm(args.find)]));return
    if not args.batch:print(canonical(Book(data).validate()));return
    result,report=merge(data,json.loads(args.batch.read_text(encoding='utf-8-sig')))
    report['written']=False
    if args.apply and result!=data:report['backup']=publish(args.book,result,digest(data),args.backup_dir);report['written']=True
    print(canonical(report))
if __name__=='__main__':main()
