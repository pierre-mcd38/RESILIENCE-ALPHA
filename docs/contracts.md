# Contrats d'Interfaces et Schémas d'Échange (`docs/contracts.md`)

Ce document formalise les contrats d'API REST et les schémas JSON échangés entre les microservices de **PROJECT RESILIENCE-ALPHA** (Étape 1).

---

## 1. Service d'Authentification (`services/auth` — Port `8002`)

### `POST /auth/v1/token`
Authentifie un opérateur ou un service technique et délivre un jeton JWT signé (`HS256`).

- **Requête** :
```json
{
  "username": "operator_alpha",
  "password": "<mot_de_passe_fictif>"
}
```
- **Réponse `200 OK`** :
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "role": "merchant_operator",
  "subject": "operator_alpha"
}
```

### `POST /auth/v1/verify`
Vérifie la validité et le rôle d'un jeton JWT.
- **Réponse `200 OK`** :
```json
{
  "valid": true,
  "subject": "operator_alpha",
  "role": "merchant_operator",
  "exp": 1792405200
}
```

---

## 2. API Métier de Paiement (`services/api` — Port `8001`, exposée via WAF `:8080`)

### `POST /api/v1/transactions`
Crée et exécute de manière atomique une transaction de paiement fictive.
- **En-têtes obligatoires** :
  - `Authorization: Bearer <access_token>`
  - `Idempotency-Key: <identifiant_unique_client_ou_uuid>`
  - `X-Correlation-ID: <optionnel, généré par le WAF si absent>`
- **Corps de requête** :
```json
{
  "source_account_id": "ACC-FR-001",
  "target_account_id": "ACC-FR-002",
  "amount_cents": 2500,
  "currency": "EUR",
  "description": "Règlement facture partenaire fictif #402"
}
```
- **Règles de validation métier** :
  - `amount_cents` doit être un entier strictement positif (`isinstance(v, int)` et `1 <= amount_cents <= 10_000_000`). Tout flottant ou montant négatif/nul est rejeté (`422 Unprocessable Entity`).
  - `source_account_id != target_account_id`.
  - Le solde du compte source doit être suffisant (`balance_cents >= amount_cents`).
  - Si `Idempotency-Key` existe déjà avec le même `payload_hash`, la réponse initiale est retournée avec l'en-tête `X-Idempotent-Replay: true` sans second débit. Si `Idempotency-Key` est réutilisée avec un corps différent, l'API renvoie `409 Conflict`.
- **Réponse `201 Created` (ou `200 OK` sur rejeu idempotent)** :
```json
{
  "tx_id": "tx-9f8c7b6a-1234-4abc-9def-001122334455",
  "idempotency_key": "idem-20261019-0001",
  "source_account_id": "ACC-FR-001",
  "target_account_id": "ACC-FR-002",
  "amount_cents": 2500,
  "amount_formatted": "25.00 EUR",
  "currency": "EUR",
  "status": "COMMITTED",
  "source_balance_after_cents": 997500,
  "target_balance_after_cents": 502500,
  "initiated_by": "operator_alpha",
  "correlation_id": "corr-7a8b9c",
  "created_at": "2026-10-19T09:30:00Z",
  "idempotent_replay": false
}
```

### `GET /api/v1/transactions` & `GET /api/v1/transactions/{tx_id}`
Consulte l'historique paginé des opérations ou une transaction spécifique pour vérification d'état.

### `GET /api/v1/accounts`
Retourne l'état exact des comptes fictifs et la somme de contrôle globale (`total_system_balance_cents`) permettant de prouver la conservation monétaire (invariant comptable).

### `POST /api/v1/transactions/verify-batch`
Endpoint de contrôle cryptographique de lots de transactions (utilisé par les opérations d'audit et ciblé par le scénario de dégradation applicative L7).

---

## 3. Format des Événements d'Anomalie ML (`services/detector` → `services/remediator`)

### `POST /soc/v1/anomaly-events` (Schéma `AnomalyEvent`)
Émis par `services/detector` lorsqu'une fenêtre d'observation est évaluée par `IsolationForest` :

```json
{
  "event_id": "evt-ml-20261019-0042",
  "timestamp": "2026-10-19T09:35:10Z",
  "model_name": "isolation_forest_v1",
  "model_version": "1.0.0",
  "window_seconds": 5,
  "anomaly_score": -0.2184,
  "decision_threshold": -0.0850,
  "is_anomaly": true,
  "consecutive_anomalies": 2,
  "features": {
    "req_rate_rps": 68.4,
    "latency_p95_ms": 942.0,
    "error_rate_ratio": 0.34,
    "expensive_endpoint_ratio": 0.91,
    "unique_ip_entropy": 0.12,
    "cpu_worker_saturation": 0.96,
    "tx_success_ratio": 0.15
  },
  "top_contributing_features": [
    "cpu_worker_saturation",
    "expensive_endpoint_ratio",
    "latency_p95_ms"
  ],
  "dominant_source_ip": "192.168.137.45"
}
```

---

## 4. Format des Décisions et Ordres de Remédiation (`services/remediator` → `services/executor`)

### 4.1 Schéma `RemediationDecision` (Journalisé par `services/remediator`)
```json
{
  "decision_id": "dec-20261019-001",
  "incident_id": "INC-20261019-001",
  "timestamp": "2026-10-19T09:35:11Z",
  "previous_state": "SUSPECT",
  "new_state": "REMEDIATING",
  "trigger_event_id": "evt-ml-20261019-0042",
  "suspect_ip": "192.168.137.45",
  "attempt_number": 1,
  "max_attempts": 3,
  "planned_actions": [
    {
      "action": "block_ip_waf",
      "parameters": {
        "ip_address": "192.168.137.45",
        "ttl_seconds": 300,
        "reason": "ML anomaly score -0.2184 (L7 resource exhaustion on /verify-batch)"
      }
    },
    {
      "action": "set_rate_limit_profile",
      "parameters": {
        "profile": "strict_mitigation",
        "ttl_seconds": 300
      }
    },
    {
      "action": "recycle_api_workers",
      "parameters": {
        "target_service": "api",
        "drain_timeout_ms": 500
      }
    }
  ]
}
```

### 4.2 Contrat `POST /executor/v1/execute` (Schéma `ExecutorCommand`)
Requête envoyée sur `control_net` avec en-têtes :
- `X-Executor-Timestamp: 1792402511`
- `X-Executor-Signature: sha256=<hmac_hex_digest>`

```json
{
  "command_id": "cmd-20261019-001a",
  "incident_id": "INC-20261019-001",
  "action": "block_ip_waf",
  "parameters": {
    "ip_address": "192.168.137.45",
    "ttl_seconds": 300,
    "reason": "ML anomaly score -0.2184"
  }
}
```

- **Liste fermée d'actions autorisées dans `executor`** :
  1. `block_ip_waf` : `ip_address` (IPv4 valide, hors liste blanche système), `ttl_seconds` (entier `10..3600`), `reason` (chaîne alphanumérique `<= 200` car.).
  2. `unblock_ip_waf` : `ip_address` (IPv4 valide).
  3. `set_rate_limit_profile` : `profile` $\in$ `{"normal", "elevated", "strict_mitigation"}`, `ttl_seconds` (`10..3600`).
  4. `recycle_api_workers` : `target_service` == `"api"`, `drain_timeout_ms` (`100..5000`).
  5. `reset_connection_pool` : `target_service` == `"api"`.
- Toute autre valeur d'`action` ou tout paramètre contenant des métacaractères shell (`;`, `|`, `&`, `` ` ``, `$`, `>`, `<`) renvoie immédiatement `403 Forbidden` et génère une alerte d'audit de sécurité.

---

## 5. Preuve Métier Post-Remédiation (Schéma `RecoveryProof`)

```json
{
  "proof_id": "prf-20261019-001",
  "incident_id": "INC-20261019-001",
  "verified_at": "2026-10-19T09:35:14Z",
  "api_health_ok": true,
  "probe_tx_id": "tx-probe-8899aabb",
  "probe_idempotency_key": "probe-recovery-INC-20261019-001-attempt-1",
  "probe_amount_cents": 100,
  "persisted_in_db": true,
  "idempotency_duplicate_prevented": true,
  "accounting_invariant_verified": true,
  "post_recovery_latency_ms": 14.2,
  "mttd_seconds": 4.1,
  "mttr_seconds": 3.4,
  "total_incident_duration_seconds": 7.5
}
```
