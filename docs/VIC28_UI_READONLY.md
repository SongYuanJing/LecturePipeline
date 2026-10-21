# VIC-28 · Work S · read-only UI

Preview 1 от 20 октября и Preview 2 от 21 октября 2026. Локальный read-only Dashboard на базе дизайна 00.03S. Ветка `dev/vic28-ui-s` от `c256ae3beee5c014478a833c1d156e14d0b32a8c`. Актуальные результаты и ограничения: [VIC28_PREVIEW2.md](VIC28_PREVIEW2.md).

Добавлены только `src/gui_web`, целевые VIC-28 тесты и документы. Tk GUI, backend modules, workers, config/data schemas, installer, launcher, updater и release metadata не меняются. Никаких PR/push/main/release операций. Существующие многогигабайтные runtime/CUDA/model используются на месте и не входят в новый UI.

## Продолжение дизайна

Сохранены shell, Liquid Glass surfaces, лиловый акцент, sidebar, таблица, inspector, typography, icon set и responsive/reduced-motion правила из 00.03S. `web/glass-base.css` — точная копия CSS предыдущего прототипа, SHA-256 `1fbc431a3798a6b8f282c5b817efe3615364298981938d7e178ce0c2bc1f35f4`. SVG icons / базовые view helpers также перенесены. Новая визуальная концепция не создавалась.

Mock transitions старого прототипа не перенесены в DEV UI. Вместо них — DTO существующего read-only catalog. Добавлены heartbeat/source/freshness и рабочая транспортная граница. Проверочный набор отделён и постоянно подписан.

## Что уже можно оценивать

Dashboard: Lecture/Dialogue worker observations, queue, verified N/M, nullable percent/ETA, configured/observed ASR device, Raw, manual AI, errors, Word/vocabulary/final status. Каталог и inspector, Unicode search, фильтры, отдельные pending Inbox и course config view, diagnostics/read audit. Уменьшение прозрачности и клавиатурная навигация работают локально.

Старт: `src/gui_web/Start-Dashboard.cmd`. Контракт и подробности: `src/gui_web/README.md`, `src/gui_web/DATA_CONTRACT.md`.

## Данные первой проверки

Реальная отдельная DEV-установка `C:\PipLine GPT WORK\app/config/config.json`: workspace dev, один курс DEV, 0 лекций, 0 Inbox, CPU выбран, оба heartbeat отсутствуют. Реальные N/M, percent, ETA, GPU usage и processing progress отсутствуют; UI их не придумывает. Существующая DEV-копия словаря не читается Dashboard и не изменяется.

## Перенос Work A после визуальной приёмки

1. Проверить DTO и подключить read-only WebView2 transport к существующим services.
2. Принять native DPI/IME/accessibility и freshness/restart поведение.
3. Отдельно добавить allowlisted actions через backend/native host; safe-open, workers и updater не переносятся в JavaScript.
4. Сохранить Tk fallback до отдельного решения. Интеграция в релиз выполняется Work A.

Новая read-only граница намеренно мала. React и .NET shell не нужны, чтобы проверить пригодность интерфейса сейчас. Выбор shell/bridge и выпуск остаются последующей интеграцией, не скрытой частью данного UI-коммита.
