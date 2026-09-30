"""Lecture Pipeline 1.8 — native control panel. Closing the window never stops workers."""
from __future__ import annotations
import argparse,json,logging,os,queue,sys,threading,traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox

# Locate production modules through the explicit config, without importing ASR workers.
def bootstrap(path):
 data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
 root=Path(data['install_root']);root=root if root.is_absolute() else Path(path).resolve().parent/root
 sys.path.insert(0,str(root.resolve()))

from actions import Actions
from dpi import enable_system_dpi,configure_root

class App(Actions):
 def __init__(self,root,config,log_dir=None):
  self.root=root;self.path=Path(config).resolve();self.events=queue.Queue();self.busy=False;self.closed=False;self.view=None;self.preflight=None;self.controls_busy=False
  self.root.title('Lecture Pipeline · '+os.environ.get('LP_APP_VERSION','1.8'));self.px=configure_root(root)
  self.root.configure(bg='#eef2f7');self.root.protocol('WM_DELETE_WINDOW',self.close)
  style=ttk.Style(root);style.theme_use('clam')
  style.configure('.',font=('Segoe UI',11));style.configure('TFrame',background='#eef2f7');style.configure('TLabel',background='#eef2f7',foreground='#18273f')
  style.configure('TNotebook',background='#eef2f7',borderwidth=0);style.configure('TNotebook.Tab',padding=(self.px(18),self.px(10)));style.map('TNotebook.Tab',background=[('selected','#ffffff')])
  style.configure('Treeview',rowheight=self.px(34),background='white',fieldbackground='white',borderwidth=0);style.configure('Treeview.Heading',font=('Segoe UI',11,'bold'),padding=self.px(7))
  style.configure('TButton',padding=(self.px(12),self.px(7)));style.configure('Title.TLabel',font=('Segoe UI',20,'bold'))
  header=tk.Frame(root,bg='#172c49');header.pack(fill='x')
  tk.Label(header,text='LECTURE PIPELINE',bg='#172c49',fg='white',font=('Segoe UI',19,'bold'),padx=24,pady=14).pack(side='left')
  tk.Label(header,text=os.environ.get('LP_APP_VERSION','1.8')+'  /  Панель управления',bg='#172c49',fg='#b7cce8',font=('Segoe UI',11)).pack(side='right',padx=24)
  self.banner=tk.StringVar(value='Загрузка конфигурации…');ttk.Label(root,textvariable=self.banner,wraplength=self.px(1150),padding=(22,10)).pack(fill='x')
  self.tabs=ttk.Notebook(root);self.tabs.pack(fill='both',expand=True,padx=18,pady=(0,10))
  self.pages={}
  for name in ('Главная','Лекции','Dialogue','AI очередь','Workspace','Система'):
   f=ttk.Frame(self.tabs,padding=18);self.tabs.add(f,text=name);self.pages[name]=f
  self.status=tk.StringVar(value='Закрытие окна не останавливает workers. ChatGPT — внешний ручной этап.')
  ttk.Label(root,textvariable=self.status,padding=(22,8)).pack(fill='x')
  self.show_tests=tk.BooleanVar(value=False);self.tables={};self.rows={};self.details={};self.ai_filter=False
  self.build_home();self.build_records('Лекции',[('subject','Предмет',240),('name','Лекция',180),('date','Дата',110),('status','ASR / worker',120),('ai','AI статус',165)])
  self.build_records('Dialogue',[('name','Запись',330),('status','Этап',160),('language','Язык',75),('duration','Аудио',100),('timing','ASR',100)])
  self.build_ai();self.build_workspace();self.build_system()
  try:
   bootstrap(self.path)
   global adapter
   import adapter
   c=adapter.Config(self.path);logs=Path(log_dir) if log_dir else c.local('logs/gui');logs.mkdir(parents=True,exist_ok=True)
   logging.basicConfig(filename=logs/'gui.log',level=logging.INFO,encoding='utf8',format='%(asctime)s %(levelname)s %(message)s')
   self.manager=adapter.Manager(self.path)
   self.refresh(full=True)
  except Exception as e:self.banner.set('Ошибка конфигурации: '+str(e));self.system.insert('1.0',traceback.format_exc())
  self.root.after(100,self.pump);self.root.after(3000,self.poll)
 def text_box(self,parent,height=8):
  frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=8)
  text=tk.Text(frame,height=height,wrap='word',font=('Segoe UI',11),bg='white',fg='#18273f',relief='flat',padx=14,pady=12)
  scroll=ttk.Scrollbar(frame,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(side='left',fill='both',expand=True)
  text.bind('<Key>',lambda e:'break' if not (e.state&4 and e.keysym.lower() in ('c','a')) else None)
  return text
 def set_text(self,widget,value):widget.delete('1.0','end');widget.insert('1.0',value)
 def build_home(self):
  f=self.pages['Главная'];ttk.Label(f,text='Система и текущая работа',style='Title.TLabel').pack(anchor='w')
  self.overview=tk.StringVar(value='Чтение статусов…');ttk.Label(f,textvariable=self.overview,font=('Segoe UI',12),wraplength=self.px(1080),justify='left').pack(anchor='w',pady=18)
  ttk.Label(f,text='Текущая задача',font=('Segoe UI',12,'bold')).pack(anchor='w');self.current=self.text_box(f,7)
  self.progress=ttk.Progressbar(f,maximum=100);self.progress.pack(fill='x',pady=5)
  ttk.Button(f,text='Обновить и проверить систему',command=lambda:self.refresh(True)).pack(anchor='w',pady=8)
 def build_records(self,name,columns):
  f=self.pages[name];top=ttk.Frame(f);top.pack(fill='x')
  ttk.Label(top,text='Последние лекции' if name=='Лекции' else 'Разговоры · Quick mode',style='Title.TLabel').pack(side='left')
  if name=='Лекции':ttk.Checkbutton(top,text='Показывать исторический тест',variable=self.show_tests,command=self.refresh).pack(side='right')
  else:
   self.dialogue_head=tk.StringVar(value='');ttk.Label(f,textvariable=self.dialogue_head).pack(anchor='w',pady=8)
  self.make_table(f,name,columns)
  bar=ttk.Frame(f);bar.pack(fill='x',pady=6)
  for title,key in [('Открыть Word','word'),('Папка','folder'),('TXT','txt'),('SRT','srt')]:ttk.Button(bar,text=title,command=lambda n=name,k=key:self.open_record(n,k)).pack(side='left',padx=(0,8))
  if name=='Лекции':ttk.Button(bar,text='Добавить лекцию',command=self.add_lecture).pack(side='right')
  self.details[name]=self.text_box(f,5)
 def make_table(self,parent,name,columns):
  frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=12)
  tree=ttk.Treeview(frame,columns=[x[0] for x in columns],show='headings',selectmode='browse',height=8)
  for key,label,width in columns:tree.heading(key,text=label);tree.column(key,width=self.px(width),minwidth=self.px(70),stretch=True)
  scroll=ttk.Scrollbar(frame,command=tree.yview);tree.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');tree.pack(fill='both',expand=True)
  tree.bind('<<TreeviewSelect>>',lambda e,n=name:self.selected(n));self.tables[name]=tree
 def build_ai(self):
  f=self.pages['AI очередь'];ttk.Label(f,text='Внешний AI-этап',style='Title.TLabel').pack(anchor='w')
  ttk.Label(f,text='ChatGPT обрабатывает локальный пакет вручную. История чата не является состоянием pipeline.').pack(anchor='w',pady=8)
  bar=ttk.Frame(f);bar.pack(fill='x');self.subject=tk.StringVar(value='Все предметы');self.subject_box=ttk.Combobox(bar,textvariable=self.subject,state='readonly',width=36);self.subject_box.pack(side='left',padx=(0,8))
  self.day=tk.StringVar();ttk.Entry(bar,textvariable=self.day,width=14).pack(side='left');ttk.Label(bar,text=' дата YYYY-MM-DD (необязательно)').pack(side='left')
  ttk.Button(bar,text='Найти waiting_ai',command=self.select_ai).pack(side='right')
  ttk.Button(bar,text='Все статусы',command=self.clear_ai).pack(side='right',padx=8)
  self.make_table(f,'AI очередь',[('subject','Предмет',270),('name','Лекция',230),('ai','AI статус',190)])
  bar=ttk.Frame(f);bar.pack(fill='x')
  ttk.Button(bar,text='Подготовить для ChatGPT',command=lambda:self.ai_action(True)).pack(side='left',padx=4)
  ttk.Button(bar,text='Импортировать результат AI',command=self.ai_action).pack(side='left',padx=4)
  ttk.Button(f,text='Диагностика: открыть пакет',command=lambda:self.open_record('AI очередь','packet')).pack(anchor='w')
  self.details['AI очередь']=self.text_box(f,5)
 def build_workspace(self):
  f=self.pages['Workspace'];ttk.Label(f,text='Рабочее пространство',style='Title.TLabel').pack(anchor='w')
  self.ws_info=tk.StringVar();ttk.Label(f,textvariable=self.ws_info,wraplength=self.px(1050)).pack(anchor='w',pady=20)
  self.workspace=tk.StringVar();self.workspace_box=ttk.Combobox(f,textvariable=self.workspace,state='readonly',width=70);self.workspace_box.pack(anchor='w',pady=12)
  ttk.Label(f,text='Переключение: проверка → остановка workers → config → preflight → восстановление запуска.\nЗанятая задача должна закончиться. При ошибке выполняется откат.\nСоздание и изменение предметов используют тот же безопасный механизм.',wraplength=self.px(1000)).pack(anchor='w',pady=20)
  self.switch_button=ttk.Button(f,text='Переключить workspace',command=self.switch);self.switch_button.pack(anchor='w')
  self.recover_button=ttk.Button(f,text='Восстановить незавершённое переключение',command=lambda:self.control(self.manager.recover));self.recover_button.pack(anchor='w',pady=12)
  ttk.Button(f,text='Создать workspace',command=self.new_workspace).pack(anchor='w',pady=4)
  self.subject_edit=tk.StringVar();self.subject_edit_box=ttk.Combobox(f,textvariable=self.subject_edit,state='readonly',width=60);self.subject_edit_box.pack(anchor='w',pady=12)
  bar=ttk.Frame(f);bar.pack(fill='x')
  for label,fn in [('Добавить предмет',lambda:self.subject_editor(True)),('Изменить предмет',self.subject_editor),('Папка предмета',self.subject_folder)]:ttk.Button(bar,text=label,command=fn).pack(side='left',padx=4)
 def build_system(self):
  f=self.pages['Система'];ttk.Label(f,text='Диагностика',style='Title.TLabel').pack(anchor='w');bar=ttk.Frame(f);bar.pack(fill='x',pady=12)
  for title,fn in [('Повторить preflight',lambda:self.refresh(True)),('Restart Lecture',lambda:self.restart('lecture')),('Restart Dialogue',lambda:self.restart('dialogue')),('Открыть логи',self.open_logs)]:ttk.Button(bar,text=title,command=fn).pack(side='left',padx=(0,8))
  bar=ttk.Frame(f);bar.pack(fill='x')
  ttk.Button(bar,text='Компоненты',command=self.components).pack(side='left',padx=4)
  ttk.Button(bar,text='Интеграция / запуск workers',command=self.integration).pack(side='left',padx=4)
  self.system=self.text_box(f,18)
 def submit(self,fn,callback):
  def run():
   try:self.events.put((callback,fn(),None))
   except Exception as e:logging.exception('GUI operation');self.events.put((callback,None,str(e)))
  threading.Thread(target=run,daemon=True).start()
 def pump(self):
  while not self.events.empty():
   cb,result,error=self.events.get()
   try:cb(result,error)
   except Exception:logging.exception('Render error');self.banner.set('Ошибка отображения; подробности в gui.log')
  if not self.closed:self.root.after(100,self.pump)
 def poll(self):
  if not self.closed:self.refresh();self.root.after(3000,self.poll)
 def refresh(self,full=False):
  if self.busy or self.controls_busy or not hasattr(self,'manager'):return
  self.busy=True;show=self.show_tests.get();self.status.set('Обновление…')
  def load():
   v=adapter.snapshot(self.path,show);p=adapter.preflight(v['config']) if full else None
   try:
    v['scheduled_tasks']=adapter.Controls(v['config']).states()
    for kind in ('lecture','dialogue'):
     if not v['scheduled_tasks'][kind]['running']:v[kind+'_worker']='Остановлен (Task Scheduler)'
   except Exception as e:v['scheduled_tasks_error']=str(e)
   return v,p,self.manager.pending()
  self.submit(load,self.loaded)
 def loaded(self,result,error):
  self.busy=False
  if self.controls_busy:return
  if error:self.banner.set('Данные недоступны: '+error);self.status.set('Показаны последние успешно прочитанные данные; они могут быть устаревшими.');return
  v,p,pending=result;self.view=v;c=v['config']
  if p is not None:self.preflight=p
  self.banner.set(('Незавершённое переключение — используйте восстановление. ' if pending else '')+(' | '.join(v['errors']) if v['errors'] else 'Данные обновлены · '+c.workspace['name']))
  pf='не выполнен' if not self.preflight else ('OK' if self.preflight['ok'] else 'ОШИБКА')
  counts={s:sum(r['ai']==s for r in v['lectures']) for s in ('waiting_ai','ai_result_ready','building','vocabulary_pending','completed','failed')}
  self.overview.set(f"Workspace: {c.workspace['name']}\nLecture: {v['lecture_worker']}     Dialogue: {v['dialogue_worker']}\nМодель: {c.data['asr']['model']} · {adapter.backend_text(self.preflight,c.data['asr']['preferred_device'])}\nPreflight: {pf}\nДанные: {c.data_root}\nAI: "+' · '.join(f'{s}: {n}' for s,n in counts.items() if n)+f"\nИсторических тестов скрыто: {v['hidden']}")
  self.set_text(self.current,v['current']);self.progress.stop();self.progress.configure(mode='determinate',value=0)
  if v.get('progress') is not None:self.progress.configure(value=v['progress']*100)
  elif v.get('asr_active'):self.progress.configure(mode='indeterminate');self.progress.start(70)
  self.dialogue_head.set('Worker: '+v['dialogue_worker']+' · Обычный drop использует '+c.data['languages']['dialogue'])
  self.fill('Лекции',v['lectures']);self.fill('Dialogue',v['dialogues']);self.fill('AI очередь',[r for r in v['lectures'] if r['ai']!='—'])
  self.subject_map={'Все предметы':None,**{k+' · '+s['title']:k for k,s in c.subjects().items()}};self.subject_box['values']=list(self.subject_map)
  if self.subject.get() not in self.subject_map:self.subject.set('Все предметы')
  if self.ai_filter:self.select_ai()
  self.ws_map={w['name']+' ['+k+']':k for k,w in c.data['workspaces'].items()};self.workspace_box['values']=list(self.ws_map)
  if self.workspace.get() not in self.ws_map:self.workspace.set(next(k for k,v in self.ws_map.items() if v==c.active))
  self.subject_edit_box['values']=[k+' · '+s['title'] for k,s in c.subjects().items()]
  if self.subject_edit.get() not in self.subject_edit_box['values']:self.subject_edit.set(next(iter(self.subject_edit_box['values']),''))
  self.ws_info.set('Активно: '+c.workspace['name']+'\n'+str(c.workspace_root))
  self.switch_button.state(['disabled'] if pending or len(self.ws_map)<2 else ['!disabled']);self.recover_button.state(['!disabled'] if pending else ['disabled'])
  checks='\n'.join(f"[{x['status']}] {x['id']}: {x['message']}" for x in (self.preflight or {}).get('checks',[]))
  task_errors=[r['name']+': '+r.get('detail','') for r in v['lectures']+v['dialogues'] if r.get('status','').lower() in ('failed','error') or r.get('ai')=='failed']
  self.set_text(self.system,f"Install: {c.install}\nData: {c.data_root}\nМодель: {c.data['asr']['model']}\nLecture: {v['lecture_worker']}\nDialogue: {v['dialogue_worker']}\nLecture state: {c.state}\nAI state: {c.ai_state}\nDialogue state: {c.dialogue_home/'dialogue_state.json'}\nAI queue: {c.queue_home/'queue.json'}\n\n{checks}\n\nОшибки чтения:\n"+('\n'.join(v['errors']) or 'Нет')+'\nTask Scheduler: '+str(v.get('scheduled_tasks_error') or v.get('scheduled_tasks'))+'\nПоследние ошибки задач:\n'+('\n'.join(task_errors[:5]) or 'Нет'))
  self.status.set('Закрытие GUI не останавливает workers. Автообновление: 3 с. Preflight — при запуске и по кнопке.')
 def fill(self,name,rows):
  tree=self.tables[name];selected=tree.selection();old_id=self.rows.get(name,{}).get(selected[0],{}).get('id') if selected else None
  tree.delete(*tree.get_children());self.rows[name]={}
  for i,row in enumerate(rows):
   iid=str(i);self.rows[name][iid]=row;tree.insert('','end',iid=iid,values=[('ТЕСТ · ' if row.get('test') and k=='name' else '')+(visual_status(row.get(k,'—')) if k in ('status','ai') else str(row.get(k,'—'))) for k in tree['columns']])
   if row['id']==old_id:tree.selection_set(iid)
 def chosen(self,name):
  ids=self.tables[name].selection()
  if not ids:raise ValueError('Выберите запись в списке')
  return self.rows[name][ids[0]]
 def selected(self,name):
  try:r=self.chosen(name)
  except ValueError:return
  self.set_text(self.details[name],r.get('detail','')+'\n'+r.get('eta','')+'\n'+r.get('part','')+'\n'+'\n'.join(k+': '+str(r[k]) for k in ('word','txt','srt','packet') if r.get(k)))
 def open_record(self,name,key):
  try:
   r=self.chosen(name);value=r.get(key)
   if isinstance(value,list):
    if not value:raise ValueError('SRT для записи отсутствует')
    if len(value)>1:self.choose_path(value);return
    value=value[0]
   adapter.safe_open(self.view['config'],value)
  except Exception as e:messagebox.showerror('Не удалось открыть',str(e),parent=self.root)
 def choose_path(self,paths):
  w=tk.Toplevel(self.root);w.title('Выберите часть');w.geometry('600x340');lb=tk.Listbox(w,font=('Segoe UI',11));lb.pack(fill='both',expand=True,padx=12,pady=12)
  for p in paths:lb.insert('end',Path(p).name)
  def go():
   try:
    if not lb.curselection():raise ValueError('Выберите файл')
    adapter.safe_open(self.view['config'],paths[lb.curselection()[0]])
   except Exception as e:messagebox.showerror('Не удалось открыть',str(e),parent=w)
  ttk.Button(w,text='Открыть',command=go).pack(pady=8)
 def open_logs(self):
  if self.view:self.choose_path([str(self.view['config'].worker_home/'worker.log'),str(self.view['config'].dialogue_home/'worker.log'),str(self.view['config'].local('logs/gui')/'gui.log')])
 def select_ai(self):
  if not self.view:return
  try:
   day=self.day.get().strip()
   if day:
    from datetime import date
    date.fromisoformat(day)
   v=self.view;q=dict(v['queue']);q['tasks']={k:t for k,t in q['tasks'].items() if self.show_tests.get() or k not in v['config'].data.get('hidden_tasks',adapter.TEST_TASKS)}
   result=adapter.select(q,v['config'].active,self.subject_map[self.subject.get()],day or None);ids={t['subject_code']+'/'+t['lecture_key'] for t in result['candidates']}
   self.ai_filter=True
   self.fill('AI очередь',[r for r in v['lectures'] if r['id'] in ids])
   self.set_text(self.details['AI очередь'],{'unique':'Найдена одна задача. Выберите её и откройте AI пакет.','not_found':'Подходящих задач нет. Задачи другого предмета не подставляются.','ambiguous':'Найдено несколько задач. Выберите нужную запись; автоматического выбора нет.'}[result['status']])
  except Exception as e:messagebox.showerror('Поиск AI',str(e),parent=self.root)
 def clear_ai(self):
  self.ai_filter=False
  if self.view:self.fill('AI очередь',[r for r in self.view['lectures'] if r['ai']!='—'])
 def switch(self):
  target=self.ws_map.get(self.workspace.get())
  if target and messagebox.askyesno('Переключение workspace','Остановить workers, проверить и переключить workspace? При ошибке config будет восстановлен.',parent=self.root):self.control(lambda:self.manager.switch(target))
 def restart(self,kind):
  if messagebox.askyesno('Restart worker','Дождаться завершения текущей задачи и перезапустить '+kind+' worker?',parent=self.root):self.control(lambda:self.manager.restart(kind))
 def control(self,fn):
  if self.controls_busy:return
  self.controls_busy=True;self.status.set('Операция выполняется… Не закрывайте окно до завершения.')
  self.submit(fn,self.control_done)
 def control_done(self,result,error):
  self.controls_busy=False
  if error:messagebox.showerror('Операция не завершена',error,parent=self.root)
  else:
   text=result or 'Готово'
   if isinstance(result,dict):
    d=result.get('dictionary',{});text='✓ Готово\n'+str(result.get('word',''))+'\nСловарь: +'+str(d.get('added',0))+' / обновлено '+str(d.get('updated',0))
   messagebox.showinfo('Готово',text,parent=self.root)
  self.preflight=None;self.refresh(True)
 def close(self):
  if self.controls_busy:messagebox.showinfo('Операция выполняется','Дождитесь окончания переключения/перезапуска. Это защищает конфигурацию.',parent=self.root);return
  self.closed=True;self.root.destroy()

def visual_status(value):
 return {'DONE':'✓ TXT/SRT готовы','completed':'✓ Готово','waiting_ai':'○ Ожидает AI','ai_result_ready':'● AI принят','building':'● Сборка Word','vocabulary_pending':'● Словарь','failed':'⚠ Ошибка','FAILED':'⚠ Ошибка','TRANSCRIBING':'● Распознавание','VERIFYING':'● Проверка файлов','PUBLISHING':'● Публикация','waiting':'○ Ожидает'}.get(value,str(value))

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=Path(__file__).resolve().parent.parent/'config.json');p.add_argument('--log-dir',type=Path);a=p.parse_args()
 enable_system_dpi()
 root=tk.Tk();app=App(root,a.config,a.log_dir);root.mainloop()
if __name__=='__main__':main()
