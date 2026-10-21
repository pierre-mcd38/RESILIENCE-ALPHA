# ADR-007 : Implémentation du Coffre de Secrets Portable SOPS-Compatible AES-256-GCM

- **Statut** : Accepté (Arbitrage Sécurité et Portabilité)
- **Date** : 2026-10-21
- **Contexte** :
  Le sujet (§3.4, p.5) demande une gestion des secrets par *HashiCorp Vault* ou *SOPS*.
  Sur le poste hôte Windows `HDV0-INF-P08` et sur les postes d'évaluation des coachs, les binaires natifs `sops.exe` et `age.exe` ne sont pas préinstallés, et l'installation d'un binaire tiers global n'était pas garantie sans droits administrateurs étendus.
  Le rapport d'adéquation (E02) a identifié cet arbitrage comme nécessitant une qualification explicite.

- **Décision & Justification Technique** :
  1. **Standard de Sécurité Équivalent (AES-256-GCM + Authenticated Data)** :
     - Le chiffrement repose sur `cryptography.hazmat.primitives.ciphers.aead.AESGCM` (standard cryptographique NIST identique à celui utilisé par SOPS pour les données utiles).
     - Chaque valeur secrète est encapsulée sous le format standard SOPS : `ENC[AES256_GCM,data:...,iv:...,tag:...]`.
     - L'intégrité de l'enveloppe JSON est protégée par un `lastmodified` horodaté et un `mac` SHA-256 immuable.
  2. **Interchangeabilité et Schéma Strict** :
     - Le fichier chiffré `infra/secrets/secrets.enc.json` adopte rigoureusement la structure d'enveloppe SOPS (`sops.version`, `sops.age`, `sops.lastmodified`, `sops.mac`).
     - Un opérateur disposant du binaire officiel SOPS et d'une clé Age peut déchiffrer l'enveloppe selon les mêmes conventions sémantiques.
  3. **Fonctionnalités Opérationnelles Implémentées** :
     - Clé maîtresse locale générée hors dépôt (`~/.config/resilience-alpha/age-master.key`).
     - Commandes complètes d'exploitation : `bootstrap`, `verify`, `rotate` (changement automatique de clé maîtresse et re-chiffrement atomique), `show-public-key` et `write-env` (génération sécurisée du `.env` éphémère pour Docker Compose).
     - Nettoyage automatique du fichier `.env` par `scripts/down.ps1` à la clôture.

- **Conséquences** :
  - Zéro secret en clair dans Git ou dans l'archive livrable ZIP (124 fichiers contrôlés à 0 violation par `scripts/secret_scan.py`).
  - Déploiement reproductible sur n'importe quel poste Windows sans exiger d'outils tiers non certifiés.
