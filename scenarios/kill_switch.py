"""
PROJECT RESILIENCE-ALPHA — Arrêt d'Urgence Immédiat (scenarios/kill_switch.py)

Permet d'interrompre instantanément tout scénario offensif en cours via un fichier
sentinelle ou un événement mémoire partagé.

Usage en ligne de commande :
  python scenarios/kill_switch.py engage   # Active l'arrêt d'urgence immédiat
  python scenarios/kill_switch.py release  # Désactive l'arrêt d'urgence après vérification
  python scenarios/kill_switch.py status   # Affiche l'état courant du kill-switch
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

KILL_SWITCH_FILE = Path(__file__).resolve().parents[1] / "data" / "KILL_SWITCH.trigger"
_MEMORY_KILL_FLAG = threading.Event()


def engage_kill_switch(reason: str = "Manual operator emergency stop") -> Dict[str, Any]:
    """Active immédiatement l'arrêt d'urgence (en mémoire et sur disque)."""
    _MEMORY_KILL_FLAG.set()
    KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "engaged": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    }
    KILL_SWITCH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def release_kill_switch() -> Dict[str, Any]:
    """Réarme le laboratoire en supprimant le fichier sentinelle d'arrêt d'urgence."""
    _MEMORY_KILL_FLAG.clear()
    if KILL_SWITCH_FILE.exists():
        KILL_SWITCH_FILE.unlink()
    return {
        "engaged": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def is_kill_switch_engaged() -> bool:
    """Vérifie avant chaque requête si l'arrêt d'urgence est enclenché."""
    if _MEMORY_KILL_FLAG.is_set():
        return True
    if os.environ.get("RESILIENCE_KILL_SWITCH", "0") == "1":
        return True
    return KILL_SWITCH_FILE.exists()


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if cmd == "engage":
        print(json.dumps(engage_kill_switch("CLI emergency stop"), indent=2))
    elif cmd == "release":
        print(json.dumps(release_kill_switch(), indent=2))
    else:
        print(json.dumps({"engaged": is_kill_switch_engaged(), "file": str(KILL_SWITCH_FILE)}, indent=2))
