import argparse,os
from pathlib import Path
from dialogue_worker import load,write,single_instance,DIRS
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);subs=p.add_subparsers(dest='command',required=True)
 s=subs.add_parser('retry');s.add_argument('--job',required=True)
 s=subs.add_parser('language');s.add_argument('--file',required=True);s.add_argument('--language',choices=['auto','zh','en'],required=True)
 a=p.parse_args();cfg=load(a.config) if Path(a.config).is_file() else {}
 central=Path(os.environ.get('LECTURE_CONFIG',str(Path(a.config).resolve().parent.parent/'config.json')))
 if central.is_file():
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent));from pipeline_config import Config
  cfg=Config(central).dialogue()
 if a.command=='language':
  if Path(a.file).name!=a.file:raise ValueError('Supply filename only')
  path=Path(cfg['root'])/DIRS[3]/'task_options.json';x=load(path) if path.exists() else dict(default_language='auto',files={});x.setdefault('files',{})[a.file]=dict(language=a.language);write(path,x)
 else:
  with single_instance(cfg['home']):
   path=Path(cfg['home'])/'dialogue_state.json';x=load(path);j=x['jobs'][a.job]
   if j['status']=='completed':raise ValueError('Completed jobs cannot be retried')
   j.update(attempts=0,retry_at=0);write(path,x)
if __name__=='__main__':main()
