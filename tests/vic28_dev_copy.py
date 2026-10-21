"""Prepare small disposable Raw/SRT copies. No audio, production paths, ledger claims or workers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
TREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TREE / 'src/gui_web'))
from readonly_snapshot import SnapshotProvider, contained
from visual_fixture import dump


def fingerprint(folder):
    return {p.name: dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size=p.stat().st_size,
                         mtime_ns=p.stat().st_mtime_ns) for p in folder.iterdir() if p.is_file()
            and (p.suffix in {'.txt', '.srt'} or p.name.endswith('_manifest.json'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared-dev-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, default=TREE / '.local/vic28-dev-copy')
    args = parser.parse_args()
    shared, source, destination = args.shared_dev_root.resolve(strict=True), args.source.resolve(strict=True), args.destination.resolve()
    if not contained(source, shared / 'scratch'):
        raise ValueError('Read only an existing DEV scratch copy, never the original Production/Drive source')
    if not contained(destination, TREE / '.local') or destination == TREE / '.local':
        raise ValueError('Destination must be inside the UI worktree .local directory')
    marker = destination / 'VIC28_DEV_COPY.json'
    if destination.exists() and any(destination.iterdir()) and not marker.is_file():
        raise ValueError('Refuse to overwrite an unowned directory')
    manifests = list(source.glob('*_manifest.json'))
    if len(manifests) != 1:
        raise ValueError('Select one small Raw folder containing exactly one manifest')
    before = fingerprint(source)
    if sum(v['size'] for v in before.values()) > 16 * 1024 * 1024:
        raise ValueError('This gate accepts only small Raw/SRT metadata copies, max 16 MiB')
    manifest = json.loads(manifests[0].read_text(encoding='utf-8-sig'))
    code, key = manifest['subject_code'], manifest['lecture']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', code) or not re.fullmatch(r'\d{2,3}_\d{4}-\d{2}-\d{2}', key):
        raise ValueError('Invalid identity')
    raw = destination / 'data/dev-copy' / code / 'raw' / key
    raw.mkdir(parents=True, exist_ok=True)
    rewrites = []

    def normalize(value, field='$'):
        if isinstance(value, dict): return {k: normalize(v, field + '.' + k) for k, v in value.items()}
        if isinstance(value, list): return [normalize(v, field + '[' + str(i) + ']') for i, v in enumerate(value)]
        if isinstance(value, str) and (re.match(r'^[A-Za-z]:[\\/]', value) or value.startswith('\\\\')):
            # Historical lineage is metadata, not a file to follow. No content is copied from it.
            replacement = str(destination / 'lineage-not-present' / Path(value).name)
            rewrites.append(dict(field=field, original=value, replacement=replacement, content_present=False))
            return replacement
        return value

    for name in before:
        if not name.endswith('_manifest.json'):
            shutil.copy2(source / name, raw / name)
            assert hashlib.sha256((raw / name).read_bytes()).hexdigest() == before[name]['sha256']
    dump(raw / manifests[0].name, normalize(manifest))
    # Intentionally empty authority, rather than manufacturing a successful completed record.
    dump(destination / 'data/dev-copy/system/state.json', dict(version=1, lectures={}))
    dump(destination / 'data/dev-copy/system/ai_state.json', dict(schema_version=1, processed={}))
    config = destination / 'app/config/config.json'
    dump(config, dict(schema_version=1, version='1.9.4', application_home='..', install_root='../versions/copy-gate',
        data_root=str(destination / 'data'), active_workspace='dev-copy',
        workspaces={'dev-copy': dict(name='DEV-копии Raw/SRT · без журнала completed', folder='dev-copy',
            lecture_state='system/state.json', ai_state='system/ai_state.json', worker_home='run/workspaces/dev-copy',
            subjects=[dict(subject_code=code, subject_name='管理科学研究方法 · Методы исследований [DEV-копия]', folder=code,
                           default_language='zh', enabled=True, paths=dict(audio='audio', raw='raw', ready='word'))])},
        languages=dict(lecture='zh', dialogue='auto'), asr=dict(model='large-v3', device_mode='cpu'),
        dialogue=dict(folder='dialogue', runtime='run/dialogue'), dictionary=dict(book='dictionary/vocabulary.xlsx'),
        ai=dict(mode='manual_chatgpt', queue_runtime='run/ai_queue'), task_prefix='LP-000000000028'))
    (destination / 'app/versions/copy-gate').mkdir(parents=True, exist_ok=True)
    snapshot = SnapshotProvider(destination, config).snapshot()
    assert snapshot['available'] and not snapshot['errors'], snapshot['errors']
    assert len(snapshot['catalog']) == 1
    row = snapshot['catalog'][0]
    assert row['stages']['raw'] == 'available' and row['status'] == 'problem'
    assert any('completed' in reason for reason in row['reasons'])
    assert row['progress'] is None and snapshot['counts']['done'] == 0
    assert before == fingerprint(source), 'Source DEV copies changed'
    proof = dict(owner='VIC28 Work S', synthetic_content=False, derived_config=True, completed_ledger_transferred=False,
                 source=str(source), files=before, rewrites=rewrites, original_manifest_sha256=before[manifests[0].name]['sha256'],
                 copied_manifest_sha256=hashlib.sha256((raw / manifests[0].name).read_bytes()).hexdigest(),
                 snapshot=snapshot, result='PASS', source_files_unchanged=True)
    dump(marker, proof)
    print(json.dumps(dict(result='PASS', config=str(config), destination=str(destination), files=len(before),
                          parts=row['parts'], raw=row['stages']['raw'], status=row['status'], reasons=row['reasons']), ensure_ascii=False))


if __name__ == '__main__': main()
