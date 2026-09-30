param([switch]$Apply)
$ErrorActionPreference='Stop'
function Test-ExpectedTask($existing,$execute,$arguments,$directory) {
 $actions=@($existing.Actions)
 return ($actions.Count -eq 1 -and $actions[0].Execute -eq $execute -and $actions[0].Arguments -ceq $arguments -and $actions[0].WorkingDirectory -eq $directory)
}
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$root=Split-Path $PSScriptRoot
$cfg=Get-Content -LiteralPath (Join-Path $root 'config\config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($cfg.task_prefix -notmatch '^LP-[a-f0-9]{12}$'){throw 'Invalid candidate task prefix'}
$python=Join-Path $root 'runtime\asr\python.exe'
& $python -B -X utf8 (Join-Path $root 'launcher\launch.py') preflight
if($LASTEXITCODE -ne 0){throw 'Preflight failed; no Windows integration created'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$tasks=@(@{name=($cfg.task_prefix+'-Lecture');mode='lecture'},@{name=($cfg.task_prefix+'-Dialogue');mode='dialogue'})
$plan=@{tasks=$tasks;execute=(Join-Path $root 'runtime\asr\pythonw.exe');launcher=(Join-Path $root 'launcher\launch.py');working_directory=$root;user=$identity;shortcut=(Join-Path $root 'Lecture Pipeline.lnk')}
$plan | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'logs\integration-plan.json') -Encoding UTF8
if(-not $Apply){Write-Output 'Plan only. Use -Apply explicitly after reviewing logs\integration-plan.json.';return}
$missing=@()
foreach($task in $tasks){
 $expectedArguments='-B -X utf8 "'+$plan.launcher+'" '+$task.mode
 $existing=Get-ScheduledTask -TaskName $task.name -ErrorAction SilentlyContinue
 if($existing){
  if(-not (Test-ExpectedTask $existing $plan.execute $expectedArguments $root)){throw ('Task conflict; unchanged: '+$task.name)}
 } else {$missing+=$task}
}
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($plan.shortcut)
$shortcutArguments='-B -X utf8 "'+$plan.launcher+'" gui'
if((Test-Path -LiteralPath $plan.shortcut) -and ($shortcut.TargetPath -ne $plan.execute -or $shortcut.Arguments -cne $shortcutArguments -or $shortcut.WorkingDirectory -ne $root)){throw 'Shortcut conflict; unchanged'}
$registered=@()
try {
 foreach($task in $missing){
  $action=New-ScheduledTaskAction -Execute $plan.execute -Argument ('-B -X utf8 "'+$plan.launcher+'" '+$task.mode) -WorkingDirectory $root
  $trigger=New-ScheduledTaskTrigger -AtLogOn -User $identity
  $principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
  $settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
  Register-ScheduledTask -TaskName $task.name -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
  $registered+=$task.name
 }
 if(-not (Test-Path -LiteralPath $plan.shortcut)){$shortcut.TargetPath=$plan.execute;$shortcut.Arguments=$shortcutArguments;$shortcut.WorkingDirectory=$root;$shortcut.Save()}; '{}' | Set-Content -LiteralPath (Join-Path $root 'logs\integration-applied.json') -Encoding UTF8
} catch {
 foreach($name in $registered){Unregister-ScheduledTask -TaskName $name -Confirm:$false}
 throw
}
Write-Output 'Isolated tasks and shortcut verified/created. Start workers explicitly from GUI; no other tasks replaced.'
