$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Config.ps1')
& $resolved.document_python -B -X utf8 (Join-Path $PSScriptRoot 'word_ai_v1.5\lecture_ai.py') @args
exit $LASTEXITCODE
