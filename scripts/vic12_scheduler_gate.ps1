param([Parameter(Mandatory=$true)][string]$GateCase,
      [Parameter(Mandatory=$true)][string]$Pythonw)
$ErrorActionPreference='Stop'
$casePath=(Resolve-Path -LiteralPath $GateCase).Path
$tempPath=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
if(-not $casePath.StartsWith($tempPath,[StringComparison]::OrdinalIgnoreCase) -or
   -not (Split-Path (Split-Path $casePath -Parent) -Leaf).StartsWith('LP-vic12-')) {throw 'Not an owned disposable VIC-12 case'}
if(-not (Test-Path -LiteralPath (Join-Path $casePath 'app\config.json'))) {throw 'Missing disposable config'}
$gateScript=Join-Path $PSScriptRoot 'vic12_crash_gate.py'
$taskName='LP-VIC12-'+[guid]::NewGuid().ToString('N')
$argsText='-B -X utf8 "'+$gateScript+'" --child "'+$casePath+'" --action worker --serve'
$action=New-ScheduledTaskAction -Execute $Pythonw -Argument $argsText
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$events=@()
try {
 Register-ScheduledTask -TaskName $taskName -Action $action -Settings $settings -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited | Out-Null
 for($round=1;$round -le 2;$round++) {
  $requested=Get-Date
  Start-ScheduledTask -TaskName $taskName
  $limit=(Get-Date).AddSeconds(25)
  do {
   Start-Sleep -Milliseconds 500
   $statusFiles=Get-ChildItem -LiteralPath (Join-Path $casePath 'data') -Filter worker_status.json -Recurse
   $status=$null
   foreach($file in $statusFiles) {
    try {$candidate=Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
     if([DateTimeOffset]::Parse($candidate.started_at).UtcDateTime -ge $requested.ToUniversalTime().AddSeconds(-1)) {$status=$candidate}
    } catch {}
   }
  } until(($status -and $status.worker -eq 'RUNNING') -or (Get-Date) -ge $limit)
  if(-not $status -or $status.worker -ne 'RUNNING') {throw 'Scheduled worker did not confirm fresh RUNNING'}
  if(($status.lectures.PSObject.Properties.Value | Where-Object status -ne 'DONE').Count) {throw 'Unexpected lecture status'}
  $events+=@{round=$round;started_at=$status.started_at;worker=$status.worker;lectures=$status.lectures}
  Stop-ScheduledTask -TaskName $taskName
  $limit=(Get-Date).AddSeconds(10)
  do {Start-Sleep -Milliseconds 200;$state=(Get-ScheduledTask -TaskName $taskName).State} until($state -ne 'Running' -or (Get-Date) -ge $limit)
  if($state -eq 'Running') {throw 'Disposable worker did not stop'}
  Start-Sleep -Seconds 2
 }
 @{status='PASS';task=$taskName;no_triggers=$true;events=$events} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $casePath 'scheduler-evidence.json') -Encoding utf8
 Write-Output "PASS: two scheduled worker start/stop cycles: $taskName"
} finally {
 if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $taskName
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
 }
}
