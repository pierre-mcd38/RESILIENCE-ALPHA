"""Générateur reproductible de sessions temporelles d'observation (sans fuite de données).

Ce script génère trois jeux de données séparés par identifiant de session (`session_id`) :
- `ml/data/train_normal_sessions.csv` : exclusivement du trafic normal varié et multimodal
  (repos nocturne, charge nominale, pics horaires légitimes de fin de journée, erreurs 4xx
  bénignes de saisie client, rapprochements comptables planifiés, incluant de rares micro-pointes
  isolées d'une seule fenêtre illustrant le bruit réel d'exploitation).
- `ml/data/val_sessions.csv` : sessions normales indépendantes + sessions d'incidents
  (flood L7 sur `/verify-batch`, dégradation progressive de latence, force brute d'auth)
  pour la calibration du seuil et la sélection de modèle.
- `ml/data/test_sessions.csv` : sessions normales indépendantes + sessions d'incidents
  jamais vues à l'entraînement ni à la calibration, pour l'évaluation finale.

Aucune variable cachée (ex: `attack_launched`) n'est créée : seules les 7 variables
observables de `FEATURE_NAMES` servent à l'apprentissage et à l'inférence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import FEATURE_NAMES, WINDOW_SECONDS, normalize_feature_dict

SEED: int = 20261019
DATA_DIR: Path = Path(__file__).resolve().parent / "data"

NORMAL_PROFILES: tuple[str, ...] = (
    "normal_idle",
    "normal_nominal",
    "normal_legitimate_peak",
    "normal_benign_4xx",
    "normal_scheduled_audit",
)

INCIDENT_PROFILES: tuple[str, ...] = (
    "attack_l7_verify_batch_flood",
    "incident_latency_degradation",
    "attack_auth_brute_force",
)


def _sample_normal_window(
    rng: np.random.Generator,
    profile: str,
    step: int,
    allow_transient_microspike: bool = False,
) -> dict[str, float]:
    """Génère une fenêtre de 5s appartenant à l'un des 5 régimes de trafic normal légitime."""
    wave = float(np.sin(step * 0.45))

    if profile == "normal_idle":
        raw = {
            "req_rate_rps": rng.normal(4.2 + 0.6 * wave, 1.1),
            "latency_p95_ms": rng.normal(19.5 + 1.5 * wave, 3.8),
            "error_rate_ratio": rng.beta(1.2, 95.0),
            "expensive_endpoint_ratio": rng.beta(1.1, 65.0),
            "unique_ip_entropy": rng.normal(0.72, 0.06),
            "cpu_worker_saturation": rng.normal(0.10 + 0.015 * wave, 0.025),
            "tx_success_ratio": rng.normal(0.96, 0.02),
        }
    elif profile == "normal_nominal":
        raw = {
            "req_rate_rps": rng.normal(15.5 + 2.0 * wave, 3.2),
            "latency_p95_ms": rng.normal(38.0 + 4.0 * wave, 7.5),
            "error_rate_ratio": rng.beta(1.8, 75.0),
            "expensive_endpoint_ratio": rng.beta(2.0, 42.0),
            "unique_ip_entropy": rng.normal(0.83, 0.055),
            "cpu_worker_saturation": rng.normal(0.27 + 0.03 * wave, 0.055),
            "tx_success_ratio": rng.normal(0.92, 0.03),
        }
    elif profile == "normal_legitimate_peak":
        # Pic horaire légitime (ex: clôture de journée / paie) :
        # Débit élevé mais forte entropie IP (nombreux clients distincts),
        # faible ratio de routes coûteuses et taux de succès transactionnel élevé.
        raw = {
            "req_rate_rps": rng.normal(35.0 + 3.5 * wave, 5.2),
            "latency_p95_ms": rng.normal(78.0 + 8.0 * wave, 14.0),
            "error_rate_ratio": rng.beta(2.0, 65.0),
            "expensive_endpoint_ratio": rng.beta(2.2, 34.0),
            "unique_ip_entropy": rng.normal(0.91, 0.04),
            "cpu_worker_saturation": rng.normal(0.51 + 0.04 * wave, 0.065),
            "tx_success_ratio": rng.normal(0.89, 0.035),
        }
    elif profile == "normal_benign_4xx":
        # Erreurs 4xx bénignes de saisie client (ex: montants invalides rejetés en 422) :
        # Taux d'erreur modérément plus haut (7 % à 16 %), mais latence basse et CPU bas.
        raw = {
            "req_rate_rps": rng.normal(13.5 + 1.5 * wave, 2.8),
            "latency_p95_ms": rng.normal(34.0 + 3.0 * wave, 6.5),
            "error_rate_ratio": rng.normal(0.11, 0.025),
            "expensive_endpoint_ratio": rng.beta(1.5, 45.0),
            "unique_ip_entropy": rng.normal(0.80, 0.06),
            "cpu_worker_saturation": rng.normal(0.23, 0.045),
            "tx_success_ratio": rng.normal(0.81, 0.04),
        }
    elif profile == "normal_scheduled_audit":
        # Rapprochement comptable régulier modéré : quelques appels /verify-batch légitimes
        # sans saturation des workers ni effondrement des transactions.
        raw = {
            "req_rate_rps": rng.normal(14.5 + 1.2 * wave, 2.6),
            "latency_p95_ms": rng.normal(68.0 + 5.0 * wave, 12.0),
            "error_rate_ratio": rng.beta(1.5, 80.0),
            "expensive_endpoint_ratio": rng.normal(0.16, 0.032),
            "unique_ip_entropy": rng.normal(0.75, 0.055),
            "cpu_worker_saturation": rng.normal(0.40, 0.055),
            "tx_success_ratio": rng.normal(0.88, 0.035),
        }
    else:
        raise ValueError(f"Profil normal inconnu : {profile}")

    raw["req_rate_rps"] = float(np.clip(raw["req_rate_rps"], 1.2, 48.0))
    raw["latency_p95_ms"] = float(np.clip(raw["latency_p95_ms"], 11.0, 135.0))
    raw["error_rate_ratio"] = float(np.clip(raw["error_rate_ratio"], 0.0, 0.17))
    raw["expensive_endpoint_ratio"] = float(np.clip(raw["expensive_endpoint_ratio"], 0.0, 0.24))
    raw["unique_ip_entropy"] = float(np.clip(raw["unique_ip_entropy"], 0.56, 0.99))
    raw["cpu_worker_saturation"] = float(np.clip(raw["cpu_worker_saturation"], 0.04, 0.65))
    raw["tx_success_ratio"] = float(np.clip(raw["tx_success_ratio"], 0.72, 1.0))

    # Micro-pointe transitoire isolée (1 seule fenêtre de 5s) :
    # Simule un bref à-coup réseau/GC d'une seule fenêtre (état SUSPECT potentiel),
    # qui retombe immédiatement à la fenêtre suivante et ne doit PAS déclencher d'INCIDENT.
    if allow_transient_microspike:
        raw["req_rate_rps"] = float(rng.uniform(44.0, 56.0))
        raw["latency_p95_ms"] = float(rng.uniform(185.0, 255.0))
        raw["error_rate_ratio"] = float(rng.uniform(0.15, 0.22))
        raw["expensive_endpoint_ratio"] = float(rng.uniform(0.24, 0.34))
        raw["unique_ip_entropy"] = float(rng.uniform(0.42, 0.54))
        raw["cpu_worker_saturation"] = float(rng.uniform(0.66, 0.74))
        raw["tx_success_ratio"] = float(rng.uniform(0.58, 0.68))

    return normalize_feature_dict(raw)


def _sample_incident_window(
    rng: np.random.Generator, profile: str, incident_step: int
) -> dict[str, float]:
    """Génère une fenêtre de 5s en phase active d'incident (`incident_step >= 0`)."""
    ramp = float(min(1.0, 0.55 + 0.22 * incident_step))

    if profile == "attack_l7_verify_batch_flood":
        # Scénario principal : Flood applicatif L7 sur /api/v1/transactions/verify-batch
        raw = {
            "req_rate_rps": rng.normal(52.0 + 24.0 * ramp, 6.5),
            "latency_p95_ms": rng.normal(480.0 + 450.0 * ramp, 70.0),
            "error_rate_ratio": rng.normal(0.21 + 0.15 * ramp, 0.045),
            "expensive_endpoint_ratio": rng.normal(0.75 + 0.16 * ramp, 0.04),
            "unique_ip_entropy": rng.normal(0.14 - 0.04 * ramp, 0.035),
            "cpu_worker_saturation": rng.normal(0.83 + 0.13 * ramp, 0.03),
            "tx_success_ratio": rng.normal(0.24 - 0.10 * ramp, 0.045),
        }
        raw["req_rate_rps"] = float(np.clip(raw["req_rate_rps"], 42.0, 110.0))
        raw["latency_p95_ms"] = float(np.clip(raw["latency_p95_ms"], 340.0, 1500.0))
        raw["error_rate_ratio"] = float(np.clip(raw["error_rate_ratio"], 0.14, 0.60))
        raw["expensive_endpoint_ratio"] = float(np.clip(raw["expensive_endpoint_ratio"], 0.65, 0.98))
        raw["unique_ip_entropy"] = float(np.clip(raw["unique_ip_entropy"], 0.02, 0.25))
        raw["cpu_worker_saturation"] = float(np.clip(raw["cpu_worker_saturation"], 0.78, 1.0))
        raw["tx_success_ratio"] = float(np.clip(raw["tx_success_ratio"], 0.05, 0.38))

    elif profile == "incident_latency_degradation":
        # Dégradation progressive de latence et contention des workers/DB :
        # À incident_step == 0, l'anomalie est parfois subtile (transition progressive),
        # puis s'aggrave franchement dès incident_step >= 1.
        if incident_step == 0 and rng.random() < 0.35:
            raw = {
                "req_rate_rps": rng.normal(24.0, 3.5),
                "latency_p95_ms": rng.normal(175.0, 22.0),
                "error_rate_ratio": rng.normal(0.11, 0.025),
                "expensive_endpoint_ratio": rng.normal(0.21, 0.035),
                "unique_ip_entropy": rng.normal(0.55, 0.05),
                "cpu_worker_saturation": rng.normal(0.62, 0.04),
                "tx_success_ratio": rng.normal(0.66, 0.05),
            }
        else:
            prog = float(min(1.0, 0.45 + 0.15 * incident_step))
            raw = {
                "req_rate_rps": rng.normal(28.0 + 8.0 * prog, 4.5),
                "latency_p95_ms": rng.normal(330.0 + 480.0 * prog, 60.0),
                "error_rate_ratio": rng.normal(0.18 + 0.16 * prog, 0.04),
                "expensive_endpoint_ratio": rng.normal(0.28 + 0.12 * prog, 0.045),
                "unique_ip_entropy": rng.normal(0.42 - 0.08 * prog, 0.05),
                "cpu_worker_saturation": rng.normal(0.76 + 0.16 * prog, 0.035),
                "tx_success_ratio": rng.normal(0.34 - 0.14 * prog, 0.05),
            }
        raw["req_rate_rps"] = float(np.clip(raw["req_rate_rps"], 18.0, 55.0))
        raw["latency_p95_ms"] = float(np.clip(raw["latency_p95_ms"], 145.0, 1200.0))
        raw["error_rate_ratio"] = float(np.clip(raw["error_rate_ratio"], 0.08, 0.55))
        raw["expensive_endpoint_ratio"] = float(np.clip(raw["expensive_endpoint_ratio"], 0.16, 0.55))
        raw["unique_ip_entropy"] = float(np.clip(raw["unique_ip_entropy"], 0.20, 0.62))
        raw["cpu_worker_saturation"] = float(np.clip(raw["cpu_worker_saturation"], 0.58, 0.99))
        raw["tx_success_ratio"] = float(np.clip(raw["tx_success_ratio"], 0.08, 0.72))

    elif profile == "attack_auth_brute_force":
        # Force brute sur l'authentification et jetons invalides en rafale
        raw = {
            "req_rate_rps": rng.normal(58.0 + 16.0 * ramp, 6.0),
            "latency_p95_ms": rng.normal(260.0 + 130.0 * ramp, 38.0),
            "error_rate_ratio": rng.normal(0.72 + 0.14 * ramp, 0.045),
            "expensive_endpoint_ratio": rng.normal(0.06, 0.02),
            "unique_ip_entropy": rng.normal(0.12, 0.035),
            "cpu_worker_saturation": rng.normal(0.74 + 0.10 * ramp, 0.04),
            "tx_success_ratio": rng.normal(0.14 - 0.05 * ramp, 0.035),
        }
        raw["req_rate_rps"] = float(np.clip(raw["req_rate_rps"], 42.0, 95.0))
        raw["latency_p95_ms"] = float(np.clip(raw["latency_p95_ms"], 180.0, 600.0))
        raw["error_rate_ratio"] = float(np.clip(raw["error_rate_ratio"], 0.55, 0.96))
        raw["expensive_endpoint_ratio"] = float(np.clip(raw["expensive_endpoint_ratio"], 0.01, 0.15))
        raw["unique_ip_entropy"] = float(np.clip(raw["unique_ip_entropy"], 0.02, 0.24))
        raw["cpu_worker_saturation"] = float(np.clip(raw["cpu_worker_saturation"], 0.65, 0.95))
        raw["tx_success_ratio"] = float(np.clip(raw["tx_success_ratio"], 0.02, 0.28))
    else:
        raise ValueError(f"Profil d'incident inconnu : {profile}")

    return normalize_feature_dict(raw)


def _generate_session_rows(
    rng: np.random.Generator,
    session_id: str,
    profile: str,
    is_incident_session: bool,
    windows_per_session: int = 12,
    inject_single_microspike: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    onset_window = 3 if is_incident_session else windows_per_session + 1
    pre_normal_profile = str(rng.choice(["normal_nominal", "normal_idle", "normal_legitimate_peak"]))
    microspike_window_idx = 6 if (inject_single_microspike and not is_incident_session) else -1

    for w_idx in range(windows_per_session):
        if not is_incident_session or w_idx < onset_window:
            base_prof = profile if not is_incident_session else pre_normal_profile
            is_spike = w_idx == microspike_window_idx
            feats = _sample_normal_window(
                rng,
                base_prof,
                step=w_idx,
                allow_transient_microspike=is_spike,
            )
            label_anomaly = 0
            active_scenario = f"{base_prof}_transient_spike" if is_spike else base_prof
        else:
            feats = _sample_incident_window(rng, profile, incident_step=w_idx - onset_window)
            label_anomaly = 1
            active_scenario = profile

        row: dict[str, Any] = {
            "session_id": session_id,
            "window_index": w_idx,
            "window_seconds": WINDOW_SECONDS,
            "session_profile": profile,
            "window_regime": active_scenario,
            "is_incident_session": int(is_incident_session),
            "label_anomaly": int(label_anomaly),
        }
        row.update(feats)
        rows.append(row)

    return rows


def generate_all_datasets(
    output_dir: Path = DATA_DIR,
    seed: int = SEED,
) -> dict[str, Any]:
    """Génère et sauvegarde les jeux `train_normal_sessions.csv`, `val_sessions.csv`, `test_sessions.csv`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    # 1. Jeu d'entraînement : 75 sessions normales variées (900 fenêtres)
    train_rows: list[dict[str, Any]] = []
    train_counts_per_profile = {
        "normal_idle": 15,
        "normal_nominal": 22,
        "normal_legitimate_peak": 15,
        "normal_benign_4xx": 12,
        "normal_scheduled_audit": 11,
    }
    s_counter = 1
    for prof, n_sess in train_counts_per_profile.items():
        for i in range(n_sess):
            sid = f"TRAIN-S{s_counter:03d}"
            s_counter += 1
            # 1 session de pic légitime sur 15 a une micro-pointe isolée d'une seule fenêtre
            spike = prof == "normal_legitimate_peak" and i == 0
            train_rows.extend(
                _generate_session_rows(
                    rng,
                    session_id=sid,
                    profile=prof,
                    is_incident_session=False,
                    windows_per_session=12,
                    inject_single_microspike=spike,
                )
            )

    # 2. Jeu de validation : 25 sessions normales variées + 15 sessions d'incident (480 fenêtres)
    val_rows: list[dict[str, Any]] = []
    v_counter = 1
    for prof in NORMAL_PROFILES:
        for i in range(5):
            sid = f"VAL-NORM-S{v_counter:03d}"
            v_counter += 1
            spike = prof in ("normal_legitimate_peak", "normal_scheduled_audit") and i == 0
            val_rows.extend(
                _generate_session_rows(
                    rng,
                    session_id=sid,
                    profile=prof,
                    is_incident_session=False,
                    windows_per_session=12,
                    inject_single_microspike=spike,
                )
            )
    for prof in INCIDENT_PROFILES:
        for _ in range(5):
            sid = f"VAL-INC-S{v_counter:03d}"
            v_counter += 1
            val_rows.extend(
                _generate_session_rows(
                    rng, session_id=sid, profile=prof, is_incident_session=True, windows_per_session=12
                )
            )

    # 3. Jeu de test final : 30 sessions normales variées + 18 sessions d'incident (576 fenêtres)
    test_rows: list[dict[str, Any]] = []
    t_counter = 1
    for prof in NORMAL_PROFILES:
        for i in range(6):
            sid = f"TEST-NORM-S{t_counter:03d}"
            t_counter += 1
            # 3 sessions normales (sur 30) contiennent chacune une micro-pointe isolée d'1 fenêtre (5s)
            # permettant de vérifier que la confirmation sur 2 fenêtres consécutives bloque 100 % des fausses alertes.
            spike = prof in ("normal_legitimate_peak", "normal_benign_4xx", "normal_scheduled_audit") and i == 0
            test_rows.extend(
                _generate_session_rows(
                    rng,
                    session_id=sid,
                    profile=prof,
                    is_incident_session=False,
                    windows_per_session=12,
                    inject_single_microspike=spike,
                )
            )
    for prof in INCIDENT_PROFILES:
        for _ in range(6):
            sid = f"TEST-INC-S{t_counter:03d}"
            t_counter += 1
            test_rows.extend(
                _generate_session_rows(
                    rng, session_id=sid, profile=prof, is_incident_session=True, windows_per_session=12
                )
            )

    df_train = pd.DataFrame(train_rows)
    df_val = pd.DataFrame(val_rows)
    df_test = pd.DataFrame(test_rows)

    train_sids = set(df_train["session_id"].unique())
    val_sids = set(df_val["session_id"].unique())
    test_sids = set(df_test["session_id"].unique())
    assert train_sids.isdisjoint(val_sids), "Fuite détectée entre train et val !"
    assert train_sids.isdisjoint(test_sids), "Fuite détectée entre train et test !"
    assert val_sids.isdisjoint(test_sids), "Fuite détectée entre val et test !"
    assert int(df_train["label_anomaly"].sum()) == 0, "Le jeu train ne doit contenir que du trafic normal !"

    train_path = output_dir / "train_normal_sessions.csv"
    val_path = output_dir / "val_sessions.csv"
    test_path = output_dir / "test_sessions.csv"

    df_train.to_csv(train_path, index=False)
    df_val.to_csv(val_path, index=False)
    df_test.to_csv(test_path, index=False)

    summary = {
        "seed": seed,
        "window_seconds": WINDOW_SECONDS,
        "features": FEATURE_NAMES,
        "splits": {
            "train": {
                "path": str(train_path),
                "sessions": int(df_train["session_id"].nunique()),
                "windows": int(len(df_train)),
                "anomaly_windows": int(df_train["label_anomaly"].sum()),
                "profiles": df_train.groupby("session_profile")["session_id"].nunique().to_dict(),
            },
            "val": {
                "path": str(val_path),
                "sessions": int(df_val["session_id"].nunique()),
                "normal_sessions": int(
                    df_val[df_val["is_incident_session"] == 0]["session_id"].nunique()
                ),
                "incident_sessions": int(
                    df_val[df_val["is_incident_session"] == 1]["session_id"].nunique()
                ),
                "windows": int(len(df_val)),
                "anomaly_windows": int(df_val["label_anomaly"].sum()),
                "profiles": df_val.groupby("session_profile")["session_id"].nunique().to_dict(),
            },
            "test": {
                "path": str(test_path),
                "sessions": int(df_test["session_id"].nunique()),
                "normal_sessions": int(
                    df_test[df_test["is_incident_session"] == 0]["session_id"].nunique()
                ),
                "incident_sessions": int(
                    df_test[df_test["is_incident_session"] == 1]["session_id"].nunique()
                ),
                "windows": int(len(df_test)),
                "anomaly_windows": int(df_test["label_anomaly"].sum()),
                "profiles": df_test.groupby("session_profile")["session_id"].nunique().to_dict(),
            },
        },
        "leakage_checks": {
            "disjoint_session_ids": True,
            "train_contains_only_normal": True,
            "hidden_cheat_columns_present": False,
        },
    }
    return summary


if __name__ == "__main__":
    info = generate_all_datasets()
    print(json.dumps(info, indent=2, ensure_ascii=False))
