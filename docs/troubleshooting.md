# Guide de Dépannage Opérationnel (`docs/troubleshooting.md`)

Ce guide recense les incidents techniques pouvant survenir sur l'environnement Windows 11 (`HDV0-INF-P08`) et leur résolution immédiate sans compromettre la sécurité du laboratoire.

---

## 1. Démon Docker Desktop Arrêté (`npipe:////./pipe/dockerDesktopLinuxEngine`)

### Symptôme
La commande `docker info` ou `scripts/up.ps1` retourne :
`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`

### Cause
Le service Windows `com.docker.service` est configuré en démarrage manuel (`Manual`) et l'application Docker Desktop n'est pas lancée dans la session graphique Windows.

### Résolution
1. Lancer l'application **Docker Desktop** depuis le menu Démarrer Windows et attendre que l'icône de la barre d'état passe à *Engine running* (~20 secondes).
2. Vérifier avec :
   ```powershell
   docker info
   powershell -ExecutionPolicy Bypass -File .\scripts\up.ps1
   ```
3. **Mode de secours immédiat sans Docker** : Si Docker Desktop est indisponible sur le poste de soutenance, tous les microservices Python (`auth`, `api`, `waf_gateway`, `detector`, `remediator`, `executor`, `rag`) fonctionnent nativement sous Python 3.13 avec persistance SQLite WAL et peuvent être testés immédiatement via `python tests/run_all_tests.py`.

---

## 2. Point d'Accès Mobile Windows (`192.168.137.1`) Non Actif

### Symptôme
L'adresse `192.168.137.1` n'apparaît pas dans `Get-NetIPAddress` et l'interface `Connexion au réseau local* 10` possède une adresse APIPA `169.254.x.x`.

### Résolution
1. Ouvrir **Paramètres Windows $\to$ Réseau et Internet $\to$ Point d'accès sans fil mobile**.
2. Configurer le nom du réseau sur `RESILIENCE-G<n>` et basculer l'interrupteur sur **Activé**.
3. Vérifier l'attribution de l'IP `192.168.137.1` :
   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq '192.168.137.1' }
   ```
4. **Attention Sécurité** : Ne jamais désactiver globalement le pare-feu Windows. Si le port `8080` ou `3000` est filtré sur l'interface privée `192.168.137.1`, demander confirmation à l'opérateur avant d'ajouter une règle entrante limitée exclusivement au sous-réseau local `192.168.137.0/24`.

---

## 3. Serveur Ollama Local Injoignable (`localhost:11434`)

### Symptôme
L'assistant RAG répond avec `"llm_status": "OFFLINE_RETRIEVAL_ONLY"`.

### Cause
Le démon Ollama n'est pas actif en arrière-plan.

### Résolution
1. Ouvrir un terminal PowerShell dédié dans la session utilisateur et lancer :
   ```powershell
   $env:OLLAMA_HOST = "127.0.0.1:11434"
   ollama serve
   ```
2. Vérifier la présence du modèle local (`gemma4:e4b` `<= 8B`) :
   ```powershell
   ollama list
   ```
3. **Impact sur la démo** : Conformément à `ADR-005`, l'assistant RAG est **hors du chemin critique**. Même si Ollama reste éteint, la détection ML (`IsolationForest`), la remédiation autonome et la recherche documentaire citée (`[Source: ...]`) restent 100 % fonctionnelles.

---

## 4. Déblocage d'une IP ou Réinitialisation de l'Automate Entre Deux Prises Vidéo

### Symptôme
Après un premier essai réussi, l'IP du PC Attaquant (`192.168.137.45`) est bloquée dans la `dynamic_blocklist` du WAF pendant 300 secondes, ou l'automate est en état `RECOVERED` / `FAILED`.

### Résolution
1. Relâcher le kill-switch s'il a été activé :
   ```powershell
   python scenarios/kill_switch.py release
   ```
2. Réinitialiser l'état de l'automate vers `NORMAL` :
   ```powershell
   curl.exe -X POST http://127.0.0.1:8004/soc/v1/reset-state
   ```
