"""Service d'inférence ML (`IsolationForest`) pour PROJECT RESILIENCE-ALPHA (`services/detector`).

Ce module fournit :
1. Une classe Python appelable directement (`AnomalyDetectorEngine`) pour les tests unitaires,
   les répétitions d'intégration locales et l'orchestration AIOps.
2. Un serveur HTTP REST (`Flask` / WSGI) sur le port `8003` exposant :
   - `GET /health`
   - `GET /metrics` (format Prometheus : `detector_anomaly_score`, `detector_is_anomaly`,
     `detector_inferences_total`, `detector_consecutive_anomalies`)
   - `GET /status` (métadonnées du modèle chargé, seuil calibré et dernier événement évalué)
   - `POST /evaluate` (évalue une fenêtre de 5s, met à jour `consecutive_anomalies`, retourne
     un `AnomalyEvent` conforme à `docs/contracts.md`, et peut le pousser à `services/remediator`)
   - `POST /reset` (réinitialise le compteur d'anomalies consécutives)
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import joblib
import requests
from flask import Flask, Response, jsonify, request

ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import (
    FEATURE_NAMES,
    WINDOW_SECONDS,
    compute_top_contributing_features,
    extract_window_features,
    features_to_vector,
)
from ml.train_evaluate import METADATA_PATH, MODEL_PATH, train_and_evaluate_all


class AnomalyDetectorEngine:
    """Moteur d'inférence temps réel encapsulant le modèle `IsolationForest` calibré."""

    def __init__(
        self,
        model_path: Path | str = MODEL_PATH,
        metadata_path: Path | str = METADATA_PATH,
        remediator_url: str | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.remediator_url = (
            remediator_url
            or os.environ.get("REMEDIATOR_URL")
            or "http://remediator:8004"
        ).rstrip("/")
        self.auto_push_remediator = (
            os.environ.get("DETECTOR_AUTO_PUSH", "false").lower() in ("1", "true", "yes")
        )

        self._lock = threading.Lock()
        self._ensure_artifacts_loaded()

        self.inferences_total: int = 0
        self.anomalies_total: int = 0
        self.consecutive_anomalies: int = 0
        self.last_score: float = 0.0
        self.last_is_anomaly: bool = False
        self.last_attack_type: str = "NOMINAL"
        self.anomalies_by_type: dict[str, int] = {
            "FLOOD_L7_VERIFY_BATCH": 0,
            "BRUTE_FORCE_AUTH_JWT": 0,
            "INJECTION_L7_SQLI_XSS": 0,
            "SATURATION_LATENCE_DOS": 0,
        }
        self.last_event: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []

    def _ensure_artifacts_loaded(self) -> None:
        if not self.model_path.exists() or not self.metadata_path.exists():
            train_and_evaluate_all()

        self.pipeline = joblib.load(self.model_path)
        self.metadata: dict[str, Any] = json.loads(
            self.metadata_path.read_text(encoding="utf-8")
        )
        self.model_name: str = str(self.metadata.get("model_name", "isolation_forest_v1"))
        self.model_version: str = str(self.metadata.get("model_version", "1.0.0"))
        self.window_seconds: int = int(self.metadata.get("window_seconds", WINDOW_SECONDS))
        self.decision_threshold: float = float(
            self.metadata.get("decision_threshold", -0.0850)
        )
        self.baseline_stats: dict[str, dict[str, float]] = self.metadata.get(
            "baseline_stats", {}
        )
        self.feature_importances: dict[str, float] = self.metadata.get(
            "feature_importances", {}
        )

    def reset_state(self) -> None:
        """Réinitialise le compteur d'anomalies consécutives (ex: après reprise vérifiée)."""
        with self._lock:
            self.consecutive_anomalies = 0
            self.last_is_anomaly = False
            self.last_attack_type = "NOMINAL"

    def _classify_attack_vector(
        self,
        features: Mapping[str, float],
        payload: Mapping[str, Any],
        is_anomaly: bool,
    ) -> str:
        if not is_anomaly:
            return "NOMINAL"
        sig_hits = int(payload.get("waf_signature_hits", 0))
        auth_reqs = int(payload.get("waf_auth_requests", 0))
        if sig_hits > 0:
            return "INJECTION_L7_SQLI_XSS"
        if auth_reqs >= 4 or (
            float(features.get("error_rate_ratio", 0.0)) >= 0.40
            and float(features.get("expensive_endpoint_ratio", 0.0)) < 0.45
        ):
            return "BRUTE_FORCE_AUTH_JWT"
        if float(features.get("expensive_endpoint_ratio", 0.0)) >= 0.35 and float(
            features.get("req_rate_rps", 0.0)
        ) >= 1.5:
            return "FLOOD_L7_VERIFY_BATCH"
        return "SATURATION_LATENCE_DOS"

    def _resolve_dominant_ip(self, payload: Mapping[str, Any]) -> str:
        if "dominant_source_ip" in payload and payload["dominant_source_ip"]:
            return str(payload["dominant_source_ip"])
        ip_counts = payload.get("ip_counts")
        if isinstance(ip_counts, Mapping) and ip_counts:
            top_ip = max(ip_counts.items(), key=lambda kv: int(kv[1]))[0]
            return str(top_ip)
        return "127.0.0.1"

    def evaluate_window(
        self,
        payload: Mapping[str, Any],
        push_to_remediator: bool | None = None,
    ) -> dict[str, Any]:
        """Évalue une fenêtre d'observation de 5 secondes et génère un `AnomalyEvent`."""
        window_sec = int(payload.get("window_seconds", self.window_seconds))
        features = extract_window_features(payload, window_seconds=float(window_sec))
        vec = features_to_vector(features).reshape(1, -1)

        raw_score = float(self.pipeline.decision_function(vec)[0])
        anomaly_score = round(raw_score, 4)
        is_anomaly = bool(raw_score < self.decision_threshold)
        attack_type = self._classify_attack_vector(features, payload, is_anomaly)

        top_features = compute_top_contributing_features(
            features,
            baseline_stats=self.baseline_stats,
            feature_importances=self.feature_importances,
            top_k=3,
        )
        dominant_ip = self._resolve_dominant_ip(payload)

        now_utc = datetime.now(timezone.utc)
        with self._lock:
            self.inferences_total += 1
            if is_anomaly:
                self.anomalies_total += 1
                self.consecutive_anomalies += 1
                self.anomalies_by_type[attack_type] = (
                    self.anomalies_by_type.get(attack_type, 0) + 1
                )
            else:
                self.consecutive_anomalies = 0

            seq_num = self.inferences_total
            consec = self.consecutive_anomalies
            self.last_score = anomaly_score
            self.last_is_anomaly = is_anomaly
            self.last_attack_type = attack_type

            event: dict[str, Any] = {
                "event_id": str(
                    payload.get(
                        "event_id",
                        f"evt-ml-{now_utc.strftime('%Y%m%d')}-{seq_num:04d}",
                    )
                ),
                "timestamp": str(
                    payload.get("timestamp", now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
                ),
                "model_name": self.model_name,
                "model_version": self.model_version,
                "window_seconds": window_sec,
                "anomaly_score": anomaly_score,
                "decision_threshold": round(self.decision_threshold, 4),
                "is_anomaly": is_anomaly,
                "detected_attack_type": attack_type,
                "consecutive_anomalies": consec,
                "features": features,
                "top_contributing_features": top_features,
                "dominant_source_ip": dominant_ip,
            }

            self.last_event = event
            self.history.append(event)
            if len(self.history) > 200:
                self.history = self.history[-200:]

        should_push = (
            bool(push_to_remediator)
            if push_to_remediator is not None
            else (self.auto_push_remediator and is_anomaly)
        )
        if should_push:
            target_url = str(
                payload.get(
                    "remediator_endpoint",
                    f"{self.remediator_url}/soc/v1/anomaly-events",
                )
            )
            try:
                resp = requests.post(target_url, json=event, timeout=2.5)
                event["remediator_delivery"] = {
                    "pushed": True,
                    "status_code": resp.status_code,
                }
            except Exception as exc:
                event["remediator_delivery"] = {
                    "pushed": False,
                    "error": str(exc),
                }

        return event

    def get_status(self) -> dict[str, Any]:
        """Retourne l'état courant du moteur et les métadonnées principales du modèle."""
        with self._lock:
            return {
                "service": "detector",
                "status": "UP",
                "model_name": self.model_name,
                "model_version": self.model_version,
                "algorithm": self.metadata.get("algorithm"),
                "window_seconds": self.window_seconds,
                "decision_threshold": self.decision_threshold,
                "consecutive_windows_required": self.metadata.get(
                    "consecutive_windows_required", 2
                ),
                "feature_names": FEATURE_NAMES,
                "feature_importances": self.feature_importances,
                "inferences_total": self.inferences_total,
                "anomalies_total": self.anomalies_total,
                "anomalies_by_type": dict(self.anomalies_by_type),
                "consecutive_anomalies": self.consecutive_anomalies,
                "last_score": self.last_score,
                "last_is_anomaly": self.last_is_anomaly,
                "last_attack_type": self.last_attack_type,
                "last_event": self.last_event,
            }

    def render_prometheus_metrics(self) -> str:
        """Génère l'exposition texte Prometheus (`/metrics`)."""
        with self._lock:
            score_val = float(self.last_score)
            is_anom_val = 1 if self.last_is_anomaly else 0
            inf_total = int(self.inferences_total)
            anom_total = int(self.anomalies_total)
            consec_val = int(self.consecutive_anomalies)
            thresh_val = float(self.decision_threshold)
            by_type = dict(self.anomalies_by_type)

        lines = [
            "# HELP detector_anomaly_score Dernier score continu IsolationForest (negatif sous le seuil = anomalie).",
            "# TYPE detector_anomaly_score gauge",
            f"detector_anomaly_score {score_val:.4f}",
            "# HELP detector_is_anomaly Indicateur binaire d'anomalie sur la derniere fenetre (1=anomalie, 0=normal).",
            "# TYPE detector_is_anomaly gauge",
            f"detector_is_anomaly {is_anom_val}",
            "# HELP detector_inferences_total Nombre total de fenetres evaluees par le modele ML.",
            "# TYPE detector_inferences_total counter",
            f"detector_inferences_total {inf_total}",
            "# HELP detector_anomalies_total Nombre total de fenetres classees anormales.",
            "# TYPE detector_anomalies_total counter",
            f"detector_anomalies_total {anom_total}",
            "# HELP detector_consecutive_anomalies Compteur courant de fenetres anormales consecutives.",
            "# TYPE detector_consecutive_anomalies gauge",
            f"detector_consecutive_anomalies {consec_val}",
            "# HELP detector_decision_threshold Seuil de decision calibre du modele IsolationForest.",
            "# TYPE detector_decision_threshold gauge",
            f"detector_decision_threshold {thresh_val:.4f}",
            "# HELP detector_attacks_by_type_total Nombre d'attaques detectees par le modele IA selon le vecteur.",
            "# TYPE detector_attacks_by_type_total counter",
        ]
        for k, v in by_type.items():
            lines.append(f'detector_attacks_by_type_total{{attack_type="{k}"}} {v}')
        lines.append("")
        return "\n".join(lines)


detector_engine = AnomalyDetectorEngine()


def create_app(engine: AnomalyDetectorEngine | None = None) -> Flask:
    """Construit l'application WSGI Flask pour `services/detector`."""
    active_engine = engine or detector_engine
    flask_app = Flask(__name__)

    @flask_app.get("/health")
    def health() -> tuple[Response, int]:
        return (
            jsonify(
                {
                    "status": "UP",
                    "service": "detector",
                    "model_loaded": True,
                    "model_name": active_engine.model_name,
                    "model_version": active_engine.model_version,
                    "decision_threshold": active_engine.decision_threshold,
                }
            ),
            200,
        )

    @flask_app.get("/metrics")
    def metrics() -> Response:
        body = active_engine.render_prometheus_metrics()
        return Response(body, status=200, mimetype="text/plain; version=0.0.4; charset=utf-8")

    @flask_app.get("/status")
    def status() -> tuple[Response, int]:
        return jsonify(active_engine.get_status()), 200

    @flask_app.post("/evaluate")
    def evaluate() -> tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, Mapping):
            return (
                jsonify({"error": "Invalid JSON payload; expected object with window features."}),
                400,
            )
        push_flag = payload.get("push_to_remediator")
        event = active_engine.evaluate_window(
            payload,
            push_to_remediator=bool(push_flag) if push_flag is not None else None,
        )
        return jsonify(event), 200

    @flask_app.post("/reset")
    def reset() -> tuple[Response, int]:
        active_engine.reset_state()
        return jsonify({"status": "RESET_OK", "consecutive_anomalies": 0}), 200

    return flask_app


app = create_app(detector_engine)


if __name__ == "__main__":
    port = int(os.environ.get("DETECTOR_PORT", "8003"))
    app.run(host="0.0.0.0", port=port, debug=False)
