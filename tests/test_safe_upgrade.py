"""The full-package upgrade must leave beta.4 recoverable and user data intact."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installer'))
import safe_upgrade


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value, encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SafeUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'app'
        self.data = self.home / 'data'
        self.data.mkdir()
        put(self.data / 'dictionary/vocabulary.xlsx', 'user dictionary')
        put(self.data / 'course/raw/lecture.srt', 'raw source')
        put(self.root / 'versions/2.0.0-beta.4/release.json',
            dict(app_version='2.0.0-beta.4', updater_protocol=1, config_schema_version=1,
                 migration_required=False))
        put(self.root / 'current.json', dict(app_version='2.0.0-beta.4',
                                             path='versions/2.0.0-beta.4'))
        put(self.root / 'launcher/launch.py', 'old launcher')
        put(self.root / 'Lecture Pipeline.vbs', 'old Tk shortcut')
        put(self.root / 'bootstrap-state.json', dict(status='ready', bundle='old', data=str(self.data)))
        put(self.root / 'config/config.json', dict(schema_version=1, data_root=str(self.data),
            application_home='..', workspaces={'semester-1': {'worker_home':'run/workspaces/semester-1'}},
            dialogue={'runtime':'run/dialogue'}))
        old_files = {p.relative_to(self.root).as_posix(): sha(p)
                     for p in self.root.rglob('*') if p.is_file()}
        put(self.root / 'package-manifest.json', dict(manifest_schema_version=1,
            app_version='2.0.0-beta.4', files=old_files))
        self.stage = self.root / '.upgrade-stage' / 'test'
        put(self.stage / 'versions/2.0.0-beta.5-dev.5/release.json',
            dict(app_version='2.0.0-beta.5-dev.5', updater_protocol=1,
                 distribution_status='dev', config_schema_version=1, migration_required=False))
        put(self.stage / 'launcher/launch.py', 'new launcher')
        put(self.stage / 'current.json', dict(app_version='2.0.0-beta.5-dev.5',
                                             path='versions/2.0.0-beta.5-dev.5'))
        put(self.stage / 'Lecture Pipeline.vbs', 'new dashboard shortcut')
        put(self.stage / 'Lecture Pipeline (Tk).vbs', 'new Tk fallback')
        self.payload = dict(app_version='2.0.0-beta.5-dev.5',
            files={p.relative_to(self.stage).as_posix():sha(p)
                   for p in self.stage.rglob('*') if p.is_file()})
        self.before_data = {p.relative_to(self.data).as_posix():sha(p)
                            for p in self.data.rglob('*') if p.is_file()}
        self.before_config = (self.root / 'config/config.json').read_bytes()

    def product_stage(self, distribution_status='beta'):
        version = '2.0.0-beta.5'
        old = self.stage / 'versions/2.0.0-beta.5-dev.5'
        new = self.stage / 'versions' / version
        old.rename(new)
        release = json.loads((new / 'release.json').read_text(encoding='utf8'))
        release.update(app_version=version, distribution_status=distribution_status)
        put(new / 'release.json', release)
        put(self.stage / 'current.json', dict(app_version=version, path='versions/' + version))
        self.payload = dict(app_version=version,
            files={p.relative_to(self.stage).as_posix():sha(p)
                   for p in self.stage.rglob('*') if p.is_file()})

    def test_product_beta5_upgrade_preserves_beta4_and_data(self):
        self.product_stage()
        result = safe_upgrade.apply(self.root, self.stage, self.payload,
                                    health=lambda _root, _code: None)
        self.assertEqual(result['current'], '2.0.0-beta.5')
        self.assertEqual((self.root / 'config/config.json').read_bytes(), self.before_config)
        self.assertEqual({p.relative_to(self.data).as_posix():sha(p)
                          for p in self.data.rglob('*') if p.is_file()}, self.before_data)

    def test_product_version_rejects_dev_distribution_metadata(self):
        self.product_stage(distribution_status='dev')
        before = (self.root / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'distribution'):
            safe_upgrade.apply(self.root, self.stage, self.payload,
                               health=lambda _root, _code: None)
        self.assertEqual((self.root / 'current.json').read_bytes(), before)

    def test_success_keeps_data_config_and_old_version(self):
        result = safe_upgrade.apply(self.root, self.stage, self.payload,
                                    health=lambda _root, _code: None)
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(json.loads((self.root / 'current.json').read_text())['app_version'],
                         '2.0.0-beta.5-dev.5')
        self.assertEqual((self.root / 'launcher/launch.py').read_text(), 'new launcher')
        self.assertTrue((self.root / 'versions/2.0.0-beta.4/release.json').is_file())
        self.assertEqual((self.root / 'config/config.json').read_bytes(), self.before_config)
        self.assertEqual({p.relative_to(self.data).as_posix():sha(p)
                          for p in self.data.rglob('*') if p.is_file()}, self.before_data)
        self.assertEqual(json.loads((self.root / 'bootstrap-state.json').read_text())['status'], 'ready')

    def test_failure_after_launcher_swap_restores_beta4_bytes(self):
        original = {name:(self.root / name).read_bytes() for name in
                    ('current.json','package-manifest.json','bootstrap-state.json','Lecture Pipeline.vbs')}
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            safe_upgrade.apply(self.root, self.stage, self.payload,
                               health=lambda _root, _code: None, fail_at='launcher')
        self.assertEqual((self.root / 'launcher/launch.py').read_text(), 'old launcher')
        for name, content in original.items():
            self.assertEqual((self.root / name).read_bytes(), content, name)
        self.assertFalse((self.root / 'run/safe-upgrade.json').exists())
        self.assertEqual({p.relative_to(self.data).as_posix():sha(p)
                          for p in self.data.rglob('*') if p.is_file()}, self.before_data)

    def test_crash_journal_recovers_before_retry(self):
        with self.assertRaises(KeyboardInterrupt):
            safe_upgrade.apply(self.root, self.stage, self.payload,
                               health=lambda _root, _code: None, fail_at='crash_after_pointer')
        self.assertTrue((self.root / 'run/safe-upgrade.json').exists())
        self.assertNotEqual((self.root / 'launcher/launch.py').read_text(), 'old launcher')
        self.assertTrue(safe_upgrade.recover(self.root))
        self.assertEqual((self.root / 'launcher/launch.py').read_text(), 'old launcher')
        self.assertEqual(json.loads((self.root / 'current.json').read_text())['app_version'],
                         '2.0.0-beta.4')
        self.assertFalse((self.root / 'run/safe-upgrade.json').exists())

    def test_explicit_rollback_after_health_restores_beta4(self):
        result = safe_upgrade.apply(self.root, self.stage, self.payload,
                                    health=lambda _root, _code: None)
        self.assertTrue(safe_upgrade.rollback(self.root, Path(result['backup'])))
        self.assertEqual((self.root / 'launcher/launch.py').read_text(), 'old launcher')
        self.assertEqual(json.loads((self.root / 'current.json').read_text())['app_version'],
                         '2.0.0-beta.4')
        self.assertEqual({p.relative_to(self.data).as_posix():sha(p)
                          for p in self.data.rglob('*') if p.is_file()}, self.before_data)

    def test_retry_after_rollback_reuses_identical_version_without_deleting_it(self):
        staged_files = {name:(self.stage / name).read_bytes() for name in self.payload['files']}
        result = safe_upgrade.apply(self.root, self.stage, self.payload,
                                    health=lambda _root, _code: None)
        self.assertTrue(safe_upgrade.rollback(self.root, Path(result['backup'])))
        self.assertTrue((self.root / 'versions/2.0.0-beta.5-dev.5/release.json').is_file())
        for name, content in staged_files.items():
            path = self.stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        retry = safe_upgrade.apply(self.root, self.stage, self.payload,
                                   health=lambda _root, _code: None)
        self.assertEqual(retry['current'], '2.0.0-beta.5-dev.5')
        self.assertEqual((self.root / 'launcher/launch.py').read_text(), 'new launcher')

    def test_retry_rejects_existing_version_with_different_bytes(self):
        put(self.root / 'versions/2.0.0-beta.5-dev.5/release.json', 'foreign version')
        with self.assertRaisesRegex(ValueError, 'differs'):
            safe_upgrade.apply(self.root, self.stage, self.payload,
                               health=lambda _root, _code: None)
        self.assertEqual(json.loads((self.root / 'current.json').read_text())['app_version'],
                         '2.0.0-beta.4')

    def test_rejects_mismatched_payload_before_mutation(self):
        self.payload['files']['launcher/launch.py'] = '0' * 64
        before = (self.root / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            safe_upgrade.apply(self.root, self.stage, self.payload,
                               health=lambda _root, _code: None)
        self.assertEqual((self.root / 'current.json').read_bytes(), before)
        self.assertFalse((self.root / 'run/safe-upgrade.json').exists())


if __name__ == '__main__':
    unittest.main()
