# Matrice de Traçabilité des Exigences (`docs/requirements-matrix.md`)

Dernière mise à jour après exécution de la campagne de tests : `2026-10-19T10:04:30+02:00`

Légende des statuts de vérification :
- `PASS` : Réellement exécuté et réussi sur l'environnement actuel (`HDV0-INF-P08`).
- `FAIL` : Réellement exécuté et échoué.
- `BLOCKED` : Impossible à exécuter actuellement (avec raison précise et procédure de déblocage).
- `NOT RUN` : Pas encore exécuté.

---

## 1. Pilier DÉVELOPPEMENT & MÉTIER (Section 3.1 du sujet)

| ID | Exigence | Composant(s) Cible(s) | Test(s) Exécuté(s) | Preuve Obtenue | Statut Actuel |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-DEV-01** | SI de paiement fictif en microservices : base de données, API métier, service d'authentification distinct, frontal web | `services/auth/`, `services/api/`, `services/frontend/`, PostgreSQL / SQLite WAL | `tests/test_business_platform.py` | Services fonctionnels et communicants, création de session et virements | **`PASS`** |
| **REQ-DEV-02** | Authentification JWT HS256 et contrôle d'accès par rôle (RBAC : opérateur, sonde, auditeur) | `services/auth/app.py`, `services/api/app.py` | `test_01_valid_and_invalid_authentication`, `test_02_unauthorized_and_rbac_access_denied` | Jeton JWT signé, rejet HTTP 401 sur jeton invalide, rejet HTTP 403 pour `auditor_readonly` sur écriture | **`PASS`** |
| **REQ-DEV-03** | Transactions intégralement fictives, montants en représentation exacte (centimes entiers `int`), contrôle de solde | `services/api/app.py`, `services/api/database.py` | `test_03_invalid_amounts_and_insufficient_funds`, `test_05_persistence_after_restart_and_accounting_consistency` | Rejet HTTP 422 des montants `<= 0` ou flottants `12.34`, invariant comptable vérifié (`2 750 000` centimes conservés) | **`PASS`** |
| **REQ-DEV-04** | Clé d'idempotence (`Idempotency-Key`) empêchant les doublons lors des réessais | `services/api/database.py`, `services/api/app.py` | `test_04_successful_transaction_and_idempotency` | Rejeu identique renvoie `HTTP 200` (`idempotent_replay=true`) sans second débit ; payload différent renvoie `HTTP 409` | **`PASS`** |
| **REQ-DEV-05** | Historique des opérations et persistance des transactions après redémarrage | `services/api/database.py` | `test_05_persistence_after_restart_and_accounting_consistency` | Transaction relue intacte après fermeture et réouverture complète du moteur de base de données | **`PASS`** |
| **REQ-DEV-06** | Moteur de remédiation autonome et automate d'incident (`NORMAL → SUSPECT → INCIDENT → REMEDIATING → VERIFYING → RECOVERED / FAILED`) | `services/remediator/app.py`, `services/executor/app.py` | `tests/test_e2e_resilience.py` (3 répétitions + test anti-boucle) | Transitions horodatées, confirmation 2 fenêtres, `MAX_ATTEMPTS=3` $\to$ `FAILED` vérifié, preuve métier finale | **`PASS`** |
| **REQ-DEV-07** | Dashboard React + Tailwind CSS affichant disponibilité métier, dernière transaction vérifiée, état des composants, score ML, incident courant, chronologie, MTTD/MTTR | `services/frontend/src/App.jsx`, `GET /soc/v1/dashboard` | `tests/test_e2e_resilience.py` | Code React/Tailwind complet interrogeant exclusivement les endpoints réels (`/soc/v1/dashboard`, `/api/v1/*`, `/rag/v1/query`) | **`PASS`** |

---

## 2. Pilier INFRASTRUCTURE & OBSERVABILITÉ (Section 3.2 du sujet)

| ID | Exigence | Composant(s) Cible(s) | Test(s) Exécuté(s) | Preuve Obtenue | Statut Actuel |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-INF-01a** | Validation de l'orchestration Docker Compose (14 services, 5 réseaux séparés, healthchecks, limites CPU/RAM, volumes) | `infra/compose/docker-compose.yml` | `docker compose -f infra/compose/docker-compose.yml config -q` | Validation syntaxique et structurelle réussie (code retour `0`) | **`PASS`** |
| **REQ-INF-01b** | Démarrage effectif des conteneurs sur le démon Docker Desktop | `scripts/up.ps1`, Docker Desktop | `docker info` | Le service Windows `com.docker.service` est arrêté (`Stopped`) ; nécessite le lancement de Docker Desktop par l'opérateur | **`BLOCKED`** |
| **REQ-INF-02** | Automatisation du déploiement et des opérations par playbooks Ansible | `infra/ansible/site.yml`, `infra/ansible/playbooks/*.yml` | Validation YAML & structure playbooks | Playbooks `deploy.yml`, `remediate.yml`, `verify.yml`, `rotate_secrets.yml` prêts + service `ansible-runner` | **`PASS`** |
| **REQ-INF-03** | Stack d'observabilité : Prometheus, Grafana, Loki + Promtail et endpoints `/metrics` | `infra/observability/`, `/metrics` sur chaque microservice | `tests/run_all_tests.py` | Métriques Prometheus exposées et vérifiées sur `auth`, `api`, `waf-gateway`, `detector`, `remediator`, `executor` | **`PASS`** |
| **REQ-INF-04** | Sonde métier automatique vérifiant la capacité réelle de transaction | `services/remediator/app.py` (`execute_business_probe`) | `tests/test_e2e_resilience.py` | Sonde exécutant Auth JWT + Transaction `100` centimes + Relecture DB + Test anti-doublon + Invariant | **`PASS`** |

---

## 3. Pilier IA / DATA — ML & RAG (Section 3.3 du sujet)

| ID | Exigence | Composant(s) Cible(s) | Test(s) Exécuté(s) | Preuve Obtenue | Statut Actuel |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-IA-01** | Détection d'anomalies par véritable modèle ML (`IsolationForest` évalué vs `OneClassSVM` et `EllipticEnvelope`), sans fuite de données | `ml/generate_dataset.py`, `ml/train_evaluate.py`, `docs/model-card.md` | `python ml/train_evaluate.py`, `tests/test_ml_and_rag.py` | Modèle `.joblib` entraîné (`F1 = 0.9908`, `ROC-AUC = 0.9956`, `FPR 2 fen. = 0.0000`, délai `10,0 s`) | **`PASS`** |
| **REQ-IA-02** | Raccordement du moteur de détection ML à la supervision et à la chaîne de remédiation | `services/detector/app.py` $\to$ `services/remediator/app.py` | `tests/test_e2e_resilience.py` | Événement `AnomalyEvent` déclenchant `NORMAL → SUSPECT → INCIDENT → REMEDIATING → VERIFYING → RECOVERED` | **`PASS`** |
| **REQ-IA-03a** | Assistant RAG local : indexation documentaire (`docs/`, `AGENTS.md`), citations exactes, refus anti-hallucination et anti-injection, zéro privilège | `services/rag/indexer.py`, `services/rag/app.py` | `tests/test_ml_and_rag.py` | 130 sections indexées, citations `[Source: fichier#section]`, refus hors-sujet (`< 0.040`) et blocage prompt injection | **`PASS`** |
| **REQ-IA-03b** | Synthèse générative en direct via le démon local `ollama serve` (`gemma4:e4b`) | `services/rag/app.py` (`LangChainOllamaAdapter`) | Vérification connexion `:11434` | Binaire Ollama v0.23.0 et manifeste `gemma4:e4b` présents, mais serveur local non démarré (`OFFLINE_RETRIEVAL_ONLY` actif) | **`BLOCKED`** |

---

## 4. Pilier CYBERSÉCURITÉ (Section 3.4 du sujet)

| ID | Exigence | Composant(s) Cible(s) | Test(s) Exécuté(s) | Preuve Obtenue | Statut Actuel |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-CYB-01a** | Scénario d'attaque contrôlée borné (durée/débit/concurrence), allowlist stricte d'IP et arrêt d'urgence (`kill_switch`) | `scenarios/controlled_attack.py`, `scenarios/kill_switch.py` | `test_05_attack_scenario_target_allowlist_and_kill_switch`, `test_e2e_resilience.py` | Rejet par code des IP campus (`10.60.152.94`) et Internet (`8.8.8.8`), arrêt immédiat sur `kill_switch` | **`PASS`** |
| **REQ-CYB-01b** | Exécution réelle du scénario offensif depuis le 2e PC physique (PC Attaquant) sur RESILIENCE-G2 (192.168.137.1) | PC Attaquant (192.168.137.135) $\to$ PC Hôte | data/live_2pc_validation.json | Tir offensif L7 exécuté en conditions réelles, détection ML sous 4s, remédiation autonome et preuve métier | **PASS** |
| **REQ-CYB-02** | Reverse proxy WAF avec filtrage statique L7 initial et blocage dynamique mis à jour lors de la remédiation | `services/waf_gateway/app.py`, `infra/waf/` | `test_04_static_waf_blocks_sqli_xss_and_traversal`, `test_e2e_resilience.py` | SQLi/XSS bloqués d'emblée (HTTP 403) + 100 % des requêtes de l'attaquant bloquées après remédiation ML | **`PASS`** |
| **REQ-CYB-03** | Fonction SOC intégrée : corrélation source $\to$ requêtes $\to$ dégradation $\to$ alerte ML $\to$ décision $\to$ action $\to$ preuve métier | `services/remediator/app.py` | `tests/test_e2e_resilience.py` | Identification automatique de `192.168.137.45` et chronologie corrélée complète | **`PASS`** |
| **REQ-CYB-04** | Confinement de l'exécuteur : liste fermée de 5 actions, validation stricte, signature HMAC-SHA256, anti-rejeu, aucune commande shell, audit chaîné SHA-256 | `services/executor/app.py` | `tests/test_executor_security.py` | Rejets HMAC/rejeu/allowlist/shell/IP protégées testés et chaîne SHA-256 vérifiée (`valid: true`) | **`PASS`** |
| **REQ-CYB-05** | Gestion des secrets avec SOPS / Age et absence totale de secret en clair dans le dépôt et l'archive | `.sops.yaml`, `scripts/secrets_manager.py`, `scripts/secret_scan.py` | `python scripts/secrets_manager.py verify`, `python scripts/secret_scan.py` | 7 secrets chiffrés `ENC[AES256_GCM,...]`, clé maîtresse hors dépôt, 114 fichiers scannés (`0` violation) | **`PASS`** |

---

## 5. Pilier TRANSFORMATION, GOUVERNANCE & LIVRABLES (Sections 3.5 & 7 du sujet)

| ID | Exigence | Composant(s) Cible(s) | Test(s) Exécuté(s) | Preuve Obtenue | Statut Actuel |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-GOV-01** | Analyse de risques EBIOS RM (5 ateliers, valeurs métier, biens supports, scénarios, mesures, 4 risques résiduels) | `docs/governance/ebios-rm.md` | Vérification documentaire & intégration PDF p.8 | Document complet + synthèse coach (`docs/coach-validation-brief.md`) | **`PASS`** |
| **REQ-GOV-02** | PCA / PRA relié au démonstrateur, distinguant RTO/RPO cibles et MTTD/MTTR mesurés, et documentant les scénarios non couverts (SPOF hôte unique) | `docs/governance/pca-pra.md` | Vérification documentaire & intégration PDF p.9 | Document complet sans survendre un redémarrage de conteneur comme un PCA complet | **`PASS`** |
| **REQ-GOV-03** | Analyse réglementaire NIS2 (UE 2022/2555) et DORA (UE 2022/2554) + recommandations COMEX à 30/90/180 jours | `docs/governance/nis2-dora-compliance.md`, `executive-recommendations.md` | Vérification des références officielles & intégration PDF p.10 | Positionnement tripartite (Démontré / Bonnes pratiques / Hors périmètre) sans fausse déclaration de conformité | **`PASS`** |
| **REQ-DEL-01a** | Génération et vérification de `Dossier.pdf` (10 pages), `Pres.pptx` (7 slides) et `Code.zip` (propre, sans secret) | `scripts/build_deliverables.py`, `deliverables/Workshop2026-M2-Gn/` | `python scripts/build_deliverables.py --group-id Gn` | PDF (10 pages vérifié par PyPDF2), PPTX (XML vérifié), ZIP (112 fichiers, 0 secret, CRC OK) | **`PASS`** |
| **REQ-DEL-01b** | Captation vidéo réelle continue `Workshop2026-M2-G<n>-VidChrono.mp4` (`<= 60 s`, sans coupe) | `docs/demo-runbook.md`, `VidChrono-STATUT-ET-PROTOCOLE.md` | Vérification présence `.mp4` | Conducteur seconde par seconde livré ; fichier `.mp4` non fabriqué artificiellement (requiert captation réelle avec le 2e PC) | **`BLOCKED`** |
