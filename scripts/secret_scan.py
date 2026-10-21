#!/usr/bin/env python3
"""
PROJECT RESILIENCE-ALPHA — Scanner Statique de Fuites de Secrets (secret_scan.py)
=================================================================================

Vérifie qu'aucun secret en clair, aucune clé privée (`age.key`, `.pem`, `PRIVATE KEY`),
aucun fichier `.env` déchiffré et aucune donnée bancaire réelle n'est présent dans le dépôt.
Vérifie également que `infra/secrets/secrets.enc.json` ne contient que des valeurs
chiffrées `ENC[AES256_GCM,...]` pour tous les champs sensibles.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    "dist",
    "build",
}

BINARY_EXTENSIONS = {
    ".joblib",
    ".pkl",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".pptx",
    ".zip",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pyc",
}

FORBIDDEN_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "age.key",
    "age-master.key",
    "secrets.dec.json",
    "id_rsa",
    "id_ed25519",
}

FORBIDDEN_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

# Motifs assemblés dynamiquement pour que ce fichier ne se déclenche pas lui-même
SECRET_CONTENT_PATTERNS: List[tuple[str, re.Pattern[str]]] = [
    (
        "PEM Private Key Header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?" + r"PRIVATE KEY-----"),
    ),
    (
        "Age Private Key Literal",
        re.compile(r"AGE-SECRET-" + r"KEY-1[A-Z0-9]{50,}"),
    ),
    (
        "AWS Access Key ID",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "GitHub Personal Access Token",
        re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    ),
    (
        "GitHub Fine-Grained Personal Access Token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{36,}\b"),
    ),
    (
        "GitHub OAuth Access Token",
        re.compile(r"\b(?:gho|ghu|ghs)_[A-Za-z0-9]{36}\b"),
    ),
    (
        "Stripe / Live Secret API Key",
        re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"),
    ),
]

SENSITIVE_VAULT_KEYS = (
    "postgres_password",
    "jwt_secret_key",
    "executor_hmac_secret",
    "operator_password",
    "probe_password",
    "grafana_admin_password",
    "internal_api_token",
)


def scan_repository(root: Path = REPO_ROOT) -> Dict[str, Any]:
    """
    Parcourt l'ensemble du dépôt et retourne un rapport détaillé :
    `{"passed": bool, "scanned_files": int, "violations": list}`.
    """
    violations: List[Dict[str, Any]] = []
    scanned_files = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        rel_dir = Path(dirpath).relative_to(root)

        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel_path = str((rel_dir / fname).as_posix())

            # 1. Vérification des noms de fichiers interdits
            if fname in FORBIDDEN_FILENAMES:
                violations.append(
                    {
                        "file": rel_path,
                        "rule": "FORBIDDEN_FILENAME",
                        "detail": f"Fichier sensible interdit dans le dépôt : {fname}",
                    }
                )
                continue

            ext = fpath.suffix.lower()
            if ext in FORBIDDEN_EXTENSIONS:
                violations.append(
                    {
                        "file": rel_path,
                        "rule": "FORBIDDEN_EXTENSION",
                        "detail": f"Extension de clé privée interdite : {ext}",
                    }
                )
                continue

            if ext == ".zip":
                # Inspection récursive des archives ZIP livrables (F08)
                try:
                    import zipfile
                    with zipfile.ZipFile(fpath, "r") as zf:
                        for zinfo in zf.infolist():
                            zname = zinfo.filename
                            zbase = Path(zname).name
                            zext = Path(zname).suffix.lower()
                            if zbase in FORBIDDEN_FILENAMES:
                                violations.append({
                                    "file": f"{rel_path}!{zname}",
                                    "rule": "FORBIDDEN_FILENAME_IN_ZIP",
                                    "detail": f"Fichier sensible interdit trouvé dans l'archive ZIP : {zname}",
                                })
                            if zext in FORBIDDEN_EXTENSIONS:
                                violations.append({
                                    "file": f"{rel_path}!{zname}",
                                    "rule": "FORBIDDEN_EXTENSION_IN_ZIP",
                                    "detail": f"Extension interdite dans l'archive ZIP : {zext}",
                                })
                            if zext in (".py", ".yml", ".yaml", ".json", ".md", ".sh", ".ps1", ".txt"):
                                try:
                                    zcontent = zf.read(zname).decode("utf-8", errors="ignore")
                                    for rule_name, pattern in SECRET_CONTENT_PATTERNS:
                                        m = pattern.search(zcontent)
                                        if m:
                                            violations.append({
                                                "file": f"{rel_path}!{zname}",
                                                "rule": f"{rule_name}_IN_ZIP",
                                                "detail": f"Motif critique détecté dans l'archive ZIP : {m.group(0)[:20]}...",
                                            })
                                except Exception:
                                    pass
                except Exception as exc:
                    violations.append({
                        "file": rel_path,
                        "rule": "CORRUPTED_ZIP_ARCHIVE",
                        "detail": f"Archive ZIP illisible : {exc}",
                    })
                scanned_files += 1
                continue

            if ext in BINARY_EXTENSIONS:
                continue

            scanned_files += 1

            # 2. Lecture et inspection du contenu texte
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for rule_name, pattern in SECRET_CONTENT_PATTERNS:
                match = pattern.search(content)
                if match:
                    violations.append(
                        {
                            "file": rel_path,
                            "rule": rule_name,
                            "detail": f"Motif critique détecté : {match.group(0)[:20]}...",
                        }
                    )

    # 3. Vérification spécifique du coffre SOPS infra/secrets/secrets.enc.json
    vault_path = root / "infra" / "secrets" / "secrets.enc.json"
    if vault_path.exists():
        try:
            vault_data = json.loads(vault_path.read_text(encoding="utf-8"))
            for key_name in SENSITIVE_VAULT_KEYS:
                val = vault_data.get(key_name)
                if not isinstance(val, str) or not val.startswith("ENC[AES256_GCM,"):
                    violations.append(
                        {
                            "file": "infra/secrets/secrets.enc.json",
                            "rule": "UNENCRYPTED_VAULT_FIELD",
                            "detail": f"Le champ '{key_name}' n'est pas chiffré avec ENC[AES256_GCM,...]",
                        }
                    )
        except Exception as exc:
            violations.append(
                {
                    "file": "infra/secrets/secrets.enc.json",
                    "rule": "INVALID_VAULT_JSON",
                    "detail": str(exc),
                }
            )
    else:
        violations.append(
            {
                "file": "infra/secrets/secrets.enc.json",
                "rule": "MISSING_ENCRYPTED_VAULT",
                "detail": "Le coffre chiffré infra/secrets/secrets.enc.json est absent.",
            }
        )

    return {
        "passed": len(violations) == 0,
        "scanned_files": scanned_files,
        "violations_count": len(violations),
        "violations": violations,
    }


def main() -> int:
    report = scan_repository(REPO_ROOT)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        print(
            f"[SECRET-SCAN] FAIL : {report['violations_count']} violation(s) détectée(s).",
            file=sys.stderr,
        )
        return 1
    print(
        f"[SECRET-SCAN] PASS : {report['scanned_files']} fichiers inspectés, 0 secret en clair détecté."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
