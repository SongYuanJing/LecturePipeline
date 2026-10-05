"""Disposable release contracts exercise real staging/pointer/cache; native GUI is a separate gate."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'installer'),str(REPO/'scripts')]
import updater as u
import update_state as state
import build_update


class Response(io.BytesIO):
    def __init__(self,data,url,offset=0,fail=False):
        super().__init__(data[offset:]);self.url=url;self.status=206 if offset else 200
        self.headers={'Content-Length':str(len(data)-offset),'ETag':'"fixture"'}
        if offset:self.headers['Content-Range']=f'bytes {offset}-{len(data)-1}/{len(data)}'
        self.fail=fail
    def geturl(self):return self.url
    def read(self,size):
        if self.fail and self.tell():raise TimeoutError('fixture disconnect')
        return super().read(min(size,32))


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'Программа 课程';self.root.mkdir()
        for name in u.RUNTIME_FILES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
        (self.root/'config').mkdir()
        (self.root/'config/config.json').write_text(json.dumps(dict(schema_version=1,
            application_home='..',install_root='../versions/1.0.0',data_root=str(self.base/'data'),
            workspaces={'one':{'worker_home':'run/workspaces/one'}},dialogue={'runtime':'run/dialogue'})))
        (self.base/'data').mkdir();(self.base/'data/lecture.docx').write_bytes(b'untouched user document')
        (self.root/'versions/1.0.0').mkdir(parents=True)
        state.atomic(self.root/'current.json',dict(app_version='1.0.0',path='versions/1.0.0'))
        self.previous=(self.root/'current.json').read_bytes()
        self.source=self.base/'source';(self.source/'gui_v1.8').mkdir(parents=True)
        (self.source/'pipeline_config.py').write_text('# fixture')
        (self.source/'gui_v1.8/app.py').write_text('# fixture')
        self.output=self.base/'release'
        self.manifest=build_update.build(self.source,self.root,self.output,'1.1.0')
        self.release=dict(tag_name='v1.1.0',draft=False,prerelease=False,assets=[])
        self.payload={}
        for path in self.output.iterdir():
            url='https://github.com/'+u.REPOSITORY+'/releases/download/v1.1.0/'+path.name
            self.payload[url]=path.read_bytes()
            self.release['assets'].append(dict(name=path.name,state='uploaded',size=path.stat().st_size,
                digest='sha256:'+u.downloads.digest(path),browser_download_url=url))
        self.before=self.snapshot()

    def snapshot(self):
        return {str(p):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in [self.root/'config/config.json',self.base/'data/lecture.docx']}

    def network(self,url,headers=None):
        offset=int((headers or {}).get('Range','bytes=0-')[6:-1])
        return Response(self.payload[url],url,offset)

    def apply(self,**kwargs):return u.apply(self.root,self.release,progress=lambda _:None,**kwargs)

    def replace_asset(self,name,data):
        item=next(a for a in self.release['assets'] if a['name']==name)
        item.update(size=len(data),digest='sha256:'+hashlib.sha256(data).hexdigest())
        self.payload[item['browser_download_url']]=data

    def test_missing_bad_or_incompatible_manifest_refused(self):
        original=json.loads(json.dumps(self.release))
        variants=[None,b'not json',json.dumps(dict(self.manifest,migration_required=True)).encode(),
                  json.dumps(dict(self.manifest,repository='someone/else')).encode()]
        for data in variants:
            self.release=json.loads(json.dumps(original))
            if data is None:self.release['assets']=[a for a in self.release['assets'] if a['name']!=u.MANIFEST]
            else:self.replace_asset(u.MANIFEST,data)
            with self.subTest(data=data),patch.object(u.downloads,'open_url',side_effect=self.network),patch.object(u,'health') as health:
                with self.assertRaises(ValueError):self.apply()
                health.assert_not_called()
            self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
            self.assertEqual(self.snapshot(),self.before)

    def test_invalid_zip_with_matching_outer_hash_refused(self):
        data=b'not a ZIP';name=self.manifest['artifact']['name']
        self.replace_asset(name,data)
        self.manifest['artifact'].update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.replace_asset(u.MANIFEST,json.dumps(self.manifest).encode())
        with patch.object(u.downloads,'open_url',side_effect=self.network):
            with self.assertRaises(zipfile.BadZipFile):self.apply()
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
        self.assertEqual(self.snapshot(),self.before)

    def test_discovery_no_update_newer_and_semver_channels(self):
        self.assertIsNone(u.discover('1.1.0',[self.release]))
        self.assertEqual(u.discover('1.0.0',[self.release]),self.release)
        beta=dict(self.release,tag_name='v2.0.0-beta.10',prerelease=True)
        self.assertIsNone(u.discover('1.1.0',[beta]))
        self.assertEqual(u.discover('2.0.0-beta.2',[beta]),beta)
        self.assertIsNone(u.discover('1.0.0',[dict(self.release,draft=True),dict(self.release,tag_name='main')]))

    def test_success_atomic_switch_and_data_unchanged_cache_reused(self):
        def trial(root,transaction):
            self.assertEqual(json.loads((root/'current.json').read_text()),transaction['next'])
            self.assertTrue(state.journal(root).exists());return 123
        with patch.object(u.downloads,'open_url',side_effect=self.network),patch.object(u,'health') as health,patch.object(u,'first_launch',side_effect=trial):
            result=self.apply();self.assertEqual(result['status'],'updated');health.assert_called_once()
        self.assertTrue((self.root/'versions/1.0.0').is_dir())
        self.assertEqual(self.snapshot(),self.before)
        self.assertFalse(state.journal(self.root).exists())
        with patch.object(u.downloads,'open_url') as net:
            self.assertEqual(self.apply()['status'],'no-update')
            u.manifest(self.root,self.release,lambda _:None)
            u.obtain(self.root,u.asset(self.release,self.manifest['artifact']['name']),lambda _:None)
            net.assert_not_called()

    def test_bad_hash_refused_before_health_or_switch(self):
        key=next(k for k in self.payload if k.endswith('.zip'));self.payload[key]=b'x'*len(self.payload[key])
        with patch.object(u.downloads,'open_url',side_effect=self.network),patch.object(u,'health') as health:
            with self.assertRaisesRegex(ValueError,'SHA256'):self.apply()
            health.assert_not_called()
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
        self.assertEqual(self.snapshot(),self.before)

    def test_broken_staged_health_leaves_current_unchanged(self):
        with patch.object(u.downloads,'open_url',side_effect=self.network),patch.object(u,'health',side_effect=RuntimeError('broken stage')):
            with self.assertRaisesRegex(RuntimeError,'broken stage'):self.apply()
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
        self.assertFalse((self.root/'versions/1.1.0').exists())

    def test_failed_first_launch_rolls_back_exact_pointer(self):
        with patch.object(u.downloads,'open_url',side_effect=self.network),patch.object(u,'health'),patch.object(u,'first_launch',side_effect=RuntimeError('bad GUI')):
            with self.assertRaisesRegex(RuntimeError,'bad GUI'):self.apply()
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
        self.assertTrue((self.root/'versions/1.1.0').exists())
        self.assertEqual(self.snapshot(),self.before)

    def test_interrupted_release_download_resumes(self):
        item=u.asset(self.release,self.manifest['artifact']['name']);data=self.payload[item['url']];calls=[]
        def network(url,headers=None):
            offset=int(headers.get('Range','bytes=0-')[6:-1]);calls.append(offset)
            return Response(data,url,offset,fail=len(calls)==1)
        with patch.object(u.downloads,'RESUME_THRESHOLD',1),patch.object(u.downloads,'open_url',side_effect=network),patch.object(u.downloads.time,'sleep'):
            result=u.obtain(self.root,item,lambda _:None)
        self.assertEqual(result.read_bytes(),data);self.assertEqual(calls,[0,32])

    def test_running_session_or_worker_refuses_switch(self):
        for lock in ('run/sessions/live.lock','run/workspaces/one/lecture_pipeline.lock'):
            with self.subTest(lock=lock),state.locked(self.root/lock),patch.object(u.downloads,'open_url') as net:
                with self.assertRaises(RuntimeError):self.apply()
                net.assert_not_called()
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)

    def test_crash_recovery_restores_pointer_without_config_write(self):
        import base64
        state.atomic(state.journal(self.root),dict(previous=base64.b64encode(self.previous).decode(),token='test'))
        state.atomic(self.root/'current.json',dict(app_version='1.1.0',path='versions/1.1.0'))
        with state.locked(self.root/'run/update.lock'):self.assertTrue(state.recover(self.root))
        self.assertEqual((self.root/'current.json').read_bytes(),self.previous)
        self.assertEqual(self.snapshot(),self.before)

    def test_recovery_also_refuses_active_direct_worker(self):
        import base64
        state.atomic(state.journal(self.root),dict(previous=base64.b64encode(self.previous).decode(),token='test'))
        state.atomic(self.root/'current.json',dict(app_version='1.1.0',path='versions/1.1.0'))
        pending=(self.root/'current.json').read_bytes()
        with state.locked(self.root/'run/workspaces/one/lecture_pipeline.lock'):
            with self.assertRaises(RuntimeError):state.recover(self.root)
        self.assertEqual((self.root/'current.json').read_bytes(),pending)

    def test_manifest_runtime_and_repository_binding(self):
        for edit in ('runtime','repository','url'):
            with self.subTest(edit=edit):
                release=json.loads(json.dumps(self.release))
                if edit=='url':release['assets'][0]['browser_download_url']='https://github.com/other/repo/releases/download/v1.1.0/file'
                elif edit=='runtime':(self.root/u.RUNTIME_FILES[0]).write_text('changed')
                else:
                    release['assets'][0]['digest']='sha256:'+'0'*64
                with patch.object(u.downloads,'open_url',side_effect=self.network):
                    with self.assertRaises(ValueError):u.manifest(self.root,release,lambda _:None)
                (self.root/u.RUNTIME_FILES[0]).write_text('{}')

    def test_archive_escape_rejected(self):
        archive=self.base/'escape.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../config/config.json',b'bad')
        with self.assertRaises(ValueError):u.stage(self.root,archive,'1.1.0')
        self.assertEqual(self.snapshot(),self.before)


if __name__=='__main__':unittest.main()
