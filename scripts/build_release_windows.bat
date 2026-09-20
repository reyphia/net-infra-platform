@echo off
REM Double-click-friendly wrapper around build_release_windows.ps1 -- avoids
REM users having to fight PowerShell's default execution policy just to run
REM a build script.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_release_windows.ps1" %*
pause
