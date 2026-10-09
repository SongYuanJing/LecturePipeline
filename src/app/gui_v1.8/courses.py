"""Small Course editor and Inbox projection; processing stays in the existing worker."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import course_setup as service
from lecture_inbox import Inbox


def explain(error):
    text=str(error)
    return ('Не удалось выполнить действие. Подробности в gui.log.' if 'Traceback' in text else text[:700])


class CourseEditor:
    MODES=('Существующая структура','Создать рекомендуемую','Вручную')
    def __init__(self,app,code=None):
        self.app=app;self.c=app.config();self.code=code;self.busy=False
        w=self.window=tk.Toplevel(app.root);w.title('Настройка курса');w.transient(app.root);w.grab_set()
        w.columnconfigure(0,weight=1);w.rowconfigure(0,weight=1)
        canvas=tk.Canvas(w,highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(w,command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
        body=ttk.Frame(canvas,padding=14);frame=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(frame,width=e.width));body.columnconfigure(1,weight=1)
        subject=self.c.subjects().get(code,{})
        binding=self.c.courses().get(code,{})
        self.name=tk.StringVar(value=subject.get('title',''));self.language=tk.StringVar(value=subject.get('default_language','zh'))
        self.enabled=tk.BooleanVar(value=binding.get('enabled',True));self.mode=tk.StringVar(value=self.MODES[2] if code else self.MODES[1]);self.root_path=tk.StringVar()
        self.paths={k:tk.StringVar(value=str(binding[k]) if binding.get(k) else '') for k in service.FIELDS}
        ttk.Label(body,text='Название курса').grid(row=0,column=0,sticky='w');ttk.Entry(body,textvariable=self.name).grid(row=0,column=1,columnspan=2,sticky='ew',pady=5)
        ttk.Label(body,text='Язык аудио').grid(row=1,column=0,sticky='w');ttk.Combobox(body,textvariable=self.language,values=('zh','en','auto'),state='readonly',width=10).grid(row=1,column=1,sticky='w')
        for i,mode in enumerate(self.MODES):ttk.Radiobutton(body,text=mode,variable=self.mode,value=mode).grid(row=2+i,column=0,columnspan=3,sticky='w',pady=3)
        ttk.Label(body,text='Папка курса').grid(row=5,column=0,sticky='w');ttk.Entry(body,textvariable=self.root_path).grid(row=5,column=1,sticky='ew')
        ttk.Button(body,text='Обзор…',command=lambda:self.browse(self.root_path)).grid(row=5,column=2,padx=5)
        ttk.Button(body,text='Показать / найти папки',command=self.propose).grid(row=6,column=1,sticky='w',pady=8)
        for i,key in enumerate(service.FIELDS,7):
            ttk.Label(body,text=service.LABELS[key]).grid(row=i,column=0,sticky='w',pady=5)
            ttk.Entry(body,textvariable=self.paths[key]).grid(row=i,column=1,sticky='ew',pady=5)
            ttk.Button(body,text='Обзор…',command=lambda k=key:self.browse(self.paths[k])).grid(row=i,column=2,padx=5)
        ttk.Checkbutton(body,text='Автоматически принимать аудио из Inbox',variable=self.enabled).grid(row=11,column=0,columnspan=3,sticky='w',pady=8)
        self.notice=tk.StringVar(value='Архив — только назначение на будущее. Исходные аудио не перемещаются.')
        ttk.Label(body,textvariable=self.notice,wraplength=600).grid(row=12,column=0,columnspan=3,sticky='ew')
        self.preview=tk.Text(body,height=6,wrap='word');self.preview.grid(row=13,column=0,columnspan=3,sticky='ew',pady=8)
        self.preview.configure(state='disabled')
        footer=ttk.Frame(w,padding=12);footer.grid(row=1,column=0,columnspan=2,sticky='ew')
        self.cancel=ttk.Button(footer,text='Отмена',command=w.destroy);self.cancel.pack(side='left')
        self.save_button=ttk.Button(footer,text='Использовать / сохранить',command=self.save);self.save_button.pack(side='right')
        w.protocol('WM_DELETE_WINDOW',lambda:None if self.busy else w.destroy())
        w.update_idletasks();scale=float(w.tk.call('tk','scaling'))*72/96
        width=min(round(860*scale),w.winfo_screenwidth()-40);height=min(round(720*scale),w.winfo_screenheight()-100)
        w.geometry(f'{width}x{height}');w.minsize(min(width,600),min(height,350))

    def browse(self,var):
        result=filedialog.askdirectory(parent=self.window,mustexist=False,title='Выберите папку')
        if result:var.set(result)

    def mapping(self):return {k:v.get().strip() or None for k,v in self.paths.items()}

    def propose(self):
        try:
            if self.mode.get()==self.MODES[1]:mapping=service.recommended(self.root_path.get());text='Будут созданы только отсутствующие папки:'
            elif self.mode.get()==self.MODES[0]:
                mapping=service.detect(self.root_path.get());text='Найдена структура. Проверьте пути и подтвердите использование.'
                if mapping is None:
                    self.mode.set(self.MODES[2]);self.notice.set('Структура неоднозначна или не распознана. Выберите папки вручную.');return
            else:mapping=self.mapping();text='Проверьте выбранные папки:'
            for key,value in mapping.items():self.paths[key].set(value or '')
            self.notice.set(text);self.preview.configure(state='normal');self.preview.delete('1.0','end')
            self.preview.insert('1.0','\n'.join(service.LABELS[k]+': '+str(v or 'не задано') for k,v in mapping.items()));self.preview.configure(state='disabled')
        except Exception as e:messagebox.showerror('Папки курса',explain(e),parent=self.window)

    def save(self):
        if self.busy or self.app.controls_busy:return
        mapping=self.mapping();create=self.mode.get()==self.MODES[1]
        if create and not any(mapping.values()):self.propose();mapping=self.mapping()
        preview='\n\n'.join(service.LABELS[k]+':\n'+str(v or 'не задано') for k,v in mapping.items())
        if not messagebox.askyesno('Создать папки и сохранить?' if create else 'Использовать эти папки?',preview+'\n\nWorkers будут безопасно остановлены и восстановлены. Существующие результаты не перемещаются.',parent=self.window):return
        self.busy=True;self.app.controls_busy=True;self.save_button.state(['disabled']);self.cancel.state(['disabled'])
        self.notice.set('Сохранение настроек и восстановление workers…')
        name=self.name.get();language=self.language.get();enabled=self.enabled.get()
        def done(result,error):
            self.busy=False;self.app.controls_busy=False
            if error:
                self.save_button.state(['!disabled']);self.cancel.state(['!disabled']);self.notice.set(explain(error));return
            self.window.destroy();self.app.refresh()
        self.app.submit(lambda:service.save_course(self.c,self.app.manager,name,mapping,course_id=self.code,enabled=enabled,create=create,language=language),done)


class CoursePanel:
    def __init__(self,app,parent):
        self.app=app;self.data=dict(courses=[],items=[])
        parent.columnconfigure(0,weight=1);parent.rowconfigure(2,weight=1);parent.rowconfigure(3,weight=1)
        bar=ttk.Frame(parent);bar.grid(row=0,column=0,sticky='ew')
        for text,fn in [('Добавить курс',lambda:CourseEditor(app)),('Настроить курс',self.edit),('Обновить',app.refresh),('Запустить / перезапустить worker',lambda:app.restart('lecture'))]:
            ttk.Button(bar,text=text,command=fn).pack(side='left',padx=3)
        self.notice=tk.StringVar(value='Состояние Inbox');ttk.Label(parent,textvariable=self.notice,wraplength=950).grid(row=1,column=0,sticky='ew',pady=6)
        self.courses=self.table(parent,('name','status','pending','last_scan','problems'),('Курс','Inbox','Ожидают','Последняя проверка','Проблемы'),3,2)
        self.courses.bind('<<TreeviewSelect>>',lambda e:self.fill_items())
        self.items=self.table(parent,('name','status_text','parts','error'),('Файл / группа','Состояние','Части','Причина'),4,3)
        self.items.bind('<<TreeviewSelect>>',lambda e:self.detail())
        self.details=tk.StringVar();ttk.Label(parent,textvariable=self.details,wraplength=950).grid(row=4,column=0,sticky='ew')
        bottom=self.footer=ttk.Frame(parent);bottom.grid(row=5,column=0,sticky='ew',pady=6)
        ttk.Button(bottom,text='Дата / ожидаемые части…',command=self.resolve).pack(side='left')
        ttk.Button(bottom,text='Проверить снова',command=self.retry).pack(side='left',padx=8)

    def table(self,parent,columns,labels,height,row):
        frame=ttk.Frame(parent);frame.grid(row=row,column=0,sticky='nsew')
        tree=ttk.Treeview(frame,columns=columns,show='headings',height=height,selectmode='browse')
        for key,label in zip(columns,labels):tree.heading(key,text=label);tree.column(key,width=160,minwidth=60)
        y=ttk.Scrollbar(frame,command=tree.yview);x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);y.pack(side='right',fill='y');x.pack(side='bottom',fill='x');tree.pack(fill='both',expand=True)
        return tree

    def render(self,data,worker=''):
        selected=self.courses.selection();self.data=data;self.courses.delete(*self.courses.get_children())
        for row in data['courses']:self.courses.insert('','end',iid=row['id'],values=[row[k] for k in self.courses['columns']])
        if selected and self.courses.exists(selected[0]):self.courses.selection_set(selected)
        elif data['courses']:self.courses.selection_set(data['courses'][0]['id'])
        self.notice.set('Worker: '+worker+'. Включённый Inbox принимает файлы, когда worker работает.');self.fill_items()

    def selected_item(self):
        selected=self.items.selection()
        if not selected:raise ValueError('Выберите файл или группу')
        return next(r for r in self.data['items'] if r['id']==selected[0])

    def fill_items(self):
        selected=self.courses.selection();prior=self.items.selection();self.items.delete(*self.items.get_children())
        if not selected:return
        for r in self.data['items']:
            if r['course_id']==selected[0]:self.items.insert('','end',iid=r['id'],values=(r['name'],r['status_text'],', '.join(str(x) for x in r['parts'] if x is not None),explain(r.get('error') or '')))
        if prior and self.items.exists(prior[0]):self.items.selection_set(prior)
        course=next(r for r in self.data['courses'] if r['id']==selected[0])
        self.details.set(explain(course.get('error') or ''));self.detail()

    def detail(self):
        try:r=self.selected_item()
        except ValueError:return
        parts=', '.join(str(x) for x in r['parts'] if x is not None) or 'без номера'
        self.details.set(f"{r['status_text']} · Найдены части: {parts} · Ожидаются: {r.get('expected_parts') or 'автоматически'}\n"+explain(r.get('error') or ''))

    def edit(self):
        selected=self.courses.selection()
        if selected:CourseEditor(self.app,selected[0])

    def retry(self):
        try:r=self.selected_item();self.app.control(lambda:Inbox(self.app.config()).review(r['id'],retry=True))
        except Exception as e:messagebox.showerror('Повторная проверка',explain(e),parent=self.app.root)

    def resolve(self):
        try:r=self.selected_item()
        except Exception as e:messagebox.showinfo('Проверка',str(e),parent=self.app.root);return
        fields=[('day','Дата YYYY-MM-DD',r.get('lecture_date') or '',None)]
        if r['kind']=='group':fields.append(('parts','Ожидаемые части (Auto или число)',str(r.get('expected_parts') or 'Auto'),None))
        def apply(values):
            parts=values.get('parts','Auto')
            try:count=0 if parts.lower()=='auto' else int(parts)
            except ValueError:raise ValueError('Введите Auto или целое число частей от 1 до 999')
            return Inbox(self.app.config()).review(r['id'],lecture_date=values['day'] or None,expected_parts=count if r['kind']=='group' else None,retry=True)
        w=tk.Toplevel(self.app.root);w.title('Дата и состав лекции');w.transient(self.app.root);w.grab_set();w.columnconfigure(1,weight=1)
        values={}
        for i,(key,label,default,_) in enumerate(fields):
            ttk.Label(w,text=label).grid(row=i,column=0,padx=12,pady=10,sticky='w')
            values[key]=tk.StringVar(value=default);ttk.Entry(w,textvariable=values[key],width=22).grid(row=i,column=1,padx=12,pady=10,sticky='ew')
        def save():
            data={k:v.get().strip() for k,v in values.items()};w.destroy();self.app.control(lambda:apply(data))
        ttk.Button(w,text='Отмена',command=w.destroy).grid(row=len(fields),column=0,padx=12,pady=12)
        ttk.Button(w,text='Сохранить',command=save).grid(row=len(fields),column=1,padx=12,pady=12,sticky='e')
        w.update_idletasks();w.minsize(min(w.winfo_reqwidth(),w.winfo_screenwidth()-50),w.winfo_reqheight())
