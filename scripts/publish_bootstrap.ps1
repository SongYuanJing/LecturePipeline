param([string]$Python='python',[string]$Dotnet='dotnet',[string]$Output,
      [string]$Version,[string]$DesktopBin)
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot
if(-not $Output){$Output=Join-Path $repo 'dist/bootstrap'}
$env:DOTNET_CLI_TELEMETRY_OPTOUT='1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE='false'
$payloadArgs=@()
if($Version){$payloadArgs+=@('--version',$Version)}
if($DesktopBin){$payloadArgs+=@('--desktop-bin',$DesktopBin)}
& $Python -B (Join-Path $PSScriptRoot 'build_bootstrap_payload.py') @payloadArgs
if($LASTEXITCODE -ne 0){throw 'Payload build failed'}
$appVersion=(Get-Content -LiteralPath (Join-Path $repo 'bootstrap/payload/application.json') -Raw | ConvertFrom-Json).app_version
Push-Location (Join-Path $repo 'bootstrap')
try {
 & $Dotnet publish Setup.csproj -c Release -o $Output "-p:Version=$appVersion" "-p:InformationalVersion=$appVersion"
 if($LASTEXITCODE -ne 0){throw 'Self-contained publish failed'}
} finally {Pop-Location}
$exe=Join-Path $Output 'Setup.exe'
$notices=Join-Path $Output 'notices'
New-Item -ItemType Directory -Force -Path $notices | Out-Null
Get-ChildItem -LiteralPath (Join-Path $repo 'bootstrap/notices') -File | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $notices $_.Name) -Force }
@{bytes=(Get-Item -LiteralPath $exe).Length;sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Output 'Setup.sha256.json') -Encoding utf8
