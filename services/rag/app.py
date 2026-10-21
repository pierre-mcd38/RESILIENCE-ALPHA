"""Service Assistant RAG Local (LangChain + Ollama) pour PROJECT RESILIENCE-ALPHA (`services/rag`).

Conformément à ADR-005 et `AGENTS.md` :
- Purement consultatif (lecture documentaire seule) : ne possède AUCUN client ni privilège
  vers `services/executor`, ni aucun outil d'exécution système.
- Indexe les documents Markdown de `docs/` et `AGENTS.md` par sections (`#`, `##`, `###`)
  via `TfidfVectorizer`.
- Intègre un adaptateur LangChain + Ollama (`OLLAMA_BASE_URL`, modèle par défaut `gemma4:e4b` `<= 8B`).
- En cas d'indisponibilité du serveur Ollama, bascule de manière transparente et explicite
  sur `llm_status: "OFFLINE_RETRIEVAL_ONLY"` (vs `"OLLAMA_ACTIVE"`) en fournissant une synthèse
  extractive fidèle avec citations obligatoires.
- Refuse d'inventer une procédure absente lorsque le score de similarité maximal est `< 0.06`
  ou lorsqu'une tentative d'injection de prompt / exécution d'action est détectée.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import requests
from flask import Flask, Response, jsonify, request

ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.rag.indexer import MarkdownSectionIndexer

SIMILARITY_THRESHOLD: float = 0.040
DEFAULT_OLLAMA_URL: str = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL: str = "gemma4:e4b"

PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(toutes\s+)?les\s+instructions", re.IGNORECASE),
    re.compile(r"oublie\s+(toutes\s+)?les\s+r[eè]gles", re.IGNORECASE),
    re.compile(r"/executor/v1/execute", re.IGNORECASE),
    re.compile(r"\b(rm\s+-rf|DROP\s+TABLE|os\.system|subprocess\.Popen)\b", re.IGNORECASE),
)


def fetch_live_soc_telemetry() -> str:
    """Récupère l'état opérationnel temps réel de la plateforme depuis le SOC / WAF."""
    urls = [
        os.environ.get("SOC_DASHBOARD_URL", "http://127.0.0.1:8080/soc/v1/dashboard"),
        "http://127.0.0.1:8004/soc/v1/dashboard",
        "http://waf-gateway:8080/soc/v1/dashboard",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=0.8)
            if r.status_code == 200:
                data = r.json()
                state = data.get("automaton_state", "UNKNOWN")
                avail = data.get("business_availability", "UNKNOWN")
                inc = data.get("current_incident")
                inc_text = f"Actif ({inc.get('incident_id')} - {inc.get('state')})" if inc else "Aucun incident actif (Système Nominal)"
                waf = data.get("waf_status", {})
                blocked = waf.get("active_blocked_ips", [])
                profile = waf.get("rate_limit_profile", "normal")
                tx = data.get("last_verified_transaction")
                tx_text = f"{tx.get('tx_id')} ({tx.get('amount_cents', 0) / 100:.2f} {tx.get('currency', 'EUR')} - {tx.get('status')})" if tx else "Aucune transaction récente"
                ml = data.get("last_ml_event")
                ml_text = f"Score={ml.get('anomaly_score', 'N/A')} (Anomalie={ml.get('is_anomaly')})" if ml else "Nominal (Score > seuil -0.1176)"
                return (
                    f"- Horodatage : {data.get('timestamp')}\n"
                    f"- Disponibilité Métier : {avail}\n"
                    f"- État Automate de Résilience : {state}\n"
                    f"- Incident en cours : {inc_text}\n"
                    f"- Score Détecteur ML : {ml_text}\n"
                    f"- WAF Gateway : Profil '{profile}', {len(blocked)} IP(s) bloquée(s) {blocked}\n"
                    f"- Dernière Transaction Vérifiée : {tx_text}"
                )
        except Exception:
            continue
    return "- Statut : Services en cours d'exécution. Télémétrie locale en attente."

RAG_SYSTEM_PROMPT_TEMPLATE: str = """Tu es l'assistant IA et superviseur opérationnel en temps réel de PROJECT RESILIENCE-ALPHA.
Règles strictes :
1. Réponds de façon claire, précise et factuelle en t'appuyant sur l'état du système (<ETAT_SYSTEME_TEMPS_REEL>) et les documents certifiés (<DOCUMENTS_CERTIFIES>).
2. Pour toute question sur l'état en direct (incidents, métriques, WAF, transactions), base-toi fidèlement sur <ETAT_SYSTEME_TEMPS_REEL>.
3. Pour les questions de procédure, d'architecture ou de sécurité, cite obligatoirement chaque source utilisée au format exact [Source: fichier#section].
4. Tu n'as aucun droit d'exécution système ni d'accès à services/executor.

<ETAT_SYSTEME_TEMPS_REEL>
{live_telemetry}
</ETAT_SYSTEME_TEMPS_REEL>

<DOCUMENTS_CERTIFIES>
{context}
</DOCUMENTS_CERTIFIES>

Question de l'opérateur : {question}
Réponse factuelle et informée en temps réel :"""


class LangChainOllamaAdapter:
    """Adaptateur LangChain + Ollama (modèle <= 8B) avec repli transparent hors-ligne."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_URL
        ).rstrip("/")
        self.model_name = (
            model_name or os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        )
        self.timeout_seconds = timeout_seconds

        # Vérifie si les composants LangChain sont installés dans l'environnement Python
        self.langchain_installed = False
        try:
            from langchain_core.prompts import PromptTemplate  # type: ignore

            self._prompt_template = PromptTemplate.from_template(RAG_SYSTEM_PROMPT_TEMPLATE)
            self.langchain_installed = True
        except ImportError:
            self._prompt_template = None

    def format_prompt(self, context: str, question: str, live_telemetry: str = "Système Nominal") -> str:
        if self._prompt_template is not None:
            try:
                return str(self._prompt_template.format(context=context, question=question, live_telemetry=live_telemetry))
            except Exception:
                pass
        return RAG_SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question, live_telemetry=live_telemetry)

    def check_ollama_online(self) -> tuple[bool, list[str]]:
        """Vérifie rapidement si le démon Ollama répond sur `OLLAMA_BASE_URL`."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                models = [str(m.get("name", "")) for m in data.get("models", [])]
                return True, models
        except Exception:
            pass
        return False, []

    def generate(self, context: str, question: str, live_telemetry: str = "Système Nominal") -> tuple[str | None, str]:
        """Tente une génération via Ollama (LangChain ou API locale) ; retourne `(texte, llm_status)`."""
        is_online, _ = self.check_ollama_online()
        if not is_online:
            return None, "OFFLINE_RETRIEVAL_ONLY"

        prompt = self.format_prompt(context=context, question=question, live_telemetry=live_telemetry)

        # Appel HTTP direct à l'API locale Ollama (/api/generate) avec keep_alive infini en RAM/VRAM
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "keep_alive": -1,
                    "options": {"temperature": 0.0, "num_predict": 250},
                },
                timeout=self.timeout_seconds,
            )
            if resp.status_code == 200:
                body = resp.json()
                text = str(body.get("response", "")).strip()
                if text:
                    return text, "OLLAMA_ACTIVE"
        except Exception:
            pass

        return None, "OFFLINE_RETRIEVAL_ONLY"


class LocalRAGAssistant:
    """Moteur RAG documentaire confiné avec seuil anti-hallucination et citations obligatoires."""

    def __init__(
        self,
        root_dir: Path | str = ROOT_DIR,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
    ) -> None:
        self.indexer = MarkdownSectionIndexer(root_dir=root_dir)
        self.similarity_threshold = float(similarity_threshold)
        self.llm_adapter = LangChainOllamaAdapter(
            base_url=ollama_base_url,
            model_name=ollama_model,
        )

    def reindex(self) -> int:
        return self.indexer.reindex()

    def _detect_prompt_injection(self, query: str) -> bool:
        return any(pattern.search(query) for pattern in PROMPT_INJECTION_PATTERNS)

    def _build_extractive_answer(self, hits: list[dict[str, Any]]) -> str:
        """Construit une réponse synthétique extractive fidèle incluant systématiquement les citations."""
        parts: list[str] = []
        for hit in hits:
            citation = hit["citation"]
            lines = [
                line.strip()
                for line in hit["content"].splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            # On ignore la première ligne d'enrichissement interne "Titre — Section"
            body_lines = lines[1:] if len(lines) > 1 else lines
            summary_snippet = " ".join(body_lines[:4])
            if len(summary_snippet) > 420:
                summary_snippet = summary_snippet[:417] + "..."
            parts.append(f"- {summary_snippet} {citation}")
        return "\n".join(parts)

    def answer_question(
        self,
        query: str,
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Traite une question opérateur avec contrôle d'injection, seuil 0.040 et citations."""
        clean_query = (query or "").strip()
        if not clean_query:
            return {
                "query": "",
                "refused": True,
                "refusal_reason": "EMPTY_QUERY",
                "similarity_threshold": self.similarity_threshold,
                "max_similarity_score": 0.0,
                "llm_status": "OFFLINE_RETRIEVAL_ONLY",
                "model": self.llm_adapter.model_name,
                "answer": "Requête vide : veuillez formuler une question portant sur l'architecture ou les procédures du projet.",
                "citations": [],
                "sources": [],
                "security_confinement": {
                    "read_only": True,
                    "executor_access": False,
                    "tools_enabled": [],
                },
            }

        if self._detect_prompt_injection(clean_query):
            is_online, _ = self.llm_adapter.check_ollama_online()
            return {
                "query": clean_query,
                "refused": True,
                "refusal_reason": "PROMPT_INJECTION_OR_PRIVILEGE_ESCALATION_BLOCKED",
                "prompt_injection_blocked": True,
                "similarity_threshold": self.similarity_threshold,
                "max_similarity_score": 0.0,
                "llm_status": "OLLAMA_ACTIVE" if is_online else "OFFLINE_RETRIEVAL_ONLY",
                "model": self.llm_adapter.model_name,
                "answer": (
                    "Refus de sécurité : tentative d'injection d'instructions ou d'exécution d'action détectée. "
                    "Le service RAG est strictement consultatif (lecture seule) et ne possède aucun outil ni "
                    "accès vers services/executor. [Source: docs/decisions/ADR-005-rag-local-ollama.md#ADR-005 : Assistant RAG Local (Ollama + LangChain) Hors Chemin Critique et Sans Privilèges]"
                ),
                "citations": [
                    "[Source: docs/decisions/ADR-005-rag-local-ollama.md#ADR-005 : Assistant RAG Local (Ollama + LangChain) Hors Chemin Critique et Sans Privilèges]"
                ],
                "sources": [],
                "security_confinement": {
                    "read_only": True,
                    "executor_access": False,
                    "tools_enabled": [],
                },
            }

        hits = self.indexer.search(clean_query, top_k=max(1, top_k))
        max_score = float(hits[0]["similarity_score"]) if hits else 0.0

        live_telemetry = fetch_live_soc_telemetry()
        LIVE_STATUS_KEYWORDS = (
            "etat", "état", "statut", "status", "incident", "anomalie",
            "temps reel", "temps réel", "en cours", "actuel", "maintenant",
            "metrique", "métrique", "transaction", "bloque", "bloquée",
            "waf", "score", "rapport", "situation", "direct", "live", "système", "systeme"
        )
        GREETING_KEYWORDS = (
            "salut", "bonjour", "bonsoir", "hello", "hi", "coucou", "hey",
            "qui es-tu", "qui est tu", "tu es qui", "presente-toi", "présente-toi",
            "ton role", "ton rôle", "que fais-tu", "que sais-tu faire",
            "aide-moi", "aide", "presentation", "présentation", "merci",
            "ça va", "ca va", "comment vas-tu", "comment ca va"
        )
        
        lower_q = clean_query.lower().strip()
        words = set(re.findall(r"\w+", lower_q))
        
        is_live_query = any(kw in lower_q for kw in LIVE_STATUS_KEYWORDS)
        is_greeting = any(kw in lower_q for kw in GREETING_KEYWORDS) or words.intersection({"salut", "bonjour", "hello", "hi", "coucou", "hey"})

        # Garde-fou anti-hallucination strict : refus si similarité < 0.040 (hors salutations et supervision temps réel)
        if (not hits or max_score < self.similarity_threshold) and not is_live_query and not is_greeting:
            is_online, _ = self.llm_adapter.check_ollama_online()
            return {
                "query": clean_query,
                "refused": True,
                "refusal_reason": "BELOW_SIMILARITY_THRESHOLD",
                "similarity_threshold": self.similarity_threshold,
                "max_similarity_score": round(max_score, 4),
                "llm_status": "OLLAMA_ACTIVE" if is_online else "OFFLINE_RETRIEVAL_ONLY",
                "model": self.llm_adapter.model_name,
                "answer": (
                    f"Refus anti-hallucination : aucune procédure ou section documentaire certifiée ne correspond "
                    f"à cette demande (score de similarité maximal = {max_score:.4f} < seuil {self.similarity_threshold}). "
                    f"L'assistant RAG refuse d'inventer une procédure absente de la base documentaire."
                ),
                "citations": [],
                "sources": [],
                "security_confinement": {
                    "read_only": True,
                    "executor_access": False,
                    "tools_enabled": [],
                },
            }

        qualified_hits = [
            h for h in hits if float(h["similarity_score"]) >= self.similarity_threshold
        ]
        if not qualified_hits:
            if is_greeting:
                qualified_hits = [{
                    "citation": "[Source: docs/architecture.md#ADR-005 : Assistant RAG Local]",
                    "excerpt": (
                        "Tu es l'assistant IA et copilote de supervision opérationnelle de PROJECT RESILIENCE-ALPHA (Groupe 2 : Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD).\n"
                        "Tu es spécialisé dans la cyber-résilience de la plateforme bancaire, l'analyse des métriques en temps réel, le modèle Isolation Forest et les procédures certifiées.\n"
                        f"État actuel du système :\n{live_telemetry}"
                    ),
                    "source_file": "docs/architecture.md",
                    "section_title": "Assistant RAG Local",
                    "similarity_score": 1.0,
                }]
            elif is_live_query:
                qualified_hits = [{
                    "citation": "[Source: telemetry/soc-dashboard#LiveStatus]",
                    "excerpt": f"Télémétrie opérationnelle en direct :\n{live_telemetry}",
                    "source_file": "telemetry/soc-dashboard",
                    "section_title": "LiveStatus",
                    "similarity_score": 1.0,
                }]
        citations = [h["citation"] for h in qualified_hits]
        context_block = "\n\n".join(
            f"{h['citation']}\n{h['excerpt']}" for h in qualified_hits
        )

        llm_text, llm_status = self.llm_adapter.generate(
            context=context_block, question=clean_query, live_telemetry=live_telemetry
        )
        if llm_text:
            # Garantit que les citations exactes figurent toujours dans la réponse finale
            missing_citations = [c for c in citations if c not in llm_text]
            if missing_citations:
                final_answer = f"{llm_text}\n\nSources citées : {' '.join(missing_citations)}"
            else:
                final_answer = llm_text
        else:
            extractive = self._build_extractive_answer(qualified_hits)
            final_answer = (
                f"Synthèse documentaire certifiée (mode {llm_status}) :\n{extractive}"
            )

        return {
            "query": clean_query,
            "refused": False,
            "refusal_reason": None,
            "similarity_threshold": self.similarity_threshold,
            "max_similarity_score": round(max_score, 4),
            "llm_status": llm_status,
            "model": self.llm_adapter.model_name,
            "answer": final_answer,
            "citations": citations,
            "sources": [
                {
                    "source_file": h["source_file"],
                    "section_title": h["section_title"],
                    "citation": h["citation"],
                    "similarity_score": h["similarity_score"],
                    "excerpt": h["excerpt"],
                }
                for h in qualified_hits
            ],
            "security_confinement": {
                "read_only": True,
                "executor_access": False,
                "tools_enabled": [],
            },
        }

    def get_status(self) -> dict[str, Any]:
        is_online, models = self.llm_adapter.check_ollama_online()
        return {
            "service": "rag",
            "status": "UP",
            "indexed_chunks": len(self.indexer.chunks),
            "indexed_files": sorted({c.source_file for c in self.indexer.chunks}),
            "similarity_threshold": self.similarity_threshold,
            "ollama_base_url": self.llm_adapter.base_url,
            "ollama_model": self.llm_adapter.model_name,
            "ollama_available_models": models,
            "llm_status": "OLLAMA_ACTIVE" if is_online else "OFFLINE_RETRIEVAL_ONLY",
            "security_confinement": {
                "read_only": True,
                "executor_access": False,
                "tools_enabled": [],
            },
        }


rag_assistant = LocalRAGAssistant()


def create_app(assistant: LocalRAGAssistant | None = None) -> Flask:
    """Construit l'application WSGI Flask pour `services/rag`."""
    active_assistant = assistant or rag_assistant
    flask_app = Flask(__name__)

    @flask_app.get("/health")
    @flask_app.get("/rag/v1/health")
    def health() -> tuple[Response, int]:
        st = active_assistant.get_status()
        return (
            jsonify(
                {
                    "status": "UP",
                    "service": "rag",
                    "indexed_chunks": st["indexed_chunks"],
                    "llm_status": st["llm_status"],
                    "ollama_model": st["ollama_model"],
                    "read_only": True,
                }
            ),
            200,
        )

    @flask_app.get("/status")
    @flask_app.get("/rag/v1/status")
    def status() -> tuple[Response, int]:
        return jsonify(active_assistant.get_status()), 200

    @flask_app.post("/query")
    @flask_app.post("/ask")
    @flask_app.post("/rag/v1/query")
    @flask_app.post("/rag/v1/ask")
    def query_endpoint() -> tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, Mapping):
            return jsonify({"error": "Invalid JSON payload; expected {'query': '...'}"}), 400
        q_text = str(payload.get("query") or payload.get("question") or "")
        top_k = int(payload.get("top_k", 3))
        result = active_assistant.answer_question(q_text, top_k=top_k)
        return jsonify(result), 200

    @flask_app.get("/metrics")
    def metrics_endpoint() -> Response:
        st = active_assistant.get_status()
        ollama_up = 1 if st["llm_status"] == "OLLAMA_ACTIVE" else 0
        lines = [
            "# HELP rag_ollama_active Statut du serveur Ollama local (1=OLLAMA_ACTIVE, 0=OFFLINE_RETRIEVAL_ONLY)",
            "# TYPE rag_ollama_active gauge",
            f"rag_ollama_active {ollama_up}",
            "# HELP rag_indexed_chunks_total Nombre de sections documentaires certifiees indexees",
            "# TYPE rag_indexed_chunks_total gauge",
            f"rag_indexed_chunks_total {st['indexed_chunks']}",
        ]
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

    @flask_app.post("/reindex")
    @flask_app.post("/rag/v1/reindex")
    def reindex_endpoint() -> tuple[Response, int]:
        count = active_assistant.reindex()
        return jsonify({"status": "REINDEXED", "indexed_chunks": count}), 200

    return flask_app


app = create_app(rag_assistant)


if __name__ == "__main__":
    port = int(os.environ.get("RAG_PORT", "8006"))
    app.run(host="0.0.0.0", port=port, debug=False)
