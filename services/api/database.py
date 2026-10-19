"""
PROJECT RESILIENCE-ALPHA — Couche de Persistance Transactionnelle (services/api/database.py)

Garantit :
- Stockage ACID persistant sur disque (SQLite WAL en mode `BEGIN IMMEDIATE` ou PostgreSQL).
- Représentation exacte des montants en centimes entiers (`INTEGER`).
- Idempotence atomique via la table `idempotency_keys` (aucun double débit possible).
- Vérification de l'invariant comptable (conservation de la masse monétaire totale).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_ACCOUNTS: List[Tuple[str, str, int, str, str]] = [
    ("ACC-FR-001", "Trésorerie Centrale Alpha (Fictif)", 1_000_000, "EUR", "ACTIVE"),
    ("ACC-FR-002", "Partenaire Compensation Beta (Fictif)", 500_000, "EUR", "ACTIVE"),
    ("ACC-FR-003", "Marchand Électronique Gamma (Fictif)", 250_000, "EUR", "ACTIVE"),
    ("ACC-PROBE-SRC", "Compte Sonde Résilience Émetteur (Fictif)", 500_000, "EUR", "ACTIVE"),
    ("ACC-PROBE-DST", "Compte Sonde Résilience Récepteur (Fictif)", 500_000, "EUR", "ACTIVE"),
]


class PaymentDatabase:
    """Gestionnaire de persistance transactionnelle ACID pour les paiements fictifs."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        resolved_path = db_path or os.environ.get(
            "RESILIENCE_DB_PATH",
            str(Path(__file__).resolve().parents[2] / "data" / "payments.sqlite3"),
        )
        self.db_path = str(resolved_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initial_total_balance_cents = sum(acc[2] for acc in DEFAULT_ACCOUNTS)
        self._init_schema_and_seed()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_schema_and_seed(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        account_id TEXT PRIMARY KEY,
                        owner_name TEXT NOT NULL,
                        balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
                        currency TEXT NOT NULL DEFAULT 'EUR',
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS transactions (
                        tx_id TEXT PRIMARY KEY,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        source_account_id TEXT NOT NULL,
                        target_account_id TEXT NOT NULL,
                        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                        currency TEXT NOT NULL DEFAULT 'EUR',
                        description TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        source_balance_after_cents INTEGER NOT NULL,
                        target_balance_after_cents INTEGER NOT NULL,
                        initiated_by TEXT NOT NULL,
                        correlation_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (source_account_id) REFERENCES accounts(account_id),
                        FOREIGN KEY (target_account_id) REFERENCES accounts(account_id)
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        idempotency_key TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        http_status INTEGER NOT NULL,
                        response_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                now = datetime.now(timezone.utc).isoformat()
                for acc_id, owner, balance, currency, status in DEFAULT_ACCOUNTS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO accounts (account_id, owner_name, balance_cents, currency, status, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?);
                        """,
                        (acc_id, owner, balance, currency, status, now),
                    )
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    @staticmethod
    def compute_payload_hash(source_account_id: str, target_account_id: str, amount_cents: int, currency: str) -> str:
        canonical = json.dumps(
            {
                "source_account_id": source_account_id,
                "target_account_id": target_account_id,
                "amount_cents": amount_cents,
                "currency": currency,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def list_accounts(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT account_id, owner_name, balance_cents, currency, status, updated_at FROM accounts ORDER BY account_id;"
                ).fetchall()
                return [
                    {
                        **dict(r),
                        "balance_formatted": f"{r['balance_cents'] / 100:.2f} {r['currency']}",
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def check_accounting_invariant(self) -> Dict[str, Any]:
        """Vérifie que la somme des soldes de tous les comptes est strictement conservée."""
        accounts = self.list_accounts()
        current_total = sum(int(a["balance_cents"]) for a in accounts)
        consistent = current_total == self.initial_total_balance_cents
        return {
            "consistent": consistent,
            "expected_total_cents": self.initial_total_balance_cents,
            "actual_total_cents": current_total,
            "accounts_count": len(accounts),
        }

    def execute_transfer(
        self,
        *,
        idempotency_key: str,
        source_account_id: str,
        target_account_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        initiated_by: str,
        correlation_id: str,
    ) -> Tuple[Dict[str, Any], int]:
        """Exécute un virement fictif de manière atomique et idempotente."""
        payload_hash = self.compute_payload_hash(source_account_id, target_account_id, amount_cents, currency)

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")

                # 1. Vérification de la clé d'idempotence
                existing = conn.execute(
                    "SELECT user_id, payload_hash, http_status, response_json FROM idempotency_keys WHERE idempotency_key = ?;",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    conn.execute("COMMIT;")
                    if existing["payload_hash"] != payload_hash:
                        return {
                            "error": "Conflit d'idempotence : même Idempotency-Key utilisée avec des paramètres différents.",
                            "code": "IDEMPOTENCY_PAYLOAD_MISMATCH",
                            "idempotency_key": idempotency_key,
                        }, 409
                    saved_response = json.loads(existing["response_json"])
                    saved_response["idempotent_replay"] = True
                    return saved_response, 200

                # 2. Vérification des comptes source et destination
                src = conn.execute(
                    "SELECT account_id, balance_cents, currency, status FROM accounts WHERE account_id = ?;",
                    (source_account_id,),
                ).fetchone()
                dst = conn.execute(
                    "SELECT account_id, balance_cents, currency, status FROM accounts WHERE account_id = ?;",
                    (target_account_id,),
                ).fetchone()

                if src is None or dst is None:
                    conn.execute("ROLLBACK;")
                    return {
                        "error": "Compte émetteur ou bénéficiaire introuvable.",
                        "code": "ACCOUNT_NOT_FOUND",
                    }, 404

                if src["status"] != "ACTIVE" or dst["status"] != "ACTIVE":
                    conn.execute("ROLLBACK;")
                    return {
                        "error": "L'un des comptes n'est pas actif.",
                        "code": "ACCOUNT_NOT_ACTIVE",
                    }, 403

                if src["currency"] != currency or dst["currency"] != currency:
                    conn.execute("ROLLBACK;")
                    return {
                        "error": "Devise incompatible avec les comptes sélectionnés.",
                        "code": "CURRENCY_MISMATCH",
                    }, 422

                if int(src["balance_cents"]) < amount_cents:
                    conn.execute("ROLLBACK;")
                    return {
                        "error": "Solde insuffisant pour exécuter la transaction.",
                        "code": "INSUFFICIENT_FUNDS",
                        "available_cents": int(src["balance_cents"]),
                        "requested_cents": amount_cents,
                    }, 422

                # 3. Mise à jour atomique des soldes
                now = datetime.now(timezone.utc).isoformat()
                new_src_balance = int(src["balance_cents"]) - amount_cents
                new_dst_balance = int(dst["balance_cents"]) + amount_cents

                conn.execute(
                    "UPDATE accounts SET balance_cents = ?, updated_at = ? WHERE account_id = ?;",
                    (new_src_balance, now, source_account_id),
                )
                conn.execute(
                    "UPDATE accounts SET balance_cents = ?, updated_at = ? WHERE account_id = ?;",
                    (new_dst_balance, now, target_account_id),
                )

                tx_id = f"tx-{uuid.uuid4()}"
                tx_record: Dict[str, Any] = {
                    "tx_id": tx_id,
                    "idempotency_key": idempotency_key,
                    "source_account_id": source_account_id,
                    "target_account_id": target_account_id,
                    "amount_cents": amount_cents,
                    "amount_formatted": f"{amount_cents / 100:.2f} {currency}",
                    "currency": currency,
                    "description": description[:240],
                    "status": "COMMITTED",
                    "source_balance_after_cents": new_src_balance,
                    "target_balance_after_cents": new_dst_balance,
                    "initiated_by": initiated_by,
                    "correlation_id": correlation_id,
                    "created_at": now,
                    "idempotent_replay": False,
                }

                conn.execute(
                    """
                    INSERT INTO transactions (
                        tx_id, idempotency_key, source_account_id, target_account_id,
                        amount_cents, currency, description, status,
                        source_balance_after_cents, target_balance_after_cents,
                        initiated_by, correlation_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        tx_id,
                        idempotency_key,
                        source_account_id,
                        target_account_id,
                        amount_cents,
                        currency,
                        description[:240],
                        "COMMITTED",
                        new_src_balance,
                        new_dst_balance,
                        initiated_by,
                        correlation_id,
                        now,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO idempotency_keys (idempotency_key, user_id, payload_hash, http_status, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        idempotency_key,
                        initiated_by,
                        payload_hash,
                        201,
                        json.dumps(tx_record, ensure_ascii=False),
                        now,
                    ),
                )

                conn.execute("COMMIT;")
                return tx_record, 201
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    def get_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM transactions WHERE tx_id = ?;",
                    (tx_id,),
                ).fetchone()
                if row is None:
                    return None
                d = dict(row)
                d["amount_formatted"] = f"{d['amount_cents'] / 100:.2f} {d['currency']}"
                return d
            finally:
                conn.close()

    def list_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?;",
                    (safe_limit,),
                ).fetchall()
                result = []
                for r in rows:
                    d = dict(r)
                    d["amount_formatted"] = f"{d['amount_cents'] / 100:.2f} {d['currency']}"
                    result.append(d)
                return result
            finally:
                conn.close()
