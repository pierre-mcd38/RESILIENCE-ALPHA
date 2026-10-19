# ADR-003 : Architecture de Remédiation Autonome et Confinement de l'Exécuteur

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le moteur de remédiation doit rétablir le service sans intervention humaine, mais le sujet avertit explicitement : *« Portez une attention particulière au moteur de remédiation, qui peut disposer de droits élevés sur les conteneurs. Une plateforme conçue pour se défendre ne doit pas introduire, par facilité, une interface d'administration accessible à n'importe quel composant. »*
- **Décision** :
  1. **Séparation Décision / Exécution** :
     - `services/remediator` héberge l'automate d'incident (`NORMAL → SUSPECT → INCIDENT → REMEDIATING → VERIFYING → RECOVERED / FAILED`), la déduplication, le cooldown (30 s), le plafond de tentatives (`MAX_ATTEMPTS = 3`) et la sonde métier post-action. Il ne possède **aucun privilège sur l'infrastructure**.
     - `services/executor` est le seul composant autorisé à appliquer des actions techniques. Il est isolé sur le réseau interne `control_net`.
  2. **Liste Fermée d'Actions (`ALLOWLIST`)** :
     - `block_ip_waf` : ajoute temporairement (TTL borné, ex. 300 s) une IP suspecte dans la liste de blocage dynamique du WAF (après vérification que l'IP n'appartient pas aux passerelles critiques ni à la sonde métier).
     - `set_rate_limit_profile` : active le profil de limitation de débit strict (`strict_mitigation`) sur le WAF pour les routes coûteuses.
     - `recycle_api_workers` : recycle proprement le pool de workers saturés et purge la file d'attente des requêtes offensives en cours sur l'API métier.
     - `reset_connection_pool` : réinitialise les connexions bloquées vers la base de données.
  3. **Absence d'Exécution Shell Arbitraire & Authentification HMAC** :
     - Aucune requête vers `executor` ne peut contenir de commande shell ni de nom de conteneur arbitraire.
     - Chaque ordre de `remediator` vers `executor` est signé par `HMAC-SHA256` avec horodatage anti-rejeu (`±30 s`) et enregistré dans un journal d'audit chaîné (`audit_log.jsonl`).
- **Conséquences** :
  - Même en cas de compromission du frontend, de l'API métier ou du RAG, un attaquant ne peut ni contacter `executor` ni lui faire exécuter des commandes arbitraires.
  - Risque résiduel du contrôle de conteneurs documenté honnêtement dans l'analyse EBIOS RM.
