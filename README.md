# PROJECT RESILIENCE-ALPHA — Plateforme de Paiement Cyber-Résiliente & Reprise Autonome

Démonstrateur d'ingénierie réalisé pour le **Workshop National EPSI Bac+5 (Octobre 2026)** — **Groupe 2 (`G2`)** : **Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD**.

---

## 1. Chaîne de Valeur Implémentée et Prouvée

```text
TRANSACTION MÉTIER INITIALE RÉUSSIE (T0)
  → PERTURBATION CONTRÔLÉE DEPUIS UN SECOND PC SUR LE RÉSEAU DU GROUPE (T1)
  → DÉGRADATION OBSERVABLE SUR L'API MÉTIER (LATENCE P95 & SATURATION WORKERS) (T2)
  → DÉTECTION PAR MACHINE LEARNING (ISOLATION FOREST SUR 7 MÉTRIQUES) (T3)
  → REMÉDIATION AUTONOME BORNÉE (BLOCAGE DYNAMIQUE WAF + RECYCLAGE WORKERS SIGNÉS HMAC) (T4)
  → SONDE MÉTIER & NOUVELLE TRANSACTION FICTIVE RÉUSSIE ET PERSISTÉE SOUS ATTAQUE FILTRÉE (T5)
```

---

## 2. Les Cinq Piliers Interconnectés

| Pilier | Composants du Dépôt | Points Clés Implémentés |
| :--- | :--- | :--- |
| **1. Développement** | `services/auth/`, `services/api/`, `services/remediator/`, `services/executor/`, `services/frontend/` | Authentification JWT HS256 & RBAC, montants exacts en centimes entiers (`int`), clé d'idempotence obligatoire (`Idempotency-Key`), invariant comptable vérifié, automate d'incident et console React + Tailwind CSS. |
| **2. Infrastructure** | `infra/compose/docker-compose.yml`, `infra/ansible/`, `infra/observability/` | 5 réseaux Docker isolés (`edge_net`, `app_net`, `data_net`, `obs_net`, `control_net`), limites CPU/RAM, healthchecks, playbooks Ansible, Prometheus, Grafana et Loki + Promtail. |
| **3. IA / Data** | `ml/`, `services/detector/`, `services/rag/`, `docs/model-card.md` | Modèle `IsolationForest` entraîné sans fuite de données (séparation stricte par sessions), inférence temps réel (`< 0,1 ms`), et assistant RAG local LangChain + Ollama (`<= 8B`) citant les sources documentaires sans aucun privilège système. |
| **4. Cybersécurité** | `services/waf_gateway/`, `infra/waf/`, `scenarios/`, `scripts/secrets_manager.py` | WAF à 2 niveaux (signatures statiques L7 + blocage dynamique AIOps), corrélation SOC, exécuteur confiné à liste fermée et audit chaîné SHA-256, secrets chiffrés SOPS/Age (`ENC[AES256_GCM,...]`), scénario offensif borné avec allowlist IP et kill-switch. |
| **5. Gouvernance** | `docs/governance/ebios-rm.md`, `pca-pra.md`, `nis2-dora-compliance.md`, `executive-recommendations.md` | Analyse EBIOS RM (5 ateliers), PCA/PRA distinguant objectifs RTO/RPO et temps mesurés (MTTD/MTTR), étude réglementaire NIS2 & DORA, et feuille de route d'industrialisation COMEX à 30/90/180 jours. |

---

## 3. Démarrage Rapide et Vérification (Windows PowerShell)

### 3.1 Vérifier l'environnement et les secrets
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-env.ps1
python scripts/secrets_manager.py verify
python scripts/secret_scan.py
```

### 3.2 Exécuter le pipeline ML et la campagne complète de tests (Unitaires, Sécurité, RAG et 3 Répétitions E2E)
```powershell
python ml/generate_dataset.py
python ml/train_evaluate.py
python tests/run_all_tests.py
```

### 3.3 Déployer la plateforme conteneurisée (avec Docker Desktop actif)
```powershell
# Pour un déploiement local sur le PC Hôte :
powershell -ExecutionPolicy Bypass -File .\scripts\up.ps1

# Pour la démonstration sur le Point d'Accès Mobile Windows RESILIENCE-G2 (192.168.137.1) :
$env:HOST_BIND_IP = "192.168.137.1"
powershell -ExecutionPolicy Bypass -File .\scripts\up.ps1
```

### 3.4 Générer les livrables finaux (`Dossier.pdf`, `Pres.pptx`, `Code.zip`)
```powershell
python scripts/build_deliverables.py --group-id G2
```

---

## 4. Documentation de Référence dans `docs/`
- [`docs/architecture.md`](docs/architecture.md) : Architecture, 5 réseaux isolés, modèle de données, automate d'états et budget de ressources.
- [`docs/contracts.md`](docs/contracts.md) : Contrats d'API REST et schémas JSON (`AnomalyEvent`, `RemediationDecision`, `ExecutorCommand`, `RecoveryProof`).
- [`docs/model-card.md`](docs/model-card.md) : Fiche du modèle `IsolationForest`, protocole d'évaluation sans fuite, métriques et limites.
- [`docs/test-report.md`](docs/test-report.md) : Rapport de recette et mesures des 3 répétitions chronométrées.
- [`docs/demo-runbook.md`](docs/demo-runbook.md) : Conducteur seconde par seconde du Clip Chrono (`<= 60 s`) et protocole à 2 PC.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) & [`docs/known-limitations.md`](docs/known-limitations.md) : Dépannage et limites connues.
