<#
.SYNOPSIS
    PROJECT RESILIENCE-ALPHA - Demarrage de la plateforme conteneurisee (up.ps1)
.DESCRIPTION
    1. Verifie/amorce le coffre de secrets SOPS/Age hors depot
    2. Valide la configuration Docker Compose
    3. Demarre l'ensemble des microservices et verifie l'etat de sante
#>
param(
    [string]$BindIp = "127.0.0.1",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $RepoRoot "infra\compose\docker-compose.yml"
$SecretsScript = Join-Path $RepoRoot "scripts\secrets_manager.py"

Write-Host "[RESILIENCE-ALPHA] Preparation du deploiement sur HOST_BIND_IP=$BindIp..." -ForegroundColor Cyan
$env:HOST_BIND_IP = $BindIp

# 1. Verifier/Amorcer les secrets chiffres
python $SecretsScript verify
if ($LASTEXITCODE -ne 0) {
    Write-Host "[RESILIENCE-ALPHA] Amorcage initial du coffre de secrets..." -ForegroundColor Yellow
    python $SecretsScript bootstrap
}

# 2. Valider la syntaxe du fichier Docker Compose
Write-Host "[RESILIENCE-ALPHA] Validation de infra/compose/docker-compose.yml..." -ForegroundColor Cyan
docker compose -f $ComposeFile config -q
if ($LASTEXITCODE -ne 0) {
    throw "Echec de validation de infra/compose/docker-compose.yml"
}

if ($DryRun) {
    Write-Host "[RESILIENCE-ALPHA] Mode DryRun termine avec succes (Configuration valide)." -ForegroundColor Green
    exit 0
}

# 3. Verifier que le demon Docker est actif
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[RESILIENCE-ALPHA] BLOQUE : Le demon Docker Desktop n'est pas demarre sur cet hote." -ForegroundColor Yellow
    Write-Host "Veuillez lancer Docker Desktop puis relancer .\scripts\up.ps1." -ForegroundColor Yellow
    exit 2
}

# 4. Demarrer la stack
Write-Host "[RESILIENCE-ALPHA] Demarrage des conteneurs..." -ForegroundColor Cyan
docker compose -f $ComposeFile up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Erreur lors de l'execution de docker compose up"
}

Write-Host "[RESILIENCE-ALPHA] Plateforme demarree :" -ForegroundColor Green
Write-Host "  - Passerelle WAF & API : http://${BindIp}:8080"
Write-Host "  - Dashboard Frontend   : http://${BindIp}:3000"
Write-Host "  - Grafana Observabilite: http://${BindIp}:3001"
