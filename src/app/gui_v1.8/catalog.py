"""Lecture catalog widgets. Read-only actions; review stays in CoursePanel."""
import tkinter as tk
from tkinter import ttk,messagebox
from lecture_catalog import LABELS,filtered
import lecture_dates

STAGES={'available':'Есть','missing':'Нет','unknown':'Неизвестно','legacy':'Старая запись',
        'problem':'Проблема','merged':'Обновлён','batch_pending':'Ожидает обновления',
        'waiting_ai':'Ожидает AI','ai_result_ready':'Результат принят','building':'Word создаётся',
        'vocabulary_pending':'Ожидает словаря','completed':'Завершено','failed':'Ошибка'}


class CatalogPanel:
    def __init__(self,app,parent):
        self.app=app;self.data=dict(items=[],pending=[],errors=[]);self.rows={};self.pending_rows={};self.config=None;self.detail_owner="lecture"
        parent.columnconfigure(0,weight=1);parent.rowconfigure(2,weight=3);parent.rowconfigure(4,weight=2);parent.rowconfigure(6,weight=1)
        bar=ttk.Frame(parent);bar.grid(row=0,column=0,sticky='ew')
        self.course=tk.StringVar(value='Все курсы');self.status=tk.StringVar(value='Все состояния');self.order=tk.StringVar(value='Сначала новые')
        for variable,width in ((self.course,26),(self.status,26),(self.order,18)):
            box=ttk.Combobox(bar,textvariable=variable,state='readonly',width=width);box.pack(side='left',padx=(0,8));box.bind('<<ComboboxSelected>>',lambda e:self.fill())
            if variable is self.course:self.course_box=box
            elif variable is self.status:self.status_box=box
            else:box['values']=('Сначала новые','Сначала старые')
        self.status_box['values']=('Все состояния',*LABELS.values())
        tools=ttk.Frame(parent);tools.grid(row=1,column=0,sticky='ew',pady=5)
        ttk.Button(tools,text='Обновить список',command=app.refresh).pack(side='left')
        ttk.Button(tools,text='Добавить лекцию',command=app.add_lecture).pack(side='left',padx=6)
        self.notice=tk.StringVar();ttk.Label(tools,textvariable=self.notice).pack(side='left',padx=8)
        self.table=self.tree(parent,2,('course','key','date','status','progress','parts','raw','ai','word'),
                             ('Предмет','Лекция','Дата','Статус','Прогресс ASR','Частей','Raw','AI','Word'),(210,160,110,220,280,65,90,160,90),5)
        self.table.bind('<<TreeviewSelect>>',lambda e:self.select())
        actions=ttk.Frame(parent);actions.grid(row=3,column=0,sticky='ew',pady=4);self.buttons={}
        for label,key in [('Открыть Word','word'),('Папка результата','result'),('Открыть Raw','raw'),('Исходная папка','source')]:
            button=ttk.Button(actions,text=label,command=lambda k=key:self.open(k));button.pack(side='left',padx=(0,6));self.buttons[key]=button
        detail_frame=ttk.Frame(parent);detail_frame.grid(row=4,column=0,sticky='nsew')
        self.detail=tk.Text(detail_frame,height=5,wrap='word',state='disabled',font=('Segoe UI',11))
        scroll=ttk.Scrollbar(detail_frame,command=self.detail.yview);scroll.pack(side='right',fill='y');self.detail.configure(yscrollcommand=scroll.set);self.detail.pack(fill='both',expand=True)
        pending_bar=ttk.Frame(parent);pending_bar.grid(row=5,column=0,sticky='ew',pady=5)
        ttk.Label(pending_bar,text='Ожидают / требуют проверки · ещё не лекции').pack(side='left')
        ttk.Button(pending_bar,text='Открыть в Курсах / Inbox',command=self.review).pack(side='right')
        self.pending=self.tree(parent,6,('course','name','date','parts','reason'),('Предмет','Файл / группа','Дата','Части','Причина'),(190,230,110,100,430),3)
        self.pending.bind('<<TreeviewSelect>>',lambda e:self.select_pending())

    def tree(self,parent,row,columns,labels,widths,height):
        frame=ttk.Frame(parent);frame.grid(row=row,column=0,sticky='nsew');frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
        tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse',height=height)
        px=getattr(self.app,'px',lambda n:n)
        for key,label,width in zip(columns,labels,widths):tree.heading(key,text=label);tree.column(key,width=px(width),minwidth=px(width),stretch=False)
        y=ttk.Scrollbar(frame,command=tree.yview);x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);tree.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew')
        return tree

    def render(self,data,config):
        # Polling unchanged authorities must not replay both selection events or
        # reset a user's scrolled details while they read/open a lecture.
        if data==self.data and self.config is not None and self.config.path==config.path:
            self.config=config;return
        self.data=data;self.config=config
        self.courses={'Все курсы':None,**{r['course_display_name']+' ['+r['course_id']+']':r['course_id'] for r in data['items']+data['pending'] if r.get('course_id')}}
        self.course_box['values']=list(self.courses)
        if self.course.get() not in self.courses:self.course.set('Все курсы')
        self.fill(preserve=True)

    def fill(self,preserve=False):
        detail_scroll=self.detail.yview();owner=self.detail_owner
        old=self.table.selection();selected=self.rows.get(old[0],{}).get('id') if old else None
        status=next((k for k,v in LABELS.items() if v==self.status.get()),None);course=getattr(self,'courses',{}).get(self.course.get())
        rows=filtered(self.data['items'],course,status,self.order.get()=='Сначала новые')
        stable=[r['id'] for r in self.rows.values()]==[r['id'] for r in rows]
        if not stable:self.table.delete(*self.table.get_children())
        self.rows={}
        for i,r in enumerate(rows):
            iid=str(i);self.rows[iid]=r;s=r['stages']
            from lecture_progress import STAGES as LIVE_STAGES
            status_text=LIVE_STAGES[r['progress']['stage']] if r.get('progress') else r['status_text']
            values=(r['course_display_name'],r['lecture_key'],r['lecture_date'] or 'Не определена',status_text,r.get('progress_view',{}).get('compact') or '—',r['parts'],STAGES.get(s.get('raw'),'—'),STAGES.get(s.get('ai'),'—'),STAGES.get(s.get('word'),'—'))
            if stable:self.table.item(iid,values=values)
            else:self.table.insert('','end',iid=iid,values=values)
            if not stable and r['id']==selected:self.table.selection_set(iid)
        prior=self.pending.selection();pending_id=self.pending_rows.get(prior[0],{}).get('id') if prior else None
        pending_rows=[r for r in self.data['pending'] if not course or r['course_id']==course]
        pending_stable=list(self.pending_rows.values())==pending_rows
        if not pending_stable:self.pending.delete(*self.pending.get_children())
        self.pending_rows={}
        for r in pending_rows:
            iid=str(len(self.pending_rows));self.pending_rows[iid]=r
            if not pending_stable:self.pending.insert('','end',iid=iid,values=(r['course_display_name'],r['name'],r['lecture_date'] or 'Не определена',', '.join(str(n) for n in r['parts'] if n is not None),r['reason']))
            if not pending_stable and r['id']==pending_id:self.pending.selection_set(iid)
        self.notice.set(f"Лекций: {len(rows)} · Ожидают: {len(self.pending_rows)}"+(' · Ошибки чтения' if self.data['errors'] else ''))
        if preserve and owner=='pending':self.select_pending()
        else:self.select()
        if preserve:self.detail.yview_moveto(detail_scroll[0])

    def text(self,value):
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('1.0',value);self.detail.configure(state='disabled')

    def select(self):
        self.detail_owner="lecture"
        ids=self.table.selection();r=self.rows.get(ids[0]) if ids else None
        for key,button in self.buttons.items():button.state(['!disabled'] if r and r['paths'].get(key) else ['disabled'])
        if not r:self.text('\n'.join(self.data['errors']) or 'Выберите лекцию.');return
        names=dict(audio='Аудио',ready='Передача',raw='Расшифровка',ai='AI',word='Word',vocabulary='Словарь')
        stages=' · '.join(names[k]+': '+STAGES.get(v,v) for k,v in r['stages'].items())
        self.text(f"{r['course_display_name']} · {r['lecture_key']} · {r['status_text']}\n"+lecture_dates.describe(r)+
                  f"\nИмпорт: {r.get('imported_at') or 'неизвестно'} · Запись: {r.get('recorded_at') or 'неизвестно'}\n{stages}\n"+
                  r.get('progress_view',{}).get('details','')+'\n'+
                  '\n'.join(f"{i}. {m['name']}"+(f" — {m['path']}" if m.get('path') else '') for i,m in enumerate(r['members'],1))+
                  '\n'+'\n'.join(r['reasons']+r.get('recovery',[]))+'\n'+'\n'.join(k+': '+str(v) for k,v in r['paths'].items())+'\n'+r.get('integrity',''))

    def select_pending(self):
        self.detail_owner="pending"
        ids=self.pending.selection()
        if ids:
            r=self.pending_rows[ids[0]];self.text(r['name']+'\n'+lecture_dates.describe(r)+'\n'+r['reason'])

    def open(self,key):
        try:
            ids=self.table.selection()
            if not ids:raise ValueError('Выберите лекцию')
            from adapter import safe_open
            safe_open(self.config,self.rows[ids[0]]['paths'].get(key))
        except Exception as exc:messagebox.showerror('Не удалось открыть',str(exc),parent=self.app.root)

    def review(self):
        ids=self.pending.selection()
        if not ids:return
        r=self.pending_rows[ids[0]];panel=self.app.course_panel
        self.app.tabs.select(self.app.pages['Курсы / Inbox'])
        if panel.courses.exists(r['course_id']):
            panel.courses.selection_set(r['course_id']);panel.fill_items()
            if panel.items.exists(r['id']):panel.items.selection_set(r['id']);panel.items.see(r['id']);panel.detail()
