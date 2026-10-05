"""Explicit published GitHub gate: no HTTP, health, process or filesystem mocks.

Run --install NAME CACHE_SOURCE, then --update NAME after publishing B.
Only a new LP2a-remote-* directory directly under TEMP is writable.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_updater_gate import snapshot, window

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/'installer'))
import updater


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def close(pid):
    titles = window(pid, True)
    assert titles, 'Main GUI not found'
    for _ in range(100):
        if not window(pid):
            time.sleep(1)
            return titles
        time.sleep(.1)
    raise RuntimeError('GUI did not close')


def command(root, *args):
    result = subprocess.run([str(root/'runtime/asr/python.exe'), '-B', '-X', 'utf8',
        str(root/'launcher/updater.py'), *args], capture_output=True, encoding='utf8', timeout=180)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def run():
    action, name = sys.argv[1:3]
    assert action in ('--install', '--update')
    assert name.startswith('LP2a-remote-') and Path(name).name == name
    gate = Path(os.environ['TEMP']).resolve()/name
    root, data = gate/'Программа 课程', gate/'Данные 课程'
    evidence_file = gate/'evidence.json'
    if action == '--install':
        gate.mkdir(exist_ok=False)
        rows = updater.releases()
        release = next(r for r in rows if r['tag_name'] == 'v1.9.6-gate.1')
        assert not release['draft']
        item = updater.asset(release, 'Setup.exe')
        # The actual published Setup must be downloaded, not copied from the build.
        exe = updater.downloads.fetch(item['url'], item['sha256'], item['name'], gate/'release-download',
            expected_size=item['bytes'], limit=item['bytes'], progress=lambda m: print(m, flush=True))
        options = [str(exe), '--run', '--install', str(root), '--data', str(data),
            '--mode', 'auto', '--shortcut-directory', str(gate/'Ярлыки 课程')]
        cancelled = gate/'cancelled.json'
        result = subprocess.run([*options, '--cancel-after-ms', '1', '--report', str(cancelled)], timeout=90)
        assert result.returncode == 130 and json.loads(cancelled.read_text())['status'] == 'cancelled'
        # Only completed download artifacts, never installed runtime/model files.
        source = Path(sys.argv[3]).resolve()
        assert source.name == 'downloads' and source.is_dir()
        reused = []
        for path in sorted(source.rglob('*')):
            if path.is_file() and not path.name.startswith('.'):
                destination = root/'cache/downloads'/path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                reused.append(dict(name=path.name, bytes=path.stat().st_size))
        started = time.monotonic()
        result = subprocess.run([*options, '--report', str(gate/'setup.json')], timeout=1800)
        report = json.loads((gate/'setup.json').read_text(encoding='utf8'))
        assert result.returncode == 0 and report['status'] == 'ready', report
        titles = close(report['application_pid'])
        assert titles == ['Lecture Pipeline · 1.9.6-gate.1'], titles
        # Add a real disposable Word document alongside freshly initialized vocabulary/state.
        subprocess.run([str(root/'runtime/document/python.exe'), '-B', '-c',
            "from docx import Document;import sys;d=Document();d.add_paragraph('Published update gate');d.save(sys.argv[1])",
            str(data/'semester-1/SUBJECT/word/gate.docx')], check=True)
        evidence = dict(gate='%TEMP%/'+name, release_a=dict(id=release['id'], tag=release['tag_name']),
            setup_asset=item, setup_seconds=time.monotonic()-started, window_a=titles,
            reused_supplier_cache=reused, snapshot_before=snapshot(root,data),
            pointer_before=json.loads((root/'current.json').read_text()),
            initial_check=command(root, 'check'))
        save(evidence_file, evidence)
    else:
        evidence = json.loads(evidence_file.read_text(encoding='utf8'))
        assert snapshot(root,data) == evidence['snapshot_before']
        evidence['discovery'] = command(root, 'check')
        assert json.loads(evidence['discovery'])['tag'] == 'v1.9.6-gate.2'
        rows = updater.releases()
        release = next(r for r in rows if r['tag_name'] == 'v1.9.6-gate.2')
        evidence['release_b'] = dict(id=release['id'], tag=release['tag_name'],
            assets=[dict(name=a['name'], size=a['size'], digest=a['digest'], url=a['browser_download_url']) for a in release['assets']])
        assert not (root/'cache/updates').exists(), 'Expected a cold update cache'
        started = time.monotonic()
        evidence['update_output'] = command(root, 'apply', '--tag', release['tag_name'])
        evidence['update_seconds'] = time.monotonic()-started
        result = json.loads(evidence['update_output'].splitlines()[-1])
        assert result['status'] == 'updated'
        evidence['window_b'] = window(result['application_pid'])
        assert evidence['window_b'] == ['Lecture Pipeline · 1.9.6-gate.2']
        evidence['pointer_after'] = json.loads((root/'current.json').read_text())
        assert evidence['pointer_after']['app_version'] == '1.9.6-gate.2'
        evidence['snapshot_after'] = snapshot(root,data)
        assert evidence['snapshot_after'] == evidence['snapshot_before']
        evidence['old_version_retained'] = (root/'versions/1.9.6-gate.1/release.json').is_file()
        assert evidence['old_version_retained'] and not (root/'run/update-transaction.json').exists()
        cached = snapshot_cache(root/'cache/updates')
        evidence['final_check'] = command(root, 'check')
        assert json.loads(evidence['final_check'])['status'] == 'no-update'
        evidence['cache_unchanged_after_check'] = cached == snapshot_cache(root/'cache/updates')
        assert evidence['cache_unchanged_after_check']
        evidence['cache'] = cached
        close(result['application_pid'])
        save(evidence_file, evidence)
    print('Evidence:', evidence_file, flush=True)


def snapshot_cache(path):
    return {p.relative_to(path).as_posix(): dict(bytes=p.stat().st_size,
        sha256=updater.downloads.digest(p), mtime_ns=p.stat().st_mtime_ns)
        for p in sorted(path.rglob('*')) if p.is_file()}


if __name__ == '__main__':
    run()
