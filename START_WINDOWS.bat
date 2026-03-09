@echo off
title Suno Backup Tool
echo.
echo  ========================================
echo        Suno Library Backup Tool
echo  ========================================
echo.

where python >nul 2>&1
if %errorlevel% == 0 (
    python setup_and_run.py %*
    goto end
)

where python3 >nul 2>&1
if %errorlevel% == 0 (
    python3 setup_and_run.py %*
    goto end
)

echo  ERROR: Python not found. Please install Python 3.9+ from https://python.org
echo  Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:end
pause
