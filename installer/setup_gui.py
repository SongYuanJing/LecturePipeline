"""Minimal first-run and component UI over the existing pinned importers."""
import json,queue,subprocess,threading,traceback,uuid
from pathlib import Path
from functools import partial
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog

class Async:
 def __init__(self,widget):self.widget=widget;self.events=queue.Queue();self.busy=False;widget.after(100,self.pump)
 def run(self,fn,done):
  if self.busy:raise ValueError('Дождитесь завершения операции')
  self.busy=True
  def work():
   try:self.events.put((done,fn(),None))
   except Exception as e:
    import logging
    logging.exception('Setup/component operation');self.events.put((done,None,str(e)))
  threading.Thread(target=work,daemon=True).start()
 def pump(self):
  while not self.events.empty():
   done,value,error=self.events.get();self.busy=False;done(value,error)
  if self.widget.winfo_exists():self.widget.after(100,self.pump)

def command(home,script,*args):
 r=subprocess.run([str(home/'runtime/asr/python.exe'),'-I','-B','-X','utf8',str(home/'launcher'/script),*map(str,args)],capture_output=True,text=True,encoding='utf8',creationflags=0x08000000)
 if r.returncode:
  (home/'logs').mkdir(exist_ok=True);(home/'logs/component-error.txt').write_text(r.stderr or r.stdout,encoding='utf8')
  raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1])
 return r.stdout

def integrate(home):
 r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(home/'launcher/Integrate.ps1'),'-Apply'],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=0x08000000)
 if r.returncode:raise RuntimeError(r.stderr.strip() or r.stdout.strip())
 return 'Интеграция готова'

class Components(ttk.Frame):
 def __init__(self,parent,home):
  super().__init__(parent,padding=10);self.home=Path(home);self.async_=Async(self);self.status=tk.StringVar(value='Проверка компонентов…')
  ttk.Label(self,textvariable=self.status,wraplength=690).pack(anchor='w')
  self.tree=ttk.Treeview(self,columns=('component','status'),show='headings',height=7)
  self.tree.heading('component',text='Компонент');self.tree.heading('status',text='Состояние');self.tree.column('component',width=210);self.tree.column('status',width=450);self.tree.pack(fill='x',pady=8)
  bar=ttk.Frame(self);bar.pack(fill='x')
  for label,script,folder in [('PyAV: выбрать файл','import_pyav.py',False),('CTranslate2: выбрать файл','import_ctranslate2.py',False),('Выбрать модель','import_model.py',True),('GPU-компонент','import_cuda.py',True)]:
   ttk.Button(bar,text=label,command=lambda s=script,f=folder:self.choose(s,f)).pack(side='left',padx=3)
  ttk.Button(self,text='Проверить компоненты',command=self.refresh).pack(anchor='w',pady=6)
  ttk.Label(self,text='Импортируются только проверенные версии. Модель: папка snapshot large-v3. CUDA необязателен для CPU. Драйвер и supplier terms не устанавливаются/не принимаются автоматически.',wraplength=690).pack(anchor='w')
  self.refresh()
 def refresh(self):
  if self.async_.busy:return
  self.status.set('Проверяем hashes и private runtime…')
  self.async_.run(lambda:json.loads(command(self.home,'component_status.py')),self.loaded)
 def loaded(self,value,error):
  if error:self.status.set(error);return
  self.tree.delete(*self.tree.get_children())
  labels={'Valid':'✓ Готово','Available':'✓ Готово','Missing':'○ Не установлено','Invalid':'⚠ Ошибка','Blocked':'○ Недоступно'}
  for name,item in value.items():self.tree.insert('','end',values=(name,labels[item['status']]+(' — '+item['reason'] if item['reason'] else '')))
  self.status.set('Проверка завершена')
 def choose(self,script,folder):
  if self.async_.busy:messagebox.showinfo('Подождите','Дождитесь проверки/импорта',parent=self);return
  if script=='import_cuda.py':
   # The native directory chooser can accept its displayed current folder
   # instead of an uncommitted typed address. Use an explicit, initially empty
   # source field for CUDA; never seed it from home or the model selection.
   path=simpledialog.askstring('Папка CUDA runtime','Вставьте полный путь к папке CUDA runtime (с cublas64_12.dll):',parent=self)
   if path is not None:
    path=path.strip()
    if path and not Path(path).is_absolute():
     messagebox.showerror('Папка CUDA runtime','Укажите полный абсолютный путь к папке',parent=self);return
  elif folder:
   # Explicit initialdir prevents the Windows/Tk chooser from reusing the last
   # component's selected folder. Each invocation owns its dialog and result.
   title='Выберите папку CUDA runtime' if script=='import_cuda.py' else 'Выберите папку модели large-v3'
   path=filedialog.Directory(parent=self,title=title,initialdir=str(self.home),mustexist=True).show()
  else:path=filedialog.askopenfilename(parent=self,title='Выберите точный supplier wheel',filetypes=[('Python wheel','*.whl')])
  if not path:return
  self.status.set('Проверка и импорт компонента…')
  def done(value,error):
   if error:messagebox.showerror('Компонент не принят',error,parent=self);self.status.set(error)
   else:self.status.set(value.strip());self.refresh()
  self.async_.run(partial(command,self.home,script,str(path)),done)

def first_run(home):
 home=Path(home);root=tk.Tk();root.title('Lecture Pipeline · Первый запуск');root.geometry('900x780');root.minsize(820,730);runner=Async(root);result=[]
 ttk.Label(root,text='Настройка Lecture Pipeline',font=('Segoe UI',18,'bold')).pack(anchor='w',padx=20,pady=15)
 form=ttk.Frame(root,padding=20);form.pack(fill='x');values={}
 for row,(key,label,default) in enumerate([('data','Папка данных (вне приложения)',''),('workspace','Название workspace','Semester 1'),('code','Код предмета','SUBJECT'),('name','Название предмета','Предмет')]):
  ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',pady=4);v=tk.StringVar(value=default);values[key]=v;ttk.Entry(form,textvariable=v,width=64).grid(row=row,column=1,sticky='ew',padx=8)
 def browse():
  p=filedialog.askdirectory(parent=root,title='Папка данных')
  if p:values['data'].set(p)
 ttk.Button(form,text='Выбрать…',command=browse).grid(row=0,column=2)
 language=tk.StringVar(value='zh');ttk.Label(form,text='Язык лекций').grid(row=4,column=0,sticky='w');ttk.Combobox(form,textvariable=language,values=('zh','en','auto'),state='readonly',width=12).grid(row=4,column=1,sticky='w',padx=8)
 panel=Components(root,home);panel.pack(fill='x',padx=10)
 tasks=tk.BooleanVar(value=True);ttk.Checkbutton(root,text='Создать отдельные tasks и запустить workers для этой установки',variable=tasks).pack(anchor='w',padx=20,pady=8)
 status=tk.StringVar();ttk.Label(root,textvariable=status,wraplength=850).pack(anchor='w',padx=20)
 def finish():
  if runner.busy or panel.async_.busy:messagebox.showinfo('Подождите','Дождитесь проверки компонентов',parent=root);return
  fields={k:v.get().strip() for k,v in values.items()};lang=language.get();with_tasks=tasks.get()
  if not all(fields.values()):messagebox.showerror('Настройка','Заполните все поля',parent=root);return
  status.set('Проверка и создание конфигурации…')
  def work():
   from setup import configure
   cfg=configure(home,Path(fields['data']),'semester-1',fields['code'],workspace_name=fields['workspace'],subject_name=fields['name'],language=lang)
   if with_tasks:
    integrate(home)
    import os,sys
    os.environ['LECTURE_CONFIG']=str(cfg)
    from launch import app_root
    app=app_root(home);sys.path[:0]=[str(app),str(app/'gui_v1.8')]
    from adapter import Controls,Config
    ctl=Controls(Config(cfg))
    for kind in ('lecture','dialogue'):ctl.action(kind,'Start')
   return str(cfg)
  def done(value,error):
   if error:
    (home/'logs').mkdir(exist_ok=True);(home/'logs/setup-error.txt').write_text(error,encoding='utf8');status.set(error);messagebox.showerror('Настройка не завершена',error,parent=root)
    if (home/'config/config.json').exists():result.append(True);root.destroy()
   else:result.append(True);root.destroy()
  runner.run(work,done)
 ttk.Button(root,text='Завершить настройку',command=finish).pack(anchor='e',padx=20,pady=12)
 def close():
  if runner.busy or panel.async_.busy:messagebox.showinfo('Подождите','Дождитесь завершения операции',parent=root)
  else:root.destroy()
 root.protocol('WM_DELETE_WINDOW',close);root.mainloop();return bool(result)

def show_components(parent,home):
 w=tk.Toplevel(parent);w.title('Компоненты Lecture Pipeline');w.geometry('850x430');panel=Components(w,home);panel.pack(fill='both',expand=True)
 w.protocol('WM_DELETE_WINDOW',lambda:messagebox.showinfo('Подождите','Выполняется проверка/импорт',parent=w) if panel.async_.busy else w.destroy())
