@echo off
title Harmoniq Music Curator
cd /d "%~dp0"

echo ===================================================
echo   Harmoniq Music Curator - Windows Launcher
echo ===================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

python main.py
if %errorlevel% neq 0 (
    echo [INFO] Exited.
    pause
)
