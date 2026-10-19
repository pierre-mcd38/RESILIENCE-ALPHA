# ==============================================================================
# PROJECT RESILIENCE-ALPHA — Déblocage Pare-feu Windows & Réseau Hotspot (scripts/fix_firewall_hotspot.ps1)
# ==============================================================================

# Vérification des droits administrateur
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[INFO] Relance avec élévation Administrateur (UAC)..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit 0
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  DÉBLOCAGE PARE-FEU WINDOWS & HOTSPOT GROUPE 2   " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Autoriser explicitement les ports 8080, 3000 et 3001
Write-Host "[1/3] Configuration des règles entrantes Pare-feu pour 8080, 3000 et 3001..." -ForegroundColor White
netsh advfirewall firewall delete rule name="Resilience-Alpha WAF 8080" 2>$null | Out-Null
netsh advfirewall firewall add rule name="Resilience-Alpha WAF 8080" dir=in action=allow protocol=TCP localport=8080 profile=any | Out-Null

netsh advfirewall firewall delete rule name="Resilience-Alpha UI 3000" 2>$null | Out-Null
netsh advfirewall firewall add rule name="Resilience-Alpha UI 3000" dir=in action=allow protocol=TCP localport=3000 profile=any | Out-Null

netsh advfirewall firewall delete rule name="Resilience-Alpha Grafana 3001" 2>$null | Out-Null
netsh advfirewall firewall add rule name="Resilience-Alpha Grafana 3001" dir=in action=allow protocol=TCP localport=3001 profile=any | Out-Null

# 2. Remplacer les règles Python "Bloquer" par "Autoriser"
Write-Host "[2/3] Déblocage des règles Python sur profil Public..." -ForegroundColor White
netsh advfirewall firewall set rule name="Python" new action=allow 2>$null | Out-Null

# 3. Vérification de l'état du hotspot et de NordVPN
Write-Host "[3/3] Diagnostic réseau..." -ForegroundColor White
$nordRunning = Get-Process -Name "*nord*" -ErrorAction SilentlyContinue
if ($nordRunning) {
    Write-Host ""
    Write-Host "⚠️  ATTENTION : NordVPN est actuellement actif !" -ForegroundColor Yellow
    Write-Host "   NordVPN active par défaut la fonction 'Invisibilité sur le réseau local' (LAN)," -ForegroundColor Yellow
    Write-Host "   ce qui empêche le 2e PC de joindre 192.168.137.1." -ForegroundColor Yellow
    Write-Host "   👉 CONSEIL : Mettez NordVPN en pause (Pause / Disconnect) le temps de la démonstration." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Pare-feu débloqué avec succès pour le 2e PC !" -ForegroundColor Green
Write-Host "   Sur le 2e PC, accédez à : http://192.168.137.1:8080/attacker" -ForegroundColor Cyan
Write-Host "   (N'oubliez pas d'écrire bien 'http://' et non 'https://')" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan
Start-Sleep -Seconds 5
