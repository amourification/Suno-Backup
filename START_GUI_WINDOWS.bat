@echo off
title Suno Backup - GUI
echo.
echo  ========================================
echo     Suno Library Backup  (GUI)
echo  ========================================
echo.

where python >nul 2>&1
if %errorlevel% == 0 (
    python setup_and_run.py --gui %*
    if errorlevel 1 pause
    goto end
)
where python3 >nul 2>&1
if %errorlevel% == 0 (
    python3 setup_and_run.py --gui %*
    if errorlevel 1 pause
    goto end
)
echo  ERROR: Python not found. Install from https://python.org
pause
exit /b 1

:end
