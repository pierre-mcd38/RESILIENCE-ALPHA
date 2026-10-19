"""
PROJECT RESILIENCE-ALPHA — Tests de Bout en Bout et Répétitions Chronométrées
(tests/test_e2e_resilience.py)

Exécute 3 répétitions complètes et chronométrées de la chaîne obligatoire :
  TRANSACTION RÉUSSIE (T0)
  → PERTURBATION CONTRÔLÉE DEPUIS IP ATTAQUANTE (T1)
  → DÉGRADATION OBSERVABLE SUR L'API MÉTIER (T2)
  → DÉTECTION ML PAR ISOLATION FOREST SUR 2 FENÊTRES (T3)
  → REMÉDIATION AUTOMATIQUE BORNÉE (BLOCAGE DYNAMIQUE WAF + RECYCLAGE WORKERS) (T4)
  → NOUVELLE TRANSACTION MÉTIER RÉUSSIE SOUS ATTAQUE CONTINUE (BLOQUÉE PAR WAF) (T5)

Vérifie également le scénario de protection anti-boucle (passage en état FAILED après 3 échecs).
Enregistre toutes les mesures réelles dans `data/rehearsal_runs.json`.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from scenarios.controlled_attack import run_bounded_resilience_scenario
from scenarios.kill_switch import release_kill_switch
from services.api.app import ApiRuntimeState, create_api_app
from services.api.database import PaymentDatabase
from services.auth.app import AuthEngine, create_auth_app
from services.detector.app import AnomalyDetectorEngine, create_app as create_detector_app
from services.executor.app import ConstrainedExecutor, create_executor_app
from services.remediator.app import RemediationOrchestrator, create_remediator_app
from services.waf_gateway.app import WafEngine, create_waf_app


def _get_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return "working-tree-uncommitted"


class EndToEndResilienceRehearsalTestCase(unittest.TestCase):
    def setUp(self) -> None:
        release_kill_switch()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.hmac_secret = "rehearsal-hmac-secret-2026"

    def tearDown(self) -> None:
        release_kill_switch()
        self.tmp_dir.cleanup()

    def _build_full_stack(self, run_idx: int) -> Dict[str, Any]:
        db_path = str(Path(self.tmp_dir.name) / f"rehearsal_{run_idx}.sqlite3")
        audit_path = str(Path(self.tmp_dir.name) / f"audit_{run_idx}.jsonl")

        auth_engine = AuthEngine(jwt_secret="rehearsal-jwt-secret-2026")
        auth_app = create_auth_app(auth_engine)

        payment_db = PaymentDatabase(db_path=db_path)
        api_state = ApiRuntimeState(max_worker_slots=4)
        api_app = create_api_app(db=payment_db, auth_engine=auth_engine, runtime_state=api_state)

        waf_engine = WafEngine()
        waf_app = create_waf_app(
            waf_engine=waf_engine,
            local_dispatchers={"auth": auth_app, "api": api_app},
        )

        executor = ConstrainedExecutor(
            hmac_secret=self.hmac_secret,
            audit_log_path=audit_path,
            waf_app=waf_app,
            api_app=api_app,
        )
        executor_app = create_executor_app(executor)

        orchestrator = RemediationOrchestrator(
            max_attempts=3,
            cooldown_seconds=0.1,
            block_ttl_seconds=300,
            hmac_secret=self.hmac_secret,
            waf_app=waf_app,
            api_app=api_app,
            auth_app=auth_app,
            executor_app=executor_app,
        )
        remediator_app = create_remediator_app(orchestrator)
        # Ajoute le dispatch SOC au WAF
        waf_app.config["WAF_ENGINE"] = waf_engine

        detector = AnomalyDetectorEngine()
        detector_app = create_detector_app(detector)

        return {
            "db": payment_db,
            "api_state": api_state,
            "auth_app": auth_app,
            "api_app": api_app,
            "waf_engine": waf_engine,
            "waf_app": waf_app,
            "executor": executor,
            "executor_app": executor_app,
            "orchestrator": orchestrator,
            "remediator_app": remediator_app,
            "detector": detector,
            "detector_app": detector_app,
        }

    def _execute_single_rehearsal(self, run_number: int) -> Dict[str, Any]:
        stack = self._build_full_stack(run_number)
        waf_client = stack["waf_app"].test_client()
        detector_client = stack["detector_app"].test_client()
        remediator_client = stack["remediator_app"].test_client()

        t_rehearsal_start = time.perf_counter()
        attacker_ip = "192.168.137.45"
        operator_ip = "127.0.0.1"

        # =====================================================================
        # ÉTAPE T0 : Transaction Métier Initiale Réussie (État NORMAL)
        # =====================================================================
        auth_resp = waf_client.post(
            "/auth/v1/token",
            json={"username": "operator_alpha", "password": "FictiveOp#2026!"},
            headers={"X-Forwarded-For": operator_ip},
        )
        self.assertEqual(auth_resp.status_code, 200)
        operator_token = auth_resp.get_json()["access_token"]

        t0_idem = f"idem-t0-run{run_number}-{uuid.uuid4().hex[:6]}"
        t0_resp = waf_client.post(
            "/api/v1/transactions",
            headers={
                "Authorization": f"Bearer {operator_token}",
                "Idempotency-Key": t0_idem,
                "X-Forwarded-For": operator_ip,
            },
            json={
                "source_account_id": "ACC-FR-001",
                "target_account_id": "ACC-FR-002",
                "amount_cents": 5000,
                "currency": "EUR",
                "description": f"Transaction initiale T0 (Répétition #{run_number})",
            },
        )
        self.assertEqual(t0_resp.status_code, 201)
        t0_tx = t0_resp.get_json()
        self.assertEqual(t0_tx["status"], "COMMITTED")

        # Vérification ML initiale (état NORMAL)
        win_t0 = stack["api_state"].compute_window_telemetry(5.0)
        ml_t0 = detector_client.post("/evaluate", json=win_t0).get_json()
        self.assertFalse(ml_t0["is_anomaly"])
        remediator_client.post("/soc/v1/anomaly-events", json=ml_t0)
        self.assertEqual(stack["orchestrator"].state, "NORMAL")

        # =====================================================================
        # ÉTAPE T1 & T2 : Perturbation Applicative Contrôlée & Dégradation Observable
        # =====================================================================
        t_perturbation_epoch = time.time()
        t_perturbation_iso = datetime.now(timezone.utc).isoformat()

        def _waf_hook(path: str, body: Dict[str, Any], hdrs: Dict[str, str]) -> int:
            r = waf_client.post(path, json=body, headers=hdrs)
            return r.status_code

        # Rafale initiale depuis l'IP attaquante (192.168.137.45) sur /api/v1/transactions/verify-batch
        wave1 = run_bounded_resilience_scenario(
            "http://127.0.0.1:8080",
            duration_seconds=1.2,
            rate_rps=25.0,
            concurrency=4,
            simulated_source_ip=attacker_ip,
            request_Hook=_waf_hook,
        )
        self.assertGreater(wave1["total_requests"], 10)

        # Mesure de la dégradation réelle sur l'API métier
        win_degraded_1 = stack["api_state"].compute_window_telemetry(5.0)
        win_degraded_1["perturbation_started_epoch"] = t_perturbation_epoch
        degraded_features = win_degraded_1["features"]
        self.assertGreater(degraded_features["latency_p95_ms"], 100.0)
        self.assertGreater(degraded_features["expensive_endpoint_ratio"], 0.5)

        # =====================================================================
        # ÉTAPE T3 : Détection ML IsolationForest (Fenêtre 1 -> SUSPECT, Fenêtre 2 -> INCIDENT)
        # =====================================================================
        ml_ev1 = detector_client.post("/evaluate", json=win_degraded_1).get_json()
        self.assertTrue(ml_ev1["is_anomaly"])
        self.assertEqual(ml_ev1["consecutive_anomalies"], 1)
        ml_ev1["perturbation_started_epoch"] = t_perturbation_epoch

        rem_step1 = remediator_client.post("/soc/v1/anomaly-events", json=ml_ev1).get_json()
        self.assertEqual(rem_step1["state"], "SUSPECT")

        # 2e fenêtre d'observation sous perturbation -> Confirmation de l'incident et déclenchement autonome
        wave2 = run_bounded_resilience_scenario(
            "http://127.0.0.1:8080",
            duration_seconds=0.8,
            rate_rps=25.0,
            concurrency=4,
            simulated_source_ip=attacker_ip,
            request_Hook=_waf_hook,
        )
        win_degraded_2 = stack["api_state"].compute_window_telemetry(5.0)
        ml_ev2 = detector_client.post("/evaluate", json=win_degraded_2).get_json()
        self.assertTrue(ml_ev2["is_anomaly"])
        self.assertEqual(ml_ev2["consecutive_anomalies"], 2)
        ml_ev2["perturbation_started_epoch"] = t_perturbation_epoch

        # =====================================================================
        # ÉTAPE T4 : Remédiation Autonome + Sonde Métier Post-Action -> RECOVERED
        # =====================================================================
        rem_step2 = remediator_client.post("/soc/v1/anomaly-events", json=ml_ev2).get_json()
        self.assertEqual(rem_step2["state"], "RECOVERED")
        self.assertEqual(rem_step2["action_taken"], "AUTONOMOUS_RECOVERY_VERIFIED")

        incident = rem_step2["incident"]
        proof = rem_step2["recovery_proof"]
        self.assertTrue(proof["persisted_in_db"])
        self.assertTrue(proof["idempotency_duplicate_prevented"])
        self.assertTrue(proof["accounting_invariant_verified"])

        # =====================================================================
        # ÉTAPE T5 : Preuve sous Charge Continue (l'attaque continue mais est bloquée 403 par le WAF,
        # tandis qu'une nouvelle transaction opérateur réussit !)
        # =====================================================================
        wave3_under_mitigation = run_bounded_resilience_scenario(
            "http://127.0.0.1:8080",
            duration_seconds=0.6,
            rate_rps=20.0,
            concurrency=4,
            simulated_source_ip=attacker_ip,
            request_Hook=_waf_hook,
        )
        # 100 % des requêtes de la vague 3 depuis 192.168.137.45 doivent être bloquées (HTTP 403) par le WAF dynamique !
        self.assertEqual(wave3_under_mitigation["status_counts"]["403"], wave3_under_mitigation["total_requests"])
        self.assertGreater(wave3_under_mitigation["blocked_by_waf_count"], 5)

        # Nouvelle transaction métier opérateur T5 pendant que le blocage WAF est actif
        t5_idem = f"idem-t5-run{run_number}-{uuid.uuid4().hex[:6]}"
        t5_resp = waf_client.post(
            "/api/v1/transactions",
            headers={
                "Authorization": f"Bearer {operator_token}",
                "Idempotency-Key": t5_idem,
                "X-Forwarded-For": operator_ip,
            },
            json={
                "source_account_id": "ACC-FR-001",
                "target_account_id": "ACC-FR-003",
                "amount_cents": 7500,
                "currency": "EUR",
                "description": f"Transaction post-reprise T5 (Répétition #{run_number})",
            },
        )
        self.assertEqual(t5_resp.status_code, 201)
        t5_tx = t5_resp.get_json()
        self.assertEqual(t5_tx["status"], "COMMITTED")

        # Vérification finale de l'invariant comptable et de la chaîne d'audit SHA-256
        invariant = stack["db"].check_accounting_invariant()
        self.assertTrue(invariant["consistent"])
        audit_chain = stack["executor"].verify_audit_chain()
        self.assertTrue(audit_chain["valid"])

        total_rehearsal_s = round(time.perf_counter() - t_rehearsal_start, 2)
        return {
            "rehearsal_number": run_number,
            "git_version": _get_git_commit(),
            "perturbation_started_at": t_perturbation_iso,
            "detected_at": incident["detected_at"],
            "recovered_at": incident["recovered_at"],
            "incident_id": incident["incident_id"],
            "suspect_ip_correlated": incident["suspect_ip"],
            "peak_ml_anomaly_score": round(float(incident["peak_ml_score"]), 4),
            "degraded_latency_p95_ms": degraded_features["latency_p95_ms"],
            "post_recovery_latency_ms": proof["post_recovery_latency_ms"],
            "mttd_seconds": incident["mttd_seconds"],
            "mttr_seconds": incident["mttr_seconds"],
            "total_incident_duration_seconds": incident["total_duration_seconds"],
            "total_rehearsal_sequence_seconds": total_rehearsal_s,
            "fits_60s_video_target": total_rehearsal_s <= 60.0,
            "t0_transaction_id": t0_tx["tx_id"],
            "probe_recovery_transaction_id": proof["probe_tx_id"],
            "t5_operator_transaction_id": t5_tx["tx_id"],
            "attacker_requests_blocked_post_remediation": wave3_under_mitigation["blocked_by_waf_count"],
            "accounting_invariant_ok": invariant["consistent"],
            "executor_audit_chain_valid": audit_chain["valid"],
            "status": "PASS",
        }

    def test_01_three_consecutive_rehearsals_and_save_evidence(self) -> None:
        runs: List[Dict[str, Any]] = []
        for idx in range(1, 4):
            summary = self._execute_single_rehearsal(idx)
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["fits_60s_video_target"])
            runs.append(summary)

        out_path = Path(__file__).resolve().parents[1] / "data" / "rehearsal_runs.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "execution_context": "local_integrated_stack_on_HDV0-INF-P08",
                    "second_pc_network_validation": "BLOCKED (Requires second PC connected to RESILIENCE-G<n> 192.168.137.1)",
                    "rehearsals_count": len(runs),
                    "runs": runs,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_02_anti_loop_max_attempts_transitions_to_failed(self) -> None:
        """Vérifie que si la sonde métier échoue 3 fois de suite, l'automate passe en FAILED et s'arrête."""
        stack = self._build_full_stack(99)
        orch: RemediationOrchestrator = stack["orchestrator"]
        orch.cooldown_seconds = 0.0
        # Mot de passe de sonde volontairement erroné pour simuler un échec persistant de la vérification métier
        orch.probe_password = "BrokenProbePasswordForFailureTest"

        anom_event = {
            "event_id": "evt-fail-test",
            "anomaly_score": -0.24,
            "is_anomaly": True,
            "consecutive_anomalies": 2,
            "dominant_source_ip": "192.168.137.99",
            "features": {"latency_p95_ms": 950.0, "cpu_worker_saturation": 0.99},
        }

        r1 = orch.handle_anomaly_event(anom_event)
        self.assertEqual(r1["state"], "INCIDENT")
        self.assertEqual(r1["incident"]["remediation_attempts"], 1)

        r2 = orch.handle_anomaly_event(anom_event)
        self.assertEqual(r2["state"], "INCIDENT")
        self.assertEqual(r2["incident"]["remediation_attempts"], 2)

        r3 = orch.handle_anomaly_event(anom_event)
        self.assertEqual(r3["state"], "FAILED")
        self.assertEqual(r3["incident"]["remediation_attempts"], 3)

        # Un 4e événement ne doit déclencher aucune nouvelle action (protection anti-boucle)
        r4 = orch.handle_anomaly_event(anom_event)
        self.assertEqual(r4["state"], "FAILED")
        self.assertEqual(r4["action_taken"], "BLOCKED_BY_MAX_ATTEMPTS")


if __name__ == "__main__":
    unittest.main()
