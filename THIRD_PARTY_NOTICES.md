# Third-party notices — v1.9.5-beta.1 thin Beta

This artifact distributes the private Python runtimes, application and the base dependencies inventoried in third_party/manifest.json, with their license/notice texts in third_party/licenses and the original runtime package directories.

It does NOT distribute PyAV/FFmpeg/codecs, CTranslate2 (including its Intel OpenMP and statically incorporated native closure), Whisper model, or NVIDIA CUDA/cuBLAS/cuDNN components. These are separate user-provisioned supplier components. Their technical manifests pin exact files and hashes; they are not mirrored in our release, and Lecture Pipeline does not claim legal clearance of those external supplier wheels.

CPython retains PSF/incorporated-software terms; faster-whisper, python-docx and openpyxl retain MIT terms; tokenizers and FlatBuffers retain Apache-2.0 terms; NumPy, lxml, ONNX Runtime and the other remaining distributions retain their own bundled third-party notices. Intel material in an ONNX notice remains associated with ONNX, not with the externally imported CTranslate2 wheel. Package-level licenses do not replace incorporated-software terms.

Clean-Windows/login/reboot validation remains a declared limitation of this first Beta. No imported installation should be uploaded as a release. Build the base ZIP using the enforced ownership/path/native-artifact exclusion gate.
