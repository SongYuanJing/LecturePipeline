@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Dashboard.ps1" -VisualFixture -Port 8769 %*
if errorlevel 1 pause
