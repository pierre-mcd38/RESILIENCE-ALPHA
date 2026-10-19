"""
PROJECT RESILIENCE-ALPHA — Service d'Authentification et RBAC (services/auth/app.py)

Responsabilités :
- Authentification des utilisateurs et services fictifs (sans aucun secret réel).
- Émission de jetons JWT signés HMAC-SHA256 (HS256) avec expiration et rôle RBAC.
- Vérification de jetons JWT pour l'API métier, la sonde de résilience et le SOC.
- Journalisation structurée JSON sans jamais exposer les mots de passe ou clés secrètes.
- Exposition des métriques Prometheus sur GET /metrics.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Flask, Response, jsonify, request

# Configuration du journal structuré JSON (sans secret)
logger = logging.getLogger("resilience.auth")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_structured(event_type: str, level: str = "INFO", **kwargs: Any) -> None:
    """Émet un journal structuré JSON exempt de secrets."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "auth",
        "event_type": event_type,
        "level": level,
        **kwargs,
    }
    logger.info(json.dumps(record, ensure_ascii=False))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode((segment + padding).encode("ascii"))


def _hash_password_pbkdf2(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class AuthEngine:
    """Moteur d'authentification JWT et RBAC déterministe et sans fuite de secret."""

    def __init__(self, jwt_secret: Optional[str] = None, token_ttl_seconds: int = 3600) -> None:
        raw_secret = jwt_secret or os.environ.get(
            "RESILIENCE_JWT_SECRET",
            "fictive-lab-jwt-key-do-not-use-in-prod-2026-resilience-alpha",
        )
        self._jwt_secret: bytes = raw_secret.encode("utf-8")
        self.token_ttl_seconds = token_ttl_seconds
        self._lock = threading.Lock()

        # Métriques internes Prometheus
        self.metrics: Dict[str, int] = {
            "auth_login_success_total": 0,
            "auth_login_failure_total": 0,
            "auth_token_verify_success_total": 0,
            "auth_token_verify_failure_total": 0,
        }

        # Comptes fictifs du laboratoire (mots de passe hachés PBKDF2-HMAC-SHA256 en mémoire)
        self._users: Dict[str, Dict[str, Any]] = {}
        self._seed_fictive_users()

    def _seed_fictive_users(self) -> None:
        default_accounts = [
            (
                "operator_alpha",
                os.environ.get("OPERATOR_PASSWORD", "FictiveOp#2026!"),
                "merchant_operator",
                ["transactions:create", "transactions:read", "accounts:read", "soc:read"],
            ),
            (
                "resilience_probe",
                os.environ.get("PROBE_PASSWORD", "FictiveProbe#2026!"),
                "resilience_probe",
                ["transactions:create", "transactions:read", "accounts:read"],
            ),
            (
                "auditor_readonly",
                os.environ.get("AUDITOR_PASSWORD", "FictiveAudit#2026!"),
                "auditor_readonly",
                ["transactions:read", "accounts:read", "soc:read"],
            ),
        ]
        for username, password, role, permissions in default_accounts:
            salt = hashlib.sha256(f"salt:{username}".encode("utf-8")).digest()[:16]
            self._users[username] = {
                "username": username,
                "salt": salt,
                "password_hash": _hash_password_pbkdf2(password, salt),
                "role": role,
                "permissions": permissions,
                "active": True,
            }

    def issue_jwt(self, subject: str, role: str, permissions: list[str], ttl: Optional[int] = None) -> Dict[str, Any]:
        now = int(time.time())
        exp = now + (ttl if ttl is not None else self.token_ttl_seconds)
        jti = str(uuid.uuid4())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": "resilience-alpha-auth",
            "sub": subject,
            "role": role,
            "permissions": permissions,
            "iat": now,
            "exp": exp,
            "jti": jti,
        }
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = hmac.new(self._jwt_secret, signing_input, hashlib.sha256).digest()
        token = f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": exp - now,
            "exp": exp,
            "role": role,
            "subject": subject,
            "permissions": permissions,
        }

    def authenticate(self, username: str, password: str, correlation_id: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not username or not password or not isinstance(username, str) or not isinstance(password, str):
            with self._lock:
                self.metrics["auth_login_failure_total"] += 1
            log_structured(
                "auth_login_failed",
                level="WARNING",
                username=str(username)[:64],
                reason="missing_credentials",
                correlation_id=correlation_id,
            )
            return None, "Identifiants manquants ou invalides."

        user = self._users.get(username)
        if not user or not user.get("active", False):
            with self._lock:
                self.metrics["auth_login_failure_total"] += 1
            log_structured(
                "auth_login_failed",
                level="WARNING",
                username=username[:64],
                reason="unknown_or_inactive_user",
                correlation_id=correlation_id,
            )
            return None, "Utilisateur inconnu ou mot de passe incorrect."

        candidate_hash = _hash_password_pbkdf2(password, user["salt"])
        if not hmac.compare_digest(candidate_hash, user["password_hash"]):
            with self._lock:
                self.metrics["auth_login_failure_total"] += 1
            log_structured(
                "auth_login_failed",
                level="WARNING",
                username=username,
                reason="bad_password",
                correlation_id=correlation_id,
            )
            return None, "Utilisateur inconnu ou mot de passe incorrect."

        with self._lock:
            self.metrics["auth_login_success_total"] += 1
        token_bundle = self.issue_jwt(
            subject=user["username"],
            role=user["role"],
            permissions=user["permissions"],
        )
        log_structured(
            "auth_login_succeeded",
            level="INFO",
            username=user["username"],
            role=user["role"],
            correlation_id=correlation_id,
        )
        return token_bundle, None

    def verify_jwt(self, token: str) -> Tuple[bool, Dict[str, Any]]:
        if not token or not isinstance(token, str):
            with self._lock:
                self.metrics["auth_token_verify_failure_total"] += 1
            return False, {"valid": False, "error": "Jeton manquant."}

        raw_token = token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()

        parts = raw_token.split(".")
        if len(parts) != 3:
            with self._lock:
                self.metrics["auth_token_verify_failure_total"] += 1
            return False, {"valid": False, "error": "Format JWT malformé."}

        header_b64, payload_b64, signature_b64 = parts
        try:
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            expected_sig = hmac.new(self._jwt_secret, signing_input, hashlib.sha256).digest()
            actual_sig = _b64url_decode(signature_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                with self._lock:
                    self.metrics["auth_token_verify_failure_total"] += 1
                return False, {"valid": False, "error": "Signature JWT invalide."}

            header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
            if header.get("alg") != "HS256":
                with self._lock:
                    self.metrics["auth_token_verify_failure_total"] += 1
                return False, {"valid": False, "error": "Algorithme JWT non autorisé."}

            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
            now = int(time.time())
            if int(payload.get("exp", 0)) < now:
                with self._lock:
                    self.metrics["auth_token_verify_failure_total"] += 1
                return False, {"valid": False, "error": "Jeton JWT expiré."}

            with self._lock:
                self.metrics["auth_token_verify_success_total"] += 1
            return True, {
                "valid": True,
                "subject": payload.get("sub"),
                "role": payload.get("role"),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp"),
                "jti": payload.get("jti"),
            }
        except Exception:
            with self._lock:
                self.metrics["auth_token_verify_failure_total"] += 1
            return False, {"valid": False, "error": "Échec de décodage JWT."}


def create_auth_app(engine: Optional[AuthEngine] = None) -> Flask:
    app = Flask(__name__)
    auth_engine = engine or AuthEngine()
    app.config["AUTH_ENGINE"] = auth_engine

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        return jsonify({
            "status": "UP",
            "service": "auth",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        m = auth_engine.metrics
        lines = [
            "# HELP auth_login_success_total Nombre total d'authentifications reussies",
            "# TYPE auth_login_success_total counter",
            f"auth_login_success_total {m['auth_login_success_total']}",
            "# HELP auth_login_failure_total Nombre total d'echecs d'authentification",
            "# TYPE auth_login_failure_total counter",
            f"auth_login_failure_total {m['auth_login_failure_total']}",
            "# HELP auth_token_verify_success_total Nombre total de verifications JWT valides",
            "# TYPE auth_token_verify_success_total counter",
            f"auth_token_verify_success_total {m['auth_token_verify_success_total']}",
            "# HELP auth_token_verify_failure_total Nombre total d'echecs de verification JWT",
            "# TYPE auth_token_verify_failure_total counter",
            f"auth_token_verify_failure_total {m['auth_token_verify_failure_total']}",
        ]
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

    @app.route("/auth/v1/token", methods=["POST"])
    def issue_token() -> Tuple[Response, int]:
        correlation_id = request.headers.get("X-Correlation-ID", f"corr-{uuid.uuid4().hex[:8]}")
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        bundle, err = auth_engine.authenticate(username, password, correlation_id=correlation_id)
        if err or not bundle:
            return jsonify({"error": err or "Authentification refusée.", "correlation_id": correlation_id}), 401
        return jsonify(bundle), 200

    @app.route("/auth/v1/verify", methods=["POST"])
    def verify_token() -> Tuple[Response, int]:
        data = request.get_json(silent=True) or {}
        token = data.get("token") or request.headers.get("Authorization", "")
        valid, details = auth_engine.verify_jwt(token)
        status_code = 200 if valid else 401
        return jsonify(details), status_code

    return app


app = create_auth_app()

if __name__ == "__main__":
    port = int(os.environ.get("AUTH_PORT", "8002"))
    app.run(host="0.0.0.0", port=port)
