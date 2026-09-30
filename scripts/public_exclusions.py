"""Fail closed on private/native/user artifacts in a thin public archive."""
from pathlib import PurePosixPath
import re,zipfile

def forbidden(name):
 p=PurePosixPath(name.lower());parts=p.parts;base=p.name
 if any(x=='av' or x=='av.libs' or re.fullmatch(r'av-.*\.dist-info',x) for x in parts):return True
 if any(x in {'ctranslate2','ctranslate2.libs'} or re.fullmatch(r'ctranslate2-.*\.(dist-info|data)',x) for x in parts):return True
 if base in {'ctranslate2.dll','libiomp5md.dll'} or (base.startswith('_ext') and base.endswith('.pyd')):return True
 if base.endswith('.whl') and base.startswith(('av-','ctranslate2-','intel_openmp-','nvidia_')):return True
 if base.endswith(('.dll','.pyd')) and (re.match(r'(lib)?(avcodec|avformat|avutil|avfilter|avdevice|swresample|swscale|x264|x265)',base) or re.match(r'(cudnn|cublas|nvblas|nvcuda)',base)):return True
 if parts and parts[0] in {'models','config','run','logs','data','raw','word','audio','dialogue','vocabulary','backups'}:return True
 if base in {'config.json','worker_status.json','status.json'}:return True
 if len(parts)>1 and parts[:2]==('runtime','cuda'):return True
 if base in {'model.bin','state.json','ai_state.json','dialogue_state.json'}:return True
 if p.suffix in {'.wav','.mp3','.m4a','.xlsx','.srt'}:return True
 if p.suffix=='.docx' and name!='runtime/document/Lib/site-packages/docx/templates/default.docx':return True
 return False

def check(names):
 bad=[n for n in names if forbidden(n)]
 if bad:raise ValueError('Public ZIP exclusion failure: '+repr(bad))

def check_zip(path):
 with zipfile.ZipFile(path) as z:check(z.namelist())
