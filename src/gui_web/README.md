# VIC-28 · read-only Dashboard / Work S

Preview 2, 21 октября 2026. Продолжение Liquid Glass-прототипа 00.03S и Preview 1. Локальный HTML/CSS/JS и небольшой Python host только для чтения существующего каталога; React/build tooling не требуется. Добавлен отдельный DEV WebView2-host без установщика. Результаты визуальной проверки и native gate: `docs/VIC28_PREVIEW2.md` из корня репозитория.

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

Preview 2 содержит 13 разных состояний backend и 5 AI-задач. Dashboard показывает первые 6 лекций; «Подробности» открывают каталог с полной карточкой. AI-очередь — фильтр существующих AI rows, без нового ledger. Основной текст увеличен; поле поиска сохраняется во время IME-композиции, пока карточки и heartbeat продолжают обновляться.

Дополнительные явно синтетические сценарии:

```powershell
.\Start-Dashboard.ps1 -VisualFixture -FixtureScenario stale -Port 8771 -NoBrowser
.\Start-Dashboard.ps1 -VisualFixture -FixtureScenario unknown -Port 8772 -NoBrowser
.\Start-Dashboard.ps1 -VisualFixture -FixtureScenario preparing -Port 8773 -NoBrowser
```

У каждого сценария отдельная `.local/vic28-visual-fixture-<scenario>`. `stale` скрывает live N/M/percent/ETA/device; `unknown` сохраняет N/M 2/3 при неизвестных percent/ETA; `preparing` показывает подготовку аудио без процента. Для переопределения места маленького набора есть `-FixtureRoot`.

Подготовка копий реальных DEV Raw/SRT, из корня UI-worktree:

```powershell
& 'C:\PipLine GPT WORK\app\runtime\document\python.exe' -B tests\vic28_dev_copy.py --shared-dev-root 'C:\PipLine GPT WORK' --source 'C:\PipLine GPT WORK\scratch\vic30-sprint04-methods-2026-10-19\source'
.\src\gui_web\Start-Dashboard.ps1 -DevRoot '.\.local\vic28-dev-copy' -Python 'C:\PipLine GPT WORK\app\runtime\document\python.exe' -Port 8770
```

Не переносится completed authority: ожидаются 7 частей, Raw есть, явная причина «completed не подтверждён», Done=0. Исторические абсолютные пути нормализуются только в новой копии manifest; оригиналы не меняются и не открываются по этим ссылкам. Хеши и таблица замен: `.local/vic28-dev-copy/VIC28_DEV_COPY.json`. Содержимое Raw остаётся отдельно от кода и source ZIP.

Нативное окно (сначала запустите viewer; перед повторной сборкой закройте прошлое окно gate):

```powershell
.\Start-NativeGate.ps1 -Url 'http://127.0.0.1:8769'
```

Существующие .NET Framework 4.8, C# compiler и Evergreen WebView2 используются на месте. Три маленьких SDK DLL из установленного Office (либо `-SdkDirectory`) копируются только в `.local/vic28-native-gate/bin`, около 0,75 MiB. Ничего не скачивается. `-BuildOnly` компилирует без запуска, `-Output` задаёт каталог evidence. DLL, EXE и profile не входят в Git/source ZIP и не становятся обязательной зависимостью продукта.

Проверены настоящие Windows 192 DPI / 200%, PerMonitorV2 и Microsoft Pinyin с подтверждёнными китайскими кандидатами при автоматическом polling. Панель «Контент» меняет только WebView zoom. Browser 125/150/200% сочетает viewport и pixel density для условного экрана 2880×1800; это web layout, а не нативная смена Windows DPI. Нативные 125/150%, перенос между мониторами и screen reader остаются непроверенными.

`tests/vic28_preview2.cjs` создаёт заполненные скриншоты и проверяет 30 компоновок, все состояния, контраст основных подписей, реальные DEV-копии и IME/heartbeat regression. Требует viewer 8769–8773; вывод — `VIC28_PREVIEW2_OUTPUT`. Обычный браузерный regression остаётся в `tests/vic28_browser.cjs`.
