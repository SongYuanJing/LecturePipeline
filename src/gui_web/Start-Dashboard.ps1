param(
    [string]$DevRoot = 'C:\PipLine GPT WORK',
    [string]$Config,
    [string]$Python,
    [int]$Port = 8768,
    [switch]$VisualFixture,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = Join-Path $DevRoot 'app\runtime\document\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'DEV Python not found. Specify -Python <existing-python.exe>. No runtime will be downloaded or copied.'
}
$taskArguments = @('-B', (Join-Path $PSScriptRoot 'readonly_host.py'), '--dev-root', $DevRoot, '--port', $Port)
if ($Config) { $taskArguments += @('--config', $Config) }
if ($VisualFixture) { $taskArguments += '--visual-fixture' }
if (-not $NoBrowser) { $taskArguments += '--open' }
& $Python @taskArguments
exit $LASTEXITCODE
