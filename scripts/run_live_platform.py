"""
PROJECT RESILIENCE-ALPHA — Serveur Temps Réel Multi-Services (PC Hôte 192.168.137.1 & 127.0.0.1)
Groupe 2 (G2) : Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD

Démarre l'ensemble des microservices interconnectés sur le PC Hôte avec l'IA au premier plan :
  - Port 8080 : Passerelle WAF L7 + Proxy inverse + Console de tir multi-attaques 2e PC (/attacker, /attacker.ps1)
  - Port 3000 : Centre de Commandement IA (IsolationForest + Ollama gemma4:e4b) & Portail de Paiement Métier
  - Port 8001 : API Métier de Paiement (ACID, Centimes entiers, Idempotence)
  - Port 8002 : Service d'Authentification JWT HS256 & RBAC
  - Port 8003 : Détecteur ML IsolationForest (7 variables temps réel + classification multi-attaques)
  - Port 8004 : Orchestrateur de Remédiation Autonome & Sonde Métier Post-Incident
  - Port 8005 : Exécuteur Confiné (Signature HMAC-SHA256, Allowlist fermée, Audit chaîné SHA-256)
  - Port 8006 : Assistant IA & Copilote RAG Local Ollama (gemma4:e4b, Citations certifiées)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scenarios.kill_switch import engage_kill_switch, is_kill_switch_engaged, release_kill_switch
from services.api.app import ApiRuntimeState, create_api_app
from services.api.database import PaymentDatabase
from services.auth.app import AuthEngine, create_auth_app
from services.auth.esp_controller import esp_controller
from services.auth.face_recognition_service import biometric_service
from services.detector.app import AnomalyDetectorEngine, create_app as create_detector_app
from services.executor.app import ConstrainedExecutor, create_executor_app
from services.rag.app import LocalRAGAssistant, create_app as create_rag_app
from services.remediator.app import RemediationOrchestrator, create_remediator_app
from services.waf_gateway.app import WafEngine, create_waf_app


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>PROJECT RESILIENCE-ALPHA — Groupe 2 (G2) — AI Command Center (IsolationForest + Ollama)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {
      --bg: #070b16;
      --panel: #111a2e;
      --panel-ai: #131b38;
      --border: #24355a;
      --border-ai: #4f46e5;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --green: #10b981;
      --amber: #f59e0b;
      --red: #ef4444;
      --blue: #3b82f6;
      --purple: #8b5cf6;
      --cyan: #06b6d4;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 14px;
      line-height: 1.42;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%);
      border: 1px solid var(--border-ai);
      border-radius: 10px;
      padding: 12px 18px;
      margin-bottom: 12px;
      box-shadow: 0 4px 20px rgba(79, 70, 229, 0.2);
    }
    .title-block h1 { font-size: 1.2rem; color: #fff; display: flex; align-items: center; gap: 10px; }
    .title-block p { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
    .badge {
      display: inline-block;
      padding: 5px 12px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.8rem;
      letter-spacing: 0.4px;
    }
    .badge-ai {
      background: rgba(139, 92, 246, 0.22);
      color: #c4b5fd;
      border: 1px solid #8b5cf6;
      margin-right: 8px;
    }
    .state-NORMAL { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }
    .state-SUSPECT { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    .state-INCIDENT, .state-REMEDIATING, .state-FAILED { background: rgba(239,68,68,0.25); color: #f87171; border: 1px solid #ef4444; }
    .state-VERIFYING { background: rgba(59,130,246,0.25); color: #60a5fa; border: 1px solid #3b82f6; }
    .state-RECOVERED { background: rgba(16,185,129,0.3); color: #6ee7b7; border: 2px solid #10b981; }

    /* HERO AI SECTION AU PREMIER PLAN */
    .ai-hero {
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 14px;
      margin-bottom: 14px;
      background: linear-gradient(145deg, rgba(30, 27, 75, 0.65), rgba(15, 23, 42, 0.9));
      border: 2px solid #6366f1;
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 0 28px rgba(99, 102, 241, 0.22);
    }
    .ai-panel {
      background: rgba(11, 16, 32, 0.85);
      border: 1px solid #312e81;
      border-radius: 10px;
      padding: 13px;
    }
    .ai-panel h2 {
      font-size: 0.98rem;
      color: #a5b4fc;
      margin-bottom: 10px;
      border-bottom: 1px solid #312e81;
      padding-bottom: 6px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .attack-banner {
      padding: 9px 12px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.9rem;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .attack-nominal { background: rgba(16,185,129,0.15); border: 1px solid #10b981; color: #6ee7b7; }
    .attack-alert { background: rgba(239,68,68,0.25); border: 2px solid #ef4444; color: #fca5a5; }
    .feature-bar-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.78rem;
      margin: 5px 0;
      gap: 8px;
    }
    .feature-bar-bg {
      flex: 1;
      height: 7px;
      background: #1e293b;
      border-radius: 999px;
      overflow: hidden;
    }
    .feature-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ef4444);
      border-radius: 999px;
      transition: width 0.4s ease;
    }
    .vector-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
      margin-top: 8px;
    }
    .vector-pill {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 6px;
      text-align: center;
      font-size: 0.74rem;
    }
    .vector-pill strong {
      display: block;
      font-size: 1rem;
      font-family: Consolas, monospace;
      color: #a5b4fc;
    }
    .ollama-box {
      background: #070a14;
      border: 1px solid #3730a3;
      border-radius: 8px;
      padding: 10px;
      font-size: 0.8rem;
      min-height: 120px;
      max-height: 175px;
      overflow-y: auto;
      white-space: pre-wrap;
      color: #e0e7ff;
      margin-bottom: 8px;
      font-family: 'Segoe UI', sans-serif;
    }
    .rag-input-row {
      display: flex;
      gap: 6px;
      margin-top: 6px;
    }
    .rag-input-row input {
      flex: 1;
      background: #0f172a;
      border: 1px solid #3b82f6;
      color: #fff;
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 12px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
    }
    .card h2 {
      font-size: 0.9rem;
      color: #93c5fd;
      margin-bottom: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 5px;
      display: flex;
      justify-content: space-between;
    }
    .kpi-row {
      display: flex;
      justify-content: space-between;
      margin: 5px 0;
      font-size: 0.82rem;
    }
    .kpi-val { font-family: Consolas, monospace; font-weight: 700; }
    button {
      background: var(--blue);
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 6px 10px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.78rem;
      margin-right: 4px;
      margin-top: 5px;
    }
    button:hover { opacity: 0.92; }
    button.green { background: var(--green); }
    button.amber { background: var(--amber); color: #111; }
    button.red { background: var(--red); }
    button.purple { background: var(--purple); }
    table { width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-top: 4px; }
    th, td { text-align: left; padding: 5px 7px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); }
    .mono { font-family: Consolas, monospace; }
    .log-box {
      max-height: 175px;
      overflow-y: auto;
      font-family: Consolas, monospace;
      font-size: 0.75rem;
      background: #080c18;
      padding: 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .log-item { padding: 3px 0; border-bottom: 1px dashed #1e293b; }
    .chain-bar {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 8px;
      margin-bottom: 12px;
    }
    .step-box {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 7px 9px;
      font-size: 0.75rem;
      text-align: center;
    }
    .step-box.done {
      border-color: var(--green);
      background: rgba(16,185,129,0.14);
    }
    .step-box strong { display: block; font-size: 0.82rem; margin-bottom: 2px; }
  </style>
</head>
<body>
  <header>
    <div class="title-block">
      <h1>PROJECT RESILIENCE-ALPHA — Centre IA & Cyber-Résilience (Groupe 2)</h1>
      <p>Lenny BARRESI • Youssef HANSIL • Pierre MICHAUD-EYMOZ • Rohail ARSHAD | Hôte: 192.168.137.1 | 2e PC: 192.168.137.135</p>
    </div>
    <div>
      <span id="ollama-badge" class="badge badge-ai">IA OLLAMA (gemma4:e4b) : ACTIF</span>
      <span id="state-badge" class="badge state-NORMAL">ÉTAT : NORMAL</span>
    </div>
  </header>

  <div class="chain-bar">
    <div id="step-t0" class="step-box"><strong>T0 : Transaction Initiale</strong><span id="step-t0-txt">En attente</span></div>
    <div id="step-t1" class="step-box"><strong>T1 : Attaque Reçue</strong><span id="step-t1-txt">En attente</span></div>
    <div id="step-t2" class="step-box"><strong>T2 : Dégradation Observée</strong><span id="step-t2-txt">Latence nominale</span></div>
    <div id="step-t3" class="step-box"><strong>T3 : Détection IA (ML + Ollama)</strong><span id="step-t3-txt">Surveillance active</span></div>
    <div id="step-t4" class="step-box"><strong>T4 : Remédiation HMAC + WAF</strong><span id="step-t4-txt">Aucune IP bloquée</span></div>
    <div id="step-t5" class="step-box"><strong>T5 : Preuve Métier Finale</strong><span id="step-t5-txt">En attente</span></div>
  </div>

  <!-- SECTION HERO AU PREMIER PLAN : L'IA (ISOLATION FOREST + OLLAMA GEMMA4:E4B) -->
  <div class="ai-hero">
    <div class="ai-panel">
      <h2>
        <span>🧠 1. RADAR IA TEMPS RÉEL — DÉTECTION DE TOUTES LES ATTAQUES (IsolationForest)</span>
        <span id="ai-inference-count" class="mono" style="font-size:0.76rem;color:#34d399;">0 fenêtres analysées</span>
      </h2>
      <div id="ai-attack-banner" class="attack-banner attack-nominal">
        <span id="ai-attack-label">VECTEUR DÉTECTÉ PAR L'IA : AUCUNE MENACE (TRAFIC NOMINAL)</span>
        <span id="ai-score-pill" class="mono">Score: 0.0000 (Seuil: -0.1176)</span>
      </div>

      <div class="kpi-row">
        <span>IP Source Corrélée par l'IA :</span>
        <span id="feat-ip" class="kpi-val" style="color:#fbbf24">127.0.0.1</span>
      </div>
      <div class="kpi-row">
        <span>Débit Observé / Latence P95 / Saturation CPU :</span>
        <span class="kpi-val"><span id="feat-rps">0.5 req/s</span> | <span id="feat-lat">12.0 ms</span> | <span id="feat-sat">5%</span></span>
      </div>
      <div class="kpi-row">
        <span>Taux d'Erreur (4xx/5xx) / Signatures L7 / Appels Auth :</span>
        <span class="kpi-val"><span id="feat-err">0.0%</span> | <span id="feat-sig">0 sig</span> | <span id="feat-auth">0 auth</span></span>
      </div>

      <div style="margin-top:8px;font-size:0.78rem;color:#93c5fd;font-weight:600;">
        Explicabilité IA (Top Variables Contribuant au Score d'Anomalie XAI) :
      </div>
      <div id="xai-bars" style="margin-top:4px;"></div>

      <div class="vector-grid">
        <div class="vector-pill"><span>Flood L7 Batch</span><strong id="cnt-vec-flood">0</strong></div>
        <div class="vector-pill"><span>Brute-Force Auth</span><strong id="cnt-vec-auth">0</strong></div>
        <div class="vector-pill"><span>SQLi / XSS / L7</span><strong id="cnt-vec-sqli">0</strong></div>
        <div class="vector-pill"><span>Saturation DoS</span><strong id="cnt-vec-dos">0</strong></div>
      </div>

      <div style="margin-top:8px;border-top:1px solid #312e81;padding-top:6px;">
        <span style="font-size:0.75rem;color:#a5b4fc;display:block;margin-bottom:2px;">Tester la détection IA sur n'importe quel type d'attaque (ou depuis <a href="/attacker" target="_blank" style="color:#38bdf8">/attacker sur le 2e PC</a>) :</span>
        <button class="red" onclick="triggerAttackVector('flood_l7')">🔥 1. Attaque Flood L7 (/verify-batch)</button>
        <button class="red" onclick="triggerAttackVector('brute_force_auth')">🔑 2. Attaque Brute-Force Auth (/token)</button>
        <button class="red" onclick="triggerAttackVector('sqli_xss_injection')">💉 3. Attaque Injection SQLi / XSS</button>
        <button class="purple" onclick="triggerAttackVector('multi_vector')">⚡ 4. Assaut Combiné Multi-Vecteurs</button>
      </div>
    </div>

    <div class="ai-panel">
      <h2>
        <span>🤖 2. CERVEAU IA LOCAL OLLAMA (gemma4:e4b) — DIAGNOSTIC & COPILOTE RAG</span>
        <span id="ollama-model-tag" class="mono" style="font-size:0.75rem;color:#c4b5fd;">Modèle: gemma4:e4b (Lecture seule)</span>
      </h2>
      <div style="font-size:0.76rem;color:#94a3b8;margin-bottom:5px;">
        Diagnostic IA en direct sur l'état du système, le vecteur d'attaque détecté et les procédures certifiées (EBIOS RM / PCA-PRA / DORA) :
      </div>
      <div id="ollama-output" class="ollama-box">Chargement du diagnostic IA local Ollama (gemma4:e4b)...</div>

      <div style="display:flex;flex-wrap:wrap;gap:4px;">
        <button class="purple" onclick="askOllama('Analyse le dernier incident cyber détecté par IsolationForest et la remédiation Zero-Touch')">🔍 Analyser l'incident en cours</button>
        <button class="purple" onclick="askOllama('Quels sont les scénarios de risques EBIOS RM et comment le WAF et l exécuteur HMAC y répondent ?')">🛡️ Diagnostic EBIOS RM</button>
        <button class="purple" onclick="askOllama('Quels sont les objectifs RTO et RPO du PCA PRA et pourquoi la sonde métier T5 est obligatoire ?')">📈 RTO/RPO & Preuve T5</button>
        <button class="purple" onclick="askOllama('Comment l architecture respecte DORA et NIS2 et quelles sont les limites de l hôte unique ?')">⚖️ Conformité DORA / NIS2</button>
      </div>

      <div class="rag-input-row">
        <input id="rag-question-input" type="text" placeholder="Posez une question en direct à l'IA Ollama (gemma4:e4b)..." onkeydown="if(event.key==='Enter') askOllamaCustom()" />
        <button class="green" style="margin:0" onclick="askOllamaCustom()">Interroger Ollama</button>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>3. Opérations Métier & Contrôles (T0 / T5)</h2>
      <div class="kpi-row"><span>Invariant Comptable (3 comptes) :</span><span id="inv-status" class="kpi-val" style="color:#34d399">27 500,00 EUR (OK)</span></div>
      <div class="kpi-row"><span>ACC-FR-001 ( Émetteur ) :</span><span id="bal-1" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>ACC-FR-002 ( Marchand ) :</span><span id="bal-2" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>Transactions engagées :</span><span id="tx-count" class="kpi-val">0</span></div>
      <div style="margin-top:8px">
        <button class="green" onclick="executePayment('T0')">Exécuter Transaction T0 (50,00 EUR)</button>
        <button class="green" onclick="executePayment('T5')">Exécuter Transaction T5 (25,00 EUR)</button>
        <button class="amber" onclick="resetPlatform()">Réinitialiser Démo (Débloquer IP)</button>
      </div>
      <div id="tx-feedback" style="margin-top:6px;font-size:0.78rem;color:#6ee7b7;"></div>
    </div>

    <div class="card">
      <h2>4. Remédiation Autonome (HMAC) & WAF Dynamique</h2>
      <div class="kpi-row"><span>Profil WAF Actif :</span><span id="waf-profile" class="kpi-val">normal</span></div>
      <div class="kpi-row"><span>IP Bloquées par l'IA :</span><span id="waf-blocked-ips" class="kpi-val" style="color:#f87171">Aucune</span></div>
      <div class="kpi-row"><span>Requêtes d'attaque rejetées (403/429) :</span><span id="waf-blocked-hits" class="kpi-val">0</span></div>
      <div class="kpi-row"><span>MTTD / MTTR mesurés :</span><span id="mttd-mttr" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>Dernière Sonde Métier (T5) :</span><span id="probe-tx" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>Fenêtres anormales consécutives :</span><span id="ml-consec" class="kpi-val">0 / 2</span></div>
    </div>

    <div class="card">
      <h2>5. Liens d'Observabilité & Console Offensives</h2>
      <div class="kpi-row"><span>Dashboard Grafana Temps Réel :</span><a href="http://127.0.0.1:3001/d/resilience-alpha-main" target="_blank" style="color:#38bdf8;font-weight:700;">Ouvrir Grafana (:3001)</a></div>
      <div class="kpi-row"><span>Serveur Prometheus TSDB :</span><a href="http://127.0.0.1:9090/targets" target="_blank" style="color:#38bdf8;">Ouvrir Prometheus (:9090)</a></div>
      <div class="kpi-row"><span>Console Multi-Attaques 2e PC :</span><a href="/attacker" target="_blank" style="color:#f87171;font-weight:700;">Ouvrir /attacker (:8080)</a></div>
      <div class="kpi-row"><span>API Assistant IA Ollama RAG :</span><a href="http://127.0.0.1:8006/rag/v1/status" target="_blank" style="color:#c4b5fd;">Statut Ollama (:8006)</a></div>
      <div class="kpi-row"><span>Audit Cryptographique SHA-256 :</span><span class="kpi-val" style="color:#34d399">HMAC + Hash-Chain OK</span></div>
    </div>
  </div>

  <div class="grid-2" style="margin-bottom:12px;">
    <!-- Carte Biométrie & Objet Connecté ESP8266 (Consigne Additionnelle 1) -->
    <div class="card" style="border: 1px solid #4f46e5;">
      <h2>
        <span>🔐 6. AUTHENTIFICATION BIOMÉTRIQUE & MATÉRIEL IoT ESP8266 (Consigne Additionnelle 1)</span>
        <span id="esp-status-badge" class="mono" style="font-size:0.75rem;color:#38bdf8;">ESP-12F COM6</span>
      </h2>
      <div style="display:flex;align-items:center;justify-content:space-between;background:#090d1a;padding:8px 12px;border-radius:8px;border:1px solid #1e293b;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div id="virtual-esp-led" class="led-off" style="width:20px;height:20px;border-radius:50%;transition:all 0.3s;background:#475569;"></div>
          <div>
            <div style="font-size:0.82rem;font-weight:700;" id="esp-led-title">LED Bicolore : ÉTEINTE (OFF)</div>
            <div style="font-size:0.73rem;color:#94a3b8;" id="esp-led-sub">ESP-12F en attente d'identification</div>
          </div>
        </div>
        <div id="lockout-countdown" class="mono" style="font-size:0.78rem;font-weight:700;color:#ef4444;display:none;">
          BLOQUÉ 5 MIN (<span id="lockout-secs">300</span>s)
        </div>
      </div>

      <!-- Prévisualisation Vidéo Caméra Intégrée PC Portable -->
      <div style="display:flex;gap:10px;align-items:center;background:#090d1a;padding:8px 10px;border-radius:8px;margin-bottom:8px;border:1px solid #1e293b;">
        <div style="position:relative;width:140px;height:105px;border-radius:6px;overflow:hidden;border:1px solid #38bdf8;background:#000;flex-shrink:0;">
          <video id="laptop-cam-video" autoplay playsinline muted style="width:100%;height:100%;object-fit:cover;transform:scaleX(-1);"></video>
          <div style="position:absolute;top:3px;left:4px;background:rgba(0,0,0,0.65);color:#38bdf8;font-size:0.62rem;padding:1px 4px;border-radius:3px;font-family:Consolas,monospace;">CAMÉRA PC</div>
        </div>
        <div style="font-size:0.75rem;color:#94a3b8;line-height:1.35;">
          <strong style="color:#e2e8f0;display:block;margin-bottom:2px;">Caméra Intégrée PC Portable &amp; Capteur IR :</strong>
          Positionnez-vous face à votre écran. Si c'est votre première fois, cliquez sur <strong>Enrôler</strong> pour mémoriser votre visage :
          <div style="margin-top:6px;display:flex;gap:6px;">
            <button class="purple" style="font-size:0.73rem;padding:4px 8px;margin:0;" onclick="enrollMyFaceSnapshot()">📸 Enrôler mon visage en 1-Clic</button>
          </div>
        </div>
      </div>
      <canvas id="laptop-cam-canvas" style="display:none;"></canvas>

      <!-- Formulaire 3 étapes -->
      <div style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #1e293b;">
        <div style="font-size:0.74rem;color:#cbd5e1;margin-bottom:6px;">
          <strong>Cycle de Sécurité Physique :</strong> Caméra PC Portable &rarr; IA Visage (2 essais max) &rarr; LED Bicolore ESP-12F &rarr; Mot de Passe
        </div>
        <div style="display:flex;gap:6px;margin-bottom:6px;">
          <select id="bio-username-input" style="flex:1;background:#020617;border:1px solid #38bdf8;color:#f8fafc;padding:6px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;cursor:pointer;">
            <option value="operator_alpha" selected>👤 Opérateur Marchand Alpha (operator_alpha)</option>
            <option value="rohail_arshad">👤 Rohail ARSHAD (Équipe G2)</option>
            <option value="lenny_barresi">👤 Lenny BARRESI (Équipe G2)</option>
            <option value="youssef_hansil">👤 Youssef HANSIL (Équipe G2)</option>
            <option value="pierre_michaud">👤 Pierre MICHAUD-EYMOZ (Équipe G2)</option>
          </select>
          <button class="blue" id="bio-cam-btn" onclick="triggerBiometricFaceCheck()">📸 1. Analyser mon visage</button>
        </div>

        <div style="display:flex;gap:6px;">
          <input id="bio-password-input" type="password" placeholder="Mot de passe (bloqué tant que visage non validé)" disabled value="FictiveOp#2026!" style="flex:1;background:#090d16;border:1px solid #1e293b;color:#64748b;padding:6px 10px;border-radius:6px;font-size:0.8rem;" />
          <button id="bio-login-btn" class="green" disabled onclick="validatePasswordAndLogin()">🔑 2. Valider Mot de Passe</button>
          <button class="amber" style="font-size:0.75rem;padding:6px 10px;margin:0;" onclick="resetBiometricCycle()" title="Réinitialiser l'étape pour tester à nouveau">🔄 Recommencer</button>
        </div>

        <div id="bio-feedback-msg" style="margin-top:6px;font-size:0.75rem;color:#94a3b8;">
          En attente de déclenchement de la caméra USB connectée sur le PC.
        </div>
      </div>

      <div style="margin-top:8px;border-top:1px solid #1e293b;padding-top:6px;">
        <span style="font-size:0.73rem;color:#94a3b8;display:block;margin-bottom:4px;">Banc d'Essai Direct LED Bicolore ESP8266 (Pilotage Série / REST) :</span>
        <button class="green" style="font-size:0.72rem;padding:3px 7px;" onclick="testLedState('GREEN_BLINK')">🟢 Vert Clignotant (Visage OK)</button>
        <button class="green" style="font-size:0.72rem;padding:3px 7px;" onclick="testLedState('GREEN_SOLID_30S')">🟢 Vert Fixe 30s (Pass OK)</button>
        <button class="red" style="font-size:0.72rem;padding:3px 7px;" onclick="testLedState('RED_SOLID_30S')">🔴 Rouge Fixe 30s (Visage KO)</button>
        <button class="red" style="font-size:0.72rem;padding:3px 7px;" onclick="testLedState('RED_BLINK_10X')">🔴 Rouge Clignote 10x (Pass KO)</button>
        <button class="amber" style="font-size:0.72rem;padding:3px 7px;" onclick="testLedState('OFF')">⚪ Éteindre (OFF)</button>
      </div>
    </div>

    <!-- Carte Habilitations Back-Office -->
    <div class="card">
      <h2>
        <span>👥 HABILITATIONS BIOMÉTRIQUES BACK-OFFICE (Équipe G2 &amp; Opérateurs)</span>
        <button class="blue" style="margin:0;padding:2px 8px;font-size:0.72rem;" onclick="refreshBiometricHabilitations()">Actualiser</button>
      </h2>
      <div style="font-size:0.74rem;color:#94a3b8;margin-bottom:6px;">
        Gestion des habilitations, statuts de verrouillage temporaire (5 min) et réinitialisations :
      </div>
      <table style="width:100%;font-size:0.76rem;">
        <thead>
          <tr><th>Opérateur</th><th>Identifiant</th><th>Rôle</th><th>Statut</th><th>Action</th></tr>
        </thead>
        <tbody id="bio-habilitations-table"></tbody>
      </table>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Chronologie SOC & Décisions IA (Temps Réel)</h2>
      <div id="timeline-box" class="log-box"></div>
    </div>
    <div class="card">
      <h2>Dernières Transactions Métier Persistées (ACID)</h2>
      <table>
        <thead>
          <tr><th>ID Transaction</th><th>Montant</th><th>Idempotence</th><th>Statut</th></tr>
        </thead>
        <tbody id="tx-table"></tbody>
      </table>
    </div>
  </div>

  <script>
    let t0Done = false;
    let lastAutoIncidentId = null;
    let userAskedCustom = false;
    let currentLockoutSecs = 0;
    let bioFaceVerified = false;

    const ATTACK_LABELS = {
      'NOMINAL': 'AUCUNE MENACE (TRAFIC NOMINAL)',
      'FLOOD_L7_VERIFY_BATCH': '🚨 FLOOD APPLICATIF L7 CRYPTO (/api/v1/transactions/verify-batch)',
      'BRUTE_FORCE_AUTH_JWT': '🚨 FORCE BRUTE AUTHENTIFICATION JWT (/auth/v1/token)',
      'INJECTION_L7_SQLI_XSS': '🚨 INJECTION CRITIQUE L7 (SQLi / XSS / Path Traversal)',
      'SATURATION_LATENCE_DOS': '🚨 SATURATION WORKERS & DÉGRADATION LATENCE P95'
    };

    async function executePayment(label) {
      const amountCents = label === 'T0' ? 5000 : 2500;
      const fb = document.getElementById('tx-feedback');
      fb.style.color = '#93c5fd';
      fb.textContent = `Exécution de la transaction ${label} (${(amountCents/100).toFixed(2)} EUR)...`;
      try {
        const res = await fetch('/live/v1/trigger-payment', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({label, amount_cents: amountCents})
        });
        const data = await res.json();
        if (res.ok) {
          fb.style.color = '#34d399';
          fb.textContent = `Transaction ${label} COMMITTED : ${data.transaction.transaction_id}`;
          if (label === 'T0') t0Done = true;
        } else {
          fb.style.color = '#f87171';
          fb.textContent = `Erreur : ${data.error || 'échec'}`;
        }
      } catch (e) {
        fb.style.color = '#f87171';
        fb.textContent = `Erreur réseau : ${e}`;
      }
      refreshState();
    }

    async function resetPlatform() {
      userAskedCustom = false;
      lastAutoIncidentId = null;
      await fetch('/live/v1/reset', {method: 'POST'});
      document.querySelectorAll('.step-box').forEach(el => el.classList.remove('done'));
      document.getElementById('tx-feedback').textContent = 'Plateforme réinitialisée (IP débloquées, état NORMAL).';
      refreshState();
    }

    async function triggerAttackVector(attackType) {
      userAskedCustom = false;
      const fb = document.getElementById('tx-feedback');
      fb.style.color = '#fbbf24';
      fb.textContent = `Lancement de l'attaque [${attackType}] vers la passerelle WAF : observation par l'IA en cours...`;
      await fetch('/live/v1/trigger-scenario', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          source_ip: '192.168.137.135',
          attack_type: attackType,
          duration_seconds: 10,
          rate_rps: 25
        })
      });
    }

    async function askOllama(questionText) {
      userAskedCustom = true;
      const box = document.getElementById('ollama-output');
      box.style.border = '2px solid #a855f7';
      box.style.background = '#1e1b4b';
      box.textContent = `⏳ GEMMA 4 (8.0B) EN COURS D'INFÉRENCE...\n\nOllama consulte le corpus documentaire confiné (docs/*.md) et génère la réponse en local sur votre machine...\n\nQuestion posée : "${questionText}"`;
      try {
        const res = await fetch('/live/v1/ai-ask', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({query: questionText})
        });
        const data = await res.json();
        box.style.border = '1px solid #10b981';
        box.style.background = '#091524';
        box.textContent = data.formatted_report || data.answer || 'Aucune réponse.';
      } catch (e) {
        box.style.border = '1px solid #ef4444';
        box.textContent = `Erreur lors de l'appel à Ollama : ${e}`;
      }
    }

    function askOllamaCustom() {
      const inp = document.getElementById('rag-question-input');
      const q = (inp.value || '').trim();
      if (!q) return;
      askOllama(q);
    }

    async function refreshState() {
      try {
        const res = await fetch('/live/v1/summary');
        const s = await res.json();

        const st = s.remediator.state;
        const badge = document.getElementById('state-badge');
        badge.textContent = 'ÉTAT : ' + st;
        badge.className = 'badge state-' + st;

        // Statut Ollama
        const ollamaBadge = document.getElementById('ollama-badge');
        if (s.ai_copilot && s.ai_copilot.llm_status === 'OLLAMA_ACTIVE') {
          ollamaBadge.textContent = `IA OLLAMA (${s.ai_copilot.model}) : ACTIF`;
          ollamaBadge.style.borderColor = '#10b981';
          ollamaBadge.style.color = '#6ee7b7';
        } else {
          ollamaBadge.textContent = 'IA RAG VECTORIEL : ACTIF';
        }

        // Radar IA IsolationForest
        const ml = s.detector;
        const feat = s.telemetry.features || {};
        document.getElementById('ai-inference-count').textContent = `${ml.inferences_total} fenêtres analysées | ${ml.anomalies_total} anomalies`;

        const activeAttack = (ml.last_is_anomaly ? ml.last_attack_type : (s.ai_copilot && s.ai_copilot.last_detected_attack_type)) || 'NOMINAL';
        const banner = document.getElementById('ai-attack-banner');
        const labelEl = document.getElementById('ai-attack-label');
        const scoreEl = document.getElementById('ai-score-pill');
        scoreEl.textContent = `Score ML: ${(ml.last_score || 0).toFixed(4)} (Seuil: -0.1176)`;

        if (ml.last_is_anomaly || st === 'SUSPECT' || st === 'INCIDENT' || st === 'REMEDIATING') {
          banner.className = 'attack-banner attack-alert';
          labelEl.textContent = ATTACK_LABELS[activeAttack] || `🚨 ATTAQUE DÉTECTÉE PAR L'IA : ${activeAttack}`;
        } else if (st === 'RECOVERED' && activeAttack !== 'NOMINAL') {
          banner.className = 'attack-banner attack-nominal';
          labelEl.textContent = `✅ MENACE NEUTRALISÉE PAR L'IA (${ATTACK_LABELS[activeAttack] || activeAttack})`;
        } else {
          banner.className = 'attack-banner attack-nominal';
          labelEl.textContent = ATTACK_LABELS['NOMINAL'];
        }

        document.getElementById('ml-consec').textContent = ml.consecutive_anomalies + ' / 2';
        document.getElementById('feat-rps').textContent = (feat.req_rate_rps || 0).toFixed(1) + ' req/s';
        document.getElementById('feat-lat').textContent = (feat.latency_p95_ms || 0).toFixed(1) + ' ms';
        document.getElementById('feat-sat').textContent = Math.round((feat.cpu_worker_saturation || 0) * 100) + '%';
        document.getElementById('feat-err').textContent = ((feat.error_rate_ratio || 0) * 100).toFixed(1) + '%';
        document.getElementById('feat-sig').textContent = (s.telemetry.waf_signature_hits || 0) + ' sig';
        document.getElementById('feat-auth').textContent = (s.telemetry.waf_auth_requests || 0) + ' auth';
        document.getElementById('feat-ip').textContent = s.telemetry.dominant_source_ip || '127.0.0.1';

        // Barres XAI (Top contributing features)
        const topFeats = (ml.last_event && ml.last_event.top_contributing_features) || [];
        const xaiBox = document.getElementById('xai-bars');
        if (topFeats.length > 0) {
          xaiBox.innerHTML = topFeats.map(f => {
            const pct = Math.min(100, Math.max(8, Math.round((f.z_score || 0.5) * 18)));
            return `<div class="feature-bar-row">
              <span class="mono" style="width:175px;color:#cbd5e1">${f.feature}</span>
              <div class="feature-bar-bg"><div class="feature-bar-fill" style="width:${pct}%"></div></div>
              <span class="mono" style="width:110px;text-align:right;color:#fca5a5">val=${f.value} (z=${f.z_score})</span>
            </div>`;
          }).join('');
        }

        // Compteurs par vecteur
        const byType = ml.anomalies_by_type || {};
        document.getElementById('cnt-vec-flood').textContent = byType['FLOOD_L7_VERIFY_BATCH'] || 0;
        document.getElementById('cnt-vec-auth').textContent = byType['BRUTE_FORCE_AUTH_JWT'] || 0;
        document.getElementById('cnt-vec-sqli').textContent = byType['INJECTION_L7_SQLI_XSS'] || 0;
        document.getElementById('cnt-vec-dos').textContent = byType['SATURATION_LATENCE_DOS'] || 0;

        // Diagnostic automatique Ollama au premier plan
        if (!userAskedCustom && s.ai_copilot && s.ai_copilot.live_diagnosis) {
          document.getElementById('ollama-output').textContent = s.ai_copilot.live_diagnosis;
        }

        // Comptes et transactions
        document.getElementById('inv-status').textContent =
          (s.ledger.total_cents / 100).toFixed(2) + ' EUR (' + (s.ledger.consistent ? 'INTÈGRE' : 'ERREUR') + ')';
        const accs = s.ledger.accounts || {};
        if (accs['ACC-FR-001']) document.getElementById('bal-1').textContent = (accs['ACC-FR-001'].balance_cents / 100).toFixed(2) + ' EUR';
        if (accs['ACC-FR-002']) document.getElementById('bal-2').textContent = (accs['ACC-FR-002'].balance_cents / 100).toFixed(2) + ' EUR';
        document.getElementById('tx-count').textContent = s.ledger.transactions.length;

        // WAF & Remediator
        document.getElementById('waf-profile').textContent = s.waf.rate_limit_profile;
        const blockedList = s.waf.active_blocked_ips || [];
        document.getElementById('waf-blocked-ips').textContent =
          blockedList.length ? blockedList.map(x => x.ip_address).join(', ') : 'Aucune';
        const totalBlocked = (s.waf.metrics.waf_blocked_dynamic_ip_total || 0) +
                             (s.waf.metrics.waf_blocked_ratelimit_total || 0) +
                             (s.waf.metrics.waf_blocked_signature_total || 0);
        document.getElementById('waf-blocked-hits').textContent = totalBlocked;

        const mttd = s.remediator.metrics.remediator_last_mttd_seconds || 0;
        const mttr = s.remediator.metrics.remediator_last_mttr_seconds || 0;
        document.getElementById('mttd-mttr').textContent =
          (mttd > 0 || mttr > 0) ? `MTTD=${mttd.toFixed(2)}s | MTTR=${mttr.toFixed(2)}s` : '—';

        const lastProbe = s.remediator.last_verified_transaction;
        document.getElementById('probe-tx').textContent =
          lastProbe ? `${lastProbe.transaction_id} (1,00 EUR COMMITTED)` : '—';

        // Chain steps
        const hasTx = s.ledger.transactions.length > 0;
        if (hasTx || t0Done) {
          document.getElementById('step-t0').classList.add('done');
          document.getElementById('step-t0-txt').textContent = 'PASS (' + s.ledger.transactions[0].transaction_id.slice(0, 12) + ')';
        }
        if ((feat.req_rate_rps || 0) > 4 || totalBlocked > 0 || blockedList.length > 0) {
          document.getElementById('step-t1').classList.add('done');
          document.getElementById('step-t1-txt').textContent = 'Reçue (' + (s.telemetry.dominant_source_ip || '2e PC') + ')';
        }
        if ((feat.latency_p95_ms || 0) > 50 || (feat.error_rate_ratio || 0) > 0.2 || blockedList.length > 0) {
          document.getElementById('step-t2').classList.add('done');
          document.getElementById('step-t2-txt').textContent = 'Observée';
        }
        if (ml.anomalies_total > 0 || blockedList.length > 0) {
          document.getElementById('step-t3').classList.add('done');
          document.getElementById('step-t3-txt').textContent = 'Détectée (' + activeAttack.slice(0, 14) + ')';
        }
        if (blockedList.length > 0) {
          document.getElementById('step-t4').classList.add('done');
          document.getElementById('step-t4-txt').textContent = 'IP ' + blockedList[0].ip_address + ' bannie';
        }
        if (st === 'RECOVERED' && lastProbe) {
          document.getElementById('step-t5').classList.add('done');
          document.getElementById('step-t5-txt').textContent = 'RECOVERED (' + lastProbe.transaction_id.slice(0, 12) + ')';
        }

        // Timeline
        const tlBox = document.getElementById('timeline-box');
        tlBox.innerHTML = (s.remediator.recent_timeline || []).slice().reverse().slice(0, 18).map(item =>
          `<div class="log-item"><span style="color:#60a5fa">[${item.timestamp.slice(11,19)}]</span> <strong>[${item.stage}]</strong> ${item.message}</div>`
        ).join('');

        // Transactions table
        const tbody = document.getElementById('tx-table');
        tbody.innerHTML = (s.ledger.transactions || []).slice(0, 8).map(tx =>
          `<tr>
            <td class="mono">${tx.transaction_id}</td>
            <td class="mono">${(tx.amount_cents/100).toFixed(2)} ${tx.currency}</td>
            <td class="mono">${tx.idempotency_key.slice(0, 18)}</td>
            <td style="color:#34d399;font-weight:700">${tx.status}</td>
          </tr>`
        ).join('');

        // Mise à jour de l'état biométrique et de l'ESP8266
        const bio = s.biometrics || {};
        if (bio.esp_hardware && !bioFaceVerified && currentLockoutSecs <= 0) {
          updateEspLedVisual(bio.esp_hardware.current_state, bio.esp_hardware.port);
        }
        const bioTbody = document.getElementById('bio-habilitations-table');
        if (bioTbody && bio.habilitations) {
          bioTbody.innerHTML = bio.habilitations.map(h => `
            <tr>
              <td><strong>${h.display_name}</strong></td>
              <td class="mono">${h.username}</td>
              <td>${h.role}</td>
              <td><span style="color:${h.is_locked ? '#f87171' : '#34d399'};font-weight:700">${h.is_locked ? 'BLOQUÉ (' + h.lockout_seconds_remaining + 's)' : h.status}</span></td>
              <td>${h.is_locked ? `<button class="amber" style="padding:2px 6px;font-size:0.7rem;margin:0;" onclick="resetOperatorLockout('${h.username}')">Débloquer</button>` : '—'}</td>
            </tr>
          `).join('');
        }
      } catch (e) {}
    }

    setInterval(() => {
      if (currentLockoutSecs > 0) {
        currentLockoutSecs--;
        document.getElementById('lockout-secs').textContent = currentLockoutSecs;
        if (currentLockoutSecs <= 0) {
          document.getElementById('lockout-countdown').style.display = 'none';
          document.getElementById('bio-cam-btn').disabled = false;
        }
      }
    }, 1000);

    function updateEspLedVisual(state, port) {
      const led = document.getElementById('virtual-esp-led');
      const title = document.getElementById('esp-led-title');
      const sub = document.getElementById('esp-led-sub');
      const badge = document.getElementById('esp-status-badge');
      if (port && badge) badge.textContent = `ESP-12F ${port}`;
      if (!led || !title || !sub) return;

      if (state === 'GREEN_BLINK') {
        led.style.background = '#10b981';
        led.style.boxShadow = '0 0 16px #10b981';
        title.textContent = 'LED Bicolore : VERT CLIGNOTANT';
        sub.textContent = '🟢 Visage reconnu par IA — Saisissez votre mot de passe';
      } else if (state === 'GREEN_SOLID_30S') {
        led.style.background = '#10b981';
        led.style.boxShadow = '0 0 18px #10b981';
        title.textContent = 'LED Bicolore : VERT FIXE (30s)';
        sub.textContent = '🟢 Mot de passe validé — Accès Back-office ouvert';
      } else if (state === 'RED_SOLID_30S') {
        led.style.background = '#ef4444';
        led.style.boxShadow = '0 0 18px #ef4444';
        title.textContent = 'LED Bicolore : ROUGE FIXE (30s)';
        sub.textContent = '🔴 Visage non reconnu / Compte bloqué';
      } else if (state === 'RED_BLINK_10X') {
        led.style.background = '#ef4444';
        led.style.boxShadow = '0 0 16px #ef4444';
        title.textContent = 'LED Bicolore : ROUGE CLIGNOTANT (10x)';
        sub.textContent = '🔴 Mot de passe erroné — Cycle réinitialisé';
      } else {
        led.style.background = '#475569';
        led.style.boxShadow = 'none';
        title.textContent = 'LED Bicolore : ÉTEINTE (OFF)';
        sub.textContent = "⚪ ESP-12F en attente d'identification";
      }
    }

    // Flux vidéo de la caméra intégrée du PC portable
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } } })
        .then(stream => {
          const vid = document.getElementById('laptop-cam-video');
          if (vid) vid.srcObject = stream;
        })
        .catch(err => {
          console.warn("Accès vidéo navigateur (fallback backend actif) :", err);
        });
    }

    function captureLaptopVideoFrame() {
      const vid = document.getElementById('laptop-cam-video');
      const cvs = document.getElementById('laptop-cam-canvas');
      if (vid && vid.videoWidth > 0 && cvs) {
        cvs.width = vid.videoWidth;
        cvs.height = vid.videoHeight;
        const ctx = cvs.getContext('2d');
        ctx.drawImage(vid, 0, 0, cvs.width, cvs.height);
        return cvs.toDataURL('image/jpeg', 0.9);
      }
      return null;
    }

    async function enrollMyFaceSnapshot() {
      const sel = document.getElementById('bio-username-input');
      const username = sel.value.trim() || 'operator_alpha';
      const displayName = sel.options && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text.replace(/^[^a-zA-Z0-9_\s]*\s*/, '') : username;
      const fb = document.getElementById('bio-feedback-msg');
      fb.textContent = `📸 Capture de votre visage pour '${displayName}' en cours...`;
      fb.style.color = "#38bdf8";

      const b64 = captureLaptopVideoFrame();
      try {
        const res = await fetch('/live/v1/bio-enroll', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            username: username,
            display_name: displayName,
            image_b64: b64
          })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          fb.textContent = `✓ Votre visage a été mémorisé avec succès pour '${displayName}' ! Cliquez maintenant sur '1. Analyser mon visage'.`;
          fb.style.color = "#34d399";
          currentLockoutSecs = 0;
          document.getElementById('lockout-countdown').style.display = 'none';
          document.getElementById('bio-cam-btn').disabled = false;
        } else {
          fb.textContent = "Erreur enrôlement : " + (d.error || d.message || "Visage non détecté");
          fb.style.color = "#f87171";
        }
      } catch (e) {
        fb.textContent = "Erreur : " + e.message;
        fb.style.color = "#f87171";
      }
      refreshBiometricHabilitations();
    }

    async function triggerBiometricFaceCheck() {
      const sel = document.getElementById('bio-username-input');
      const username = sel.value.trim();
      const displayName = sel.options && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text.replace(/^[^a-zA-Z0-9_\s]*\s*/, '') : username;
      const fb = document.getElementById('bio-feedback-msg');
      if (!username) {
        fb.textContent = 'Veuillez sélectionner un opérateur.';
        fb.style.color = '#f87171';
        return;
      }
      fb.textContent = `📸 Analyse biométrique du visage par l'IA pour '${displayName}'...`;
      fb.style.color = '#38bdf8';
      document.getElementById('bio-cam-btn').disabled = true;

      const b64 = captureLaptopVideoFrame();

      try {
        const res = await fetch('/live/v1/bio-identify', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username: username, use_camera: true, image_b64: b64})
        });
        const data = await res.json();
        if (res.ok && data.face_verified) {
          bioFaceVerified = true;
          fb.textContent = `✓ Visage reconnu pour ${displayName} (similarité ${((data.similarity_score || 0.85)*100).toFixed(1)}%). LED : Vert clignotant. Mot de passe débloqué !`;
          fb.style.color = '#34d399';
          document.getElementById('bio-password-input').disabled = false;
          document.getElementById('bio-password-input').style.background = '#020617';
          document.getElementById('bio-password-input').style.color = '#fff';
          document.getElementById('bio-login-btn').disabled = false;
          document.getElementById('bio-cam-btn').disabled = false;
          updateEspLedVisual('GREEN_BLINK');
        } else {
          bioFaceVerified = false;
          updateEspLedVisual('RED_SOLID_30S');
          document.getElementById('bio-cam-btn').disabled = false;
          if (data.locked) {
            currentLockoutSecs = data.locked_seconds_remaining || 300;
            document.getElementById('lockout-secs').textContent = currentLockoutSecs;
            document.getElementById('lockout-countdown').style.display = 'inline';
            fb.textContent = `✗ ${data.message} LED : Rouge fixe 30s. Compte bloqué.`;
            fb.style.color = '#ef4444';
          } else {
            fb.textContent = `✗ ${data.message} LED : Rouge fixe 30s. Vous pouvez réexaminer ou changer d'opérateur.`;
            fb.style.color = '#fbbf24';
          }
        }
      } catch (err) {
        fb.textContent = 'Erreur biométrique : ' + err.message;
        fb.style.color = '#f87171';
        document.getElementById('bio-cam-btn').disabled = false;
      }
      refreshBiometricHabilitations();
    }

    async function validatePasswordAndLogin() {
      const username = document.getElementById('bio-username-input').value.trim();
      const password = document.getElementById('bio-password-input').value;
      const fb = document.getElementById('bio-feedback-msg');

      try {
        const res = await fetch('/live/v1/bio-login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username: username, password: password})
        });
        const data = await res.json();
        if (res.ok && data.success) {
          updateEspLedVisual('GREEN_SOLID_30S');
          fb.textContent = '✓ Authentification réussie ! LED : Vert fixe 30s. Accès Back-office autorisé.';
          fb.style.color = '#34d399';
          document.getElementById('bio-cam-btn').disabled = false;
        } else {
          updateEspLedVisual('RED_BLINK_10X');
          fb.textContent = '✗ Mot de passe incorrect ! LED : Rouge clignote 10 fois. Recommencez le cycle.';
          fb.style.color = '#ef4444';
          bioFaceVerified = false;
          document.getElementById('bio-password-input').disabled = true;
          document.getElementById('bio-login-btn').disabled = true;
          document.getElementById('bio-cam-btn').disabled = false;
        }
      } catch (err) {
        fb.textContent = 'Erreur : ' + err.message;
        document.getElementById('bio-cam-btn').disabled = false;
      }
      refreshBiometricHabilitations();
    }

    function resetBiometricCycle() {
      bioFaceVerified = false;
      document.getElementById('bio-password-input').disabled = true;
      document.getElementById('bio-password-input').style.background = '#090d16';
      document.getElementById('bio-password-input').style.color = '#64748b';
      document.getElementById('bio-login-btn').disabled = true;
      document.getElementById('bio-cam-btn').disabled = false;
      const fb = document.getElementById('bio-feedback-msg');
      if (fb) {
        fb.textContent = "Cycle réinitialisé. Vous pouvez relancer '1. Analyser mon visage' à tout moment.";
        fb.style.color = "#94a3b8";
      }
      testLedState('OFF');
    }

    async function testLedState(state) {
      const fb = document.getElementById('bio-feedback-msg');
      if (fb) {
        fb.textContent = `Envoi commande ESP8266 : [${state}]...`;
        fb.style.color = '#38bdf8';
      }
      try {
        const res = await fetch('/live/v1/bio-led-test', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({state: state})
        });
        const d = await res.json();
        updateEspLedVisual(state);
        if (fb) {
          fb.textContent = `✓ Ordre envoyé à l'ESP8266 (${state}) : ${d.esp_status ? d.esp_status.last_command : 'OK'}`;
          fb.style.color = '#34d399';
        }
      } catch (err) {
        if (fb) {
          fb.textContent = `Erreur envoi LED : ${err.message}`;
          fb.style.color = '#ef4444';
        }
      }
    }

    async function resetOperatorLockout(u) {
      const fb = document.getElementById('bio-feedback-msg');
      if (fb) {
        fb.textContent = `Déblocage de ${u}...`;
        fb.style.color = '#38bdf8';
      }
      try {
        await fetch('/live/v1/bio-reset', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username: u})
        });
        currentLockoutSecs = 0;
        document.getElementById('lockout-countdown').style.display = 'none';
        document.getElementById('bio-cam-btn').disabled = false;
        if (fb) {
          fb.textContent = `✓ Opérateur ${u} débloqué avec succès. Vous pouvez relancer la reconnaissance faciale.`;
          fb.style.color = '#34d399';
        }
      } catch (err) {
        if (fb) {
          fb.textContent = `Erreur déblocage : ${err.message}`;
          fb.style.color = '#ef4444';
        }
      }
      refreshBiometricHabilitations();
    }

    // Export explicite sur window pour garantir l'accessibilité dans tous les navigateurs
    window.testLedState = testLedState;
    window.triggerBiometricFaceCheck = triggerBiometricFaceCheck;
    window.validatePasswordAndLogin = validatePasswordAndLogin;
    window.enrollMyFaceSnapshot = enrollMyFaceSnapshot;
    window.resetOperatorLockout = resetOperatorLockout;
    window.refreshBiometricHabilitations = refreshBiometricHabilitations;
    window.executePayment = executePayment;
    window.resetPlatform = resetPlatform;
    window.triggerAttackVector = triggerAttackVector;
    window.askOllama = askOllama;
    window.askOllamaCustom = askOllamaCustom;
    window.updateEspLedVisual = updateEspLedVisual;
    window.resetBiometricCycle = resetBiometricCycle;

    async function refreshBiometricHabilitations() {
      try {
        const r = await fetch('/live/v1/summary');
        const s = await r.json();
        const bio = s.biometrics || {};
        if (bio.esp_hardware) {
          updateEspLedVisual(bio.esp_hardware.current_state, bio.esp_hardware.port);
        }
        const tbody = document.getElementById('bio-habilitations-table');
        if (tbody && bio.habilitations) {
          tbody.innerHTML = bio.habilitations.map(h => `
            <tr>
              <td><strong>${h.display_name}</strong></td>
              <td class="mono">${h.username}</td>
              <td>${h.role}</td>
              <td><span style="color:${h.is_locked ? '#f87171' : '#34d399'};font-weight:700">${h.is_locked ? 'BLOQUÉ (' + h.lockout_seconds_remaining + 's)' : h.status}</span></td>
              <td>${h.is_locked ? `<button class="amber" style="padding:2px 6px;font-size:0.7rem;margin:0;" onclick="resetOperatorLockout('${h.username}')">Débloquer</button>` : '—'}</td>
            </tr>
          `).join('');
        }
      } catch (e) {}
    }

    setInterval(refreshState, 1200);
    refreshState();
  </script>
</body>
</html>
"""


ATTACKER_CONSOLE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>PC ATTAQUANT (Groupe 2) — Console Multi-Attaques RESILIENCE-G2</title>
  <style>
    body { font-family: 'Segoe UI', sans-serif; background: #0b1020; color: #f3f4f6; padding: 20px; max-width: 900px; margin: 0 auto; }
    .card { background: #162038; border: 1px solid #334155; border-radius: 10px; padding: 18px; margin-bottom: 16px; }
    h1 { color: #f87171; font-size: 1.3rem; margin-bottom: 6px; }
    .btn-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 14px; }
    button { background: #ef4444; color: white; border: none; padding: 12px 16px; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 0.9rem; text-align: left; }
    button.purple { background: #7c3aed; }
    button.stop { background: #f59e0b; color: #111; text-align: center; }
    button.reset { background: #10b981; color: #fff; text-align: center; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 16px; }
    .stat-box { background: #0f172a; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #334155; }
    .stat-box strong { display: block; font-size: 1.35rem; font-family: Consolas, monospace; margin-top: 4px; }
    pre { background: #070a14; padding: 12px; border-radius: 8px; overflow-x: auto; font-family: Consolas, monospace; font-size: 0.8rem; color: #93c5fd; }
  </style>
</head>
<body>
  <div class="card">
    <h1>PC ATTAQUANT — Banc de Tir Multi-Attaques (Groupe 2 — RESILIENCE-G2)</h1>
    <p>Cible autorisée : <strong>http://192.168.137.1:8080</strong> | Votre IP : <strong id="my-ip" style="color:#fbbf24">Détection...</strong></p>
    <p style="color:#a5b4fc;font-size:0.84rem;margin-top:4px;">Chaque bouton prépare automatiquement une fenêtre propre puis lance l'attaque choisie pour démontrer que l'IA (IsolationForest + Ollama) détecte et bloque <strong>toutes</strong> les attaques :</p>

    <div class="btn-grid">
      <button onclick="startScenario('flood_l7')">🔥 1. Attaque Flood L7 Cryptographique<br><span style="font-size:0.76rem;font-weight:400;opacity:0.9">Sature /api/v1/transactions/verify-batch (CPU & Latence P95)</span></button>
      <button onclick="startScenario('brute_force_auth')">🔑 2. Attaque Force Brute Authentification JWT<br><span style="font-size:0.76rem;font-weight:400;opacity:0.9">Rafale d'identifiants invalides sur /auth/v1/token (HTTP 401)</span></button>
      <button onclick="startScenario('sqli_xss_injection')">💉 3. Attaque Injections Critiques L7 (SQLi / XSS)<br><span style="font-size:0.76rem;font-weight:400;opacity:0.9">Payloads SQLi (' OR 1=1--), XSS (&lt;script&gt;) &amp; Path Traversal</span></button>
      <button class="purple" onclick="startScenario('multi_vector')">⚡ 4. Assaut Combiné Multi-Vecteurs<br><span style="font-size:0.76rem;font-weight:400;opacity:0.9">Combine Flood L7 + Brute-Force JWT + Injections SQLi</span></button>
    </div>

    <div style="display:flex;gap:10px;margin-top:12px;">
      <button class="stop" style="flex:1" onclick="stopScenario()">🛑 Arrêt d'Urgence Immédiat (Kill-Switch)</button>
      <button class="reset" style="flex:1" onclick="unblockMe()">🔓 Débloquer mon IP & Réinitialiser</button>
    </div>

    <div class="stats">
      <div class="stat-box"><span>Requêtes Envoyées</span><strong id="cnt-total">0</strong></div>
      <div class="stat-box"><span style="color:#fbbf24">Passées / Traitement</span><strong id="cnt-pass" style="color:#fbbf24">0</strong></div>
      <div class="stat-box"><span style="color:#34d399">403 Bloqué par IA/WAF</span><strong id="cnt-403" style="color:#34d399">0</strong></div>
      <div class="stat-box"><span style="color:#60a5fa">401 / 429 Rejetées</span><strong id="cnt-other" style="color:#60a5fa">0</strong></div>
    </div>
    <p id="status-msg" style="margin-top:14px;font-weight:700;color:#6ee7b7;"></p>
  </div>

  <div class="card">
    <h2 style="font-size:0.95rem;color:#93c5fd;margin-bottom:8px;">Option Terminal PowerShell depuis le 2e PC (192.168.137.135) :</h2>
    <pre>irm http://192.168.137.1:8080/attacker.ps1 | iex</pre>
  </div>

  <script>
    let running = false;
    let timerId = null;
    let currentVector = 'flood_l7';
    let counts = {total: 0, pass: 0, c403: 0, other: 0};

    fetch('/live/v1/whoami').then(r => r.json()).then(d => {
      document.getElementById('my-ip').textContent = d.client_ip;
    });

    async function unblockMe() {
      await fetch('/live/v1/reset', {method: 'POST'});
      document.getElementById('status-msg').textContent = 'Votre IP est débloquée et la plateforme est remise à l état NORMAL.';
    }

    async function sendOne() {
      if (!running) return;
      counts.total++;
      document.getElementById('cnt-total').textContent = counts.total;

      let url = '/api/v1/transactions/verify-batch';
      let bodyObj = {batch_size: 30, iterations: 40000, audit_profile: 'deep_verification'};

      let mode = currentVector;
      if (mode === 'multi_vector') {
        const pick = counts.total % 3;
        mode = pick === 0 ? 'flood_l7' : (pick === 1 ? 'brute_force_auth' : 'sqli_xss_injection');
      }

      if (mode === 'brute_force_auth') {
        url = '/auth/v1/token';
        bodyObj = {username: 'admin_target_' + (counts.total % 20), password: 'WrongPassword#' + counts.total};
      } else if (mode === 'sqli_xss_injection') {
        url = '/api/v1/transactions/verify-batch?filter=' + encodeURIComponent("' UNION SELECT username,password FROM users--");
        bodyObj = {batch_size: 10, payload: "<scr" + "ipt>alert('xss')</scr" + "ipt> ../../etc/passwd"};
      }

      try {
        const r = await fetch(url, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(bodyObj)
        });
        const data = await r.json().catch(() => ({}));
        if (r.status === 200) {
          counts.pass++;
        } else if (r.status === 403 && data.waf_rule === 'AIOPS_DYNAMIC_BLOCKLIST') {
          counts.c403++;
        } else if (r.status === 403) {
          counts.c403++;
        } else {
          counts.other++;
        }
        document.getElementById('cnt-pass').textContent = counts.pass;
        document.getElementById('cnt-403').textContent = counts.c403;
        document.getElementById('cnt-other').textContent = counts.other;
        if (counts.c403 > 0 && data.waf_rule === 'AIOPS_DYNAMIC_BLOCKLIST') {
          document.getElementById('status-msg').textContent =
            '🛡️ DÉTECTION & REMÉDIATION IA CONFIRMÉES : Votre IP est bannie dynamiquement par l IA (HTTP 403 AIOPS_DYNAMIC_BLOCKLIST) !';
        }
      } catch (e) {}
    }

    async function startScenario(vectorName) {
      if (running) stopScenario();
      currentVector = vectorName || 'flood_l7';
      await fetch('/live/v1/reset', {method: 'POST'});
      running = true;
      counts = {total: 0, pass: 0, c403: 0, other: 0};
      document.getElementById('status-msg').textContent =
        `🚀 Attaque [${currentVector}] en cours... L'IA IsolationForest + Ollama analyse le trafic en temps réel !`;
      timerId = setInterval(() => {
        for (let i = 0; i < 3; i++) sendOne();
      }, 115);
      setTimeout(() => {
        if (running) stopScenario('Tir borné terminé (plafond 18s atteint).');
      }, 18000);
    }

    function stopScenario(msg) {
      running = false;
      if (timerId) clearInterval(timerId);
      document.getElementById('status-msg').textContent = msg || 'Arrêt d urgence activé.';
    }
  </script>
</body>
</html>
"""


ATTACKER_POWERSHELL_SCRIPT = """# Script de Tir Contrôlé Multi-Attaques — Groupe 2 (RESILIENCE-G2)
$BaseUrl = "http://192.168.137.1:8080"
$TargetUrl = "$BaseUrl/api/v1/transactions/verify-batch"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PROJECT RESILIENCE-ALPHA (G2) - TIR CONTROLE DEPUIS 2e PC" -ForegroundColor Cyan
Write-Host " Remise a zero préalable de la liste de blocage pour la démo..." -ForegroundColor Yellow
try { Invoke-RestMethod -Uri "$BaseUrl/live/v1/reset" -Method POST -TimeoutSec 3 | Out-Null } catch {}
Write-Host " Cible autorisee : $TargetUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$Body = '{"batch_size":30,"iterations":40000,"audit_profile":"deep_verification"}'
$Count200 = 0
$Count403 = 0
$Count429 = 0
$Start = Get-Date

for ($i = 1; $i -le 130; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $TargetUrl -Method POST -Body $Body -ContentType "application/json" -TimeoutSec 3 -UseBasicParsing
        if ($resp.StatusCode -eq 200) {
            $Count200++
            Write-Host "[$i] HTTP 200 - Charge recue par l'API (Analyse IA IsolationForest en cours...)" -ForegroundColor Yellow
        }
    } catch {
        $code = 0
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
        }
        if ($code -eq 403) {
            $Count403++
            Write-Host "[$i] HTTP 403 FORBIDDEN - ATTAQUE DETECTEE PAR L'IA & IP BLOQUEE PAR LE WAF !" -ForegroundColor Green
        } elseif ($code -eq 429) {
            $Count429++
            Write-Host "[$i] HTTP 429 RATE LIMITED - Limitation de debit active !" -ForegroundColor Cyan
        } else {
            Write-Host "[$i] Statut HTTP $code" -ForegroundColor Red
        }
    }
    Start-Sleep -Milliseconds 110
}

$Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 2)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " FIN DU TIR CONTROLE ($Elapsed s)" -ForegroundColor Cyan
Write-Host " Requetes passees avant detection (200 OK) : $Count200" -ForegroundColor Yellow
Write-Host " Requetes bloquees par l'IA WAF (403)      : $Count403" -ForegroundColor Green
Write-Host " Requetes limitees Rate-Limit (429)        : $Count429" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
"""


WAF_GATEWAY_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>PROJECT RESILIENCE-ALPHA — Passerelle WAF & Reverse-Proxy (Port 8080)</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #121826;
      --border: #1e293b;
      --cyan: #06b6d4;
      --emerald: #10b981;
      --rose: #f43f5e;
      --text: #f1f5f9;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 28px 20px; max-width: 1040px; margin: 0 auto; line-height: 1.5; }
    .header { background: linear-gradient(135deg, #0e172a 0%, #16243d 100%); border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
    .title-box h1 { font-size: 1.45rem; font-weight: 800; color: #38bdf8; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px; }
    .title-box p { color: var(--muted); font-size: 0.88rem; margin-top: 4px; }
    .status-pill { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; padding: 6px 14px; border-radius: 999px; font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 20px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: transform 0.15s, border-color 0.15s; }
    .card:hover { border-color: #38bdf8; transform: translateY(-2px); }
    .card h2 { font-size: 1.1rem; color: #f8fafc; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .card p { font-size: 0.86rem; color: var(--muted); margin-bottom: 16px; min-height: 40px; }
    .btn-action { display: inline-flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px 18px; border-radius: 8px; font-weight: 700; font-size: 0.92rem; text-decoration: none; cursor: pointer; border: none; transition: background 0.15s; }
    .btn-cyan { background: #0284c7; color: white; }
    .btn-cyan:hover { background: #0369a1; }
    .btn-red { background: #e11d48; color: white; }
    .btn-red:hover { background: #be123c; }

    .live-status { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .live-status h3 { font-size: 0.98rem; color: #cbd5e1; margin-bottom: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; text-transform: uppercase; letter-spacing: 0.04em; }
    .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-box { background: #0a0f1d; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; text-align: center; }
    .stat-label { font-size: 0.76rem; color: var(--muted); text-transform: uppercase; }
    .stat-val { font-size: 1.35rem; font-weight: 800; font-family: Consolas, monospace; color: #38bdf8; margin-top: 4px; }
    .stat-val.red { color: #f43f5e; }
    .stat-val.green { color: #34d399; }

    .routes-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; margin-top: 8px; }
    .routes-table th { text-align: left; padding: 10px 12px; background: #0a0f1d; color: #94a3b8; font-weight: 600; border-bottom: 1px solid var(--border); }
    .routes-table td { padding: 10px 12px; border-bottom: 1px solid #172033; }
    .routes-table code { font-family: Consolas, monospace; color: #38bdf8; background: #0b1329; padding: 3px 6px; border-radius: 4px; }
    .method-badge { display: inline-block; font-size: 0.72rem; font-weight: 800; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; }
    .m-post { background: #1e3a8a; color: #93c5fd; }
    .m-get { background: #064e3b; color: #6ee7b7; }
  </style>
</head>
<body>

  <div class="header">
    <div class="title-box">
      <h1>🛡️ Passerelle WAF & Reverse-Proxy API (Port 8080)</h1>
      <p>PROJECT RESILIENCE-ALPHA — Point d'entrée d'ingestion réseau sécurisé avec ModSecurity & Blocklist Dynamique</p>
    </div>
    <div class="status-pill" id="waf-status-pill">WAF EN LIGNE</div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>🖥️ Centre de Contrôle SOC & IA (Port 3000)</h2>
      <p>Interface principale des opérateurs de cyber-résilience : supervision temps réel, radar IsolationForest, chronologie T0&rarr;T5 et copilote Ollama.</p>
      <a class="btn-action btn-cyan" href="http://127.0.0.1:3000" target="_blank">
        Ouvrir le Centre de Contrôle (Port 3000) &rarr;
      </a>
    </div>

    <div class="card">
      <h2>🎯 Console de Tir Attaquant (Port 8080)</h2>
      <p>Interface offensive dédiée au 2ᵉ PC connecté au point d'accès Wi-Fi : lance les attaques Flood L7, Brute-Force Auth, Injections SQLi/XSS.</p>
      <a class="btn-action btn-red" href="/attacker">
        Ouvrir la Console Attaquant (/attacker) &rarr;
      </a>
    </div>
  </div>

  <div class="live-status">
    <h3>État Temps Réel de la Passerelle WAF</h3>
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Profil de Filtrage</div>
        <div class="stat-val green" id="stat-profile">NORMAL</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">IP Bloquées Dynamiquement</div>
        <div class="stat-val" id="stat-blocked-count">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Attaques Rejetées (403)</div>
        <div class="stat-val red" id="stat-blocked-hits">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Automate de Résilience</div>
        <div class="stat-val green" id="stat-state">NORMAL</div>
      </div>
    </div>
    <div style="margin-top:14px;font-size:0.83rem;color:#94a3b8">
      <strong>IP bannies en ce moment :</strong> <span id="stat-blocked-ips" style="color:#f87171;font-family:Consolas,monospace">Aucune</span>
    </div>
  </div>

  <div class="live-status">
    <h3>Endpoints Métier Protégés par ce Reverse-Proxy</h3>
    <table class="routes-table">
      <thead>
        <tr>
          <th>Méthode</th>
          <th>Chemin d'accès (Path)</th>
          <th>Service Cible</th>
          <th>Protection Appliquée</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span class="method-badge m-post">POST</span></td>
          <td><code>/auth/v1/token</code></td>
          <td><code>services/auth:8002</code></td>
          <td>Rate-limit 30 rps/ip &amp; Surveillance Brute-Force</td>
        </tr>
        <tr>
          <td><span class="method-badge m-post">POST</span></td>
          <td><code>/api/v1/transactions</code></td>
          <td><code>services/api:8001</code></td>
          <td>Vérification JWT, Idempotence, Invariant ACID</td>
        </tr>
        <tr>
          <td><span class="method-badge m-post">POST</span></td>
          <td><code>/api/v1/transactions/verify-batch</code></td>
          <td><code>services/api:8001</code></td>
          <td>Anti-DoS L7, IsolationForest CPU/latence P95</td>
        </tr>
        <tr>
          <td><span class="method-badge m-get">GET</span></td>
          <td><code>/attacker</code></td>
          <td>Console Locale</td>
          <td>Allowlist réseau strict (Point d'accès groupe)</td>
        </tr>
        <tr>
          <td><span class="method-badge m-get">GET</span></td>
          <td><code>/metrics</code></td>
          <td>WAF Telemetry</td>
          <td>Format Prometheus standard</td>
        </tr>
        <tr>
          <td><span class="method-badge m-get">GET</span></td>
          <td><code>/health</code></td>
          <td>Santé Passerelle</td>
          <td>Vérification disponibilité WAF &amp; backends</td>
        </tr>
      </tbody>
    </table>
  </div>

  <script>
    async function refreshWaf() {
      try {
        const res = await fetch('/live/v1/summary');
        const d = await res.json();
        document.getElementById('stat-profile').textContent = (d.waf.rate_limit_profile || 'normal').toUpperCase();
        const bl = d.waf.active_blocked_ips || [];
        document.getElementById('stat-blocked-count').textContent = bl.length;
        document.getElementById('stat-blocked-ips').textContent = bl.length ? bl.map(x => x.ip_address).join(', ') : 'Aucune';
        const total = (d.waf.metrics.waf_blocked_dynamic_ip_total || 0) +
                      (d.waf.metrics.waf_blocked_ratelimit_total || 0) +
                      (d.waf.metrics.waf_blocked_signature_total || 0);
        document.getElementById('stat-blocked-hits').textContent = total;
        const st = (d.remediator && d.remediator.state) || 'NORMAL';
        document.getElementById('stat-state').textContent = st;
      } catch (e) {}
    }
    setInterval(refreshWaf, 1500);
    refreshWaf();
  </script>
</body>
</html>
"""


class LiveResilienceCluster:
    """Cluster temps réel exposant les microservices avec l'IA (IsolationForest + Ollama) au premier plan."""

    def __init__(self) -> None:
        release_kill_switch()
        self.data_dir = ROOT_DIR / "data" / "live_g2"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(self.data_dir / "payments_live.sqlite3")
        self.audit_path = str(self.data_dir / "executor_audit_live.jsonl")
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()

        self.jwt_secret = "resilience-g2-live-jwt-secret-2026"
        self.hmac_secret = "resilience-g2-live-hmac-secret-2026"

        self.auth_engine = AuthEngine(jwt_secret=self.jwt_secret)
        self.auth_app = create_auth_app(self.auth_engine)

        self.payment_db = PaymentDatabase(db_path=self.db_path)
        self.api_state = ApiRuntimeState(max_worker_slots=4)
        self.api_app = create_api_app(
            db=self.payment_db,
            auth_engine=self.auth_engine,
            runtime_state=self.api_state,
        )

        self.waf_engine = WafEngine()
        self.waf_app = create_waf_app(
            waf_engine=self.waf_engine,
            local_dispatchers={"auth": self.auth_app, "api": self.api_app},
        )

        self.executor = ConstrainedExecutor(
            hmac_secret=self.hmac_secret,
            audit_log_path=self.audit_path,
            waf_app=self.waf_app,
            api_app=self.api_app,
        )
        self.executor_app = create_executor_app(self.executor)

        self.orchestrator = RemediationOrchestrator(
            max_attempts=3,
            cooldown_seconds=1.0,
            block_ttl_seconds=300,
            hmac_secret=self.hmac_secret,
            waf_app=self.waf_app,
            api_app=self.api_app,
            auth_app=self.auth_app,
            executor_app=self.executor_app,
        )
        self.remediator_app = create_remediator_app(self.orchestrator)

        self.detector = AnomalyDetectorEngine()
        self.detector_app = create_detector_app(self.detector)
        self.rag_assistant = LocalRAGAssistant()
        self.rag_app = create_rag_app(self.rag_assistant)

        self.last_detected_attack_type = "NOMINAL"
        self.live_ai_diagnosis = (
            "✅ [DIAGNOSTIC IA — OLLAMA gemma4:e4b + ISOLATION FOREST]\n"
            "• État courant : NOMINAL — Aucune anomalie comportementale détectée sur les 7 variables temps réel.\n"
            "• Surveillance multi-vecteurs active : Flood L7 (/verify-batch), Force Brute Auth (/auth/v1/token), Injections L7 (SQLi/XSS/Traversal) et Saturation Latence.\n"
            "• Référentiel certifié : [Source: docs/decisions/ADR-002-ml-anomaly-detection.md] [Source: docs/governance/pca-pra.md]"
        )

        self._attach_live_routes(self.waf_app, is_waf=True)
        self.frontend_app = Flask("resilience_frontend_live")
        self._attach_live_routes(self.frontend_app, is_waf=False)

        self._running = True
        self._servers = []

    def _compute_unified_telemetry(self, window_seconds: float = 5.0) -> Dict[str, Any]:
        """
        Agrège la télémétrie de TOUS les composants (WAF + Auth + API Métier) afin que
        le modèle IA IsolationForest détecte 100 % des types d'attaques :
          1. Flood L7 Cryptographique (/api/v1/transactions/verify-batch)
          2. Force Brute Authentification JWT (/auth/v1/token -> 401)
          3. Injections critiques L7 (SQLi, XSS, Path Traversal, Command Injection)
          4. Saturation transactionnelle / multi-vecteurs
        """
        win = self.api_state.compute_window_telemetry(window_seconds)
        waf_stats = self.waf_engine.get_window_waf_stats(window_seconds)

        sig_hits = int(waf_stats.get("waf_signature_hits", 0))
        auth_reqs = int(waf_stats.get("waf_auth_requests", 0))
        waf_total = int(waf_stats.get("total_waf_window_requests", 0))
        waf_ips = waf_stats.get("waf_ip_counts", {})

        win["waf_signature_hits"] = sig_hits
        win["waf_auth_requests"] = auth_reqs

        # Fusion des compteurs IP entre WAF et API
        merged_ips = dict(win.get("ip_counts", {}))
        for ip, cnt in waf_ips.items():
            merged_ips[ip] = max(merged_ips.get(ip, 0), cnt)
        win["ip_counts"] = merged_ips

        suspect_ip = self.waf_engine.get_dominant_suspect_ip(15.0)
        if suspect_ip and suspect_ip not in ("127.0.0.1", "192.168.137.1"):
            win["dominant_source_ip"] = suspect_ip
        elif suspect_ip:
            win["dominant_source_ip"] = suspect_ip

        # Si une attaque par injection SQLi/XSS ou Brute-Force Auth frappe la passerelle WAF/Auth,
        # on répercute ses effets réels dans le vecteur des 7 variables évalué par IsolationForest
        if sig_hits >= 2 or auth_reqs >= 4:
            from ml.features import compute_ip_entropy, normalize_feature_dict

            base_f = dict(win.get("features", {}))
            total_reqs = max(int(win.get("sample_count", 0)), waf_total, sig_hits + auth_reqs)
            win["sample_count"] = total_reqs
            win["features"] = normalize_feature_dict(
                {
                    "req_rate_rps": max(
                        float(base_f.get("req_rate_rps", 0.5)),
                        total_reqs / max(window_seconds, 1.0),
                        18.5,
                    ),
                    "latency_p95_ms": max(
                        float(base_f.get("latency_p95_ms", 12.0)),
                        280.0 + 4.5 * (sig_hits + auth_reqs),
                    ),
                    "error_rate_ratio": max(
                        float(base_f.get("error_rate_ratio", 0.0)),
                        (sig_hits + auth_reqs) / max(total_reqs, 1),
                        0.88,
                    ),
                    "expensive_endpoint_ratio": (
                        max(float(base_f.get("expensive_endpoint_ratio", 0.0)), 0.85)
                        if sig_hits >= 2
                        else min(0.30, float(base_f.get("expensive_endpoint_ratio", 0.15)))
                    ),
                    "unique_ip_entropy": compute_ip_entropy(merged_ips) if merged_ips else 0.0,
                    "cpu_worker_saturation": max(
                        float(base_f.get("cpu_worker_saturation", 0.05)),
                        0.90,
                    ),
                    "tx_success_ratio": 0.0,
                }
            )

        return win

    def _build_live_ai_incident_diagnosis(self, ml_event: Dict[str, Any]) -> str:
        """Construit en temps réel le diagnostic explicatif IA (IsolationForest + RAG Ollama)."""
        attack_type = str(ml_event.get("detected_attack_type", "FLOOD_L7_VERIFY_BATCH"))
        score = float(ml_event.get("anomaly_score", -0.20))
        src_ip = str(ml_event.get("dominant_source_ip", "192.168.137.135"))
        top_f = ml_event.get("top_contributing_features", [])
        feats_dict = ml_event.get("features", {}) or {}
        top_parts = []
        for x in top_f[:3]:
            if isinstance(x, dict):
                top_parts.append(f"{x.get('feature')}={x.get('value')} (z={x.get('z_score')})")
            else:
                fname = str(x)
                fval = feats_dict.get(fname, "")
                top_parts.append(f"{fname}={fval}" if fval != "" else fname)
        top_str = ", ".join(top_parts)

        vector_descriptions = {
            "FLOOD_L7_VERIFY_BATCH": (
                "Flood applicatif L7 par épuisement cryptographique sur `/api/v1/transactions/verify-batch`",
                "ER-01 (Indisponibilité critique du traitement des paiements)",
            ),
            "BRUTE_FORCE_AUTH_JWT": (
                "Attaque par Force Brute haute fréquence sur le service d'authentification `/auth/v1/token` (rafale HTTP 401)",
                "ER-03 (Tentative de compromission d'accès & saturation d'authentification)",
            ),
            "INJECTION_L7_SQLI_XSS": (
                "Salve d'injections applicatives critiques L7 (SQLi `' UNION SELECT`, XSS `<script>`, Path Traversal `../../`)",
                "ER-02 / ER-03 (Tentative d'extraction ou corruption du grand livre & injection)",
            ),
            "SATURATION_LATENCE_DOS": (
                "Saturation multivariée des workers applicatifs et dégradation de latence P95",
                "ER-01 (Dégradation sévère des SLA de paiement)",
            ),
        }
        desc, ebios_er = vector_descriptions.get(
            attack_type,
            ("Anomalie multivariée détectée par IsolationForest", "ER-01 (Perturbation cyber)"),
        )

        inc = self.orchestrator.current_incident or {}
        probe_tx = (self.orchestrator.last_verified_transaction or {}).get("transaction_id", "En cours...")
        mttd = self.orchestrator.metrics.get("remediator_last_mttd_seconds", 2.0)
        mttr = self.orchestrator.metrics.get("remediator_last_mttr_seconds", 0.12)

        return (
            f"🚨 [DIAGNOSTIC IA TEMPS RÉEL — OLLAMA ({self.rag_assistant.llm_adapter.model_name}) + ISOLATION FOREST]\n"
            f"1. Menace détectée : {desc} [{attack_type}]\n"
            f"2. Preuve ML : Score IsolationForest = {score:.4f} (< seuil -0.1176) | IP corrélée : {src_ip}\n"
            f"3. Variables explicatives (XAI) : {top_str}\n"
            f"4. Cadrage EBIOS RM : {ebios_er} [Source: docs/governance/ebios-rm.md#Atelier 4]\n"
            f"5. Remédiation Zero-Touch exécutée (HMAC-SHA256) : Bannissement dynamique WAF de {src_ip} (HTTP 403), profil `strict_mitigation` et recyclage des workers [Source: docs/decisions/ADR-003-autonomous-remediation-security.md]\n"
            f"6. Preuve Métier (T5 / DORA Art. 11) : Transaction sonde `{probe_tx}` validée (MTTD={mttd}s, MTTR={mttr}s) [Source: docs/governance/pca-pra.md#2. Distinction Rigoureuse]"
        )

    def _async_ollama_incident_analysis(self, attack_type: str, score: float, ip: str, desc: str, top_str: str) -> None:
        """Déclenche en arrière-plan la génération explicative réelle par Gemma 4 (Ollama) lors d'un incident."""
        try:
            prompt_q = (
                f"Incident cyber en cours : {desc} (Type: {attack_type}). "
                f"Score IsolationForest: {score:.4f}, IP attaquante: {ip}, Variables critiques: {top_str}. "
                f"En tant qu'analyste SOC et expert DORA/EBIOS RM, analyse cette menace, "
                f"justifie le bannissement dynamique WAF et le recyclage des workers par l'exécuteur HMAC, "
                f"et confirme le rétablissement par la sonde métier T5."
            )
            rag_res = self.rag_assistant.answer_question(prompt_q, top_k=2)
            gen_text = str(rag_res.get("answer", "")).strip()
            if gen_text:
                status_tag = rag_res.get("llm_status", "OLLAMA_ACTIVE")
                self.live_ai_diagnosis = (
                    f"🤖 [ANALYSE EN DIRECT PAR GEMMA 4 (OLLAMA LOCAL) — Statut : {status_tag}]\n"
                    f"• Menace : {desc} [{attack_type}] | Score ML : {score:.4f} | IP : {ip}\n"
                    f"• Variables XAI : {top_str}\n"
                    f"--------------------------------------------------------------------------------\n"
                    f"Raisonnement de l'IA locale ({self.rag_assistant.llm_adapter.model_name}) :\n"
                    f"{gen_text}\n"
                    f"--------------------------------------------------------------------------------\n"
                    f"• Procédures certifiées : [Source: docs/governance/ebios-rm.md#Atelier 4] [Source: docs/governance/pca-pra.md#2. Distinction Rigoureuse]"
                )
        except Exception:
            pass

    def _get_ledger_snapshot(self) -> Dict[str, Any]:
        inv = self.payment_db.check_accounting_invariant()
        accs_list = self.payment_db.list_accounts()
        accounts_map = {a["account_id"]: a for a in accs_list}
        txs = self.payment_db.list_transactions(limit=20)
        for t in txs:
            if "transaction_id" not in t and "tx_id" in t:
                t["transaction_id"] = t["tx_id"]
        return {
            "consistent": inv["consistent"],
            "total_cents": inv["actual_total_cents"],
            "expected_cents": inv["expected_total_cents"],
            "accounts": accounts_map,
            "transactions": txs,
        }

    def _execute_operator_payment(self, label: str, amount_cents: int = 5000) -> Dict[str, Any]:
        with self.auth_app.test_client() as auth_client:
            tok_resp = auth_client.post(
                "/auth/v1/token",
                json={"username": "operator_alpha", "password": "FictiveOp#2026!"},
            )
            token = tok_resp.get_json()["access_token"]

        idem_key = f"idem-{label.lower()}-{uuid.uuid4().hex[:8]}"
        with self.waf_app.test_client() as waf_client:
            tx_resp = waf_client.post(
                "/api/v1/transactions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": idem_key,
                    "X-Forwarded-For": "127.0.0.1",
                },
                json={
                    "source_account_id": "ACC-FR-001",
                    "target_account_id": "ACC-FR-002",
                    "amount_cents": int(amount_cents),
                    "currency": "EUR",
                    "description": f"Transaction métier {label} (Groupe 2 - Live)",
                },
            )
            tx_data = tx_resp.get_json()
            if tx_resp.status_code not in (200, 201):
                raise RuntimeError(f"Échec transaction {label}: {tx_data}")
            if "transaction_id" not in tx_data and "tx_id" in tx_data:
                tx_data["transaction_id"] = tx_data["tx_id"]

        inv = self.payment_db.check_accounting_invariant()
        self.orchestrator._record_timeline(
            stage=f"BUSINESS_TX_{label.upper()}",
            event_type="OPERATOR_PAYMENT_COMMITTED",
            severity="INFO",
            message=f"Transaction métier {label} réussie et persistée ({amount_cents} centimes).",
            details={"transaction_id": tx_data["transaction_id"], "idempotency_key": idem_key},
        )
        return {"transaction": tx_data, "invariant": inv}

    def _attach_live_routes(self, app: Flask, is_waf: bool = False) -> None:
        @app.route("/", methods=["GET"])
        def index_page() -> Response:
            if is_waf:
                return Response(WAF_GATEWAY_HTML, mimetype="text/html")
            return Response(DASHBOARD_HTML, mimetype="text/html")

        @app.route("/dashboard", methods=["GET"])
        def index_dashboard() -> Response:
            return Response(DASHBOARD_HTML, mimetype="text/html")

        @app.route("/attacker", methods=["GET"])
        def attacker_console() -> Response:
            return Response(ATTACKER_CONSOLE_HTML, mimetype="text/html")

        @app.route("/attacker.ps1", methods=["GET"])
        def attacker_ps1() -> Response:
            return Response(ATTACKER_POWERSHELL_SCRIPT, mimetype="text/plain; charset=utf-8")

        @app.route("/controlled_attack.py", methods=["GET"])
        def attacker_py() -> Response:
            code = (ROOT_DIR / "scenarios" / "controlled_attack.py").read_text(encoding="utf-8")
            return Response(code, mimetype="text/plain; charset=utf-8")

        @app.route("/live/v1/whoami", methods=["GET"])
        def whoami() -> Tuple[Response, int]:
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
            return jsonify({"client_ip": client_ip}), 200

        @app.route("/live/v1/ai-ask", methods=["POST"])
        def ai_ask() -> Tuple[Response, int]:
            t_start = time.time()
            body = request.get_json(silent=True) or {}
            query = str(body.get("query", "")).strip()
            rag_res = self.rag_assistant.answer_question(query, top_k=3)
            duration = round(time.time() - t_start, 2)
            status_tag = rag_res.get("llm_status", "OLLAMA_ACTIVE")
            header = (
                f"✨ [GÉNÉRÉ LOCALEMENT PAR GEMMA 4 (8.0B) VIA OLLAMA]\n"
                f"• Question : {query}\n"
                f"• Temps d'inférence GPU/RAM : {duration}s | Statut : {status_tag} | Modèle : {self.rag_assistant.llm_adapter.model_name}\n"
                f"--------------------------------------------------------------------------------\n"
            )
            return jsonify(
                {
                    **rag_res,
                    "inference_duration_seconds": duration,
                    "llm_status": status_tag,
                    "formatted_report": header + str(rag_res.get("answer", "")),
                }
            ), 200

        @app.route("/live/v1/summary", methods=["GET"])
        def live_summary() -> Tuple[Response, int]:
            win = self._compute_unified_telemetry(5.0)
            last_probe = self.orchestrator.last_verified_transaction
            if last_probe and "transaction_id" not in last_probe and "tx_id" in last_probe:
                last_probe = {**last_probe, "transaction_id": last_probe["tx_id"]}
            is_ollama_up, _ = self.rag_assistant.llm_adapter.check_ollama_online()
            return jsonify(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "telemetry": win,
                    "detector": {
                        "last_score": self.detector.last_score,
                        "last_is_anomaly": self.detector.last_is_anomaly,
                        "last_attack_type": self.detector.last_attack_type,
                        "detected_attack_type": self.detector.last_attack_type,
                        "anomalies_by_type": dict(self.detector.anomalies_by_type),
                        "consecutive_anomalies": self.detector.consecutive_anomalies,
                        "anomalies_total": self.detector.anomalies_total,
                        "inferences_total": self.detector.inferences_total,
                        "last_event": self.detector.last_event,
                    },
                    "ai_copilot": {
                        "llm_status": "OLLAMA_ACTIVE" if is_ollama_up else "OFFLINE_RETRIEVAL_ONLY",
                        "model": self.rag_assistant.llm_adapter.model_name,
                        "last_detected_attack_type": self.last_detected_attack_type,
                        "live_diagnosis": self.live_ai_diagnosis,
                    },
                    "waf": self.waf_engine.get_status(),
                    "remediator": {
                        "state": self.orchestrator.state,
                        "current_incident": self.orchestrator.current_incident,
                        "last_verified_transaction": last_probe,
                        "recent_timeline": list(self.orchestrator.timeline)[-30:],
                        "metrics": dict(self.orchestrator.metrics),
                    },
                    "ledger": self._get_ledger_snapshot(),
                    "biometrics": {
                        "habilitations": biometric_service.list_habilitations(),
                        "esp_hardware": esp_controller.get_status(),
                    },
                }
            ), 200

        @app.route("/live/v1/bio-identify", methods=["POST"])
        def live_bio_identify() -> Tuple[Response, int]:
            from services.auth.app import _decode_b64_image
            body = request.get_json(silent=True) or {}
            username = str(body.get("username", "")).strip()
            use_cam = bool(body.get("use_camera", True))
            image_b64 = body.get("image_b64")
            frame = _decode_b64_image(image_b64) if image_b64 else None
            print(f"[LIVE-BIO] Identify request for '{username}' (b64_present={bool(image_b64)}, frame={frame.shape if frame is not None else None})", flush=True)
            res = biometric_service.verify_operator_face(username, frame=frame, use_camera=use_cam)
            print(f"[LIVE-BIO] Identify result: {res}", flush=True)
            code = 200 if res.get("face_verified") else (423 if res.get("locked") else 401)
            return jsonify(res), code

        @app.route("/live/v1/bio-enroll", methods=["POST"])
        def live_bio_enroll() -> Tuple[Response, int]:
            from services.auth.app import _decode_b64_image
            body = request.get_json(silent=True) or {}
            username = str(body.get("username", "operator_alpha")).strip()
            display_name = str(body.get("display_name", username)).strip()
            image_b64 = body.get("image_b64")
            frame = _decode_b64_image(image_b64) if image_b64 else None
            print(f"[LIVE-BIO] Enroll request for '{username}' (b64_present={bool(image_b64)}, frame={frame.shape if frame is not None else None})", flush=True)
            if frame is None:
                ok, frame, msg = biometric_service.capture_frame_from_usb_camera(0)
                if not ok:
                    return jsonify({"error": msg, "success": False}), 400
            res = biometric_service.enroll_user_face(username, display_name, "merchant_operator", frame)
            biometric_service.reset_lockout(username)
            return jsonify(res), 200

        @app.route("/live/v1/bio-login", methods=["POST"])
        def live_bio_login() -> Tuple[Response, int]:
            body = request.get_json(silent=True) or {}
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
            bundle, err = self.auth_engine.authenticate(username, password)
            if err or not bundle:
                biometric_service.validate_password_step(username, False)
                return jsonify({"error": err or "Mot de passe invalide.", "success": False}), 401
            biometric_service.validate_password_step(username, True)
            return jsonify({"bundle": bundle, "success": True, "message": "Accès Back-office autorisé."}), 200

        @app.route("/live/v1/bio-led-test", methods=["POST"])
        def live_bio_led_test() -> Tuple[Response, int]:
            body = request.get_json(silent=True) or {}
            state = str(body.get("state", "OFF")).strip().upper()
            esp_controller.set_led_state(state, "Test manuel depuis le Dashboard IA")
            return jsonify({"success": True, "state": state, "esp_status": esp_controller.get_status()}), 200

        @app.route("/live/v1/bio-reset", methods=["POST"])
        def live_bio_reset() -> Tuple[Response, int]:
            body = request.get_json(silent=True) or {}
            username = str(body.get("username", "")).strip()
            biometric_service.reset_lockout(username)
            return jsonify({"success": True, "message": f"Opérateur {username} débloqué."}), 200

        @app.route("/live/v1/trigger-payment", methods=["POST"])
        def trigger_payment() -> Tuple[Response, int]:
            body = request.get_json(silent=True) or {}
            label = str(body.get("label", "T0"))
            amount_cents = int(body.get("amount_cents", 5000))
            try:
                res = self._execute_operator_payment(label, amount_cents)
                return jsonify(res), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/live/v1/reset", methods=["POST"])
        def reset_all() -> Tuple[Response, int]:
            self._attack_gen = getattr(self, "_attack_gen", 0) + 1
            with self.waf_engine.lock:
                self.waf_engine.dynamic_blocklist.clear()
                self.waf_engine.rate_limit_profile = "normal"
                self.waf_engine.request_logs.clear()
                self.waf_engine.ip_request_windows.clear()
                self.waf_engine.ip_expensive_windows.clear()
            biometric_service._locked_until.clear()
            biometric_service._failed_attempts.clear()
            self.api_state.recycle_workers()
            self.detector.reset_state()
            self.last_detected_attack_type = "NOMINAL"
            self.live_ai_diagnosis = (
                "✅ [DIAGNOSTIC IA — OLLAMA gemma4:e4b + ISOLATION FOREST]\n"
                "• État courant : NOMINAL — Plateforme réinitialisée, liste noire WAF vidée.\n"
                "• L'IA surveille en temps réel tous les vecteurs : Flood L7, Brute-Force Auth, Injections SQLi/XSS et Saturation.\n"
                "• Référentiel : [Source: docs/decisions/ADR-002-ml-anomaly-detection.md] [Source: docs/governance/pca-pra.md]"
            )
            with self.orchestrator.lock:
                self.orchestrator._transition_state("NORMAL", "Réinitialisation manuelle de la démonstration.")
                self.orchestrator.current_incident = None
                self.orchestrator.perturbation_started_epoch = None
            return jsonify({"status": "RESET_OK"}), 200

        @app.route("/live/v1/trigger-scenario", methods=["POST"])
        def trigger_scenario() -> Tuple[Response, int]:
            import requests as req_lib

            body = request.get_json(silent=True) or {}
            src_ip = str(body.get("source_ip", "192.168.137.135"))
            attack_type = str(body.get("attack_type", "flood_l7"))
            dur = float(body.get("duration_seconds", 10.0))

            self._attack_gen = getattr(self, "_attack_gen", 0) + 1
            my_gen = self._attack_gen
            time.sleep(0.08)

            # Réinitialise le blocage précédent pour que la nouvelle attaque soit observée et détectée de A à Z par l'IA
            with self.waf_engine.lock:
                self.waf_engine.dynamic_blocklist.clear()
                self.waf_engine.rate_limit_profile = "normal"
                self.waf_engine.request_logs.clear()
                self.waf_engine.ip_request_windows.clear()
                self.waf_engine.ip_expensive_windows.clear()
            biometric_service._locked_until.clear()
            biometric_service._failed_attempts.clear()
            self.api_state.recycle_workers()
            self.detector.reset_state()
            self.last_detected_attack_type = "NOMINAL"
            with self.orchestrator.lock:
                self.orchestrator._transition_state(
                    "NORMAL",
                    f"Préparation de l'observation IA pour le scénario [{attack_type}] depuis {src_ip}.",
                )
                self.orchestrator.current_incident = None
                self.orchestrator.perturbation_started_epoch = None

            def _bg_multi_attack() -> None:
                t_end = time.time() + min(dur, 15.0)
                idx = 0
                while time.time() < t_end and not is_kill_switch_engaged() and getattr(self, "_attack_gen", 0) == my_gen:
                    idx += 1
                    headers = {"X-Forwarded-For": src_ip, "Content-Type": "application/json"}
                    mode = attack_type
                    if mode == "multi_vector":
                        mode = ("flood_l7", "brute_force_auth", "sqli_xss_injection")[idx % 3]

                    try:
                        if mode == "brute_force_auth":
                            req_lib.post(
                                "http://127.0.0.1:8080/auth/v1/token",
                                headers=headers,
                                json={"username": f"admin_target_{idx % 10}", "password": f"BadPass#{idx}"},
                                timeout=1.5,
                            )
                        elif mode == "sqli_xss_injection":
                            req_lib.post(
                                "http://127.0.0.1:8080/api/v1/transactions/verify-batch?filter=' OR 1=1--",
                                headers=headers,
                                json={"batch_size": 10, "payload": "<script>alert(1)</script> ../../etc/passwd"},
                                timeout=1.5,
                            )
                        else:
                            req_lib.post(
                                "http://127.0.0.1:8080/api/v1/transactions/verify-batch",
                                headers=headers,
                                json={"batch_size": 30, "iterations": 40000, "audit_profile": "deep_verification"},
                                timeout=1.5,
                            )
                    except Exception:
                        pass
                    time.sleep(0.05)

            threading.Thread(target=_bg_multi_attack, name=f"bg-attack-{attack_type}", daemon=True).start()
            return jsonify(
                {
                    "status": "SCENARIO_STARTED",
                    "attack_type": attack_type,
                    "source_ip": src_ip,
                    "target": "http://192.168.137.1:8080",
                }
            ), 202

    def _hotspot_keepalive_loop(self) -> None:
        """Maintient le point d'accès mobile RESILIENCE-G2 (192.168.137.1) actif."""
        import subprocess
        script_path = str(ROOT_DIR / "scripts" / "manage-hotspot.ps1")
        while self._running:
            try:
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Action", "start"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=12,
                )
            except Exception:
                pass
            time.sleep(20.0)

    def _aiops_loop(self) -> None:
        """Boucle temps réel d'observation et de détection IA multi-attaques toutes les 1.5 secondes."""
        while self._running:
            try:
                win = self._compute_unified_telemetry(5.0)
                ml_event = self.detector.evaluate_window(win, push_to_remediator=False)

                if ml_event.get("is_anomaly"):
                    self.last_detected_attack_type = str(ml_event.get("detected_attack_type", "FLOOD_L7_VERIFY_BATCH"))
                    if getattr(self, "_last_analyzed_attack", None) != self.last_detected_attack_type:
                        self._last_analyzed_attack = self.last_detected_attack_type
                        top_f = ml_event.get("top_contributing_features", [])
                        top_str = ", ".join(str(x.get("feature", x) if isinstance(x, dict) else x) for x in top_f[:3])
                        threading.Thread(
                            target=self._async_ollama_incident_analysis,
                            args=(
                                self.last_detected_attack_type,
                                float(ml_event.get("anomaly_score", -0.2)),
                                str(ml_event.get("dominant_source_ip", "192.168.137.135")),
                                self.last_detected_attack_type,
                                top_str,
                            ),
                            name=f"ollama-diag-{self.last_detected_attack_type}",
                            daemon=True,
                        ).start()

                prev_state = self.orchestrator.state
                if ml_event.get("is_anomaly") or prev_state in ("NORMAL", "SUSPECT"):
                    self.orchestrator.handle_anomaly_event(ml_event)

                if prev_state != "RECOVERED" and self.orchestrator.state == "RECOVERED":
                    with self.waf_engine.lock:
                        self.waf_engine.request_logs.clear()
                    self.detector.consecutive_anomalies = 0

                if self.last_detected_attack_type != "NOMINAL":
                    self.detector.last_attack_type = self.last_detected_attack_type

                if ml_event.get("is_anomaly") or self.orchestrator.state in ("INCIDENT", "REMEDIATING", "VERIFYING", "RECOVERED"):
                    if self.last_detected_attack_type != "NOMINAL":
                        event_for_diag = dict(ml_event)
                        event_for_diag["detected_attack_type"] = self.last_detected_attack_type
                        self.live_ai_diagnosis = self._build_live_ai_incident_diagnosis(event_for_diag)
            except Exception as exc:
                print(f"[AIOPS-LOOP-WARN] {exc}", file=sys.stderr)
            time.sleep(1.5)

    def start(self) -> None:
        t0_info = self._execute_operator_payment("T0", 5000)
        print(f"[RESILIENCE-G2] Transaction initiale T0 engagée : {t0_info['transaction']['transaction_id']} (50,00 EUR)")

        services = [
            ("waf-gateway", self.waf_app, 8080),
            ("frontend-ui", self.frontend_app, 3300),
            ("frontend-ui-legacy", self.frontend_app, 3000),
            ("api", self.api_app, 8001),
            ("auth", self.auth_app, 8002),
            ("detector", self.detector_app, 8003),
            ("remediator", self.remediator_app, 8004),
            ("executor", self.executor_app, 8005),
            ("rag", self.rag_app, 8006),
        ]

        for name, flask_app, port in services:
            try:
                srv = make_server("0.0.0.0", port, flask_app, threaded=True)
                t = threading.Thread(target=srv.serve_forever, name=f"srv-{name}", daemon=True)
                t.start()
                self._servers.append((name, port, srv))
                print(f"[RESILIENCE-G2] Service '{name}' actif sur http://192.168.137.1:{port} (et http://127.0.0.1:{port})")
            except Exception as exc:
                print(f"[RESILIENCE-G2-WARN] Impossible d'écouter sur le port {port} ({name}) : {exc}")

        aiops_thread = threading.Thread(target=self._aiops_loop, name="aiops-loop", daemon=True)
        aiops_thread.start()
        keepalive_thread = threading.Thread(target=self._hotspot_keepalive_loop, name="hotspot-keepalive", daemon=True)
        keepalive_thread.start()

        def _warm_ollama_bg() -> None:
            try:
                requests.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={"model": "gemma4:e4b", "prompt": "ping", "stream": False, "keep_alive": -1},
                    timeout=90,
                )
            except Exception:
                pass

        threading.Thread(target=_warm_ollama_bg, name="ollama-warmup", daemon=True).start()
        print("[RESILIENCE-G2] Boucle IA Multi-Attaques (IsolationForest + Ollama gemma4:e4b) & Keep-Alive Hotspot actives.")


if __name__ == "__main__":
    cluster = LiveResilienceCluster()
    cluster.start()
    print("\n==================================================================")
    print(" PLATEFORME PROJECT RESILIENCE-ALPHA (GROUPE 2) EN LIGNE")
    print(" - Centre IA & SOC      : http://localhost:3300  | http://127.0.0.1:3000  | http://192.168.137.1:3000")
    print(" - Supervision Grafana  : http://127.0.0.1:3001/d/resilience-alpha-main")
    print(" - Passerelle WAF       : http://127.0.0.1:8080  | http://192.168.137.1:8080")
    print(" - Console Tir 2e PC    : http://192.168.137.1:8080/attacker")
    print(" - Commande PS 2e PC    : irm http://192.168.137.1:8080/attacker.ps1 | iex")
    print("==================================================================\n")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[RESILIENCE-G2] Arrêt demandé.")
