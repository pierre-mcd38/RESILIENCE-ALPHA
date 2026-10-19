# ADR-004 : Passerelle WAF Dynamique, Observabilité Légère et Fonction SOC Corrélée

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le sujet requiert un reverse proxy avec WAF, Prometheus, Grafana, Loki (sans Elastic Stack pour préserver la RAM du PC Hôte) et une fonction SOC intégrée. De plus, il faut expliquer pourquoi le trafic du scénario d'attaque principal franchit les règles statiques initiales du WAF et comment la politique dynamique bloque l'attaque après détection ML.
- **Décision** :
  1. **WAF à Deux Niveaux (`infra/waf/` + `services/waf_gateway/`)** :
     - **Niveau 1 (Statique / Signatures L7)** : Bloque immédiatement les charges utiles malveillantes classiques (injections SQL `' OR 1=1`, XSS `<script>`, traversée de chemin `../`, scanners connus).
     - **Niveau 2 (Dynamique / Comportemental piloté par AIOps)** : Le scénario d'attaque principal envoie des requêtes HTTP **syntaxiquement valides** vers l'endpoint de calcul/vérification par lots (`/api/v1/transactions/verify-batch`). Chaque requête étant bien formée, elle passe légitimement le filtre de signatures statiques initial. Lorsque le modèle ML (`IsolationForest`) détecte la dégradation anormale (latence P95 + saturation workers + concentration IP), l'exécuteur met à jour à chaud la table de blocage dynamique (`dynamic_blocklist` avec TTL) et le profil de rate-limiting du WAF.
  2. **Corrélation SOC (`services/remediator/soc.py`)** :
     - Tous les composants émettent des journaux JSON structurés partageant `correlation_id`, `source_ip`, `service`, `event_type` et `severity`.
     - Le moteur SOC agrège et relie automatiquement : IP source dominante pendant la fenêtre d'anomalie → requêtes WAF → dégradation métriques API → score ML → décision de remédiation → action Exécuteur → preuve de transaction de la sonde métier.
- **Conséquences** :
  - Démonstration réaliste : le WAF n'est jamais désactivé artificiellement, et la complémentarité WAF statique + Détection ML comportementale + Blocage dynamique WAF est démontrée en direct.
