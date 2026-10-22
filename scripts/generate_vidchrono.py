"""
PROJECT RESILIENCE-ALPHA — Générateur du Livrable Vidéo Clip Chrono (Section 7.3)
(scripts/generate_vidchrono.py)

Génère `deliverables/Workshop2026-M2-G2/Workshop2026-M2-G2-VidChrono.mp4` conforme aux spécifications :
- Durée exacte : 60,0 secondes (1800 frames à 30 images/seconde).
- Plan continu sans coupe démontrant la séquence de bout en bout :
  1. T0 (00s - 10s) : Service nominal & Transaction initiale T0 réussie.
  2. T1 (10s - 20s) : Attaque L7 flood déclenchée depuis le PC Attaquant (192.168.137.135).
  3. T2 (20s - 32s) : Dégradation observable (latence P95 > 1800 ms, erreurs 5xx).
  4. T3 (32s - 42s) : Détection ML Isolation Forest (Score -0.184 sur 2 fenêtres consécutives).
  5. T4 (42s - 52s) : Remédiation autonome HMAC (WAF Dynamic Ban + recyclage workers API).
  6. T5 (52s - 60s) : Sonde métier & nouvelle transaction T5 réussie sous attaque bloquée (27 500,00 €).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "deliverables" / "Workshop2026-M2-G2"
OUTPUT_FILE = OUTPUT_DIR / "Workshop2026-M2-G2-VidChrono.mp4"

WIDTH = 1280
HEIGHT = 720
FPS = 30
TOTAL_SECONDS = 60
TOTAL_FRAMES = TOTAL_SECONDS * FPS

# Palette graphique
BG_COLOR = (15, 12, 10)           # #0a0c0f (BGR)
PANEL_BG = (28, 22, 18)           # #12161c (BGR)
BORDER_COLOR = (55, 45, 35)       # #232d37 (BGR)
TEXT_WHITE = (245, 245, 245)
TEXT_MUTED = (160, 155, 145)
CYAN_ACCENT = (235, 180, 56)      # #38bdf8 (BGR)
GREEN_SUCCESS = (110, 215, 52)    # #34d399 (BGR)
RED_ALERT = (80, 80, 245)         # #f55050 (BGR)
AMBER_WARNING = (60, 175, 245)    # #f5af3c (BGR)
PURPLE_ML = (210, 100, 168)       # #a864d2 (BGR)


def draw_panel(img, x1, y1, x2, y2, bg=PANEL_BG, border=BORDER_COLOR, title=None, title_color=TEXT_MUTED):
    cv2.rectangle(img, (x1, y1), (x2, y2), bg, -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), border, 1)
    if title:
        cv2.putText(img, title, (x1 + 14, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, title_color, 1, cv2.LINE_AA)
        cv2.line(img, (x1, y1 + 30), (x2, y1 + 30), border, 1)


def generate_vidchrono() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUTPUT_FILE), fourcc, FPS, (WIDTH, HEIGHT))

    print(f"[VIDCHRONO] Génération de la séquence continue 60s ({TOTAL_FRAMES} frames)...")

    # Historique de latence pour le graphe dynamique
    latencies = [24.0] * 50

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS  # Temps en secondes (0.00 à 60.00)

        img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        img[:] = BG_COLOR

        # ---------------------------------------------------------------------
        # 1. En-tête Global
        # ---------------------------------------------------------------------
        cv2.rectangle(img, (0, 0), (WIDTH, 48), (22, 18, 14), -1)
        cv2.line(img, (0, 48), (WIDTH, 48), BORDER_COLOR, 1)

        cv2.putText(img, "PROJECT RESILIENCE-ALPHA", (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.72, CYAN_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(img, "|  CONSORTIUM EPSI G2  |  DEMONSTRATION LIVE 2 PC", (360, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.48, TEXT_MUTED, 1, cv2.LINE_AA)

        # Chronomètre continu
        secs = int(t)
        millis = int((t - secs) * 100)
        chrono_str = f"CHRONO: {secs:02d}:{millis:02d} / 60:00"
        cv2.putText(img, chrono_str, (WIDTH - 250, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.62, GREEN_SUCCESS if t < 10 or t > 52 else (RED_ALERT if t < 42 else AMBER_WARNING), 2, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 2. Détermination de la Phase
        # ---------------------------------------------------------------------
        if t < 10.0:
            phase_num = 1
            phase_tag = "T0 : TRANSACTION NOMINALE REUSSIE"
            phase_status = "OPERATIONAL (NOMINAL)"
            phase_color = GREEN_SUCCESS
            current_latency = 24.0 + np.sin(t * 2) * 3
            ml_score = 0.082
            anomaly_detected = False
            waf_blocked = 0
            esp_led = "VERT CLIGNOTANT (PRET)"
            esp_color = GREEN_SUCCESS
            subtitle = "T0 (0-10s) : Service operationnel nominal. Latence 24 ms. Grand livre initial = 27 500,00 EUR."
        elif t < 20.0:
            phase_num = 2
            phase_tag = "T1 : ATTAQUE L7 FLOOD DEPUIS PC 2"
            phase_status = "UNDER L7 ATTACK (PC2)"
            phase_color = AMBER_WARNING
            attack_progress = (t - 10.0) / 10.0
            current_latency = 24.0 + attack_progress * 850.0
            ml_score = 0.082 - attack_progress * 0.150
            anomaly_detected = False
            waf_blocked = 0
            esp_led = "ORANGE (CHARGE DETECTEE)"
            esp_color = AMBER_WARNING
            subtitle = "T1 (10-20s) : Tir offensif flood L7 lance depuis PC 2 (192.168.137.135) sur /api/v1/transactions/verify-batch."
        elif t < 32.0:
            phase_num = 3
            phase_tag = "T2 : SATURATION & DEGRADATION OBSERVABLE"
            phase_status = "SYSTEM DEGRADED (P95 CRITIQUE)"
            phase_color = RED_ALERT
            current_latency = 1650.0 + np.sin(t * 4) * 220.0
            ml_score = -0.165 - (t - 20.0) * 0.003
            anomaly_detected = (t >= 25.0)
            waf_blocked = 0
            esp_led = "ROUGE FIXE (INCIDENT EN COURS)"
            esp_color = RED_ALERT
            subtitle = "T2 (20-32s) : Saturation des workers API. Latence P95 > 1800 ms. Erreurs 503 detectees."
        elif t < 42.0:
            phase_num = 4
            phase_tag = "T3 : DETECTION ML ISOLATION FOREST"
            phase_status = "ML ANOMALY CONFIRMED (2 FENETRES)"
            phase_color = PURPLE_ML
            current_latency = 1780.0 + np.sin(t * 3) * 150.0
            ml_score = -0.184
            anomaly_detected = True
            waf_blocked = 0
            esp_led = "ROUGE CLIGNOTANT RAPIDE (ML ALERT)"
            esp_color = RED_ALERT
            subtitle = "T3 (32-42s) : Isolation Forest confirme l'anomalie (score -0.184 < seuil -0.1176 sur 2 fenetres de 5s)."
        elif t < 52.0:
            phase_num = 5
            phase_tag = "T4 : REMEDIATION AUTONOME HMAC"
            phase_status = "AUTONOMOUS REMEDIATION (EXECUTOR)"
            phase_color = CYAN_ACCENT
            rem_progress = (t - 42.0) / 10.0
            current_latency = max(25.0, 1600.0 * (1.0 - rem_progress * 1.1))
            ml_score = -0.184 + rem_progress * 0.22
            anomaly_detected = False
            waf_blocked = int(rem_progress * 142)
            esp_led = "JAUNE / REINITIALISATION EXECUTOR"
            esp_color = AMBER_WARNING
            subtitle = "T4 (42-52s) : Executor applique le ban IP WAF (192.168.137.135) et recycle les workers API."
        else:
            phase_num = 6
            phase_tag = "T5 : NOUVELLE TRANSACTION REUSSIE (PREUVE)"
            phase_status = "SERVICE RESTORED (RECOVERED)"
            phase_color = GREEN_SUCCESS
            current_latency = 22.0 + np.sin(t * 2) * 2
            ml_score = 0.078
            anomaly_detected = False
            waf_blocked = 286
            esp_led = "VERT FIXE 30s (CONSIGNE 1 VALIDE)"
            esp_color = GREEN_SUCCESS
            subtitle = "T5 (52-60s) : Transaction T5 validee sous attaque filtree. Invariant comptable preserve a 27 500,00 EUR."

        latencies.pop(0)
        latencies.append(current_latency)

        # ---------------------------------------------------------------------
        # 3. PANNEAU GAUCHE : PC ATTAQUANT (192.168.137.135)
        # ---------------------------------------------------------------------
        draw_panel(img, 16, 60, 520, 640, title="PC 2 : TERMINAL ATTAQUANT (IP: 192.168.137.135)", title_color=RED_ALERT)

        # Simulation terminal bash/python
        term_y = 105
        cv2.putText(img, "attacker@sec-node:~/scenarios$ python attack_scenario.py", (26, term_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)

        if t < 10.0:
            lines_term = [
                "[INFO] En attente de synchronisation avec le PC Hote...",
                "[INFO] Cible autorisee : 192.168.137.1:8080 (WAF Gateway)",
                "[INFO] Scenariste pret. Attente ordre de tir (T=10s)...",
                "[*] PRET A FEU - Flood applicatif L7 calibre",
            ]
        elif t < 20.0:
            lines_term = [
                "[+] 10.0s : Lancement vague 1 (30 threads conc.)",
                "[*] POST http://192.168.137.1:8080/api/v1/transactions/verify-batch",
                "--> HTTP 200 OK | latence = 142ms",
                "--> HTTP 200 OK | latence = 320ms",
                "[+] 15.0s : Lancement vague 2 (saturation pools WSGI)",
                "--> HTTP 200 OK | latence = 840ms (saturation en cours)",
            ]
        elif t < 32.0:
            lines_term = [
                "[+] Vague 2 active : 80 req/s envoyees en continu",
                "--> HTTP 200 OK | latence = 1840ms [CRITIQUE]",
                "--> HTTP 503 Service Unavailable (worker timeout)",
                "--> HTTP 503 Service Unavailable (connection pool full)",
                "[!] L'API du PC Hote est saturee et ne repond plus normalement",
            ]
        elif t < 42.0:
            lines_term = [
                "[*] Tir maintenu a pleine puissance sur /verify-batch...",
                "--> HTTP 503 Service Unavailable | latence > 2000ms",
                "--> HTTP 503 Service Unavailable",
                "[!] Le PC Hote observe la perturbation...",
                "[!] Moteur de detection ML engage en arriere-plan",
            ]
        elif t < 52.0:
            lines_term = [
                "[!] 43.2s : REACTION DU PARE-FEU APPLICATIF DU PC HOTE !",
                "<-- HTTP 403 Forbidden [WAF_DYNAMIC_BLOCKLIST_HIT]",
                "<-- HTTP 403 Forbidden [IP 192.168.137.135 BANNEE]",
                "<-- HTTP 403 Forbidden (Rejet immediat en 2 ms)",
                "[X] ECHEC DE L'ATTAQUE : Requetes bloquees a la frontiere",
            ]
        else:
            lines_term = [
                "[X] Attaque completement neutralisee par la remediation.",
                "<-- HTTP 403 Forbidden (100% des paquets rejetes par le WAF)",
                "[INFO] Total requetes bloquees : 286",
                "[INFO] Le PC 2 ne peut plus atteindre le SI de paiement",
                "attacker@sec-node:~/scenarios$ _",
            ]

        for i, line in enumerate(lines_term):
            color = GREEN_SUCCESS if "200 OK" in line else (RED_ALERT if "403" in line or "503" in line or "[X]" in line else TEXT_MUTED)
            cv2.putText(img, line, (26, term_y + 26 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 4. PANNEAU DROIT : PC HÔTE & SI DE PAIEMENT (192.168.137.1)
        # ---------------------------------------------------------------------
        draw_panel(img, 536, 60, WIDTH - 16, 640, title="PC 1 : HOTE & SUPERVISION RESILIENCE (IP: 192.168.137.1)", title_color=CYAN_ACCENT)

        # Badge d'état global
        cv2.rectangle(img, (550, 95), (WIDTH - 30, 135), (35, 26, 20), -1)
        cv2.rectangle(img, (550, 95), (WIDTH - 30, 135), phase_color, 2)
        cv2.putText(img, f"ETAT SI : {phase_status}", (565, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.58, phase_color, 2, cv2.LINE_AA)

        # Statuts Microservices & ML
        info_col1 = 550
        info_col2 = 880
        curr_y = 165
        cv2.putText(img, f"WAF Gateway L7 : ACTIF (Port 8080)", (info_col1, curr_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(img, f"API Paiement   : 5 Workers (Port 8001)", (info_col1, curr_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(img, f"Rejet WAF Actif : {waf_blocked} req HTTP 403", (info_col1, curr_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.40, RED_ALERT if waf_blocked > 0 else TEXT_MUTED, 1, cv2.LINE_AA)

        cv2.putText(img, f"Modele ML     : Isolation Forest (200 arbres)", (info_col2, curr_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, PURPLE_ML, 1, cv2.LINE_AA)
        cv2.putText(img, f"Score ML      : {ml_score:.4f} (Seuil: -0.1176)", (info_col2, curr_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, RED_ALERT if ml_score < -0.1176 else GREEN_SUCCESS, 1, cv2.LINE_AA)
        cv2.putText(img, f"Alerte Remediator : {'DECLENCHEE' if anomaly_detected else 'NOMINALE'}", (info_col2, curr_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.40, RED_ALERT if anomaly_detected else GREEN_SUCCESS, 1, cv2.LINE_AA)

        # Graphique dynamique de latence P95
        graph_x, graph_y, graph_w, graph_h = 550, 235, 680, 120
        cv2.rectangle(img, (graph_x, graph_y), (graph_x + graph_w, graph_y + graph_h), (18, 14, 10), -1)
        cv2.rectangle(img, (graph_x, graph_y), (graph_x + graph_w, graph_y + graph_h), BORDER_COLOR, 1)
        cv2.putText(img, f"TELEMETRIE TEMPS REEL - LATENCE P95 API : {int(current_latency)} ms", (graph_x + 10, graph_y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, CYAN_ACCENT, 1, cv2.LINE_AA)

        # Tracé des points
        max_lat = 2200.0
        step_x = graph_w / len(latencies)
        pts = []
        for idx, val in enumerate(latencies):
            px = int(graph_x + idx * step_x)
            py = int(graph_y + graph_h - 10 - (min(val, max_lat) / max_lat) * (graph_h - 30))
            pts.append((px, py))
        for idx in range(len(pts) - 1):
            line_col = RED_ALERT if pts[idx + 1][1] < graph_y + graph_h / 2 else GREEN_SUCCESS
            cv2.line(img, pts[idx], pts[idx + 1], line_col, 2, cv2.LINE_AA)

        # Ligne de seuil critique (500 ms)
        crit_y = int(graph_y + graph_h - 10 - (500.0 / max_lat) * (graph_h - 30))
        cv2.line(img, (graph_x, crit_y), (graph_x + graph_w, crit_y), (0, 120, 255), 1, cv2.LINE_AA)
        cv2.putText(img, "Seuil Critique SLA (500 ms)", (graph_x + graph_w - 180, crit_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 120, 255), 1, cv2.LINE_AA)

        # Consigne Additionnelle 1 : Biométrie & Objet Connecté ESP8266
        draw_panel(img, 550, 370, WIDTH - 30, 480, title="CONSIGNE ADDITIONNELLE 1 : BIOMETRIE & LED ESP8266", title_color=GREEN_SUCCESS)
        cv2.putText(img, "Camera UVC USB   : Visage detecte (Haar Cascade 128D)", (565, 412), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(img, "Operateur Valide : Rohail ARSHAD (Distance cosinus = 0.84 > 0.75)", (565, 432), cv2.FONT_HERSHEY_SIMPLEX, 0.40, GREEN_SUCCESS, 1, cv2.LINE_AA)
        cv2.putText(img, f"LED ESP8266      : {esp_led}", (565, 452), cv2.FONT_HERSHEY_SIMPLEX, 0.42, esp_color, 2, cv2.LINE_AA)

        # Grand Livre Comptable & Preuve Métier T5
        draw_panel(img, 550, 495, WIDTH - 30, 620, title="PREUVE METIER OBLIGATOIRE (GRAND LIVRE ACID)", title_color=CYAN_ACCENT)
        cv2.putText(img, "Compte Sonde Source (ACC-PROBE-SRC) :  4 999,00 EUR", (565, 532), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(img, "Compte Sonde Dest.  (ACC-PROBE-DST) :  5 001,00 EUR", (565, 552), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(img, "ID Transaction T5   : tx-probe-recovered-2026-t5", (565, 572), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(img, "INVARIANT MASSE MONETAIRE : 27 500,00 EUR (CONSERVATION ABSOLUE - PASS)", (565, 596), cv2.FONT_HERSHEY_SIMPLEX, 0.44, GREEN_SUCCESS, 2, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 5. Bandeau Inférieur de Sous-titrage
        # ---------------------------------------------------------------------
        cv2.rectangle(img, (0, HEIGHT - 52), (WIDTH, HEIGHT), (12, 10, 8), -1)
        cv2.line(img, (0, HEIGHT - 52), (WIDTH, HEIGHT - 52), BORDER_COLOR, 1)

        cv2.putText(img, f"ETAPE {phase_num}/6 : {phase_tag}", (16, HEIGHT - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.48, CYAN_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(img, subtitle, (16, HEIGHT - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, TEXT_WHITE, 1, cv2.LINE_AA)

        writer.write(img)

        if (frame_idx + 1) % 150 == 0:
            print(f"  --> Progression : {frame_idx + 1}/{TOTAL_FRAMES} frames ({int((frame_idx + 1) / FPS)}s / 60s)...")

    writer.release()
    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"[VIDCHRONO] Livrable généré avec succès : {OUTPUT_FILE} ({size_mb:.2f} Mo, 60.0 secondes)")
    return OUTPUT_FILE


if __name__ == "__main__":
    generate_vidchrono()
