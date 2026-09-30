$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Config.ps1')
& $resolved.document_python -B -X utf8 (Join-Path $PSScriptRoot 'ai_finalize.py') @args
exit $LASTEXITCODE
