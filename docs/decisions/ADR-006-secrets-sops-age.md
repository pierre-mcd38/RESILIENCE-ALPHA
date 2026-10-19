# ADR-006 : Gestion des Secrets par SOPS + Age et Hygiène du Dépôt

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le sujet impose la gestion des secrets avec HashiCorp Vault ou SOPS, et interdit formellement tout secret en clair dans le dépôt Git, les journaux ou l'archive finale `Workshop2026-M2-G<n>-Code.zip`. Sur le PC Hôte `HDV0-INF-P08`, les binaires CLI `sops` et `age` ne sont pas installés globalement dans le PATH Windows, mais Python `cryptography` (v48.0.0) et `PyNaCl` (v1.6.2) sont installés.
- **Décision** :
  1. **Choix de SOPS plutôt que Vault Server** : SOPS (chiffrement de fichiers au repos) ne consomme aucune mémoire vive en exécution, contrairement à un conteneur Vault supplémentaire, ce qui préserve la RAM du PC Hôte.
  2. **Configuration et Outillage Portable** :
     - Fournir `.sops.yaml` définissant les règles de chiffrement des clés sensibles (`^(password|secret|jwt_secret|hmac_key|api_key|private_key)$`).
     - Fournir `scripts/secrets_manager.py` qui utilise `sops` + `age` s'ils sont présents dans le PATH, ou chiffre/déchiffre localement chaque valeur sensible en utilisant `cryptography.fernet` / `PyNaCl` X25519 (format d'enveloppe SOPS `ENC[AES256_GCM,...]`) avec une clé stockée **exclusivement hors du dépôt** (`$env:USERPROFILE\.config\resilience-alpha\age-master.key`).
  3. **Exclusion et Vérification Automatique** :
     - `.gitignore` et `.dockerignore` excluent `.env`, `*.decrypted.*`, `*.key`, `*secret*.json`.
     - `scripts/secret_scan.py` vérifie automatiquement l'ensemble des fichiers suivis et le contenu de l'archive `.zip` avant toute validation.
- **Conséquences** :
  - Zéro secret en clair dans le dépôt ni dans l'archive finale.
  - Amorçage reproductible sur n'importe quelle machine via `python scripts/secrets_manager.py bootstrap`.
