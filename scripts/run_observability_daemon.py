"""
PROJECT RESILIENCE-ALPHA — Superviseur Natif Prometheus (:9090) & Grafana OSS (:3001)
Lance et maintient en vie les binaires officiels Windows de Prometheus v2.54.1 et Grafana v11.2.0
sans dépendre de WSL2 / Docker Desktop Linux Engine, tout en provisionnant automatiquement :
  - la source de données Prometheus (http://127.0.0.1:9090, scrape 2s sur tous les microservices)
  - le dashboard officiel `infra/observability/grafana/dashboards/resilience-alpha.json`
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OBS_BASE = Path(os.path.expandvars(r"%LOCALAPPDATA%\resilience-alpha-obs"))
PROM_DIR = OBS_BASE / "prometheus-2.54.1.windows-amd64"
PROM_EXE = PROM_DIR / "prometheus.exe"
GRAFANA_DIR = OBS_BASE / "grafana-v11.2.0"
GRAFANA_EXE = GRAFANA_DIR / "bin" / "grafana-server.exe"


def write_configs() -> tuple[Path, Path]:
    OBS_BASE.mkdir(parents=True, exist_ok=True)
    prom_cfg = OBS_BASE / "prometheus-local.yml"

    prom_yaml = """global:
  scrape_interval: 2s
  evaluation_interval: 2s
  external_labels:
    project: "resilience-alpha"
    environment: "workshop-2026-live"

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
"""
    prom_cfg.write_text(prom_yaml, encoding="utf-8")

    prov_dir = OBS_BASE / "grafana-provisioning"
    for sub in ("datasources", "dashboards", "plugins", "notifiers", "alerting"):
        (prov_dir / sub).mkdir(parents=True, exist_ok=True)

    ds_yaml = """apiVersion: 1

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
"""
    (prov_dir / "datasources" / "datasources.yml").write_text(ds_yaml, encoding="utf-8")

    dash_dir_slash = (REPO_ROOT / "infra" / "observability" / "grafana" / "dashboards").as_posix()
    default_dash_slash = (
        REPO_ROOT / "infra" / "observability" / "grafana" / "dashboards" / "resilience-alpha.json"
    ).as_posix()

    dash_yaml = f"""apiVersion: 1

providers:
  - name: "Resilience-Alpha Dashboards"
    orgId: 1
    folder: "RESILIENCE-ALPHA"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 5
    allowUiUpdates: true
    options:
      path: {dash_dir_slash}
      foldersFromFilesStructure: false
"""
    (prov_dir / "dashboards" / "dashboards.yml").write_text(dash_yaml, encoding="utf-8")

    for dname in ("grafana-data", "grafana-logs", "grafana-plugins"):
        (OBS_BASE / dname).mkdir(parents=True, exist_ok=True)

    data_dir = (OBS_BASE / "grafana-data").as_posix()
    logs_dir = (OBS_BASE / "grafana-logs").as_posix()
    plugins_dir = (OBS_BASE / "grafana-plugins").as_posix()
    prov_slash = prov_dir.as_posix()

    custom_ini = GRAFANA_DIR / "conf" / "custom.ini"
    ini_content = f"""[paths]
data = {data_dir}
logs = {logs_dir}
plugins = {plugins_dir}
provisioning = {prov_slash}

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
default_home_dashboard_path = {default_dash_slash}

[users]
default_theme = dark
"""
    custom_ini.write_text(ini_content, encoding="utf-8")
    return prom_cfg, custom_ini


def main() -> None:
    if not PROM_EXE.exists() or not GRAFANA_EXE.exists():
        print(f"[ERREUR] Binaires introuvables dans {OBS_BASE}. Exécutez start_grafana_native.ps1 d'abord.")
        sys.exit(1)

    subprocess.run(["taskkill", "/F", "/IM", "prometheus.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "grafana-server.exe"], capture_output=True)
    time.sleep(1)

    prom_cfg, custom_ini = write_configs()
    prom_tsdb = OBS_BASE / "prometheus-data"
    prom_tsdb.mkdir(parents=True, exist_ok=True)

    prom_log_file = open(OBS_BASE / "prometheus-stdout.log", "w", encoding="utf-8")
    graf_log_file = open(OBS_BASE / "grafana-stdout.log", "w", encoding="utf-8")

    print("[OBS] Démarrage de Prometheus v2.54.1 sur 0.0.0.0:9090...", flush=True)
    prom_proc = subprocess.Popen(
        [
            str(PROM_EXE),
            f"--config.file={prom_cfg}",
            f"--storage.tsdb.path={prom_tsdb}",
            "--web.listen-address=0.0.0.0:9090",
        ],
        cwd=str(PROM_DIR),
        stdout=prom_log_file,
        stderr=subprocess.STDOUT,
    )

    print("[OBS] Démarrage de Grafana OSS v11.2.0 sur 0.0.0.0:3001...", flush=True)
    graf_proc = subprocess.Popen(
        [
            str(GRAFANA_EXE),
            f"--homepath={GRAFANA_DIR}",
            f"--config={custom_ini}",
        ],
        cwd=str(GRAFANA_DIR),
        stdout=graf_log_file,
        stderr=subprocess.STDOUT,
    )

    prom_ready = False
    graf_ready = False
    for _ in range(60):
        time.sleep(1)
        if not prom_ready:
            try:
                with urllib.request.urlopen("http://127.0.0.1:9090/-/ready", timeout=1) as r:
                    if r.status == 200:
                        prom_ready = True
                        print("[OBS] Prometheus est PRET sur http://127.0.0.1:9090", flush=True)
            except Exception:
                pass
        if not graf_ready:
            try:
                with urllib.request.urlopen("http://127.0.0.1:3001/api/health", timeout=1) as r:
                    if r.status == 200:
                        graf_ready = True
                        print("[OBS] Grafana est PRET sur http://127.0.0.1:3001", flush=True)
            except Exception:
                pass
        if prom_ready and graf_ready:
            break

    print("======================================================================", flush=True)
    print("  SERVEURS GRAFANA (:3001) & PROMETHEUS (:9090) OPERATIONNELS EN DIRECT", flush=True)
    print("  URL Dashboard : http://127.0.0.1:3001/d/resilience-alpha-main", flush=True)
    print("======================================================================", flush=True)

    try:
        while True:
            time.sleep(5)
            if prom_proc.poll() is not None:
                print(f"[OBS] Prometheus s'est arrêté (code={prom_proc.returncode})", flush=True)
                break
            if graf_proc.poll() is not None:
                print(f"[OBS] Grafana s'est arrêté (code={graf_proc.returncode})", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        prom_proc.terminate()
        graf_proc.terminate()


if __name__ == "__main__":
    main()
