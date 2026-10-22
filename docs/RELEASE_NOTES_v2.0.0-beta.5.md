# Lecture Pipeline v2.0.0-beta.5 — pre-release notes

This is a Windows 11 x64 beta. It is a full Setup.exe delivery. Existing v2.0.0-beta.4 installations must use **Setup.exe --upgrade**; the beta.4 code-only updater cannot install this version.

## Included

- A read-only WebView2 dashboard for lecture and course status, with the existing Tk interface available from the separate **Lecture Pipeline (Tk)** launcher. Processing and data ownership remain in the Python backend.
- Safer worker start and restart confirmation, including delayed Task Scheduler starts and a new-session heartbeat check (VIC-26).
- Course Setup fixes for connecting existing folders, explicit creation of recommended folders, preview refresh and rollback on save failure (VIC-27).
- AI queue refresh after each completed lecture, retaining existing locking and idempotency rules.
- Installer first-launch readiness acknowledgement. If WebView2 initialization fails during a beta.4 upgrade, Setup restores the previous launcher, version pointer and installation metadata from its recovery journal.
- Product icon and managed shortcut updates. User-edited or unrelated shortcuts remain untouched.

## Compatibility and scope

- Configuration schema 1 and vocabulary XLSX schema 1.4 remain in use. The upgrade does not migrate or replace the dictionary.
- Existing courses, external folder paths, Raw/SRT, AI queue, processed lecture records and user data remain in their configured locations.
- The WebView2 dashboard is for viewing. Worker, AI and course commands remain in Tk. VIC-30 vocabulary experiments, Excel GUI and automatic AI are not included.
- No automatic worker registration or Task Scheduler changes are performed by Setup.exe.

Use the [safe upgrade guide](BETA5_SAFE_UPGRADE.md) before updating an existing installation. This release candidate has not been published or installed into Production.
