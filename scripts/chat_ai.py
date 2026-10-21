#!/usr/bin/env python3
"""
PROJECT RESILIENCE-ALPHA — Console Interactive de Dialogue en Temps Réel avec l'IA
(scripts/chat_ai.py)

Permet à l'opérateur de converser en direct avec le modèle local Ollama (gemma4:e4b)
informé en continu de la télémétrie du système (WAF, Détecteur ML, Automate, Soldes).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Configuration encodage console
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from services.rag.app import LocalRAGAssistant, fetch_live_soc_telemetry

# Couleurs ANSI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_BLUE = "\033[94m"
C_DIM = "\033[2m"


def print_banner(rag: LocalRAGAssistant) -> None:
    is_online, models = rag.llm_adapter.check_ollama_online()
    status_str = f"{C_GREEN}OLLAMA ACTIF ({rag.llm_adapter.model_name}){C_RESET}" if is_online else f"{C_YELLOW}MODE SECOURS HORS-LIGNE{C_RESET}"
    
    print("\n" + C_CYAN + "=" * 76 + C_RESET)
    print(f"{C_BOLD}{C_CYAN}  PROJECT RESILIENCE-ALPHA — IA Superviseur Opérationnel en Direct{C_RESET}")
    print(f"  Moteur : {status_str} | LangChain : {C_GREEN if rag.llm_adapter.langchain_installed else C_YELLOW}{'Actif' if rag.llm_adapter.langchain_installed else 'Inactif'}{C_RESET}")
    print(f"  Télémétrie : {C_GREEN}Connectée au SOC Gateway (http://127.0.0.1:8080){C_RESET}")
    print(C_CYAN + "=" * 76 + C_RESET)
    print(f"{C_DIM}Commandes utiles : /status (diagnostic rapide), /help (exemples), /exit (quitter){C_RESET}\n")


def display_quick_status() -> None:
    telemetry = fetch_live_soc_telemetry()
    print(f"\n{C_BOLD}{C_BLUE}--- [POINT DE SITUATION TEMPS RÉEL DU SYSTÈME] ---{C_RESET}")
    print(f"{C_CYAN}{telemetry}{C_RESET}\n")


def display_help() -> None:
    print(f"\n{C_BOLD}Exemples de questions que vous pouvez poser à l'IA en temps réel :{C_RESET}")
    print(f"  {C_GREEN}•{C_RESET} \"Quel est l'état actuel de la plateforme ?\"")
    print(f"  {C_GREEN}•{C_RESET} \"Y a-t-il une anomalie ou une attaque en cours ?\"")
    print(f"  {C_GREEN}•{C_RESET} \"Quelles adresses IP sont actuellement bloquées par le WAF ?\"")
    print(f"  {C_GREEN}•{C_RESET} \"Quelle est la procédure de remédiation autonome si une attaque survient ?\"")
    print(f"  {C_GREEN}•{C_RESET} \"Comment l'API garantit-elle la conservation exacte des soldes et l'idempotence ?\"")
    print(f"  {C_GREEN}•{C_RESET} \"Quels sont les rôles de Lenny, Youssef, Pierre et Rohail ?\"\n")


def main() -> None:
    rag = LocalRAGAssistant(
        root_dir=repo_root,
        similarity_threshold=0.040,
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="gemma4:e4b",
    )

    print_banner(rag)

    while True:
        try:
            prompt_input = input(f"{C_BOLD}{C_GREEN}Vous > {C_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_DIM}Session terminée. À bientôt !{C_RESET}")
            break

        if not prompt_input:
            continue

        cmd = prompt_input.lower()
        if cmd in ("/exit", "/quit", "exit", "quit", "q"):
            print(f"{C_DIM}Fermeture de la console IA.{C_RESET}")
            break
        elif cmd in ("/status", "/etat", "/statut"):
            display_quick_status()
            continue
        elif cmd in ("/help", "/aide", "?"):
            display_help()
            continue
        elif cmd in ("/clear", "clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            print_banner(rag)
            continue

        # Interrogation en direct
        print(f"{C_DIM}IA réfléchit et consulte la télémétrie...{C_RESET}", end="\r", flush=True)
        start_time = time.perf_counter()
        
        try:
            result = rag.answer_question(prompt_input)
            duration = round(time.perf_counter() - start_time, 2)
            
            # Nettoyage de la ligne "IA réfléchit..."
            print(" " * 60, end="\r")

            print(f"{C_BOLD}{C_MAGENTA}IA Superviseur ({result.get('model', 'gemma4:e4b')} • {duration}s) :{C_RESET}")
            print(f"{result.get('answer', '')}\n")

            citations = result.get("citations", [])
            if citations:
                print(f"{C_DIM}Citations certifiées : {', '.join(citations)}{C_RESET}\n")

        except Exception as e:
            print(f"\n{C_RED}[!] Erreur lors de l'interrogation : {e}{C_RESET}\n")


if __name__ == "__main__":
    main()
