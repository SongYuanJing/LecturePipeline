# VIC-28 Preview 2 · визуальная приёмка Work S

21 октября 2026. Продолжение 00.03S и Preview 1. Ветка `dev/vic28-ui-s`, база `c256ae3beee5c014478a833c1d156e14d0b32a8c`. Релизная интеграция не выполнялась.

## Проверяемый результат

Запускаются отдельные read-only HTML/CSS/JS viewer и небольшой диагностический .NET Framework/WebView2-host. Перенос в release/launcher, production .NET shell и command API остаются Work A после визуальной приёмки. Исходный Liquid Glass CSS сохранён побайтно; доработки добавлены в `dashboard.css`.

Основные подписи увеличены до 11–14 CSS px, статусы могут переноситься на следующую строку. Измеренный минимальный контраст проверенных основных подписей — **4,77:1** на консервативном фоне `#35313e`. Это целевая проверка, не полный accessibility audit. Активный этап выделен; окончания «части/частей» и «запись/записи» исправлены. Во время китайской композиции сохраняется только поле поиска; карточки и heartbeat продолжают обновляться.

На Dashboard оставлены первые 6 лекций и сводка Raw/AI/проблем. «Подробности» открывают каталог с карточкой, где больше места для этапов. Отдельная AI-очередь показывает существующие задачи всех AI-этапов. У неё нет собственного ledger или команд обработки.

## Состояния и источники

Синтетический набор: **13 лекций / 13 разных backend statuses**, 5 AI-задач и один неполный Inbox. Покрыты `ready`, `asr`, `publishing`, `raw`, `waiting_ai`, `ai_ready`, `word`, `vocabulary`, `done`, `error`, `review`, `problem`, `waiting`; отдельный сценарий `preparing` использует настоящее поле live-stage существующего progress resolver. Числа 2/3, 57%, ETA 7 минут и CUDA здесь исключительно синтетические; это не ASR/performance evidence.

| Сценарий | Проверенное отображение |
|---|---|
| Нормальный fixture | 2/3, 57%, ETA ASR около 7 минут; пометка синтетики на каждом экране |
| Stale heartbeat | Старше 12 минут; live N/M, percent, ETA и observed device скрыты, durable stage сохранён |
| Неизвестные percent/ETA | N/M 2/3 сохранён; нулевой процент и фиктивный ETA не подставляются |
| Подготовка аудио | Явный preparing stage без прогресса ASR |
| Ручной AI | Состояние ожидания без процентов, ETA и автоматической отправки |
| Ошибка / review / problem | Причины из backend; исходники и authority не исправляются viewer |
| Word до словаря | Словарь ожидает завершения; Done не заявляется |
| Неполный authority / потеря HTTP | Явное предупреждение; неполное чтение не выглядит пустым каталогом |
| Stale во время IME | Поле и окно кандидатов сохраняются; heartbeat и скрытие live progress перерисовываются сразу |

Обычная отдельная DEV-установка остаётся пустой: 0 лекций, 0 Inbox, CPU выбран, heartbeat отсутствуют. Её данные не заполнялись тестовыми записями.

Реальные DEV-копии: из существующей `scratch/vic30-sprint04-methods-2026-10-19/source` перенесены **15 TXT/SRT с неизменными байтами** и копия manifest в `.local/vic28-dev-copy`. Исходные 16 файлов остались неизменными по SHA-256 и mtime. Аудио не копировалось. Исторические абсолютные source paths в новом manifest заменены на отсутствующие локальные lineage paths; содержимое этих путей не читалось. Оригинальный и производный хеши manifest, таблица замен и read audit сохранены в `VIC28_DEV_COPY.json`.

Config копии производный, completed ledger намеренно не создаёт записи об успехе. Каталог видит 7 частей и наличие Raw, но показывает «completed не подтверждён; восстановление VIC-12» и Done=0. Это ожидаемый результат отсутствующей authority, а не повреждение оригинальной лекции. Reader не читает содержимое Raw/SRT: он проверяет manifest и наличие перечисленных файлов.

## Что работает и что не подключено

| Элемент | Реализация |
|---|---|
| Dashboard, polling, workers/heartbeat | Реальное чтение DTO; свежесть по существующему backend gate |
| Каталог, AI-очередь, Inbox, курсы | Рабочие read-only представления существующих rows/config |
| Поиск, фильтры, выбор, карточка | Работают, включая китайский/русский текст, IME и Ctrl+K |
| Проценты, N/M, ETA, GPU/CPU | Отображаются только при наличии соответствующих данных; fixture явно подписан |
| Причины ошибок, read audit | Работают без recovery или записи в authority |
| Уменьшение прозрачности, keyboard modal | Работают локально |
| Tk fallback | Исходники сохранены; кнопка показывает информацию, не запускает Tk |
| Worker start/stop, приём и изменения курса | Не подключены, команды не имитируются |
| Raw/Word open, AI export/import, recovery | Не подключены; наличие результата не является просмотром файла |
| Updater, preflight, GPU probe, setup | Не вызываются этим UI |
| Product bridge / установка / release shell | Не реализованы в Preview 2; native gate является отдельным QA-host |

## Первый native gate

Существующие локальные компоненты: .NET Framework 4.8, Framework C# compiler, WebView2 SDK 1.0.2365.46 из установленного Office, Evergreen Runtime **155.0.4283.62**. Скопировано около 0,75 MiB SDK DLL в собственную `.local`; installer/SDK/runtime/model/CUDA не загружались. Сторонние DLL и скомпилированный EXE не включены в Git и source ZIP.

| Проверка | Результат / граница |
|---|---|
| WebView2 startup и loopback DTO | PASS, настоящий WebView2 process и native window |
| Windows DPI | PASS на **192 DPI / 200%**, awareness=2 (PerMonitorV2), DPR=2 |
| Большое окно | Веб-viewport 1440×795 CSS px; root/main overflow=0 |
| Restore / небольшое окно | PASS, реальный viewport 700×404 CSS px при DPR=2; root/main overflow=0, вертикальная прокрутка |
| Китайский Microsoft Pinyin | PASS, физические клавиши `y/u/n` → кандидат `运`; на финальном коде `f/a` → кандидат `法` |
| IME + настоящий polling | PASS на DEV-копии; композиция сохранялась несколько минут, свежий timestamp продолжал обновляться; `法` нашёл единственную лекцию |
| Русский текст / китайские названия | Отображены в настоящем native window без повреждения Unicode |
| Нативные 125/150% / WM_DPICHANGED между мониторами | Не проверены: системные настройки DPI не менялись |
| Screen reader, native release packaging / updater | Не проверялись и не заявляются принятыми |

`sky` UI Automation сообщает фокус WebView document; focusin/input/composition в изолированном host подтверждены дополнительно событиями самой страницы. Unicode paste не выдаётся за IME: китайский кандидат выбирался клавишами в реальном окне Microsoft Pinyin. Profile и QA traces находятся только в `.local/vic28-native-gate`.

Browser 125/150/200% проверен отдельно с viewport и pixel density условного экрана 2880×1800, плюс 1280×720, 1024×576, 640×360. Вертикальная прокрутка ожидаема; горизонтального переполнения страницы в 30 целевых компоновках нет. При малой ширине карточки переходят в одну колонку, навигация остаётся доступной через подписанные кнопки/иконки.

## Проверки и повторный запуск

- 17 Python tests: PASS, 12,031 с. Покрывают read fence, отсутствие мутаций, authority/freshness, все fixture stages и null values.
- Браузерный regression: PASS; целевой Preview 2 прогон после последнего IME-фикса: PASS, 30 компоновок, 0 JavaScript errors, 0 external page requests, contrast minimum 4,77:1.
- Проверка на копиях: PASS, 7 частей, Raw есть, отсутствие completed authority показано явно, source hashes/mtime сохранены.
- Полный backend regression и ASR smoke не запускались: execution paths Work A не менялись.

Команды viewer, scenarios, DEV-copy helper и native host: [README](../src/gui_web/README.md). Контракт чтения: [DATA_CONTRACT](../src/gui_web/DATA_CONTRACT.md). QA: `tests/test_vic28_dashboard.py`, `tests/vic28_browser.cjs`, `tests/vic28_preview2.cjs`, `tests/vic28_dev_copy.py`.

Нативная DPI-конфигурация и профиль сверялись с первичными источниками: [WinForms high DPI](https://learn.microsoft.com/en-us/dotnet/desktop/winforms/high-dpi-support-in-windows-forms), [WebView2 environment / userDataFolder](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environment.createasync), [WinForms WebView2 initialization](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.winforms.webview2.ensurecorewebview2async).

Production, Google Drive, рабочий словарь, Work A backend/build, GitHub main, tags и Releases не изменялись. Разрешённые записи: собственный UI-worktree, маленькие `.local` fixtures/profile/evidence, локальная UI-ветка и handoff. Tk fallback сохранён. Визуальная и релизная приёмка остаются за пользователем и Work A.
