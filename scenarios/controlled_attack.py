"""
PROJECT RESILIENCE-ALPHA — Générateur de Charge de Test de Résilience Borné
(scenarios/controlled_attack.py)

Objectif pédagogique (Section 6 & Section 10) :
- Générer une charge applicative bornée et reproductible sur l'endpoint de rapprochement
  par lots (`/api/v1/transactions/verify-batch`) afin de tester la détection ML
  (`IsolationForest`) et la remédiation autonome (`Zero-Touch Recovery`).

Garde-fous de sécurité stricts intégrés :
1. Liste blanche d'hôtes autorisés (`ALLOWED_HOSTS`) : uniquement `127.0.0.1`, `localhost`
   ou le point d'accès isolé du groupe `192.168.137.1`. Toute autre adresse IP (campus,
   Internet, autres sous-réseaux) lève immédiatement `PermissionError`.
2. Plafonds matériels stricts :
   - `MAX_DURATION_SECONDS = 45.0`
   - `MAX_RATE_RPS = 50.0`
   - `MAX_CONCURRENCY = 8`
3. Vérification de l'arrêt d'urgence (`is_kill_switch_engaged()`) avant chaque requête.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

from scenarios.kill_switch import is_kill_switch_engaged

ALLOWED_HOSTS: Set[str] = {
    "127.0.0.1",
    "localhost",
    "192.168.137.1",
}

MAX_DURATION_SECONDS: float = 45.0
MAX_RATE_RPS: float = 50.0
MAX_CONCURRENCY: int = 8


def validate_authorized_target(target_url: str, require_remote_confirmation: bool = False, confirmed: bool = False) -> str:
    """
    Vérifie que l'URL cible appartient exclusivement au périmètre de laboratoire autorisé.
    Refuse toute cible publique, du campus (`10.60.0.0/16`) ou hors `ALLOWED_HOSTS`.
    """
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Schéma URL non supporté : {parsed.scheme}")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("Hôte cible manquant dans l'URL.")

    if host not in ALLOWED_HOSTS:
        # Vérifie explicitement si c'est une IP hors liste blanche
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_global or str(ip_obj).startswith("10.60."):
                raise PermissionError(
                    f"REFUS DE SÉCURITÉ : Cible '{host}' hors périmètre autorisé (réseau campus ou public interdit)."
                )
        except ValueError:
            pass
        raise PermissionError(
            f"REFUS DE SÉCURITÉ : Hôte '{host}' absent de la liste locale d'autorisation ({sorted(ALLOWED_HOSTS)})."
        )

    if host == "192.168.137.1" and require_remote_confirmation and not confirmed:
        raise PermissionError(
            "Confirmation explicite requise (--confirm-authorized-lab) pour cibler 192.168.137.1."
        )

    return host


def run_bounded_resilience_scenario(
    target_base_url: str = "http://127.0.0.1:8080",
    *,
    duration_seconds: float = 8.0,
    rate_rps: float = 20.0,
    concurrency: int = 4,
    simulated_source_ip: str = "192.168.137.45",
    confirmed_lab: bool = True,
    request_Hook: Optional[Callable[[str, Dict[str, Any], Dict[str, str]], int]] = None,
) -> Dict[str, Any]:
    """
    Exécute un test borné de saturation applicative sur `/api/v1/transactions/verify-batch`.
    Si `request_Hook` est fourni (mode test d'intégration local), l'utilise à la place d'un socket réseau.
    """
    host = validate_authorized_target(
        target_base_url,
        require_remote_confirmation=( simulated_source_ip != "127.0.0.1" and "192.168.137.1" in target_base_url ),
        confirmed=confirmed_lab,
    )

    safe_duration = max(0.5, min(float(duration_seconds), MAX_DURATION_SECONDS))
    safe_rate = max(1.0, min(float(rate_rps), MAX_RATE_RPS))
    safe_concurrency = max(1, min(int(concurrency), MAX_CONCURRENCY))

    endpoint = f"{target_base_url.rstrip('/')}/api/v1/transactions/verify-batch"
    headers = {
        "Content-Type": "application/json",
        "X-Forwarded-For": simulated_source_ip,
        "User-Agent": "ResilienceAlpha-LabScenario/1.0",
    }
    payload = {
        "batch_size": 30,
        "iterations": 40000,
        "audit_profile": "deep_verification",
    }

    t_start = time.perf_counter()
    deadline = t_start + safe_duration
    interval = 1.0 / safe_rate

    status_counts: Dict[str, int] = {"200": 0, "403": 0, "429": 0, "503": 0, "other": 0}
    total_sent = 0
    aborted_by_kill_switch = False

    def _single_call() -> int:
        if is_kill_switch_engaged():
            return -1
        if request_Hook is not None:
            return int(request_Hook("/api/v1/transactions/verify-batch", payload, headers))
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=2.5)
            return resp.status_code
        except Exception:
            return 503

    with ThreadPoolExecutor(max_workers=safe_concurrency) as pool:
        futures = []
        while time.perf_counter() < deadline:
            if is_kill_switch_engaged():
                aborted_by_kill_switch = True
                break
            futures.append(pool.submit(_single_call))
            total_sent += 1
            time.sleep(interval)

        for fut in futures:
            code = fut.result()
            if code == -1:
                aborted_by_kill_switch = True
                continue
            key = str(code) if str(code) in status_counts else "other"
            status_counts[key] += 1

    elapsed = round(time.perf_counter() - t_start, 3)
    return {
        "scenario": "L7_BATCH_VERIFICATION_LOAD",
        "target_host": host,
        "simulated_source_ip": simulated_source_ip,
        "duration_configured_s": safe_duration,
        "duration_actual_s": elapsed,
        "rate_configured_rps": safe_rate,
        "concurrency": safe_concurrency,
        "total_requests": total_sent,
        "status_counts": status_counts,
        "blocked_by_waf_count": status_counts["403"] + status_counts["429"],
        "aborted_by_kill_switch": aborted_by_kill_switch,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scénario borné de test de résilience PROJECT RESILIENCE-ALPHA")
    parser.add_argument("--target", default="http://127.0.0.1:8080", help="URL du WAF cible (liste blanche stricte)")
    parser.add_argument("--duration", type=float, default=15.0, help="Durée en secondes (max 45s)")
    parser.add_argument("--rate", type=float, default=25.0, help="Débit en req/s (max 50 rps)")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrence (max 8)")
    parser.add_argument("--source-ip", default="192.168.137.45", help="IP source du poste de test")
    parser.add_argument("--confirm-authorized-lab", action="store_true", help="Confirme le périmètre isolé RESILIENCE-G<n>")
    args = parser.parse_args()

    summary = run_bounded_resilience_scenario(
        target_base_url=args.target,
        duration_seconds=args.duration,
        rate_rps=args.rate,
        concurrency=args.concurrency,
        simulated_source_ip=args.source_ip,
        confirmed_lab=args.confirm_authorized_lab,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
