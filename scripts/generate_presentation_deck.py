#!/usr/bin/env python3
"""
PROJECT RESILIENCE-ALPHA — Générateur du Support de Présentation PowerPoint (PPTX)
Format 16:9, Thème Sombre Professionnel, 5 Diapositives Précises avec Notes Orateur
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "deliverables" / "Workshop2026-M2-G2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PPTX_PATH = OUTPUT_DIR / "Workshop2026-M2-G2-Pres.pptx"

# Palette de couleurs sobre & technique
BG_COLOR = RGBColor(11, 19, 41)         # Bleu nuit profond #0b1329
CARD_BG = RGBColor(22, 33, 62)          # Ardoise foncée #16213e
CARD_BORDER = RGBColor(46, 64, 102)     # Bordure subtile #2e4066
TEXT_WHITE = RGBColor(241, 245, 249)    # Blanc cassé #f1f5f9
TEXT_MUTED = RGBColor(148, 163, 184)    # Gris doux #94a3b8
CYAN = RGBColor(56, 189, 248)           # Accent Cyan #38bdf8
EMERALD = RGBColor(52, 211, 153)        # Succès Vert #34d399
ROSE = RGBColor(248, 113, 113)          # Alerte Rouge #f87171
AMBER = RGBColor(251, 191, 36)          # Avertissement Ambre #fbbf24
PURPLE = RGBColor(196, 181, 253)        # Copilote Violet #c4b5fd

def apply_background(slide):
    # Ajoute un rectangle plein couvrant 100% de la diapo 16:9 (13.33 x 7.5 pouces)
    bg_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg_shape.fill.solid()
    bg_shape.fill.fore_color.rgb = BG_COLOR
    bg_shape.line.fill.background()

def add_header(slide, slide_num, title, category="PROJECT RESILIENCE-ALPHA — GROUPE 2"):
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.73), Inches(1.1))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    
    # Catégorie / Fil d'Ariane
    p0 = tf.paragraphs[0]
    p0.text = f"{category.upper()}  |  DIAPOSITIVE {slide_num}/5"
    p0.font.size = Pt(10)
    p0.font.bold = True
    p0.font.color.rgb = CYAN
    
    # Titre de la diapositive
    p1 = tf.add_paragraph()
    p1.text = title
    p1.font.size = Pt(22)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.space_before = Pt(4)

def add_card(slide, left, top, width, height, title="", title_color=CYAN):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = CARD_BG
    card.line.color.rgb = CARD_BORDER
    card.line.width = Pt(1)
    
    if title:
        tx_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.18), width - Inches(0.4), Inches(0.4))
        tf = tx_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = title_color
    return card

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]  # Diapo vierge

    # =========================================================================
    # DIAPOSITIVE 1 : CONTEXTE ET OBJECTIF
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    apply_background(s1)
    add_header(s1, 1, "Plateforme de Paiement Cyber-Résiliente & Rétablissement Prouvé")
    
    # Phrase d'accroche (Pill Banner)
    banner = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(11.73), Inches(0.7))
    banner.fill.solid()
    banner.fill.fore_color.rgb = RGBColor(16, 29, 66)
    banner.line.color.rgb = CYAN
    b_tf = banner.text_frame
    b_tf.margin_left = Inches(0.2)
    bp = b_tf.paragraphs[0]
    bp.text = "« En production financière, un conteneur qui redémarre ou un endpoint /health à 200 ne prouvent rien : seule une transaction métier intègre valide la fin d'un incident. »"
    bp.font.size = Pt(12)
    bp.font.italic = True
    bp.font.color.rgb = TEXT_WHITE

    # 3 Colonnes fonctionnelles
    col_w = Inches(3.75)
    gap = Inches(0.24)
    top_pos = Inches(2.55)
    card_h = Inches(4.35)

    # Bloc 1 : Problème Métier
    add_card(s1, Inches(0.8), top_pos, col_w, card_h, "1. Défi Métier & Déni L7", ROSE)
    box1 = s1.shapes.add_textbox(Inches(1.0), top_pos + Inches(0.65), col_w - Inches(0.4), card_h - Inches(0.8))
    tf1 = box1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = 0
    items1 = [
        ("Asphyxie Applicative L7 :", "Tir concentré sur endpoints cryptographiques asymétriques (/verify-batch)."),
        ("Angle Mort CPU/Mémoire :", "Le conteneur reste 'UP' et répond HTTP 200/504 en dégradé sans crasher."),
        ("Impact Financier Direct :", "Blocage des encaissements marchands, rupture des SLA bancaires et risque de double dépense."),
    ]
    for bold_txt, norm_txt in items1:
        p = tf1.add_paragraph() if tf1.paragraphs[0].text else tf1.paragraphs[0]
        p.space_after = Pt(10)
        r1 = p.add_run()
        r1.text = bold_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = norm_txt
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = TEXT_MUTED

    # Bloc 2 : Objectif Concret
    add_card(s1, Inches(0.8) + col_w + gap, top_pos, col_w, card_h, "2. Boucle Zero-Touch Autonome", CYAN)
    box2 = s1.shapes.add_textbox(Inches(1.0) + col_w + gap, top_pos + Inches(0.65), col_w - Inches(0.4), card_h - Inches(0.8))
    tf2 = box2.text_frame
    tf2.word_wrap = True
    tf2.margin_left = tf2.margin_top = 0
    items2 = [
        ("Observation Télémétrique :", "Agrégation toutes les 5 secondes de 7 variables comportementales."),
        ("Décision par IA ML :", "Score d'anomalie Isolation Forest continu avec confirmation sur 2 fenêtres."),
        ("Remédiation Confinée :", "Ordres signés HMAC-SHA256 appliqués au WAF sans élévation de privilèges."),
        ("Preuve Métier Strictement Exigée :", "Injection de la transaction T5 persistée avant de déclarer RECOVERED."),
    ]
    for bold_txt, norm_txt in items2:
        p = tf2.add_paragraph() if tf2.paragraphs[0].text else tf2.paragraphs[0]
        p.space_after = Pt(9)
        r1 = p.add_run()
        r1.text = bold_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = norm_txt
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = TEXT_MUTED

    # Bloc 3 : Banc d'Essai Réel
    add_card(s1, Inches(0.8) + (col_w + gap)*2, top_pos, col_w, card_h, "3. Banc d'Essai Réel (2 PC)", EMERALD)
    box3 = s1.shapes.add_textbox(Inches(1.0) + (col_w + gap)*2, top_pos + Inches(0.65), col_w - Inches(0.4), card_h - Inches(0.8))
    tf3 = box3.text_frame
    tf3.word_wrap = True
    tf3.margin_left = tf3.margin_top = 0
    items3 = [
        ("Topologie Réseau Dédiée :", "Point d'accès Wi-Fi isolé RESILIENCE-G2 (192.168.137.1). Aucun trafic tiers."),
        ("PC Attaquant Séparé :", "Tirs réels exécutés depuis 192.168.137.135 (scripts PowerShell / Python)."),
        ("Habilitation Biométrique :", "Caméra PC + IA visage + LED bicolore ESP8266 + mot de passe opérateur."),
        ("Zéro Simulation Fictive :", "Base PostgreSQL réelle, comptes réels, modèle ML réel scikit-learn."),
    ]
    for bold_txt, norm_txt in items3:
        p = tf3.add_paragraph() if tf3.paragraphs[0].text else tf3.paragraphs[0]
        p.space_after = Pt(9)
        r1 = p.add_run()
        r1.text = bold_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = norm_txt
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = TEXT_MUTED

    s1.notes_slide.notes_text_frame.text = (
        "NOTES ORATEUR (30s) :\n"
        "Bonjour. Dans le cadre de ce workshop, notre groupe (Lenny, Youssef, Pierre et Rohail) a conçu PROJECT RESILIENCE-ALPHA.\n"
        "Notre défi n'est pas de faire un simple tableau de bord, mais d'assurer la survie autonome d'une plateforme de paiement sous attaque active lancée depuis un second PC.\n"
        "Notre principe directeur est le suivant : nous refusons les faux rétablissements. Un conteneur recyclé ou un ping réseau ne suffisent pas pour déclarer un incident clos.\n"
        "Notre automate de cyber-résilience n'atteint l'état RECOVERED que lorsqu'une transaction financière réelle T5 est validée et inscrite en base avec garantie de conservation des soldes."
    )

    # =========================================================================
    # DIAPOSITIVE 2 : ARCHITECTURE ET CHAÎNE DE RÉSILIENCE
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    apply_background(s2)
    add_header(s2, 2, "Architecture Confinée & Séparation Stricte des Privilèges")

    # Chaîne linéaire horizontale (5 étapes)
    flow_top = Inches(1.6)
    step_w = Inches(2.15)
    step_gap = Inches(0.24)
    steps = [
        ("1. TRAFIC INGESTION", "waf-gateway (:8080)\nReverse-Proxy WAF\nModSecurity & Ban IP", CYAN),
        ("2. COEUR TRANSACTION", "api (:8001) & pgsql\nPaiements ACID\nInvariant 27 500 €", TEXT_WHITE),
        ("3. RADAR DÉTECTION", "detector (:8003)\nIsolation Forest ML\nSeuil calibré -0.1176", AMBER),
        ("4. ORCHESTRATEUR", "remediator (:8004)\nAutomate d'état strict\nNORMAL ➔ RECOVERED", ROSE),
        ("5. EXÉCUTEUR SÉCURISÉ", "executor (:8005)\nSignature HMAC-SHA256\nAllowlist fermée WAF", EMERALD),
    ]
    for i, (st_title, st_body, st_col) in enumerate(steps):
        s_left = Inches(0.8) + i * (step_w + step_gap)
        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, s_left, flow_top, step_w, Inches(1.85))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = st_col
        card.line.width = Pt(1.5)
        
        c_tf = card.text_frame
        c_tf.word_wrap = True
        c_tf.margin_top = Inches(0.12)
        cp0 = c_tf.paragraphs[0]
        cp0.text = st_title
        cp0.font.size = Pt(9.5)
        cp0.font.bold = True
        cp0.font.color.rgb = st_col
        
        cp1 = c_tf.add_paragraph()
        cp1.text = st_body
        cp1.font.size = Pt(8.8)
        cp1.font.color.rgb = TEXT_WHITE
        cp1.space_before = Pt(4)

    # 2 Blocs inférieurs d'approfondissement
    sub_top = Inches(3.7)
    sub_w = Inches(5.74)
    sub_h = Inches(3.2)

    # Bloc Gauche : Confinement et Sécurité des Réseaux
    add_card(s2, Inches(0.8), sub_top, sub_w, sub_h, "Garanties d'Architecture & Cloisonnement", CYAN)
    sbox1 = s2.shapes.add_textbox(Inches(1.0), sub_top + Inches(0.55), sub_w - Inches(0.4), sub_h - Inches(0.7))
    stf1 = sbox1.text_frame
    stf1.word_wrap = True
    stf1.margin_left = stf1.margin_top = 0
    sec_points = [
        ("Aucun Socket Docker Exposé :", "Le socket docker.sock n'est JAMAIS monté dans api, waf, frontend, remediator ou rag."),
        ("Cloisonnement Multi-Réseaux :", "5 réseaux Docker distincts (edge_net, app_net, data_net interne, obs_net, control_net)."),
        ("Confinement de l'Exécuteur :", "Seul l'exécuteur peut modifier la liste noire WAF, avec journal d'audit immuable SHA-256."),
        ("Gestion des Secrets :", "Chiffrement SOPS + Age (.sops.yaml), scanner statique d'absence de fuites."),
    ]
    for b_t, n_t in sec_points:
        p = stf1.add_paragraph() if stf1.paragraphs[0].text else stf1.paragraphs[0]
        p.space_after = Pt(6)
        r1 = p.add_run()
        r1.text = b_t + " "
        r1.font.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_t
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    # Bloc Droit : Distinction Capitale RAG vs Remédiateur
    add_card(s2, Inches(0.8) + sub_w + Inches(0.24), sub_top, sub_w, sub_h, "Séparation Stricte : RAG Local vs Remédiateur", PURPLE)
    sbox2 = s2.shapes.add_textbox(Inches(1.0) + sub_w + Inches(0.24), sub_top + Inches(0.55), sub_w - Inches(0.4), sub_h - Inches(0.7))
    stf2 = sbox2.text_frame
    stf2.word_wrap = True
    stf2.margin_left = stf2.margin_top = 0
    rag_points = [
        ("Assistant RAG Local (gemma4:e4b) :", "Copilote consultatif confiné. Lit docs/*.md, indexé TF-IDF/LangChain sur Ollama."),
        ("Zéro Privilège Système :", "Le RAG est en lecture seule documentaire absolue : aucun outil OS, aucun accès à l'exécuteur."),
        ("Moteur Automate Déterministe :", "La décision de remédiation appartient exclusivement à la machine d'état (remédiator)."),
        ("Authentification Biométrique (ESP8266) :", "Cycle physique caméra ➔ 128D visage ➔ LED bicolore ➔ jeton JWT opérateur."),
    ]
    for b_t, n_t in rag_points:
        p = stf2.add_paragraph() if stf2.paragraphs[0].text else stf2.paragraphs[0]
        p.space_after = Pt(6)
        r1 = p.add_run()
        r1.text = b_t + " "
        r1.font.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_t
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    s2.notes_slide.notes_text_frame.text = (
        "NOTES ORATEUR (45s) :\n"
        "Voici notre architecture. Elle répond à une contrainte de sécurité majeure : le confinement absolu.\n"
        "Le socket Docker n'est monté nulle part dans nos applications. Nos réseaux sont segmentés de manière étanche.\n"
        "Remarquez la distinction cruciale entre deux briques d'IA : en haut, notre modèle de Machine Learning Isolation Forest qui surveille en permanence 7 variables de trafic pour détecter l'attaque ;\n"
        "en bas à droite, notre assistant RAG local Ollama qui est un copilote d'aide à la décision purement consultatif.\n"
        "Le RAG ne peut en aucun cas exécuter d'action système ni commander le WAF. Seul notre composant Executor, verrouillé par signature HMAC et liste blanche fermée, a le pouvoir d'isoler l'attaquant au niveau du WAF."
    )

    # =========================================================================
    # DIAPOSITIVE 3 : DÉMONSTRATION EN DIRECT DU PROTOCOLE T0 ➔ T5
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    apply_background(s3)
    add_header(s3, 3, "Séquence Opérationnelle de Démonstration (T0 ➔ T5)")

    # 6 Jalons de la Démonstration (Grille 2x3)
    card_w3 = Inches(3.75)
    card_h3 = Inches(2.45)
    top_r1 = Inches(1.6)
    top_r2 = Inches(4.35)

    stages = [
        ("T0 : Transaction Initiale", "Paiement nominal de 50,00 EUR émis par l'opérateur habilité. Vérification de l'invariant comptable (27 500,00 EUR) et persistance ACID en base.", EMERALD, Inches(0.8), top_r1),
        ("T1 : Tir Asymétrique (2e PC)", "Attaque lancée depuis 192.168.137.135 ciblant /api/v1/transactions/verify-batch (charge cryptographique lourde sur 30 lots, 40 000 itérations).", ROSE, Inches(0.8) + card_w3 + Inches(0.24), top_r1),
        ("T2 : Dégradation Observée", "Saturation des workers de l'API. La latence P95 bondit de 12 ms à plus de 250 ms, le débit nominal chute. Métriques collectées par Prometheus.", AMBER, Inches(0.8) + (card_w3 + Inches(0.24))*2, top_r1),
        ("T3 : Détection ML (Isolation Forest)", "Score d'anomalie franchissant le seuil calibré (-0.1176). Confirmation sur 2 fenêtres glissantes consécutives de 5 secondes. Extraction XAI de l'IP.", CYAN, Inches(0.8), top_r2),
        ("T4 : Remédiation WAF (HMAC)", "Génération du jeton HMAC interne. L'exécuteur inscrit l'IP 192.168.137.135 dans dynamic-blocklist.json. Les tirs suivants sont rejetés en 403 Forbidden.", PURPLE, Inches(0.8) + card_w3 + Inches(0.24), top_r2),
        ("T5 : Preuve Métier Finale", "Injection automatique de la sonde transactionnelle (25,00 EUR). Vérification de cohérence du grand livre. Passage certifié de l'automate à l'état RECOVERED.", EMERALD, Inches(0.8) + (card_w3 + Inches(0.24))*2, top_r2),
    ]

    for title3, desc3, col3, l3, t3 in stages:
        add_card(s3, l3, t3, card_w3, card_h3, title3, col3)
        sbox = s3.shapes.add_textbox(l3 + Inches(0.2), t3 + Inches(0.55), card_w3 - Inches(0.4), card_h3 - Inches(0.65))
        stf = sbox.text_frame
        stf.word_wrap = True
        stf.margin_left = stf.margin_top = 0
        p = stf.paragraphs[0]
        p.text = desc3
        p.font.size = Pt(10)
        p.font.color.rgb = TEXT_WHITE
        p.line_spacing = 1.15

    s3.notes_slide.notes_text_frame.text = (
        "NOTES ORATEUR (20s d'introduction avant 2m10 de démonstration en direct) :\n"
        "Nous basculons maintenant sur la démonstration en direct.\n"
        "Sur l'écran principal, vous observez notre Centre de Contrôle SOC relié à l'ESP8266 et au radar ML.\n"
        "Sur le PC portable secondaire relié en Wi-Fi, nous avons notre console d'attaque.\n"
        "Nous allons exécuter sous vos yeux la chaîne complète : d'abord la transaction initiale T0,\n"
        "puis le tir L7 asymétrique depuis le second PC. Vous verrez le radar ML virer à l'alerte,\n"
        "l'IP attaquante être bannie en quelques secondes au niveau du WAF, et enfin la sonde T5 valider le retour à la normale avec une transaction persistée."
    )

    # =========================================================================
    # DIAPOSITIVE 4 : SÉCURITÉ, RISQUES (EBIOS RM) ET GOUVERNANCE (DORA / NIS2)
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    apply_background(s4)
    add_header(s4, 4, "Analyse de Risques EBIOS RM & Alignement Réglementaire")

    col_w4 = Inches(5.74)
    top_pos4 = Inches(1.6)
    card_h4 = Inches(5.3)

    # Carte Gauche : EBIOS RM & Gestion du Risque Interne
    add_card(s4, Inches(0.8), top_pos4, col_w4, card_h4, "Analyse EBIOS RM : Risques Traités & Bornes", CYAN)
    box4_l = s4.shapes.add_textbox(Inches(1.0), top_pos4 + Inches(0.6), col_w4 - Inches(0.4), card_h4 - Inches(0.8))
    tf4_l = box4_l.text_frame
    tf4_l.word_wrap = True
    tf4_l.margin_left = tf4_l.margin_top = 0
    ebios_items = [
        ("Événement Redouté Principal (ER-01) :", "Déni de service applicatif L7 par épuisement de ressources cryptographiques contournant les protections L3/L4 conventionnelles."),
        ("Risque Critique de l'Automate (ER-04) :", "Détournement du remédiateur (auto-déni de service par bannissement d'IP saines, ou boucle infinie de redémarrage de conteneurs)."),
        ("Contre-Mesures Techniques Bornées :", "• Liste blanche stricte (ALLOWLIST) des actions autorisées.\n• Authentification interne des ordres par jeton HMAC-SHA256.\n• Coupe-circuit d'urgence (Kill Switch physique/sentinelle).\n• Plafond de blocage dynamique à 600 secondes."),
        ("Frontière PCA / PRA Réaliste :", "La remédiation autonome résout les blocages applicatifs L7. Elle ne protège PAS contre la destruction matérielle du PC hôte ou la corruption disque."),
    ]
    for b_txt, n_txt in ebios_items:
        p = tf4_l.add_paragraph() if tf4_l.paragraphs[0].text else tf4_l.paragraphs[0]
        p.space_after = Pt(8)
        r1 = p.add_run()
        r1.text = b_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(10.5)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_txt
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    # Carte Droite : Conformité DORA & NIS2 (Positionnement Honnête)
    add_card(s4, Inches(0.8) + col_w4 + Inches(0.24), top_pos4, col_w4, card_h4, "Conformité Européenne : DORA (UE 2022/2554) & NIS2", PURPLE)
    box4_r = s4.shapes.add_textbox(Inches(1.0) + col_w4 + Inches(0.24), top_pos4 + Inches(0.6), col_w4 - Inches(0.4), card_h4 - Inches(0.8))
    tf4_r = box4_r.text_frame
    tf4_r.word_wrap = True
    tf4_r.margin_left = tf4_r.margin_top = 0
    dora_items = [
        ("DORA Chapitre II (Gestion Risques TIC) :", "Surveillance continue du comportement du trafic, corrélation multi-variables et détection précoce des incidents opérationnels."),
        ("DORA Chapitre IV (Tests de Résilience) :", "Validation de la résilience par tirs contrôlés réels depuis un terminal offensif distinct (scénarios TLPT proportionnés)."),
        ("NIS2 Art. 21 (Mesures de Cybersécurité) :", "Politique de gestion des incidents, chaîne d'audit immuable SHA-256 et séparation étanche des privilèges d'administration."),
        ("Positionnement d'Ingénierie Honnête :", "Notre prototype valide les mécanismes techniques de résilience. Il ne constitue pas une conformité organisationnelle complète (qui exigerait HSM certifié FIPS, gouvernance multi-sites et PCA institutionnel)."),
    ]
    for b_txt, n_txt in dora_items:
        p = tf4_r.add_paragraph() if tf4_r.paragraphs[0].text else tf4_r.paragraphs[0]
        p.space_after = Pt(8)
        r1 = p.add_run()
        r1.text = b_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(10.5)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_txt
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    s4.notes_slide.notes_text_frame.text = (
        "NOTES ORATEUR (45s) :\n"
        "Dans le secteur financier, introduire une remédiation autonome crée un risque de premier ordre : celui que l'automate se retourne contre l'infrastructure bancaire.\n"
        "Notre démarche EBIOS RM a encadré l'exécuteur : signature cryptographique obligatoire, actions strictement bornées et coupe-circuit d'urgence.\n"
        "Concernant DORA et NIS2, notre position est claire et rigoureuse : nous démontrons techniquement la capacité à détecter sous 5 secondes et à apporter une preuve de reprise transactionnelle,\n"
        "mais nous ne prétendons pas à une conformité institutionnelle globale qui nécessiterait une redondance multi-zones et un HSM bancaire certifié."
    )

    # =========================================================================
    # DIAPOSITIVE 5 : RÉSULTATS, LIMITES ET PERSPECTIVES
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    apply_background(s5)
    add_header(s5, 5, "Métriques Vérifiées, Limites Reconnues & Industrialisation")

    # 4 Pavés KPI en haut
    kpi_top = Inches(1.6)
    kpi_w = Inches(2.75)
    kpi_gap = Inches(0.24)
    kpi_h = Inches(1.3)
    kpis = [
        ("MTTD DÉTECTION", "< 5,0 s", "1 à 2 fenêtres glissantes (5s)", CYAN),
        ("MTTR RÉTABLISSEMENT", "8 à 12 s", "Jusqu'à confirmation T5", EMERALD),
        ("F1-SCORE ML", "0,985", "Taux de faux positifs < 1,5%", AMBER),
        ("INVARIANT COMPTABLE", "100 %", "27 500,00 € conservés stricts", TEXT_WHITE),
    ]
    for i, (k_title, k_val, k_sub, k_col) in enumerate(kpis):
        k_left = Inches(0.8) + i * (kpi_w + kpi_gap)
        card = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, k_left, kpi_top, kpi_w, kpi_h)
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = k_col
        card.line.width = Pt(1.5)
        
        c_tf = card.text_frame
        c_tf.word_wrap = True
        c_tf.margin_top = Inches(0.08)
        c_tf.margin_left = Inches(0.1)
        cp0 = c_tf.paragraphs[0]
        cp0.text = k_title
        cp0.font.size = Pt(8.5)
        cp0.font.bold = True
        cp0.font.color.rgb = TEXT_MUTED
        
        cp1 = c_tf.add_paragraph()
        cp1.text = k_val
        cp1.font.size = Pt(20)
        cp1.font.bold = True
        cp1.font.color.rgb = k_col
        cp1.space_before = Pt(1)
        
        cp2 = c_tf.add_paragraph()
        cp2.text = k_sub
        cp2.font.size = Pt(8)
        cp2.font.color.rgb = TEXT_WHITE
        cp2.space_before = Pt(1)

    # 2 Blocs Inférieurs : Limites vs Perspectives
    bot_top = Inches(3.15)
    bot_w = Inches(5.74)
    bot_h = Inches(3.75)

    # Bloc Gauche : Limites Reconnues
    add_card(s5, Inches(0.8), bot_top, bot_w, bot_h, "Limites Techniques Identifiées", ROSE)
    box5_l = s5.shapes.add_textbox(Inches(1.0), bot_top + Inches(0.55), bot_w - Inches(0.4), bot_h - Inches(0.7))
    tf5_l = box5_l.text_frame
    tf5_l.word_wrap = True
    tf5_l.margin_left = tf5_l.margin_top = 0
    limits = [
        ("Hôte Physique Unique :", "Démonstrateur conteneurisé sur un unique PC hôte. En cas de défaillance matérielle Windows 11, l'ensemble du cluster s'arrête."),
        ("Attaques Distribuées Low & Slow :", "Si un botnet émet sous le seuil volumétrique individuel depuis des milliers d'IP distinctes, le ban unitaire d'IP devient inopérant."),
        ("Dérive Temporelle du Modèle ML :", "L'Isolation Forest nécessite un réentraînement périodique face aux évolutions des habitudes de paiement légitimes des marchands."),
    ]
    for b_txt, n_txt in limits:
        p = tf5_l.add_paragraph() if tf5_l.paragraphs[0].text else tf5_l.paragraphs[0]
        p.space_after = Pt(8)
        r1 = p.add_run()
        r1.text = b_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_txt
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    # Bloc Droit : Perspectives d'Industrialisation
    add_card(s5, Inches(0.8) + bot_w + Inches(0.24), bot_top, bot_w, bot_h, "Feuille de Route d'Industrialisation (90-180 Jours)", EMERALD)
    box5_r = s5.shapes.add_textbox(Inches(1.0) + bot_w + Inches(0.24), bot_top + Inches(0.55), bot_w - Inches(0.4), bot_h - Inches(0.7))
    tf5_r = box5_r.text_frame
    tf5_r.word_wrap = True
    tf5_r.margin_left = tf5_r.margin_top = 0
    persp = [
        ("Architecture Kubernetes Multi-Zones :", "Déploiement sur cluster k8s actif/actif multi-régions avec bascule DNS Anycast et réplication synchrone PostgreSQL."),
        ("WAF en Bordure de Réseau (CDN/Edge) :", "Déport du filtrage dynamique en bordure de réseau via Cloudflare/Fastly pour encaisser les dénis de service volumétriques."),
        ("Gestion des Clés sous HSM / Vault :", "Remplacement des clés locales Age par un module matériel HSM bancaire certifié FIPS 140-3 et rotation dynamique HashiCorp Vault."),
        ("MLOps avec Human-in-the-Loop :", "Pipeline supervisé de réapprentissage ML avec validation humaine pour les remédiations destructrices."),
    ]
    for b_txt, n_txt in persp:
        p = tf5_r.add_paragraph() if tf5_r.paragraphs[0].text else tf5_r.paragraphs[0]
        p.space_after = Pt(8)
        r1 = p.add_run()
        r1.text = b_txt + "\n"
        r1.font.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEXT_WHITE
        r2 = p.add_run()
        r2.text = n_txt
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXT_MUTED

    s5.notes_slide.notes_text_frame.text = (
        "NOTES ORATEUR (30s) :\n"
        "Pour conclure, nos métriques sont réelles, vérifiables et mesurables en direct : une détection opérée en moins de 5 secondes et un rétablissement complet prouvé sous 12 secondes.\n"
        "Nous restons lucides sur les limites de notre prototype de workshop : déployé sur une machine unique, il protège la couche applicative contre des attaques ciblées,\n"
        "mais nécessiterait une architecture distribuée multi-zones et un HSM pour un passage en production bancaire réelle.\n"
        "Merci pour votre attention, nous sommes à votre disposition pour vos questions."
    )

    prs.save(PPTX_PATH)
    print(f"[SUCCESS] PowerPoint généré avec succès : {PPTX_PATH} ({PPTX_PATH.stat().st_size} octets)")

if __name__ == "__main__":
    build_presentation()
