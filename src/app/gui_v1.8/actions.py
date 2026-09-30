"""Human actions; all processing is delegated to existing backend contracts."""
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import human_ux as ux

class Actions:
 def config(self):
  from pipeline_config import Config
  return Config(self.path)
 def components(self):
  from setup_gui import show_components
  show_components(self.root,self.config().home)
 def integration(self):
  def run():
   from setup_gui import integrate
   from adapter import Controls
   c=self.config();integrate(c.home);ctl=Controls(c)
   for kind in ('lecture','dialogue'):ctl.action(kind,'Start')
   return 'Интеграция готова. Workers запущены.'
  self.control(run)
 def form(self,title,fields,callback):
  w=tk.Toplevel(self.root);w.title(title);w.geometry('650x320');w.transient(self.root);w.grab_set();values={}
  for row,(key,label,default,choices) in enumerate(fields):
   ttk.Label(w,text=label).grid(row=row,column=0,padx=12,pady=10,sticky='w');v=tk.StringVar(value=default);values[key]=v
   control=ttk.Combobox(w,textvariable=v,values=choices,state='readonly',width=42) if choices else ttk.Entry(w,textvariable=v,width=44)
   control.grid(row=row,column=1,padx=12,pady=10)
  def finish():
   data={k:v.get().strip() for k,v in values.items()};w.destroy();self.control(lambda:callback(data))
  ttk.Button(w,text='Сохранить',command=finish).grid(row=len(fields),column=1,pady=12,sticky='e')
 def new_workspace(self):self.form('Новый workspace',[('name','Название','',None)],lambda v:ux.add_workspace(self.config(),v['name'],self.manager))
 def subject_editor(self,new=False):
  c=self.config();subjects=c.subjects()
  if new:code='';name='';language='zh'
  else:
   code=self.subject_edit.get().split(' · ',1)[0]
   if code not in subjects:messagebox.showerror('Предмет','Выберите предмет',parent=self.root);return
   name=subjects[code]['title'];language=subjects[code]['default_language']
  self.form('Добавить предмет' if new else 'Изменить предмет', [('code','Код',code,None if new else (code,)),('name','Название',name,None),('language','Язык',language,('zh','en','auto'))],lambda v:ux.edit_subject(self.config(),v['code'],v['name'],v['language'],self.manager,new))
 def subject_folder(self):
  try:
   from adapter import safe_open
   c=self.config();code=self.subject_edit.get().split(' · ',1)[0];safe_open(c,c.subjects()[code]['subject_dir'])
  except Exception as e:messagebox.showerror('Папка предмета',str(e),parent=self.root)
 def add_lecture(self):
  c=self.config();subjects=c.subjects()
  if not subjects:messagebox.showinfo('Добавить лекцию','Сначала добавьте предмет во вкладке Workspace',parent=self.root);return
  w=tk.Toplevel(self.root);w.title('Добавить лекцию');w.transient(self.root)
  w.columnconfigure(0,weight=1);w.rowconfigure(3,weight=1)
  choices={k+' · '+s['title']:k for k,s in subjects.items()};subject=tk.StringVar(value=next(iter(choices)));day=tk.StringVar(value=date.today().isoformat());number=tk.StringVar()
  form=ttk.Frame(w,padding=14);form.grid(row=0,column=0,sticky='ew');form.columnconfigure(1,weight=1)
  for row,(label,var) in enumerate([('Предмет',subject),('Дата YYYY-MM-DD',day),('Номер лекции',number)]):
   ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',pady=5)
   entry=ttk.Combobox(form,textvariable=var,values=list(choices),state='readonly',width=50) if row==0 else ttk.Entry(form,textvariable=var,width=24)
   entry.grid(row=row,column=1,sticky='ew',padx=12)
   if row==0:entry.bind('<<ComboboxSelected>>',lambda e:number.set(str(ux.next_number(c,choices[subject.get()]))))
  number.set(str(ux.next_number(c,choices[subject.get()])))
  ttk.Label(w,text='Порядок частей: сверху вниз. Исходные файлы сохраняются.').grid(row=1,column=0,sticky='w',padx=14)
  parts=ttk.Frame(w);parts.grid(row=3,column=0,sticky='nsew',padx=14,pady=8)
  lb=tk.Listbox(parts,height=6);scroll=ttk.Scrollbar(parts,command=lb.yview);lb.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');lb.pack(fill='both',expand=True);files=[]
  def choose():
   selected=filedialog.askopenfilenames(parent=w,title='Аудио лекции',filetypes=[('Аудио','*.m4a *.mp3 *.wav *.aac *.flac *.mp4 *.ogg *.opus *.mov')])
   for p in selected:
    if p not in files:files.append(p);lb.insert('end',p)
  def move(step):
   if not lb.curselection():return
   i=lb.curselection()[0];j=i+step
   if 0<=j<len(files):files[i],files[j]=files[j],files[i];lb.delete(0,'end');[lb.insert('end',p) for p in files];lb.selection_set(j)
  def remove():
   if lb.curselection():i=lb.curselection()[0];files.pop(i);lb.delete(i)
  bar=ttk.Frame(w,padding=14);bar.grid(row=2,column=0,sticky='ew')
  for label,fn in [('Выбрать аудио',choose),('↑',lambda:move(-1)),('↓',lambda:move(1)),('Убрать',remove)]:ttk.Button(bar,text=label,command=fn).pack(side='left',padx=3)
  def finish():
   try:n=int(number.get());d=day.get();date.fromisoformat(d);code=choices[subject.get()];selected=list(files)
   except ValueError:messagebox.showerror('Лекция','Проверьте номер и дату',parent=w);return
   if not selected:messagebox.showerror('Лекция','Выберите аудиофайлы',parent=w);return
   w.destroy();self.control(lambda:'Лекция добавлена: '+ux.add_lecture(c,code,d,n,selected)+'. Worker начнёт обработку автоматически.')
  footer=ttk.Frame(w,padding=14);footer.grid(row=4,column=0,sticky='ew')
  ttk.Button(footer,text='Отмена',command=w.destroy).pack(side='left')
  ttk.Button(footer,text='Добавить в обработку',command=finish).pack(side='right')
  w.bind('<Escape>',lambda e:w.destroy())
  # Reserve form/toolbars/footer; only the parts list absorbs resizing.
  w.update_idletasks()
  scale=float(w.tk.call('tk','scaling'))*72/96
  margin=round(60*scale);limit_w=w.winfo_screenwidth()-margin;limit_h=w.winfo_screenheight()-margin
  requested_w=w.winfo_reqwidth();requested_h=w.winfo_reqheight()
  minimum_w=min(requested_w,limit_w);minimum_h=min(requested_h-lb.winfo_reqheight()+round(70*scale),limit_h)
  w.minsize(minimum_w,minimum_h)
  width=min(max(requested_w,round(760*scale)),limit_w);height=min(max(requested_h,round(520*scale)),limit_h)
  w.geometry(f'{width}x{height}');w.grab_set()
 def ai_action(self,export=False):
  try:
   row=self.chosen('AI очередь');c=self.config();identity=c.active+'/'+row['id']
   path=filedialog.asksaveasfilename(parent=self.root,title='Пакет для ChatGPT',initialfile=row['name']+'-AI.zip',defaultextension='.zip',filetypes=[('ZIP','*.zip')]) if export else filedialog.askopenfilename(parent=self.root,title='Импортировать ai_content.json',filetypes=[('AI result','*.json')])
   if not path:return
   self.control(lambda:('Пакет для обычного ChatGPT: '+ux.export_packet(c,identity,path)) if export else ux.import_result(c,identity,path))
  except Exception as e:messagebox.showerror('AI результат',str(e),parent=self.root)

