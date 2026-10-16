# Lecture Pipeline

**Current public beta: v2.0.0-beta.4**

**Download: [v2.0.0-beta.4 GitHub Release](https://github.com/SongYuanJing/LecturePipeline/releases/tag/v2.0.0-beta.4)**

**Download Setup.exe from the release page.** The current release is a prerelease; use the link above rather than `releases/latest`.

Local lecture transcription for **Windows 11 x64**, with **CPU / NVIDIA GPU** support:
audio → Raw TXT/SRT → manual-compatible AI stage → Word and vocabulary.

## Install and first run

1. Download and run **Setup.exe** from the linked release. Choose writable installation and separate data locations. A system Python or .NET runtime is not required.
2. Setup obtains the private base runtime and pinned PyAV, CTranslate2, Whisper large-v3 and GPU components as needed, checking sizes and SHA-256. Verified downloads are cached; large downloads can resume. Offline/manual component import remains an advanced fallback.
3. Choose **Auto**, **CPU** or **GPU**. Auto selects GPU only after the private runtime probe succeeds; otherwise it uses CPU. Forced GPU reports a failed probe rather than silently switching to CPU. CPU does not require CUDA.
4. Complete setup and open the application. Run `Integrate.cmd -Apply` when registering this installation's worker tasks. The application shortcut is independent of worker task registration.
5. Configure a Course and its Inbox, Raw and final Word folders. Keep your lecture data outside the installation directory.

Setup does not install NVIDIA drivers or change global PATH or system Python. See [online components](docs/ONLINE_COMPONENTS.md), [offline import](docs/OFFLINE_INSTALL.md) and [bootstrapper](docs/PHASE_1C.md).

## Process lectures

Use the Course Inbox or add a lecture manually. Multipart recordings belong to one lecture with ordered parts. The Catalog shows lecture dates, part counts, processing state and available output files; progress and ETA are shown where meaningful.

After transcription, export the AI packet for ordinary ChatGPT and import the resulting `ai_content.json` using the existing manual workflow. The local finalizer validates the result, creates Word and updates vocabulary. **Automatic AI API integration is not implemented.** Chat history is optional context, never pipeline state.

Word/Excel are optional for generating documents, useful for viewing results. Google Drive is optional; locally available folders can be used. Workers can continue running when the GUI is closed.

## Updates and data

In the application, select **Проверить обновления** (Check updates), then **Обновить** when a newer applicable release is available. Updates come only from tagged GitHub Releases, never from `main`. There is no background automatic update check.

The existing updater downloads and verifies the release manifest/archive, stages the new version beside the old one, checks its health and switches `current.json`. Failed health or first-launch readiness retains/restores the previous version. The previous version remains available; user config and external lecture data are preserved rather than replaced by the code update.

`main` contains the accepted source and documentation. User installers are published in GitHub Releases.

**Legacy limitation:** a code-only upgrade from v1.9.7-beta.2 does not replace its stable `launcher/update_gui.py`, so its older updater error presentation remains. Fresh v2 Setup includes the updater UX fix. See [final acceptance](docs/VIC24_FINAL_ACCEPTANCE.md).

## Removal and Beta limitations

Close the GUI and stop this installation's workers before using the documented removal tools. `launcher/RemoveIntegration.ps1 -Apply` removes integration; `Uninstall.cmd -Apply` performs manifest-based removal (omit `-Apply` to preview). External data, configuration and imported components are preserved; see [Packaging](PACKAGING.md). Never delete your data root to uninstall the application.

This is an unsigned Beta. Native acceptance covers the tested Windows 11 x64 / RTX 3050 host; Windows 10 and a newly provisioned Windows OS are not qualified. Supplier components remain subject to their applicable terms. See [release notes and evidence](docs/VIC24_RELEASE.md), [final acceptance](docs/VIC24_FINAL_ACCEPTANCE.md), [prerequisites](docs/PREREQUISITES.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
