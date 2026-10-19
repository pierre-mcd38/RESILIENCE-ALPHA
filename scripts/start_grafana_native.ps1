# ==============================================================================
# PROJECT RESILIENCE-ALPHA — Démarrage Natif Windows de Prometheus + Grafana OSS
# Permet d'exécuter le vrai serveur Grafana (port 3001) et Prometheus (port 9090)
# directement sous Windows lorsque le moteur Linux Docker Desktop / WSL est absent.
# ==============================================================================
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ObsBaseDir = Join-Path $env:LOCALAPPDATA "resilience-alpha-obs"
$PromVersion = "2.54.1"
$GrafanaVersion = "11.2.0"

New-Item -ItemType Directory -Force -Path $ObsBaseDir | Out-Null

$PromZip = Join-Path $ObsBaseDir "prometheus-$PromVersion.zip"
$PromExtractDir = Join-Path $ObsBaseDir "prometheus-$PromVersion.windows-amd64"
$PromExe = Join-Path $PromExtractDir "prometheus.exe"

$GrafanaZip = Join-Path $ObsBaseDir "grafana-$GrafanaVersion.zip"
$GrafanaExtractDir = Join-Path $ObsBaseDir "grafana-v$GrafanaVersion"
$GrafanaExe = Join-Path $GrafanaExtractDir "bin\grafana-server.exe"

Write-Host "[1/4] Vérification des binaires officiels Prometheus v$PromVersion et Grafana v$GrafanaVersion..." -ForegroundColor Cyan

if (-not (Test-Path $PromExe)) {
    Write-Host "  -> Téléchargement de Prometheus v$PromVersion pour Windows..." -ForegroundColor Yellow
    curl.exe -L --fail -o $PromZip "https://github.com/prometheus/prometheus/releases/download/v$PromVersion/prometheus-$PromVersion.windows-amd64.zip"
    Write-Host "  -> Extraction de Prometheus..." -ForegroundColor Yellow
    tar.exe -xf $PromZip -C $ObsBaseDir
}

if (-not (Test-Path $GrafanaExe)) {
    Write-Host "  -> Téléchargement de Grafana OSS v$GrafanaVersion pour Windows..." -ForegroundColor Yellow
    curl.exe -L --fail -o $GrafanaZip "https://dl.grafana.com/oss/release/grafana-$GrafanaVersion.windows-amd64.zip"
    Write-Host "  -> Extraction de Grafana..." -ForegroundColor Yellow
    tar.exe -xf $GrafanaZip -C $ObsBaseDir
}

Write-Host "[2/4] Génération de la configuration Prometheus locale (scrape 2s sur 127.0.0.1:8080/8001..8006)..." -ForegroundColor Cyan
$PromConfigPath = Join-Path $ObsBaseDir "prometheus-local.yml"
$AlertsRulePath = (Join-Path $RepoRoot "infra\observability\prometheus\alerts.yml") -replace "\\", "/"

$PromYaml = @"
global:
  scrape_interval: 2s
  evaluation_interval: 2s
  external_labels:
    project: "resilience-alpha"
    environment: "workshop-2026-live"

rule_files:
  - "$AlertsRulePath"

scrape_configs:
  - job_name: "waf-gateway"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8080"]
        labels:
          zone: "edge_net"
          service: "waf-gateway"

  - job_name: "payment-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8001"]
        labels:
          zone: "app_net"
          service: "api"

  - job_name: "auth-service"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8002"]
        labels:
          zone: "app_net"
          service: "auth"

  - job_name: "ml-detector"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8003"]
        labels:
          zone: "obs_net"
          service: "detector"

  - job_name: "soc-remediator"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8004"]
        labels:
          zone: "obs_net"
          service: "remediator"

  - job_name: "rag-assistant"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["127.0.0.1:8006"]
        labels:
          zone: "obs_net"
          service: "rag"
"@
Set-Content -Path $PromConfigPath -Value $PromYaml -Encoding UTF8

Write-Host "[3/4] Provisionnement automatique de Grafana (Datasource Prometheus + Dashboard RESILIENCE-ALPHA)..." -ForegroundColor Cyan
$ProvisioningDir = Join-Path $ObsBaseDir "grafana-provisioning"
$DatasourcesDir = Join-Path $ProvisioningDir "datasources"
$DashboardsProvDir = Join-Path $ProvisioningDir "dashboards"
$PluginsProvDir = Join-Path $ProvisioningDir "plugins"
$NotifiersProvDir = Join-Path $ProvisioningDir "notifiers"
$AlertingProvDir = Join-Path $ProvisioningDir "alerting"

New-Item -ItemType Directory -Force -Path $DatasourcesDir, $DashboardsProvDir, $PluginsProvDir, $NotifiersProvDir, $AlertingProvDir | Out-Null

$DatasourceYaml = @"
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus_ds
    access: proxy
    url: http://127.0.0.1:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: "2s"
"@
Set-Content -Path (Join-Path $DatasourcesDir "datasources.yml") -Value $DatasourceYaml -Encoding UTF8

$RepoDashboardsDir = (Join-Path $RepoRoot "infra\observability\grafana\dashboards") -replace "\\", "/"
$DefaultDashJsonPath = (Join-Path $RepoRoot "infra\observability\grafana\dashboards\resilience-alpha.json") -replace "\\", "/"

$DashboardProvYaml = @"
apiVersion: 1

providers:
  - name: "Resilience-Alpha Dashboards"
    orgId: 1
    folder: "RESILIENCE-ALPHA"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 5
    allowUiUpdates: true
    options:
      path: $RepoDashboardsDir
      foldersFromFilesStructure: false
"@
Set-Content -Path (Join-Path $DashboardsProvDir "dashboards.yml") -Value $DashboardProvYaml -Encoding UTF8

$GrafanaDataDir = (Join-Path $ObsBaseDir "grafana-data") -replace "\\", "/"
$GrafanaLogsDir = (Join-Path $ObsBaseDir "grafana-logs") -replace "\\", "/"
$GrafanaPluginsDir = (Join-Path $ObsBaseDir "grafana-plugins") -replace "\\", "/"
$ProvisioningDirSlash = $ProvisioningDir -replace "\\", "/"

$CustomIniPath = Join-Path $GrafanaExtractDir "conf\custom.ini"
$CustomIniContent = @"
[paths]
data = $GrafanaDataDir
logs = $GrafanaLogsDir
plugins = $GrafanaPluginsDir
provisioning = $ProvisioningDirSlash

[server]
http_addr = 0.0.0.0
http_port = 3001
domain = localhost

[security]
admin_user = admin
admin_password = resilience_grafana_2026
allow_embedding = true

[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Viewer

[dashboards]
default_home_dashboard_path = $DefaultDashJsonPath

[users]
default_theme = dark
"@
Set-Content -Path $CustomIniPath -Value $CustomIniContent -Encoding UTF8

Write-Host "[4/4] Démarrage des démons Prometheus (:9090) et Grafana (:3001)..." -ForegroundColor Cyan

# Arrêter d'éventuelles instances précédentes
Get-Process prometheus -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process grafana-server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

$PromStorageDir = Join-Path $ObsBaseDir "prometheus-data"
Start-Process -FilePath $PromExe -ArgumentList "--config.file=`"$PromConfigPath`"", "--storage.tsdb.path=`"$PromStorageDir`"", "--web.listen-address=0.0.0.0:9090" -WorkingDirectory $PromExtractDir -WindowStyle Hidden

Start-Process -FilePath $GrafanaExe -ArgumentList "--homepath=`"$GrafanaExtractDir`"", "--config=`"$CustomIniPath`"" -WorkingDirectory $GrafanaExtractDir -WindowStyle Hidden

Write-Host "Attente de la disponibilité HTTP sur :9090 et :3001..." -ForegroundColor Yellow
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    $gOk = (Test-NetConnection -ComputerName 127.0.0.1 -Port 3001 -WarningAction SilentlyContinue).TcpTestSucceeded
    $pOk = (Test-NetConnection -ComputerName 127.0.0.1 -Port 9090 -WarningAction SilentlyContinue).TcpTestSucceeded
    if ($gOk -and $pOk) {
        break
    }
}

Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "  GRAFANA & PROMETHEUS SONT ACTIFS !" -ForegroundColor Green
Write-Host "  -> Grafana UI        : http://127.0.0.1:3001  (ou http://192.168.137.1:3001)" -ForegroundColor Green
Write-Host "  -> Identifiants      : admin / resilience_grafana_2026 (ou accès direct sans login)" -ForegroundColor Green
Write-Host "  -> Prometheus UI     : http://127.0.0.1:9090" -ForegroundColor Green
Write-Host "  -> Command Center UI : http://127.0.0.1:3000" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
