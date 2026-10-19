# ADR-001 : Architecture Microservices en Python + React/Tailwind et Double Mode d'Exécution (Conteneurisé & Local)

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le sujet officiel impose une architecture en microservices comprenant au minimum une base de données, une API métier de paiement, un service d'authentification distinct, un moteur de remédiation et un frontal React + Tailwind CSS. Sur le PC Hôte `HDV0-INF-P08`, Python 3.13.14 (avec `Flask`, `scikit-learn`, `pandas`, `numpy`, `cryptography`, `requests`) et Node.js v22 sont disponibles immédiatement, tandis que le démon Docker Desktop est actuellement arrêté et l'espace disque libre est de 41,46 Go.
- **Décision** :
  1. **Stack Backend** : Implémenter les microservices backend (`auth`, `api`, `waf_gateway`, `detector`, `remediator`, `executor`, `rag`) en Python avec une architecture modulaire compatible à la fois avec FastAPI/ASGI (dans les conteneurs Docker `python:3.12-slim`) et exécutable nativement via la bibliothèque standard HTTP / Flask sous Python 3.13 sur l'hôte, sans nécessiter d'installation globale non autorisée.
  2. **Stockage Persistant** : Utiliser PostgreSQL 16 (`postgres:16-alpine`) dans Docker Compose avec bascule transparente vers un moteur SQL transactionnel persistant sur disque (SQLite en mode `WAL` + verrouillage atomique `IMMEDIATE`) pour les essais locaux hors démon Docker.
  3. **Représentation Monétaire** : Stocker et manipuler tous les montants en **centimes entiers (`int`, ex. `15000` pour `150,00 €`)** et valider les entrées décimales via `decimal.Decimal` afin d'éliminer toute erreur d'arrondi IEEE 754.
  4. **Idempotence** : Exiger l'en-tête `Idempotency-Key` sur `POST /api/v1/transactions` avec contrainte d'unicité en base.
- **Conséquences** :
  - Garantit une empreinte disque et mémoire minimale sur `HDV0-INF-P08`.
  - Permet d'exécuter et de prouver 100 % des tests unitaires, d'intégration et de bout en bout localement même lorsque Docker Desktop est arrêté, tout en fournissant un `docker-compose.yml` complet et validé pour le déploiement conteneurisé.
