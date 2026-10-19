# AGENTS.md — Règles d'Ingénierie et Guide Opérationnel (PROJECT RESILIENCE-ALPHA)

## 1. Mission Centrale
Réaliser et démontrer **PROJECT RESILIENCE-ALPHA** (Workshop National EPSI Bac+5 — Octobre 2026) : une plateforme de paiement fictive conteneurisée capable d'encaisser une attaque contrôlée lancée depuis un second PC, de détecter l'anomalie par Machine Learning, d'exécuter une remédiation autonome sécurisée sans intervention humaine (**Zero-Touch Recovery**), et de prouver le rétablissement du service par une **nouvelle transaction métier réussie et persistée**.

Chaîne de valeur critique obligatoire :
```text
TRANSACTION RÉUSSIE (T0)
  → ATTAQUE CONTRÔLÉE DEPUIS PC ATTAQUANT (T1)
  → DÉGRADATION OBSERVABLE (T2)
  → DÉTECTION ML (Isolation Forest) (T3)
  → REMÉDIATION AUTOMATIQUE BORNÉE (T4)
  → NOUVELLE TRANSACTION MÉTIER RÉUSSIE & VÉRIFIÉE (T5)
```

## 2. Règles Impératives de Travail et de Sécurité
1. **Zéro Simulation Frauduleuse** : Aucun composant central laissé en `TODO`. Aucun faux résultat de test. Un test non exécuté est `NOT RUN` ou `BLOCKED`, jamais `PASS`.
2. **Preuve Métier Obligatoire** : Un conteneur redémarré ou un endpoint `/health` ne suffit pas. L'état `RECOVERED` de l'automate d'incident exige une transaction fictive complète (authentification JWT, clé d'idempotence unique, écriture atomique en base, vérification de lecture et cohérence des soldes en centimes).
3. **Sécurité & Périmètre Réseau** :
   - Données 100 % fictives (aucun numéro de carte réel, aucun IBAN réel, aucun secret de production).
   - Cibles offensives strictement limitées à l'IP autorisée du PC Hôte sur le point d'accès isolé du groupe (`192.168.137.1` / `RESILIENCE-G<n>`) ou `127.0.0.1` pour les essais unitaires locaux.
   - Refus par code (allowlist stricte) de toute cible publique, du réseau campus (`10.60.0.0/16`), d'autres groupes ou d'Internet.
   - Plafonds stricts de durée, de débit et de concurrence + arrêt d'urgence (`scenarios/kill_switch.py` / fichier sentinelle).
4. **Confinement des Privilèges** :
   - Le socket Docker n'est **jamais** monté dans `frontend`, `api`, `auth`, `detector`, `remediator` ou `rag`.
   - Seul `executor` peut exécuter une liste fermée (`ALLOWLIST`) d'actions de remédiation validées par schéma Pydantic strict et authentifiées par jeton interne HMAC, avec journal d'audit immuable.
   - L'assistant RAG (`services/rag`) est purement consultatif (lecture documentaire uniquement, aucun outil système ni exécution d'action).
5. **Gestion des Secrets** :
   - Chiffrement avec SOPS + Age (`.sops.yaml`).
   - Aucune clé privée (`age.key`) ni fichier `.env` déchiffré ne doit être commité dans Git ou inclus dans `Workshop2026-M2-G<n>-Code.zip`.

## 3. Contexte Environnemental (PC Hôte Découvert : `HDV0-INF-P08`)
- **OS** : Windows 11 Professionnel (Build 26200)
- **CPU / RAM / GPU** : Intel Core Ultra 9 185H (16 cœurs / 22 threads), 31.42 Go RAM, NVIDIA RTX 4070 Laptop GPU
- **Stockage** : Disque `C:` avec ~41.4 Go libres (vigilance sur la taille des images Docker et caches)
- **Outils natifs présents** :
  - `git` (`C:\Program Files\Git\cmd\git.exe`)
  - `docker` v29.5.3 & `docker compose` v5.1.4 (CLI installée ; démon Docker Desktop à démarrer manuellement par l'opérateur)
  - `python` v3.13.14 (`scikit-learn`, `pandas`, `numpy`, `weasyprint`, `reportlab`, `cryptography`, `PyYAML`, `requests` installés)
  - `node` v22.20.0 & `npm` v10.9.3
  - `ollama` v0.23.0 (modèle local `gemma4:e4b` détecté dans `~/.ollama/models`)
- **Outils absents nativement sur Windows** :
  - `wsl`, `ansible`, `sops`, `age` (compensés par conteneur `ansible-runner` dans Docker Compose et scripts Python/PowerShell de secours documentés).

## 4. Commandes Utiles (PowerShell — Windows)

### 4.1 Vérification de l'environnement et de la configuration
```powershell
# Vérifier l'état des outils et des services
powershell -ExecutionPolicy Bypass -File .\scripts\check-env.ps1

# Valider la syntaxe du fichier Docker Compose
docker compose -f infra/compose/docker-compose.yml config -q
```

### 4.2 Exécution des tests et de la chaîne ML (en local)
```powershell
# Entraîner et évaluer le modèle ML Isolation Forest
python ml/train_evaluate.py

# Lancer la suite complète de tests (unitaires, métier, sécurité, intégration locale, recherche de secrets)
python tests/run_all_tests.py
```

### 4.3 Déploiement et Exploitation Docker Compose (PC Hôte)
```powershell
# Démarrer l'ensemble de la plateforme
powershell -ExecutionPolicy Bypass -File .\scripts\up.ps1

# Arrêter proprement la plateforme (sans supprimer les volumes de données)
powershell -ExecutionPolicy Bypass -File .\scripts\down.ps1
```

### 4.4 Génération des livrables et vérification d'absence de secrets
```powershell
# Scanner le dépôt contre toute fuite de secret
python scripts/secret_scan.py

# Générer les livrables (Dossier PDF, Support PPTX, Archive ZIP propre)
python scripts/build_deliverables.py
```
