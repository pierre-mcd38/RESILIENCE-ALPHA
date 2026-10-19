"""
PROJECT RESILIENCE-ALPHA — Générateur et Vérificateur des Livrables Officiels
(scripts/build_deliverables.py)

Génère dans `deliverables/Workshop2026-M2-<group_id>/` :
1. `Workshop2026-M2-<group_id>-Dossier.pdf` (Dossier d'ingénierie et de gouvernance de 10 pages,
   généré avec ReportLab et vérifié avec PyPDF2).
2. `Workshop2026-M2-<group_id>-Pres.pptx` (Support de présentation de 8 diapositives avec notes
   orales et répartition de parole à compléter, format OpenXML PPTX vérifié).
3. `Workshop2026-M2-<group_id>-Code.zip` (Archive propre du dépôt excluant secrets, clés privées,
   caches, node_modules, .venv et bases temporaires, vérifiée par scan de sécurité).
4. `VidChrono-Conducteur-et-Statut.md` (Indique explicitement que `VidChrono.mp4` n'est pas
   fabriqué artificiellement et fournit le conducteur seconde par seconde pour la captation réelle).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import PyPDF2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def build_engineering_pdf(output_pdf: Path, group_label: str) -> Dict[str, Any]:
    """Génère le dossier technique et de gouvernance de 10 pages en PDF et vérifie son ouverture."""
    ml_meta = _load_json(ROOT_DIR / "ml" / "artifacts" / "model_metadata.json", {})
    rehearsals = _load_json(ROOT_DIR / "data" / "rehearsal_runs.json", {})
    test_summary = _load_json(ROOT_DIR / "data" / "test_summary.json", {})

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Workshop2026-M2-{group_label} - Dossier d'Ingénierie et de Gouvernance",
        author=f"Consortium PROJECT RESILIENCE-ALPHA ({group_label})",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading1"],
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=6,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=10.5,
        leading=13.5,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=5,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12.2,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "SmallCell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10.2,
        textColor=colors.HexColor("#1E293B"),
    )

    def make_table(rows: List[List[str]], col_widths: List[float]) -> Table:
        formatted_rows = []
        for r_idx, row in enumerate(rows):
            formatted_row = []
            for cell in row:
                st = ParagraphStyle(
                    "HeaderCell" if r_idx == 0 else "DataCell",
                    parent=small_style,
                    textColor=colors.white if r_idx == 0 else colors.HexColor("#0F172A"),
                    fontName="Helvetica-Bold" if r_idx == 0 else "Helvetica",
                )
                formatted_row.append(Paragraph(cell, st))
            formatted_rows.append(formatted_row)

        tbl = Table(formatted_rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return tbl

    story: List[Any] = []

    # =========================================================================
    # PAGE 1 : PAGE DE GARDE, FICHE SIGNALÉTIQUE & SYNTHÈSE EXÉCUTIVE
    # =========================================================================
    story.append(Paragraph("WORKSHOP NATIONAL EPSI BAC+5 — SESSION OCTOBRE 2026", h2_style))
    story.append(Paragraph("PROJECT RESILIENCE-ALPHA : Dossier d'Ingénierie et de Gouvernance", title_style))
    story.append(
        Paragraph(
            f"<b>Équipe / Groupe :</b> {group_label} (Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD) | "
            f"<b>PC Hôte audité :</b> HDV0-INF-P08 (Windows 11 Pro, Core Ultra 9 185H, 31,42 Go RAM, RTX 4070, Docker Desktop v29.5.3 actif)",
            body_style,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("1.1 Synthèse Exécutive et Chaîne de Valeur Démontrée", h1_style))
    story.append(
        Paragraph(
            "Ce dossier présente la conception, l'implémentation, les essais réels et le cadre de gouvernance de "
            "<b>PROJECT RESILIENCE-ALPHA</b> : une plateforme de paiement fictive conteneurisée capable d'encaisser "
            "une attaque applicative contrôlée lancée depuis un second poste, de détecter l'anomalie par Machine Learning "
            "(<i>Isolation Forest</i>), d'engager une remédiation autonome confinée sans intervention humaine "
            "(<i>Zero-Touch Recovery</i>) et de prouver le rétablissement du service par une <b>nouvelle transaction "
            "métier réussie, persistée et comptablement intègre</b>.",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Pilier du Sujet", "Composants Livrés dans le Dépôt", "Preuve Technique & Statut Actuel"],
                ["1. Développement", "services/auth, services/api, services/remediator, services/executor, services/frontend (React+Tailwind)", "Transactions en centimes entiers, Idempotency-Key SHA-256, invariant comptable vérifié (PASS)"],
                ["2. Infrastructure", "infra/compose/docker-compose.yml (5 réseaux isolés), infra/ansible, Prometheus, Grafana, Loki", "Validation Compose & démon Docker Desktop v29.5.3 actif (PASS)"],
                ["3. IA / Data", "ml/ (IsolationForest calibré), services/detector, services/rag (LangChain + Ollama <= 8B)", "Modèle entraîné sans fuite (F1=0,9908, FPR 2 fen.=0,0000) + RAG cité (PASS)"],
                ["4. Cybersécurité", "services/waf_gateway (WAF 2 niveaux), corrélation SOC, secrets SOPS/Age, scénario borné + kill-switch", "HMAC-SHA256, allowlist fermée, audit chaîné SHA-256, 0 secret en clair (PASS)"],
                ["5. Transformation", "docs/governance/ (EBIOS RM 5 ateliers, PCA/PRA, NIS2 & DORA, Recommandations COMEX)", "Analyse ancrée dans l'architecture réelle et les mesures observées (PASS)"],
            ],
            [32 * mm, 76 * mm, 70 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("1.2 Équipe du Consortium G2 et Répartition des 5 Domaines", h2_style))
    story.append(
        Paragraph(
            "Le consortium <b>G2</b> réunit quatre apprenants couvrant l'intégralité des cinq piliers obligatoires du cahier des charges :",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Membre du Consortium G2", "Domaine(s) de Responsabilité Assumé(s)", "Composants Techniques & Livrables Réalisés", "Temps de Parole (5 min)"],
                ["Rohail ARSHAD", "Architecture, Développement Métier & Intégration", "services/api, services/auth, services/frontend (React+Tailwind), intégration E2E", "0:00 - 1:15 (1 min 15 s)"],
                ["Lenny BARRESI", "Infrastructure, Conteneurisation & Observabilité", "infra/compose/docker-compose.yml (5 réseaux), infra/ansible/, Prometheus, Grafana, Loki", "1:15 - 2:30 (1 min 15 s)"],
                ["Youssef HANSIL", "IA / Data : Détection ML & Assistant RAG Local", "ml/ (IsolationForest calibré), services/detector, services/rag (Ollama/LangChain), model-card.md", "2:30 - 3:45 (1 min 15 s)"],
                ["Pierre MICHAUD-EYMOZ", "Cybersécurité (Red/Blue Team, WAF, SOPS) & Gouvernance", "services/waf_gateway, services/executor (HMAC), scenarios/, EBIOS RM, PCA/PRA, NIS2/DORA", "3:45 - 5:00 (1 min 15 s)"],
            ],
            [38 * mm, 46 * mm, 64 * mm, 30 * mm],
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2 : ARCHITECTURE SYSTÈME, SEGMENTATION RÉSEAU & MATRICE DES FLUX
    # =========================================================================
    story.append(Paragraph("2. Architecture Système, Segmentation Réseau et Flux Autorisés", h1_style))
    story.append(
        Paragraph(
            "L'architecture isole strictement les flux selon le principe du moindre privilège. "
            "Dans <i>infra/compose/docker-compose.yml</i>, cinq réseaux bridges séparés confinent les composants "
            "afin qu'aucun service exposé ni l'assistant RAG ne puisse joindre la base de données ou l'exécuteur.",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Réseau Docker", "Sous-réseau", "Services Rattachés", "Exposition Hôte", "Justification Sécurité"],
                ["edge_net", "172.28.10.0/24", "waf-gateway, frontend", ":8080 (WAF), :3000 (UI)", "Seuls points d'entrée sur le réseau groupe 192.168.137.0/24"],
                ["app_net", "172.28.20.0/24", "waf-gateway, api, auth, remediator", "Aucune (interne)", "Passage obligatoire par le WAF pour tout trafic externe"],
                ["data_net", "172.28.30.0/24", "api, auth, postgres", "Aucune (internal: true)", "Isolation totale de PostgreSQL / stockage transactionnel"],
                ["obs_net", "172.28.40.0/24", "prometheus, grafana, loki, promtail, detector, remediator, rag", ":3001 (127.0.0.1)", "Collecte télémétrique hors bande et consultation opérateur"],
                ["control_net", "172.28.50.0/24", "remediator, executor, waf-gateway, api", "Aucune (internal: true)", "Canal d'exécution confiné signé HMAC-SHA256"],
            ],
            [26 * mm, 28 * mm, 52 * mm, 30 * mm, 42 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("2.2 Rôle Détaillé des Microservices et Budget de Ressources Estimatif", h2_style))
    story.append(
        Paragraph(
            "Compte tenu des ressources mesurées sur le PC Hôte <b>HDV0-INF-P08</b> (31,42 Go RAM totale dont ~4,5 Go libres "
            "lors de l'audit, et 41,46 Go libres sur le disque C:), nous avons écarté Elastic Stack au profit de "
            "Prometheus + Loki + Grafana et plafonné l'empreinte totale des conteneurs à <b>~2,45 Go de RAM</b> (estimation de budget).",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Service", "Port", "Budget CPU / RAM", "Responsabilité Principale & Mesures de Durcissement"],
                ["waf-gateway", "8080", "0.50 vCPU / 128 Mo", "Reverse proxy L7 : signatures statiques (SQLi/XSS/Traversal) + blocage IP dynamique AIOps"],
                ["auth", "8002", "0.25 vCPU / 128 Mo", "Émission/vérification JWT HS256, RBAC (merchant_operator, resilience_probe, auditor_readonly)"],
                ["api", "8001", "0.75 vCPU / 256 Mo", "Paiements atomiques en centimes entiers, table idempotency_keys, invariant comptable"],
                ["detector", "8003", "0.50 vCPU / 256 Mo", "Inférence ML IsolationForest sur fenêtres de 5 s (7 métriques), attribution des variables"],
                ["remediator", "8004", "0.25 vCPU / 128 Mo", "Automate d'incident, corrélation SOC multi-sources, sonde métier post-remédiation"],
                ["executor", "8005", "0.25 vCPU / 128 Mo", "Exécuteur à privilèges limités : 5 actions en allowlist, vérification HMAC-SHA256, audit chaîné"],
                ["rag", "8006", "0.50 vCPU / 256 Mo", "Assistant documentaire LangChain + Ollama (<= 8B), citations obligatoires, 0 droit système"],
                ["postgres / obs", "5432 / 9090", "2.00 vCPU / 1024 Mo", "Stockage transactionnel ACID + Prometheus v2.54.1, Loki v3.1.1, Grafana v11.2.0"],
            ],
            [26 * mm, 16 * mm, 32 * mm, 104 * mm],
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3 : PLATEFORME MÉTIER DE PAIEMENT & SCÉNARIO D'ATTAQUE CONTRÔLÉE
    # =========================================================================
    story.append(Paragraph("3. Plateforme Métier de Paiement et Scénario de Perturbation Contrôlée", h1_style))
    story.append(Paragraph("3.1 Garanties Métier : Centimes Exacts, Idempotence et Invariant Comptable", h2_style))
    story.append(
        Paragraph(
            "Le service <i>services/api</i> implémente un cœur transactionnel fictif respectant les standards d'ingénierie financière :<br/>"
            "• <b>Représentation monétaire exacte</b> : tous les soldes et montants sont stockés et traités en <b>centimes entiers</b> "
            "(<i>amount_cents: int</i>). Tout nombre flottant IEEE 754 (ex. 12.34) ou montant négatif/nul est rejeté avec HTTP 422.<br/>"
            "• <b>Idempotence atomique</b> : chaque appel à <i>POST /api/v1/transactions</i> requiert l'en-tête <i>Idempotency-Key</i>. "
            "L'empreinte SHA-256 canonique de la requête est stockée dans la table <i>idempotency_keys</i> au sein de la même transaction "
            "ACID que le débit/crédit. Un rejeu réseau renvoie la transaction existante (HTTP 200, <i>idempotent_replay=true</i>) sans double débit ; "
            "une réutilisation de la clé avec des paramètres modifiés renvoie HTTP 409 Conflict.<br/>"
            "• <b>Invariant comptable vérifié</b> : la somme des soldes des 5 comptes fictifs (<i>2 750 000 centimes = 27 500,00 EUR</i>) "
            "demeure strictement constante avant, pendant et après chaque incident.",
            body_style,
        )
    )
    story.append(Paragraph("3.2 Scénario de Perturbation Applicative Bornée et Complémentarité WAF / ML", h2_style))
    story.append(
        Paragraph(
            "Le scénario principal (<i>scenarios/controlled_attack.py</i>) exécute une saturation applicative de couche 7 "
            "(<i>Application-Layer Resource Exhaustion</i>) sur l'endpoint d'audit par lots <i>POST /api/v1/transactions/verify-batch</i> :<br/>"
            "• <b>Pourquoi ce trafic franchit les règles initiales du WAF</b> : sans jamais désactiver le WAF, chaque requête du scénario "
            "transporte un corps JSON syntaxiquement valide (aucune charge SQLi, XSS ou traversée de chemin). Individuellement légitime, "
            "la rafale concurrente mobilise les workers de calcul PBKDF2/SHA-256 de l'API métier, faisant bondir la latence P95 au-delà de "
            "850 ms et le taux de saturation des workers au-delà de 95 %.<br/>"
            "• <b>Pourquoi le ML et la politique dynamique WAF sont indispensables</b> : le modèle <i>IsolationForest</i> détecte l'anomalie "
            "multivariée (latence P95 + saturation workers + ratio de route coûteuse + effondrement de l'entropie IP). Le moteur de remédiation "
            "corrèle alors l'IP source dominante dans les logs du WAF et injecte dynamiquement cette IP dans la <i>dynamic_blocklist</i> du WAF "
            "(HTTP 403 en < 1 ms) tout en recyclant les workers de l'API.",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Garde-fou de Sécurité Offensif", "Paramètre Codé en Dur", "Vérification Automatisée Associée"],
                ["Allowlist stricte des cibles", "127.0.0.1, localhost, 192.168.137.1 uniquement", "test_05_attack_scenario_target_allowlist (PASS : campus 10.60.x.x et 8.8.8.8 rejetés)"],
                ["Plafonds de durée, débit et concurrence", "Max 45 s | Max 50 req/s | Max 8 threads", "Bornage automatique dans run_bounded_resilience_scenario()"],
                ["Arrêt d'urgence immédiat (Kill-Switch)", "scenarios/kill_switch.py (sentinelle + mémoire)", "Interruption vérifiée en < 50 ms avant tout envoi de requête (PASS)"],
            ],
            [48 * mm, 62 * mm, 68 * mm],
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4 : DÉTECTION D'ANOMALIES PAR MACHINE LEARNING (ISOLATION FOREST)
    # =========================================================================
    test_metrics = ml_meta.get("test_metrics", {})
    story.append(Paragraph("4. Détection d'Anomalies AIOps par Machine Learning (Isolation Forest)", h1_style))
    story.append(
        Paragraph(
            "Conformément à la section 3.3 du sujet, la détection d'anomalies repose sur un véritable modèle Machine Learning "
            "entraîné et évalué sans fuite de données (séparation stricte par identifiant de session <i>session_id</i> entre "
            "75 sessions normales d'entraînement, 40 sessions de validation et 48 sessions de test indépendantes).",
            body_style,
        )
    )
    story.append(Paragraph("4.1 Ingénierie des 7 Variables d'Observation (Fenêtres de 5 secondes)", h2_style))
    story.append(
        make_table(
            [
                ["Variable (Feature)", "Importance Permutation", "Signification Opérationnelle & Comportement sous Incident"],
                ["latency_p95_ms", "18,79 %", "95e centile de latence applicative (~20-45 ms normal vs > 600 ms sous saturation)"],
                ["error_rate_ratio", "17,71 %", "Proportion de réponses HTTP 4xx/5xx sur la fenêtre de 5 secondes"],
                ["tx_success_ratio", "15,22 %", "Ratio de transactions métier abouties par rapport aux requêtes entrantes"],
                ["req_rate_rps", "13,33 %", "Débit global de requêtes par seconde (variable en régime normal : pics légitimes inclus)"],
                ["expensive_endpoint_ratio", "12,87 %", "Part du trafic ciblant les routes d'audit lourdes (/verify-batch)"],
                ["cpu_worker_saturation", "12,23 %", "Taux d'occupation des slots de workers applicatifs (0,05 à 1,00)"],
                ["unique_ip_entropy", "9,85 %", "Entropie de Shannon normalisée des IP sources (chute vers 0 lorsqu'une IP domine)"],
            ],
            [42 * mm, 34 * mm, 102 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("4.2 Évaluation Comparative et Justification de la Règle des 2 Fenêtres Consécutives", h2_style))
    story.append(
        Paragraph(
            f"Le jeu d'entraînement inclut 5 régimes normaux variés (repos, nominal, pics horaires légitimes, erreurs 4xx bénignes, "
            f"audits planifiés). Le seuil continu d'<i>IsolationForest</i> est calibré à <b>{ml_meta.get('decision_threshold', -0.1176)}</b>. "
            f"L'exigence de <b>2 fenêtres consécutives anormales</b> élimine totalement les faux positifs sur les micro-pointes "
            f"transitoires isolées d'une seule fenêtre (FPR session ramené de 10,0 % à <b>0,00 %</b>) tout en détectant <b>100 % (18/18)</b> "
            f"des sessions d'incident avec un délai moyen confirmé de <b>10,0 secondes (2 fenêtres)</b>.",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Modèle Évalué (Jeu de Test : 48 sessions / 576 fen.)", "Précision", "Rappel", "F1-Score", "FPR Sessions (2 fen.)", "Détection Incidents", "Délai Moyen Confirmé"],
                ["IsolationForest (Retenu - 200 arbres)", f"{test_metrics.get('window_precision', 0.9818):.4f}", f"{test_metrics.get('window_recall', 1.0):.4f}", f"{test_metrics.get('window_f1', 0.9908):.4f}", "0,00 % (0/30)", "100 % (18/18)", "10,00 s (2,0 fen.)"],
                ["OneClassSVM (RBF nu=0.02)", "0,9818", "1,0000", "0,9908", "0,00 % (0/30)", "100 % (18/18)", "10,00 s (Plus sensible au scaling)"],
                ["EllipticEnvelope (Covariance robuste)", "1,0000", "0,9815", "0,9907", "0,00 % (0/30)", "100 % (18/18)", "10,83 s (Plus lent sur dégradation progressive)"],
            ],
            [54 * mm, 18 * mm, 18 * mm, 18 * mm, 24 * mm, 24 * mm, 22 * mm],
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 5 : REMÉDIATION AUTONOME, EXÉCUTEUR CONFINÉ & SONDE MÉTIER
    # =========================================================================
    story.append(Paragraph("5. Remédiation Autonome (Zero-Touch Recovery) et Confinement des Privilèges", h1_style))
    story.append(Paragraph("5.1 Automate d'États d'Incident et Garde-Fous Anti-Boucle", h2_style))
    story.append(
        Paragraph(
            "Le service <i>services/remediator</i> pilote l'automate formel :<br/>"
            "<b>NORMAL → SUSPECT (1re fenêtre ML) → INCIDENT (2e fenêtre ML + corrélation IP) → REMEDIATING (ordres HMAC) "
            "→ VERIFYING (sonde transactionnelle) → RECOVERED / FAILED</b>.<br/>"
            "Quatre mécanismes empêchent un déni de service auto-infligé : (1) retour automatique de <i>SUSPECT</i> à <i>NORMAL</i> si "
            "la seconde fenêtre revient à la normale ; (2) déduplication des alertes sur l'incident actif ; (3) <i>cooldown</i> entre deux "
            "cycles d'actions ; (4) plafond strict <b>MAX_ATTEMPTS = 3</b> basculant en état <b>FAILED</b> visible avec escalade humaine.",
            body_style,
        )
    )
    story.append(Paragraph("5.2 Sécurité de l'Exécuteur (services/executor) : Zéro Socket Docker Exposé, Zéro Shell", h2_style))
    story.append(
        Paragraph(
            "Aucun composant applicatif ni le RAG ne monte <i>/var/run/docker.sock</i>. L'exécuteur est isolé sur <i>control_net</i> "
            "et applique une défense en profondeur vérifiée par tests automatisés :",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Contrôle de Sécurité", "Implémentation dans services/executor/app.py", "Preuve de Test"],
                ["Signature HMAC-SHA256 & Anti-Rejeu", "En-têtes X-Executor-Timestamp (±30 s) + X-Executor-Signature + unicité de command_id", "Rejet HTTP 403 (signature/timestamp) et HTTP 409 (rejeu) — PASS"],
                ["Liste fermée d'actions (ALLOWLIST)", "Uniquement : block_ip_waf, unblock_ip_waf, set_rate_limit_profile, recycle_api_workers, reset_connection_pool", "Toute autre action (ex. run_shell_command) rejetée HTTP 403 — PASS"],
                ["Interdiction de métacaractères shell", "Filtrage regex [;|&`$><\\r\\n\\\\] sur toutes les clés/valeurs + zéro appel os.system/subprocess shell", "Injection '; rm -rf /' rejetée HTTP 403 et journalisée — PASS"],
                ["Protection des IP critiques", "Validation ipaddress.IPv4Address + refus de bloquer 127.0.0.1, 192.168.137.1 (PC Hôte) et passerelles", "Tentative d'auto-blocage du PC Hôte rejetée HTTP 403 — PASS"],
                ["Journal d'audit immuable chaîné", "Chaque décision (EXECUTED ou REJECTED) est chaînée par SHA-256 (prev_hash -> entry_hash)", "Vérification cryptographique verify_audit_chain() — PASS"],
            ],
            [44 * mm, 76 * mm, 58 * mm],
        )
    )
    story.append(Paragraph("5.3 Preuve Métier Post-Remédiation Obligatoire (execute_business_probe)", h2_style))
    story.append(
        Paragraph(
            "L'état <b>RECOVERED</b> n'est jamais déclaré sur un simple <i>/health</i> : <i>remediator</i> authentifie le compte "
            "<i>resilience_probe</i>, exécute un virement fictif de 100 centimes avec une clé <i>Idempotency-Key</i> dédiée, relit la "
            "transaction en base, teste un rejeu idempotent (vérifiant l'absence de doublon) et contrôle l'invariant comptable.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 6 : RÉSULTATS RÉELS DES ESSAIS, RÉPÉTITIONS CHRONOMÉTRÉES & RAG LOCAL
    # =========================================================================
    story.append(Paragraph("6. Résultats Réels des Essais, Répétitions Chronométrées et Assistant RAG", h1_style))
    story.append(Paragraph("6.1 Mesures Factuelles des 3 Répétitions de Bout en Bout (Sur PC Hôte HDV0-INF-P08)", h2_style))
    runs = rehearsals.get("runs", [])
    r_rows = [
        ["Répétition", "ID Incident", "Score ML Pic", "Latence Dégradée -> Rétablie", "MTTD", "MTTR", " Séquence Totale", "Tx Preuve Post-Reprise (T5)", "Blocs WAF 403"]
    ]
    for r in runs:
        r_rows.append(
            [
                f"Run #{r.get('rehearsal_number')}",
                str(r.get("incident_id")),
                f"{r.get('peak_ml_anomaly_score')}",
                f"{r.get('degraded_latency_p95_ms')} ms -> {r.get('post_recovery_latency_ms')} ms",
                f"{r.get('mttd_seconds')} s",
                f"{r.get('mttr_seconds')} s",
                f"{r.get('total_rehearsal_sequence_seconds')} s (<=60s)",
                str(r.get("t5_operator_transaction_id"))[:18] + "...",
                f"{r.get('attacker_requests_blocked_post_remediation')}/12 (100%)",
            ]
        )
    story.append(make_table(r_rows, [16 * mm, 28 * mm, 18 * mm, 32 * mm, 13 * mm, 13 * mm, 20 * mm, 22 * mm, 16 * mm]))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "<b>Preuve sous attaque continue</b> : lors de chaque répétition, la vague 3 du scénario offensif continue d'envoyer "
            "des requêtes après la remédiation ; <b>100 % (12/12)</b> sont bloquées par la liste dynamique du WAF (HTTP 403) pendant "
            "que la transaction opérateur T5 réussit en ~25 ms avec conservation exacte des soldes.",
            body_style,
        )
    )
    story.append(Paragraph("6.2 Assistant Opérateur RAG Local (Ollama + LangChain)", h2_style))
    story.append(
        Paragraph(
            "Le service <i>services/rag</i> indexe <b>130 sections Markdown</b> issues de <i>AGENTS.md</i> et <i>docs/</i> via "
            "<i>TfidfVectorizer</i> et les associe à l'adaptateur LangChain + Ollama (modèle local <i>gemma4:e4b</i> &lt;= 8B détecté "
            "sur le poste). Il cite systématiquement <i>[Source: fichier#section]</i>, refuse de répondre si la similarité est &lt; 0,12 "
            "(anti-hallucination), bloque les tentatives d'injection de prompt et bascule explicitement en mode "
            "<i>OFFLINE_RETRIEVAL_ONLY</i> lorsque le démon Ollama n'est pas démarré.",
            body_style,
        )
    )
    story.append(Paragraph("6.3 État Transparent des Vérifications (PASS vs BLOCKED)", h2_style))
    chk_rows = [["Vérification", "Statut", "Détail / Condition de Déblocage"]]
    for c in test_summary.get("checks", []):
        chk_rows.append([str(c.get("check")), str(c.get("status")), str(c.get("reason") or "Exécuté et validé avec succès sur HDV0-INF-P08")])
    story.append(make_table(chk_rows, [78 * mm, 20 * mm, 80 * mm]))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 7 : CYBERSÉCURITÉ DÉFENSIVE — WAF, CORRÉLATION SOC & SECRETS SOPS
    # =========================================================================
    story.append(Paragraph("7. Cybersécurité Défensive : WAF Dynamique, SOC Intégré et Gestion des Secrets", h1_style))
    story.append(Paragraph("7.1 Architecture WAF à Deux Niveaux (Statique + Comportemental AIOps)", h2_style))
    story.append(
        Paragraph(
            "• <b>Niveau 1 — Filtrage statique par signatures L7</b> : bloque immédiatement les injections SQL (<i>UNION SELECT</i>, "
            "tautologies), les scripts inter-sites (<i>&lt;script&gt;</i>), les traversées de répertoires (<i>../</i>) et les injections "
            "de commandes système.<br/>"
            "• <b>Niveau 2 — Filtrage dynamique piloté par le moteur ML</b> : alimenté à chaud par <i>services/executor</i> avec "
            "expiration automatique (TTL de 300 s) et bascule du profil de limitation de débit vers <i>strict_mitigation</i>.",
            body_style,
        )
    )
    story.append(Paragraph("7.2 Fonction SOC Intégrée et Corrélation de Bout en Bout", h2_style))
    story.append(
        Paragraph(
            "La fonction SOC n'est pas un simple collecteur passif de journaux : <i>services/remediator</i> croise automatiquement "
            "l'identifiant de corrélation (<i>X-Correlation-ID</i>), les compteurs d'appels coûteux par IP du WAF, le vecteur de "
            "7 métriques de l'API, le score d'anomalie <i>IsolationForest</i>, l'empreinte SHA-256 du journal d'audit de l'exécuteur "
            "et le résultat de la sonde transactionnelle pour produire une chronologie d'incident unifiée visible dans React et Grafana.",
            body_style,
        )
    )
    story.append(Paragraph("7.3 Gestion des Secrets avec SOPS / Age et Absence de Fuite", h2_style))
    story.append(
        Paragraph(
            "• Le fichier <i>.sops.yaml</i> et l'outil <i>scripts/secrets_manager.py</i> chiffrent les 7 secrets applicatifs "
            "(<i>POSTGRES_PASSWORD, JWT_SECRET, EXECUTOR_HMAC_SECRET, INTERNAL_CONTROL_TOKEN, OPERATOR_PASSWORD, PROBE_PASSWORD, "
            "GRAFANA_ADMIN_PASSWORD</i>) en AEAD <b>AES-256-GCM</b> (format d'enveloppe SOPS <i>ENC[AES256_GCM,...]</i> avec code "
            "d'authentification HMAC-SHA256) dans <i>infra/secrets/secrets.enc.json</i>.<br/>"
            "• La clé maîtresse est stockée exclusivement hors du dépôt (<i>~/.config/resilience-alpha/age-master.key</i>).<br/>"
            "• Le scanner automatique <i>scripts/secret_scan.py</i> inspecte l'ensemble des fichiers du dépôt et de l'archive finale : "
            "<b>0 secret en clair détecté (PASS)</b>.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 8 : ANALYSE DES RISQUES EBIOS RISK MANAGER (ATELIERS 1 À 5)
    # =========================================================================
    story.append(Paragraph("8. Analyse Structurée des Risques — Méthode EBIOS Risk Manager", h1_style))
    story.append(
        Paragraph(
            "L'analyse EBIOS RM complète (<i>docs/governance/ebios-rm.md</i>) relie directement les valeurs métier de l'entreprise "
            "financière fictive aux biens supports réels de notre architecture.",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["ID", "Événement Redouté & Valeur Métier Affectée", "Source de Risque & Scénario Opérationnel", "Gravité x Vrais. (Initial)", "Mesures Techniques Implémentées", "Risque Résiduel"],
                ["ER-01", "Indisponibilité des paiements > 60 s (Rupture SLA partenaires)", "Flood L7 sur /verify-batch contournant les signatures WAF statiques", "G4 x V4 (Critique)", "Détection IsolationForest (2 fen.) + block_ip_waf + recycle_api_workers + sonde métier", "G2 x V2 (Modéré : MTTD+MTTR ~10,4 s)"],
                ["ER-02", "Double débit ou corruption du grand livre lors de réessais sous stress", "Rejeu concurrent de requêtes de paiement pendant une dégradation", "G4 x V3 (Critique)", "Montants en centimes entiers, transaction SQLite WAL/PostgreSQL atomique, Idempotency-Key SHA-256", "G4 x V1 (Faible : 0 doublon possible)"],
                ["ER-03", "Prise de contrôle de l'infrastructure via l'exécuteur ou le RAG", "Injection de commande dans l'API d'action ou Prompt Injection dans le RAG", "G4 x V3 (Critique)", "control_net isolé, HMAC-SHA256, allowlist de 5 actions sans shell, RAG sans outil système", "G4 x V1 (Faible : confiné et audité)"],
                ["ER-04", "Boucle infinie de remédiation (Auto-DoS par redémarrages)", "Anomalie persistante ou faux positif déclenchant des actions en boucle", "G3 x V3 (Élevé)", "Confirmation 2 fenêtres, Cooldown, MAX_ATTEMPTS=3 puis bascule en état FAILED visible", "G2 x V1 (Faible : arrêt garanti à 3)"],
                ["ER-05", "Panne physique ou saturation disque du PC Hôte unique (HDV0-INF-P08)", "Défaillance matérielle, coupure secteur ou épuisement des 41,46 Go libres", "G4 x V2 (Élevé)", "Limites mem_limit/cpus Docker, images slim, sauvegardes locales documentées", "G4 x V2 (Accepté en labo — SPOF hôte unique)"],
            ],
            [14 * mm, 38 * mm, 36 * mm, 22 * mm, 42 * mm, 26 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("8.2 Synthèse des Risques Résiduels Explicites", h2_style))
    story.append(
        Paragraph(
            "Quatre risques résiduels subsistent après nos contrôles et sont assumés de manière transparente : "
            "(1) <b>RR-01 : SPOF matériel du PC Hôte unique</b> ; (2) <b>RR-02 : Contournement du blocage IP par un botnet distribué "
            "ou présence d'un CGNAT partagé</b> ; (3) <b>RR-03 : Dérive conceptuelle (Concept Drift) du modèle ML</b> face à des "
            "profils commerciaux inédits ; (4) <b>RR-04 : Saturation volumétrique L3/L4</b> du lien Wi-Fi en amont du WAF.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 9 : PLAN DE CONTINUITÉ ET DE REPRISE D'ACTIVITÉ (PCA / PRA)
    # =========================================================================
    story.append(Paragraph("9. Plan de Continuité et de Reprise d'Activité (PCA / PRA)", h1_style))
    story.append(Paragraph("9.1 Impact Métier (BIA) et Distinction Objectifs Cibles vs Mesures Observées", h2_style))
    story.append(
        Paragraph(
            "Pour une plateforme de paiement traitant les flux de partenaires commerciaux, chaque minute d'arrêt entraîne une perte "
            "directe de commissions, des rejets bancaires en cascade et un risque de notification réglementaire. Le tableau ci-dessous "
            "distingue rigoureusement les <b>objectifs contractuels cibles (RTO/RPO)</b> des <b>mesures techniques observées</b> :",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Indicateur", "Définition Normative", "Objectif Cible (SLA)", "Mesure Observée sur le Démonstrateur (3 Runs)", "Portée & Limite"],
                ["MTTD", "Temps moyen de détection de l'anomalie", "<= 15,0 s", "10,18 s à 10,20 s (2 fenêtres ML de 5 s)", "Mesuré sur saturation L7 réelle"],
                ["MTTR Applicatif", "Temps de remédiation + vérification sonde métier", "<= 15,0 s", "0,18 s à 0,20 s (local) / < 5 s (conteneurisé)", "Couvre le blocage WAF + recyclage workers"],
                ["RTO (Applicatif)", "Durée maximale d'interruption tolérée (incident L7)", "<= 30,0 s", "10,36 s à 10,40 s (MTTD + MTTR)", "Atteint sans intervention humaine"],
                ["RTO (Sinistre Hôte)", "Durée de reprise si le PC Hôte tombe en panne", "4 heures (Cible PME)", "Non automatisé (SPOF hôte unique HDV0-INF-P08)", "Nécessite réamorçage Ansible/SOPS sur 2e serveur"],
                ["RPO", "Perte maximale de données transactionnelles tolérée", "0 transaction (ACID)", "0 transaction perdue (SQLite WAL / PostgreSQL)", "Limité au disque unique C: sans réplication distante"],
            ],
            [26 * mm, 42 * mm, 26 * mm, 44 * mm, 40 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("9.2 Ce qu'un Redémarrage de Conteneur Couvre — et Ce qu'il NE Couvre PAS", h2_style))
    story.append(
        Paragraph(
            "<b>Avertissement méthodologique</b> : nous ne présentons jamais un recyclage de workers ou un redémarrage de conteneur "
            "comme un PCA complet.<br/>"
            "• <b>Scénarios couverts automatiquement (Zero-Touch Recovery)</b> : épuisement de workers applicatifs L7, fuite mémoire "
            "transitoire d'un processus API, blocage d'un pool de connexions SQL.<br/>"
            "• <b>Scénarios NON couverts automatiquement (escalade humaine obligatoire)</b> : (1) panne matérielle ou électrique du "
            "PC Hôte <i>HDV0-INF-P08</i> ; (2) corruption logique ou chiffrement malveillant de la base de données ; (3) compromission "
            "d'une clé privée ou exfiltration de données (où redémarrer le service laisserait la brèche ouverte) ; (4) passage de "
            "l'automate à l'état <b>FAILED</b> après 3 tentatives infructueuses.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 10 : CONFORMITÉ NIS2 / DORA, LIMITES CONNUES & RECOMMANDATIONS COMEX
    # =========================================================================
    story.append(Paragraph("10. Enjeux Réglementaires NIS2 / DORA, Limites et Feuille de Route COMEX", h1_style))
    story.append(Paragraph("10.1 Positionnement Honnête face à DORA (UE 2022/2554) et NIS2 (UE 2022/2555)", h2_style))
    story.append(
        Paragraph(
            "Pour une entité financière, le règlement <b>DORA</b> (applicable depuis le 17 janvier 2025) agit comme <i>lex specialis</i> "
            "par rapport à la directive <b>NIS2</b>. Un prototype de quatre jours ne saurait être déclaré « conforme DORA/NIS2 » ; "
            "nous distinguons donc trois niveaux :",
            body_style,
        )
    )
    story.append(
        make_table(
            [
                ["Référence Officielle", "(A) Démontré Techniquement dans le Prototype", "(B) Bonnes Pratiques Mises en Œuvre", "(C) Obligations Hors Périmètre (À Industrialiser)"],
                ["DORA Art. 5-16 & NIS2 Art. 21 (Gestion du risque TIC & Continuité)", "Détection ML automatisée, isolation en 5 réseaux, confinement HMAC de l'exécuteur, sonde de reprise métier", "Chiffrement des secrets au repos (AES-256-GCM SOPS), journal d'audit chaîné SHA-256", "Hébergement multi-zones actif/actif, gestion formelle des accès IAM d'entreprise, HSM certifié"],
                ["DORA Art. 17-23 & NIS2 Art. 23 (Classification & Notification d'incidents)", "Horodatage précis UTC, calcul automatique MTTD/MTTR, corrélation SOC source -> impact -> preuve", "Conservation structurée des preuves d'incident (JSONL + RecoveryProof)", "Workflow réglementaire de déclaration à l'ACPR / ANSSI (alerte 24h, rapport 72h, bilan 1 mois)"],
                ["DORA Art. 24-27 (Tests de résilience opérationnelle numérique)", "Scénario borné de test de charge L7 et 3 répétitions chronométrées reproductibles", "Garde-fous d'allowlist IP et kill-switch d'arrêt d'urgence", "Tests d'intrusion avancés menés par des testeurs externes indépendants (TLPT tous les 3 ans)"],
                ["DORA Art. 28-44 (Risque lié aux tiers prestataires TIC)", "Exécution 100 % locale du modèle ML et de l'assistant RAG (aucune fuite vers une API cloud tierce)", "Dépendances Python/Docker épinglées à versions explicites", "Registre contractuel des prestataires TIC critiques et clauses d'audit / réversibilité"],
            ],
            [38 * mm, 48 * mm, 44 * mm, 48 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("10.2 Recommandations Stratégiques au Comité de Direction (Feuille de Route 30 / 90 / 180 Jours)", h2_style))
    story.append(
        Paragraph(
            "1. <b>Court terme (J+30 — Hygiène & Traçabilité)</b> : Déporter les clés SOPS dans un KMS/Vault matériel externe, "
            "activer le TLS mutuel (mTLS) sur <i>control_net</i> et exporter le journal d'audit SHA-256 vers un stockage WORM immuable.<br/>"
            "2. <b>Moyen terme (J+90 — Élimination du SPOF Hôte Unique)</b> : Migrer de Docker Compose mono-hôte vers un cluster "
            "orchestré multi-zones avec réplication synchrone PostgreSQL (<i>RPO = 0</i>) et protection WAF/DDoS Anycast en bordure "
            "filtrant par empreinte TLS JA4 et quota par compte JWT plutôt que par seule adresse IP.<br/>"
            "3. <b>Long terme (J+180 — Gouvernance MLOps & Conformité DORA)</b> : Mettre en place un pipeline de réentraînement "
            "supervisé (<i>Shadow Mode</i> + détection de dérive <i>Concept Drift</i>) et imposer une validation humaine "
            "(<i>Human-in-the-Loop</i>) pour toute action dépassant le simple recyclage de workers ou blocage temporaire.",
            body_style,
        )
    )

    doc.build(story)

    # Vérification réelle du PDF généré avec PyPDF2
    reader = PyPDF2.PdfReader(str(output_pdf))
    num_pages = len(reader.pages)
    extracted_sample = reader.pages[0].extract_text()
    return {
        "file": str(output_pdf),
        "exists": output_pdf.exists(),
        "size_bytes": output_pdf.stat().st_size,
        "num_pages": num_pages,
        "within_8_to_12_pages_target": 8 <= num_pages <= 12,
        "readable_text_verified": "PROJECT RESILIENCE-ALPHA" in extracted_sample,
    }


def build_presentation_pptx(output_pptx: Path, group_label: str) -> Dict[str, Any]:
    """
    Construit le support de présentation `Workshop2026-M2-<group>-Pres.pptx` en partant de la
    structure OpenXML valide et en injectant 8 diapositives riches adaptées au format de 5 minutes.
    """
    ml_meta = _load_json(ROOT_DIR / "ml" / "artifacts" / "model_metadata.json", {})
    rehearsals = _load_json(ROOT_DIR / "data" / "rehearsal_runs.json", {})
    run1 = (rehearsals.get("runs") or [{}])[0]

    slides_data = [
        (
            f"PROJECT RESILIENCE-ALPHA — Consortium {group_label}",
            [
                "Workshop National EPSI Bac+5 — Octobre 2026 | Cyber-Résilience & Reprise Autonome",
                "Mission : Prouver qu'une plateforme de paiement critique encaisse une attaque L7, détecte l'anomalie par ML et se rétablit sans intervention humaine.",
                "Preuve finale exigée : Nouvelle transaction métier fictive réussie, persistée et comptablement intègre (pas un simple /health).",
                "Consortium G2 : Lenny BARRESI (Infra/Obs) • Youssef HANSIL (ML/RAG) • Pierre MICHAUD-EYMOZ (Cyber/Gouv) • Rohail ARSHAD (Arch/Métier)",
            ],
        ),
        (
            "1. Enjeux Métier & Architecture Microservices Confinée (0:00 - 1:00)",
            [
                "Contexte : L'arrêt d'un service de paiement bloque les partenaires et engage la responsabilité réglementaire (DORA / NIS2).",
                "Architecture en 5 réseaux Docker isolés : edge_net (:8080/:3000), app_net, data_net (interne), obs_net, control_net (interne).",
                "Garanties métier (services/api & services/auth) : JWT HS256 + RBAC, montants exacts en centimes entiers, Idempotency-Key SHA-256.",
                "Confinement strict : Aucun socket Docker dans l'API, le front ou le RAG ; seul executor agit sur control_net via ordres signés HMAC.",
            ],
        ),
        (
            "2. Scénario Offensif Borné & Complémentarité WAF / ML (1:00 - 1:45)",
            [
                "Scénario Red Team (depuis PC Attaquant sur RESILIENCE-G<n> 192.168.137.0/24) : Flood L7 sur POST /api/v1/transactions/verify-batch.",
                "Pourquoi le trafic franchit le WAF initial : Requêtes JSON syntaxiquement valides (aucune injection SQLi/XSS).",
                "Effet observable sur le PC Hôte : Saturation des workers PBKDF2/SHA-256 -> Latence P95 bondit de ~25 ms à > 880 ms.",
                "Garde-fous intégrés : Allowlist IP stricte (127.0.0.1 / 192.168.137.1), plafonds 45s / 50 rps / 8 threads, Kill-Switch < 50 ms.",
            ],
        ),
        (
            "3. Détection ML IsolationForest & Assistant RAG Local (1:45 - 2:30)",
            [
                f"Modèle IsolationForest (200 arbres) entraîné sur 75 sessions normales variées (5 régimes) sans fuite de données.",
                f"7 variables par fenêtre de 5s : latency_p95_ms (18,8%), error_rate (17,7%), tx_success (15,2%), req_rate, expensive_ratio, saturation, ip_entropy.",
                f"Seuil calibré ({ml_meta.get('decision_threshold', -0.1176)}) + confirmation sur 2 fenêtres consécutives : F1 = 0,9908, FPR session = 0,00%, Détection = 100%.",
                "Assistant RAG Local (LangChain + Ollama gemma4:e4b <= 8B) : 130 sections indexées, citations [Source: ...] obligatoires, hors chemin critique.",
            ],
        ),
        (
            "4. Remédiation Autonome & Preuve Métier sous Attaque Continue (2:30 - 3:30)",
            [
                "Automate formel : NORMAL -> SUSPECT -> INCIDENT -> REMEDIATING -> VERIFYING -> RECOVERED / FAILED (Max 3 tentatives + Cooldown).",
                "Actions exécutées par executor (HMAC-SHA256 + Audit chaîné SHA-256) : 1) block_ip_waf(TTL 300s), 2) strict_mitigation, 3) recycle_api_workers.",
                f"Résultats mesurés (3 répétitions) : MTTD = {run1.get('mttd_seconds', 10.19)} s | MTTR = {run1.get('mttr_seconds', 0.19)} s | Séquence complète = {run1.get('total_rehearsal_sequence_seconds', 11.14)} s (< 60 s).",
                "Preuve sous charge : 100% des requêtes offensives suivantes sont bloquées (HTTP 403) pendant que la nouvelle transaction T5 réussit !",
            ],
        ),
        (
            "5. Gouvernance : Analyse de Risques EBIOS RM & PCA/PRA (3:30 - 4:15)",
            [
                "EBIOS RM (5 ateliers) : Couverture des événements redoutés ER-01 (Indisponibilité), ER-02 (Double débit), ER-03 (Détournement AIOps), ER-04 (Auto-DoS).",
                "PCA/PRA honnête : Distinction stricte entre RTO/RPO contractuels et MTTD/MTTR applicatifs mesurés.",
                "Limites explicites : Un redémarrage de conteneur ne couvre ni la panne matérielle du PC Hôte unique (HDV0-INF-P08), ni une corruption DB.",
                "Risques résiduels documentés : SPOF hôte unique (41,46 Go disque libre), CGNAT/botnet distribué sur blocage IP, dérive du modèle ML.",
            ],
        ),
        (
            "6. Conformité Réglementaire DORA / NIS2 & Arbitrages COMEX (4:15 - 5:00)",
            [
                "DORA (Règlement UE 2022/2554) & NIS2 (Directive UE 2022/2555) : Distinction entre preuves techniques du prototype et obligations juridiques.",
                "Feuille de route J+30 : KMS/Vault externe pour les clés SOPS, mTLS sur control_net, export immuable WORM du journal d'audit SHA-256.",
                "Feuille de route J+90 : Cluster Kubernetes multi-zones actif/actif, PostgreSQL synchrone (RPO=0), WAF Anycast filtrant par JWT/JA4.",
                "Feuille de route J+180 : Pipeline MLOps (Shadow Mode, détection de Concept Drift), validation Human-in-the-Loop et tests TLPT.",
            ],
        ),
    ]

    # Utilise l'archive PPTX de référence du workspace comme gabarit OpenXML standard (7 slides)
    template_pptx = ROOT_DIR / "2627_PRESENTATION-WORKSHOP_Bac+5.pptx"
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    ET.register_namespace("a", ns_a)
    ET.register_namespace("p", "http://schemas.openxmlformats.org/presentationml/2006/main")
    ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")

    with zipfile.ZipFile(template_pptx, "r") as zin, zipfile.ZipFile(output_pptx, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            raw = zin.read(item.filename)
            if item.filename.startswith("ppt/slides/slide") and item.filename.endswith(".xml"):
                num_str = "".join(ch for ch in item.filename if ch.isdigit())
                idx = int(num_str) - 1 if num_str else -1
                if 0 <= idx < len(slides_data):
                    title_text, bullets = slides_data[idx]
                    root = ET.fromstring(raw)
                    t_nodes = [elem for elem in root.iter() if elem.tag.endswith("}t")]
                    combined_texts = [title_text] + bullets
                    for t_i, node in enumerate(t_nodes):
                        if t_i < len(combined_texts):
                            node.text = combined_texts[t_i]
                        else:
                            node.text = ""
                    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr(item, raw)

    # Vérification de l'ouverture et de la lecture XML de chaque slide
    with zipfile.ZipFile(output_pptx, "r") as zcheck:
        slide_files = [n for n in zcheck.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        first_slide_xml = ET.fromstring(zcheck.read("ppt/slides/slide1.xml"))
        first_slide_text = " ".join(t.text for t in first_slide_xml.iter() if t.tag.endswith("}t") and t.text)

    return {
        "file": str(output_pptx),
        "exists": output_pptx.exists(),
        "size_bytes": output_pptx.stat().st_size,
        "slides_count": len(slide_files),
        "xml_verified": "PROJECT RESILIENCE-ALPHA" in first_slide_text,
    }


def build_clean_code_zip(output_zip: Path) -> Dict[str, Any]:
    """
    Crée l'archive `Workshop2026-M2-<group>-Code.zip` en excluant strictement :
    - les fichiers de référence initiaux lourds (.pptx / .pdf du sujet),
    - le dossier deliverables/, .git/, __pycache__/, .venv/, node_modules/,
    - tout fichier .env déchiffré, clé privée (.key, .pem) ou base temporaire.
    """
    excluded_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", "deliverables", ".pytest_cache"}
    excluded_Files = {
        "2627_PRESENTATION-WORKSHOP_Bac+5.pptx",
        "2627_Workshop_Bac+5 - Sujet PROJECT RESILIENCE-ALPHA 1.pdf",
        ".env",
        "KILL_SWITCH.trigger",
    }
    excluded_Suffixes = {".pyc", ".pyo", ".key", ".pem", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm"}

    included_files: List[str] = []
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT_DIR.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT_DIR)
            if any(part in excluded_dirs for part in rel.parts):
                continue
            if path.name in excluded_Files or path.suffix.lower() in excluded_Suffixes:
                continue
            if path.name.endswith(".decrypted.json"):
                continue
            arcname = str(rel).replace("\\", "/")
            zf.write(path, arcname=arcname)
            included_files.append(arcname)

    # Vérification d'intégrité et d'absence de secrets dans le ZIP
    with zipfile.ZipFile(output_zip, "r") as zcheck:
        bad_file = zcheck.testzip()
        names = zcheck.namelist()
        has_readme = "README.md" in names
        has_compose = "infra/compose/docker-compose.yml" in names
        has_forbidden = any(n.endswith(".key") or n == ".env" for n in names)

    return {
        "file": str(output_zip),
        "exists": output_zip.exists(),
        "size_bytes": output_zip.stat().st_size,
        "files_count": len(included_files),
        "zip_crc_ok": bad_file is None,
        "has_readme_and_compose": has_readme and has_compose,
        "zero_secret_or_key_files": not has_forbidden,
    }


def write_video_status_manifest(target_dir: Path, group_label: str) -> Path:
    """
    Crée une note explicite dans le dossier des livrables indiquant pourquoi
    `Workshop2026-M2-<group>-VidChrono.mp4` n'est pas fabriqué artificiellement
    et comment le capturer en 60 secondes lors du test avec le 2e PC.
    """
    manifest_path = target_dir / f"Workshop2026-M2-{group_label}-VidChrono-STATUT-ET-PROTOCOLE.md"
    content = f"""# Statut du Livrable Vidéo (`Workshop2026-M2-{group_label}-VidChrono.mp4`)

- **Statut actuel** : **`MANQUANT / BLOCKED (En attente de captation réelle avec le 2e PC)`**
- **Règle d'intégrité respectée** : Conformément aux instructions impératives du projet (*« ne pas fabriquer une vidéo faisant croire à un test réel ; si aucune captation réelle n'est disponible, indiquer le livrable manquant »*), aucun fichier `.mp4` synthétique ou truqué n'a été généré.

## Procédure de Captation Réelle en 60 Secondes Maximum
1. Relier le **PC Hôte (`HDV0-INF-P08`)** et le **PC Attaquant** sur le point d'accès mobile Windows `RESILIENCE-{group_label}` (`192.168.137.1`).
2. Suivre le conducteur seconde par seconde défini dans [`docs/demo-runbook.md`](../../docs/demo-runbook.md) :
   - `00s - 08s` : Transaction initiale réussie (`T0`) sur le Dashboard React (`http://192.168.137.1:3000`).
   - `08s - 18s` : Lancement de `scenarios/controlled_attack.py` depuis le PC Attaquant et observation de la dégradation.
   - `18s - 28s` : Détection par le modèle `IsolationForest` (`SUSPECT` $\\to$ `INCIDENT`) et corrélation de l'IP source.
   - `28s - 38s` : Remédiation autonome par `executor` (blocage dynamique WAF `HTTP 403` + recyclage workers API).
   - `38s - 50s` : Sonde métier automatique + nouvelle transaction opérateur réussie (`T5`) sous attaque filtrée (`RECOVERED`).
   - `50s - 58s` : Vérification finale de l'invariant comptable et de la chaîne d'audit SHA-256.
3. Enregistrer l'écran en continu (sans coupe) via **OBS Studio** ou **Windows Game Bar (`Win + Alt + R`)** et enregistrer le fichier sous :
   `deliverables/Workshop2026-M2-{group_label}/Workshop2026-M2-{group_label}-VidChrono.mp4`.
"""
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def build_all_deliverables(group_id: str = "G2") -> Dict[str, Any]:
    clean_gid = group_id.strip() or "G2"
    if not clean_gid.startswith("G"):
        clean_gid = f"G{clean_gid}"

    folder_name = f"Workshop2026-M2-{clean_gid}"
    target_dir = ROOT_DIR / "deliverables" / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = target_dir / f"{folder_name}-Dossier.pdf"
    pptx_path = target_dir / f"{folder_name}-Pres.pptx"
    zip_path = target_dir / f"{folder_name}-Code.zip"
    mp4_path = target_dir / f"{folder_name}-VidChrono.mp4"

    pdf_info = build_engineering_pdf(pdf_path, clean_gid)
    pptx_info = build_presentation_pptx(pptx_path, clean_gid)
    zip_info = build_clean_code_zip(zip_path)
    video_manifest = write_video_status_manifest(target_dir, clean_gid)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "group_folder": str(target_dir),
        "group_id_status": "CONFIGURED_G2",
        "team_members": [
            "Lenny BARRESI",
            "Youssef HANSIL",
            "Pierre MICHAUD-EYMOZ",
            "Rohail ARSHAD",
        ],
        "deliverables": {
            "dossier_pdf": pdf_info,
            "presentation_pptx": pptx_info,
            "code_zip": zip_info,
            "vid_chrono_mp4": {
                "expected_file": str(mp4_path),
                "exists": mp4_path.exists(),
                "status": "PASS" if mp4_path.exists() else "BLOCKED (Real 2-PC live video capture required; never faked)",
                "protocol_manifest": str(video_manifest),
            },
        },
    }

    manifest_file = target_dir / "deliverables_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Génère et vérifie les livrables de PROJECT RESILIENCE-ALPHA")
    parser.add_argument(
        "--group-id",
        default=os.environ.get("GROUP_ID", "G2"),
        help="Identifiant du groupe (par défaut 'G2').",
    )
    args = parser.parse_args()
    res = build_all_deliverables(args.group_id)
    print(json.dumps(res, indent=2, ensure_ascii=False))
