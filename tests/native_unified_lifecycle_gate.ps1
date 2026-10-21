param(
    [Parameter(Mandatory=$true)][string]$Candidate,
    [int]$WebCycles = 20,
    [int]$TkCycles = 5
)
$ErrorActionPreference = 'Stop'
$candidateRoot = (Resolve-Path -LiteralPath $Candidate).Path
$root = Join-Path $candidateRoot 'app'
$marker = Get-Content -LiteralPath (Join-Path $candidateRoot 'DEV_CANDIDATE.json') -Raw | ConvertFrom-Json
$current = Get-Content -LiteralPath (Join-Path $root 'current.json') -Raw | ConvertFrom-Json
$code = Join-Path $root $current.path
$release = Get-Content -LiteralPath (Join-Path $code 'release.json') -Raw | ConvertFrom-Json
if ($marker.purpose -ne 'Lecture Pipeline unified DEV' -or
    $marker.install_root -ne $root -or $marker.data_root -ne (Join-Path $candidateRoot 'data') -or
    $release.distribution_status -ne 'dev' -or $WebCycles -lt 1 -or $TkCycles -lt 0) {
    throw 'This gate requires an isolated unified DEV candidate'
}
$shellPath = Join-Path $code 'gui_web\native\LecturePipelineDesktop.exe'
$pythonPath = Join-Path $root 'runtime\asr\pythonw.exe'
$webShortcut = Join-Path $root 'Lecture Pipeline DEV.vbs'
$tkShortcut = Join-Path $root 'Lecture Pipeline (Tk).vbs'
foreach ($path in @($shellPath, $pythonPath, $webShortcut, $tkShortcut)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing DEV entry: $path" }
}
$prefix = (Get-Content -LiteralPath (Join-Path $root 'config\config.json') -Raw | ConvertFrom-Json).task_prefix
if ($prefix -notlike 'LP-*') { throw 'Invalid DEV task prefix' }
$tasksBefore = @(Get-ScheduledTask | Where-Object TaskName -Like "$prefix*").Count
$dataRoot = Join-Path $candidateRoot 'data'
function DataHashes {
    @((Get-ChildItem -LiteralPath $dataRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
        "$($_.FullName.Substring($dataRoot.Length))=$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
    }))
}
$hashesBefore = DataHashes
function CandidateProcesses {
    @(Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq 'LecturePipelineDesktop.exe' -and $_.ExecutablePath -eq $shellPath) -or
        ($_.Name -eq 'pythonw.exe' -and $_.ExecutablePath -eq $pythonPath -and
         $_.CommandLine.Contains((Join-Path $root 'launcher\launch.py')))
    })
}
function Dashboard {
    $all = @(CandidateProcesses)
    $shell = @($all | Where-Object Name -EQ 'LecturePipelineDesktop.exe')
    $hosts = @($all | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine.EndsWith(' dashboard') })
    $ports = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -eq '127.0.0.1' -and $hosts.ProcessId -contains $_.OwningProcess })
    @{shell=$shell; hosts=$hosts; ports=$ports}
}
function Until([scriptblock]$condition, [int]$seconds=15) {
    $limit = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $limit) {
        if (& $condition) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}
function OpenShortcut([string]$path) {
    Start-Process -FilePath (Join-Path $env:WINDIR 'System32\wscript.exe') `
        -ArgumentList ('"' + $path + '"') -WindowStyle Hidden | Out-Null
}
if (@(CandidateProcesses).Count -ne 0) { throw 'Close existing DEV GUI processes before this gate' }
$results = @()
for ($i=1; $i -le $WebCycles; $i++) {
    OpenShortcut $webShortcut
    if (-not (Until { $d=Dashboard; $d.shell.Count -eq 1 -and $d.hosts.Count -eq 1 -and $d.ports.Count -eq 1 })) {
        throw "WebView2 did not open cleanly at cycle $i"
    }
    $d = Dashboard
    $port = $d.ports[0].LocalPort
    $shellPid = $d.shell[0].ProcessId
    $hostPid = $d.hosts[0].ProcessId
    if ($i -eq 1) {
        OpenShortcut $webShortcut
        Start-Sleep -Seconds 3
        $double = Dashboard
        if ($double.shell.Count -ne 1 -or $double.hosts.Count -ne 1 -or $double.ports.Count -ne 1 -or
            $double.shell[0].ProcessId -ne $shellPid -or $double.ports[0].LocalPort -ne $port) {
            throw 'Second launch created another DEV dashboard process or port'
        }
    }
    if ($i -eq [math]::Max(2, [math]::Floor($WebCycles / 2))) {
        $process = Get-Process -Id $shellPid
        if ($process.Path -ne $shellPath) { throw 'Refusing to kill an unexpected process' }
        Stop-Process -Id $shellPid -Force
        $mode = 'crash'
    } else {
        $process = Get-Process -Id $shellPid
        if ($process.Path -ne $shellPath -or -not $process.CloseMainWindow()) {
            throw 'DEV dashboard refused normal close'
        }
        $mode = 'close'
    }
    if (-not (Until { $d=Dashboard; $d.shell.Count -eq 0 -and $d.hosts.Count -eq 0 -and $d.ports.Count -eq 0 })) {
        throw "DEV dashboard process/port remained after $mode at cycle $i"
    }
    if (@(Get-ChildItem -LiteralPath (Join-Path $root 'run\sessions') -Filter '*.lock').Count -ne 0) {
        throw "DEV GUI session lock remained after cycle $i"
    }
    $results += [pscustomobject]@{cycle=$i; mode=$mode; shell_pid=$shellPid; host_pid=$hostPid; port=$port}
}
$tkResults = @()
for ($i=1; $i -le $TkCycles; $i++) {
    OpenShortcut $tkShortcut
    if (-not (Until {
        $all = @(CandidateProcesses)
        $opened = @($all | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine.EndsWith(' gui') })
        $opened.Count -eq 1 -and (Get-Process -Id $opened[0].ProcessId).MainWindowHandle -ne 0
    })) { throw "Tk did not open at cycle $i" }
    $tk = @(CandidateProcesses | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine.EndsWith(' gui') })[0]
    $process = Get-Process -Id $tk.ProcessId
    if ($process.Path -ne $pythonPath -or -not $process.CloseMainWindow()) {
        throw "Tk did not close normally at cycle $i"
    }
    if (-not (Until {
        @((CandidateProcesses) | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine.EndsWith(' gui') }).Count -eq 0
    })) { throw "Tk process remained after cycle $i" }
    $tkResults += [pscustomobject]@{cycle=$i; pid=$tk.ProcessId}
}
$tasksAfter = @(Get-ScheduledTask | Where-Object TaskName -Like "$prefix*").Count
$hashesAfter = DataHashes
if ($tasksAfter -ne $tasksBefore -or (Compare-Object $hashesBefore $hashesAfter)) {
    throw 'DEV task count or user data changed during GUI lifecycle gate'
}
[pscustomobject]@{
    candidate=$candidateRoot; version=$current.app_version; web_cycles=$WebCycles; tk_cycles=$TkCycles
    double_launch='single instance'; crash_recovery='passed'; ports_released='all'; sessions_released='all'
    data_files=$hashesBefore.Count; data_hashes_unchanged=$true; dev_tasks=$tasksAfter
    web=$results; tk=$tkResults
} | ConvertTo-Json -Depth 5
