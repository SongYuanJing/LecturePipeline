param([switch]$Apply)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$cfg=Get-Content -LiteralPath (Join-Path $root 'config\config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($cfg.task_prefix -notmatch '^LP-[a-f0-9]{12}$'){throw 'Invalid candidate task prefix'}
$names=@(($cfg.task_prefix+'-Lecture'),($cfg.task_prefix+'-Dialogue'))
foreach($name in $names){
 $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
 if($task){
  if($task.Actions.Execute -ne (Join-Path $root 'runtime\asr\pythonw.exe')){throw 'Task ownership mismatch'}
  if($task.State -eq 'Running'){throw 'Stop this candidate workers gracefully in GUI before removing integration'}
 }
}
if(-not $Apply){Write-Output 'Verified candidate tasks only; use -Apply to remove.';return}
foreach($name in $names){if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){Unregister-ScheduledTask -TaskName $name -Confirm:$false}}
$shortcut=Join-Path $root 'Lecture Pipeline.lnk';if(Test-Path -LiteralPath $shortcut){Remove-Item -LiteralPath $shortcut}
$marker=Join-Path $root 'logs\integration-applied.json';if(Test-Path -LiteralPath $marker){Remove-Item -LiteralPath $marker}
Write-Output 'Candidate integration removed. User data and config retained.'
