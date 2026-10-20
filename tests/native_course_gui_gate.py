"""Disposable real Tk integration/visual fixture. No OS tasks or ASR model used.

GUI callbacks and real config/folder/READY/Word services run; scheduler controls,
runtime preflight and recognizer are explicit fixture substitutes. Confirmation
dialogs are captured/accepted by the integration harness, not hidden in product.
"""
import io
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
import wave
import tkinter as tk

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_course_setup import fixture,dump,APP,manager,FixtureControls,university
from pipeline_config import Config
import course_setup as service
from lecture_inbox import Inbox
import human_ux as ux
import adapter
import app as gui
from courses import CourseEditor
from test_local_finalize import lecture


def main():
    gate=Path(os.environ['TEMP'])/('LP-course-gui-'+time.strftime('%Y%m%d-%H%M%S'));gate.mkdir(exist_ok=False)
    c=fixture(gate);data=c.data;data['workspaces'][c.active]['subjects']=[];dump(c.path,data);c=Config(c.path)
    os.environ['LECTURE_CONFIG']=str(c.path);os.environ['LP_APP_VERSION']='VIC-21 disposable'
    dump(c.dialogue_home/'dialogue_state.json',dict(jobs={}))
    for name in ('00 — Входящие аудио','01 — Расшифровки','02 — Word','99 — Служебное'):(c.dialogue_root/name).mkdir(parents=True,exist_ok=True)
    dump(c.worker_home/'worker_status.json',{});dump(c.dialogue_home/'status.json',{})
    evidence=dict(gate='%TEMP%/'+gate.name,confirmation_previews=[],scope='Real Tk callbacks/config transaction/files/READY/raw/Word. Fixture scheduler + preflight + recognizer; no OS task or model access.')
    errors=[]
    def confirm(title,message,**kw):evidence['confirmation_previews'].append(dict(title=title,message=message.replace(str(gate),'%GATE%')));return True
    def showerror(title,message,**kw):errors.append(str(message));print('GUI ERROR:',message,flush=True)
    original=gui.configure_root
    def scaled(root):
        original(root);root.tk.call('tk','scaling',192/72)
        root.geometry(f'{min(2360,root.winfo_screenwidth()-60)}x{min(1600,root.winfo_screenheight()-120)}')
        return lambda value:round(value*2)
    patches=[patch.object(adapter,'Controls',FixtureControls),patch.object(adapter,'preflight',lambda c:dict(ok=True,checks=[])),
             patch.object(gui,'configure_root',scaled),patch('courses.messagebox.askyesno',side_effect=confirm),
             patch('courses.messagebox.showerror',side_effect=showerror)]
    for p in patches:p.start()
    gui.enable_system_dpi();root=tk.Tk();app=gui.App(root,c.path);app.manager=manager(c)
    def wait_until(predicate,seconds=20):
        deadline=time.monotonic()+seconds
        while not predicate():
            root.update();time.sleep(.03)
            if time.monotonic()>deadline:raise TimeoutError('GUI fixture timed out')
        root.update()
    wait_until(lambda:not app.busy)
    app.tabs.select(app.pages['Курсы / Inbox']);root.update()
    editor=CourseEditor(app);editor.mode.set(editor.MODES[1]);editor.name.set('中级微观经济学');editor.root_path.set(str(gate/'Drive Desktop 大学/微观'))
    editor.propose();root.update();mapping=editor.mapping()
    assert not Path(mapping['source_audio_folder']).exists()
    assert all(str(p) in editor.preview.get('1.0','end') for p in mapping.values())
    evidence['preview_before_creation']=True
    evidence['editor_footer_visible']=editor.save_button.winfo_rooty()+editor.save_button.winfo_height()<=editor.window.winfo_rooty()+editor.window.winfo_height()
    editor.save();wait_until(lambda:not editor.busy);assert not errors,errors
    c=Config(c.path);code=next(iter(c.subjects()));assert all(Path(p).is_dir() for p in mapping.values())
    evidence['created_course_id']=code;evidence['recommended_tree_created']=True
    app.closed=True
    for token in root.tk.call('after','info'):root.after_cancel(token)
    root.destroy()
    root=tk.Tk();app=gui.App(root,c.path);app.manager=manager(c);wait_until(lambda:not app.busy)
    app.tabs.select(app.pages['Курсы / Inbox']);root.update()
    assert next(iter(app.config().subjects()))==code
    assert app.config().courses()[code]['raw_output_folder']==Path(mapping['raw_output_folder'])
    evidence['gui_restart_identity_bindings_unchanged']=True
    # Minimum supported settling for a bounded native filesystem gate.
    data=c.data;data['workspaces'][c.active]['subjects'][0]['inbox'].update(settle_seconds=10,poll_seconds=5);dump(c.path,data);c=Config(c.path)
    source=Path(mapping['source_audio_folder']);payload=io.BytesIO()
    with wave.open(payload,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
    for name in ('微观2026_10_09_1.wav','微观2026_10_09_2.wav','Gap20261009_1.wav','Gap20261009_3.wav','Unknown.wav'):
        (source/name).write_bytes(payload.getvalue())
    originals={p.name:ux.sha(p) for p in source.iterdir()};inbox=Inbox(c)
    def scan():
        result=inbox.scan();app.course_panel.render(service.view(c),'Disposable: ручные циклы проверки');root.update();return result
    scan();assert any(r['status']=='waiting_parts' for r in service.view(c)['items'])
    start=time.monotonic()
    for _ in range(4):
        end=time.monotonic()+5
        while time.monotonic()<end:root.update();time.sleep(.05)
        result=scan()
    group=next(g for g in result['groups'] if g['status']=='queued');key=group['lecture_key']
    assert sum(g['status']=='queued' for g in result['groups'])==1
    assert any(r['status']=='review' and r['name']=='Unknown.wav' for r in service.view(c)['items'])
    assert any(r['status']=='review' and 'пропущены' in r.get('error','') for r in service.view(c)['items'])
    p=ux.pipeline(c);s=c.subjects()[code];parts=p.collect_lectures(s['audio_dir'])[key]
    from lecture_worker import Worker
    worker=Worker(c.worker_home,stable_seconds=0);worker.stable_ready(s,key,parts,set());assert worker.stable_ready(s,key,parts,set())[0]
    with patch.object(p,'transcribe_one',return_value=([(0,1,'测试内容')],SimpleNamespace(language='zh'))),patch.object(p,'safe_print'):
        p.process_lecture(object(),code,s,key,parts,p.load_state(c.state),c.state,gate/'pipeline.log')
    assert (Path(mapping['raw_output_folder'])/key/(key+'_manifest.json')).exists()
    import ai_finalize
    identity,content,_=lecture(c,'90_2026-10-08');final=ai_finalize.finalize(c,identity,content)
    assert Path(final['word']).is_relative_to(Path(mapping['final_output_folder']))
    before={p.name:[ux.sha(p),p.stat().st_mtime_ns] for p in s['audio_dir'].iterdir() if p.is_file()}
    Inbox(c).scan();assert before=={p.name:[ux.sha(p),p.stat().st_mtime_ns] for p in s['audio_dir'].iterdir() if p.is_file()}
    evidence.update(multipart_real_settle_seconds=time.monotonic()-start,one_group_queued=True,worker_accepts=True,
        raw_in_split_folder=True,word_in_split_folder=True,unknown_date_review=True,gap_reason_visible=True,restart_no_duplicate=True)
    # Existing structure through the same editor callbacks; read-only proposal.
    second=gate/'Existing structure 计量';expected=university(second)
    before={str(p):p.stat().st_mtime_ns for p in second.rglob('*')}
    editor=CourseEditor(app);editor.name.set('计量经济学');editor.mode.set(editor.MODES[0]);editor.root_path.set(str(second));editor.propose()
    assert editor.mapping()==expected;assert before=={str(p):p.stat().st_mtime_ns for p in second.rglob('*')}
    editor.save();wait_until(lambda:not editor.busy);assert not errors,errors
    c=Config(c.path);secondcode=next(k for k in c.subjects() if k!=code)
    # Manual edit preserves the stable identity and explicitly disables watching.
    editor=CourseEditor(app,secondcode);editor.mode.set(editor.MODES[2]);editor.name.set('计量 · renamed');editor.enabled.set(False)
    editor.save();wait_until(lambda:not editor.busy);assert not errors,errors
    c=Config(c.path);assert c.subjects()[secondcode]['title']=='计量 · renamed';assert not c.courses()[secondcode]['enabled']
    assert all(ux.sha(source/name)==sha for name,sha in originals.items())
    evidence.update(existing_structure_readonly_detection=True,existing_structure_confirmed=True,manual_editor_preserves_id=True,
        original_audio_unchanged=True,tk_dpi=root.winfo_fpixels('1i'),screen=[root.winfo_screenwidth(),root.winfo_screenheight()],
        scheduler='FixtureControls only; no Task Scheduler writes',visual='Pending external screenshot inspection')
    root.update();footer=app.course_panel.footer
    evidence['status_footer_visible']=footer.winfo_rooty()+footer.winfo_height()<=root.winfo_rooty()+root.winfo_height()
    assert evidence['status_footer_visible']
    dump(gate/'evidence.json',evidence);print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)
    print('VISUAL READY '+str(gate),flush=True)
    app.refresh();root.mainloop()


if __name__=='__main__':main()
