param([ValidateSet('Install','Start','Stop','ForceStop','Status','Uninstall','Retry','Language')][string]$Action='Status',[string]$File,[ValidateSet('auto','zh','en')][string]$Language='auto',[string]$Job)
$ErrorActionPreference='Stop'
$base=$PSScriptRoot
$taskName=$null
. (Join-Path $PSScriptRoot 'Config.ps1')
$taskName=$resolved.tasks.dialogue
$config=$resolved.dialogue
$dialogueHome=$config.home
$stopFile=Join-Path $dialogueHome 'stop'
if($Action -in @('Install','Start')) {
 & $resolved.asr_python -B -X utf8 (Join-Path $base 'pipeline_config.py') | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Preflight failed. Run pipeline_config.py for details; worker not started.'}
}
switch($Action) {
 'Install' {
  if($bootstrap.application_home){throw 'Use packaged Integrate.ps1 to register isolated tasks'}
  if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Dialogue task already exists'}
  $identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $taskAction=New-ScheduledTaskAction -Execute (Join-Path (Split-Path $resolved.asr_python) 'pythonw.exe') -Argument ('-B -X utf8 "'+(Join-Path $base 'dialogue_v1.6\dialogue_worker.py')+'" --config "'+(Join-Path $base 'dialogue_v1.6\config.json')+'"') -WorkingDirectory $base
  $trigger=New-ScheduledTaskTrigger -AtLogOn -User $identity
  $principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
  $settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
  Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'Separate local Dialogue Quick worker; no lecture state or READY.' | Out-Null
  if(Test-Path -LiteralPath $stopFile){Remove-Item -LiteralPath $stopFile}
  Start-ScheduledTask -TaskName $taskName
 }
 'Start' {if(Test-Path -LiteralPath $stopFile){Remove-Item -LiteralPath $stopFile};Enable-ScheduledTask -TaskName $taskName | Out-Null;Start-ScheduledTask -TaskName $taskName}
 'Stop' {Disable-ScheduledTask -TaskName $taskName | Out-Null;Set-Content -LiteralPath $stopFile -Value 'Stop after current dialogue';Write-Output 'Dialogue stops after current job; lecture worker unchanged.'}
 'ForceStop' {Disable-ScheduledTask -TaskName $taskName | Out-Null;Set-Content -LiteralPath $stopFile -Value 'Forced';Stop-ScheduledTask -TaskName $taskName}
 'Status' {Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State;Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime,LastTaskResult;if(Test-Path -LiteralPath (Join-Path $dialogueHome 'status.json')){Get-Content -LiteralPath (Join-Path $dialogueHome 'status.json') -Encoding UTF8}}
 'Uninstall' {Set-Content -LiteralPath $stopFile -Value 'Uninstalled';if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){Stop-ScheduledTask -TaskName $taskName;Unregister-ScheduledTask -TaskName $taskName -Confirm:$false};Write-Output 'Dialogue autostart removed; all audio, results and state retained.'}
 'Retry' {if(-not $Job){throw 'Supply -Job ID from dialogue_state.json'};& $resolved.asr_python -B -X utf8 (Join-Path $base 'dialogue_v1.6\dialogue_manage.py') --config (Join-Path $base 'dialogue_v1.6\config.json') retry --job $Job;if($LASTEXITCODE){throw 'Retry failed. Stop Dialogue worker first.'}}
 'Language' {if(-not $File){throw 'Supply the ordinary audio filename with -File'};& $resolved.asr_python -B -X utf8 (Join-Path $base 'dialogue_v1.6\dialogue_manage.py') --config (Join-Path $base 'dialogue_v1.6\config.json') language --file $File --language $Language;if($LASTEXITCODE){throw 'Language update failed'}}
}

