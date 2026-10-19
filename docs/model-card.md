# Model Card — Détection d'Anomalies AIOps (`isolation_forest_v1`)

Document de référence ML & AIOps — **PROJECT RESILIENCE-ALPHA** (Étape 5 — Conformité `REQ-IA-01`, `REQ-IA-02` et `ADR-002`).

---

## 1. Identité et Objectif Opérationnel du Modèle

| Propriété | Valeur Exacte (`ml/artifacts/model_metadata.json`) |
| :--- | :--- |
| **Nom du modèle** | `isolation_forest_v1` |
| **Version** | `1.0.0` |
| **Algorithme** | `sklearn.pipeline.Pipeline(StandardScaler + IsolationForest)` |
| **Hyperparamètres** | `n_estimators = 200`, `max_samples = "auto"`, `contamination = 0.02`, `random_state = 20261019` |
| **Artefact binaire** | `ml/artifacts/isolation_forest.joblib` |
| **Métadonnées d'audit** | `ml/artifacts/model_metadata.json` |
| **Fenêtre d'observation** | `5 secondes` (`window_seconds = 5`) |
| **Seuil de décision calibré** | `decision_threshold = -0.1176` (`score < -0.1176` $\Rightarrow$ fenêtre anormale) |
| **Règle de confirmation** | **2 fenêtres consécutives anormales** (`NORMAL` $\rightarrow$ `SUSPECT` $\rightarrow$ `INCIDENT`) |
| **Temps d'inférence mesuré** | `0,0344 ms` par fenêtre sur CPU (`< 0,1 ms`, aucun GPU requis) |
| **Temps d'entraînement mesuré** | `333,53 ms` sur CPU (`HDV0-INF-P08`) |

### Rôle dans la Chaîne Critique Zero-Touch
Le modèle `isolation_forest_v1` est embarqué dans le microservice `services/detector` (`:8003`). Il évalue toutes les 5 secondes l'état conjoint du reverse proxy WAF (`services/waf_gateway`) et de l'API métier de paiement (`services/api`). Contrairement à une règle statique sur le seul débit HTTP, il distingue :
- **Les variations légitimes du trafic métier** : périodes de repos nocturne (`normal_idle`), activité nominale (`normal_nominal`), **pics horaires légitimes de fin de journée** (`normal_legitimate_peak`), **erreurs HTTP 4xx bénignes de saisie client** (`normal_benign_4xx`), et **rapprochements comptables planifiés** (`normal_scheduled_audit`).
- **Les dégradations et attaques applicatives de couche 7** : flood d'épuisement de ressources sur `/api/v1/transactions/verify-batch` (`attack_l7_verify_batch_flood`), dégradation progressive de latence / contention pool DB (`incident_latency_degradation`), et attaque par force brute sur l'authentification JWT (`attack_auth_brute_force`).

---

## 2. Vecteur de Caractéristiques (7 Variables par Fenêtre de 5 s)

Aucune colonne cachée ou artificielle (telle que `attack_launched`) n'existe dans les données ni dans le pipeline. Le modèle reçoit exclusivement les 7 variables observables définies dans `ml/features.py` :

| # | Variable | Unité / Domaine | Moyenne Normale ($\mu$) | Écart-Type Normal ($\sigma$) | Intervalle Normal `[P05 ; P95]` | Sens d'Anomalie | Importance par Permutation |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `latency_p95_ms` | `ms` ($\ge 0$) | `46,17 ms` | `24,10 ms` | `[17,07 ; 90,03]` | $\uparrow$ Hausse | **18,79 %** (1re) |
| 2 | `error_rate_ratio` | `[0.0, 1.0]` | `0,0364` | `0,0378` | `[0,0032 ; 0,1248]` | $\uparrow$ Hausse | **17,71 %** (2e) |
| 3 | `tx_success_ratio` | `[0.0, 1.0]` | `0,8996` | `0,0573` | `[0,7902 ; 0,9771]` | $\downarrow$ Chute | **15,22 %** (3e) |
| 4 | `req_rate_rps` | `req/s` ($\ge 0$) | `16,84 rps` | `10,87 rps` | `[3,37 ; 40,04]` | $\uparrow$ Hausse | **13,33 %** (4e) |
| 5 | `expensive_endpoint_ratio` | `[0.0, 1.0]` | `0,0560` | `0,0546` | `[0,0031 ; 0,1758]` | $\uparrow$ Hausse | **12,87 %** (5e) |
| 6 | `cpu_worker_saturation` | `[0.0, 1.0]` | `0,2991` | `0,1527` | `[0,0822 ; 0,5685]` | $\uparrow$ Hausse | **12,23 %** (6e) |
| 7 | `unique_ip_entropy` | `[0.0, 1.0]` | `0,8082` | `0,0874` | `[0,6603 ; 0,9525]` | $\downarrow$ Chute | **9,85 %** (7e) |

### Pourquoi l'interaction multivariée est indispensable
- Lors d'un **pic horaire légitime** (`normal_legitimate_peak`), `req_rate_rps` monte jusqu'à `~40-48 rps` et `cpu_worker_saturation` jusqu'à `~0,60`, **mais** `unique_ip_entropy` reste très élevée (`> 0,85`, trafic réparti sur de nombreux clients), `expensive_endpoint_ratio` reste bas (`< 0,12`) et `tx_success_ratio` demeure voisin de `0,89`. Le score `IsolationForest` reste supérieur à `-0.1176` (`NORMAL`).
- Lors d'une **saisie erronée bénigne** (`normal_benign_4xx`), `error_rate_ratio` atteint `~0,10-0,15`, mais `latency_p95_ms` reste basse (`~34 ms`) et `cpu_worker_saturation` faible (`~0,23`). Le modèle ne déclenche pas d'alerte.
- Lors du **flood applicatif L7 sur `/verify-batch`** (`attack_l7_verify_batch_flood`), `expensive_endpoint_ratio` bondit (`> 0,75`), `unique_ip_entropy` s'effondre (`< 0,20`, une IP source concentre la charge), `cpu_worker_saturation` dépasse `0,85`, `latency_p95_ms` franchit `500-950 ms` et `tx_success_ratio` chute sous `0,25`. Le score plonge sous `-0,20` dès la première fenêtre.

---

## 3. Protocole d'Entraînement et Garantie d'Absence de Fuite de Données

Les jeux de données sont générés par `ml/generate_dataset.py` avec graine déterministe fixe (`SEED = 20261019`) et cloisonnés par identifiant de session (`session_id`) :

1. **`ml/data/train_normal_sessions.csv` (Entraînement non supervisé / One-Class)** :
   - **75 sessions normales** (`900 fenêtres` de 5 s, **0 fenêtre d'anomalie**).
   - Répartition : 22 sessions `normal_nominal`, 15 `normal_idle`, 15 `normal_legitimate_peak`, 12 `normal_benign_4xx`, 11 `normal_scheduled_audit`.
2. **`ml/data/val_sessions.csv` (Calibration du seuil de décision)** :
   - **40 sessions indépendantes** (`480 fenêtres`) : 25 sessions normales (5 par profil, incluant des micro-pointes transitoires isolées d'une seule fenêtre) + 15 sessions d'incident (5 `attack_l7_verify_batch_flood`, 5 `incident_latency_degradation`, 5 `attack_auth_brute_force`).
3. **`ml/data/test_sessions.csv` (Évaluation finale hors échantillon)** :
   - **48 sessions indépendantes** (`576 fenêtres`) : 30 sessions normales (6 par profil, dont 3 comportant une micro-pointe isolée d'une seule fenêtre) + 18 sessions d'incident (6 par scénario d'incident, avec 3 fenêtres initiales normales pré-incident suivies de 9 fenêtres d'incident actif).
4. **Vérifications automatisées anti-fuite (`leakage_checks`)** :
   - `disjoint_session_ids = true` (`TRAIN-S*`, `VAL-*`, `TEST-*` strictement disjoints).
   - `train_contains_only_normal = true` (`0` anomalie dans le jeu d'entraînement).
   - `hidden_cheat_columns_present = false`.

---

## 4. Comparaison Quantitative des Modèles (Jeu de Test Indépendant)

Les trois modèles ont été entraînés sur les mêmes 900 fenêtres normales de `train_normal_sessions.csv`, calibrés sur `val_sessions.csv`, puis évalués sur les 576 fenêtres (48 sessions) de `test_sessions.csv` :

| Modèle (`scikit-learn`) | Seuil Calibré | Précision (Fenêtre) | Rappel (Fenêtre) | Score F1 (Fenêtre) | ROC-AUC (Fenêtre) | FPR Fenêtres Normales | FPR Sessions (Sans Confirm. 1 fen.) | **FPR Sessions (Confirmé 2 fen.)** | **Taux Détection Sessions Incident** | **Délai Moyen Détection Confirmée** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`IsolationForest` (Retenu)** | **`-0.1176`** | **`0.9818`** | **`1.0000`** | **`0.9908`** | **`0.9956`** | `0.0072` (3/414) | `0.1000` (3/30) | **`0.0000` (0/30)** | **`1.0000` (18/18)** | **`2,00 fen. (10,0 s)`** |
| `OneClassSVM` (`kernel="rbf"`) | `-3.1466` | `0.9818` | `1.0000` | `0.9908` | `1.0000` | `0.0072` (3/414) | `0.1000` (3/30) | `0.0000` (0/30) | `1.0000` (18/18) | `2,00 fen. (10,0 s)` |
| `EllipticEnvelope` (Mahalanobis) | `-643.7990` | `1.0000` | `0.9815` | `0.9907` | `0.9999` | `0.0000` (0/414) | `0.0000` (0/30) | `0.0000` (0/30) | `1.0000` (18/18) | `2,17 fen. (10,83 s)` |

### Justification du Choix d'`IsolationForest` + Confirmation sur 2 Fenêtres
1. **Supériorité sur `EllipticEnvelope` pour la détection précoce** : `EllipticEnvelope` suppose que le trafic normal suit une distribution gaussienne elliptique unique. Face aux 5 régimes normaux multimodaux, sa frontière très large manque certaines fenêtres de début de dégradation progressive (`window_recall = 0.9815` contre `1.0000` pour `IsolationForest`), retardant le délai moyen de détection confirmée à `10,83 s` contre **`10,00 s`** (`1,0 fenêtre / 5,0 s` pour le passage en `SUSPECT` et `2,0 fenêtres / 10,0 s` pour la confirmation `INCIDENT`).
2. **Avantage d'`IsolationForest` sur `OneClassSVM` en production AIOps** : À performances prédictives égales sur le jeu de test (`F1 = 0.9908`), `IsolationForest` produit un score borné et stable dans `[-0.5, +0.5]` (contre une distance non bornée pour `OneClassSVM`), supporte nativement les distributions tabulaires asymétriques (ratios bornés dans `[0, 1]` et latences à queue lourde), et se prête directement à l'explicabilité locale des variables (`top_contributing_features`).
3. **Preuve empirique de la règle de confirmation sur 2 fenêtres consécutives** :
   - Sur le jeu de test, 3 sessions normales contiennent volontairement une micro-pointe transitoire d'une seule fenêtre de 5 s (bruit d'exploitation réaliste).
   - **Sans confirmation** (déclenchement dès la 1re fenêtre), le taux de fausses alertes par session normale serait de **10,0 % (3/30)**.
   - **Avec la règle `consecutive_windows_required = 2`**, ces 3 micro-pointes placent brièvement l'automate en état `SUSPECT` pendant 5 s puis reviennent immédiatement à `NORMAL` : le taux de fausses alertes d'incident (`normal_session_fpr`) tombe à **0,00 % (0/30)** tout en maintenant **100 % (18/18)** de détection sur les vrais incidents en **10,0 secondes**.

---

## 5. Résultats Détaillés par Profil sur le Jeu de Test (`48 sessions`)

| Profil de Session (`test_sessions.csv`) | Type | Sessions Testées | Incidents Confirmés Déclenchés | Résultat Attendu | Statut |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `normal_idle` (Repos nocturne) | Normal | `6` | `0 / 6` (`0 %`) | Aucune alerte | `PASS` |
| `normal_nominal` (Charge nominale) | Normal | `6` | `0 / 6` (`0 %`) | Aucune alerte | `PASS` |
| `normal_legitimate_peak` (Pic horaire légitime + micro-pointe) | Normal | `6` | `0 / 6` (`0 %`) | Aucune alerte | `PASS` |
| `normal_benign_4xx` (Erreurs 4xx client + micro-pointe) | Normal | `6` | `0 / 6` (`0 %`) | Aucune alerte | `PASS` |
| `normal_scheduled_audit` (Audit comptable + micro-pointe) | Normal | `6` | `0 / 6` (`0 %`) | Aucune alerte | `PASS` |
| `attack_l7_verify_batch_flood` (Flood L7 `/verify-batch`) | Incident | `6` | `6 / 6` (`100 %`) | Détection confirmée | `PASS` |
| `incident_latency_degradation` (Dégradation latence/DB) | Incident | `6` | `6 / 6` (`100 %`) | Détection confirmée | `PASS` |
| `attack_auth_brute_force` (Force brute JWT) | Incident | `6` | `6 / 6` (`100 %`) | Détection confirmée | `PASS` |

---

## 6. Explicabilité Locale (`top_contributing_features`)

À chaque appel de `POST /evaluate`, `services/detector` retourne dans l'`AnomalyEvent` les 3 variables qui contribuent le plus à l'écart d'anomalie via `compute_top_contributing_features` (`ml/features.py`) :
$$\text{Contribution}(x_i) = w_i \cdot \text{direction}_i \cdot \frac{x_i - \mu_i}{\sigma_i}$$
où $(\mu_i, \sigma_i)$ sont la moyenne et l'écart-type appris sur `train_normal_sessions.csv`, $\text{direction}_i \in \{+1, -1\}$ indique le sens de dérive pathologique, et $w_i$ est pondéré par l'importance par permutation mesurée sur le modèle.

---

## 7. Limites Honnêtes de Généralisation et Garde-Fous

1. **Dérive conceptuelle (*Concept Drift*)** : Si le profil de trafic légitime de la plateforme change structurellement (ex. lancement d'une campagne promotionnelle doublant durablement le débit nominal au-delà de `60 rps` ou ajout de nouvelles routes lourdes), le modèle doit être ré-entraîné et son seuil recalibré sur de nouvelles sessions de référence.
2. **Attaques lentes sous le radar (*Low-and-Slow*)** : Une attaque logique distribuée sur des centaines d'adresses IP à très faible débit (`< 2 rps`) qui n'induit ni hausse de latence P95, ni baisse d'entropie IP, ni hausse du taux d'erreur ne sera pas détectée par ces 7 métriques volumétriques/RED et relève des contrôles métier d'authentification et d'idempotence (`services/auth` et `services/api`).
3. **Protection contre les boucles de remédiation** : Conformément à `docs/architecture.md`, le score ML ne déclenche jamais d'action destructive directe : il alimente l'automate `services/remediator` qui applique une confirmation sur 2 fenêtres, un `cooldown` de 15 s, un plafond strict `MAX_ATTEMPTS = 3`, et une vérification par **sonde transactionnelle réelle** avant de clore l'incident.
