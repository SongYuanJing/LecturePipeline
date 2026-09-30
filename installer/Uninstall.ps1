param([switch]$Apply)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot))
if(Test-Path -LiteralPath (Join-Path $root 'logs\integration-applied.json')){throw 'Run RemoveIntegration.ps1 first. Workers must be stopped.'}
$manifest=Get-Content -LiteralPath (Join-Path $root 'package-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$targets=@()
$entries=@('Setup.cmd','Preflight.cmd','ImportModel.cmd','ImportPyAV.cmd','ImportCTranslate2.cmd','ImportCUDA.cmd','Components.cmd','Integrate.cmd','Uninstall.cmd','Lecture Pipeline.vbs','current.json','README.md','PACKAGING.md','CHANGELOG.md','THIRD_PARTY_NOTICES.md','ARCHITECTURE.md','DEVELOPMENT_PLAYBOOK.md')
foreach($prop in $manifest.files.PSObject.Properties){
 $relative=$prop.Name
 $path=[IO.Path]::GetFullPath((Join-Path $root $relative))
 $first=($relative -split '[/\\]')[0]
 if(-not $path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or (($first -notin @('versions','launcher','runtime','third_party','docs')) -and ($relative -notin $entries))){throw ('Unsafe uninstall path: '+$relative)}
 $ancestor=Split-Path $path
 while($ancestor -and $ancestor.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)){
  if((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Uninstall refuses reparse-point directories'}
  $ancestor=Split-Path $ancestor
 }
 if(Test-Path -LiteralPath $path){
  $item=Get-Item -LiteralPath $path
  if($item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw ('Not a regular owned file: '+$relative)}
  $stream=[IO.File]::OpenRead($path)
  try{$hasher=[Security.Cryptography.SHA256]::Create();$hash=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$stream.Dispose();$hasher.Dispose()}
  if($hash -ne $prop.Value){throw ('Changed app file: '+$relative)}
  $targets+=,$path
 }
}
if($Apply){foreach($path in $targets){Remove-Item -LiteralPath $path -Force}}
[pscustomobject]@{Files=$targets.Count;Removed=[bool]$Apply;Preserved='config, models, optional CUDA, logs, run, backups, external data, package manifest; empty directories'} | ConvertTo-Json
