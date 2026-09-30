# Offline installation — v1.9.3 thin candidate

Carry these separately: public application ZIP; exact PyAV wheel; exact CTranslate2 wheel; verified large-v3 model snapshot; optional verified NVIDIA/CUDA component folder. The public ZIP alone does not run ASR. There is no hidden download, pip latest, dependency resolution, system Python, user site or global PATH installation.

1. Extract to a new application folder. Run Components.cmd: the base runtime hashes and component states are checked without creating workspace/config/state.
2. ImportPyAV.cmd "path/av-18.1.0-cp311-abi3-win_amd64.whl"
3. ImportCTranslate2.cmd "path/ctranslate2-4.8.2-cp311-cp311-win_amd64.whl"
4. ImportModel.cmd "verified-large-v3-snapshot-folder"
5. Optional GPU: ImportCUDA.cmd "verified-cuda-component-folder". Never auto-install a driver.
6. Components.cmd reports Missing/Invalid/Valid independently, CPU capability and GPU capability with reasons. A missing CUDA component blocks GPU, not CPU.
7. Setup.cmd --data-root "external-folder" --workspace semester-1 --subject SUBJECT validates required ASR/model and document runtimes before workspace initialization.
8. Preflight.cmd, then explicit Integrate.cmd if desired. No automatic tasks/integration during import.

PyAV SHA256: ea1480b7a8d5405cb5f382b344731bf125fd2c1c6fae3964f6c48595628387ff.
CTranslate2 SHA256: 995938fcd24a1174a7abf9765e7fa216b5b91a1d8e8c4c8f383c7a186e8bab2e.
Exact official files.pythonhosted.org URLs are in launcher/pyav-manifest.json and launcher/ctranslate2-manifest.json. Obtain the supplier wheels yourself from those sources or use verified offline copies. We do not mirror/repackage these wheels in our artifact or claim to clear their supplier terms. Import CTranslate2 whole, including its own DLLs; do not remove individual OpenMP/cuDNN files from the local supplier component.

Each wheel import verifies filename, SHA256, version/ABI, metadata, RECORD, archive paths and native load before publishing a completed directory. A process lock serializes same-component imports; concurrent attempts fail clearly for retry. Wrong input or failed probe cannot replace an existing good component. Corrupted completed components fail closed. Interrupted owned staging directories are ignored by runtime and cleaned under lock on retry. Imported components are not owned by the application uninstall manifest.

Fully offline operation requires bringing all desired components separately. Keep the original supplier wheels for recovery. A completed component is verified before it is added to private Python paths. CPU/GPU worker behavior and ASR parameters are unchanged.
