$configPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$portableConfig=Join-Path (Split-Path (Split-Path $PSScriptRoot)) 'config\config.json'
$configPath=if($env:LECTURE_CONFIG){$env:LECTURE_CONFIG}elseif(Test-Path -LiteralPath $portableConfig){$portableConfig}else{Join-Path $PSScriptRoot 'config.json'}
$env:LECTURE_CONFIG=$configPath
$bootstrap=Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$installPath=if([IO.Path]::IsPathRooted($bootstrap.install_root)){$bootstrap.install_root}else{[IO.Path]::GetFullPath((Join-Path (Split-Path $configPath) $bootstrap.install_root))}
if($bootstrap.runtimes.asr_python){$configPython=$bootstrap.runtimes.asr_python}
$applicationHome=if($bootstrap.application_home){[IO.Path]::GetFullPath((Join-Path (Split-Path $configPath) $bootstrap.application_home))}else{$installPath}
if(-not [IO.Path]::IsPathRooted($configPython)){$configPython=Join-Path $applicationHome $configPython}
$resolved=& $configPython -B -X utf8 (Join-Path $PSScriptRoot 'pipeline_config.py') --config $configPath --resolve
if($LASTEXITCODE -ne 0){throw 'Configuration invalid; processing not started'}
$resolved=$resolved | ConvertFrom-Json
