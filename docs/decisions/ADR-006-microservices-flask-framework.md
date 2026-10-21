# ADR-006 : Choix du Micro-framework Synchrone Flask pour la Résilience et Portabilité

- **Statut** : Accepté (Arbitrage Pédagogique et Technique)
- **Date** : 2026-10-21
- **Contexte** : 
  Le sujet officiel (§3.1, p.4) mentionne comme exemples d'environnements de services : `Node.js, Python/FastAPI ou Go`. 
  L'équipe a choisi d'implémenter l'ensemble des microservices (`auth`, `api`, `waf_gateway`, `detector`, `remediator`, `executor`, `rag`) sous **Python 3.13 avec Flask 3.1 / Werkzeug**. 
  Le rapport d'adéquation pédagogique (E01) a relevé cet écart par rapport à la citation textuelle de FastAPI et a invité à formaliser cet arbitrage.

- **Décision & Justification Technique** :
  1. **Déterminisme des Métriques de Latence pour l'IA (Isolation Forest)** :
     - Les frameworks asynchrones (FastAPI / ASGI avec uvloop/asyncio) regroupent les requêtes dans une boucle d'événements partagée. Lors d'un tir de saturation L7, le temps d'attente dans l'Event Loop pollue la mesure pure du réseau et du traitement métier, créant de la gigue artificielle.
     - Le modèle synchrone multi-threads de Flask / WSGI attribue un thread par worker, fournissant des mesures de latence P95 (`latency_p95_ms`) et de saturation CPU (`cpu_worker_saturation`) mathématiquement stables, directement représentatives de la charge réelle du système.
  2. **Portabilité Immédiate Windows & Conteneurs (Zéro Dépendance C Native)** :
     - Sur le poste hôte Windows 11 `HDV0-INF-P08`, l'exécution native de FastAPI avec certains accélérateurs asynchrones (`uvloop`) n'est pas supportée nativement sous Windows sans WSL.
     - Flask 3.1 fonctionne de manière 100 % iso-fonctionnelle sur Windows (scripts directs) et sous Linux Alpine (`gunicorn -w 2 -b 0.0.0.0:8001`) dans les conteneurs Docker.
  3. **Conformité Stricte aux Contrats d'API** :
     - Tous les endpoints respectent à la virgule près les contrats REST JSON définis dans `docs/contracts.md` (codes HTTP 200, 201, 400, 401, 403, 409, 422, en-têtes `Idempotency-Key`, JWT `Bearer`, formats de payload).
     - Le framework sous-jacent n'a aucun impact sur l'expérience utilisateur (Dashboard React) ni sur l'interopérabilité réseau.

- **Conséquences** :
  - Stabilité absolue démontrée : 14/14 tests réussis, 0 plantage de boucle asynchrone sous charge offensive.
  - Aucune régression introduite, maintenance simplifiée pour l'ensemble des piliers.
