<#
.SYNOPSIS
    PROJECT RESILIENCE-ALPHA - Arret propre de la plateforme (down.ps1)
.DESCRIPTION
    Arrete et supprime les conteneurs de la plateforme tout en preservant
    par defaut les volumes de donnees transactionnelles et d'audit.
#>
param(
    [switch]$PurgeVolumes
)

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $RepoRoot "infra\compose\docker-compose.yml"

Write-Host "[RESILIENCE-ALPHA] Arret controle de la plateforme..." -ForegroundColor Cyan

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[RESILIENCE-ALPHA] Demon Docker inactif - aucun conteneur actif a arreter." -ForegroundColor Yellow
    exit 0
}

if ($PurgeVolumes) {
    Write-Host "[RESILIENCE-ALPHA] Arret avec purge des volumes (-v)..." -ForegroundColor Yellow
    docker compose -f $ComposeFile down -v --remove-orphans
} else {
    docker compose -f $ComposeFile down --remove-orphans
}

$EnvFile = Join-Path $RepoRoot "infra\compose\.env"
if (Test-Path $EnvFile) {
    Remove-Item $EnvFile -Force -ErrorAction SilentlyContinue
}

Write-Host "[RESILIENCE-ALPHA] Plateforme arretee proprement." -ForegroundColor Green
exit 0
