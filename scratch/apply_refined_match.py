import re
from pathlib import Path

rag_file = Path("services/rag/app.py")
text = rag_file.read_text(encoding="utf-8")

old_domain_block = text[text.find('PROJECT_DOMAIN_KEYWORDS = ('):text.find('is_project_query =')]

new_domain_block = '''CYBER_AND_SYSTEM_WORDS = {
            "attaque", "attaques", "attaquant", "attaquants", "attaquer", "agresseur",
            "pirate", "hack", "hacker", "menace", "menaces", "danger", "alerte", "alertes",
            "incident", "incidents", "anomalie", "anomalies", "perturbation", "degradation", "dégradation",
            "ddos", "dos", "flood", "brute", "bruteforce", "injection", "sqli", "xss", "l7",
            "waf", "firewall", "bloque", "bloquee", "bloqué", "bloquée", "bloquer", "ip", "blacklist",
            "etat", "état", "statut", "status", "sante", "santé", "situation", "rapport",
            "metrique", "métrique", "score", "forest", "isolation", "ml", "aiops",
            "transaction", "transactions", "paiement", "paiements", "virement", "virements",
            "argent", "solde", "soldes", "centimes", "compte", "comptes", "banque",
            "idempotence", "idempotent", "ledger", "invariant", "remediation", "remédiation",
            "ebios", "pca", "pra", "dora", "nis2", "lenny", "youssef", "pierre", "rohail",
            "resilience", "alpha", "epsi", "workshop", "salut", "bonjour", "hello", "coucou"
        }
        CONVERSATIONAL_PHRASES = (
            "qui es-tu", "qui est tu", "tu es qui", "presente-toi", "présente-toi",
            "ton role", "ton rôle", "que fais-tu", "tu as vu", "tu vois", "tu sais",
            "comment vas-tu", "ça va", "ca va", "aide-moi"
        )
        
        lower_q = clean_query.lower().strip()
        words = set(re.findall(r"\\w+", lower_q))
        
        '''

text = text.replace(old_domain_block, new_domain_block)

old_check = 'is_project_query = any(kw in lower_q for kw in PROJECT_DOMAIN_KEYWORDS) or words.intersection({"salut", "bonjour", "hello", "hi", "coucou", "hey"})'
new_check = 'is_project_query = bool(words.intersection(CYBER_AND_SYSTEM_WORDS)) or any(phrase in lower_q for phrase in CONVERSATIONAL_PHRASES)'
text = text.replace(old_check, new_check)

rag_file.write_text(text, encoding="utf-8")
print("services/rag/app.py updated with refined word/phrase matching!")
