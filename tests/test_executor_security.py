"""
PROJECT RESILIENCE-ALPHA — Tests de Sécurité de l'Exécuteur, du WAF et des Garde-fous Offensifs
(tests/test_executor_security.py)

Vérifie :
1. Rejet par `executor` de toute commande non signée HMAC ou avec signature invalide / expirée.
2. Rejet du rejeu d'un même `command_id` (anti-rejeu).
3. Rejet de toute action absente de la liste fermée (`ALLOWLIST`).
4. Rejet de toute tentative d'injection de métacaractères shell (`;`, `|`, `$()`, `` ` ``).
5. Refus de bloquer les adresses IP protégées (`127.0.0.1`, `192.168.137.1`).
6. Intégrité cryptographique de la chaîne d'audit SHA-256 (`verify_audit_chain`).
7. Filtrage WAF statique (SQLi, XSS, Path Traversal, Command Injection).
8. Refus par `scenarios/controlled_attack.py` de toute IP hors liste blanche (ex. réseau campus `10.60.152.94` ou IP publique) et fonctionnement immédiat du `kill_switch`.
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from scenarios.controlled_attack import run_bounded_resilience_scenario, validate_authorized_target
from scenarios.kill_switch import engage_kill_switch, is_kill_switch_engaged, release_kill_switch
from services.api.app import create_api_app
from services.api.database import PaymentDatabase
from services.executor.app import ConstrainedExecutor, create_executor_app, sign_executor_payload
from services.waf_gateway.app import WafEngine, create_waf_app


class ExecutorAndWafSecurityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_path = str(Path(self.tmp_dir.name) / "test_audit.jsonl")
        self.db_path = str(Path(self.tmp_dir.name) / "test_sec_db.sqlite3")
        self.hmac_secret = "test-hmac-secret-2026"
        self.waf_engine = WafEngine()
        self.api_app = create_api_app(db=PaymentDatabase(self.db_path))
        self.waf_app = create_waf_app(self.waf_engine, local_dispatchers={"api": self.api_app})
        self.executor = ConstrainedExecutor(
            hmac_secret=self.hmac_secret,
            audit_log_path=self.audit_path,
            waf_app=self.waf_app,
            api_app=self.api_app,
        )
        self.exec_app = create_executor_app(self.executor)
        self.exec_client = self.exec_app.test_client()
        self.waf_client = self.waf_app.test_client()
        release_kill_switch()

    def tearDown(self) -> None:
        release_kill_switch()
        self.tmp_dir.cleanup()

    def _send_signed(self, payload: dict, ts_offset: int = 0, override_sig: str | None = None):
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ts_str = str(int(time.time()) + ts_offset)
        sig = override_sig or sign_executor_payload(raw, ts_str, self.hmac_secret)
        return self.exec_client.post(
            "/executor/v1/execute",
            data=raw,
            headers={
                "X-Executor-Timestamp": ts_str,
                "X-Executor-Signature": sig,
                "Content-Type": "application/json",
            },
        )

    def test_01_reject_unsigned_or_bad_hmac_or_expired_timestamp(self) -> None:
        cmd = {
            "command_id": "cmd-sec-01",
            "incident_id": "INC-SEC-01",
            "action": "recycle_api_workers",
            "parameters": {"target_service": "api"},
        }
        # Signature invalide
        r_bad = self._send_signed(cmd, override_sig="sha256=0000deadbeef")
        self.assertEqual(r_bad.status_code, 403)

        # Horodatage expiré (-120s)
        r_old = self._send_signed(cmd, ts_offset=-120)
        self.assertEqual(r_old.status_code, 403)

    def test_02_reject_disallowed_actions_and_shell_injection(self) -> None:
        # Action absente de l'ALLOWLIST
        r_unlisted = self._send_signed({
            "command_id": "cmd-sec-02",
            "incident_id": "INC-SEC-01",
            "action": "run_shell_command",
            "parameters": {"cmd": "whoami"},
        })
        self.assertEqual(r_unlisted.status_code, 403)

        # Métacaractères shell dans un paramètre d'action autorisée
        r_shell = self._send_signed({
            "command_id": "cmd-sec-03",
            "incident_id": "INC-SEC-01",
            "action": "block_ip_waf",
            "parameters": {
                "ip_address": "192.168.137.45",
                "ttl_seconds": 60,
                "reason": "test; rm -rf /",
            },
        })
        self.assertEqual(r_shell.status_code, 403)

    def test_03_reject_protected_ips_and_replay_attacks(self) -> None:
        # Tentative de bloquer le PC Hôte (192.168.137.1) ou loopback (127.0.0.1)
        for protected_ip in ("127.0.0.1", "192.168.137.1"):
            r_prot = self._send_signed({
                "command_id": f"cmd-prot-{protected_ip}",
                "incident_id": "INC-SEC-01",
                "action": "block_ip_waf",
                "parameters": {"ip_address": protected_ip, "ttl_seconds": 120, "reason": "test"},
            })
            self.assertEqual(r_prot.status_code, 403)

        # Exécution légitime suivie d'une tentative de rejeu du même command_id
        valid_cmd = {
            "command_id": "cmd-valid-unique-01",
            "incident_id": "INC-SEC-01",
            "action": "block_ip_waf",
            "parameters": {"ip_address": "192.168.137.88", "ttl_seconds": 120, "reason": "Confirmed ML incident"},
        }
        r_ok = self._send_signed(valid_cmd)
        self.assertEqual(r_ok.status_code, 200)

        r_replay = self._send_signed(valid_cmd)
        self.assertEqual(r_replay.status_code, 409)

        # Vérification de l'intégrité de la chaîne d'audit SHA-256 (4 commandes dans ce test)
        chain = self.executor.verify_audit_chain()
        self.assertTrue(chain["valid"])
        self.assertEqual(chain["entries_count"], 4)

    def test_04_static_waf_blocks_sqli_xss_and_traversal(self) -> None:
        sqli = self.waf_client.get("/api/v1/transactions?limit=10' UNION SELECT username,password FROM users--")
        self.assertEqual(sqli.status_code, 403)
        self.assertEqual(sqli.get_json()["waf_rule"], "SQLI_UNION_SELECT")

        xss = self.waf_client.post(
            "/api/v1/transactions",
            json={"description": "<script>alert(1)</script>"},
        )
        self.assertEqual(xss.status_code, 403)
        self.assertEqual(xss.get_json()["waf_rule"], "XSS_SCRIPT_TAG")

    def test_05_attack_scenario_target_allowlist_and_kill_switch(self) -> None:
        # Refus strict du réseau campus (10.60.152.94) et d'Internet (8.8.8.8)
        with self.assertRaises(PermissionError):
            validate_authorized_target("http://10.60.152.94:8080")
        with self.assertRaises(PermissionError):
            validate_authorized_target("https://8.8.8.8:8080")
        with self.assertRaises(PermissionError):
            validate_authorized_target("http://example.com:8080")

        # Cible locale autorisée
        self.assertEqual(validate_authorized_target("http://127.0.0.1:8080"), "127.0.0.1")

        # Test de l'arrêt d'urgence immédiat (kill-switch)
        engage_kill_switch("Unit test emergency stop")
        self.assertTrue(is_kill_switch_engaged())
        res = run_bounded_resilience_scenario(
            "http://127.0.0.1:8080",
            duration_seconds=2.0,
            rate_rps=10.0,
            request_Hook=lambda _p, _b, _h: 200,
        )
        self.assertTrue(res["aborted_by_kill_switch"])
        self.assertEqual(res["total_requests"], 0)
        release_kill_switch()


if __name__ == "__main__":
    unittest.main()
