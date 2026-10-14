# Harmoniq Music Curator - PowerShell Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Harmoniq Music Curator - PowerShell Launcher" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

python main.py
