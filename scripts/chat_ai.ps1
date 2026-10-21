<#
.SYNOPSIS
    Lance la console interactive de dialogue en direct avec l'IA Superviseur (Ollama gemma4:e4b).
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\chat_ai.ps1
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host "Initialisation du dialogue avec l'IA Superviseur en cours..." -ForegroundColor Cyan
python scripts\chat_ai.py
