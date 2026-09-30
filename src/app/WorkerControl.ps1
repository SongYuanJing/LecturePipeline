param([ValidateSet('Install','Start','Stop','ForceStop','Status','Uninstall')][string]$Action='Status')
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
. (Join-Path $PSScriptRoot 'Config.ps1')
$workerHome=$resolved.worker_home
$taskName = $resolved.tasks.lecture
$stopFile = Join-Path $workerHome 'worker.stop'
if($Action -in @('Install','Start')) {
    & $resolved.asr_python -B -X utf8 (Join-Path $base 'pipeline_config.py') | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Preflight failed. Run pipeline_config.py for details; worker not started.'}
}
switch ($Action) {
    'Install' {
        if($bootstrap.application_home){throw 'Use packaged Integrate.ps1 to register isolated tasks'}
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Task already exists; use Start or Uninstall first.' }
        $python = Join-Path (Split-Path $resolved.asr_python) 'pythonw.exe'
        if (-not (Test-Path -LiteralPath $python)) { throw 'pythonw.exe not found' }
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $taskAction = New-ScheduledTaskAction -Execute $python -Argument ('-X utf8 "' + (Join-Path $base 'lecture_worker.py') + '"') -WorkingDirectory $base
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
        $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
        Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'Local lecture worker; remote READY folders via Drive. No sleep/power changes.' | Out-Null
        if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
        Start-ScheduledTask -TaskName $taskName
    }
    'Start' {
        if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
        Enable-ScheduledTask -TaskName $taskName | Out-Null
        Start-ScheduledTask -TaskName $taskName
    }
    'Stop' {
        Disable-ScheduledTask -TaskName $taskName | Out-Null
        Set-Content -LiteralPath $stopFile -Value 'Stop after current lecture' -Encoding ascii
        Write-Output 'Stop requested. Current lecture finishes safely; then worker exits. Autostart disabled.'
    }
    'ForceStop' {
        Disable-ScheduledTask -TaskName $taskName | Out-Null
        Set-Content -LiteralPath $stopFile -Value 'Forced stop' -Encoding ascii
        Stop-ScheduledTask -TaskName $taskName
        Write-Output 'Worker terminated. Interrupted work will recover when Start is used.'
    }
    'Status' {
        Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
        Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime,LastTaskResult,NextRunTime
        if (Test-Path -LiteralPath (Join-Path $workerHome 'worker_status.json')) { Get-Content -LiteralPath (Join-Path $workerHome 'worker_status.json') -Encoding UTF8 }
    }
    'Uninstall' {
        Set-Content -LiteralPath $stopFile -Value 'Uninstalled' -Encoding ascii
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $taskName
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }
        Write-Output 'Autostart removed. Pipeline, journal, backup and all lecture files retained.'
    }
}
