"""Opt-in, short real worker gate against a disposable unified DEV installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    root = args.install.resolve(strict=True)
    candidate = root.parent
    marker = json.loads((candidate / 'DEV_CANDIDATE.json').read_text(encoding='utf-8'))
    if marker.get('purpose') != 'Lecture Pipeline unified DEV' or Path(marker['install_root']).resolve() != root:
        raise ValueError('Only the isolated unified DEV installation is permitted')
    current = json.loads((root / 'current.json').read_text(encoding='utf-8'))
    app = (root / current['path']).resolve(strict=True)
    if json.loads((app / 'release.json').read_text(encoding='utf-8')).get('distribution_status') != 'dev':
        raise ValueError('Not a DEV version')
    sys.path[:0] = [str(app), str(app / 'gui_v1.8')]
    os.environ['LECTURE_CONFIG'] = str(root / 'config/config.json')
    from pipeline_config import Config, read
    import human_ux
    from lecture_worker import Worker
    c = Config(root / 'config/config.json')
    if c.install != app or c.data_root != Path(marker['data_root']).resolve() or c.data_root.parent != candidate:
        raise ValueError('Candidate config leaves its isolated root')
    if not args.fixture.is_file() or args.fixture.suffix.lower() != '.wav' or args.fixture.stat().st_size > 1_000_000:
        raise ValueError('A short WAV fixture is required')
    source = candidate / 'test-inputs' / args.fixture.name
    source.parent.mkdir(exist_ok=True)
    if source.exists() and digest(source) != digest(args.fixture):
        raise ValueError('Existing test input differs')
    if not source.exists():
        shutil.copy2(args.fixture, source)
    course = next(iter(c.subjects()))
    key = human_ux.add_lecture(c, course, '2026-10-20', human_ux.next_number(c, course), [source])
    worker = Worker(c.worker_home, stable_seconds=0)
    worker.safe_cycle()
    worker.safe_cycle()
    state = read(c.state)['lectures'].get(course + '/' + key, {})
    bundle = c.subjects()[course]['raw_dir'] / key
    files = {p.name: digest(p) for p in bundle.iterdir() if p.is_file()} if bundle.exists() else {}
    ai = read(c.ai_state)
    before = (json.dumps(state, sort_keys=True), files, json.dumps(ai, sort_keys=True))
    worker.safe_cycle()
    state2 = read(c.state)['lectures'].get(course + '/' + key, {})
    files2 = {p.name: digest(p) for p in bundle.iterdir() if p.is_file()} if bundle.exists() else {}
    ai2 = read(c.ai_state)
    result = dict(course=course, lecture=key, status=state2.get('status'),
                  raw_files=sorted(files2), ai_records=len(ai2.get('processed', {})),
                  repeated_cycle_unchanged=before == (json.dumps(state2, sort_keys=True), files2, json.dumps(ai2, sort_keys=True)),
                  worker_state=worker.worker_state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if state2.get('status') != 'completed' or not files2 or not result['repeated_cycle_unchanged']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
