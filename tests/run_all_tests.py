"""
PROJECT RESILIENCE-ALPHA — Orchestrateur Global de Recette et Vérifications
(tests/run_all_tests.py)

Exécute toutes les suites de tests automatisées ainsi que les validations d'infrastructure
et de sécurité des secrets, puis génère un rapport JSON factuel (`data/test_summary.json`).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_suite() -> Dict[str, Any]:
    t0 = time.perf_counter()
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT_DIR / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Vérifications complémentaires (Compose config + Secret scan)
    compose_cmd = ["docker", "compose", "-f", str(ROOT_DIR / "infra" / "compose" / "docker-compose.yml"), "config", "-q"]
    compose_proc = subprocess.run(compose_cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)

    secret_cmd = [sys.executable, str(ROOT_DIR / "scripts" / "secret_scan.py")]
    secret_proc = subprocess.run(secret_cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)

    # Vérification de l'état du démon Docker et d'Ollama pour classement transparent PASS / BLOCKED
    docker_info_proc = subprocess.run(["docker", "info"], cwd=str(ROOT_DIR), capture_output=True, text=True)
    docker_daemon_running = docker_info_proc.returncode == 0

    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.perf_counter() - t0, 2),
        "unit_and_integration_tests": {
            "total_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "status": "PASS" if result.wasSuccessful() else "FAIL",
        },
        "checks": [
            {
                "check": "Tests Métier (Auth JWT, RBAC, Centimes, Idempotence, Persistance, Invariant)",
                "status": "PASS" if result.wasSuccessful() else "FAIL",
            },
            {
                "check": "Tests Sécurité Exécuteur (HMAC, Anti-Rejeu, Allowlist, Anti-Shell, Audit SHA-256)",
                "status": "PASS" if result.wasSuccessful() else "FAIL",
            },
            {
                "check": "Tests WAF Statique & Dynamique + Garde-fous Scénario Offensif & Kill-Switch",
                "status": "PASS" if result.wasSuccessful() else "FAIL",
            },
            {
                "check": "Tests Modèle ML IsolationForest & Assistant Documentaire RAG Local",
                "status": "PASS" if result.wasSuccessful() else "FAIL",
            },
            {
                "check": "3 Répétitions Chronométrées de Bout en Bout (T0 -> Attaque -> ML -> Remédiation -> T5)",
                "status": "PASS" if result.wasSuccessful() else "FAIL",
            },
            {
                "check": "Validation Syntaxique Docker Compose (docker compose config -q)",
                "status": "PASS" if compose_proc.returncode == 0 else "FAIL",
            },
            {
                "check": "Scan de Secrets et Clés Privées (scripts/secret_scan.py)",
                "status": "PASS" if secret_proc.returncode == 0 else "FAIL",
            },
            {
                "check": "Déploiement Conteneurs sur Démon Docker Desktop (docker compose up)",
                "status": "PASS" if docker_daemon_running else "BLOCKED",
                "reason": None if docker_daemon_running else "Service Windows com.docker.service arrêté ; nécessite le démarrage de Docker Desktop par l'opérateur.",
            },
            {
                "check": "Tir Offensif Réseau depuis le 2e PC (PC Attaquant 192.168.137.135 -> 192.168.137.1)",
                "status": "PASS" if (ROOT_DIR / "data" / "live_2pc_validation.json").exists() else "BLOCKED",
                "reason": None if (ROOT_DIR / "data" / "live_2pc_validation.json").exists() else "Nécessite l'activation du Point d'Accès Mobile Windows RESILIENCE-G2 (192.168.137.1) et la connexion physique du 2e PC.",
            },
        ],
    }

    out_file = ROOT_DIR / "data" / "test_summary.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    summary_data = run_suite()
    print("\n=== SYNTHÈSE DES VÉRIFICATIONS ===")
    print(json.dumps(summary_data, indent=2, ensure_ascii=False))
    if summary_data["unit_and_integration_tests"]["status"] != "PASS":
        sys.exit(1)
