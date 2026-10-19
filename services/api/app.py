"""
PROJECT RESILIENCE-ALPHA — API Métier de Paiement (services/api/app.py)

Fonctionnalités clés :
- Authentification et autorisation RBAC via jeton JWT (vérifié auprès de AuthEngine ou service auth).
- Création de transactions fictives avec montants exacts en centimes (`amount_cents: int`).
- Idempotence stricte via en-tête `Idempotency-Key`.
- Consultation de l'historique et vérification de l'invariant comptable.
- Endpoint d'audit intensif `/api/v1/transactions/verify-batch` illustrant une saturation réaliste
  des workers lors d'un flood applicatif L7, avec recyclage à chaud par l'Exécuteur confiné.
- Exposition de métriques temps réel (Prometheus `/metrics` + `/api/v1/telemetry/window`).
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Deque, Dict, List, Optional, Tuple

import requests
from flask import Flask, Response, g, jsonify, request

from services.api.database import PaymentDatabase
from services.auth.app import AuthEngine

logger = logging.getLogger("resilience.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_structured(event_type: str, level: str = "INFO", **kwargs: Any) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "api",
        "event_type": event_type,
        "level": level,
        **kwargs,
    }
    logger.info(json.dumps(record, ensure_ascii=False))


class ApiRuntimeState:
    """État opérationnel et télémétrique temps réel de l'API métier."""

    def __init__(self, max_worker_slots: int = 4) -> None:
        self.lock = threading.RLock()
        self.max_worker_slots = max_worker_slots
        self.active_expensive_workers = 0
        self.saturated_backlog = 0
        self.worker_generation = 1
        self.connection_pool_generation = 1
        self.last_recycle_at: Optional[str] = None

        # Fenêtre glissante d'événements de requêtes (horodatage, latence_ms, status_code, is_expensive, is_tx_success, source_ip)
        self.recent_requests: Deque[Dict[str, Any]] = collections.deque(maxlen=2000)

        # Compteurs Prometheus
        self.counters: Dict[str, int] = {
            "api_requests_total": 0,
            "api_errors_total": 0,
            "api_transactions_committed_total": 0,
            "api_transactions_idempotent_replay_total": 0,
            "api_verify_batch_calls_total": 0,
            "api_worker_recycles_total": 0,
            "api_pool_resets_total": 0,
        }

    def record_request(
        self,
        *,
        latency_ms: float,
        status_code: int,
        is_expensive: bool,
        is_tx_success: bool,
        source_ip: str,
        path: str,
    ) -> None:
        now = time.time()
        with self.lock:
            self.counters["api_requests_total"] += 1
            if status_code >= 400:
                self.counters["api_errors_total"] += 1
            self.recent_requests.append(
                {
                    "ts": now,
                    "latency_ms": float(latency_ms),
                    "status_code": int(status_code),
                    "is_expensive": bool(is_expensive),
                    "is_tx_success": bool(is_tx_success),
                    "source_ip": str(source_ip or "127.0.0.1"),
                    "path": path,
                }
            )

    def recycle_workers(self) -> Dict[str, Any]:
        """Recycle les workers saturés et purge l'engorgement applicatif."""
        with self.lock:
            previous_active = self.active_expensive_workers
            previous_backlog = self.saturated_backlog
            self.worker_generation += 1
            self.active_expensive_workers = 0
            self.saturated_backlog = 0
            self.counters["api_worker_recycles_total"] += 1
            self.last_recycle_at = datetime.now(timezone.utc).isoformat()
            # Nettoyage des échantillons obsolètes d'avant le recyclage pour refléter l'état sain post-action
            cutoff = time.time() - 1.0
            while self.recent_requests and self.recent_requests[0]["ts"] < cutoff:
                self.recent_requests.popleft()
            return {
                "status": "RECYCLED",
                "worker_generation": self.worker_generation,
                "cleared_active_workers": previous_active,
                "cleared_backlog": previous_backlog,
                "recycled_at": self.last_recycle_at,
            }

    def reset_connection_pool(self) -> Dict[str, Any]:
        with self.lock:
            self.connection_pool_generation += 1
            self.counters["api_pool_resets_total"] += 1
            return {
                "status": "POOL_RESET",
                "connection_pool_generation": self.connection_pool_generation,
                "reset_at": datetime.now(timezone.utc).isoformat(),
            }

    def compute_window_telemetry(self, window_seconds: float = 5.0) -> Dict[str, Any]:
        """Calcule les 7 variables d'observation ML sur les `window_seconds` dernières secondes."""
        now = time.time()
        cutoff = now - window_seconds
        with self.lock:
            samples = [r for r in self.recent_requests if r["ts"] >= cutoff]
            active_workers = self.active_expensive_workers
            backlog = self.saturated_backlog

        total = len(samples)
        if total == 0:
            return {
                "window_seconds": window_seconds,
                "sample_count": 0,
                "features": {
                    "req_rate_rps": 0.5,
                    "latency_p95_ms": 12.0,
                    "error_rate_ratio": 0.0,
                    "expensive_endpoint_ratio": 0.0,
                    "unique_ip_entropy": 1.0,
                    "cpu_worker_saturation": 0.05,
                    "tx_success_ratio": 1.0,
                },
                "dominant_source_ip": "127.0.0.1",
            }

        req_rate_rps = total / max(window_seconds, 1.0)
        latencies = sorted(r["latency_ms"] for r in samples)
        p95_idx = min(len(latencies) - 1, int(math.ceil(0.95 * len(latencies))) - 1)
        latency_p95_ms = float(latencies[max(0, p95_idx)])

        errors = sum(1 for r in samples if r["status_code"] >= 400)
        error_rate_ratio = errors / total

        expensive_count = sum(1 for r in samples if r["is_expensive"])
        expensive_endpoint_ratio = expensive_count / total

        tx_success_count = sum(1 for r in samples if r["is_tx_success"])
        tx_attempts = sum(1 for r in samples if r["path"].startswith("/api/v1/transactions") and not r["is_expensive"])
        if tx_attempts > 0:
            tx_success_ratio = tx_success_count / tx_attempts
        else:
            tx_success_ratio = max(0.0, 1.0 - (0.8 * expensive_endpoint_ratio) - (0.5 * error_rate_ratio))

        # Entropie de distribution des adresses IP sources
        ip_counts: Dict[str, int] = {}
        for r in samples:
            ip = r["source_ip"]
            ip_counts[ip] = ip_counts.get(ip, 0) + 1
        dominant_source_ip = max(ip_counts.items(), key=lambda kv: kv[1])[0]
        if len(ip_counts) <= 1:
            unique_ip_entropy = 0.05 if total > 10 else 0.85
        else:
            raw_entropy = -sum((c / total) * math.log2(c / total) for c in ip_counts.values())
            max_entropy = math.log2(max(len(ip_counts), 2))
            unique_ip_entropy = min(1.0, raw_entropy / max_entropy)

        saturation_from_workers = min(1.0, (active_workers + backlog * 0.5) / max(self.max_worker_slots, 1))
        saturation_from_load = min(1.0, (expensive_count / max(window_seconds * 4.0, 1.0)))
        cpu_worker_saturation = round(max(0.05, min(1.0, max(saturation_from_workers, saturation_from_load))), 4)

        return {
            "window_seconds": window_seconds,
            "sample_count": total,
            "features": {
                "req_rate_rps": round(req_rate_rps, 3),
                "latency_p95_ms": round(latency_p95_ms, 2),
                "error_rate_ratio": round(error_rate_ratio, 4),
                "expensive_endpoint_ratio": round(expensive_endpoint_ratio, 4),
                "unique_ip_entropy": round(unique_ip_entropy, 4),
                "cpu_worker_saturation": cpu_worker_saturation,
                "tx_success_ratio": round(max(0.0, min(1.0, tx_success_ratio)), 4),
            },
            "dominant_source_ip": dominant_source_ip,
        }


def parse_exact_amount_cents(data: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    """
    Valide et extrait le montant en centimes entiers sans imprécision flottante.
    Accepte :
    - `amount_cents`: int strict (ni bool, ni float), ex. 2500
    - ou `amount_decimal`: str exacte avec max 2 décimales, ex. "25.00"
    """
    if "amount_cents" in data and data["amount_cents"] is not None:
        raw = data["amount_cents"]
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None, "Le champ amount_cents doit être un entier exact (les flottants sont interdits)."
        if raw <= 0:
            return None, "Le montant amount_cents doit être strictement supérieur à 0."
        if raw > 10_000_000:
            return None, "Le montant dépasse le plafond autorisé par transaction (100 000,00 EUR)."
        return raw, None

    if "amount_decimal" in data and data["amount_decimal"] is not None:
        raw_dec = data["amount_decimal"]
        if isinstance(raw_dec, float):
            return None, "Les nombres flottants IEEE 754 sont refusés ; utilisez amount_cents (entier) ou une chaîne décimale exacte."
        try:
            d = Decimal(str(raw_dec))
        except InvalidOperation:
            return None, "Format décimal invalide."
        if d.as_tuple().exponent < -2:
            return None, "Précision maximale autorisée : 2 décimales (centimes)."
        cents = int((d * Decimal("100")).to_integral_exact())
        if cents <= 0 or cents > 10_000_000:
            return None, "Montant hors bornes autorisées (0,01 EUR à 100 000,00 EUR)."
        return cents, None

    return None, "Montant requis (amount_cents entier)."


def create_api_app(
    db: Optional[PaymentDatabase] = None,
    auth_engine: Optional[AuthEngine] = None,
    runtime_state: Optional[ApiRuntimeState] = None,
) -> Flask:
    app = Flask(__name__)
    payment_db = db or PaymentDatabase()
    local_auth = auth_engine or AuthEngine()
    state = runtime_state or ApiRuntimeState()
    auth_service_url = os.environ.get("AUTH_SERVICE_URL", "").strip()
    internal_control_secret = os.environ.get(
        "INTERNAL_CONTROL_TOKEN",
        "resilience-internal-control-token-2026",
    )

    app.config["PAYMENT_DB"] = payment_db
    app.config["AUTH_ENGINE"] = local_auth
    app.config["RUNTIME_STATE"] = state

    def verify_request_token() -> Tuple[bool, Dict[str, Any]]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return False, {"error": "En-tête Authorization Bearer manquant."}
        if auth_service_url:
            try:
                resp = requests.post(
                    f"{auth_service_url.rstrip('/')}/auth/v1/verify",
                    json={"token": auth_header},
                    timeout=2.0,
                )
                return resp.status_code == 200, resp.json()
            except Exception:
                pass
        return local_auth.verify_jwt(auth_header)

    @app.before_request
    def _before_request() -> None:
        g.start_time = time.perf_counter()
        g.correlation_id = request.headers.get("X-Correlation-ID", f"corr-{uuid.uuid4().hex[:10]}")
        g.source_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        g.is_expensive = False
        g.is_tx_success = False

    @app.after_request
    def _after_request(response: Response) -> Response:
        start = getattr(g, "start_time", None)
        latency_ms = (time.perf_counter() - start) * 1000.0 if start is not None else 1.0
        response.headers["X-Correlation-ID"] = getattr(g, "correlation_id", "")
        response.headers["X-Response-Time-Ms"] = f"{latency_ms:.2f}"
        if request.path not in ("/metrics", "/api/v1/telemetry/window"):
            state.record_request(
                latency_ms=latency_ms,
                status_code=response.status_code,
                is_expensive=getattr(g, "is_expensive", False),
                is_tx_success=getattr(g, "is_tx_success", False),
                source_ip=getattr(g, "source_ip", "127.0.0.1"),
                path=request.path,
            )
        return response

    @app.route("/health", methods=["GET"])
    def health() -> Tuple[Response, int]:
        # Si le backlog de saturation dépasse le seuil critique, la latence et l'état reflètent la dégradation réelle
        with state.lock:
            backlog = state.saturated_backlog
            active_w = state.active_expensive_workers
        if backlog > 6:
            time.sleep(min(0.35, backlog * 0.03))
        invariant = payment_db.check_accounting_invariant()
        degraded = backlog >= 4 or active_w >= state.max_worker_slots
        status_code = 503 if backlog >= 10 else 200
        return jsonify({
            "status": "DEGRADED" if degraded else "UP",
            "service": "api",
            "worker_generation": state.worker_generation,
            "active_expensive_workers": active_w,
            "saturated_backlog": backlog,
            "accounting_invariant_ok": invariant["consistent"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), status_code

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        tel = state.compute_window_telemetry(5.0)
        feat = tel["features"]
        c = state.counters
        lines = [
            "# HELP api_requests_total Nombre total de requetes HTTP traitees par l'API",
            "# TYPE api_requests_total counter",
            f"api_requests_total {c['api_requests_total']}",
            "# HELP api_errors_total Nombre total de reponses HTTP >= 400",
            "# TYPE api_errors_total counter",
            f"api_errors_total {c['api_errors_total']}",
            "# HELP api_transactions_committed_total Nombre total de transactions fictives validees",
            "# TYPE api_transactions_committed_total counter",
            f"api_transactions_committed_total {c['api_transactions_committed_total']}",
            "# HELP api_transactions_idempotent_replay_total Nombre de rejeux idempotents absorbes sans doublon",
            "# TYPE api_transactions_idempotent_replay_total counter",
            f"api_transactions_idempotent_replay_total {c['api_transactions_idempotent_replay_total']}",
            "# HELP api_latency_p95_ms Latence P95 sur la fenetre glissante de 5s",
            "# TYPE api_latency_p95_ms gauge",
            f"api_latency_p95_ms {feat['latency_p95_ms']}",
            "# HELP api_cpu_worker_saturation Taux de saturation des workers applicatifs (0..1)",
            "# TYPE api_cpu_worker_saturation gauge",
            f"api_cpu_worker_saturation {feat['cpu_worker_saturation']}",
            "# HELP api_worker_recycles_total Nombre de recyclages de workers declenches par la remediation",
            "# TYPE api_worker_recycles_total counter",
            f"api_worker_recycles_total {c['api_worker_recycles_total']}",
        ]
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

    @app.route("/api/v1/telemetry/window", methods=["GET"])
    def telemetry_window() -> Tuple[Response, int]:
        window_s = float(request.args.get("window_seconds", "5.0"))
        return jsonify(state.compute_window_telemetry(window_s)), 200

    @app.route("/api/v1/accounts", methods=["GET"])
    def list_accounts() -> Tuple[Response, int]:
        valid, claims = verify_request_token()
        if not valid:
            return jsonify({"error": claims.get("error", "Non autorisé")}), 401
        if "accounts:read" not in claims.get("permissions", []):
            return jsonify({"error": "Permission accounts:read requise."}), 403
        accounts = payment_db.list_accounts()
        invariant = payment_db.check_accounting_invariant()
        return jsonify({"accounts": accounts, "invariant": invariant}), 200

    @app.route("/api/v1/transactions", methods=["GET"])
    def list_transactions() -> Tuple[Response, int]:
        valid, claims = verify_request_token()
        if not valid:
            return jsonify({"error": claims.get("error", "Non autorisé")}), 401
        if "transactions:read" not in claims.get("permissions", []):
            return jsonify({"error": "Permission transactions:read requise."}), 403
        limit = int(request.args.get("limit", "50"))
        txs = payment_db.list_transactions(limit=limit)
        return jsonify({"transactions": txs, "count": len(txs)}), 200

    @app.route("/api/v1/transactions/<tx_id>", methods=["GET"])
    def get_transaction(tx_id: str) -> Tuple[Response, int]:
        valid, claims = verify_request_token()
        if not valid:
            return jsonify({"error": claims.get("error", "Non autorisé")}), 401
        if "transactions:read" not in claims.get("permissions", []):
            return jsonify({"error": "Permission transactions:read requise."}), 403
        tx = payment_db.get_transaction(tx_id)
        if tx is None:
            return jsonify({"error": "Transaction introuvable."}), 404
        return jsonify(tx), 200

    @app.route("/api/v1/transactions", methods=["POST"])
    def create_transaction() -> Tuple[Response, int]:
        valid, claims = verify_request_token()
        if not valid:
            return jsonify({"error": claims.get("error", "Non autorisé")}), 401
        if "transactions:create" not in claims.get("permissions", []):
            return jsonify({"error": "Accès refusé : permission transactions:create requise."}), 403

        # Effet réel de la saturation des workers sur les paiements légitimes
        with state.lock:
            backlog = state.saturated_backlog
            active_w = state.active_expensive_workers
        if backlog >= 8 or active_w >= state.max_worker_slots:
            time.sleep(min(0.45, 0.08 * max(backlog, active_w)))
            if backlog >= 12:
                log_structured(
                    "transaction_rejected_saturation",
                    level="ERROR",
                    correlation_id=g.correlation_id,
                    source_ip=g.source_ip,
                    saturated_backlog=backlog,
                )
                return jsonify({
                    "error": "Service temporairement saturé (file de workers pleine).",
                    "code": "WORKER_POOL_SATURATED",
                    "correlation_id": g.correlation_id,
                }), 503

        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            return jsonify({
                "error": "En-tête Idempotency-Key obligatoire (1 à 128 caractères).",
                "code": "MISSING_IDEMPOTENCY_KEY",
            }), 400

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Corps JSON invalide."}), 400

        amount_cents, amount_err = parse_exact_amount_cents(data)
        if amount_err or amount_cents is None:
            return jsonify({"error": amount_err, "code": "INVALID_AMOUNT"}), 422

        source_account_id = str(data.get("source_account_id", "")).strip()
        target_account_id = str(data.get("target_account_id", "")).strip()
        currency = str(data.get("currency", "EUR")).strip().upper()
        description = str(data.get("description", "Paiement fictif RESILIENCE-ALPHA")).strip()

        if not source_account_id or not target_account_id:
            return jsonify({"error": "Comptes source_account_id et target_account_id obligatoires."}), 422
        if source_account_id == target_account_id:
            return jsonify({"error": "Le compte source et le compte bénéficiaire doivent être distincts."}), 422

        result, status_code = payment_db.execute_transfer(
            idempotency_key=idempotency_key,
            source_account_id=source_account_id,
            target_account_id=target_account_id,
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            initiated_by=str(claims.get("subject", "unknown")),
            correlation_id=g.correlation_id,
        )

        if status_code in (200, 201):
            g.is_tx_success = True
            with state.lock:
                if result.get("idempotent_replay"):
                    state.counters["api_transactions_idempotent_replay_total"] += 1
                else:
                    state.counters["api_transactions_committed_total"] += 1
            log_structured(
                "transaction_processed",
                level="INFO",
                tx_id=result.get("tx_id"),
                amount_cents=amount_cents,
                currency=currency,
                source_account_id=source_account_id,
                target_account_id=target_account_id,
                idempotent_replay=result.get("idempotent_replay", False),
                initiated_by=claims.get("subject"),
                correlation_id=g.correlation_id,
            )
        else:
            log_structured(
                "transaction_failed",
                level="WARNING",
                reason=result.get("code", "VALIDATION_ERROR"),
                status_code=status_code,
                correlation_id=g.correlation_id,
            )

        return jsonify(result), status_code

    @app.route("/api/v1/transactions/verify-batch", methods=["POST"])
    def verify_batch() -> Tuple[Response, int]:
        """
        Opération d'audit et de rapprochement cryptographique de lots de transactions.
        Légitime à faible fréquence, mais volontairement coûteuse en CPU/latence lorsqu'elle
        est appelée en rafale concurrente (scénario de démonstration de dégradation L7).
        """
        g.is_expensive = True
        data = request.get_json(silent=True) or {}
        batch_size = max(1, min(int(data.get("batch_size", 25)), 100))
        iterations = max(5_000, min(int(data.get("iterations", 35_000)), 80_000))

        with state.lock:
            state.counters["api_verify_batch_calls_total"] += 1
            state.active_expensive_workers += 1
            if state.active_expensive_workers > state.max_worker_slots:
                state.saturated_backlog += 2
            else:
                state.saturated_backlog = min(20, state.saturated_backlog + 1)
            current_gen = state.worker_generation
            current_backlog = state.saturated_backlog

        try:
            # Travail CPU réel + contention proportionnelle à l'engorgement des workers
            digest = b"resilience-alpha-ledger-seed"
            for i in range(batch_size):
                if state.worker_generation != current_gen:
                    # Interruption immédiate si l'Exécuteur recycle les workers pendant le calcul !
                    return jsonify({
                        "status": "ABORTED_BY_WORKER_RECYCLE",
                        "worker_generation": state.worker_generation,
                    }), 503
                digest = hashlib.pbkdf2_hmac("sha256", digest, f"batch-{i}".encode("utf-8"), iterations // batch_size)

            # Contention de file d'attente observable
            contention_delay = min(0.85, 0.06 * current_backlog)
            if contention_delay > 0:
                time.sleep(contention_delay)

            status_code = 503 if current_backlog >= 10 else 200
            return jsonify({
                "status": "DEGRADED_BATCH" if status_code == 503 else "VERIFIED",
                "batch_size": batch_size,
                "verification_digest": digest.hex()[:32],
                "saturated_backlog": current_backlog,
                "correlation_id": g.correlation_id,
            }), status_code
        finally:
            with state.lock:
                state.active_expensive_workers = max(0, state.active_expensive_workers - 1)

    @app.route("/internal/v1/admin/recycle-workers", methods=["POST"])
    def internal_recycle_workers() -> Tuple[Response, int]:
        token = request.headers.get("X-Internal-Control-Token", "")
        if token != internal_control_secret:
            return jsonify({"error": "Jeton de contrôle interne invalide."}), 403
        res = state.recycle_workers()
        log_structured("workers_recycled_by_executor", level="INFO", **res)
        return jsonify(res), 200

    @app.route("/internal/v1/admin/reset-pool", methods=["POST"])
    def internal_reset_pool() -> Tuple[Response, int]:
        token = request.headers.get("X-Internal-Control-Token", "")
        if token != internal_control_secret:
            return jsonify({"error": "Jeton de contrôle interne invalide."}), 403
        res = state.reset_connection_pool()
        log_structured("connection_pool_reset_by_executor", level="INFO", **res)
        return jsonify(res), 200

    return app


app = create_api_app()

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", "8001"))
    app.run(host="0.0.0.0", port=port, threaded=True)
