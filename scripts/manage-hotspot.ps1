<#
.SYNOPSIS
    Gestionnaire du Point d'Accès Mobile Windows RESILIENCE-G2 (192.168.137.1)
.DESCRIPTION
    Permet de vérifier, démarrer ou arrêter le point d'accès sans fil mobile
    exigé pour le PC Attaquant dans le cadre du Workshop PROJECT RESILIENCE-ALPHA.
.PARAMETER Action
    status | start | stop
#>
[CmdletBinding()]
param(
    [ValidateSet("status", "start", "stop")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await-AsyncOperation($asyncOp, $resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($asyncOp))
    $task.Wait(15000) | Out-Null
    return $task.Result
}

[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime] | Out-Null

$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if (-not $profile) {
    Write-Error "Aucun profil de connexion Internet actif détecté pour partager le réseau."
    exit 1
}

$mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$config = $mgr.GetCurrentAccessPointConfiguration()

switch ($Action) {
    "start" {
        if ($mgr.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On) {
            Write-Host "[HOTSPOT] Déjà actif sur SSID: $($config.Ssid)" -ForegroundColor Green
        } else {
            Write-Host "[HOTSPOT] Démarrage du point d'accès mobile..." -ForegroundColor Cyan
            $opResult = Await-AsyncOperation ($mgr.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            if ($opResult.Status -ne "Success") {
                Write-Error "[HOTSPOT] Échec du démarrage: $($opResult.Status)"
                exit 1
            }
            Start-Sleep -Seconds 2
        }
    }
    "stop" {
        if ($mgr.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On) {
            Write-Host "[HOTSPOT] Arrêt du point d'accès mobile..." -ForegroundColor Yellow
            $opResult = Await-AsyncOperation ($mgr.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            Write-Host "[HOTSPOT] Statut arrêt: $($opResult.Status)" -ForegroundColor Green
        } else {
            Write-Host "[HOTSPOT] Le point d'accès est déjà inactif." -ForegroundColor Gray
        }
    }
    "status" {
        # Simple affichage
    }
}

$ipObj = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -like "192.168.137.*" } | Select-Object -First 1

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " POINT D'ACCES SANS FIL MOBILE - GROUPE 2 (G2)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Etat actuel      : $($mgr.TetheringOperationalState)" -ForegroundColor $(if ($mgr.TetheringOperationalState -eq 'On') { 'Green' } else { 'Yellow' })
Write-Host "SSID (Reseau)    : $($config.Ssid)"
Write-Host "Cle de securite  : $($config.Passphrase)"
Write-Host "Clients connectes: $($mgr.ClientCount)"
if ($ipObj) {
    Write-Host "Adresse IP Hote  : $($ipObj.IPAddress)/$($ipObj.PrefixLength) (Interface: $($ipObj.InterfaceAlias))" -ForegroundColor Green
} else {
    Write-Host "Adresse IP Hote  : Non assignee (Point d'acces inactif)" -ForegroundColor Red
}
Write-Host "==================================================" -ForegroundColor Cyan
