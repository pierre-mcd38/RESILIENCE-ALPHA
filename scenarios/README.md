# Scénario de Perturbation Applicative Contrôlée (`scenarios/README.md`)

Ce dossier contient l'outillage de test de résilience borné destiné à démontrer la chaîne **Zero-Touch Recovery** de **PROJECT RESILIENCE-ALPHA**.

## 1. Garde-fous de Sécurité Impératifs
- **Liste blanche stricte (`ALLOWED_HOSTS`)** : Seules les cibles `127.0.0.1`, `localhost` (essais locaux sur le PC Hôte) et `192.168.137.1` (interface du PC Hôte sur le point d'accès mobile isolé `RESILIENCE-G<n>`) sont autorisées.
- **Refus automatique hors périmètre** : Toute adresse du réseau campus (`10.60.0.0/16`), d'un autre sous-réseau ou d'Internet lève immédiatement une exception `PermissionError` avant tout envoi réseau.
- **Plafonds matériels codés en dur** :
  - Durée maximale : `45 secondes` (`MAX_DURATION_SECONDS = 45.0`)
  - Débit maximal : `50 req/s` (`MAX_RATE_RPS = 50.0`)
  - Concurrence maximale : `8 threads` (`MAX_CONCURRENCY = 8`)
- **Arrêt d'urgence (`scenarios/kill_switch.py`)** :
  ```powershell
  # Interrompre immédiatement tout scénario en cours (< 50 ms)
  python scenarios/kill_switch.py engage

  # Réarmer après vérification
  python scenarios/kill_switch.py release
  ```

## 2. Fonctionnement Technique et Complémentarité WAF / ML
1. **Passage initial à travers le WAF statique** : Le script sollicite l'endpoint `/api/v1/transactions/verify-batch` avec des charges JSON syntaxiquement valides (aucune injection SQL/XSS). Les signatures statiques de Niveau 1 laissent donc légitimement passer ces requêtes initiales.
2. **Dégradation observable** : L'accumulation d'appels de vérification cryptographique par lots sature les workers de l'API métier (`cpu_worker_saturation` $\to 0.95+$, `latency_p95_ms` $> 600\text{ ms}$).
3. **Détection ML et Remédiation Dynamique** : Le modèle `IsolationForest` détecte l'anomalie multivariée en 2 fenêtres consécutives. Le moteur `remediator` identifie l'IP source dominante dans les logs du WAF et ordonne à `executor` :
   - l'ajout de l'IP dans la `dynamic_blocklist` du WAF (`HTTP 403`) ;
   - le passage du WAF en profil `strict_mitigation` (`HTTP 429`) ;
   - le recyclage des workers saturés de l'API métier.
4. **Preuve sous charge continue** : Alors que le scénario continue d'émettre des requêtes, celles-ci sont bloquées en périphérie par le WAF (`status_counts["403"]` augmente), et la sonde métier exécute avec succès une nouvelle transaction fictive vérifiée en base.
