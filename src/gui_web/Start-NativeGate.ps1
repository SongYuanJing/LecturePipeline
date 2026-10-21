param(
    [string]$Url = 'http://127.0.0.1:8769',
    [string]$SdkDirectory,
    [string]$Output,
    [switch]$BuildOnly
)
$ErrorActionPreference = 'Stop'
$uri = [Uri]$Url
if ($uri.Scheme -ne 'http' -or $uri.Host -ne '127.0.0.1') { throw 'Native gate accepts only 127.0.0.1 HTTP.' }
$tree = Split-Path (Split-Path $PSScriptRoot)
$ownedRoot = Join-Path $tree '.local\vic28-native-gate'
$bin = Join-Path $ownedRoot 'bin'
if (-not $Output) { $Output = Join-Path $ownedRoot 'evidence' }
# This is a DEV gate, not the product dependency-discovery policy. No download/install.
if (-not $SdkDirectory) {
    $candidate = Join-Path $env:ProgramFiles 'Microsoft Office\root\Office16\ADDINS\Microsoft Power Query for Excel Integrated\bin'
    if (Test-Path -LiteralPath (Join-Path $candidate 'Microsoft.Web.WebView2.WinForms.dll')) { $SdkDirectory = $candidate }
}
if (-not $SdkDirectory) { throw 'Existing WebView2 SDK assemblies not found. Pass -SdkDirectory. Nothing will be downloaded.' }
$names = @('Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll')
foreach ($name in $names) { if (-not (Test-Path -LiteralPath (Join-Path $SdkDirectory $name) -PathType Leaf)) { throw "Missing existing component: $name" } }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Existing Framework C# compiler not found. No SDK will be installed.' }
New-Item -ItemType Directory -Path $bin -Force | Out-Null
foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $SdkDirectory $name) -Destination (Join-Path $bin $name) -Force }
$source = Join-Path $PSScriptRoot 'native_gate'
$exe = Join-Path $bin 'NativeGate.exe'
& $compiler /nologo /target:winexe /platform:x64 ("/out:" + $exe) ("/win32manifest:" + (Join-Path $source 'NativeGate.manifest')) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ("/reference:" + (Join-Path $bin $names[0])) ("/reference:" + (Join-Path $bin $names[1])) (Join-Path $source 'NativeGate.cs')
if ($LASTEXITCODE -ne 0) { throw 'Native gate compilation failed' }
Copy-Item -LiteralPath (Join-Path $source 'NativeGate.exe.config') -Destination ($exe + '.config') -Force
$provenance = foreach ($name in $names) { $item=Get-Item -LiteralPath (Join-Path $SdkDirectory $name); [pscustomobject]@{ file=$name; source=$item.FullName; version=$item.VersionInfo.FileVersion; sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash } }
$provenance | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ownedRoot 'components.json') -Encoding UTF8
Write-Output "Built: $exe"
Write-Output "Evidence: $Output"
if (-not $BuildOnly) {
    # Deliberately visible: this is the interactive native window requested for visual acceptance.
    Start-Process -FilePath $exe -ArgumentList ('"' + $Url + '" "' + $Output + '" "' + (Join-Path $ownedRoot 'profile') + '"')
}
