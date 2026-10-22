param(
    [Parameter(Mandatory)][string]$SdkDirectory,
    [Parameter(Mandatory)][string]$Output,
    [ValidateSet('dev','beta')][string]$DistributionStatus='dev'
)
$ErrorActionPreference = 'Stop'
$source = Join-Path (Split-Path $PSScriptRoot) 'src\gui_web\desktop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) { throw 'Existing .NET Framework compiler is unavailable' }
if (Test-Path -LiteralPath $Output) { throw 'Use a new desktop build directory' }
$names = @('Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll')
foreach ($name in $names) {
    if (-not (Test-Path -LiteralPath (Join-Path $SdkDirectory $name) -PathType Leaf)) { throw "Missing WebView2 component: $name" }
}
New-Item -ItemType Directory -Path $Output | Out-Null
foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $SdkDirectory $name) -Destination (Join-Path $Output $name) }
foreach ($name in @('LecturePipeline-A-dark.ico', 'LecturePipeline-A-light.ico')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $Output $name)
}
$exe = Join-Path $Output 'LecturePipelineDesktop.exe'
$defines = @()
if ($DistributionStatus -eq 'beta') { $defines += '/define:LP_PRODUCT' }
& $compiler /nologo /target:winexe /platform:x64 @defines ("/out:" + $exe) ("/win32manifest:" + (Join-Path $source 'DesktopShell.manifest')) ("/win32icon:" + (Join-Path $source 'LecturePipeline-A-dark.ico')) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll ("/reference:" + (Join-Path $Output $names[0])) ("/reference:" + (Join-Path $Output $names[1])) (Join-Path $source 'DesktopShell.cs')
if ($LASTEXITCODE -ne 0) { throw 'WebView2 desktop compilation failed' }
Copy-Item -LiteralPath (Join-Path $source 'DesktopShell.exe.config') -Destination ($exe + '.config')
$files = Get-ChildItem -LiteralPath $Output -File | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{ name = $_.Name; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); bytes = $_.Length }
}
$files | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Output 'desktop-components.json') -Encoding UTF8
Write-Output $exe
