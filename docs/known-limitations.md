# Limites Connues et Transparence Technique (`docs/known-limitations.md`)

Conformément aux exigences d'honnêteté d'ingénierie du sujet officiel (Sections 2.3, 3.5, 9 et 10), ce document recense sans complaisance les limites techniques, opérationnelles et matérielles du démonstrateur **PROJECT RESILIENCE-ALPHA**.

---

## 1. Limites d'Infrastructure et de Continuité (SPOF Hôte Unique)

1. **Point de défaillance unique matériel (Single Point of Failure — SPOF)** :
   - L'ensemble des microservices, de la base transactionnelle et de la chaîne d'observabilité s'exécute sur un seul poste physique (`HDV0-INF-P08`).
   - Un recyclage de workers ou le redémarrage d'un conteneur **ne constitue pas un Plan de Continuité d'Activité (PCA) complet**. En cas de coupure électrique, d'écran bleu (BSOD), de panne matérielle de la carte mère ou de corruption du SSD `C:`, l'indisponibilité est totale jusqu'à restauration sur une autre machine.
2. **Contraintes de stockage et de mémoire vive sur `HDV0-INF-P08`** :
   - Bien que le poste dispose de `31,42 Go` de RAM installée, environ `26,5 Go` sont occupés par l'environnement système hôte au moment de l'audit, et l'espace libre sur `C:` est de `41,46 Go` (légèrement inférieur aux `50 Go` recommandés par le sujet).
   - La rétention des métriques Prometheus et des journaux Loki est volontairement bornée pour éviter toute saturation disque.

---

## 2. Limites de la Détection ML (`IsolationForest`)

1. **Entraînement sur données synthétiques calibrées de laboratoire** :
   - En l'absence d'historique de production bancaire réel sur plusieurs mois, le modèle `IsolationForest` a été entraîné et évalué sur des sessions générées de manière reproductible (`ml/generate_dataset.py` : 75 sessions d'entraînement couvrant 5 régimes légitimes variés, et 88 sessions de validation/test indépendantes).
   - Bien que la séparation par sessions garantisse l'absence de fuite de données (*data leakage*) et atteigne un F1-score de `0,9908` sur le banc d'essai, ces performances **ne doivent pas être extrapolées à un trafic Internet ouvert** sans réentraînement sur des traces réelles.
2. **Sensibilité à la dérive conceptuelle (*Concept Drift*) et aux attaques lentes (*Low-and-Slow*)** :
   - Lors d'événements commerciaux exceptionnels inédits (ex. *Black Friday* multipliant le débit légitime par 10), un modèle non supervisé figé peut générer des faux positifs si le profil de charge s'écarte fortement des 5 régimes appris.
   - Inversement, un attaquant distribuant sa charge très lentement sous le seuil de saturation des workers pourrait dégrader marginalement les performances sans franchir le seuil `-0.1176` sur deux fenêtres consécutives.

---

## 3. Limites de la Remédiation Autonome et du Filtrage WAF

1. **Limites du blocage par adresse IP (`block_ip_waf`)** :
   - Dans un réseau de laboratoire (`192.168.137.0/24`), bloquer l'adresse IP du PC Attaquant (`192.168.137.45`) neutralise immédiatement la source sans dommage collatéral.
   - Dans un environnement industriel réel, si des milliers de clients légitimes partagent une même adresse IP publique derrière un opérateur télécom (CGNAT / proxy d'entreprise), un blocage par IP pénaliserait ces utilisateurs légitimes (d'où le choix d'un TTL court de `300 s` et la recommandation d'évoluer vers un filtrage par jeton JWT / empreinte TLS JA4 en production).
2. **Incapacité d'un WAF applicatif face à une attaque DDoS volumétrique L3/L4** :
   - Si une attaque sature la bande passante physique de la carte Wi-Fi du point d'accès `RESILIENCE-G<n>` en amont du PC Hôte, le WAF local ne peut pas restaurer la disponibilité réseau : une protection en amont (scrubbing center opérateur / Anycast CDN) est indispensable.
3. **Distinction Disponibilité vs Compromission / Fuite de Données** :
   - La chaîne de remédiation implémentée traite un incident de **disponibilité / saturation applicative**.
   - Si un incident impliquait une exfiltration de données ou une compromission de clé privée, recycler un worker ou bloquer une IP ne résoudrait pas l'incident : il faudrait isoler le système (quarantaine), révoquer les clés cryptographiques et mener une investigation forensique.

---

## 4. Vérifications Restant Dépendantes d'Actions Opérateur (`BLOCKED`)

Conformément à la règle de transparence (Section 2.3), les éléments suivants sont prêts et outillés mais marqués `BLOCKED` tant que l'action physique correspondante n'est pas réalisée par l'équipe :
1. **Démarrage du démon Docker Desktop** sur `HDV0-INF-P08` pour exécuter `docker compose up -d` en conteneurs Linux (tous les tests s'exécutent en attendant `PASS` sur les processus Python locaux).
2. **Tir réseau depuis le second PC physique (PC Attaquant)** sur le Wi-Fi `RESILIENCE-G<n>` (`192.168.137.1`) et enregistrement vidéo continu du fichier `Workshop2026-M2-G<n>-VidChrono.mp4`.
3. **Démarrage du serveur local `ollama serve`** pour activer la synthèse générative en plus de la recherche documentaire citée.
4. **Renseignement administratif** du numéro de groupe définitif (`G<n>`) et des noms des membres de l'équipe.
