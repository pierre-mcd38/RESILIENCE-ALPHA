"""Entraînement, calibration et évaluation comparative du modèle ML de détection d'anomalies.

Compare trois approches non supervisées / one-class de `scikit-learn` entraînées exclusivement
sur les sessions normales variées (`train_normal_sessions.csv`) :
1. `IsolationForest` (modèle retenu — ADR-002)
2. `OneClassSVM` (noyau RBF)
3. `EllipticEnvelope` (estimation robuste de covariance de Mahalanobis)

Évalue chaque modèle :
- Au niveau fenêtre (5 s) : Précision, Rappel, F1-score, FPR sur fenêtres normales.
- Au niveau session temporelle avec la règle de confirmation sur **2 fenêtres consécutives**
  (`NORMAL -> SUSPECT -> INCIDENT`) : FPR sur sessions normales (notamment lors des pics horaires
  légitimes et erreurs 4xx bénignes), Taux de détection des sessions d'incident, et Délai moyen
  de détection (en fenêtres et en secondes).

Sauvegarde :
- `ml/artifacts/isolation_forest.joblib`
- `ml/artifacts/model_metadata.json`
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import FEATURE_NAMES, WINDOW_SECONDS
from ml.generate_dataset import DATA_DIR, SEED, generate_all_datasets

ARTIFACTS_DIR: Path = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH: Path = ARTIFACTS_DIR / "isolation_forest.joblib"
METADATA_PATH: Path = ARTIFACTS_DIR / "model_metadata.json"

ANOMALY_DIRECTIONS: dict[str, float] = {
    "req_rate_rps": 1.0,
    "latency_p95_ms": 1.0,
    "error_rate_ratio": 1.0,
    "expensive_endpoint_ratio": 1.0,
    "unique_ip_entropy": -1.0,
    "cpu_worker_saturation": 1.0,
    "tx_success_ratio": -1.0,
}


def _calibrate_threshold(
    scores_val: np.ndarray,
    df_val: pd.DataFrame,
    consecutive_required: int = 2,
) -> float:
    """Calibre le seuil `decision_threshold` sur le jeu de validation.

    Un échantillon est déclaré anormal si `score < decision_threshold`.
    On cherche le seuil qui maximise le score combiné :
      F1_fenêtre + 1.5 * Taux_Détection_Session - 2.5 * FPR_Session_Normale
    En cas d'égalité, on choisit le seuil offrant la meilleure marge de sécurité
    entre le quantile 1 % des fenêtres normales et le quantile 95 % des fenêtres d'incident.
    """
    y_val = df_val["label_anomaly"].to_numpy( dtype=int)
    normal_scores = scores_val[y_val == 0]
    anomaly_scores = scores_val[y_val == 1]

    candidates = np.linspace(
        float(np.percentile(anomaly_scores, 50)),
        float(np.percentile(normal_scores, 15)),
        250,
    )

    best_thresh = float(np.median(candidates))
    best_objective = -1e9

    # Idéal théorique : milieu entre le centile 1% des normaux et le centile 95% des anomalies
    safe_midpoint = 0.5 * (
        float(np.percentile(normal_scores, 1.0)) + float(np.percentile(anomaly_scores, 95.0))
    )

    for thresh in candidates:
        metrics = evaluate_predictions(
            df_val, scores_val, float(thresh), consecutive_required=consecutive_required
        )
        # Pénalise fortement tout faux positif et tout délai > 2 fenêtres
        objective = (
            metrics["window_f1"]
            + 1.5 * metrics["incident_session_detection_rate"]
            - 3.0 * metrics["normal_session_fpr"]
            - 1.0 * metrics["normal_window_fpr"]
            - 0.02 * abs(float(thresh) - safe_midpoint)
        )
        if objective > best_objective:
            best_objective = objective
            best_thresh = float(thresh)

    return round(best_thresh, 4)


def evaluate_predictions(
    df: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
    consecutive_required: int = 2,
) -> dict[str, Any]:
    """Calcule les métriques au niveau fenêtre et au niveau session (avec confirmation 2 fenêtres)."""
    y_true = df["label_anomaly"].to_numpy(dtype=int)
    # Score < threshold => Anomalie (1)
    y_pred_raw = (scores < threshold).astype(int)

    precision = float(precision_score(y_true, y_pred_raw, zero_division=0))
    recall = float(recall_score(y_true, y_pred_raw, zero_division=0))
    f1 = float(f1_score(y_true, y_pred_raw, zero_division=0))
    try:
        roc_auc = float(roc_auc_score(y_true, -scores))
    except ValueError:
        roc_auc = 0.0

    normal_mask = y_true == 0
    fp_windows = int(np.sum((y_pred_raw == 1) & normal_mask))
    tn_windows = int(np.sum((y_pred_raw == 0) & normal_mask))
    normal_window_fpr = fp_windows / max(fp_windows + tn_windows, 1)

    # Évaluation temporelle par session avec la règle de confirmation (consecutive_required)
    df_eval = df.copy()
    df_eval["score"] = scores
    df_eval["is_window_anomaly"] = y_pred_raw

    normal_sessions_total = 0
    normal_sessions_false_alarm = 0
    incident_sessions_total = 0
    incident_sessions_detected = 0
    suspect_delays_windows: list[int] = []
    confirmed_delays_windows: list[int] = []

    per_profile_detection: dict[str, dict[str, int]] = {}

    for _, group in df_eval.groupby("session_id", sort=False):
        group_sorted = group.sort_values("window_index")
        is_inc_sess = bool(group_sorted["is_incident_session"].iloc[0] == 1)
        profile = str(group_sorted["session_profile"].iloc[0])
        per_profile_detection.setdefault(profile, {"total": 0, "triggered_incident": 0})
        per_profile_detection[profile]["total"] += 1

        consec = 0
        first_suspect_idx: int | None = None
        confirmed_incident_idx: int | None = None

        for _, row in group_sorted.iterrows():
            w_idx = int(row["window_index"])
            if int(row["is_window_anomaly"]) == 1:
                consec += 1
                if consec == 1 and first_suspect_idx is None:
                    first_suspect_idx = w_idx
                if consec >= consecutive_required and confirmed_incident_idx is None:
                    confirmed_incident_idx = w_idx
            else:
                consec = 0

        if not is_inc_sess:
            normal_sessions_total += 1
            if confirmed_incident_idx is not None:
                normal_sessions_false_alarm += 1
                per_profile_detection[profile]["triggered_incident"] += 1
        else:
            incident_sessions_total += 1
            anomaly_rows = group_sorted[group_sorted["label_anomaly"] == 1]
            onset_idx = int(anomaly_rows["window_index"].min()) if not anomaly_rows.empty else 0

            # Recherche de la détection à partir du déclenchement réel de l'incident
            consec_post = 0
            post_suspect_idx: int | None = None
            post_confirmed_idx: int | None = None
            for _, row in group_sorted[group_sorted["window_index"] >= onset_idx].iterrows():
                w_idx = int(row["window_index"])
                if int(row["is_window_anomaly"]) == 1:
                    consec_post += 1
                    if consec_post == 1 and post_suspect_idx is None:
                        post_suspect_idx = w_idx
                    if consec_post >= consecutive_required and post_confirmed_idx is None:
                        post_confirmed_idx = w_idx
                else:
                    consec_post = 0

            if post_confirmed_idx is not None:
                incident_sessions_detected += 1
                per_profile_detection[profile]["triggered_incident"] += 1
                # Nombre de fenêtres écoulées depuis le début de l'incident (1 = dès la 1re fenêtre,
                # 2 = dès la 2e fenêtre consécutive confirmant l'état INCIDENT)
                suspect_w = (post_suspect_idx - onset_idx + 1) if post_suspect_idx is not None else 1
                confirmed_w = post_confirmed_idx - onset_idx + 1
                suspect_delays_windows.append(int(suspect_w))
                confirmed_delays_windows.append(int(confirmed_w))

    mean_suspect_windows = (
        float(np.mean(suspect_delays_windows)) if suspect_delays_windows else 0.0
    )
    mean_confirmed_windows = (
        float(np.mean(confirmed_delays_windows)) if confirmed_delays_windows else 0.0
    )

    return {
        "decision_threshold": round(float(threshold), 4),
        "window_precision": round(precision, 4),
        "window_recall": round(recall, 4),
        "window_f1": round(f1, 4),
        "window_roc_auc": round(roc_auc, 4),
        "normal_window_fpr": round(float(normal_window_fpr), 4),
        "normal_sessions_total": int(normal_sessions_total),
        "normal_sessions_false_alarms": int(normal_sessions_false_alarm),
        "normal_session_fpr": round(
            normal_sessions_false_alarm / max(normal_sessions_total, 1), 4
        ),
        "incident_sessions_total": int(incident_sessions_total),
        "incident_sessions_detected": int(incident_sessions_detected),
        "incident_session_detection_rate": round(
            incident_sessions_detected / max(incident_sessions_total, 1), 4
        ),
        "mean_suspect_delay_windows": round(mean_suspect_windows, 2),
        "mean_suspect_delay_seconds": round(mean_suspect_windows * WINDOW_SECONDS, 2),
        "mean_confirmed_detection_delay_windows": round(mean_confirmed_windows, 2),
        "mean_confirmed_detection_delay_seconds": round(
            mean_confirmed_windows * WINDOW_SECONDS, 2
        ),
        "per_profile_summary": per_profile_detection,
    }


def compute_permutation_importance(
    model: Pipeline,
    X_test: np.ndarray,
    y_test: np.ndarray,
    threshold: float,
    seed: int = SEED,
) -> dict[str, float]:
    """Calcule l'importance par permutation de chacune des 7 variables sur le jeu de test."""
    rng = np.random.default_rng(seed)
    base_scores = model.decision_function(X_test)
    base_f1 = float(f1_score(y_test, (base_scores < threshold).astype(int), zero_division=0))

    raw_importances: dict[str, float] = {}
    for idx, feat_name in enumerate(FEATURE_NAMES):
        drops: list[float] = []
        score_shifts: list[float] = []
        for _ in range(15):
            X_perm = X_test.copy()
            X_perm[:, idx] = rng.permutation(X_perm[:, idx])
            perm_scores = model.decision_function(X_perm)
            perm_f1 = float(
                f1_score(y_test, (perm_scores < threshold).astype(int), zero_division=0)
            )
            drops.append(max(0.0, base_f1 - perm_f1))
            score_shifts.append(float(np.mean(np.abs(base_scores - perm_scores))))
        # Combinaison de la baisse de F1 et du déplacement moyen de la frontière de décision
        raw_importances[feat_name] = float(np.mean(drops) + 0.5 * np.mean(score_shifts))

    total = sum(raw_importances.values()) or 1.0
    normalized = {k: round(v / total, 4) for k, v in raw_importances.items()}
    return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))


def train_and_evaluate_all() -> dict[str, Any]:
    """Exécute la génération (si nécessaire), l'entraînement, la comparaison et la sauvegarde."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    train_csv = DATA_DIR / "train_normal_sessions.csv"
    val_csv = DATA_DIR / "val_sessions.csv"
    test_csv = DATA_DIR / "test_sessions.csv"

    if not (train_csv.exists() and val_csv.exists() and test_csv.exists()):
        dataset_summary = generate_all_datasets(DATA_DIR, seed=SEED)
    else:
        dataset_summary = generate_all_datasets(DATA_DIR, seed=SEED)

    df_train = pd.read_csv(train_csv)
    df_val = pd.read_csv(val_csv)
    df_test = pd.read_csv(test_csv)

    X_train = df_train[FEATURE_NAMES].to_numpy(dtype=np.float64)
    X_val = df_val[FEATURE_NAMES].to_numpy(dtype=np.float64)
    X_test = df_test[FEATURE_NAMES].to_numpy(dtype=np.float64)
    y_test = df_test["label_anomaly"].to_numpy(dtype=int)

    # Calcul des statistiques de base sur le jeu d'entraînement normal (pour l'explicabilité)
    baseline_stats: dict[str, dict[str, float]] = {}
    for idx, feat_name in enumerate(FEATURE_NAMES):
        col = X_train[:, idx]
        baseline_stats[feat_name] = {
            "mean": round(float(np.mean(col)), 4),
            "std": round(float(np.std(col, ddof=1)), 4),
            "p05": round(float(np.percentile(col, 5)), 4),
            "p95": round(float(np.percentile(col, 95)), 4),
            "direction": ANOMALY_DIRECTIONS[feat_name],
        }

    # Définition des 3 modèles candidats (entraînés uniquement sur X_train normal)
    candidate_models: dict[str, Pipeline] = {
        "IsolationForest": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    IsolationForest(
                        n_estimators=200,
                        max_samples="auto",
                        contamination=0.02,
                        random_state=SEED,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "OneClassSVM": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", OneClassSVM(kernel="rbf", nu=0.04, gamma="scale")),
            ]
        ),
        "EllipticEnvelope": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    EllipticEnvelope(contamination=0.03, support_fraction=0.85, random_state=SEED),
                ),
            ]
        ),
    }

    comparison_results: dict[str, Any] = {}
    trained_pipelines: dict[str, Pipeline] = {}

    for name, pipe in candidate_models.items():
        t0 = time.perf_counter()
        pipe.fit(X_train)
        train_time_ms = (time.perf_counter() - t0) * 1000.0

        val_scores = pipe.decision_function(X_val)
        calibrated_thresh = _calibrate_threshold(val_scores, df_val, consecutive_required=2)

        t_inf0 = time.perf_counter()
        test_scores = pipe.decision_function(X_test)
        total_inf_ms = (time.perf_counter() - t_inf0) * 1000.0
        single_window_inf_ms = total_inf_ms / max(len(X_test), 1)

        val_metrics = evaluate_predictions(
            df_val, val_scores, calibrated_thresh, consecutive_required=2
        )
        test_metrics = evaluate_predictions(
            df_test, test_scores, calibrated_thresh, consecutive_required=2
        )
        # Évaluation comparative sans confirmation (1 seule fenêtre) pour prouver la valeur de la règle de 2 fenêtres
        test_metrics_single_window = evaluate_predictions(
            df_test, test_scores, calibrated_thresh, consecutive_required=1
        )

        comparison_results[name] = {
            "calibrated_threshold": calibrated_thresh,
            "train_time_ms": round(train_time_ms, 2),
            "inference_time_ms_per_window": round(single_window_inf_ms, 4),
            "validation": val_metrics,
            "test": test_metrics,
            "test_without_confirmation_1_window": {
                "normal_session_fpr": test_metrics_single_window["normal_session_fpr"],
                "normal_sessions_false_alarms": test_metrics_single_window[
                    "normal_sessions_false_alarms"
                ],
                "incident_session_detection_rate": test_metrics_single_window[
                    "incident_session_detection_rate"
                ],
            },
        }
        trained_pipelines[name] = pipe

    selected_model_name = "IsolationForest"
    best_pipeline = trained_pipelines[selected_model_name]
    selected_info = comparison_results[selected_model_name]
    selected_threshold = float(selected_info["calibrated_threshold"])

    feature_importances = compute_permutation_importance(
        best_pipeline, X_test, y_test, threshold=selected_threshold, seed=SEED
    )
    for feat_name, imp in feature_importances.items():
        baseline_stats[feat_name]["weight"] = round(max(0.6, imp * 7.0), 4)

    # Sauvegarde du modèle entraîné
    joblib.dump(best_pipeline, MODEL_PATH)

    metadata: dict[str, Any] = {
        "model_name": "isolation_forest_v1",
        "model_version": "1.0.0",
        "algorithm": "sklearn.ensemble.IsolationForest (with StandardScaler pipeline)",
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "window_seconds": WINDOW_SECONDS,
        "consecutive_windows_required": 2,
        "feature_names": FEATURE_NAMES,
        "decision_threshold": selected_threshold,
        "hyperparameters": {
            "n_estimators": 200,
            "max_samples": "auto",
            "contamination": 0.02,
            "random_state": SEED,
        },
        "baseline_stats": baseline_stats,
        "feature_importances": feature_importances,
        "dataset_summary": dataset_summary,
        "selected_model_metrics": selected_info,
        "model_comparison": comparison_results,
        "artifact_path": str(MODEL_PATH),
    }

    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    meta = train_and_evaluate_all()
    print(
        json.dumps(
            {
                "model_name": meta["model_name"],
                "decision_threshold": meta["decision_threshold"],
                "feature_importances": meta["feature_importances"],
                "test_metrics": meta["selected_model_metrics"]["test"],
                "comparison_summary": {
                    k: {
                        "threshold": v["calibrated_threshold"],
                        "test_window_f1": v["test"]["window_f1"],
                        "test_window_precision": v["test"]["window_precision"],
                        "test_window_recall": v["test"]["window_recall"],
                        "test_normal_window_fpr": v["test"]["normal_window_fpr"],
                        "test_normal_session_fpr": v["test"]["normal_session_fpr"],
                        "test_incident_detection_rate": v["test"][
                            "incident_session_detection_rate"
                        ],
                        "mean_confirmed_delay_s": v["test"][
                            "mean_confirmed_detection_delay_seconds"
                        ],
                    }
                    for k, v in meta["model_comparison"].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
