# VIC-28 · read-only Dashboard / Work S

Первая запускаемая версия нового GUI, 20 октября 2026. Продолжение Liquid Glass-прототипа 00.03S. Локальный HTML/CSS/JS и небольшой Python host только для чтения существующего каталога; React/build tooling и новые runtime-компоненты не требуются.

## Запуск в общей DEV-директории

Двойной щелчок по `Start-Dashboard.cmd` откроет `http://127.0.0.1:8768` в обычном браузере. Консоль оставляется открытой; Ctrl+C закрывает только viewer. Рабочие процессы Pipeline не запускаются и не останавливаются.

По умолчанию используется уже существующий `C:\PipLine GPT WORK\app\runtime\document\python.exe` и `C:\PipLine GPT WORK\app\config\config.json`. Модель, CUDA и Python не копируются и не загружаются. Скрипт добавляет путь своих модулей явно: embedded Python может не добавлять папку скрипта в sys.path. `_pth`, runtime и глобальные настройки не меняются.

Параметры PowerShell:

```powershell
.\Start-Dashboard.ps1 -DevRoot 'C:\PipLine GPT WORK' -Port 8768 -NoBrowser
```

Для другого disposable DEV-корня укажите `-DevRoot`, при необходимости `-Config` и существующий `-Python`. Все фактические источники должны оставаться внутри выбранного DEV-корня. Изменение путей на Production/Drive не допускается для этой приёмки.

## Два раздельных источника

1. **Start-Dashboard.cmd** — только реальные read-only данные отдельной DEV-установки. На проверке 20.10.2026 это были 0 лекций, 0 входящих, выбранный CPU и отсутствующие heartbeat. Интерфейс показывает именно это; отсутствие heartbeat не объявляется остановленным worker.
2. **Start-Visual-Fixture.cmd** — отдельный `http://127.0.0.1:8769`. Маленький синтетический набор создаётся только в принадлежащей Work S `.local/vic28-visual-fixture`. Первый снимок фиксируется в памяти; в шапке постоянно написано «Синтетический пример». Пример показывает 2/3, 57%, ETA ASR, GPU, остановленный Dialogue, Raw, waiting_ai, Word, словарь, Done и ошибку. Он не подтверждает работу ASR/GPU. Аудио/Word в fixtures — только presence markers, их нельзя воспроизводить/открывать как документы.

Не переносите проверочные записи в реальную DEV-установку. Смена источника из браузера не предусмотрена. Источник и режим задаются при запуске host.

## Доступные действия

Навигация, выбор лекции, фильтры курса/этапа, поиск по русским и китайским названиям, Ctrl+K, просмотр причин, источника и read audit. Прозрачность можно уменьшить локально. Запуск worker, приём лекции, редактирование config, recovery, AI import/export, safe-open и updater не подключены. Tk GUI и его исходники остаются штатным fallback.

## Контракт и перенос

См. `DATA_CONTRACT.md`. Используется существующий `lecture_catalog.build(Config)` из `src/app` той же рабочей копии. Статусы, identity, dates и live ASR gate не переписаны. Это не второй Pipeline. HTML/JS потребляет DTO `vic28.dashboard/1` и не знает путей authority files.

При будущем .NET/WebView2 host можно заменить только транспорт снимка, сохранив DTO, статические ресурсы и существующие Python read services. Native host сохраняет файловые диалоги, safe-open, управление системными задачами, setup/updater и транзакции. Интеграция в release/launcher отсутствует; выполняется Work A после визуальной приёмки.

## Проверки

Из корня репозитория:

```powershell
& 'C:\PipLine GPT WORK\app\runtime\document\python.exe' -B tests\test_vic28_dashboard.py
```

Браузерная проверка `tests/vic28_browser.cjs` требует Playwright только в среде QA и два запущенных viewer. Укажите `NODE_PATH`, если пакет находится в bundled QA runtime, и при необходимости `CHROME_PATH`, `VIC28_QA_OUTPUT`, `VIC28_DEV_URL`, `VIC28_FIXTURE_URL`. В продуктовых файлах нет зависимости от Codex runtime или Playwright.

Браузерный scale 125/150/200% и размеры viewport проверяют web layout, но не являются нативной приёмкой Windows DPI, WebView2, китайского IME и screen reader. Эти проверки остаются для этапа desktop host.
