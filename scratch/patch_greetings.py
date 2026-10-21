from pathlib import Path

rag_file = Path("services/rag/app.py")
text = rag_file.read_text(encoding="utf-8")

# Locate LIVE_STATUS_KEYWORDS definition
old_keywords_block = '''        live_telemetry = fetch_live_soc_telemetry()
        LIVE_STATUS_KEYWORDS = (
            "etat", "état", "statut", "status", "incident", "anomalie",
            "temps reel", "temps réel", "en cours", "actuel", "maintenant",
            "metrique", "métrique", "transaction", "bloque", "bloquée",
            "waf", "score", "rapport", "situation", "direct", "live", "système", "systeme"
        )
        is_live_query = any(kw in clean_query.lower() for kw in LIVE_STATUS_KEYWORDS)

        # Garde-fou anti-hallucination strict : refus si similarité < 0.040 (hors requête opérationnelle temps réel)
        if (not hits or max_score < self.similarity_threshold) and not is_live_query:'''

new_keywords_block = '''        live_telemetry = fetch_live_soc_telemetry()
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
        words = set(re.findall(r"\\w+", lower_q))
        
        is_live_query = any(kw in lower_q for kw in LIVE_STATUS_KEYWORDS)
        is_greeting = any(kw in lower_q for kw in GREETING_KEYWORDS) or words.intersection({"salut", "bonjour", "hello", "hi", "coucou", "hey"})

        # Garde-fou anti-hallucination strict : refus si similarité < 0.040 (hors salutations et supervision temps réel)
        if (not hits or max_score < self.similarity_threshold) and not is_live_query and not is_greeting:'''

text = text.replace(old_keywords_block, new_keywords_block)

# Update qualified_hits handling when it's greeting or live query
old_qual_handling = '''        qualified_hits = [
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

new_qual_handling = '''        qualified_hits = [
            h for h in hits if float(h["similarity_score"]) >= self.similarity_threshold
        ]
        if not qualified_hits:
            if is_greeting:
                qualified_hits = [{
                    "citation": "[Source: docs/architecture.md#ADR-005 : Assistant RAG Local]",
                    "excerpt": (
                        "Tu es l'assistant IA et copilote de supervision opérationnelle de PROJECT RESILIENCE-ALPHA (Groupe 2 : Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD).\\n"
                        "Tu es spécialisé dans la cyber-résilience de la plateforme bancaire, l'analyse des métriques en temps réel, le modèle Isolation Forest et les procédures certifiées.\\n"
                        f"État actuel du système :\\n{live_telemetry}"
                    ),
                    "source_file": "docs/architecture.md",
                    "section_title": "Assistant RAG Local",
                    "similarity_score": 1.0,
                }]
            elif is_live_query:
                qualified_hits = [{
                    "citation": "[Source: telemetry/soc-dashboard#LiveStatus]",
                    "excerpt": f"Télémétrie opérationnelle en direct :\\n{live_telemetry}",
                    "source_file": "telemetry/soc-dashboard",
                    "section_title": "LiveStatus",
                    "similarity_score": 1.0,
                }]'''

text = text.replace(old_qual_handling, new_qual_handling)

rag_file.write_text(text, encoding="utf-8")
print("services/rag/app.py updated with conversational greeting and persona support!")
