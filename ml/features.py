"""Extraction, normalisation et explicabilité des 7 variables ML par fenêtre de 5 secondes.

Conformément à ADR-002 et `docs/contracts.md`, chaque fenêtre d'observation de 5 secondes
est résumée par un vecteur de 7 caractéristiques comportementales et applicatives :
1. `req_rate_rps` : débit total de requêtes par seconde (>= 0)
2. `latency_p95_ms` : 95e centile du temps de réponse applicatif en ms (>= 0)
3. `error_rate_ratio` : proportion de réponses HTTP 4xx/5xx dans [0.0, 1.0]
4. `expensive_endpoint_ratio` : proportion d'appels vers les routes coûteuses dans [0.0, 1.0]
5. `unique_ip_entropy` : entropie de Shannon normalisée des IP sources dans [0.0, 1.0]
6. `cpu_worker_saturation` : taux d'occupation des workers applicatifs dans [0.0, 1.0]
7. `tx_success_ratio` : ratio de transactions métier abouties par rapport au trafic entrant [0.0, 1.0]
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

import numpy as np

WINDOW_SECONDS: int = 5

FEATURE_NAMES: list[str] = [
    "req_rate_rps",
    "latency_p95_ms",
    "error_rate_ratio",
    "expensive_endpoint_ratio",
    "unique_ip_entropy",
    "cpu_worker_saturation",
    "tx_success_ratio",
]

EXPENSIVE_ENDPOINTS: tuple[str, ...] = (
    "/api/v1/transactions/verify-batch",
    "/api/v1/audit/reconcile",
)

# Statistiques de référence par défaut sur trafic normal varié (écrasées par model_metadata.json)
DEFAULT_BASELINE_STATS: dict[str, dict[str, float]] = {
    "req_rate_rps": {"mean": 14.5, "std": 9.5, "direction": 1.0, "weight": 1.0},
    "latency_p95_ms": {"mean": 42.0, "std": 25.0, "direction": 1.0, "weight": 1.25},
    "error_rate_ratio": {"mean": 0.025, "std": 0.03, "direction": 1.0, "weight": 1.0},
    "expensive_endpoint_ratio": {"mean": 0.04, "std": 0.04, "direction": 1.0, "weight": 1.35},
    "unique_ip_entropy": {"mean": 0.78, "std": 0.14, "direction": -1.0, "weight": 1.15},
    "cpu_worker_saturation": {"mean": 0.28, "std": 0.16, "direction": 1.0, "weight": 1.35},
    "tx_success_ratio": {"mean": 0.88, "std": 0.09, "direction": -1.0, "weight": 1.15},
}


def _clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def compute_ip_entropy(ip_counts: Mapping[str, int] | Sequence[str], ref_ip_pool: int = 16) -> float:
    """Calcule l'entropie de Shannon normalisée dans [0.0, 1.0] de la distribution des IP sources.

    - Lorsqu'une seule adresse IP concentre 100 % des requêtes (ex: flood depuis un hôte unique),
      l'entropie vaut 0.0.
    - Lorsque le trafic est distribué équitablement entre `ref_ip_pool` clients ou plus,
      l'entropie tend vers 1.0.
    """
    if isinstance(ip_counts, Mapping):
        counts = [int(v) for v in ip_counts.values() if int(v) > 0]
    else:
        counter = Counter(str(ip) for ip in ip_counts if ip)
        counts = list(counter.values())

    total = sum(counts)
    if total <= 0 or len(counts) <= 1:
        return 0.0

    entropy = 0.0
    for count in counts:
        p = count / total
        if p > 0.0:
            entropy -= p * math.log2(p)

    max_entropy = math.log2(max(ref_ip_pool, 2))
    return round(_clamp(entropy / max_entropy, 0.0, 1.0), 4)


def normalize_feature_dict(raw_features: Mapping[str, Any]) -> dict[str, float]:
    """Valide, borne et normalise un dictionnaire contenant les 7 variables du modèle."""
    req_rate = max(0.0, float(raw_features.get("req_rate_rps", 0.0)))
    latency_p95 = max(0.0, float(raw_features.get("latency_p95_ms", 0.0)))
    error_rate = _clamp(float(raw_features.get("error_rate_ratio", 0.0)), 0.0, 1.0)
    expensive_ratio = _clamp(float(raw_features.get("expensive_endpoint_ratio", 0.0)), 0.0, 1.0)
    ip_entropy = _clamp(float(raw_features.get("unique_ip_entropy", 0.0)), 0.0, 1.0)
    cpu_sat = _clamp(float(raw_features.get("cpu_worker_saturation", 0.0)), 0.0, 1.0)
    tx_success = _clamp(float(raw_features.get("tx_success_ratio", 0.0)), 0.0, 1.0)

    return {
        "req_rate_rps": round(req_rate, 4),
        "latency_p95_ms": round(latency_p95, 4),
        "error_rate_ratio": round(error_rate, 4),
        "expensive_endpoint_ratio": round(expensive_ratio, 4),
        "unique_ip_entropy": round(ip_entropy, 4),
        "cpu_worker_saturation": round(cpu_sat, 4),
        "tx_success_ratio": round(tx_success, 4),
    }


def extract_window_features(
    window_data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    window_seconds: float = float(WINDOW_SECONDS),
) -> dict[str, float]:
    """Extrait les 7 variables standardisées à partir d'une fenêtre de télémétrie ou de logs bruts.

    Accepte soit :
    - Un dictionnaire déjà agrégé (contenant directement les 7 clés ou des compteurs bruts
      `total_requests`, `latencies_ms`, `error_count`, `expensive_count`, `ip_counts`, etc.)
    - Une séquence d'événements HTTP individuels enregistrés pendant la fenêtre de 5 secondes.
    """
    duration = max(float(window_seconds), 0.1)

    if isinstance(window_data, Mapping):
        if all(k in window_data for k in FEATURE_NAMES):
            return normalize_feature_dict(window_data)

        if "features" in window_data and isinstance(window_data["features"], Mapping):
            return normalize_feature_dict(window_data["features"])

        total_requests = int(window_data.get("total_requests", 0))
        req_rate = float(window_data.get("req_rate_rps", total_requests / duration))

        if "latency_p95_ms" in window_data:
            latency_p95 = float(window_data["latency_p95_ms"])
        else:
            latencies = [float(x) for x in window_data.get("latencies_ms", [])]
            latency_p95 = float(np.percentile(latencies, 95)) if latencies else 0.0

        if "error_rate_ratio" in window_data:
            error_rate = float(window_data["error_rate_ratio"])
        else:
            error_count = int(window_data.get("error_count", 0))
            error_rate = (error_count / total_requests) if total_requests > 0 else 0.0

        if "expensive_endpoint_ratio" in window_data:
            expensive_ratio = float(window_data["expensive_endpoint_ratio"])
        else:
            expensive_count = int(window_data.get("expensive_count", 0))
            expensive_ratio = (expensive_count / total_requests) if total_requests > 0 else 0.0

        if "unique_ip_entropy" in window_data:
            ip_entropy = float(window_data["unique_ip_entropy"])
        else:
            ip_counts = window_data.get("ip_counts", {})
            ip_entropy = compute_ip_entropy(ip_counts)

        cpu_sat = float(
            window_data.get(
                "cpu_worker_saturation",
                min(1.0, (req_rate * (1.0 + 3.0 * expensive_ratio)) / 65.0),
            )
        )

        if "tx_success_ratio" in window_data:
            tx_success = float(window_data["tx_success_ratio"])
        else:
            tx_ok = int(window_data.get("tx_committed_count", 0))
            tx_total = max(int(window_data.get("tx_attempt_count", total_requests)), 1)
            tx_success = tx_ok / tx_total if total_requests > 0 else 1.0

        return normalize_feature_dict(
            {
                "req_rate_rps": req_rate,
                "latency_p95_ms": latency_p95,
                "error_rate_ratio": error_rate,
                "expensive_endpoint_ratio": expensive_ratio,
                "unique_ip_entropy": ip_entropy,
                "cpu_worker_saturation": cpu_sat,
                "tx_success_ratio": tx_success,
            }
        )

    # Cas d'une liste d'événements HTTP bruts sur la fenêtre
    events = list(window_data)
    total_requests = len(events)
    if total_requests == 0:
        return normalize_feature_dict(
            {
                "req_rate_rps": 0.0,
                "latency_p95_ms": 12.0,
                "error_rate_ratio": 0.0,
                "expensive_endpoint_ratio": 0.0,
                "unique_ip_entropy": 1.0,
                "cpu_worker_saturation": 0.05,
                "tx_success_ratio": 1.0,
            }
        )

    req_rate = total_requests / duration
    latencies = [float(ev.get("latency_ms", 15.0)) for ev in events]
    latency_p95 = float(np.percentile(latencies, 95))

    errors = sum(1 for ev in events if int(ev.get("status_code", 200)) >= 400)
    error_rate = errors / total_requests

    expensive_hits = sum(
        1
        for ev in events
        if any(str(ev.get("path", "")).startswith(ep) for ep in EXPENSIVE_ENDPOINTS)
    )
    expensive_ratio = expensive_hits / total_requests

    ips = [str(ev.get("source_ip", "127.0.0.1")) for ev in events]
    ip_entropy = compute_ip_entropy(ips)

    cpu_values = [
        float(ev["cpu_worker_saturation"])
        for ev in events
        if "cpu_worker_saturation" in ev
    ]
    if cpu_values:
        cpu_sat = float(np.mean(cpu_values))
    else:
        cpu_sat = _clamp(
            0.08 + (req_rate / 75.0) * 0.45 + expensive_ratio * 0.45 + (latency_p95 / 1200.0) * 0.25,
            0.0,
            1.0,
        )

    tx_events = [
        ev for ev in events if str(ev.get("path", "")).startswith("/api/v1/transactions")
    ]
    if tx_events:
        tx_ok = sum(
            1
            for ev in tx_events
            if int(ev.get("status_code", 200)) in (200, 201)
            and not str(ev.get("path", "")).endswith("/verify-batch")
        )
        tx_success = tx_ok / len(tx_events)
    else:
        tx_success = max(0.0, 1.0 - error_rate)

    return normalize_feature_dict(
        {
            "req_rate_rps": req_rate,
            "latency_p95_ms": latency_p95,
            "error_rate_ratio": error_rate,
            "expensive_endpoint_ratio": expensive_ratio,
            "unique_ip_entropy": ip_entropy,
            "cpu_worker_saturation": cpu_sat,
            "tx_success_ratio": tx_success,
        }
    )


def features_to_vector(features: Mapping[str, Any]) -> np.ndarray:
    """Convertit un dictionnaire de variables en vecteur NumPy 1D ordonné selon `FEATURE_NAMES`."""
    normalized = normalize_feature_dict(features)
    return np.array([normalized[name] for name in FEATURE_NAMES], dtype=np.float64)


def compute_top_contributing_features(
    features: Mapping[str, Any],
    baseline_stats: Mapping[str, Mapping[str, float]] | None = None,
    feature_importances: Mapping[str, float] | None = None,
    top_k: int = 3,
) -> list[str]:
    """Identifie les `top_k` variables qui contribuent le plus à l'écart d'anomalie observé.

    Pour chaque variable :
    - On calcule l'écart réduit orienté (Z-score directionnel) par rapport à la moyenne et
      l'écart-type appris sur le trafic normal (`baseline_stats`).
    - Pour les variables qui augmentent lors d'un incident (`req_rate_rps`, `latency_p95_ms`,
      `error_rate_ratio`, `expensive_endpoint_ratio`, `cpu_worker_saturation`), un dépassement
      positif de la moyenne accroît fortement le score de contribution.
    - Pour les variables qui chutent lors d'un incident (`unique_ip_entropy`, `tx_success_ratio`),
      une baisse sous la moyenne normale accroît le score de contribution.
    - On pondère par l'importance de la variable (`feature_importances` ou poids métier).
    """
    normalized = normalize_feature_dict(features)
    stats = baseline_stats or DEFAULT_BASELINE_STATS

    contributions: list[tuple[str, float]] = []
    for name in FEATURE_NAMES:
        val = normalized[name]
        f_stat = stats.get(name, DEFAULT_BASELINE_STATS[name])
        mean = float(f_stat.get("mean", DEFAULT_BASELINE_STATS[name]["mean"]))
        std = max(float(f_stat.get("std", DEFAULT_BASELINE_STATS[name]["std"])), 1e-6)
        direction = float(f_stat.get("direction", DEFAULT_BASELINE_STATS[name]["direction"]))
        base_weight = float(f_stat.get("weight", DEFAULT_BASELINE_STATS[name]["weight"]))

        if feature_importances and name in feature_importances:
            imp_weight = max(0.5, float(feature_importances[name]) * 5.0)
        else:
            imp_weight = base_weight

        raw_z = (val - mean) / std
        directional_z = raw_z * direction
        # Si la dérive est dans le sens d'une anomalie, on lui donne le poids plein ;
        # sinon on conserve une faible contribution absolue en cas de valeur extrême atypique.
        effective_score = (
            directional_z * imp_weight
            if directional_z > 0
            else abs(raw_z) * 0.25 * imp_weight
        )
        contributions.append((name, float(effective_score)))

    contributions.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in contributions[: max(1, min(top_k, len(FEATURE_NAMES)))]]
