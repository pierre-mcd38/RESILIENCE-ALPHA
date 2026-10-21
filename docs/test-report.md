# Rapport de Recette, Tests Automatisés et Répétitions Chronométrées (`docs/test-report.md`)

Date d'exécution : `2026-10-19T08:00:06Z` (`10:00:06+02:00`)  
Poste d'exécution : PC Hôte `HDV0-INF-P08` (Windows 11 Pro, Intel Core Ultra 9 185H, Python 3.13.14)  
Commande reproductible : `python tests/run_all_tests.py`

---

## 1. Synthèse Globale des Vérifications (`PASS` / `FAIL` / `BLOCKED` / `NOT RUN`)

Conformément à la règle de transparence (Section 2.3 du cahier des charges), aucune vérification non exécutée n'est marquée `PASS`.

| Catégorie de Test / Vérification | Commande / Script | Résultat | Détails Factuels |
| :--- | :--- | :---: | :--- |
| **1. Tests Métier & Paiement** | `tests/test_business_platform.py` (5 tests) | **`PASS`** | Auth JWT HS256 valide/invalide, RBAC `auditor_readonly` refusé (HTTP 403), rejet des montants négatifs/nuls/flottants, idempotence stricte (`Idempotency-Key` 201 $\to$ 200 sans double débit, 409 sur conflit payload), persistance SQLite WAL après redémarrage, conservation de l'invariant comptable. |
| **2. Tests Sécurité Exécuteur & WAF** | `tests/test_executor_security.py` (5 tests) | **`PASS`** | Rejet des requêtes sans HMAC ou horodatage expiré (`> 30s`), rejet du rejeu de `command_id` (HTTP 409), rejet des actions hors `ALLOWLIST`, rejet des métacaractères shell (`; rm -rf /`), protection des IP `127.0.0.1` et `192.168.137.1`, validité de la chaîne d'audit SHA-256, blocage WAF statique (SQLi/XSS), allowlist IP et `kill_switch` fonctionnels. |
| **3. Tests Pipeline ML & Assistant RAG** | `tests/test_ml_and_rag.py` (2 tests) | **`PASS`** | Modèle `IsolationForest` (`F1 = 0.9908`, seuil `-0.1176`, FPR 2 fenêtres = `0.0000`), distinction normale vs dégradation L7, recherche documentaire RAG sur 130 sections avec citations `[Source: ...]`, refus anti-hallucination (`score < 0.040`) et blocage d'injection de prompt. |
| **4. Répétitions E2E & Anti-Boucle** | `tests/test_e2e_resilience.py` (2 tests / 3 runs) | **`PASS`** | 3 répétitions consécutives de la chaîne `T0 → Perturbation → Détection ML → Remédiation WAF/Workers → Sonde & T5` réussies en `~11,1 s` chacune (`< 60 s`). Vérification de la bascule en état `FAILED` après `MAX_ATTEMPTS = 3`. |
| **5. Validation Docker Compose** | `docker compose -f infra/compose/docker-compose.yml config -q` | **`PASS`** | Syntaxe des 14 services, 5 réseaux isolés, limites CPU/RAM et volumes validée (code retour `0`). |
| **6. Gestion et Scan des Secrets** | `python scripts/secrets_manager.py verify` & `secret_scan.py` | **`PASS`** | Chiffrement AEAD `AES-256-GCM` vérifié, clé maîtresse hors dépôt (`~/.config/resilience-alpha/age-master.key`), `0` secret en clair détecté. |
| **7. Déploiement sur Démon Docker** | powershell -File scripts/up.ps1 | **STANDBY_READY** | Démon Docker Desktop installé et configuré. Fichier .env généré à la volée par write-env et volume persistant pi_data intégré. |
| **8. Inférence Générative Ollama Live** | scripts/validate_ollama_live.py & 	est_03 | **PASS** | Serveur ollama serve actif avec modèle gemma4:e4b (8.0B paramètres, conforme <= 8B). LangChain actif, réponses sourcées avec citations [Source: ...], refus hors périmètre et repli hors-ligne validés (data/live_ollama_validation.json). |
| **9. Tir Réseau depuis le 2e PC (Attaque L7)** | scenarios/controlled_attack.py | **PASS** | Exécuté en conditions réelles sur Wi-Fi RESILIENCE-G2 (192.168.137.1) depuis le 2e PC (192.168.137.135). Preuve complète journalisée dans data/live_2pc_validation.json (délai détection 4s, remédiation autonome, transaction T5 réussie). |
| **10. Clip Chrono Obligatoire (VidChrono.mp4)** | Workshop2026-M2-G2-VidChrono.mp4 (<= 60s) | **STANDBY_READY** | Conducteur de tir seconde par seconde et protocole formalisés (VidChrono-STATUT-ET-PROTOCOLE.md). La captation physique continue sera enregistrée par l'équipe lors de la répétition générale sans fabrication artificielle. |

---

## 2. Résultats Détaillés des 3 Répétitions Chronométrées (`data/rehearsal_runs.json`)

> **Important** : Ces 3 répétitions ont été exécutées sur la pile complète interconnectée des services sur `HDV0-INF-P08`. Elles prouvent le fonctionnement bout en bout du code et la tenue de l'objectif `< 60 s`, mais ne remplacent pas l'essai réseau depuis le second PC physique.

| Mesure / Preuve | Répétition #1 | Répétition #2 | Répétition #3 |
| :--- | :--- | :--- | :--- |
| **Identifiant d'incident** | `INC-20261019-38169D` | `INC-20261019-3B41F5` | `INC-20261019-B23929` |
| **Début perturbation (UTC)** | `07:59:22.786Z` | `07:59:34.361Z` | `07:59:45.921Z` |
| **Détection confirmée (UTC)** | `07:59:32.976Z` | `07:59:44.558Z` | `07:59:56.097Z` |
| **Reprise prouvée `RECOVERED` (UTC)** | `07:59:33.161Z` | `07:59:44.757Z` | `07:59:56.278Z` |
| **IP source corrélée par le SOC** | `192.168.137.45` | `192.168.137.45` | `192.168.137.45` |
| **Score ML minimal (`IsolationForest`)** | `-0.2160` (`< -0.1176`) | `-0.2160` (`< -0.1176`) | `-0.2160` (`< -0.1176`) |
| **Latence P95 pendant dégradation** | `882,25 ms` | `882,86 ms` | `880,89 ms` |
| **Latence après remédiation** | `24,75 ms` | `26,64 ms` | `25,91 ms` |
| **MTTD mesuré (2 fenêtres ML)** | **`10,19 s`** | **`10,20 s`** | **`10,18 s`** |
| **MTTR mesuré (Actions + Sonde)** | **`0,19 s`** | **`0,20 s`** | **`0,18 s`** |
| **Durée totale de l'incident** | **`10,38 s`** | **`10,40 s`** | **`10,36 s`** |
| **Durée séquence complète (T0 $\to$ T5)** | **`11,14 s`** (`<= 60 s`) | **`11,15 s`** (`<= 60 s`) | **`11,11 s`** (`<= 60 s`) |
| **Transaction initiale `T0`** | `tx-04d03bd8-17fb...` | `tx-f22a2a57-210a...` | `tx-a24c6d7d-67e9...` |
| **Transaction sonde `RECOVERY`** | `tx-1aa6411e-615f...` | `tx-7a37d262-04d5...` | `tx-31756819-5862...` |
| **Transaction opérateur `T5`** | `tx-abde3038-b8ef...` | `tx-6eb5dcd5-8297...` | `tx-35913f2c-ea5e...` |
| **Requêtes offensives bloquées (HTTP 403) pendant T5** | `12 / 12` (`100 %`) | `12 / 12` (`100 %`) | `12 / 12` (`100 %`) |
| **Invariant comptable & Chaîne d'audit SHA-256** | `True` / `True` | `True` / `True` | `True` / `True` |
