# Journal d'Avancement et Statut des Vérifications (`docs/progress.md`)

Dernière mise à jour : `2026-10-19T12:00:00+02:00` — **Groupe 2 (`G2`)** : **Lenny BARRESI**, **Youssef HANSIL**, **Pierre MICHAUD-EYMOZ**, **Rohail ARSHAD**

---

## Vue d'Ensemble des 12 Étapes (Étapes 0 à 11)

| Étape | Intitulé | Statut | Synthèse Factuelle |
| :--- | :--- | :---: | :--- |
| **Étape 0** | Audit et extraction des exigences | **TERMINÉE (`PASS`)** | Sujet PDF (12p) et PPTX (7 slides) analysés ; audit matériel/réseau `HDV0-INF-P08` ; Git initialisé ; `AGENTS.md`, `environment.md`, `requirements-matrix.md`, `implementation-plan.md` et `ADR-001` à `ADR-006` créés. |
| **Étape 1** | Conception et contrats | **TERMINÉE (`PASS`)** | Architecture 5 réseaux, modèle de données, contrats REST/JSON (`docs/contracts.md`), automate d'incident et fiche coach (`docs/coach-validation-brief.md`) formalisés. |
| **Étape 2** | Squelette, déploiement et SOPS | **TERMINÉE (`PASS`)** | `docker-compose.yml` validé (`config -q` `PASS`), démon Docker Desktop actif (`v29.5.3`), playbooks Ansible créés, chiffrement AEAD `AES-256-GCM` SOPS (`secrets.enc.json`) et `secret_scan.py` `PASS`. |
| **Étape 3** | Plateforme métier | **TERMINÉE (`PASS`)** | `services/auth` (JWT HS256 + RBAC) et `services/api` (centimes entiers, `Idempotency-Key`, persistance SQLite WAL / PostgreSQL, invariant comptable) implémentés et validés (`5/5` tests `PASS`). |
| **Étape 4** | Observabilité, WAF et SOC | **TERMINÉE (`PASS`)** | `services/waf_gateway` (signatures statiques L7 + liste dynamique AIOps), corrélation SOC, configurations Prometheus/Grafana/Loki et Dashboard Live Command Center (`scripts/run_live_platform.py` / `services/frontend/`) créés et actifs sur `192.168.137.1` et `127.0.0.1`. |
| **Étape 5** | Données et Machine Learning | **TERMINÉE (`PASS`)** | Générateur multi-sessions sans fuite (`ml/generate_dataset.py`), entraînement/évaluation comparative `IsolationForest` (`F1=0.9908`, `FPR 2 fen.=0.0000`, délai `10,0 s`), `services/detector` et `docs/model-card.md` validés. |
| **Étape 6** | Attaque contrôlée depuis 2e PC | **TERMINÉE (`PASS`)** | Point d'accès Wi-Fi `RESILIENCE-G2` activé (`192.168.137.1`). 2e PC connecté (`192.168.137.135`). Tir contrôlé L7 réellement exécuté depuis le 2e PC, plafonné et journalisé (`data/live_2pc_validation.json`). |
| **Étape 7** | Remédiation autonome | **TERMINÉE (`PASS`)** | `IsolationForest` a détecté l'attaque (`MTTD = 2,0 s`), l'exécuteur HMAC a banni l'IP `192.168.137.135` (`533` requêtes bloquées WAF en `HTTP 403`), recyclé les workers saturés et prouvé la reprise via sonde métier (`MTTR = 0,10 s`, état `RECOVERED`). |
| **Étape 8** | Assistant RAG local | **TERMINÉE (`PASS` retrieval / `OPTIONNEL` Ollama)** | `services/rag` indexant 130 sections Markdown avec citations `[Source: ...]`, refus anti-hallucination (`< 0.040`) et anti-injection (`PASS`). Prêt pour liaison avec `ollama serve` (`gemma4:e4b`). |
| **Étape 9** | Gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) | **TERMINÉE (`PASS`)** | `ebios-rm.md` (5 ateliers), `pca-pra.md`, `nis2-dora-compliance.md` et `executive-recommendations.md` rédigés et reliés aux composants et mesures réelles. |
| **Étape 10** | Recette et répétitions | **TERMINÉE (`PASS`)** | `9/9` vérifications globales `PASS`, `14/14` tests automatisés `PASS`, validation réelle à 2 PC `PASS`, `test-report.md`, `demo-runbook.md`, `troubleshooting.md`, `known-limitations.md` validés. |
| **Étape 11** | Livrables finaux & Dépôt Git | **TERMINÉE (`PASS` PDF/PPTX/ZIP/Git / `EN ATTENTE` Vidéo)** | `Dossier.pdf` (10 pages), `Pres.pptx` (7 slides), `Code.zip` (116 fichiers, 0 secret) créés dans `deliverables/Workshop2026-M2-G2/`. Projet poussé sur GitHub (`pierre-mcd38/RESILIENCE-ALPHA`). Protocole de captation vidéo 60s documenté. |

---

## Synthèse des Livrables et Statut Git

- **Dépôt Git distant** : [https://github.com/pierre-mcd38/RESILIENCE-ALPHA](https://github.com/pierre-mcd38/RESILIENCE-ALPHA) (Branche `main`, commit `810aaaf`)
- **Dossier technique** : `deliverables/Workshop2026-M2-G2/Workshop2026-M2-G2-Dossier.pdf` (10 pages)
- **Présentation soutenance** : `deliverables/Workshop2026-M2-G2/Workshop2026-M2-G2-Pres.pptx` (7 diapositives)
- **Archive code source** : `deliverables/Workshop2026-M2-G2/Workshop2026-M2-G2-Code.zip` (116 fichiers propres, zéro secret)
- **Vidéo Clip Chrono 60s** : `deliverables/Workshop2026-M2-G2/Workshop2026-M2-G2-VidChrono.mp4` (à enregistrer par l'équipe en écran partagé ou filmé selon le protocole préparé)

