"""Small, clearly synthetic disposable records for visual QA, never real DEV installation data."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def create_fixture(root, scenario='normal'):
    if scenario not in ('normal', 'stale', 'unknown', 'preparing'):
        raise ValueError('Unknown visual fixture scenario')
    root = Path(root).resolve()
    marker = root / 'VIC28_SYNTHETIC_FIXTURE.json'
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise ValueError('Fixture destination is not empty and has no VIC-28 ownership marker')
    root.mkdir(parents=True, exist_ok=True)
    dump(marker, dict(owner='VIC28 Work S', synthetic=True, media_is_not_playable=True, scenario=scenario))
    app, data = root / 'app', root / 'data'
    config = app / 'config/config.json'
    now = datetime.now(timezone.utc).isoformat()
    subjects = [dict(subject_code=code, subject_name=name, folder=code, default_language='zh',
                     enabled=True, paths=dict(audio='audio', raw='raw', ready='word'))
                for code, name in [('ECON', '计量经济学 · Эконометрика'),
                                   ('OPS', '运筹学 · Исследование операций'),
                                   ('SYS', '系统工程 · Системная инженерия')]]
    dump(config, dict(schema_version=1, version='1.9.4', application_home='..',
                      install_root='../versions/fixture', data_root=str(data), active_workspace='visual',
                      workspaces=dict(visual=dict(name='Визуальный пример · синтетические данные', folder='visual',
                                                lecture_state='system/state.json', ai_state='system/ai_state.json',
                                                worker_home='run/workspaces/visual', subjects=subjects)),
                      languages=dict(lecture='zh', dialogue='auto'), asr=dict(model='large-v3', device_mode='auto'),
                      dialogue=dict(folder='dialogue', runtime='run/dialogue'),
                      dictionary=dict(book='dictionary/vocabulary.xlsx'),
                      ai=dict(mode='manual_chatgpt', queue_runtime='run/ai_queue'), task_prefix='LP-000000000028'))
    (app / 'versions/fixture').mkdir(parents=True, exist_ok=True)
    state, processed, jobs, tasks, observations = {}, {}, {}, {}, {}
    for code in ('ECON', 'OPS', 'SYS'):
        for name in ('audio', 'raw', 'word'):
            (data / 'visual' / code / name).mkdir(parents=True, exist_ok=True)
    cases = [('OPS', '01_2026-10-20', 'asr', 3), ('ECON', '02_2026-10-20', 'ready', 2),
             ('SYS', '03_2026-10-19', 'waiting_ai', 3), ('ECON', '04_2026-10-18', 'raw', 1),
             ('OPS', '05_2026-10-17', 'building', 2), ('SYS', '06_2026-10-16', 'vocabulary_pending', 2),
             ('ECON', '07_2026-10-15', 'completed', 1), ('SYS', '08_2026-10-14', 'error', 3),
             ('OPS', '09_2026-10-13', 'publishing', 2), ('ECON', '10_2026-10-12', 'ai_result_ready', 2),
             ('SYS', '11_2026-10-11', 'review', 2), ('ECON', '12_2026-10-10', 'problem', 2),
             ('OPS', '13_2026-10-09', 'waiting', 2)]
    for code, key, stage, parts in cases:
        folder = data / 'visual' / code
        identity, full = code + '/' + key, 'visual/' + code + '/' + key
        metadata = dict(lecture_date=key.split('_')[1], lecture_date_source='explicit', imported_at=now, recorded_at=None)
        files = []
        for n in range(1, parts + 1):
            name = key + '_' + str(n) + '.wav'
            # Presence-only metadata fixtures. These bytes are not an audio recording.
            if stage != 'problem' or n != parts:
                (folder / 'audio' / name).write_bytes(b'VIC28 SYNTHETIC - NOT AUDIO')
            files.append(dict(name=name))
        if stage == 'waiting':
            state[identity] = dict(status='queued', sources=files, **metadata)
            continue
        dump(folder / 'audio' / (key + '.READY.json'), dict(lecture=key, files=files, intake=metadata))
        if stage == 'review':
            dump(folder / 'audio' / ('.manual-handoff-' + key + '.json'),
                 dict(course_id=code, lecture_key=key, review_required=True, status='review',
                      error='Синтетический конфликт метаданных. Требуется ручная проверка.', **metadata))
        if stage in ('asr', 'publishing', 'error'):
            jobs[identity] = dict(phase={'asr':'transcribing','publishing':'publishing','error':'error'}[stage], token='fixture-job-' + key,
                                  error='Синтетическая ошибка проверки результатов; исходники сохранены.' if stage == 'error' else '')
        if stage == 'asr':
            observations[identity] = dict(progress=dict(schema=1, identity=identity, course_id=code, lecture_key=key,
                attempt='fixture-attempt', job_token=jobs[identity]['token'], worker_started_at=now, active=True,
                stage='asr', part_index=2, part_count=parts, percent=57.0, eta_seconds=420.0, eta_available=True,
                processed_audio_seconds=4001, total_audio_seconds=7020, elapsed_seconds=1200,
                updated_at=time.time(), backend=dict(device='cuda', compute_type='int8_float16')))
        if stage in ('ready', 'asr', 'publishing', 'error', 'review', 'problem'):
            continue
        raw = folder / 'raw' / key
        raw.mkdir(parents=True, exist_ok=True)
        (raw / 'raw.txt').write_text('Синтетический материал для проверки интерфейса. 示例文本。', encoding='utf-8')
        outputs = []
        for n in range(1, parts + 1):
            name = 'part-' + str(n) + '.srt'
            (raw / name).write_text('1\n00:00:00,000 --> 00:00:01,000\n示例：合成界面测试。\n', encoding='utf-8')
            outputs.append(dict(srt=name))
        dump(raw / (key + '_manifest.json'), dict(lecture=key, subject_code=code, combined_txt='raw.txt', outputs=outputs,
                                                 sources=[dict(name=f['name']) for f in files], **metadata))
        state[identity] = dict(status='completed', **metadata)
        if stage == 'raw':
            continue
        result = app / 'run/ai_queue/results' / code / key / 'ai_content.json'
        dump(result, dict(schema_version=1, synthetic=True))
        tasks[full] = dict(id=full, workspace='visual', subject_code=code, lecture_key=key, status=stage, ai_content=str(result))
        if stage in ('completed', 'vocabulary_pending'):
            word = folder / 'word' / key / 'lecture.docx'
            word.parent.mkdir(parents=True, exist_ok=True)
            word.write_bytes(b'VIC28 SYNTHETIC PRESENCE FIXTURE - NOT A DOCUMENT')
            processed[full] = dict(subject_code=code, lecture_id=key, output_docx_local_path=str(word),
                                   vocabulary_status='merged' if stage == 'completed' else 'batch_pending')
    home = app / 'run/workspaces/visual'
    progress = observations['OPS/01_2026-10-20']['progress']
    if scenario in ('unknown', 'preparing'):
        progress.update(percent=None, eta_seconds=None, eta_available=False,
                        stage='preparing' if scenario == 'preparing' else 'asr')
    heartbeat = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat() if scenario == 'stale' else now
    dump(data / 'visual/system/state.json', dict(version=1, lectures=state))
    dump(data / 'visual/system/ai_state.json', dict(schema_version=1, processed=processed))
    dump(home / 'worker_jobs.json', dict(jobs=jobs))
    dump(home / 'worker_status.json', dict(worker='RUNNING', started_at=now, heartbeat=heartbeat, lectures=observations))
    dump(app / 'run/dialogue/status.json', dict(worker='STOPPED', heartbeat=now))
    dump(app / 'run/ai_queue/queue.json', dict(schema_version=1, tasks=tasks))
    dump(home / 'inbox.json', dict(schema_version=1,
        sources={str(n): dict(course_id='SYS', source_path=str(root / ('fixture_part_' + str(n) + '.wav')), part_hint=n, status='waiting_parts') for n in (1, 3)},
        groups=dict(example=dict(course_id='SYS', session_stem='模型分析 · Модельный анализ', member_ids=['1', '3'],
                                 status='review', error='Не хватает части 2', lecture_date=None, expected_parts=3))))
    return config
