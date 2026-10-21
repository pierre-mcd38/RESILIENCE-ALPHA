import re
from pathlib import Path

rag_file = Path("services/rag/app.py")
text = rag_file.read_text(encoding="utf-8")

# 1. Add fetch_live_soc_telemetry helper
helper_code = '''
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
                    f"- Horodatage : {data.get('timestamp')}\\n"
                    f"- Disponibilité Métier : {avail}\\n"
                    f"- État Automate de Résilience : {state}\\n"
                    f"- Incident en cours : {inc_text}\\n"
                    f"- Score Détecteur ML : {ml_text}\\n"
                    f"- WAF Gateway : Profil '{profile}', {len(blocked)} IP(s) bloquée(s) {blocked}\\n"
                    f"- Dernière Transaction Vérifiée : {tx_text}"
                )
        except Exception:
            continue
    return "- Statut : Services en cours d'exécution. Télémétrie locale en attente."
'''

# Replace template
old_tpl_pattern = r'RAG_SYSTEM_PROMPT_TEMPLATE: str = """.*?"""'
new_tpl = '''RAG_SYSTEM_PROMPT_TEMPLATE: str = """Tu es l'assistant IA et superviseur opérationnel en temps réel de PROJECT RESILIENCE-ALPHA.
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
Réponse factuelle et informée en temps réel :"""'''

text = re.sub(old_tpl_pattern, new_tpl, text, flags=re.DOTALL)

# Insert helper right after PROMPT_INJECTION_PATTERNS
idx_prompt = text.find("RAG_SYSTEM_PROMPT_TEMPLATE: str =")
text = text[:idx_prompt] + helper_code + "\n" + text[idx_prompt:]

# Update format_prompt
text = text.replace(
    'def format_prompt(self, context: str, question: str) -> str:\n        if self._prompt_template is not None:\n            return str(self._prompt_template.format(context=context, question=question))\n        return RAG_SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)',
    'def format_prompt(self, context: str, question: str, live_telemetry: str = "Système Nominal") -> str:\n        if self._prompt_template is not None:\n            try:\n                return str(self._prompt_template.format(context=context, question=question, live_telemetry=live_telemetry))\n            except Exception:\n                pass\n        return RAG_SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question, live_telemetry=live_telemetry)'
)

# Update generate method
text = text.replace(
    'def generate(self, context: str, question: str) -> tuple[str | None, str]:',
    'def generate(self, context: str, question: str, live_telemetry: str = "Système Nominal") -> tuple[str | None, str]:'
)
text = text.replace(
    'prompt = self.format_prompt(context=context, question=question)',
    'prompt = self.format_prompt(context=context, question=question, live_telemetry=live_telemetry)'
)

# Update answer_question
search_anchor = '        # Garde-fou anti-hallucination strict : refus si similarité < 0.040'
live_hook = '''        live_telemetry = fetch_live_soc_telemetry()
        LIVE_STATUS_KEYWORDS = (
            "etat", "état", "statut", "status", "incident", "anomalie",
            "temps reel", "temps réel", "en cours", "actuel", "maintenant",
            "metrique", "métrique", "transaction", "bloque", "bloquée",
            "waf", "score", "rapport", "situation", "direct", "live", "système", "systeme"
        )
        is_live_query = any(kw in clean_query.lower() for kw in LIVE_STATUS_KEYWORDS)

        # Garde-fou anti-hallucination strict : refus si similarité < 0.040 (hors requête opérationnelle temps réel)
        if (not hits or max_score < self.similarity_threshold) and not is_live_query:'''

text = text.replace(search_anchor, live_hook)

# If hits were below threshold but it is a live query, build live context block
old_qualified = '        qualified_hits = [\n            h for h in hits if float(h["similarity_score"]) >= self.similarity_threshold\n        ]'
new_qualified = '''        qualified_hits = [
            h for h in hits if float(h["similarity_score"]) >= self.similarity_threshold
        ]
        if not qualified_hits and is_live_query:
            qualified_hits = [{
                "citation": "[Source: telemetry/soc-dashboard#LiveStatus]",
                "excerpt": f"Télémétrie opérationnelle en direct :\\n{live_telemetry}",
                "source_file": "telemetry/soc-dashboard",
                "section_title": "LiveStatus",
                "similarity_score": 1.0,
            }]'''

text = text.replace(old_qualified, new_qualified)

# Pass live_telemetry to generate
old_call = 'llm_text, llm_status = self.llm_adapter.generate(\n            context=context_block, question=clean_query\n        )'
new_call = 'llm_text, llm_status = self.llm_adapter.generate(\n            context=context_block, question=clean_query, live_telemetry=live_telemetry\n        )'
text = text.replace(old_call, new_call)

rag_file.write_text(text, encoding="utf-8")
print("services/rag/app.py patched successfully!")
