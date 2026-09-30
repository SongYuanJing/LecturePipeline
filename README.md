# Lecture Pipeline — Windows x64 Beta

Local lecture transcription and document preparation: audio parts → TXT/SRT → self-contained AI packet → manual ChatGPT result → Word and a merged vocabulary workbook. A separate local Dialogue / Quick mode is also included. Workers continue running when the control window is closed.

## Download and first run

Use the **v1.9.5-beta.1 tagged GitHub Release** and its `LecturePipeline-1.9.5-beta.1-win-x64.zip`, not a checkout of the development branch. Compare its SHA256 with the release checksum. Until the repository is published, the same artifact is available locally only.

1. Extract into a new writable folder. Keep user data in a separate folder.
2. Install the official Microsoft Visual C++ v14 x64 runtime if missing. Do not install a system Python for this application.
3. Open **Lecture Pipeline.vbs** to enter first-run setup. Import the pinned PyAV and CTranslate2 supplier wheels and large-v3 model folder using the component controls. Optional CUDA uses the exact folder containing the pinned DLLs. See [Offline installation](docs/OFFLINE_INSTALL.md) for exact versions, hashes, supplier sources and command alternatives.
4. Choose a separate data directory, workspace, subject and language. Complete setup. With integration enabled, this creates unique per-installation Windows tasks and starts both workers.
5. Reopen the generated **Lecture Pipeline.lnk** shortcut. It uses private pythonw without a console and works independently of VBS. If Windows Script Host is disabled before setup, use the documented command setup and `Integrate.cmd -Apply`, then the shortcut.

## Add a lecture and finish its AI step

In **Лекции → Добавить лекцию**, select the subject/date/number and audio files. **Several files in one submission are ordered parts of ONE lecture**, not separate lectures. Confirm to publish READY for the running worker. After transcription, the AI queue shows `waiting_ai`.

Export the task ZIP for ordinary ChatGPT. Supply its START_HERE, versioned instructions and sources; receive a valid `ai_content.json`. Import that result in the GUI. The local finalizer validates it, creates Word, merges vocabulary and marks the task completed. Chat history is optional context, never pipeline state. There is no OpenAI API integration or automatic ChatGPT operation.

## Components and data

Private Python runtimes and base dependencies are included. PyAV, CTranslate2, large-v3 and optional CUDA are separate verified imports, not bundled binaries. No Codex runtime, system Python or user HuggingFace cache is required. GPU is optional; the established CPU int8 fallback is retained. No driver installation or global PATH changes.

Word/Excel are optional for generation, useful for viewing results. Google Drive is optional; an available local filesystem data root works. External data contains workspaces/audio/TXT/SRT/Word, dictionary and lecture states. Application config, journal and logs stay in the application directory.

## Removal and Beta limitations

Close the GUI, stop this installation's workers, then use `launcher/RemoveIntegration.ps1 -Apply` and `Uninstall.cmd -Apply` (omit `-Apply` to preview). The manifest-based removal preserves external data, configuration and imported components; see [Packaging](PACKAGING.md). Never delete your data root to uninstall the application.

This is an unsigned first Beta. Validation uses a separate installation on the existing Windows host, not a newly provisioned OS. Full clean-Windows/login/reboot certification remains outside this release pass. Progress/part counts/ETA and AI workflow presentation need refinement; Word layout/names remain unchanged. Supplier components require separate acquisition and applicable terms. See [Backlog](BACKLOG.md), [Prerequisites](docs/PREREQUISITES.md), [Third-party notices](THIRD_PARTY_NOTICES.md) and [validation record](docs/BETA1_VALIDATION.md).
