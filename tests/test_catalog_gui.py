"""Regression for the selection/detail flicker observed in the native VIC-13 gate."""
import copy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest
import test_lecture_catalog as fixtures
from catalog import CatalogPanel


class CatalogGuiTests(unittest.TestCase):
    setUp=fixtures.CatalogTests.setUp
    def test_unchanged_poll_preserves_detail_and_selection(self):
        fixtures.add(self.c,parts=8)
        root=tk.Tk();self.addCleanup(root.destroy);root.tk.call('tk','scaling',192/72)
        frame=ttk.Frame(root);frame.pack(fill='both',expand=True)
        panel=CatalogPanel(SimpleNamespace(root=root,refresh=lambda:None,add_lecture=lambda:None),frame)
        data=fixtures.catalog.build(self.c)
        data['pending']=[dict(id='pending',course_id='ECON',course_display_name='Эконометрика',name='Группа',lecture_date=None,parts=[1,3],reason='Не хватает части 2')]
        panel.render(data,self.c);root.update()
        panel.pending.selection_set('0');root.update()
        panel.table.selection_set('0');root.update();panel.select()
        panel.detail.yview_moveto(1);root.update()
        before=(panel.detail.get('1.0','end'),panel.detail.yview(),panel.table.selection())
        panel.render(copy.deepcopy(data),self.c);root.update()
        # Tk can settle wrapped-line geometry on the next idle update at 192 DPI.
        # At the bottom, the first fractional coordinate is not a stable pixel.
        self.assertEqual(panel.detail.get('1.0','end'),before[0])
        self.assertEqual(panel.table.selection(),before[2])
        self.assertAlmostEqual(before[1][1],1)
        self.assertAlmostEqual(panel.detail.yview()[1],1)
        self.assertIn('8.',before[0])

    def test_changing_progress_preserves_selection_and_scroll(self):
        fixtures.add(self.c,parts=8)
        root=tk.Tk();self.addCleanup(root.destroy)
        frame=ttk.Frame(root);frame.pack(fill='both',expand=True)
        panel=CatalogPanel(SimpleNamespace(root=root,refresh=lambda:None,add_lecture=lambda:None),frame)
        data=fixtures.catalog.build(self.c)
        panel.render(data,self.c);root.update()
        panel.table.selection_set('0');root.update();panel.detail.yview_moveto(1);root.update()
        before=(panel.table.selection(),panel.detail.yview(),panel.table.yview(),panel.table.xview())
        self.assertAlmostEqual(before[1][1],1)
        for n in range(10):
            changed=copy.deepcopy(data)
            changed['items'][0]['progress_view']=dict(compact=f'Распознавание · 3/8 · {n}%',details=f'ETA ASR: ~{n+10} мин')
            panel.render(changed,self.c);root.update()
            self.assertEqual(panel.table.selection(),before[0])
            # Progress text can change wrapping/line count. A reader at the
            # bottom must stay there, not retain an obsolete fractional offset.
            self.assertAlmostEqual(panel.detail.yview()[1],1)
            self.assertGreater(panel.detail.yview()[0],0)
            self.assertEqual((panel.table.yview(),panel.table.xview()),before[2:])
            self.assertIn('ETA ASR:',panel.detail.get('1.0','end'))
