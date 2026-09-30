import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lecture_asr as a
import lecture_pipeline as p

def successful(profile=a.GPU_PROFILE):
    return dict(status='ok',profile=profile,info=dict(duration=10.,language='zh'),
                segments=[dict(start=0.,end=10.,text='完整中文句子')])

class ASRTests(unittest.TestCase):
    def test_no_model_substitution_or_network(self):
        for kw in [dict(model_size_or_path='medium'),dict(local_files_only=False)]:
            with self.assertRaises(ValueError):a.ProductionWhisperModel(**kw)

    def test_profile_defaults(self):
        m=a.ProductionWhisperModel()
        with patch.object(m,'_invoke',return_value=successful()) as call:
            rows,info=m.transcribe('test.wav',beam_size=1,vad_filter=False)
            self.assertEqual(next(rows).text,'完整中文句子')
            options=call.call_args.args[1]
            self.assertTrue(options['vad_filter']);self.assertEqual(options['beam_size'],5)
            self.assertEqual(options['vad_parameters'],a.VAD_PARAMETERS)
            self.assertFalse(options['condition_on_previous_text'])

    def test_cuda_failures_retry_cpu_once_and_stay_cpu(self):
        for message in ['CUDA failed','cudnn missing DLL','CUDA out of memory']:
            m=a.ProductionWhisperModel()
            with patch.object(m,'_invoke',side_effect=[a.BackendError(message,cuda=True),successful(a.CPU_PROFILE),successful(a.CPU_PROFILE)]) as call:
                rows,_=m.transcribe('same.wav',initial_prompt='prompt',hotwords='terms')
                self.assertEqual([s.text for s in rows],['完整中文句子'])
                m.transcribe('next.wav')
                self.assertEqual([c.args[2]['device'] for c in call.call_args_list],['cuda','cpu','cpu'])
                cpu=call.call_args_list[1]
                self.assertEqual(cpu.args[0],'same.wav')
                self.assertEqual(cpu.args[1]['initial_prompt'],'prompt')
                self.assertEqual(cpu.args[1]['hotwords'],'terms')
                self.assertFalse(cpu.args[1]['vad_filter']);self.assertNotIn('vad_parameters',cpu.args[1])
                self.assertTrue(cpu.args[1]['condition_on_previous_text'])
                self.assertTrue(call.call_args_list[2].args[1]['condition_on_previous_text'])

    def test_audio_or_model_errors_do_not_fallback(self):
        m=a.ProductionWhisperModel()
        with patch.object(m,'_invoke',side_effect=a.BackendError('Invalid audio')) as call:
            with self.assertRaises(a.BackendError):m.transcribe('broken.wav')
            self.assertEqual(call.call_count,1);self.assertFalse(m.cpu_only)
        for e in [ValueError('bad audio'),FileNotFoundError('model.bin'),RuntimeError('invalid model')]:
            self.assertFalse(a.cuda_error(e))

    def test_cpu_failure_propagates_no_retry_loop(self):
        m=a.ProductionWhisperModel()
        with patch.object(m,'_invoke',side_effect=[a.BackendError('CUDA OOM',cuda=True),a.BackendError('CPU failed')]) as call:
            with self.assertRaisesRegex(a.BackendError,'CPU failed'):m.transcribe('a.wav')
            self.assertEqual(call.call_count,2)

    def test_native_abort_classified_but_plain_script_error_not_hidden(self):
        class Child:
            def __init__(self,command,**kw):
                req=json.loads(Path(command[-2]).read_text(encoding='utf-8'))
                Path(req['progress']).write_text(json.dumps({'phase':'transcribe'}))
            def communicate(self,timeout=None):return ('native failure',None)
            def poll(self):return self.returncode
        for code,expected in [(0xc0000005,True),(1,False)]:
            Child.returncode=code
            with patch.object(a.subprocess,'Popen',Child):
                with self.assertRaises(a.BackendError) as ctx:
                    a.ProductionWhisperModel()._invoke('a.wav',{},a.GPU_PROFILE)
                self.assertEqual(ctx.exception.cuda,expected)

    def test_no_partial_result_on_nonzero_child_exit(self):
        class Child:
            returncode=1
            def __init__(self,command,**kw):
                Path(command[-1]).write_text(json.dumps(successful()))
            def communicate(self,timeout=None):return ('failure after partial output',None)
            def poll(self):return 1
        with patch.object(a.subprocess,'Popen',Child):
            with self.assertRaises(a.BackendError):
                a.ProductionWhisperModel()._invoke('a.wav',{},a.GPU_PROFILE)

    def test_cuda_exception_classifier(self):
        for e in [RuntimeError('CUDA failed'),RuntimeError('cuBLAS OOM'),ImportError('DLL load failed'),MemoryError()]:
            self.assertTrue(a.cuda_error(e))

    def test_setup_os_error_without_cuda_in_message_falls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for n in a.CUDA_DLLS:(root/n).touch()
            req=root/'request.json';result=root/'result.json'
            req.write_text(json.dumps(dict(profile=a.GPU_PROFILE,runtime_dir=str(root),
                           progress=str(root/'progress.json'),parent_pid=os.getpid())),encoding='utf-8')
            with patch.object(a,'_watch_parent'),patch.object(a.os,'add_dll_directory',side_effect=OSError('not a valid Win32 application')):
                self.assertEqual(a._child(req,result),1)
            self.assertTrue(json.loads(result.read_text())['cuda_error'])

    def test_cpu_explicit_has_no_vad_or_cuda_setup(self):
        m=a.ProductionWhisperModel(device='cpu',compute_type='int8')
        with patch.object(m,'_invoke',return_value=successful(a.CPU_PROFILE)) as call:
            m.transcribe('a.wav',vad_filter=True,vad_parameters={'threshold':0.9})
            self.assertEqual(call.call_args.args[2],a.CPU_PROFILE)
            self.assertNotIn('vad_parameters',call.call_args.args[1])
            self.assertTrue(call.call_args.args[1]['condition_on_previous_text'])

class TimestampTests(unittest.TestCase):
    def test_known_benchmark_tail_preserves_all_text(self):
        rows=[(284.56,289.56,'实际讲话'),(289.56,290.56,'嗯。'),(290.56,291.56,'还有重要一句。')]
        fixed=a.bounded_segments(rows,289.7266875)
        self.assertEqual(' '.join(r[2] for r in fixed),'实际讲话 嗯。 还有重要一句。')
        self.assertTrue(all(0<=s<e<=289.7266875 for s,e,t in fixed))
        self.assertEqual(p.fmt_ts(fixed[-1][1]),'00:04:49,726')

    def test_export_never_rounds_past_duration(self):
        for duration in [1.0001,1.0009,59.9999,289.7266875]:
            rows=a.bounded_segments([(0,duration+30,'speech')],duration)
            ms=round(rows[0][1]*1000)
            self.assertLessEqual(ms,math.floor(duration*1000))

    def test_all_late_and_negative_start_keep_text(self):
        self.assertEqual(a.bounded_segments([(20,25,'late')],10),[(0,10,'late')])
        self.assertEqual(a.bounded_segments([(-5,4,'first')],10),[(0,4,'first')])

    def test_invalid_values_fail_closed(self):
        for rows,d in [([(1,float('nan'),'x')],2),([(3,1,'x')],4),([(0,2,'x')],0)]:
            with self.assertRaises(ValueError):a.bounded_segments(rows,d)

    def test_in_bounds_content_unchanged(self):
        rows=[(0.,1.3,'您好'),(2.,3.4,'后面讲话')]
        self.assertEqual(a.bounded_segments(rows,10),rows)

if __name__=='__main__':unittest.main(verbosity=2)
