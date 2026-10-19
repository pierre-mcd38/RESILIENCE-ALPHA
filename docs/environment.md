# Audit de l'Environnement et Paramètres du Projet (`docs/environment.md`)

Date de l'audit initial : `2026-10-19T09:23:00+02:00`

---

## 1. Paramètres du Projet et du Consortium

| Paramètre | Valeur / État Actuel | Statut | Action Requise |
| :--- | :--- | :--- | :--- |
| **Projet** | `PROJECT RESILIENCE-ALPHA` | Confirmé | — |
| **Cadre** | Workshop National EPSI Bac+5 (Sprint 4 jours — Octobre 2026) | Confirmé | — |
| **Numéro du groupe (`<n>`)** | `2` (`G2` — Dossier `Workshop2026-M2-G2`, Wi-Fi `RESILIENCE-G2`) | **CONFIRMÉ (`G2`)** | — |
| **Membres et contributions** | **Lenny BARRESI**, **Youssef HANSIL**, **Pierre MICHAUD-EYMOZ**, **Rohail ARSHAD** (table de traçabilité nominative intégrée au dossier PDF et au PPTX) | **CONFIRMÉ (4 membres)** | — |
| **PC Hôte** | `HDV0-INF-P08` (`SEYSSINET-PARISET.LOCAL`) — ASUS ROG Zephyrus G16 (`GU605MI`) | **CONFIRMÉ & ACTIF** | Docker Desktop actif (`v29.5.3`) ; Point d'accès `RESILIENCE-G2` actif (`192.168.137.1/24`) |
| **PC Attaquant** | Poste 2 connecté sur `RESILIENCE-G2` — IP **`192.168.137.135`** (`MAC : 74-04-F1-EA-7E-D2`) | **CONFIRMÉ & TESTÉ (`PASS`)** | Tir contrôlé réel exécuté vers `192.168.137.1:8080`, détecté par `IsolationForest` (`MTTD=2,0s`), bloqué dynamiquement (`533` requêtes `HTTP 403`) et suivi de `RECOVERED` (`MTTR=0,10s`) |
| **PC IA facultatif** | Non requis matériellement (PC Hôte dispose de 31.4 Go RAM + RTX 4070 8 Go VRAM), mais supporté par configuration (`OLLAMA_BASE_URL`) | **DÉCOUVERT / OPTIONNEL** | Confirmer si Ollama reste sur le PC Hôte ou est déporté |
| **Contraintes du coach** | `À RENSEIGNER` (validation jalon Lundi : architecture + EBIOS RM préparée pour revue) | **À RENSEIGNER** | Faire valider l'architecture et la matrice EBIOS RM par le coach |

---

## 2. Ressources Matérielles Découvertes sur le PC Hôte (`HDV0-INF-P08`)

| Composant | Mesure Réelle Observée | Prérequis Sujet Officiel (PDF p.6) | Évaluation |
| :--- | :--- | :--- | :--- |
| **Système d'exploitation** | Microsoft Windows 11 Professionnel (`10.0.26200`) | Windows 10 ou 11 | **CONFORME** |
| **Processeur (CPU)** | Intel(R) Core(TM) Ultra 9 185H — 16 cœurs physiques / 22 processeurs logiques | 4 cœurs minimum (6–8 recommandés) | **EXCELLENT** |
| **Mémoire vive (RAM)** | `31.42 Go` total (`33 735 987 200` octets) ; `~4.04–4.98 Go` libres au moment de l'audit | 16 Go minimum (32 Go recommandés) | **ATTENTION (RAM libre)** : 31.4 Go installés, mais ~26.5 Go déjà occupés par les processus hôtes. Limites mémoire strictes requises sur les conteneurs. |
| **Processeur Graphique (GPU)** | NVIDIA GeForce RTX 4070 Laptop GPU (8 Go VRAM dédiée) + Intel Arc Graphics | Optionnel (utile pour Ollama) | **EXCELLENT** |
| **Stockage Disque (`C:`)** | `41.46 Go` libres sur `952.79 Go` (`911.33 Go` utilisés) | 50 Go libres sur SSD (100 Go recommandés) | **VIGILANCE** : Légèrement sous le seuil de 50 Go. Utilisation d'images Alpine/Slim (`python:3.12-slim`, `postgres:16-alpine`, `nginx:1.27-alpine`) impérative. |

---

## 3. Interfaces Réseau Découvertes sur le PC Hôte

| Interface | Adresse IPv4 Actuelle | Masque | Rôle & Statut Sécurité |
| :--- | :--- | :--- | :--- |
| `Wi-Fi` | `10.60.152.94` | `/21` | **Réseau Campus — HORS PÉRIMÈTRE OFFENSIF (INTERDICTION STRICTE)** |
| `vEthernet (Default Switch)` | `172.29.16.1` | `/20` | Switch interne Hyper-V |
| `VMware Network Adapter VMnet8` | `192.168.14.1` | `/24` | Réseau NAT VMware local |
| `VMware Network Adapter VMnet1` | `192.168.220.1` | `/24` | Réseau Host-Only VMware local |
| `Connexion au réseau local* 10` | `192.168.137.1` | `/24` | **ACTIF (`PASS`)** : Point d'accès sans fil mobile Windows `RESILIENCE-G2` (2e PC connecté en `192.168.137.135`) |

---

## 4. Audit des Outils Logiciels

| Outil | Statut | Version / Chemin Découvert | Détails & Impact Opérationnel |
| :--- | :--- | :--- | :--- |
| **Git** | `PASS` | `C:\Program Files\Git\cmd\git.exe` | Dépôt Git initialisé dans `TP_WORKGROUP`. |
| **Docker CLI** | `PASS` | `29.5.3, build d1c06ef` | Binaire présent. Contextes : `desktop-linux` et `default`. |
| **Docker Compose** | `PASS` | `v5.1.4` | Validation syntaxique et orchestration (`docker compose config` : `PASS`). |
| **Docker Daemon** | `PASS` | `ServerVersion=29.5.3` (22 CPUs, 16.46 Go RAM alloués) | Démon Docker Desktop actif et vérifié (`docker info` code retour `0`). |
| **WSL (`wsl.exe`)** | `BLOCKED` | Absent de `C:\Windows\System32\wsl.exe` | Non installé ou non exposé dans le PATH système. Les scripts du projet sont fournis en PowerShell natif (`.ps1`) et Python multiplateforme (`.py`) pour ne pas dépendre de bash/WSL. |
| **Python** | `PASS` | `Python 3.13.14` | Bibliothèques déjà présentes : `scikit-learn 1.7.2`, `pandas 2.3.3`, `numpy 2.3.5`, `Flask 3.1.3`, `weasyprint 69.0`, `reportlab 5.0.0`, `cryptography 48.0.0`, `PyYAML 6.0.3`, `requests 2.33.1`, `joblib 1.5.2`. |
| **Node.js & npm** | `PASS` | `node v22.20.0` / `npm 10.9.3` | Disponibles nativement pour le frontend React + Tailwind. |
| **Ollama** | `PARTIAL / BLOCKED` | `v0.23.0` (`...\Programs\Ollama\ollama.exe`) | Binaire présent. Manifeste `gemma4:e4b` présent dans `~/.ollama/models`, mais le serveur Ollama n'est pas démarré actuellement (`could not connect to a running Ollama instance`). |
| **Ansible** | `MISSING (Host)` | Non présent sous Windows natif | Contournement propre implémenté : playbooks Ansible standards dans `infra/ansible/` + service conteneurisé `ansible-runner` et script de validation structurelle YAML/Jinja. |
| **SOPS / Age** | `MISSING (Host)` | Binaires `sops` / `age` absents du PATH | Configuration `.sops.yaml` standard fournie + outil Python local de chiffrement/déchiffrement compatible SOPS-envelope (`scripts/secrets_manager.py` basé sur `cryptography` / `PyNaCl` installés) pour garantir zéro secret en clair. |

---

## 5. Contraintes Windows / Docker et Commandes par Contexte

1. **Pas de dépendance obligatoire à WSL côté scripts** : Tous les scripts d'orchestration (`scripts/*.ps1`) et d'exécution/test (`scripts/*.py`, `tests/*.py`, `ml/*.py`, `scenarios/*.py`) s'exécutent nativement sous Windows PowerShell et Python 3.13.
2. **Démarrage du démon Docker** : Conformément aux règles de sécurité de l'agent, aucune modification de service système Windows (`com.docker.service`) ni installation globale n'est lancée sans confirmation. En attendant le démarrage de Docker Desktop par l'opérateur, l'intégralité des microservices peut être testée en processus locaux isolés ET validée via `docker compose config`.
3. **Publication réseau restreinte** : Dans `infra/compose/docker-compose.yml`, les ports exposés peuvent être liés à `${HOST_BIND_IP:-127.0.0.1}` (ou `192.168.137.1` lors de la démo sur le Point d'Accès Mobile Windows `RESILIENCE-G<n>`) afin de ne jamais exposer l'infrastructure sur le Wi-Fi du campus (`10.60.152.94`).
