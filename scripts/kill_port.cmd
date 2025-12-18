@echo off
setlocal enabledelayedexpansion

REM Usage:
REM   scripts\kill_port.cmd 8000

set PORT=%1
if "%PORT%"=="" (
  echo Usage: scripts\kill_port.cmd ^<port^>
  exit /b 1
)

echo [*] Finding processes on port %PORT%...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
  echo [*] Killing PID %%p on port %PORT%...
  taskkill /PID %%p /F >nul 2>&1
)

echo [*] Done.


