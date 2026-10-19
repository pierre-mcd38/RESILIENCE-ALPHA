# Journal d'Avancement et Statut des Vérifications (`docs/progress.md`)

Dernière mise à jour : `2026-10-19T10:05:00+02:00`

---

## Vue d'Ensemble des 12 Étapes (Étapes 0 à 11)

| Étape | Intitulé | Statut | Synthèse Factuelle |
| :--- | :--- | :---: | :--- |
| **Étape 0** | Audit et extraction des exigences | **TERMINÉE (`PASS`)** | Sujet PDF (12p) et PPTX (7 slides) analysés ; audit matériel/réseau `HDV0-INF-P08` ; Git initialisé ; `AGENTS.md`, `environment.md`, `requirements-matrix.md`, `implementation-plan.md` et `ADR-001` à `ADR-006` créés. |
| **Étape 1** | Conception et contrats | **TERMINÉE (`PASS`)** | Architecture 5 réseaux, modèle de données, contrats REST/JSON (`docs/contracts.md`), automate d'incident et fiche coach (`docs/coach-validation-brief.md`) formalisés. |
| **Étape 2** | Squelette, déploiement et SOPS | **TERMINÉE (`PASS` / `BLOCKED` démon)** | `docker-compose.yml` validé (`config -q` `PASS`), playbooks Ansible créés, chiffrement AEAD `AES-256-GCM` SOPS (`secrets.enc.json`) et `secret_scan.py` `PASS`. Démarrage des conteneurs `BLOCKED` tant que Docker Desktop est arrêté. |
| **Étape 3** | Plateforme métier | **TERMINÉE (`PASS`)** | `services/auth` (JWT HS256 + RBAC) et `services/api` (centimes entiers, `Idempotency-Key`, persistance SQLite WAL / PostgreSQL, invariant comptable) implémentés et validés (`5/5` tests `PASS`). |
| **Étape 4** | Observabilité, WAF et SOC | **TERMINÉE (`PASS`)** | `services/waf_gateway` (signatures statiques L7 + liste dynamique AIOps), corrélation SOC, configurations Prometheus/Grafana/Loki et Dashboard `React + Tailwind CSS` (`services/frontend/`) créés. |
| **Étape 5** | Données et Machine Learning | **TERMINÉE (`PASS`)** | Générateur multi-sessions sans fuite (`ml/generate_dataset.py`), entraînement/évaluation comparative `IsolationForest` (`F1=0.9908`, `FPR 2 fen.=0.0000`, délai `10,0 s`), `services/detector` et `docs/model-card.md` validés. |
| **Étape 6** | Attaque contrôlée | **TERMINÉE (`PASS` local / `BLOCKED` 2e PC)** | `scenarios/controlled_attack.py` et `scenarios/kill_switch.py` implémentés avec allowlist stricte (`127.0.0.1` / `192.168.137.1`), plafonds matériels et arrêt `< 50 ms`. Tir depuis le 2e PC `BLOCKED` en attente du Wi-Fi `RESILIENCE-G<n>`. |
| **Étape 7** | Remédiation autonome | **TERMINÉE (`PASS`)** | `services/remediator` + `services/executor` (HMAC-SHA256, anti-rejeu, allowlist de 5 actions sans shell, audit chaîné SHA-256) + sonde métier post-reprise validés sous attaque continue. |
| **Étape 8** | Assistant RAG local | **TERMINÉE (`PASS` retrieval / `BLOCKED` Ollama live)** | `services/rag` indexant 130 sections Markdown avec citations `[Source: ...]`, refus anti-hallucination (`< 0.12`) et anti-injection (`PASS`). Génération LLM live `BLOCKED` tant que `ollama serve` n'est pas démarré. |
| **Étape 9** | Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | **TERMINÉE (`PASS`)** | `ebios-rm.md`, `pca-pra.md`, `nis2-dora-compliance.md` et `executive-recommendations.md` rédigés et reliés aux composants et mesures réelles. |
| **Étape 10** | Recette et répétitions | **TERMINÉE (`PASS`)** | `14/14` tests automatisés `PASS` (`python tests/run_all_tests.py`), 3 répétitions E2E chronométrées (`~11,1 s` chacune, `< 60 s`), `test-report.md`, `demo-runbook.md`, `troubleshooting.md`, `known-limitations.md` créés. |
| **Étape 11** | Livrables finaux | **TERMINÉE (`PASS` PDF/PPTX/ZIP / `BLOCKED` MP4)** | `Dossier.pdf` (10 pages), `Pres.pptx` (7 slides), `Code.zip` (112 fichiers, 0 secret) générés et vérifiés dans `deliverables/Workshop2026-M2-Gn/`. `VidChrono.mp4` documenté comme nécessitant la captation réelle à 2 PC. |

---

## Commandes Réellement Exécutées et Statuts

1. `docker compose -f infra/compose/docker-compose.yml config -q` $\to$ **`PASS`** (Code 0)
2. `python scripts/secrets_manager.py bootstrap` & `python scripts/secrets_manager.py verify` $\to$ **`PASS`** (7 secrets chiffrés `AES-256-GCM`, clé hors dépôt)
3. `python ml/generate_dataset.py` & `python ml/train_evaluate.py` $\to$ **`PASS`** (`isolation_forest.joblib` et `model_metadata.json` générés)
4. `python tests/run_all_tests.py` $\to$ **`PASS`** (`14/14` tests réussis, 3 répétitions E2E enregistrées dans `data/rehearsal_runs.json`)
5. `python scripts/build_deliverables.py --group-id Gn` $\to$ **`PASS`** (PDF 10p, PPTX 7 slides, ZIP 112 fichiers vérifiés)
6. `python scripts/secret_scan.py` $\to$ **`PASS`** (`114` fichiers inspectés, `0` secret en clair)
