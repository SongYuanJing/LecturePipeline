param([string]$Batch, [switch]$Apply, [string]$Find)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Config.ps1')
$python = $resolved.asr_python
$arguments = @('-B','-X','utf8',(Join-Path $PSScriptRoot 'dictionary_merge.py'),'--book',$resolved.dictionary)
if ($Batch) { $arguments += @('--batch',$Batch) }
if ($Find) { $arguments += @('--find',$Find) }
if ($Apply) {
    if (-not $Batch) { throw 'Provide -Batch for an update.' }
    $arguments += @('--apply','--backup-dir',(Join-Path $resolved.application_home 'backups\dictionary'))
}
& $python @arguments
exit $LASTEXITCODE
