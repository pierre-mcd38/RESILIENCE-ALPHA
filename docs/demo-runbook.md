# Runbook de Démonstration et Conducteur Clip Chrono (`docs/demo-runbook.md`)

Ce document fournit le mode opératoire exact pour :
1. Le déploiement et la vérification pré-démonstration entre le **PC Hôte (`HDV0-INF-P08`)** et le **PC Attaquant**.
2. Le conducteur **seconde par seconde** du **Clip Chrono (`<= 60 secondes`, sans coupe)**.
3. Le déroulé de la soutenance locale (5 minutes pitch + démonstration live, 5 minutes Q&A) et de la finale nationale (1 min pitch + 1 min Clip Chrono + 3 min démo live).

---

## 1. Préparation Pré-Démo (Checklist Opérateur)

### 1.1 Sur le PC Hôte (`HDV0-INF-P08`)
1. **Activer le Point d'Accès Sans Fil Mobile Windows** :
   - Paramètres Windows $\to$ Réseau et Internet $\to$ Point d'accès sans fil mobile.
   - Nom du réseau (SSID) : `RESILIENCE-G<n>` (remplacer `<n>` par le numéro du groupe).
   - Vérifier que l'interface locale du point d'accès porte l'adresse `192.168.137.1`.
2. **Démarrer Docker Desktop** (ou lancer la pile locale des services) :
   ```powershell
   # Vérifier l'environnement
   powershell -ExecutionPolicy Bypass -File .\scripts\check-env.ps1

   # Déployer la plateforme sur l'interface du groupe
   $env:HOST_BIND_IP = "192.168.137.1"
   powershell -ExecutionPolicy Bypass -File .\scripts\up.ps1
   ```
3. **Ouvrir les vues nécessaires à l'écran du PC Hôte (Disposition Split-Screen 2x2)** :
   - **Haut-Gauche (55 % largeur)** : Console React + Tailwind (`http://192.168.137.1:3000`) montrant l'état `NORMAL`, le portail de paiement et la chronologie SOC.
   - **Bas-Gauche** : Tableau technique Grafana (`http://127.0.0.1:3001`) sur le dashboard `RESILIENCE-ALPHA` (latence P95, score ML, blocages WAF).
   - **Droite** : Terminal PowerShell affichant les journaux corrélés du moteur de remédiation et de l'exécuteur (`audit_entry_hash`).

### 1.2 Sur le PC Attaquant (Second Poste Distinct)
1. Se connecter uniquement au Wi-Fi `RESILIENCE-G<n>` (vérifier l'adresse IP attribuée, ex. `192.168.137.45`).
2. Vérifier la connectivité vers la passerelle WAF uniquement :
   ```powershell
   curl.exe -s http://192.168.137.1:8080/health
   ```
3. Préparer la commande de tir contrôlé borné (sans la lancer avant le top départ) :
   ```powershell
   python scenarios/controlled_attack.py --target http://192.168.137.1:8080 --duration 25 --rate 30 --concurrency 6 --source-ip 192.168.137.45 --confirm-authorized-lab
   ```
4. Garder un second terminal prêt sur l'arrêt d'urgence :
   ```powershell
   python scenarios/kill_switch.py engage
   ```

---

## 2. Conducteur Seconde par Seconde — Clip Chrono (`<= 60 s`, Sans Coupe)

> **Règle d'intégrité** : Le fichier `Workshop2026-M2-G<n>-VidChrono.mp4` doit être issu d'une **captation réelle continue sans coupe** (via OBS Studio ou Windows Game Bar `Win+Alt+R` en 1080p 30fps). Aucune vidéo truquée ou montée par coupures ne doit être produite.

| Chronomètre | Phase | Action à l'Écran | Preuve Visuelle Attendue | Sous-titre Incrusté Recommandé |
| :---: | :--- | :--- | :--- | :--- |
| **`00s – 08s`** | **T0 — État Nominal & Transaction Initiale** | Sur le Dashboard React (`NORMAL`), l'opérateur clique sur **Exécuter Transaction (`25,00 EUR`)** avec clé `Idempotency-Key`. | Réponse `HTTP 201 COMMITTED`, solde mis à jour en centimes, invariant comptable `OK`, latence `~15 ms`. | `[T0] Service Nominal — Transaction métier #1 validée et persistée (25,00 EUR)` |
| **`08s – 18s`** | **T1 & T2 — Attaque Contrôlée & Dégradation** | Depuis le **PC Attaquant** (encart ou terminal SSH/2e écran visible), lancement de `controlled_attack.py` sur `/api/v1/transactions/verify-batch`. | Les requêtes JSON valides passent les signatures statiques initiales du WAF. La latence P95 grimpe (`> 500 ms`) et la saturation des workers atteint `> 90 %`. | `[T1-T2] Flood L7 depuis PC Attaquant (192.168.137.45) — Saturation des workers API` |
| **`18s – 28s`** | **T3 — Détection ML (`IsolationForest`)** | Le service `detector` évalue les 7 variables temps réel. Le score ML passe sous le seuil calibré (`-0.1176`) sur 2 fenêtres consécutives. | Le badge d'état passe à `SUSPECT` puis `INCIDENT` (rouge clignotant). L'IP `192.168.137.45` est corrélée automatiquement par le SOC. | `[T3] Détection ML IsolationForest (Score -0.22 < -0.1176) — IP 192.168.137.45 corrélée` |
| **`28s – 38s`** | **T4 — Remédiation Autonome Confinée** | **Aucune main sur le clavier.** `remediator` envoie les 3 ordres signés `HMAC-SHA256` à `executor` : `block_ip_waf`, `set_rate_limit_profile(strict_mitigation)`, `recycle_api_workers`. | La chronologie SOC affiche les 3 actions `HTTP 200` avec leur empreinte d'audit SHA-256. Sur le PC Attaquant, les requêtes reçoivent désormais `HTTP 403 Forbidden`. | `[T4] Zero-Touch Recovery : Blocage dynamique WAF (HTTP 403) + Recyclage Workers API` |
| **`38s – 50s`** | **T5 — Sonde Métier & Nouvelle Transaction Réussie** | L'automate passe en `VERIFYING`, exécute automatiquement la sonde transactionnelle (`1,00 EUR` + test anti-doublon idempotent), puis bascule en `RECOVERED`. L'opérateur exécute une nouvelle transaction (`75,00 EUR`). | Tandis que l'attaque continue d'être bloquée par le WAF, la nouvelle transaction réussit (`HTTP 201 COMMITTED`, latence `< 25 ms`). MTTD et MTTR s'affichent. | `[T5] Service Rétabli (RECOVERED) — Nouvelle transaction métier réussie sous attaque filtrée` |
| **`50s – 58s`** | **Clôture & Preuve d'Intégrité** | Vue finale sur le bandeau de preuve : `INVARIANT COMPTABLE OK`, `Audit SHA-256 Valide`, `MTTD + MTTR < 15s`. | Fin de l'enregistrement continu à `< 60 s`. | `Chaîne complète validée sans intervention humaine — Invariant comptable 100 % intègre` |

---

## 3. Répartition du Temps de Passage (Soutenance 5 Minutes)

- **`0:00 – 1:00` (Pitch Stratégique & Architecture)** : Contexte métier (coût d'arrêt des paiements), architecture 5 réseaux isolés, séparation `remediator` / `executor` signé HMAC sans socket Docker exposé.
- **`1:00 – 3:30` (Démonstration Live en Direct)** : Exécution de la séquence `T0 → T1/T2 → T3 → T4 → T5` + interrogation rapide de l'assistant RAG local avec citations.
- **`3:30 – 5:00` (Gouvernance EBIOS RM, PCA/PRA, NIS2/DORA & Limites Honnêtes)** : Synthèse des risques résiduels (SPOF hôte unique `HDV0-INF-P08`), distinction RTO/RPO cibles vs MTTR mesuré, et feuille de route d'industrialisation à 30/90/180 jours.
