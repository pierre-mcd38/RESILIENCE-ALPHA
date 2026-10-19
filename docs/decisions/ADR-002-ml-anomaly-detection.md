# ADR-002 : Détection d'Anomalies par Machine Learning (`IsolationForest` Calibré sur Fenêtres Glissantes)

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le sujet interdit de réduire la détection d'anomalies à de simples seuils fixes sur le débit. Le modèle doit exploiter des métriques ou journaux réels, distinguer une charge légitime variable (pics horaires, erreurs de saisie bénignes) d'un comportement offensif, et alimenter la remédiation automatique en moins de 15 secondes pour tenir dans le format du Clip Chrono (60 s max).
- **Décision** :
  1. **Vecteur de caractéristiques (7 variables par fenêtre de 5 secondes)** :
     - `req_rate_rps` : débit total de requêtes par seconde ;
     - `latency_p95_ms` : 95e centile du temps de réponse applicatif ;
     - `error_rate_ratio` : proportion de réponses HTTP 4xx/5xx ;
     - `expensive_endpoint_ratio` : proportion d'appels vers les routes coûteuses (`/api/v1/transactions/verify-batch`, `/api/v1/audit/reconcile`) ;
     - `unique_ip_entropy` : entropie de distribution des adresses IP sources (faible lorsqu'une seule IP concentre la charge) ;
     - `cpu_worker_saturation` : taux d'occupation des workers applicatifs ;
     - `tx_success_ratio` : ratio de transactions métier abouties par rapport au trafic entrant.
  2. **Évaluation comparative sans fuite de données** :
     - Séparation stricte par sessions temporelles indépendantes (sessions d'entraînement normales variées vs sessions de validation/test normales et d'attaque).
     - Comparaison d'`IsolationForest` (`scikit-learn`) avec `OneClassSVM` et `EllipticEnvelope` / Z-score robuste.
  3. **Calibration et confirmation** :
     - `IsolationForest` produit un score continu d'anomalie. Un seuil calibré sur le jeu de validation + l'exigence de **2 fenêtres consécutives anormales** déclenche la transition `NORMAL → SUSPECT → INCIDENT` afin de réduire les faux positifs sur les micro-pics légitimes.
- **Conséquences** :
  - Temps d'inférence `< 5 ms` sur CPU (aucun GPU requis pour la détection).
  - Explicabilité complète devant le jury (importance des variables par permutation et frontière de décision documentée dans `docs/model-card.md`).
