from __future__ import annotations

import json
import argparse
import hashlib
import shutil
import tempfile
import uuid
from contextlib import contextmanager
import re
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

from lecture_asr import bounded_segments
from pipeline_config import Config
CONFIG = Config()
WhisperModel = CONFIG.new_model

ROOT = CONFIG.workspace_root

MODEL_NAME = "large-v3"
DEVICE = "cuda"
COMPUTE_TYPE = "int8_float16"

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".mp4", ".mov", ".ogg", ".opus"}
# Имя можно писать достаточно свободно. Рекомендуемый формат:
#   №5_2026-09-19_p1.m4a
#   №5 19.09.2026 pt01.m4a
#   5-19_09_2026-1.m4a
# Все три варианта будут приведены к одному ключу: 05_2026-09-19.
#
# Для старых имён без номера лекции остаётся fallback:
#   19_09_2026_p1 / 19_09_2026_pt1 / 19_09_2026_part1
STRUCTURED_NAME_RE = re.compile(
    r"^\s*(?:№\s*)?(?P<lecture_no>\d{1,3})\s*[-_. ]+\s*"
    r"(?P<date>(?:\d{4}[-_. ]\d{1,2}[-_. ]\d{1,2})|(?:\d{1,2}[-_. ]\d{1,2}[-_. ]\d{4}))"
    r"(?:\s*[-_. ]+\s*(?:(?:p|pt|part|ч|часть)\s*[-_. ]*)?(?P<part>\d{1,3}))?\s*$",
    re.IGNORECASE,
)

LEGACY_PART_RE = re.compile(
    r"^(?P<lecture>.+?)[ _.-]+(?:(?:p|pt|part|ч|часть)[ _.-]*)(?P<part>\d{1,3})$",
    re.IGNORECASE,
)

SUBJECTS = CONFIG.subjects()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_print(text=""):
    print(text, flush=True)


def find_one(parent: Path, predicate, label: str) -> Path:
    matches = [p for p in parent.iterdir() if p.is_dir() and predicate(p)]
    if not matches:
        raise FileNotFoundError(f"Не найдена папка: {label}\nВнутри: {parent}")
    matches.sort(key=lambda p: p.name)
    return matches[0]


def discover_layout():
    return CONFIG.layout()


def load_state(path: Path) -> dict:
    # Fail closed: losing the completion ledger must never enqueue old lectures.
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("lectures"), dict):
        raise ValueError("Некорректный state.json; восстановите контрольную копию")
    if any(not isinstance(v, dict) or not isinstance(v.get("status"), str)
           for v in data["lectures"].values()):
        raise ValueError("Некорректные записи state.json")
    return data


def save_state(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_log(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {text}\n")


def source_signature(path: Path) -> dict:
    st = path.stat()
    return {
        "name": path.name,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
    }


def _parse_date(text: str):
    nums = [int(x) for x in re.findall(r"\d+", text)]
    if len(nums) != 3:
        return None

    if nums[0] >= 1000:
        year, month, day = nums
    elif nums[2] >= 1000:
        day, month, year = nums
    else:
        return None

    try:
        dt = datetime(year, month, day)
    except ValueError:
        return None
    return dt.year, dt.month, dt.day


def lecture_key_from_stem(stem: str):
    """
    Возвращает (канонический_ключ_лекции, номер_части).

    Главная идея: пунктуация не важна. Если в начале есть номер лекции
    и затем дата, то разные варианты записи имени попадут в одну группу.
    """
    m = STRUCTURED_NAME_RE.match(stem)
    if m:
        parsed_date = _parse_date(m.group("date"))
        if parsed_date:
            year, month, day = parsed_date
            lecture_no = int(m.group("lecture_no"))
            part_num = int(m.group("part")) if m.group("part") else 0
            key = f"{lecture_no:02d}_{year:04d}-{month:02d}-{day:02d}"
            return key, part_num

    # Совместимость со старыми именами, где номер лекции не указан.
    m = LEGACY_PART_RE.match(stem)
    if m:
        lecture = re.sub(r"[ .-]+", "_", m.group("lecture").strip())
        lecture = re.sub(r"_+", "_", lecture)
        return lecture, int(m.group("part"))

    # Один файл без номера части: не ломаем имя и обрабатываем как одну лекцию.
    return stem.strip(), 0


def collect_lectures(audio_dir: Path):
    groups = {}
    for p in audio_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        lecture_key, part_num = lecture_key_from_stem(p.stem)
        groups.setdefault(lecture_key, []).append((part_num, p))

    result = {}
    for lecture_key, items in groups.items():
        items.sort(key=lambda x: (x[0], x[1].name.lower()))
        result[lecture_key] = [p for _, p in items]
    return result


def lecture_state_key(subject_code: str, lecture_key: str) -> str:
    return f"{subject_code}/{lecture_key}"


def needs_processing(state, subject_code, lecture_key, parts, raw_dir, reprocess=False):
    record = state.get("lectures", {}).get(lecture_state_key(subject_code, lecture_key), {})
    if reprocess:
        return True
    # Also protect surviving output when a ledger entry has been lost.
    return (record.get("status", "").lower() not in {"completed", "done"}
            and not (raw_dir / lecture_key / f"{lecture_key}_manifest.json").exists()
            and not (raw_dir / lecture_key / f"{lecture_key}_raw.txt").exists())


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_numbers(parts, count):
    if type(count) is not int or not 1 <= count <= 999:
        raise ValueError("expected_parts должен быть числом от 1 до 999")
    numbers = [lecture_key_from_stem(p.stem)[1] for p in parts]
    if count == 1 and numbers == [0]:
        return
    missing = sorted(set(range(1, count + 1)) - set(numbers))
    if missing:
        raise ValueError(f"ожидаются части {missing}")
    if sorted(numbers) != list(range(1, count + 1)):
        raise ValueError("лишние, повторные или ненумерованные части")


def ready_path(cfg, key):
    return cfg["audio_dir"] / f"{key}.READY.json"


def read_ready(cfg, key, parts):
    path = ready_path(cfg, key)
    if not path.exists():
        raise ValueError("нет READY: комплект ещё не подтверждён")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("version") != 1 or data.get("lecture") != key:
        raise ValueError("неверный READY")
    check_numbers(parts, data.get("expected_parts"))
    files = data.get("files", [])
    if (not isinstance(files, list) or len(files) != len(parts)
            or any(not isinstance(f, dict) for f in files)
            or {f.get("name") for f in files} != {p.name for p in parts}):
        raise ValueError("состав комплекта не совпадает с READY")
    by_name = {f["name"]: f for f in files}
    for p in parts:
        entry = by_name[p.name]
        if (type(entry.get("size")) is not int or entry["size"] <= 0
                or p.stat().st_size != entry["size"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", "")))):
            raise ValueError(f"неполный файл или неверная подпись: {p.name}")
    return data


def prepare_ready(cfg, key, count):
    parts = collect_lectures(cfg["audio_dir"]).get(key, [])
    check_numbers(parts, count)
    before = [source_signature(p) for p in parts]
    files = [{"name": p.name, "size": p.stat().st_size, "sha256": digest(p)} for p in parts]
    if any(f["size"] <= 0 for f in files) or before != [source_signature(p) for p in parts]:
        raise ValueError("файлы пусты или изменяются; дождитесь окончания загрузки")
    save_state(ready_path(cfg, key), {
        "version": 1, "lecture": key, "expected_parts": count, "files": files,
    })


@contextmanager
def verified_inputs(cfg, key, parts):
    # Transcribe immutable local copies, never files still being synced by Drive.
    data = read_ready(cfg, key, parts)
    before = [source_signature(p) for p in parts]
    with tempfile.TemporaryDirectory(prefix="lecture-input-") as folder:
        copies = []
        entries = {f["name"]: f for f in data["files"]}
        for p in parts:
            target = Path(folder) / p.name
            shutil.copy2(p, target)
            if target.stat().st_size != entries[p.name]["size"] or digest(target) != entries[p.name]["sha256"]:
                raise ValueError(f"файл ещё загружается или изменён: {p.name}")
            copies.append(target)
        current = collect_lectures(cfg["audio_dir"]).get(key, [])
        if current != parts or before != [source_signature(p) for p in parts] or read_ready(cfg, key, parts) != data:
            raise ValueError("комплект изменился во время проверки")
        yield copies


@contextmanager
def pipeline_lock(path):
    # Windows releases the byte lock even after a crash. File is deliberately retained.
    import msvcrt
    with path.open("a+b") as f:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def fmt_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def fmt_short(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02}:{m:02}:{s:02}"
    return f"{m:02}:{s:02}"


def transcribe_one(model, audio: Path, prompt: str, hotwords: str, language="zh"):
    started = time.monotonic()
    segments, info = model.transcribe(
        str(audio),
        language=None if language == "auto" else language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True,
        initial_prompt=prompt,
        hotwords=hotwords,
    )

    duration = float(getattr(info, "duration", 0.0) or 0.0)
    stop_heartbeat = threading.Event()

    def heartbeat():
        # Даже если large-v3 долго считает первый кусок, консоль не выглядит зависшей.
        while not stop_heartbeat.wait(20):
            elapsed = int(time.monotonic() - started)
            safe_print(f"    ...в процессе, прошло {elapsed // 60:02d}:{elapsed % 60:02d} реального времени")

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()

    materialized = []
    last_percent = -10
    try:
        for seg in segments:
            text = seg.text.strip()
            if text:
                start = float(seg.start)
                end = float(seg.end)
                materialized.append((start, end, text))

                if duration > 0:
                    percent = min(100, int(end / duration * 100))
                    # Не спамим каждым сегментом: показываем шаг примерно 10%.
                    if percent >= last_percent + 10 or percent >= 99:
                        elapsed = int(time.monotonic() - started)
                        safe_print(
                            f"    прогресс: ~{percent:3d}% "
                            f"({fmt_short(end)} / {fmt_short(duration)} аудио), "
                            f"прошло {elapsed // 60:02d}:{elapsed % 60:02d}"
                        )
                        last_percent = percent
                elif len(materialized) % 10 == 0:
                    elapsed = int(time.monotonic() - started)
                    safe_print(
                        f"    прогресс: дошёл до {fmt_short(end)} аудио, "
                        f"прошло {elapsed // 60:02d}:{elapsed % 60:02d}"
                    )
    finally:
        stop_heartbeat.set()
        hb.join(timeout=1)

    elapsed = int(time.monotonic() - started)
    safe_print(f"    распознавание части закончено за {elapsed // 60:02d}:{elapsed % 60:02d}")
    bounded = bounded_segments(materialized, duration)
    if bounded != materialized:
        safe_print("    Таймкоды ограничены длительностью аудио; весь текст сохранён")
    return bounded, info


def write_srt(path: Path, segments):
    with path.open("w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{fmt_ts(start)} --> {fmt_ts(end)}\n")
            f.write(text + "\n\n")


def process_lecture(model, subject_code: str, cfg: dict, lecture_key: str, parts: list[Path], state: dict, state_file: Path, log_file: Path):
    with tempfile.TemporaryDirectory(prefix="lecture-output-") as folder:
        return _process_lecture(model, subject_code, dict(cfg, _staging_dir=folder),
                                lecture_key, parts, state, state_file, log_file)


def _process_lecture(model, subject_code: str, cfg: dict, lecture_key: str, parts: list[Path], state: dict, state_file: Path, log_file: Path):
    final_dir = cfg["raw_dir"] / lecture_key
    out_dir = Path(cfg["_staging_dir"])

    combined_path = out_dir / f"{lecture_key}_raw.txt"
    manifest_path = out_dir / f"{lecture_key}_manifest.json"

    all_sections = []
    part_outputs = []

    safe_print()
    safe_print("=" * 72)
    safe_print(f"[{subject_code}] {cfg['title']}")
    safe_print(f"Лекция: {lecture_key}")
    safe_print(f"Частей аудио: {len(parts)}")
    safe_print("=" * 72)

    for idx, audio in enumerate(parts, 1):
        safe_print()
        safe_print(f"[{idx}/{len(parts)}] {audio.name}")
        safe_print("Распознаю... large-v3 работает локально. Жди сообщения о прогрессе.")

        if hasattr(model,'progress_context'):model.progress_context=dict(part=idx,parts=len(parts))
        segments, info = transcribe_one(
            model,
            audio,
            cfg["prompt"],
            cfg["hotwords"],
            **({"language": cfg["default_language"]} if cfg.get("default_language", "zh") != "zh" else {}),
        )

        srt_path = out_dir / f"{audio.stem}.srt"
        part_txt_path = out_dir / f"{audio.stem}.txt"

        write_srt(srt_path, segments)

        with part_txt_path.open("w", encoding="utf-8") as f:
            for start, end, text in segments:
                line = f"[{fmt_short(start)} - {fmt_short(end)}] {text}"
                f.write(line + "\n")
                safe_print(line)

        all_sections.append(
            "\n".join([
                f"===== ЧАСТЬ {idx}/{len(parts)} =====",
                f"Источник: {audio.name}",
                "",
                *[f"[{fmt_short(s)} - {fmt_short(e)}] {t}" for s, e, t in segments],
                "",
            ])
        )

        part_outputs.append({
            "source": audio.name,
            "txt": part_txt_path.name,
            "srt": srt_path.name,
            "language": getattr(info, "language", "zh"),
        })

    combined_path.write_text("\n\n".join(all_sections), encoding="utf-8")

    manifest = {
        "lecture": lecture_key,
        "subject_code": subject_code,
        "subject": cfg["title"],
        "model": MODEL_NAME,
        "processed_at": now_iso(),
        "sources": [source_signature(p) for p in parts],
        "outputs": part_outputs,
        "combined_txt": combined_path.name,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Preserve the previous raw bundle before explicit replacement.
    if final_dir.exists():
        archive = cfg["raw_dir"] / ".history" / (lecture_key + "-" + uuid.uuid4().hex)
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(final_dir, archive)
    final_dir.mkdir(parents=True, exist_ok=True)
    for output in out_dir.iterdir():
        target = final_dir / output.name
        temporary = target.with_name(target.name + ".pending")
        shutil.copyfile(output, temporary)
        temporary.replace(target)
    out_dir = final_dir
    combined_path = out_dir / combined_path.name

    state_key = lecture_state_key(subject_code, lecture_key)
    state.setdefault("lectures", {})[state_key] = {
        "status": "completed",
        "model": MODEL_NAME,
        "processed_at": now_iso(),
        "sources": [source_signature(p) for p in parts],
        "output_dir": str(out_dir),
        "combined_txt": str(combined_path),
    }
    state["model"] = MODEL_NAME
    state["updated_at"] = now_iso()
    save_state(state_file, state)

    append_log(log_file, f"OK {state_key} -> {combined_path}")
    safe_print()
    safe_print(f"ГОТОВО: {combined_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Безопасная обработка комплектов лекций")
    parser.add_argument("--reprocess", action="append", default=[], metavar="SUBJECT/LECTURE")
    parser.add_argument("--prepare-ready", metavar="SUBJECT/LECTURE",
                        help="Подтвердить полностью загруженный комплект")
    parser.add_argument("--parts", type=int, help="Известное полное число частей")
    parser.add_argument("--dry-run", action="store_true", help="Проверить без распознавания и изменения state")
    args = parser.parse_args(argv)
    if args.prepare_ready and (args.parts is None or args.reprocess or args.dry_run):
        parser.error("--prepare-ready требует --parts и используется отдельно")
    if args.parts is not None and not args.prepare_ready:
        parser.error("--parts используется только с --prepare-ready")
    try:
        from pipeline_config import require_preflight
        require_preflight(CONFIG)
        CONFIG.worker_home.mkdir(parents=True, exist_ok=True)
        with pipeline_lock(CONFIG.worker_home / 'lecture_pipeline.lock'):
            return run(args)
    except Exception as e:
        safe_print(f"ОСТАНОВЛЕНО БЕЗ АВТОПЕРЕЗАПУСКА: {e}")
        return 2


def run(args):
    try:
        state_file, log_file, subjects = discover_layout()
    except Exception as e:
        safe_print("ОШИБКА СТРУКТУРЫ ПАПОК:")
        safe_print(str(e))
        return 2

    state = load_state(state_file)

    if args.prepare_ready:
        code, key = args.prepare_ready.split("/", 1)
        if code not in subjects or key not in collect_lectures(subjects[code]["audio_dir"]):
            raise ValueError("неизвестная лекция")
        prepare_ready(subjects[code], key, args.parts)
        safe_print(f"READY создан: {ready_path(subjects[code], key)}")
        return 0

    known = {lecture_state_key(c, k) for c, cfg in subjects.items()
             for k in collect_lectures(cfg["audio_dir"])}
    if set(args.reprocess) - known:
        raise ValueError(f"неизвестные лекции для reprocess: {set(args.reprocess) - known}")
    pending = []

    safe_print("Проверяю папки предметов...")
    safe_print()

    for code, cfg in subjects.items():
        groups = collect_lectures(cfg["audio_dir"])

        pending_here = 0
        for lecture_key, parts in groups.items():
            if needs_processing(state, code, lecture_key, parts, cfg["raw_dir"],
                                lecture_state_key(code, lecture_key) in args.reprocess):
                try:
                    read_ready(cfg, lecture_key, parts)
                except (ValueError, OSError, TypeError, AttributeError) as e:
                    safe_print(f"COLLECTING {code}/{lecture_key}: {e}")
                    if lecture_state_key(code, lecture_key) in args.reprocess:
                        raise ValueError(f"reprocess заблокирован: {e}") from e
                    continue
                pending.append((code, cfg, lecture_key, parts))
                pending_here += 1

        safe_print(
            f"[{code}] {cfg['title']}: "
            f"лекций найдено {len(groups)}, новых/изменённых {pending_here}"
        )

    if not pending:
        safe_print()
        safe_print("Новых аудиолекций нет. Ничего делать не нужно.")
        return 0

    safe_print()
    safe_print(f"Нужно обработать лекций: {len(pending)}")
    safe_print(f"Модель: {MODEL_NAME}")
    if args.dry_run:
        for code, cfg, key, parts in pending:
            with verified_inputs(cfg, key, parts):
                safe_print(f"READY {code}/{key}: проверены все части и SHA-256")
        return 0
    safe_print("Загружаю модель локально...")

    try:
        model = WhisperModel(
            MODEL_NAME,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            local_files_only=True,
        )
    except Exception as e:
        safe_print()
        safe_print("Не удалось открыть локальную large-v3.")
        safe_print("Модель должна быть уже скачана в кэш Hugging Face.")
        safe_print(str(e))
        return 3

    ok = 0
    failed = 0

    for code, cfg, lecture_key, parts in pending:
        try:
            with verified_inputs(cfg, lecture_key, parts) as verified_parts:
                process_lecture(
                    model=model,
                    subject_code=code,
                    cfg=cfg,
                    lecture_key=lecture_key,
                    parts=verified_parts,
                    state=state,
                    state_file=state_file,
                    log_file=log_file,
                )
            ok += 1
        except KeyboardInterrupt:
            safe_print("\nОстановлено пользователем.")
            append_log(log_file, f"STOP {code}/{lecture_key}")
            return 130
        except Exception as e:
            failed += 1
            safe_print()
            safe_print(f"ОШИБКА: {code}/{lecture_key}")
            safe_print(str(e))
            append_log(log_file, f"ERROR {code}/{lecture_key}: {repr(e)}")

    safe_print()
    safe_print("=" * 72)
    safe_print("ОБРАБОТКА ЗАВЕРШЕНА")
    safe_print(f"Успешно: {ok}")
    safe_print(f"С ошибкой: {failed}")
    safe_print(f"Состояние: {state_file}")
    safe_print("=" * 72)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
