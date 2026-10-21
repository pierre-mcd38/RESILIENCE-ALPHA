"""
PROJECT RESILIENCE-ALPHA — Exécuteur Confiné à Privilèges Limités (services/executor/app.py)

Garanties de sécurité (Section 3.4 & Section 11) :
1. Liste fermée d'actions (`ALLOWLIST`) :
   - `block_ip_waf`
   - `unblock_ip_waf`
   - `set_rate_limit_profile`
   - `recycle_api_workers`
   - `reset_connection_pool`
2. Authentification cryptographique : chaque ordre doit être signé par `HMAC-SHA256` avec un
   horodatage dans une fenêtre anti-rejeu de ±30 secondes et un `command_id` unique.
3. Validation stricte des paramètres :
   - Aucune commande shell arbitraire n'est jamais construite ni exécutée.
   - Rejet immédiat de tout métacaractère shell (`;`, `|`, `&`, `` ` ``, `$`, `>`, `<`, `\n`).
   - Validation syntaxique `ipaddress.IPv4Address` et refus de bloquer les adresses protégées
     (loopback `127.0.0.1`, IP du PC Hôte `192.168.137.1`, passerelles internes Docker).
4. Journal d'audit immuable chaîné par empreinte SHA-256 (`prev_hash` -> `entry_hash`).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from flask import Flask, Response, jsonify, request

logger = logging.getLogger("resilience.executor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


ALLOWED_ACTIONS: Set[str] = {
    "block_ip_waf",
    "unblock_ip_waf",
    "set_rate_limit_profile",
    "recycle_api_workers",
    "reset_connection_pool",
}

PROTECTED_IPS: Set[str] = {
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "192.168.137.1",  # PC Hôte (ne jamais s'auto-bloquer !)
    "172.28.10.1",
    "172.28.20.1",
    "172.28.30.1",
    "172.28.40.1",
    "172.28.50.1",
}

FORBIDDEN_SHELL_CHARS = re.compile(r"[;|&`$><\r\n\\]")


def sign_executor_payload(payload_bytes: bytes, timestamp_str: str, hmac_secret: str) -> str:
    """Calcule la signature HMAC-SHA256 canonique `sha256=<hex>` pour un ordre de remédiation."""
    message = f"{timestamp_str}.".encode("ascii") + payload_bytes
    digest = hmac.new(hmac_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class ConstrainedExecutor:
    """Exécuteur d'actions de remédiation à liste fermée et audit chaîné."""

    def __init__(
        self,
        *,
        hmac_secret: Optional[str] = None,
        internal_control_token: Optional[str] = None,
        audit_log_path: Optional[str] = None,
        waf_app: Optional[Flask] = None,
        api_app: Optional[Flask] = None,
    ) -> None:
        self._hmac_secret = hmac_secret or os.environ.get(
            "EXECUTOR_HMAC_SECRET",
            "fictive-lab-executor-hmac-secret-2026-resilience",
        )
        self._internal_token = internal_control_token or os.environ.get(
            "INTERNAL_CONTROL_TOKEN",
            "resilience-internal-control-token-2026",
        )
        resolved_audit = audit_log_path or os.environ.get(
            "EXECUTOR_AUDIT_PATH",
            str(Path(__file__).resolve().parents[2] / "data" / "executor_audit.jsonl"),
        )
        self.audit_log_path = Path(resolved_audit)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._seen_command_ids: Set[str] = set()
        self._last_hash = "0" * 64
        self._audit_entries: List[Dict[str, Any]] = []
        self._reload_audit_history_unlocked()

        self.waf_app = waf_app
        self.api_app = api_app
        self.waf_url = os.environ.get("WAF_SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
        self.api_url = os.environ.get("API_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")

        self.metrics: Dict[str, int] = {
            "executor_commands_executed_total": 0,
            "executor_commands_rejected_auth_total": 0,
            "executor_commands_rejected_validation_total": 0,
            "executor_commands_failed_total": 0,
        }

    def _reload_audit_history_unlocked(self) -> None:
        """Recharge l'historique d'audit persistant et restaure la tête de chaîne de hachage SHA-256 (F07)."""
        if not self.audit_log_path.exists():
            return
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    entry = json.loads(line_s)
                    self._audit_entries.append(entry)
                    cmd_id = str(entry.get("command_id", ""))
                    if cmd_id:
                        self._seen_command_ids.add(cmd_id)
                    entry_h = str(entry.get("entry_hash", ""))
                    if entry_h:
                        self._last_hash = entry_h
        except Exception as exc:
            logger.warning(f"Avertissement rechargement audit: {exc}")

    def _append_audit_entry(
        self,
        *,
        command_id: str,
        incident_id: str,
        action: str,
        parameters: Dict[str, Any],
        decision: str,
        reason: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            timestamp = datetime.now(timezone.utc).isoformat()
            core = {
                "timestamp": timestamp,
                "command_id": command_id,
                "incident_id": incident_id,
                "action": action,
                "parameters": parameters,
                "decision": decision,
                "reason": reason,
                "result": result or {},
                "prev_hash": self._last_hash,
            }
            canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            entry = {**core, "entry_hash": entry_hash}
            self._last_hash = entry_hash
            self._audit_entries.append(entry)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(json.dumps({"service": "executor", "event_type": "audit_record", **entry}, ensure_ascii=False))
            return entry

    def verify_audit_chain(self) -> Dict[str, Any]:
        """Vérifie l'intégrité cryptographique de toute la chaîne d'audit SHA-256 (sur disque et en mémoire)."""
        with self._lock:
            file_entries: List[Dict[str, Any]] = []
            if self.audit_log_path.exists():
                try:
                    with open(self.audit_log_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line_s = line.strip()
                            if line_s:
                                file_entries.append(json.loads(line_s))
                except Exception as exc:
                    return {"valid": False, "error": f"Erreur lecture fichier audit: {exc}"}

            entries_to_check = file_entries if file_entries else self._audit_entries
            prev = "0" * 64
            for idx, item in enumerate(entries_to_check):
                if item.get("prev_hash") != prev:
                    return {"valid": False, "broken_at_index": idx, "entries_count": len(entries_to_check)}
                check_copy = {k: v for k, v in item.items() if k != "entry_hash"}
                canonical = json.dumps(check_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if item.get("entry_hash") != expected_hash:
                    return {"valid": False, "broken_at_index": idx, "entries_count": len(entries_to_check)}
                prev = expected_hash
            return {"valid": True, "entries_count": len(entries_to_check), "head_hash": prev}

    def verify_hmac_and_freshness(
        self,
        payload_bytes: bytes,
        timestamp_header: str,
        signature_header: str,
    ) -> Tuple[bool, Optional[str]]:
        if not timestamp_header or not signature_header:
            return False, "En-têtes X-Executor-Timestamp ou X-Executor-Signature manquants."
        try:
            ts_int = int(timestamp_header)
        except ValueError:
            return False, "Horodatage X-Executor-Timestamp invalide."

        now = int(time.time())
        if abs(now - ts_int) > 30:
            return False, "Horodatage hors fenêtre anti-rejeu (±30 secondes)."

        expected_sig = sign_executor_payload(payload_bytes, timestamp_header, self._hmac_secret)
        if not hmac.compare_digest(expected_sig, signature_header.strip()):
            return False, "Signature HMAC-SHA256 invalide."

        return True, None

    @staticmethod
    def _contains_shell_metacharacters(obj: Any) -> bool:
        if isinstance(obj, str):
            return bool(FORBIDDEN_SHELL_CHARS.search(obj))
        if isinstance(obj, dict):
            return any(
                ConstrainedExecutor._contains_shell_metacharacters(k)
                or ConstrainedExecutor._contains_shell_metacharacters(v)
                for k, v in obj.items()
            )
        if isinstance(obj, list):
            return any(ConstrainedExecutor._contains_shell_metacharacters(x) for x in obj)
        return False

    def validate_command(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Format de commande invalide."

        command_id = str(data.get("command_id", "")).strip()
        incident_id = str(data.get("incident_id", "")).strip()
        action = str(data.get("action", "")).strip()
        params = data.get("parameters")

        if not command_id or not incident_id or not isinstance(params, dict):
            return False, "Champs command_id, incident_id et parameters (objet) obligatoires."

        if self._contains_shell_metacharacters(data):
            return False, "Caractères métashell interdits détectés dans la requête."

        if action not in ALLOWED_ACTIONS:
            return False, f"Action '{action}' hors de la liste fermée autorisée ({sorted(ALLOWED_ACTIONS)})."

        if action in ("block_ip_waf", "unblock_ip_waf"):
            ip_str = str(params.get("ip_address", "")).strip()
            try:
                ip_obj = ipaddress.IPv4Address(ip_str)
            except Exception:
                return False, f"Adresse IPv4 invalide : '{ip_str}'."

            if ip_str in PROTECTED_IPS or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_unspecified:
                return False, f"Refus de sécurité : l'adresse IP '{ip_str}' appartient aux adresses protégées."

            if action == "block_ip_waf":
                ttl = params.get("ttl_seconds", 300)
                if isinstance(ttl, bool) or not isinstance(ttl, int) or not (10 <= ttl <= 3600):
                    return False, "Le paramètre ttl_seconds doit être un entier entre 10 et 3600 secondes."

        elif action == "set_rate_limit_profile":
            profile = str(params.get("profile", "")).strip()
            if profile not in ("normal", "elevated", "strict_mitigation"):
                return False, f"Profil de limitation '{profile}' non autorisé."
            ttl = params.get("ttl_seconds", 300)
            if isinstance(ttl, bool) or not isinstance(ttl, int) or not (10 <= ttl <= 3600):
                return False, "Le paramètre ttl_seconds doit être un entier entre 10 et 3600 secondes."

        elif action in ("recycle_api_workers", "reset_connection_pool"):
            target = str(params.get("target_service", "")).strip()
            if target != "api":
                return False, f"Cible '{target}' non autorisée : seul le service 'api' est autorisé."

        return True, None

    def _call_internal_endpoint(self, target: str, path: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        headers = {"X-Internal-Control-Token": self._internal_token, "Content-Type": "application/json"}
        if target == "waf" and self.waf_app is not None:
            with self.waf_app.test_client() as client:
                resp = client.post(path, json=payload, headers=headers)
                return resp.get_json(silent=True) or {}, resp.status_code
        if target == "api" and self.api_app is not None:
            with self.api_app.test_client() as client:
                resp = client.post(path, json=payload, headers=headers)
                return resp.get_json(silent=True) or {}, resp.status_code

        base = self.waf_url if target == "waf" else self.api_url
        resp = requests.post(f"{base}{path}", json=payload, headers=headers, timeout=4.0)
        return resp.json() if resp.content else {}, resp.status_code

    def execute_validated_command(
        self,
        payload_bytes: bytes,
        timestamp_header: str,
        signature_header: str,
    ) -> Tuple[Dict[str, Any], int]:
        try:
            data = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            with self._lock:
                self.metrics["executor_commands_rejected_validation_total"] += 1
            return {"error": "JSON malformé."}, 400

        command_id = str(data.get("command_id", "unknown"))
        incident_id = str(data.get("incident_id", "unknown"))
        action = str(data.get("action", "unknown"))
        params = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}

        # 1. Vérification HMAC et anti-rejeu
        auth_ok, auth_err = self.verify_hmac_and_freshness(payload_bytes, timestamp_header, signature_header)
        if not auth_ok:
            with self._lock:
                self.metrics["executor_commands_rejected_auth_total"] += 1
            entry = self._append_audit_entry(
                command_id=command_id,
                incident_id=incident_id,
                action=action,
                parameters=params,
                decision="REJECTED_AUTH",
                reason=auth_err or "Signature invalide",
            )
            return {"error": auth_err, "audit_entry_hash": entry["entry_hash"]}, 403

        with self._lock:
            if command_id in self._seen_command_ids:
                self.metrics["executor_commands_rejected_auth_total"] += 1
                entry = self._append_audit_entry(
                    command_id=command_id,
                    incident_id=incident_id,
                    action=action,
                    parameters=params,
                    decision="REJECTED_REPLAY",
                    reason="command_id déjà utilisé (anti-rejeu).",
                )
                return {"error": "Rejeu détecté : command_id déjà exécuté.", "audit_entry_hash": entry["entry_hash"]}, 409
            # Réservation atomique immédiate de l'identifiant pour empêcher toute concurrence de rejeu
            self._seen_command_ids.add(command_id)

        # 2. Validation de la liste fermée et des paramètres
        valid, val_err = self.validate_command(data)
        if not valid:
            with self._lock:
                self.metrics["executor_commands_rejected_validation_total"] += 1
            entry = self._append_audit_entry(
                command_id=command_id,
                incident_id=incident_id,
                action=action,
                parameters=params,
                decision="REJECTED_POLICY",
                reason=val_err or "Paramètres non autorisés",
            )
            return {"error": val_err, "audit_entry_hash": entry["entry_hash"]}, 403

        # 3. Exécution confinée de l'action
        try:
            if action == "block_ip_waf":
                res, code = self._call_internal_endpoint("waf", "/internal/v1/waf/block-ip", params)
            elif action == "unblock_ip_waf":
                res, code = self._call_internal_endpoint("waf", "/internal/v1/waf/unblock-ip", params)
            elif action == "set_rate_limit_profile":
                res, code = self._call_internal_endpoint("waf", "/internal/v1/waf/rate-limit-profile", params)
            elif action == "recycle_api_workers":
                res, code = self._call_internal_endpoint("api", "/internal/v1/admin/recycle-workers", params)
            elif action == "reset_connection_pool":
                res, code = self._call_internal_endpoint("api", "/internal/v1/admin/reset-pool", params)
            else:
                return {"error": "Action non supportée."}, 403

            if code >= 400:
                with self._lock:
                    self.metrics["executor_commands_failed_total"] += 1
                entry = self._append_audit_entry(
                    command_id=command_id,
                    incident_id=incident_id,
                    action=action,
                    parameters=params,
                    decision="EXECUTION_ERROR",
                    reason=f"Code retour amont {code}",
                    result=res,
                )
                return {"error": "Échec d'exécution sur le composant cible.", "details": res, "audit_entry_hash": entry["entry_hash"]}, 502

            with self._lock:
                self.metrics["executor_commands_executed_total"] += 1
            entry = self._append_audit_entry(
                command_id=command_id,
                incident_id=incident_id,
                action=action,
                parameters=params,
                decision="EXECUTED",
                reason="Ordre validé et appliqué avec succès.",
                result=res,
            )
            return {
                "status": "EXECUTED",
                "command_id": command_id,
                "incident_id": incident_id,
                "action": action,
                "result": res,
                "audit_entry_hash": entry["entry_hash"],
                "executed_at": entry["timestamp"],
            }, 200
        except Exception as exc:
            with self._lock:
                self.metrics["executor_commands_failed_total"] += 1
            entry = self._append_audit_entry(
                command_id=command_id,
                incident_id=incident_id,
                action=action,
                parameters=params,
                decision="EXECUTION_EXCEPTION",
                reason=str(exc),
            )
            return {"error": f"Exception lors de l'action : {exc}", "audit_entry_hash": entry["entry_hash"]}, 500


def create_executor_app(executor: Optional[ConstrainedExecutor] = None) -> Flask:
    app = Flask(__name__)
    exec_engine = executor or ConstrainedExecutor()
    app.config["EXECUTOR_ENGINE"] = exec_engine

    @app.route("/health", methods=["GET"])
    def health() -> Tuple[Response, int]:
        chain_status = exec_engine.verify_audit_chain()
        return jsonify({
            "status": "UP",
            "service": "executor",
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "audit_chain": chain_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        m = exec_engine.metrics
        lines = [
            "# HELP executor_commands_executed_total Actions de remediation executees avec succes",
            "# TYPE executor_commands_executed_total counter",
            f"executor_commands_executed_total {m['executor_commands_executed_total']}",
            "# HELP executor_commands_rejected_auth_total Commandes rejetees pour signature HMAC ou rejeu",
            "# TYPE executor_commands_rejected_auth_total counter",
            f"executor_commands_rejected_auth_total {m['executor_commands_rejected_auth_total']}",
            "# HELP executor_commands_rejected_validation_total Commandes rejetees hors allowlist ou parametres invalides",
            "# TYPE executor_commands_rejected_validation_total counter",
            f"executor_commands_rejected_validation_total {m['executor_commands_rejected_validation_total']}",
        ]
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

    @app.route("/executor/v1/execute", methods=["POST"])
    def execute() -> Tuple[Response, int]:
        payload_bytes = request.get_data()
        ts_header = request.headers.get("X-Executor-Timestamp", "")
        sig_header = request.headers.get("X-Executor-Signature", "")
        res, status = exec_engine.execute_validated_command(payload_bytes, ts_header, sig_header)
        return jsonify(res), status

    @app.route("/executor/v1/audit", methods=["GET"])
    def audit_log() -> Tuple[Response, int]:
        chain = exec_engine.verify_audit_chain()
        with exec_engine._lock:
            entries = list(exec_engine._audit_entries)[-100:]
        return jsonify({
            "chain_integrity": chain,
            "entries": entries,
        }), 200

    return app


app = create_executor_app()

if __name__ == "__main__":
    port = int(os.environ.get("EXECUTOR_PORT", "8005"))
    app.run(host="0.0.0.0", port=port)
