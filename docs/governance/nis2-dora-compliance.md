# Analyse de Conformité Réglementaire : DORA & NIS2 (`docs/governance/nis2-dora-compliance.md`)

**Projet** : `PROJECT RESILIENCE-ALPHA` — Plateforme de Paiement Conteneurisée & Résilience Autonome  
**Textes de Référence** :
1. **Règlement DORA** : Règlement (UE) 2022/2554 du Parlement européen et du Conseil du 14 décembre 2022 sur la résilience opérationnelle numérique du secteur financier *(applicable depuis le 17 janvier 2025)*.
2. **Directive NIS2** : Directive (UE) 2022/2555 du Parlement européen et du Conseil du 14 décembre 2022 concernant des mesures destinées à assurer un niveau élevé commun de cybersécurité dans l'ensemble de l'Union.

> [!IMPORTANT]
> **Clause de Rigueur et de Sincérité Réglementaire** : Un prototype technique réalisé en 4 jours par un consortium d'ingénierie **ne peut en aucun cas être déclaré « conforme DORA » ou « conforme NIS2 »**. La conformité réglementaire européenne porte sur une entité juridique globale (gouvernance de l'organe de direction, contrats tiers, notifications aux autorités ACPR/BCE/ANSSI, audits indépendants). Ce document distingue donc strictement : **(A) ce que le prototype démontre techniquement par le code**, **(B) les bonnes pratiques d'ingénierie mises en œuvre**, et **(C) les obligations organisationnelles et juridiques hors périmètre d'un démonstrateur de 4 jours**.

---

## 1. Articulation Juridique entre DORA et NIS2 (*Lex Specialis*)

Pour un établissement de paiement ou un prestataire de services de paiement (PSP) :
- **DORA constitue la *lex specialis* (loi spéciale)** au sens de l'article 4 de la directive NIS2 et de l'article 1, paragraphe 2, du règlement DORA : les entités financières soumises à DORA appliquent directement les exigences de DORA en matière de gestion du risque TIC, de notification d'incidents majeurs et de tests de résilience.
- **NIS2 demeure toutefois directement pertinente** pour :
  1. Les fournisseurs d'infrastructures numériques, d'hébergement ou de services gérés (MSP) de la chaîne d'approvisionnement (qualifiés d'*Entités Essentielles* ou *Importantes* au titre des Annexes I et II de NIS2) ;
  2. L'alignement des exigences de cybersécurité technique (Art. 21 NIS2) et de gouvernance exécutive (Art. 20 NIS2) avec les standards européens transverses.

---

## 2. Analyse Détaillée selon le Règlement DORA — Règlement (UE) 2022/2554

### 2.1 Chapitre II — Gestion du Risque lié aux TIC (Articles 5 à 16)

| Article DORA | Exigence Réglementaire Officielle | Implémentation Technique dans `PROJECT RESILIENCE-ALPHA` |
| :--- | :--- | :--- |
| **Art. 5 & 6** — *Gouvernance, organisation et cadre de gestion du risque TIC* | L'organe de direction définit, approuve et supervise le cadre de gestion du risque TIC ; maintien d'une documentation à jour et d'une analyse de risques. | Formalisation de l'analyse EBIOS RM complète (`docs/governance/ebios-rm.md`), de l'architecture (`docs/architecture.md`) et de la note d'arbitrage COMEX (`docs/governance/executive-recommendations.md`). |
| **Art. 9** — *Protection et prévention* | Conception de systèmes TIC résilients, ségrégation des réseaux, politiques de contrôle d'accès strictes et protection des clés cryptographiques. | • **Segmentation en 5 réseaux Docker** (`edge_net`, `app_net`, `data_net`, `obs_net`, `control_net`) avec `internal: true` sur les zones de données et de contrôle.<br/>• **Moindre privilège** : aucun montage de `/var/run/docker.sock` ; `executor` restreint à une `ALLOWLIST` de 5 actions signées `HMAC-SHA256`.<br/>• **Cryptographie** : secrets chiffrés au repos via SOPS/Age (`.sops.yaml`, `scripts/secrets_manager.py`). |
| **Art. 10** — *Détection* | Mise en place de mécanismes permettant de détecter rapidement les activités anormales, y compris les problèmes de performance du réseau et les incidents liés aux TIC, avec seuils d'alerte multicouches. | • Collecte continue toutes les `2 s` des métriques RED (`prometheus`) et journaux structurés (`loki`).<br/>• Inférence ML non supervisée par `IsolationForest` (`services/detector`) sur 7 caractéristiques conjointes.<br/>• Confirmation anti-faux-positifs sur **2 fenêtres consécutives** avant passage à l'état `INCIDENT`. |
| **Art. 11** — *Réponse et rétablissement* | Politique de continuité des activités TIC et plans de réponse et de rétablissement assurant la poursuite des fonctions critiques et la maîtrise des pertes. | • Automate d'incident déterministe (`services/remediator`) avec garde-fous (`MAX_ATTEMPTS = 3`, `COOLDOWN_SECONDS = 15`, `BLOCK_TTL_SECONDS = 300`).<br/>• Exécution automatique bornée : blocage IP dynamique WAF, profil `strict_mitigation` et recyclage des workers API. |
| **Art. 12 & 13** — *Politiques de sauvegarde, restauration et vérification post-incident* | Vérification de l'intégrité des données lors du rétablissement et revue post-incident à partir des preuves collectées. | • **Preuve métier obligatoire (`RecoveryProof`)** : la reprise n'est actée (`RECOVERED`) qu'après une transaction réelle de `100` centimes persistée en base (`COMMITTED`), vérification du rejeu idempotent (`X-Idempotent-Replay: true`) et contrôle de l'invariant comptable `total_system_balance_cents`. |

### 2.2 Chapitre III — Gestion, Classification et Notification des Incidents liés aux TIC (Articles 17 à 23)

- **Art. 17 (Processus de gestion des incidents liés aux TIC)** : Le service `services/remediator` enregistre automatiquement chaque incident (`INC-YYYYMMDD-NNN`), ses horodatages exacts (`detected_at`, `remediated_at`, `recovered_at`), ses décisions (`RemediationDecision`) et l'empreinte chaînée d'audit (`audit_chain_hash`).
- **Art. 18 (Classification des incidents)** : Les métriques capturées dans `AnomalyEvent` et `RecoveryProof` fournissent directement les indicateurs exigés par les normes techniques de réglementation (RTS) de DORA :
  1. *Durée de l'incident et temps d'indisponibilité du service* (`total_incident_duration_seconds`, `mttd_seconds`, `mttr_seconds`) ;
  2. *Impact sur les transactions et l'intégrité des données* (`tx_success_ratio`, `accounting_invariant_verified`) ;
  3. *Origine et vecteur de l'attaque* (`dominant_source_ip`, `top_contributing_features`).
- **Art. 19 (Notification des incidents majeurs liés aux TIC)** : En production, ces journaux structurés JSON alimentent les trois étapes de déclaration auprès de l'autorité compétente (ACPR en France) :
  1. **Notification initiale** (dans les 4 heures suivant la classification de l'incident comme majeur, et au plus tard 24 heures après sa détection) ;
  2. **Rapport intermédiaire** (dans les 72 heures, mis à jour dès que le service est rétabli) ;
  3. **Rapport final** (dans un délai d'un mois après la résolution, incluant l'analyse des causes profondes).

### 2.3 Chapitre IV — Tests de Résilience Opérationnelle Numérique (Articles 24 à 27)

- **Art. 24 & 25 (Exigences générales et tests d'outils et de systèmes TIC)** : Le projet intègre une suite complète de tests automatisés (`tests/run_all_tests.py`) couvrant les tests unitaires, l'exactitude monétaire en centimes, l'idempotence, le refus d'injection sur `executor`, l'absence de secrets en clair (`scripts/secret_scan.py`) et un scénario d'attaque contrôlée en conditions réelles depuis un second poste (`scenarios/`).
- **Art. 26 & 27 (Tests fondés sur la menace — TLPT / *Threat-Led Penetration Testing*)** : Le scénario Red Team/Blue Team exécuté entre le PC Attaquant (`192.168.137.x`) et le PC Hôte (`192.168.137.1`) illustre à échelle réduite la philosophie d'un test en conditions réelles avec garde-fous stricts (liste blanche IP, plafonds de débit et de durée, arrêt d'urgence `scenarios/kill_switch.py`).

### 2.4 Chapitre V — Gestion du Risque lié aux Tiers Prestataires TIC (Articles 28 à 44)

- **Maîtrise des dépendances technologiques** :
  - L'assistant documentaire IA (`services/rag`) utilise un modèle exécuté **100 % localement** via Ollama (`gemma4:e4b`), évitant toute exfiltration de journaux SOC ou de schémas d'architecture vers une API LLM cloud publique tierce.
  - Par ailleurs, conformément au principe de précaution sur les systèmes d'IA tiers, `services/rag` est **purement consultatif** : la boucle critique de détection (`IsolationForest` déterministe avec graine fixée) et de remédiation (`remediator` $\rightarrow$ `executor`) ne dépend d'aucun LLM génératif.

---

## 3. Analyse Détaillée selon la Directive NIS2 — Directive (UE) 2022/2555

| Article NIS2 | Exigence de la Directive (UE) 2022/2555 | Traduction dans `PROJECT RESILIENCE-ALPHA` |
| :--- | :--- | :--- |
| **Art. 20** — *Gouvernance* | Les organes de direction approuvent les mesures de gestion des risques de cybersécurité, en supervisent la mise en œuvre et suivent des formations régulières. | Livrable dédié au COMEX (`docs/governance/executive-recommendations.md`) chiffrant les risques résiduels et la feuille de route à 30/90/180 jours. |
| **Art. 21 §2 a)** — *Analyse des risques et sécurité des SI* | Politiques relatives à l'analyse des risques et à la sécurité des systèmes d'information. | Analyse EBIOS RM complète (`docs/governance/ebios-rm.md`) couvrant les 5 ateliers ANSSI et les 4 risques résiduels explicites. |
| **Art. 21 §2 b)** — *Gestion des incidents* | Capacités de détection, d'analyse, de confinement et de réponse aux incidents. | Chaîne automatisée `detector` (:8003) $\rightarrow$ `remediator` (:8004) $\rightarrow$ `executor` (:8005) avec journal d'audit chaîné par hachage SHA-256. |
| **Art. 21 §2 c)** — *Continuité des activités et gestion des crises* | Gestion des sauvegardes, reprise après sinistre et gestion des crises. | Document PCA/PRA (`docs/governance/pca-pra.md`), sonde de preuve transactionnelle (`RecoveryProof`) et procédure d'escalade sur état `FAILED`. |
| **Art. 21 §2 d) & e)** — *Chaîne d'approvisionnement & Développement sécurisé* | Sécurité dans l'acquisition, le développement et la maintenance des systèmes TIC, y compris la gestion des vulnérabilités. | Infrastructure-as-Code validée (`docker-compose.yml`, playbooks Ansible `infra/ansible/`), schémas Pydantic stricts, tests de sécurité automatisés. |
| **Art. 21 §2 h)** — *Cryptographie et chiffrement* | Politiques et procédures relatives à l'utilisation de la cryptographie et, le cas échéant, du chiffrement. | Jeton JWT `HS256` à durée de vie bornée, signature `HMAC-SHA256` anti-rejeu (`<= 30 s`) sur `control_net`, chiffrement SOPS/Age des secrets au repos. |
| **Art. 21 §2 i) & j)** — *Contrôle d'accès et authentification* | Politiques de contrôle d'accès, gestion des actifs et authentification sécurisée. | RBAC strict dans `services/auth` (`merchant_operator`, `resilience_probe`, `auditor_readonly`) et isolation réseau empêchant tout accès direct à `postgres`. |
| **Art. 23** — *Obligations de notification* | Chronologie légale de notification au CSIRT / ANSSI :<br/>1. **Alerte précoce sous 24 h** ;<br/>2. **Notification d'incident sous 72 h** ;<br/>3. **Rapport final sous 1 mois**. | Export structuré immédiat des métriques d'incident (`INCIDENTS`, `RecoveryProof`) fournissant dès $T_0 + \text{quelques secondes}$ les éléments techniques requis pour l'alerte à 24 h et le rapport à 72 h. |

---

## 4. Tableau de Positionnement Tripartite (Transparence Prototype vs Conformité Entreprise)

Ce tableau synthétise avec exactitude le positionnement de **PROJECT RESILIENCE-ALPHA** afin d'éviter toute confusion entre démonstration technique et homologation juridique :

| Domaine Réglementaire (DORA / NIS2) | (A) Ce que le Prototype Démontre Techniquement (Code & Preuves Exécutables) | (B) Bonnes Pratiques d'Ingénierie Mises en Œuvre dans le Dépôt | (C) Obligations Organisationnelles & Juridiques HORS PÉRIMÈTRE d'un Prototype de 4 Jours |
| :--- | :--- | :--- | :--- |
| **1. Détection & Réponse aux Incidents** *(DORA Art. 10–11, NIS2 Art. 21 b)* | • Détection temps réel par `IsolationForest` sur 7 métriques (`AnomalyEvent`).<br/>• Confirmation sur 2 fenêtres.<br/>• Blocage IP dynamique WAF + recyclage workers via `ExecutorCommand` signé HMAC. | • Automate fini à 7 états avec garde-fous anti-boucle (`MAX_ATTEMPTS = 3`, `COOLDOWN = 15 s`, `BLOCK_TTL = 300 s`).<br/>• Séparation stricte entre décision (`remediator`) et exécution (`executor`). | • Équipe SOC humaine en 24/7/365 (3×8).<br/>• Contrats d'astreinte et d'intervention forensique (CSIRT externe).<br/>• Intégration avec les sondes réseau opérateur (BGP Flowspec). |
| **2. Continuité d'Activité & Preuve de Rétablissement** *(DORA Art. 11–12, NIS2 Art. 21 c)* | • Sonde métier post-incident exécutant un virement réel de `100` centimes (`POST /api/v1/transactions`).<br/>• Vérification d'idempotence (`X-Idempotent-Replay: true`) et de l'invariant comptable (`RecoveryProof`). | • Arithmétique monétaire 100 % en centimes entiers (`int`).<br/>• Transactions SQL ACID dans `postgres`.<br/>• Documentation honnête des scénarios non couverts par un redémarrage de conteneur (`pca-pra.md`). | • Hébergement actif/actif multi-datacenters distants (> 50 km).<br/>• Réplication synchrone inter-sites de la base de données.<br/>• Exercice annuel de bascule complète sur site de secours avec les équipes métiers. |
| **3. Confinement des Privilèges, Réseau & Cryptographie** *(DORA Art. 9, NIS2 Art. 21 h–i)* | • Rejet (`403 Forbidden`) de toute commande hors `ALLOWLIST` ou contenant des métacaractères shell.<br/>• Vérification de signature `HMAC-SHA256` et d'horodatage (`<= 30 s`).<br/>• `secret_scan.py` validé à 0 fuite. | • 5 réseaux Docker isolés (`data_net` et `control_net` en `internal: true`).<br/>• Absence totale de `/var/run/docker.sock` dans les conteneurs.<br/>• Enveloppe de chiffrement SOPS/Age (`.sops.yaml`). | • Module matériel de sécurité (HSM certifié FIPS 140-3 / eIDAS) pour la garde des clés maîtresses.<br/>• Authentification multifacteur matérielle (FIDO2/WebAuthn) des administrateurs.<br/>• PKI interne avec mTLS mutuel entre tous les microservices. |
| **4. Notification Réglementaire & Traçabilité** *(DORA Art. 17–19, NIS2 Art. 23)* | • Génération automatique des objets JSON horodatés (`INCIDENTS`, `RemediationDecision`, `RecoveryProof`) et du chaînage cryptographique `audit_chain_hash`. | • Conservation des indicateurs réglementaires clés : `mttd_seconds`, `mttr_seconds`, `suspect_ip`, `peak_ml_score`, `recovery_tx_id`. | • Déclaration juridique officielle sur les portails réglementaires (OneGate ACPR / Portail ANSSI) sous 4h/24h, 72h et 1 mois.<br/>• Archivage légal à valeur probante (coffre-fort numérique WORM certifié NF Z42-013). |
| **5. Tests de Résilience & Risque Tiers / IA** *(DORA Art. 24–28, NIS2 Art. 21 d)* | • Suite de tests automatisés (`run_all_tests.py`) + scénario d'attaque L7 borné avec coupe-circuit (`kill_switch.py`).<br/>• Assistant `rag` isolé en lecture seule avec LLM local (`gemma4:e4b`). | • Interdiction par code de cibler toute IP hors du point d'accès isolé (`192.168.137.1` / `127.0.0.1`).<br/>• Exclusion totale du LLM de la boucle de décision critique. | • Test d'intrusion avancé TLPT (cadre TIBER-EU) conduit tous les 3 ans par des testeurs externes accrédités.<br/>• Tenue du Registre d'Information complet des contrats tiers TIC et clauses contractuelles d'audit DORA Art. 30. |
