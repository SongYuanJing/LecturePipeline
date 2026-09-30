"""Real Tk geometry, no Computer Use, ASR, ingestion or production config."""
import sys,unittest,tkinter as tk
from tkinter import ttk,font
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'src/app'
sys.path[:0]=[str(APP),str(APP/'gui_v1.8')]
import actions
from dpi import enable_system_dpi

class AddLectureLayoutTests(unittest.TestCase):
 def test_required_controls_inside_dialog_at_scaled_initial_and_minimum_size(self):
  enable_system_dpi();root=tk.Tk();root.attributes('-alpha',0);root.update()
  try:
   for dpi in (96,144,192):
    root.tk.call('tk','scaling',dpi/72)
    font.nametofont('TkDefaultFont').configure(family='Segoe UI',size=11)
    style=ttk.Style(root);style.theme_use('clam');style.configure('.',font=('Segoe UI',11));style.configure('TButton',padding=(round(10*dpi/96),round(6*dpi/96)))
    config=SimpleNamespace(subjects=lambda:{'TEST':{'title':'Тестовый предмет'}})
    owner=SimpleNamespace(root=root,config=lambda:config,control=lambda fn:None)
    original=tk.Toplevel
    def invisible(*a,**kw):
     w=original(*a,**kw);w.attributes('-alpha',0);return w
    with patch.object(actions.tk,'Toplevel',side_effect=invisible),patch.object(actions.ux,'next_number',return_value=1):
     actions.Actions.add_lecture(owner)
    w=next(x for x in root.winfo_children() if isinstance(x,original));w.update()
    def descendants(parent):
     for child in parent.winfo_children():yield child;yield from descendants(child)
    widgets=list(descendants(w));buttons={x.cget('text'):x for x in widgets if x.winfo_class()=='TButton'}
    required=[buttons[t] for t in ('Выбрать аудио','Добавить в обработку','Отмена')]
    required += [x for x in widgets if x.winfo_class() in ('TEntry','TCombobox','Listbox')]
    self.assertEqual(len(required),7)
    for geometry in (w.geometry().split('+')[0],'%dx%d'%w.minsize()):
     w.geometry(geometry);w.update()
     for widget in required:
      x=widget.winfo_rootx()-w.winfo_rootx();y=widget.winfo_rooty()-w.winfo_rooty()
      self.assertTrue(widget.winfo_ismapped(),(dpi,widget))
      self.assertGreater(widget.winfo_height(),5)
      self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
      self.assertLessEqual(x+widget.winfo_width(),w.winfo_width(),(dpi,geometry,widget))
      self.assertLessEqual(y+widget.winfo_height(),w.winfo_height(),(dpi,geometry,widget))
    w.destroy()
  finally:root.destroy()

if __name__=='__main__':unittest.main()

