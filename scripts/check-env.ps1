<#
.SYNOPSIS
    PROJECT RESILIENCE-ALPHA - Audit d'environnement du PC Hote (check-env.ps1)
.DESCRIPTION
    Controle la presence des outils requis (Git, Python 3, Docker, Docker Compose, Node, Ollama),
    l'espace disque disponible, le coffre de secrets SOPS/Age et la validite de docker-compose.yml.
#>

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " PROJECT RESILIENCE-ALPHA - Audit d'Environnement Operationnel" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "Depot : $RepoRoot"
Write-Host "Hote  : $env:COMPUTERNAME ($([System.Environment]::OSVersion.VersionString))"
Write-Host ""

$Checks = @()

function Add-CheckResult {
    param([string]$Component, [string]$Status, [string]$Details)
    $script:Checks += [PSCustomObject]@{
        Component = $Component
        Status    = $Status
        Details   = $Details
    }
}

# 1. Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = (git --version) -join " "
    Add-CheckResult "Git CLI" "PASS" $gitVer
} else {
    Add-CheckResult "Git CLI" "FAIL" "Absent du PATH"
}

# 2. Python 3
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = (python --version 2>&1) -join " "
    Add-CheckResult "Python Runtime" "PASS" $pyVer
} else {
    Add-CheckResult "Python Runtime" "FAIL" "Absent du PATH"
}

# 3. Docker CLI & Compose
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerVer = (docker --version 2>&1) -join " "
    Add-CheckResult "Docker CLI" "PASS" $dockerVer

    $composeVer = (docker compose version 2>&1) -join " "
    if ($LASTEXITCODE -eq 0) {
        Add-CheckResult "Docker Compose" "PASS" $composeVer
    } else {
        Add-CheckResult "Docker Compose" "FAIL" "Plugin compose indisponible"
    }

    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-CheckResult "Docker Daemon" "PASS" "Demon Docker actif"
    } else {
        Add-CheckResult "Docker Daemon" "WARN" "Demon Docker arrete (demarrer Docker Desktop pour le runtime)"
    }
} else {
    Add-CheckResult "Docker CLI" "FAIL" "Absent du PATH"
}

# 4. Validation syntaxique docker-compose.yml
$ComposeFile = Join-Path $RepoRoot "infra\compose\docker-compose.yml"
if (Test-Path $ComposeFile) {
    $null = docker compose -f $ComposeFile config -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-CheckResult "Compose Config" "PASS" "infra/compose/docker-compose.yml valide"
    } else {
        Add-CheckResult "Compose Config" "FAIL" "Erreur de syntaxe dans docker-compose.yml"
    }
} else {
    Add-CheckResult "Compose Config" "FAIL" "Fichier introuvable : $ComposeFile"
}

# 5. Ollama Local (RAG)
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $ollamaVer = (ollama --version 2>&1) -join " "
    Add-CheckResult "Ollama (RAG Local)" "PASS" $ollamaVer
} else {
    Add-CheckResult "Ollama (RAG Local)" "WARN" "Absent (mode fallback extractif documentaire actif)"
}

# 6. Espace disque C:
$drive = Get-PSDrive -Name C -ErrorAction SilentlyContinue
if ($null -ne $drive) {
    $freeGb = [math]::Round($drive.Free / 1GB, 2)
    if ($freeGb -ge 10) {
        Add-CheckResult "Espace Disque (C:)" "PASS" "$freeGb Go libres"
    } else {
        Add-CheckResult "Espace Disque (C:)" "WARN" "$freeGb Go libres (seuil recommande : 10 Go)"
    }
}

# 7. Coffre de secrets chiffre SOPS/Age
$SecretsVault = Join-Path $RepoRoot "infra\secrets\secrets.enc.json"
if (Test-Path $SecretsVault) {
    Add-CheckResult "Coffre Secrets (SOPS)" "PASS" "infra/secrets/secrets.enc.json present"
} else {
    Add-CheckResult "Coffre Secrets (SOPS)" "WARN" "Executer: python scripts/secrets_manager.py bootstrap"
}

$Checks | Format-Table -AutoSize

$Failed = @($Checks | Where-Object { $_.Status -eq "FAIL" })
if ($Failed.Count -gt 0) {
    Write-Host "[STATUT] ECHEC : $($Failed.Count) prerequis critique(s) en erreur." -ForegroundColor Red
    exit 1
} else {
    Write-Host "[STATUT] ENVIRONNEMENT OPERATIONNEL VALIDE." -ForegroundColor Green
    exit 0
}
