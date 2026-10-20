# VIC-28 · read contract v1

## Граница

`readonly_host.py` слушает только `127.0.0.1`. Он отдаёт четыре статических ресурса и `GET /api/v1/snapshot`. POST/PUT/PATCH/DELETE возвращают 405; произвольных путей чтения и системных команд нет. Интернет и облачные сервисы не используются.

Нормальный источник задаётся `--dev-root` и `--config` при запуске. Корень проверяется до чтения каталога. Config, application home, data root, worker homes, queue, subject paths и Inbox bindings должны разрешаться внутрь DEV-корня. Абсолютные пути в прочитанном JSON также проверяются. Неподходящий путь даёт ошибку, а не автоматическую подмену.

## Переиспользованный backend

`pipeline_config.Config` → `lecture_catalog.build(c)` → существующие `lecture_dates` и `lecture_progress.live/presentation`. Источник кода — `src/app` этого worktree, baseline `c256ae3beee5c014478a833c1d156e14d0b32a8c`. В этих файлах нет изменений Work S. Обработку, queue refresh, finalizer, recovery и updater UI не вызывает.

Читаются по существующему контракту:

- `app/config/config.json`, `app/current.json`;
- активные lecture state и AI state;
- необязательные `worker_status.json`, `worker_jobs.json`, `inbox.json` / initialization markers;
- необязательный `queue.json`, metadata AI-пакетов и receipts;
- READY, Raw manifests и structural/presence evidence результатов, как это уже делает catalog;
- Dialogue status — только наблюдение heartbeat.

Чтение snapshot выполняется без создания `.pyc`, каталогов, locks, логов и persistent cache. В thread-scoped audit-контексте запрещены запись файлов, mutation filesystem и запуск subprocess. Содержимое аудио, Word и XLSX не открывается. Наличие файлов может проверяться существующим catalog; SHA больших результатов при poll не вычисляется. `read_audit.files` перечисляет открытые metadata files. JSON больше 16 MiB отклоняется с явной ошибкой UI.

## Envelope

```text
contract: "vic28.dashboard/1"
available: boolean                 # config / источник доступны
captured_at: ISO-8601 UTC
revision: string                   # content revision, не processing authority
source: { kind: "dev" | "fixture", frozen: boolean, dev_root, config }
workspace: { id, name } | null
version: string | null
workers: WorkerObservation[]
courses: [{ id, name, enabled, language, inbox_enabled }]
catalog: ExistingCatalogRow[]
pending: ExistingPendingRow[]       # ещё не принятые материалы, не новые lectures
counts: { total, ready, asr, raw, waiting_ai, done, problems, pending } | null
device: { configured: "cpu" | "gpu" | "auto" | null, observed: object | string | null }
preflight: { status: "not_run", message }
capabilities: { read_only: true, commands: false, safe_open: false, tk_fallback: true }
errors: string[]
read_audit: { files, file_count, content_excluded, mutations_allowed: false }
read_duration_ms: number
```

Поля existing catalog row сохраняются: `id`, `course_id`, `course_display_name`, `lecture_key`, date metadata, `status/status_text`, `parts/members`, `stages/paths`, `reasons/problems`, `recovery`, `integrity`, `progress/progress_view`. UI не определяет заново Done или duplicate и не редактирует immutable identity/date.

## Наблюдения и неизвестные значения

`WorkerObservation` содержит `reported_state`, `heartbeat_at`, `heartbeat_age_seconds`, `health = missing|fresh|stale|invalid`, `message`, `scheduler_state = null`. Scheduler не опрашивается; сообщения worker не доказывают состояние Windows task.

Для live ASR действует существующий backend gate: identity, attempt/job token, worker session, RUNNING, heartbeat ≤90 с, observation ≤10 с, корректные part count и числовые поля. Дополнительно UI-reader скрывает progress при невалидном heartbeat worker. `percent`, `eta_seconds` и observed backend сохраняют null; N/M берётся только из прошедшего gate observation. При устаревании остаётся durable stage и статическое число частей, без выдуманной текущей части.

ETA относится только к ASR. На waiting_ai/Word/vocabulary процент и ETA не показываются. Raw/Word availability и Done берутся из backend projection. Наличие Word само по себе не считается Done.

Если authority JSON отсутствует/повреждён, `errors` сохраняются, а `counts = null`: ошибка чтения не превращается в нулевой каталог. При потере HTTP-связи браузер помечает предыдущий снимок устаревшим и скрывает N/M, процент, ETA и observed device. Отсутствующие optional heartbeat не являются ошибкой пустой новой установки.

## Раздельный визуальный набор

`--visual-fixture` создаёт только собственные маленькие disposable fixtures. Снимок, построенный тем же catalog, фиксируется в памяти. `source.kind = fixture`, `source.frozen = true`; крупная постоянная подпись UI отличает его от DEV. Все числа в нём синтетические. Это инструмент визуальной оценки, не evidence реального ASR, CPU/GPU или workers.

## WebView2

DTO может передаваться через read-only bridge от native host без обязательного HTTP. Пока реализован только loopback transport. Будущий bridge должен отдавать versioned snapshots, не принимать произвольные пути/команды, сохранять backend authority и рассматривать ответы на команды отдельно от подтверждённых состояний. Внедрение в release и command API в этот этап не входят.
