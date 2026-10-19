# Plan d'Exécution Ordonné (`docs/implementation-plan.md`)

Ce plan structure la réalisation complète de **PROJECT RESILIENCE-ALPHA** en 12 étapes séquentielles vérifiables (Étapes 0 à 11). Conformément aux règles d'ingénierie, chaque étape possède des livrables précis et un critère de sortie vérifié avant passage à la suivante.

---

## Étape 0 — Audit et Extraction des Exigences
- **Actions** : Lecture intégrale du sujet PDF et de la présentation PPTX ; audit matériel, OS, réseau et outils sur `HDV0-INF-P08` ; initialisation Git ; création des fichiers de gouvernance projet et des ADRs initiaux.
- **Livrables** : `AGENTS.md`, `docs/environment.md`, `docs/requirements-matrix.md`, `docs/implementation-plan.md`, `docs/progress.md`, `docs/decisions/ADR-001` à `ADR-006`.
- **Critère de sortie** : Toutes les exigences sont tracées et les blocages matériels/logiciels sont identifiés explicitement.

## Étape 1 — Conception et Contrats d'Architecture
- **Actions** : Spécification complète de l'architecture cible, de la segmentation réseau Docker, des contrats d'API REST (OpenAPI/JSON Schema), du modèle de données financier, du format des événements d'anomalie ML, du format des décisions de remédiation et de l'automate d'incident (`NORMAL` → `SUSPECT` → `INCIDENT` → `REMEDIATING` → `VERIFYING` → `RECOVERED` / `FAILED`).
- **Livrables** : `docs/architecture.md` (incluant diagrammes Mermaid, budget de ressources estimatif, contrats d'interface et fiche de validation coach).
- **Critère de sortie** : Interfaces, garde-fous anti-boucle et critères de reprise métier définis sans ambiguïté.

## Étape 2 — Squelette, Infrastructure, Déploiement et SOPS
- **Actions** : Création de l'arborescence normalisée (`services/`, `infra/`, `ml/`, `scenarios/`, `tests/`, `scripts/`, `docs/`, `deliverables/`) ; écriture de `infra/compose/docker-compose.yml` (réseaux isolés, limites CPU/RAM, healthchecks), des playbooks Ansible (`infra/ansible/`), de la configuration WAF (`infra/waf/`), de la stack Prometheus/Grafana/Loki (`infra/observability/`), et de l'outillage SOPS/Age (`.sops.yaml`, `scripts/secrets_manager.py`).
- **Livrables** : Arborescence complète, `docker-compose.yml`, `.env.example`, `.gitignore`, `.dockerignore`, playbooks Ansible, scripts PowerShell (`up.ps1`, `down.ps1`, `check-env.ps1`).
- **Critère de sortie** : Validation syntaxique et structurelle (`docker compose config`, validation YAML Ansible/Observabilité, chiffrement local de secrets de test).

## Étape 3 — Plateforme Métier (Auth, API Paiement, Stockage, Frontend Paiement)
- **Actions** : Implémentation du service d'authentification JWT (`services/auth/`), de l'API métier de paiement (`services/api/`) avec montants exacts en centimes, clé d'idempotence (`Idempotency-Key`), contrôle d'intégrité des soldes, persistance atomique (compatible PostgreSQL et SQLite persistant pour exécution locale sans démon Docker), et exposition de métriques.
- **Livrables** : `services/auth/`, `services/api/`, tests unitaires et d'intégration métier (`tests/test_business_platform.py`).
- **Critère de sortie** : 100 % des tests métier (authentification, RBAC, montants invalides, idempotence, persistance après redémarrage, cohérence comptable) à l'état `PASS`.

## Étape 4 — Observabilité, WAF Dynamique et Fonction SOC Intégrée
- **Actions** : Implémentation de la passerelle WAF (`services/waf_gateway/` + configuration Nginx/ModSecurity dans `infra/waf/`), de la collecte de métriques RED (Rate, Errors, Duration) et saturation, des journaux JSON structurés avec `correlation_id`, de la sonde métier continue, de la corrélation SOC multi-sources et du tableau de bord React + Tailwind (`services/frontend/`).
- **Livrables** : `services/waf_gateway/`, `services/frontend/`, `infra/observability/`, `tests/test_observability_soc.py`.
- **Critère de sortie** : Corrélation SOC vérifiée par tests automatisés et interface React compilable/vérifiée consommant exclusivement les endpoints réels.

## Étape 5 — Données et Machine Learning (Isolation Forest)
- **Actions** : Création du générateur de trafic métier normal (avec variations réalistes de charge légitime, pics horaires, erreurs bénignes client) et de sessions d'anomalies ; extraction de variables temporelles par fenêtre glissante ; évaluation comparative d'`IsolationForest` sans fuite de données (train/test séparés par sessions) ; calibration du seuil de décision ; sauvegarde du modèle et de ses métadonnées ; implémentation du microservice d'inférence `services/detector/`. Rédaction de `docs/model-card.md`.
- **Livrables** : `ml/generate_dataset.py`, `ml/train_evaluate.py`, `ml/artifacts/isolation_forest.joblib`, `ml/artifacts/model_metadata.json`, `services/detector/`, `docs/model-card.md`, `tests/test_ml_pipeline.py`.
- **Critère de sortie** : Modèle réellement entraîné et évalué (`PASS`), produisant des scores réels avec mesure du taux de faux positifs et du délai de détection.

## Étape 6 — Scénario d'Attaque Contrôlée (Red Team Bornée)
- **Actions** : Implémentation du scénario de dégradation applicative contrôlée (`scenarios/controlled_attack.py`) simulant un flood applicatif d'opérations coûteuses d'audit/rapprochement (L7 resource exhaustion) qui contourne les signatures statiques initiales du WAF mais provoque une dégradation observable (latence et saturation des workers). Intégration d'une allowlist stricte d'IP cibles, de plafonds de débit/durée/concurrence et d'un arrêt d'urgence (`scenarios/kill_switch.py`).
- **Livrables** : `scenarios/controlled_attack.py`, `scenarios/kill_switch.py`, `scenarios/README.md`, `tests/test_attack_safety.py`.
- **Critère de sortie** : Garde-fous de sécurité testés (`PASS` sur le rejet d'IP hors périmètre et l'arrêt d'urgence). Scénario réseau inter-PC marqué `BLOCKED` tant que le PC Attaquant et le périmètre `192.168.137.1` ne sont pas confirmés.

## Étape 7 — Remédiation Autonome et Exécuteur à Privilèges Limités
- **Actions** : Implémentation de l'orchestrateur de décision (`services/remediator/`) gérant l'automate d'incident et de l'exécuteur confiné (`services/executor/`) appliquant une liste fermée d'actions (`block_ip_waf`, `set_rate_limit_profile`, `recycle_api_workers`, `reset_connection_pool`) avec authentification HMAC, validation stricte et journal d'audit chaîné par empreinte SHA-256. Validation de la sonde métier post-remédiation pendant que l'attaque continue d'être bloquée par le WAF.
- **Livrables** : `services/remediator/`, `services/executor/`, `tests/test_executor_security.py`, `tests/test_remediation_chain.py`.
- **Critère de sortie** : Chaîne complète autonome testée de bout en bout en environnement local multi-services (`PASS`), avec preuve d'une nouvelle transaction métier réussie pendant que le trafic offensif est filtré.

## Étape 8 — Assistant RAG Local (Ollama + LangChain)
- **Actions** : Implémentation du service RAG (`services/rag/`) indexant la documentation réelle du projet (`docs/`, `AGENTS.md`, playbooks) avec découpage par sections, recherche documentaire avec citations exactes des fichiers/sections, intégration LangChain + Ollama (modèle `gemma4:e4b` ou `llama3.2:3b` `<= 8B`), refus explicite d'inventer une procédure absente, et isolation stricte (zéro outil d'exécution).
- **Livrables** : `services/rag/`, `tests/test_rag_assistant.py`.
- **Critère de sortie** : Récupération documentaire et citations vérifiées (`PASS`) ; appel au démon LLM Ollama testé (ou marqué `BLOCKED` si le serveur Ollama local ne peut pas démarrer en session non-interactive).

## Étape 9 — Gouvernance, EBIOS RM, PCA/PRA et Conformité NIS2/DORA
- **Actions** : Rédaction des livrables de gouvernance ancrés dans l'architecture réelle et les mesures du démonstrateur : analyse de risques EBIOS RM (Ateliers 1 à 5), PCA/PRA opérationnel (distinguant objectifs RTO/RPO et mesures observées, avec analyse franche des limites d'un hôte unique), et étude NIS2 (Directive UE 2022/2555) & DORA (Règlement UE 2022/2554) avec arbitrages budgétaires pour un comité de direction.
- **Livrables** : `docs/governance/ebios-rm.md`, `docs/governance/pca-pra.md`, `docs/governance/nis2-dora-compliance.md`, `docs/governance/executive-recommendations.md`.
- **Critère de sortie** : Documents complets, précis, citant les textes officiels et alignés sur les composants livrés.

## Étape 10 — Recette, Répétitions Chronométrées et Rapports de Tests
- **Actions** : Exécution de la campagne complète de tests (unitaires, sécurité exécuteur, scan de secrets, validation configs, et 3 répétitions chronométrées de la boucle complète `Transaction T0 → Attaque → Détection ML → Remédiation WAF/Workers → Transaction T5` sur la pile locale des services en fonctionnement). Rédaction des documents d'exploitation et de recette.
- **Livrables** : `tests/run_all_tests.py`, `tests/test_e2e_resilience.py`, `docs/test-report.md`, `docs/demo-runbook.md`, `docs/troubleshooting.md`, `docs/known-limitations.md`.
- **Critère de sortie** : Rapport de test factuel avec horodatages précis, MTTD/MTTR mesurés en local, et distinction explicite entre validation locale (`PASS`) et validation depuis le 2e PC (`BLOCKED` en attente du PC Attaquant).

## Étape 11 — Génération et Vérification des Livrables Finaux
- **Actions** : Génération automatisée et vérifiée du dossier `deliverables/Workshop2026-M2-G<n>/` contenant le dossier d'ingénierie PDF (`Workshop2026-M2-G<n>-Dossier.pdf`), le support de présentation (`Workshop2026-M2-G<n>-Pres.pptx`), l'archive propre du code (`Workshop2026-M2-G<n>-Code.zip`), et le protocole + conducteur seconde par seconde pour la capture vidéo (`VidChrono-Conducteur-et-Capture.md`, sans inventer de fausse vidéo).
- **Livrables** : `scripts/build_deliverables.py`, `deliverables/Workshop2026-M2-G<n>/`.
- **Critère de sortie** : Existence, ouverture et intégrité du PDF, du PPTX et du ZIP vérifiées par script (`PASS`), absence de secrets dans l'archive (`PASS`), et mention explicite que `VidChrono.mp4` nécessite la captation réelle avec le 2e PC (`BLOCKED`).
