"""Real Tk widget/callback integration over disposable services, no OS automation."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_course_setup import fixture,manager,Config,cs,dump
from courses import CourseEditor,CoursePanel
from lecture_inbox import Inbox


class CourseGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.c=fixture(self.base)
        self.root=tk.Tk();self.root.tk.call('tk','scaling',192/72);self.root.geometry('1200x800');self.addCleanup(self.root.destroy)
        self.errors=[]
        def submit(fn,done):
            try:result=fn()
            except Exception as e:self.errors.append(str(e));done(None,str(e))
            else:done(result,None)
        self.app=SimpleNamespace(root=self.root,config=lambda:Config(self.c.path),manager=manager(self.c),
            controls_busy=False,submit=submit,refresh=lambda:None,restart=lambda k:None,control=lambda fn:fn())

    def test_preview_cancel_never_creates(self):
        editor=CourseEditor(self.app);editor.name.set('课程');editor.root_path.set(str(self.base/'课程 root'));editor.propose();self.root.update()
        self.assertIn('Lectures',editor.preview.get('1.0','end'))
        with patch('courses.messagebox.askyesno',return_value=False):editor.save()
        self.assertFalse((self.base/'课程 root').exists());self.assertFalse(self.app.controls_busy)
        self.assertLessEqual(editor.save_button.winfo_rooty()+editor.save_button.winfo_height(),editor.window.winfo_rooty()+editor.window.winfo_height())
        editor.window.destroy()

    def test_confirmed_editor_creates_without_user_code(self):
        editor=CourseEditor(self.app);editor.name.set('课程');editor.root_path.set(str(self.base/'课程 root'));editor.propose()
        with patch('courses.messagebox.askyesno',return_value=True):editor.save()
        self.assertFalse(self.errors,self.errors);c=Config(self.c.path)
        code=next(k for k in c.courses());self.assertTrue(code.startswith('course-'))
        self.assertTrue(c.courses()[code]['raw_output_folder'].is_dir())

    def prepare_panel(self,filename):
        mapping=cs.recommended(self.base/'大学');cs.save_course(self.c,manager(self.c),'课程',mapping,course_id='SUBJECT',create=True)
        data=Config(self.c.path).data;data['workspaces'][self.c.active]['subjects'][0]['inbox'].update(settle_seconds=10,poll_seconds=5);dump(self.c.path,data)
        self.c=Config(self.c.path);source=Path(mapping['source_audio_folder']);(source/filename).write_bytes(b'fixture')
        self.clock=0;self.inbox=Inbox(self.c,monotonic=lambda:self.clock)
        for _ in range(5):self.clock+=5;self.inbox.scan()
        frame=ttk.Frame(self.root);frame.pack(fill='both',expand=True);panel=CoursePanel(self.app,frame);panel.render(cs.view(self.c),'Тест')
        self.root.update();row=panel.data['items'][0];panel.items.selection_set(row['id']);panel.resolve();self.root.update()
        dialog=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        return panel,dialog,row

    def test_date_override_through_actual_review_widgets(self):
        panel,dialog,row=self.prepare_panel('Unknown.wav')
        self.assertEqual(row['status_text'],'Нужна проверка')
        entry=next(w for w in dialog.winfo_children() if isinstance(w,ttk.Entry));entry.insert(0,'2026-10-08')
        next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Сохранить').invoke()
        saved=Inbox(self.c).load()['sources'][row['id']]
        self.assertEqual((saved['lecture_date'],saved['lecture_date_source']),('2026-10-08','explicit'))

    def test_expected_parts_through_actual_review_widgets(self):
        panel,dialog,row=self.prepare_panel('Gap20261009_1.wav')
        # The lone part already queued after quiet; use an actual incomplete group instead.
        dialog.destroy();panel.items.delete(*panel.items.get_children())
        source=self.c.courses()['SUBJECT']['source_audio_folder']
        for n in (1,3):(source/f'Other20261009_{n}.wav').write_bytes(b'fixture')
        for _ in range(5):self.clock+=5;self.inbox.scan()
        panel.render(cs.view(self.c),'Тест');row=next(r for r in panel.data['items'] if r['status']=='review')
        panel.items.selection_set(row['id']);panel.resolve();self.root.update()
        dialog=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        entries=[w for w in dialog.winfo_children() if isinstance(w,ttk.Entry)]
        entries[1].delete(0,'end');entries[1].insert(0,'3')
        next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Сохранить').invoke()
        self.assertEqual(Inbox(self.c).load()['groups'][row['id']]['expected_parts'],3)


if __name__=='__main__':unittest.main()
