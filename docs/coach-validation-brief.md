# Fiche de Synthèse — Validation Jalon Lundi par le Coach (`docs/coach-validation-brief.md`)

> **Statut de validation** : `EN ATTENTE DE VALIDATION PAR LE COACH` (Ce document synthétise les choix d'architecture, le périmètre de sécurité et l'analyse de risques initiale pour revue par l'encadrant pédagogique).

---

## 1. Résumé Exécutif du Dispositif Retenu

| Pilier | Choix Technique Retenu | Justification & Adaptation au PC Hôte (`HDV0-INF-P08`) |
| :--- | :--- | :--- |
| **1. Développement** | Microservices Python (`auth`, `api`, `remediator`, `executor`) + Frontend `React + Tailwind CSS` + PostgreSQL 16 | Transactions fictives en centimes entiers (`int`), idempotence stricte (`Idempotency-Key`), invariant comptable vérifié à chaque opération. |
| **2. Infrastructure** | Docker Compose (5 réseaux isolés) + Playbooks Ansible + Prometheus / Grafana / Loki | Empreinte mémoire plafonnée à ~2,45 Go RAM pour l'ensemble des conteneurs (adapté aux 31,4 Go installés et 41,4 Go disque libre). Pas d'Elastic Stack. |
| **3. IA / Data** | Détection : `IsolationForest` (`scikit-learn`) sur 7 variables temps réel. Assistant : RAG Local `LangChain` + `Ollama` (`gemma4:e4b`) | Modèle ML entraîné sur sessions séparées sans fuite de données. RAG strictement consultatif avec citations des sources et hors du chemin critique. |
| **4. Cybersécurité** | Passerelle WAF à 2 niveaux (Signatures statiques + Blocage dynamique AIOps), corrélation SOC, secrets SOPS/Age, Exécuteur confiné HMAC | Aucun montage du socket Docker dans les services métier ou le RAG. Liste fermée d'actions dans `executor` avec audit chaîné SHA-256. |
| **5. Transformation** | Analyse EBIOS RM (5 ateliers), PCA/PRA opérationnel (RTO/RPO cibles vs mesurés), étude NIS2 & DORA | Distinction rigoureuse entre continuité locale démontrée (automatisation applicative) et résilience industrielle multi-sites. |

---

## 2. Scénario de Démonstration et Sécurité du Laboratoire

- **Topologie réseau** : Utilisation exclusive du Point d'Accès sans fil mobile Windows `RESILIENCE-G<n>` (`192.168.137.1/24` sur le PC Hôte).
- **Scénario offensif** : Saturation applicative contrôlée (L7 Resource Exhaustion) depuis le PC Attaquant (`192.168.137.x`) vers la route de vérification par lots `/api/v1/transactions/verify-batch`.
- **Garde-fous intégrés dans le code offensif (`scenarios/controlled_attack.py`)** :
  1. Liste blanche stricte d'IP cibles (`127.0.0.1`, `192.168.137.1`) — rejet immédiat par code de toute IP du campus (`10.60.0.0/16`) ou publique.
  2. Durée plafonnée (`max 45 s`), débit plafonné (`max 80 req/s`) et concurrence plafonnée (`max 12 threads`).
  3. Arrêt d'urgence immédiat (`scenarios/kill_switch.py` ou `Ctrl+C`).

---

## 3. Première Analyse des Risques Principaux (Synthèse EBIOS RM)

| ID | Événement Redouté | Bien Support Visé | Gravité | Vraisemblance | Mesure de Traitement Implémentée |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **ER-01** | Indisponibilité du traitement des paiements (> 60 s) entraînant perte de confiance et rupture SLA partenaires | API Métier (`api`), Passerelle (`waf-gateway`) | **4 (Critique)** | **4 (Très forte)** | Détection ML `IsolationForest` (< 10 s) + blocage dynamique WAF de l'IP source + recyclage des workers saturés + sonde métier automatique. |
| **ER-02** | Double débit ou corruption des soldes lors des réessais clients pendant une perturbation réseau | Base transactionnelle (`postgres`), API Métier | **4 (Critique)** | **3 (Forte)** | Clé d'idempotence obligatoire (`Idempotency-Key`), transactions ACID atomiques et montants en centimes entiers. |
| **ER-03** | Prise de contrôle de l'infrastructure via le moteur de remédiation ou par injection de prompt dans le RAG | Exécuteur (`executor`), Assistant RAG (`rag`) | **4 (Critique)** | **2 (Moyenne)** | Isolation réseau (`control_net`), signature `HMAC-SHA256`, liste fermée de 5 actions paramétrées sans shell, RAG dépourvu de tout outil d'action. |
| **ER-04** | Boucle infinie de redémarrage provoquant un déni de service auto-infligé (auto-DoS) | Orchestrateur (`remediator`) | **3 (Grave)** | **3 (Forte)** | Confirmation sur 2 fenêtres, Cooldown de 15 s, plafond de 3 tentatives (`MAX_ATTEMPTS = 3`) et bascule en état `FAILED` visible. |

---

## 4. Points à Confirmer avec le Coach et l'Équipe

- [ ] Numéro officiel du groupe (`G<n>`) attribué par le campus.
- [ ] Liste nominative des membres du groupe et répartition finale des prises de parole (5 minutes).
- [ ] Autorisation d'exécuter le tir contrôlé entre le PC Attaquant et le PC Hôte sur le Wi-Fi isolé `RESILIENCE-G<n>` (`192.168.137.0/24`).
