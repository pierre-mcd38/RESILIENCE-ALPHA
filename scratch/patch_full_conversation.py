from pathlib import Path

rag_file = Path("services/rag/app.py")
text = rag_file.read_text(encoding="utf-8")

old_block = '''        live_telemetry = fetch_live_soc_telemetry()
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

new_block = '''        live_telemetry = fetch_live_soc_telemetry()
        PROJECT_DOMAIN_KEYWORDS = (
            # Cybersécurité & Attaques
            "attaque", "attaques", "attaquant", "attaquants", "attaquer", "agression",
            "pirate", "hack", "hacker", "menace", "menaces", "danger", "alerte", "alertes",
            "incident", "incidents", "anomalie", "anomalies", "perturbation", "dégradation",
            "ddos", "dos", "flood", "brute", "bruteforce", "injection", "sqli", "xss", "l7",
            "waf", "firewall", "bloque", "bloquée", "bloquer", "ip", "blacklist", "rate",
            
            # État système & Supervision
            "etat", "état", "statut", "status", "santé", "sante", "situation", "rapport",
            "temps reel", "temps réel", "en direct", "en cours", "actuel", "maintenant",
            "live", "système", "systeme", "plateforme", "marche", "fonctionne", "panne",
            "ralentissement", "latence", "cpu", "mémoire", "memoire", "saturation", "workers",
            "metrique", "métrique", "score", "forest", "isolation", "ml", "aiops",
            
            # Métier bancaire
            "transaction", "transactions", "paiement", "paiements", "virement", "virements",
            "argent", "solde", "soldes", "centimes", "compte", "comptes", "banque",
            "idempotence", "idempotent", "ledger", "grand livre", "invariant",
            
            # Remédiation & Résilience
            "remediation", "remédiation", "zero-touch", "recupere", "récupère", "recovered",
            "failed", "sonde", "probe", "hmac", "executor", "exécuteur", "ordre", "action",
            
            # Gouvernance & Équipe
            "ebios", "rm", "pca", "pra", "dora", "nis2", "rto", "rpo", "mttd", "mttr",
            "lenny", "youssef", "pierre", "rohail", "barresi", "hansil", "michaud", "arshad",
            "equipe", "équipe", "groupe 2", "g2", "workshop", "epsi", "resilience", "alpha",
            
            # Conversation & Questions opérationnelles adressées à l'IA
            "salut", "bonjour", "bonsoir", "hello", "hi", "coucou", "hey",
            "qui es-tu", "qui est tu", "tu es qui", "presente-toi", "présente-toi",
            "ton role", "ton rôle", "que fais-tu", "que sais-tu faire",
            "aide-moi", "aide", "presentation", "présentation", "merci",
            "ça va", "ca va", "comment vas-tu", "comment ca va",
            "tu as vu", "tu vois", "tu sais", "qu'est-ce", "quest-ce", "que se passe",
            "est-ce que", "dis-moi", "parle-moi", "explique-moi", "raconte-moi"
        )
        
        lower_q = clean_query.lower().strip()
        words = set(re.findall(r"\\w+", lower_q))
        
        is_project_query = any(kw in lower_q for kw in PROJECT_DOMAIN_KEYWORDS) or words.intersection({"salut", "bonjour", "hello", "hi", "coucou", "hey"})

        # Garde-fou anti-hallucination strict : refus si similarité < 0.040 (hors requête liée au projet et supervision)
        if (not hits or max_score < self.similarity_threshold) and not is_project_query:'''

text = text.replace(old_block, new_block)

old_qual_block = '''        qualified_hits = [
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

new_qual_block = '''        qualified_hits = [
            h for h in hits if float(h["similarity_score"]) >= self.similarity_threshold
        ]
        if not qualified_hits and is_project_query:
            qualified_hits = [{
                "citation": "[Source: docs/architecture.md#ADR-005 : Assistant RAG Local]",
                "excerpt": (
                    "Tu es l'assistant IA et copilote de supervision opérationnelle de PROJECT RESILIENCE-ALPHA (Groupe 2 : Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD).\\n"
                    "Tu es spécialisé dans la cyber-résilience de la plateforme bancaire, l'observation des attaques (Flood L7, Brute-Force, SQLi), le modèle Isolation Forest, le WAF dynamique et les procédures certifiées.\\n"
                    f"État opérationnel en direct du système :\\n{live_telemetry}"
                ),
                "source_file": "docs/architecture.md",
                "section_title": "Assistant RAG Local",
                "similarity_score": 1.0,
            }]'''

text = text.replace(old_qual_block, new_qual_block)

rag_file.write_text(text, encoding="utf-8")
print("services/rag/app.py patched with full conversational cyber/project scope!")
