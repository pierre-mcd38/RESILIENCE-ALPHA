"""
PROJECT RESILIENCE-ALPHA — Validation Formelle de l'Assistant RAG Local (Ollama + LangChain)
Génère la preuve d'adéquation au sujet (Attendu E05) :
- Identification du modèle gemma4:e4b (8.0B paramètres <= 8B requis).
- Réponses génératives réelles en mode OLLAMA_ACTIVE avec citations [Source: ...].
- Refus strict anti-hallucination sur question hors périmètre (seuil 0.040).
- Repli transparent en mode OFFLINE_RETRIEVAL_ONLY.
- Enregistrement de la preuve dans data/live_ollama_validation.json.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import requests

from services.rag.app import LocalRAGAssistant, LangChainOllamaAdapter

sys.stdout.reconfigure(encoding="utf-8")


def run_ollama_validation() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    evidence_path = repo_root / "data" / "live_ollama_validation.json"

    print("=== PROJECT RESILIENCE-ALPHA : VALIDATION FORMELLE RAG LOCAL ===")

    # 1. Inspection du modèle chargé dans Ollama
    ollama_url = "http://127.0.0.1:11434"
    model_metadata = {}
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=3.0)
        if r.status_code == 200:
            models_info = r.json().get("models", [])
            for m in models_info:
                if "gemma4" in m.get("name", ""):
                    model_metadata = {
                        "name": m.get("name"),
                        "parameter_size": m.get("details", {}).get("parameter_size"),
                        "quantization": m.get("details", {}).get("quantization_level"),
                        "format": m.get("details", {}).get("format"),
                        "size_bytes": m.get("size"),
                        "digest": m.get("digest")[:16] + "...",
                    }
                    break
    except Exception as e:
        print(f"[!] Erreur connexion Ollama : {e}")

    print(f"[*] Modèle détecté : {model_metadata}")

    # 2. Vérification de LangChain
    adapter = LangChainOllamaAdapter(base_url=ollama_url, model_name="gemma4:e4b")
    langchain_active = adapter.langchain_installed
    print(f"[*] LangChain installé et actif : {langchain_active}")

    # 3. Initialisation de l'assistant RAG
    rag = LocalRAGAssistant(
        root_dir=repo_root,
        similarity_threshold=0.040,
        ollama_base_url=ollama_url,
        ollama_model="gemma4:e4b",
    )

    # 4. Questions de test
    test_queries = [
        {
            "id": "Q1_INCIDENT_REMEDIATION",
            "query": "Quelle est la procédure de remédiation en cas d incident ?",
            "expected_refusal": False,
        },
        {
            "id": "Q2_IDEMPOTENCY_LEDGER",
            "query": "Comment l API garantit-elle la non double dépense et l idempotence ?",
            "expected_refusal": False,
        },
        {
            "id": "Q3_OUT_OF_SCOPE",
            "query": "Donne-moi la recette de la tarte aux pommes de grand-mère.",
            "expected_refusal": True,
        },
    ]

    results = []
    for tq in test_queries:
        print(f"\n[*] Exécution du test {tq['id']} : {tq['query']}")
        start_t = time.perf_counter()
        resp = rag.answer_question(tq["query"])
        elapsed = round(time.perf_counter() - start_t, 2)

        verdict = "PASS" if resp["refused"] == tq["expected_refusal"] else "FAIL"
        print(f"    - Statut LLM : {resp.get('llm_status')}")
        print(f"    - Refusé : {resp.get('refused')} (Raison: {resp.get('refusal_reason')})")
        print(f"    - Citations : {len(resp.get('citations', []))}")
        print(f"    - Durée : {elapsed}s | Verdict : {verdict}")

        results.append({
            "test_id": tq["id"],
            "query": tq["query"],
            "elapsed_seconds": elapsed,
            "refused": resp["refused"],
            "refusal_reason": resp.get("refusal_reason"),
            "llm_status": resp.get("llm_status"),
            "model": resp.get("model"),
            "answer_preview": resp.get("answer", "")[:250] + ("..." if len(resp.get("answer", "")) > 250 else ""),
            "citations": resp.get("citations", []),
            "verdict": verdict,
        })

    # 5. Test du mode de secours dégradé hors-ligne
    print("\n[*] Test du repli hors-ligne (OFFLINE_RETRIEVAL_ONLY)...")
    offline_rag = LocalRAGAssistant(
        root_dir=repo_root,
        similarity_threshold=0.040,
        ollama_base_url="http://127.0.0.1:59999",  # Port invalide pour forcer le mode secours
        ollama_model="gemma4:e4b",
    )
    offline_resp = offline_rag.answer_question("Quelle est la procédure de remédiation ?")
    offline_ok = offline_resp["llm_status"] == "OFFLINE_RETRIEVAL_ONLY" and len(offline_resp["citations"]) > 0
    print(f"    - Statut dégradé : {offline_resp['llm_status']} (Repli réussi : {offline_ok})")

    evidence = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ollama_server": ollama_url,
        "model_metadata": model_metadata,
        "parameter_size_compliant_le_8b": model_metadata.get("parameter_size") == "8.0B",
        "langchain_prompt_active": langchain_active,
        "similarity_threshold": 0.040,
        "queries_tested": results,
        "graceful_fallback_verified": offline_ok,
        "global_status": "PASS" if all(r["verdict"] == "PASS" for r in results) and offline_ok else "FAIL",
    }

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Preuve formelle enregistrée dans {evidence_path}")
    print(f"[+] Statut Global : {evidence['global_status']}")
    return evidence


if __name__ == "__main__":
    run_ollama_validation()
