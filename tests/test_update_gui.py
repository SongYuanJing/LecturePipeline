import queue
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'installer'), str(REPO/'src/app/gui_v1.8')]
import update_gui
from updates import UpdateControls


class UpdateGuiTests(unittest.TestCase):
    def controls(self):
        panel = UpdateControls.__new__(UpdateControls)
        panel.app = Mock(controls_busy=False)
        panel.check_button = Mock(); panel.apply_button = Mock(); panel.status = Mock()
        panel.pending = False; panel.tag = None
        return panel

    def test_manual_check_disables_apply_and_queues_work(self):
        panel = self.controls(); panel.check()
        panel.status.set.assert_called_with('Проверка...')
        panel.app.submit.assert_called_once()
        panel.apply_button.configure.assert_called_with(state='disabled')
        panel.check(); self.assertEqual(panel.app.submit.call_count, 1)

    def test_no_update_and_available_messages(self):
        panel = self.controls()
        panel.checked(dict(status='no-update', current='1.9.7-beta.1'), None)
        panel.status.set.assert_called_with('Установлена последняя версия')
        self.assertIsNone(panel.tag)
        panel.checked(dict(status='available', current='1.9.7-beta.1', tag='v1.9.7-beta.2'), None)
        panel.apply_button.configure.assert_called_with(state='normal')
        self.assertEqual(panel.tag, 'v1.9.7-beta.2')

    def test_failed_handoff_keeps_gui_open(self):
        panel = self.controls(); panel.handed_off(None, 'failed')
        panel.app.close.assert_not_called()
        panel.handed_off(True, None); panel.app.close.assert_called_once()

    def test_parent_must_exit_before_engine(self):
        kernel = Mock(); kernel.WaitForSingleObject.return_value = 258
        events = queue.Queue()
        with patch.object(update_gui.updater, 'apply_tag') as apply:
            update_gui.perform_update(kernel, 1, 'v1.9.7-beta.2', events)
            apply.assert_not_called()
        self.assertEqual(events.get()[0], 'error')
        kernel.CloseHandle.assert_called_once_with(1)

    def test_engine_progress_success_and_failure_are_forwarded(self):
        for fail in (False, True):
            kernel = Mock(); kernel.WaitForSingleObject.return_value = 0
            events = queue.Queue()
            def apply(root, tag, progress):
                self.assertEqual(tag, 'v1.9.7-beta.2')
                progress('Downloading: app.zip')
                if fail: raise RuntimeError('bad hash; old pointer retained')
                return dict(status='updated')
            with patch.object(update_gui.updater, 'apply_tag', side_effect=apply):
                update_gui.perform_update(kernel, 1, 'v1.9.7-beta.2', events)
            rows = list(events.queue)
            self.assertIn(('progress', 'Загрузка: app.zip'), rows)
            self.assertEqual(rows[-1][0], 'error' if fail else 'success')
            kernel.CloseHandle.assert_called_once_with(1)

    def test_selected_tag_delegates_to_existing_engine(self):
        import updater
        release = dict(tag_name='v1.9.7-beta.2', draft=False)
        with patch('launch.app_root'), patch.object(updater, 'releases', return_value=[release]), \
             patch.object(updater, 'apply', return_value='ok') as apply:
            progress = Mock()
            self.assertEqual(updater.apply_tag(REPO, release['tag_name'], progress), 'ok')
            apply.assert_called_once_with(REPO, release, progress)


if __name__ == '__main__':
    unittest.main()
