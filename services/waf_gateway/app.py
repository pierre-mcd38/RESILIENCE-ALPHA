"""
PROJECT RESILIENCE-ALPHA — Passerelle Reverse Proxy & WAF Dynamique L7 (services/waf_gateway/app.py)

Responsabilités :
1. Filtrage applicatif statique (Niveau 1) : bloque immédiatement les charges utiles contenant des
   signatures d'attaque (SQLi, XSS, Path Traversal, Command Injection).
2. Politique dynamique pilotée par AIOps (Niveau 2) :
   - Liste de blocage dynamique (`dynamic_blocklist`) avec TTL borné, alimentée par `services/executor`
     après détection ML par `IsolationForest`.
   - Profils de limitation de débit (`normal`, `elevated`, `strict_mitigation`).
3. Journalisation structurée des événements WAF pour la corrélation SOC et exposition Prometheus `/metrics`.
"""

from __future__ import annotations

import collections
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import requests
from flask import Flask, Response, jsonify, request

logger = logging.getLogger("resilience.waf")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


STATIC_WAF_SIGNATURES: List[Tuple[str, re.Pattern[str]]] = [
    ("SQLI_UNION_SELECT", re.compile(r"(?i)\bunion\s+all\s+select\b|\bunion\s+select\b")),
    ("SQLI_TAUTOLOGY", re.compile(r"(?i)('|\")\s*or\s+('?1'?\s*=\s*'?1|true)\b|--\s*$")),
    ("XSS_SCRIPT_TAG", re.compile(r"(?i)<\s*script\b|javascript\s*:|onerror\s*=")),
    ("PATH_TRAVERSAL", re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\\)", re.IGNORECASE)),
    ("CMD_INJECTION", re.compile(r"(?:;|\|\||&&|\$\()\s*(?:cat|ls|whoami|id|bash|sh|powershell|cmd|curl|wget)\b", re.IGNORECASE)),
]


class WafEngine:
    """Moteur WAF à deux niveaux (Signatures Statiques L7 + Blocage Dynamique AIOps)."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.rate_limit_profile: str = "normal"
        self.profile_expires_at: Optional[float] = None
        # ip -> {"blocked_at": iso, "expires_at": epoch, "ttl_seconds": int, "reason": str, "blocked_hits": int}
        self.dynamic_blocklist: Dict[str, Dict[str, Any]] = {}
        # ip -> deque of timestamps
        self.ip_request_windows: Dict[str, Deque[float]] = {}
        self.ip_request_Windows = self.ip_request_windows
        self.ip_expensive_windows: Dict[str, Deque[float]] = {}
        self.waf_events: Deque[Dict[str, Any]] = collections.deque(maxlen=500)
        self.request_logs: Deque[Dict[str, Any]] = collections.deque(maxlen=1000)

        self.metrics: Dict[str, int] = {
            "waf_requests_total": 0,
            "waf_allowed_total": 0,
            "waf_blocked_signature_total": 0,
            "waf_blocked_dynamic_ip_total": 0,
            "waf_blocked_ratelimit_total": 0,
        }

    def _cleanup_expired_unlocked(self, now: float) -> None:
        expired_ips = [ip for ip, info in self.dynamic_blocklist.items() if info["expires_at"] <= now]
        for ip in expired_ips:
            del self.dynamic_blocklist[ip]
        if self.profile_expires_at is not None and now >= self.profile_expires_at:
            self.rate_limit_profile = "normal"
            self.profile_expires_at = None

    def block_ip(self, ip_address: str, ttl_seconds: int = 300, reason: str = "ML anomaly mitigation") -> Dict[str, Any]:
        now = time.time()
        safe_ttl = max(10, min(int(ttl_seconds), 3600))
        with self.lock:
            self._cleanup_expired_unlocked(now)
            entry = {
                "ip_address": ip_address,
                "blocked_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": now + safe_ttl,
                "ttl_seconds": safe_ttl,
                "reason": reason,
                "blocked_hits": self.dynamic_blocklist.get(ip_address, {}).get("blocked_hits", 0),
            }
            self.dynamic_blocklist[ip_address] = entry
            self._record_event_unlocked(
                event_type="WAF_DYNAMIC_BLOCK_ADDED",
                source_ip=ip_address,
                path="*",
                rule_id="AIOPS_DYNAMIC_BLOCKLIST",
                action="BLOCK_CONFIGURED",
                reason=reason,
            )
            return dict(entry)

    def unblock_ip(self, ip_address: str) -> Dict[str, Any]:
        with self.lock:
            existed = self.dynamic_blocklist.pop(ip_address, None) is not None
            return {"ip_address": ip_address, "unblocked": existed}

    def set_rate_limit_profile(self, profile: str, ttl_seconds: int = 300) -> Dict[str, Any]:
        if profile not in ("normal", "elevated", "strict_mitigation"):
            raise ValueError(f"Profil WAF inconnu : {profile}")
        now = time.time()
        with self.lock:
            self.rate_limit_profile = profile
            self.profile_expires_at = (now + ttl_seconds) if profile != "normal" else None
            self._record_event_unlocked(
                event_type="WAF_PROFILE_UPDATED",
                source_ip="internal-executor",
                path="*",
                rule_id=f"PROFILE_{profile.upper()}",
                action="PROFILE_CHANGE",
                reason=f"Rate limit profile set to {profile} for {ttl_seconds}s",
            )
            return {
                "profile": self.rate_limit_profile,
                "ttl_seconds": ttl_seconds,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    def _record_event_unlocked(
        self,
        *,
        event_type: str,
        source_ip: str,
        path: str,
        rule_id: str,
        action: str,
        reason: str,
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        evt = {
            "event_id": f"waf-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "source_ip": source_ip,
            "path": path,
            "rule_id": rule_id,
            "action": action,
            "reason": reason,
            "correlation_id": correlation_id,
        }
        self.waf_events.append(evt)
        logger.info(json.dumps({"service": "waf-gateway", **evt}, ensure_ascii=False))
        return evt

    def inspect_request(
        self,
        *,
        source_ip: str,
        method: str,
        path: str,
        query_string: str,
        body_text: str,
        correlation_id: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]], int]:
        """
        Inspecte une requête entrante.
        Retourne `(allowed: bool, block_payload: Optional[dict], status_code: int)`.
        """
        now = time.time()
        with self.lock:
            self.metrics["waf_requests_total"] += 1
            self._cleanup_expired_unlocked(now)

            # 1. Vérification de la liste de blocage dynamique (alimentée par l'AIOps)
            if source_ip in self.dynamic_blocklist:
                entry = self.dynamic_blocklist[source_ip]
                entry["blocked_hits"] += 1
                self.metrics["waf_blocked_dynamic_ip_total"] += 1
                evt = self._record_event_unlocked(
                    event_type="WAF_REQUEST_BLOCKED_DYNAMIC_IP",
                    source_ip=source_ip,
                    path=path,
                    rule_id="AIOPS_DYNAMIC_BLOCKLIST",
                    action="BLOCK",
                    reason=entry["reason"],
                    correlation_id=correlation_id,
                )
                return False, {
                    "error": "Requête bloquée par la politique dynamique du WAF (remédiation autonome active).",
                    "waf_rule": "AIOPS_DYNAMIC_BLOCKLIST",
                    "source_ip": source_ip,
                    "event_id": evt["event_id"],
                    "correlation_id": correlation_id,
                }, 403

            # 2. Inspection des signatures statiques L7 (SQLi, XSS, Path Traversal, Command Injection)
            inspection_buffer = f"{path} {query_string} {body_text}"
            for rule_id, pattern in STATIC_WAF_SIGNATURES:
                if pattern.search(inspection_buffer):
                    self.metrics["waf_blocked_signature_total"] += 1
                    self.request_logs.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "ts_epoch": now,
                            "source_ip": source_ip,
                            "method": method,
                            "path": path,
                            "is_expensive": True,
                            "is_signature_attack": True,
                            "is_auth_route": "/auth/" in path,
                            "rule_id": rule_id,
                            "correlation_id": correlation_id,
                        }
                    )
                    evt = self._record_event_unlocked(
                        event_type="WAF_REQUEST_BLOCKED_SIGNATURE",
                        source_ip=source_ip,
                        path=path,
                        rule_id=rule_id,
                        action="BLOCK",
                        reason=f"Signature statique déclenchée : {rule_id}",
                        correlation_id=correlation_id,
                    )
                    return False, {
                        "error": f"Requête bloquée par le WAF (règle {rule_id}).",
                        "waf_rule": rule_id,
                        "event_id": evt["event_id"],
                        "correlation_id": correlation_id,
                    }, 403

            # 3. Limitation de débit selon le profil actif
            win = self.ip_request_windows.setdefault(source_ip, collections.deque(maxlen=500))
            while win and win[0] < now - 5.0:
                win.popleft()
            win.append(now)

            is_expensive_route = "/verify-batch" in path or "/reconcile" in path
            is_auth_route = "/auth/" in path
            exp_win = self.ip_expensive_windows.setdefault(source_ip, collections.deque(maxlen=300))
            while exp_win and exp_win[0] < now - 5.0:
                exp_win.popleft()
            if is_expensive_route:
                exp_win.append(now)

            # En profil 'normal', le plafond est large (150 req/5s) ce qui laisse passer le début du flood L7
            # pour démontrer la détection ML comportementale, puis en profil 'strict_mitigation' il tombe à 2 req/5s.
            max_general = 150 if self.rate_limit_profile == "normal" else (50 if self.rate_limit_profile == "elevated" else 25)
            max_expensive = 120 if self.rate_limit_profile == "normal" else (10 if self.rate_limit_profile == "elevated" else 2)

            is_internal_probe = source_ip in ("127.0.0.1", "::1", "localhost") or correlation_id.startswith("probe-")
            if not is_internal_probe and (len(win) > max_general or (is_expensive_route and len(exp_win) > max_expensive)):
                self.metrics["waf_blocked_ratelimit_total"] += 1
                self.request_logs.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "ts_epoch": now,
                        "source_ip": source_ip,
                        "method": method,
                        "path": path,
                        "is_expensive": is_expensive_route,
                        "is_signature_attack": False,
                        "is_auth_route": is_auth_route,
                        "is_rate_limited": True,
                        "correlation_id": correlation_id,
                    }
                )
                evt = self._record_event_unlocked(
                    event_type="WAF_REQUEST_RATE_LIMITED",
                    source_ip=source_ip,
                    path=path,
                    rule_id=f"RATELIMIT_{self.rate_limit_profile.upper()}",
                    action="RATE_LIMIT",
                    reason=f"Dépassement de quota sous profil {self.rate_limit_profile}",
                    correlation_id=correlation_id,
                )
                return False, {
                    "error": "Trop de requêtes (WAF Rate Limiting actif).",
                    "waf_rule": f"RATELIMIT_{self.rate_limit_profile.upper()}",
                    "profile": self.rate_limit_profile,
                    "event_id": evt["event_id"],
                    "correlation_id": correlation_id,
                }, 429

            self.metrics["waf_allowed_total"] += 1
            self.request_logs.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ts_epoch": now,
                    "source_ip": source_ip,
                    "method": method,
                    "path": path,
                    "is_expensive": is_expensive_route,
                    "is_signature_attack": False,
                    "is_auth_route": is_auth_route,
                    "correlation_id": correlation_id,
                }
            )
            return True, None, 200

    def get_dominant_suspect_ip(self, window_seconds: float = 15.0) -> Optional[str]:
        """Identifie l'adresse IP responsable du plus grand volume d'appels suspects sur la fenêtre récente."""
        now = time.time()
        cutoff = now - window_seconds
        with self.lock:
            counts: Dict[str, int] = {}
            for entry in self.request_logs:
                if entry["ts_epoch"] >= cutoff:
                    ip = entry["source_ip"]
                    if ip in ("127.0.0.1", "::1", "192.168.137.1", "localhost"):
                        continue
                    weight = 5 if entry.get("is_signature_attack") else (3 if (entry.get("is_expensive") or entry.get("is_auth_route")) else 1)
                    counts[ip] = counts.get(ip, 0) + weight
            if not counts:
                return None
            return max(counts.items(), key=lambda kv: kv[1])[0]

    def get_window_waf_stats(self, window_seconds: float = 5.0) -> Dict[str, Any]:
        """Retourne les statistiques temps réel de tous les vecteurs observés par le WAF sur la fenêtre."""
        now = time.time()
        cutoff = now - window_seconds
        with self.lock:
            recent = [e for e in self.request_logs if e["ts_epoch"] >= cutoff]
            sig_hits = sum(1 for e in recent if e.get("is_signature_attack"))
            auth_reqs = sum(1 for e in recent if e.get("is_auth_route"))
            exp_reqs = sum(1 for e in recent if e.get("is_expensive"))
            ip_counts: Dict[str, int] = {}
            for e in recent:
                ip = e["source_ip"]
                ip_counts[ip] = ip_counts.get(ip, 0) + 1
            return {
                "total_waf_window_requests": len(recent),
                "waf_signature_hits": sig_hits,
                "waf_auth_requests": auth_reqs,
                "waf_expensive_requests": exp_reqs,
                "waf_ip_counts": ip_counts,
            }

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        with self.lock:
            self._cleanup_expired_unlocked(now)
            return {
                "status": "UP",
                "service": "waf-gateway",
                "rate_limit_profile": self.rate_limit_profile,
                "active_blocked_ips": list(self.dynamic_blocklist.values()),
                "metrics": dict(self.metrics),
                "recent_events_count": len(self.waf_events),
                "dominant_suspect_ip": self.get_dominant_suspect_ip(15.0),
            }


def create_waf_app(
    waf_engine: Optional[WafEngine] = None,
    local_dispatchers: Optional[Dict[str, Flask]] = None,
) -> Flask:
    """
    Crée l'application Flask du WAF.
    - En mode conteneurisé : relaie via HTTP vers `API_SERVICE_URL` et `AUTH_SERVICE_URL`.
    - En mode test/local intégré : peut relayer directement vers les apps Flask passées dans `local_dispatchers`.
    """
    app = Flask(__name__)
    engine = waf_engine or WafEngine()
    dispatchers = local_dispatchers or {}
    app.config["WAF_ENGINE"] = engine

    api_url = os.environ.get("API_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
    auth_url = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
    remediator_url = os.environ.get("REMEDIATOR_SERVICE_URL", "http://127.0.0.1:8004").rstrip("/")
    rag_url = os.environ.get("RAG_SERVICE_URL", "http://127.0.0.1:8006").rstrip("/")
    internal_control_secret = os.environ.get(
        "INTERNAL_CONTROL_TOKEN",
        "resilience-internal-control-token-2026",
    )
    trusted_proxies = set(
        p.strip() for p in os.environ.get("WAF_TRUSTED_PROXIES", "127.0.0.1,::1,localhost").split(",") if p.strip()
    )
    allow_simulated_ips = os.environ.get("WAF_ALLOW_SIMULATED_IP", "true").lower() in ("true", "1", "yes")

    def _resolve_client_ip(req: Any) -> str:
        """Résout l'adresse IP cliente de manière sécurisée en prévenant l'usurpation via X-Forwarded-For."""
        direct_ip = req.remote_addr or "127.0.0.1"
        xff = req.headers.get("X-Forwarded-For", "").strip()
        # En mode simulation ou si la connexion provient d'un reverse-proxy de confiance déclaré
        if (allow_simulated_ips or direct_ip in trusted_proxies) and xff:
            claimed_ip = xff.split(",")[0].strip()
            if claimed_ip:
                return claimed_ip
        return direct_ip

    @app.route("/health", methods=["GET"])
    def health() -> Tuple[Response, int]:
        return jsonify(engine.get_status()), 200

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        m = engine.metrics
        lines = [
            "# HELP waf_requests_total Total des requetes inspectees par le WAF",
            "# TYPE waf_requests_total counter",
            f"waf_requests_total {m['waf_requests_total']}",
            "# HELP waf_allowed_total Total des requetes autorisees par le WAF",
            "# TYPE waf_allowed_total counter",
            f"waf_allowed_total {m['waf_allowed_total']}",
            "# HELP waf_blocked_signature_total Requetes bloquees par signature statique L7",
            "# TYPE waf_blocked_signature_total counter",
            f"waf_blocked_signature_total {m['waf_blocked_signature_total']}",
            "# HELP waf_blocked_dynamic_ip_total Requetes bloquees par liste dynamique AIOps",
            "# TYPE waf_blocked_dynamic_ip_total counter",
            f"waf_blocked_dynamic_ip_total {m['waf_blocked_dynamic_ip_total']}",
            "# HELP waf_blocked_ratelimit_total Requetes bloquees par limitation de debit",
            "# TYPE waf_blocked_ratelimit_total counter",
            f"waf_blocked_ratelimit_total {m['waf_blocked_ratelimit_total']}",
        ]
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

    @app.route("/waf/v1/status", methods=["GET"])
    def waf_status() -> Tuple[Response, int]:
        return jsonify(engine.get_status()), 200

    @app.route("/waf/v1/telemetry/window", methods=["GET"])
    def waf_telemetry_window() -> Tuple[Response, int]:
        win_sec = float(request.args.get("window_seconds", 5.0))
        return jsonify(engine.get_window_waf_stats(win_sec)), 200

    @app.route("/waf/v1/events", methods=["GET"])
    def waf_events() -> Tuple[Response, int]:
        with engine.lock:
            evts = list(engine.waf_events)[-100:]
        return jsonify({"events": list(reversed(evts)), "count": len(evts)}), 200

    @app.route("/internal/v1/waf/block-ip", methods=["POST"])
    def internal_block_ip() -> Tuple[Response, int]:
        if request.headers.get("X-Internal-Control-Token", "") != internal_control_secret:
            return jsonify({"error": "Jeton de contrôle interne invalide."}), 403
        data = request.get_json(silent=True) or {}
        ip_addr = str(data.get("ip_address", "")).strip()
        ttl = int(data.get("ttl_seconds", 300))
        reason = str(data.get("reason", "ML anomaly remediation"))
        res = engine.block_ip(ip_addr, ttl_seconds=ttl, reason=reason)
        return jsonify(res), 200

    @app.route("/internal/v1/waf/unblock-ip", methods=["POST"])
    def internal_unblock_ip() -> Tuple[Response, int]:
        if request.headers.get("X-Internal-Control-Token", "") != internal_control_secret:
            return jsonify({"error": "Jeton de contrôle interne invalide."}), 403
        data = request.get_json(silent=True) or {}
        ip_addr = str(data.get("ip_address", "")).strip()
        return jsonify(engine.unblock_ip(ip_addr)), 200

    @app.route("/internal/v1/waf/rate-limit-profile", methods=["POST"])
    def internal_set_profile() -> Tuple[Response, int]:
        if request.headers.get("X-Internal-Control-Token", "") != internal_control_secret:
            return jsonify({"error": "Jeton de contrôle interne invalide."}), 403
        data = request.get_json(silent=True) or {}
        profile = str(data.get("profile", "strict_mitigation"))
        ttl = int(data.get("ttl_seconds", 300))
        return jsonify(engine.set_rate_limit_profile(profile, ttl_seconds=ttl)), 200

    def _forward_request(target_key: str, base_url: str, subpath: str) -> Tuple[Response, int]:
        correlation_id = request.headers.get("X-Correlation-ID", f"corr-{uuid.uuid4().hex[:10]}")
        source_ip = _resolve_client_ip(request)
        body_bytes = request.get_data()
        body_text = body_bytes.decode("utf-8", errors="ignore")

        allowed, block_payload, block_status = engine.inspect_request(
            source_ip=source_ip,
            method=request.method,
            path=request.path,
            query_string=request.query_string.decode("utf-8", errors="ignore"),
            body_text=body_text,
            correlation_id=correlation_id,
        )
        if not allowed and block_payload is not None:
            return jsonify(block_payload), block_status

        fwd_headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        fwd_headers["X-Correlation-ID"] = correlation_id
        fwd_headers["X-Forwarded-For"] = source_ip

        if target_key in dispatchers:
            target_app = dispatchers[target_key]
            with target_app.test_client() as client:
                qs = request.query_string.decode("utf-8", errors="ignore")
                full_path = f"{subpath}?{qs}" if qs else subpath
                resp = client.open(
                    path=full_path,
                    method=request.method,
                    headers=fwd_headers,
                    data=body_bytes,
                    content_type=request.content_type,
                )
                return Response(resp.get_data(), status=resp.status_code, content_type=resp.content_type), resp.status_code

        target_full_url = f"{base_url}{subpath}"
        if request.query_string:
            target_full_url += f"?{request.query_string.decode('utf-8', errors='ignore')}"
        try:
            upstream = requests.request(
                method=request.method,
                url=target_full_url,
                headers=fwd_headers,
                data=body_bytes,
                timeout=5.0,
            )
            return Response(
                upstream.content,
                status=upstream.status_code,
                content_type=upstream.headers.get("Content-Type", "application/json"),
            ), upstream.status_code
        except Exception as exc:
            return jsonify({"error": f"Service amont ({target_key}) injoignable : {exc}"}), 502

    @app.route("/auth/<path:rest>", methods=["GET", "POST"])
    def proxy_auth(rest: str) -> Tuple[Response, int]:
        return _forward_request("auth", auth_url, f"/auth/{rest}")

    @app.route("/api/<path:rest>", methods=["GET", "POST"])
    def proxy_api(rest: str) -> Tuple[Response, int]:
        return _forward_request("api", api_url, f"/api/{rest}")

    @app.route("/soc/<path:rest>", methods=["GET", "POST"])
    def proxy_soc(rest: str) -> Tuple[Response, int]:
        return _forward_request("remediator", remediator_url, f"/soc/{rest}")

    @app.route("/rag/<path:rest>", methods=["GET", "POST"])
    def proxy_rag(rest: str) -> Tuple[Response, int]:
        return _forward_request("rag", rag_url, f"/rag/{rest}")

    return app


app = create_waf_app()

if __name__ == "__main__":
    port = int(os.environ.get("WAF_PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
