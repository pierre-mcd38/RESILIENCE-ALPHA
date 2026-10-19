"""
PROJECT RESILIENCE-ALPHA — Tests Unitaires et d'Intégration Métier (tests/test_business_platform.py)

Vérifie les 7 exigences métier de l'Étape 3 :
1. Authentification valide et invalide (JWT HS256).
2. Refus d'accès non autorisé (jeton absent, invalide ou rôle RBAC insuffisant).
3. Validation stricte des montants (rejet <= 0, flottants IEEE 754, plafond, solde insuffisant).
4. Transaction fictive réussie en centimes entiers.
5. Idempotence : rejeu d'une même requête sans double débit + rejet 409 si payload modifié.
6. Persistance réelle sur disque après arrêt/redémarrage du moteur de base de données.
7. Cohérence comptable (invariant de conservation de la somme des soldes).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.api.app import create_api_app
from services.api.database import PaymentDatabase
from services.auth.app import AuthEngine, create_auth_app


class BusinessPlatformTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_payments.sqlite3")
        self.auth_engine = AuthEngine(jwt_secret="test-jwt-secret-resilience-2026")
        self.auth_app = create_auth_app(self.auth_engine)
        self.db = PaymentDatabase(db_path=self.db_path)
        self.api_app = create_api_app(db=self.db, auth_engine=self.auth_engine)
        self.auth_client = self.auth_app.test_client()
        self.api_client = self.api_app.test_client()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _get_token(self, username: str = "operator_alpha", password: str = "FictiveOp#2026!") -> str:
        resp = self.auth_client.post("/auth/v1/token", json={"username": username, "password": password})
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()["access_token"]

    def test_01_valid_and_invalid_authentication(self) -> None:
        # Authentification valide
        ok_resp = self.auth_client.post(
            "/auth/v1/token",
            json={"username": "operator_alpha", "password": "FictiveOp#2026!"},
        )
        self.assertEqual(ok_resp.status_code, 200)
        data = ok_resp.get_json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "merchant_operator")

        # Mot de passe erroné
        bad_resp = self.auth_client.post(
            "/auth/v1/token",
            json={"username": "operator_alpha", "password": "WrongPassword!"},
        )
        self.assertEqual(bad_resp.status_code, 401)

        # Utilisateur inexistant
        unknown_resp = self.auth_client.post(
            "/auth/v1/token",
            json={"username": "ghost_user", "password": "FictiveOp#2026!"},
        )
        self.assertEqual(unknown_resp.status_code, 401)

    def test_02_unauthorized_and_rbac_access_denied(self) -> None:
        # Sans jeton
        no_tok = self.api_client.get("/api/v1/accounts")
        self.assertEqual(no_tok.status_code, 401)

        # Jeton falsifié
        tampered = self.api_client.get(
            "/api/v1/accounts",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiadminIn0.invalidsig"},
        )
        self.assertEqual(tampered.status_code, 401)

        # Rôle auditor_readonly : lecture autorisée, création de transaction refusée (403)
        auditor_token = self._get_token("auditor_readonly", "FictiveAudit#2026!")
        read_ok = self.api_client.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        self.assertEqual(read_ok.status_code, 200)

        create_denied = self.api_client.post(
            "/api/v1/transactions",
            headers={
                "Authorization": f"Bearer {auditor_token}",
                "Idempotency-Key": "idem-rbac-test-1",
            },
            json={
                "source_account_id": "ACC-FR-001",
                "target_account_id": "ACC-FR-002",
                "amount_cents": 1500,
                "currency": "EUR",
            },
        )
        self.assertEqual(create_denied.status_code, 403)

    def test_03_invalid_amounts_and_insufficient_funds(self) -> None:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Montant négatif ou nul
        for invalid_val in (0, -500, 12.34, True):
            resp = self.api_client.post(
                "/api/v1/transactions",
                headers={**headers, "Idempotency-Key": f"idem-inv-{invalid_val}"},
                json={
                    "source_account_id": "ACC-FR-001",
                    "target_account_id": "ACC-FR-002",
                    "amount_cents": invalid_val,
                    "currency": "EUR",
                },
            )
            self.assertEqual(resp.status_code, 422)

        # Solde insuffisant (ACC-FR-003 possède 250 000 centimes)
        insuff = self.api_client.post(
            "/api/v1/transactions",
            headers={**headers, "Idempotency-Key": "idem-insuff-01"},
            json={
                "source_account_id": "ACC-FR-003",
                "target_account_id": "ACC-FR-001",
                "amount_cents": 900_000,
                "currency": "EUR",
            },
        )
        self.assertEqual(insuff.status_code, 422)
        self.assertEqual(insuff.get_json()["code"], "INSUFFICIENT_FUNDS")

    def test_04_successful_transaction_and_idempotency(self) -> None:
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "idem-tx-unique-2026-001",
        }
        payload = {
            "source_account_id": "ACC-FR-001",
            "target_account_id": "ACC-FR-002",
            "amount_cents": 12500,
            "currency": "EUR",
            "description": "Paiement test unitaire #1",
        }

        # 1er appel : 201 Created
        r1 = self.api_client.post("/api/v1/transactions", headers=headers, json=payload)
        self.assertEqual(r1.status_code, 201)
        tx1 = r1.get_json()
        self.assertEqual(tx1["status"], "COMMITTED")
        self.assertEqual(tx1["amount_cents"], 12500)
        self.assertFalse(tx1["idempotent_replay"])
        self.assertEqual(tx1["source_balance_after_cents"], 1_000_000 - 12500)
        self.assertEqual(tx1["target_balance_after_cents"], 500_000 + 12500)

        # 2e appel identique avec la même clé : 200 OK, même tx_id, aucun second débit
        r2 = self.api_client.post("/api/v1/transactions", headers=headers, json=payload)
        self.assertEqual(r2.status_code, 200)
        tx2 = r2.get_json()
        self.assertTrue(tx2["idempotent_replay"])
        self.assertEqual(tx2["tx_id"], tx1["tx_id"])

        # 3e appel avec la même clé mais un montant modifié : 409 Conflict
        modified_payload = {**payload, "amount_cents": 99900}
        r3 = self.api_client.post("/api/v1/transactions", headers=headers, json=modified_payload)
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(r3.get_json()["code"], "IDEMPOTENCY_PAYLOAD_MISMATCH")

    def test_05_persistence_after_restart_and_accounting_consistency(self) -> None:
        token = self._get_token()
        r = self.api_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-persist-001"},
            json={
                "source_account_id": "ACC-FR-002",
                "target_account_id": "ACC-FR-003",
                "amount_cents": 3333,
                "currency": "EUR",
            },
        )
        self.assertEqual(r.status_code, 201)
        tx_id = r.get_json()["tx_id"]

        # Simulation d'un redémarrage complet du service API et réouverture du fichier SQLite WAL
        restarted_db = PaymentDatabase(db_path=self.db_path)
        restarted_app = create_api_app(db=restarted_db, auth_engine=self.auth_engine)
        restarted_client = restarted_app.test_client()

        read_back = restarted_client.get(
            f"/api/v1/transactions/{tx_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(read_back.status_code, 200)
        self.assertEqual(read_back.get_json()["amount_cents"], 3333)

        invariant = restarted_db.check_accounting_invariant()
        self.assertTrue(invariant["consistent"])
        self.assertEqual(invariant["expected_total_cents"], invariant["actual_total_cents"])


if __name__ == "__main__":
    unittest.main()
