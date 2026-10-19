"""
PROJECT RESILIENCE-ALPHA — Serveur Temps Réel Multi-Services (PC Hôte 192.168.137.1 & 127.0.0.1)
Groupe 2 (G2) : Lenny BARRESI, Youssef HANSIL, Pierre MICHAUD-EYMOZ, Rohail ARSHAD

Démarre l'ensemble des microservices interconnectés sur le PC Hôte :
  - Port 8080 : Passerelle WAF L7 + Proxy inverse + Console de tir 2e PC (/attacker, /attacker.ps1)
  - Port 3000 : Portail de Paiement & Centre de Commandement SOC / AIOps Temps Réel
  - Port 8001 : API Métier de Paiement (ACID, Centimes entiers, Idempotence)
  - Port 8002 : Service d'Authentification JWT HS256 & RBAC
  - Port 8003 : Détecteur ML IsolationForest (7 variables temps réel)
  - Port 8004 : Orchestrateur de Remédiation Autonome & Sonde Métier Post-Incident
  - Port 8005 : Exécuteur Confiné (Signature HMAC-SHA256, Allowlist fermée, Audit chaîné SHA-256)
  - Port 8006 : Assistant Documentaire RAG Local (Citations des sources)
Ainsi que la boucle AIOps temps réel (évaluation ML toutes les 2 secondes).
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
from services.detector.app import AnomalyDetectorEngine, create_app as create_detector_app
from services.executor.app import ConstrainedExecutor, create_executor_app
from services.rag.app import create_app as create_rag_app
from services.remediator.app import RemediationOrchestrator, create_remediator_app
from services.waf_gateway.app import WafEngine, create_waf_app


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>PROJECT RESILIENCE-ALPHA — Groupe 2 (G2) — Live Command Center</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {
      --bg: #0b1020;
      --panel: #131c33;
      --border: #243256;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --green: #10b981;
      --amber: #f59e0b;
      --red: #ef4444;
      --blue: #3b82f6;
      --purple: #8b5cf6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 16px;
      line-height: 1.45;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 20px;
      margin-bottom: 16px;
    }
    .title-block h1 { font-size: 1.25rem; color: #fff; }
    .title-block p { font-size: 0.82rem; color: var(--muted); }
    .badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.85rem;
      letter-spacing: 0.5px;
    }
    .state-NORMAL { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }
    .state-SUSPECT { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    .state-INCIDENT, .state-REMEDIATING, .state-FAILED { background: rgba(239,68,68,0.25); color: #f87171; border: 1px solid #ef4444; }
    .state-VERIFYING { background: rgba(59,130,246,0.25); color: #60a5fa; border: 1px solid #3b82f6; }
    .state-RECOVERED { background: rgba(16,185,129,0.3); color: #6ee7b7; border: 2px solid #10b981; }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-bottom: 14px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 14px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }
    .card h2 {
      font-size: 0.95rem;
      color: #93c5fd;
      margin-bottom: 10px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 6px;
      display: flex;
      justify-content: space-between;
    }
    .kpi-row {
      display: flex;
      justify-content: space-between;
      margin: 6px 0;
      font-size: 0.86rem;
    }
    .kpi-val { font-family: Consolas, monospace; font-weight: 700; }
    button {
      background: var(--blue);
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 8px 12px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.83rem;
      margin-right: 6px;
      margin-top: 6px;
    }
    button:hover { opacity: 0.92; }
    button.green { background: var(--green); }
    button.amber { background: var(--amber); color: #111; }
    button.red { background: var(--red); }
    table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-top: 6px; }
    th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); }
    .mono { font-family: Consolas, monospace; }
    .log-box {
      max-height: 210px;
      overflow-y: auto;
      font-family: Consolas, monospace;
      font-size: 0.77rem;
      background: #080c18;
      padding: 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .log-item { padding: 4px 0; border-bottom: 1px dashed #1e293b; }
    .chain-bar {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }
    .step-box {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 0.78rem;
      text-align: center;
    }
    .step-box.done {
      border-color: var(--green);
      background: rgba(16,185,129,0.12);
    }
    .step-box strong { display: block; font-size: 0.85rem; margin-bottom: 2px; }
  </style>
</head>
<body>
  <header>
    <div class="title-block">
      <h1>PROJECT RESILIENCE-ALPHA — Groupe 2 (G2)</h1>
      <p>Lenny BARRESI • Youssef HANSIL • Pierre MICHAUD-EYMOZ • Rohail ARSHAD | Hôte: 192.168.137.1 | 2e PC: 192.168.137.135</p>
    </div>
    <div>
      <span id="state-badge" class="badge state-NORMAL">ÉTAT : NORMAL</span>
    </div>
  </header>

  <div class="chain-bar">
    <div id="step-t0" class="step-box"><strong>T0 : Transaction Initiale</strong><span id="step-t0-txt">En attente</span></div>
    <div id="step-t1" class="step-box"><strong>T1 : Tir 2e PC (192.168.137.135)</strong><span id="step-t1-txt">En attente</span></div>
    <div id="step-t2" class="step-box"><strong>T2 : Dégradation API</strong><span id="step-t2-txt">Latence nominale</span></div>
    <div id="step-t3" class="step-box"><strong>T3 : Détection ML (IsolationForest)</strong><span id="step-t3-txt">Score normal</span></div>
    <div id="step-t4" class="step-box"><strong>T4 : Remédiation HMAC + WAF</strong><span id="step-t4-txt">Aucune IP bloquée</span></div>
    <div id="step-t5" class="step-box"><strong>T5 : Preuve Métier Finale</strong><span id="step-t5-txt">En attente</span></div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>1. Opérations Métier & Contrôles (T0 / T5)</h2>
      <div class="kpi-row"><span>Invariant Comptable (3 comptes) :</span><span id="inv-status" class="kpi-val" style="color:#34d399">27 500,00 EUR (OK)</span></div>
      <div class="kpi-row"><span>ACC-FR-001 ( Émetteur ) :</span><span id="bal-1" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>ACC-FR-002 ( Marchand ) :</span><span id="bal-2" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>Transactions engagées :</span><span id="tx-count" class="kpi-val">0</span></div>
      <div style="margin-top:10px">
        <button class="green" onclick="executePayment('T0')">Exécuter Transaction T0 (50,00 EUR)</button>
        <button class="red" onclick="triggerLiveScenario()">Lancer Scénario 2e PC (192.168.137.135)</button>
        <button class="green" onclick="executePayment('T5')">Exécuter Transaction T5 (25,00 EUR)</button>
        <button class="amber" onclick="resetPlatform()">Réinitialiser Démo</button>
      </div>
      <div id="tx-feedback" style="margin-top:8px;font-size:0.8rem;color:#6ee7b7;"></div>
    </div>

    <div class="card">
      <h2>2. Détection ML Temps Réel (IsolationForest)</h2>
      <div class="kpi-row"><span>Score d'anomalie courant :</span><span id="ml-score" class="kpi-val">0.0000</span></div>
      <div class="kpi-row"><span>Seuil calibré (2 fenêtres) :</span><span class="kpi-val">-0.0850</span></div>
      <div class="kpi-row"><span>Fenêtres anormales consécutives :</span><span id="ml-consec" class="kpi-val">0 / 2</span></div>
      <div class="kpi-row"><span>Débit observé (req/s) :</span><span id="feat-rps" class="kpi-val">0.5</span></div>
      <div class="kpi-row"><span>Latence P95 API (ms) :</span><span id="feat-lat" class="kpi-val">12.0 ms</span></div>
      <div class="kpi-row"><span>Saturation Workers CPU :</span><span id="feat-sat" class="kpi-val">5%</span></div>
      <div class="kpi-row"><span>IP Source Dominante :</span><span id="feat-ip" class="kpi-val">127.0.0.1</span></div>
    </div>

    <div class="card">
      <h2>3. WAF Dynamique, Remédiation & Sonde Métier</h2>
      <div class="kpi-row"><span>Profil WAF Actif :</span><span id="waf-profile" class="kpi-val">normal</span></div>
      <div class="kpi-row"><span>IP Bloquées par AIOps :</span><span id="waf-blocked-ips" class="kpi-val" style="color:#f87171">Aucune</span></div>
      <div class="kpi-row"><span>Requêtes d'attaque rejetées (403/429) :</span><span id="waf-blocked-hits" class="kpi-val">0</span></div>
      <div class="kpi-row"><span>MTTD / MTTR mesurés :</span><span id="mttd-mttr" class="kpi-val">—</span></div>
      <div class="kpi-row"><span>Dernière Sonde Métier (T5) :</span><span id="probe-tx" class="kpi-val">—</span></div>
      <div style="margin-top:8px;font-size:0.78rem;color:var(--muted);">
        Console 2e PC : <a href="/attacker" target="_blank" style="color:#60a5fa">http://192.168.137.1:8080/attacker</a>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Chronologie SOC & Automate d'Incident (Temps Réel)</h2>
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
    let t5Done = false;

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
          if (label === 'T0') t0Done = true;
          if (label === 'T5') t5Done = true;
          fb.style.color = '#34d399';
          fb.textContent = `[PASS] ${label} engagée : ID=${data.transaction.transaction_id} | ${(data.transaction.amount_cents/100).toFixed(2)} EUR | Invariant=${data.invariant.consistent}`;
          refreshState();
        } else {
          fb.style.color = '#f87171';
          fb.textContent = `[ERREUR] ${JSON.stringify(data)}`;
        }
      } catch (e) {
        fb.style.color = '#f87171';
        fb.textContent = `[ERREUR] ${e}`;
      }
    }

    async function resetPlatform() {
      await fetch('/live/v1/reset', {method: 'POST'});
      t0Done = false;
      t5Done = false;
      document.querySelectorAll('.step-box').forEach(el => el.classList.remove('done'));
      document.getElementById('tx-feedback').textContent = 'Plateforme réinitialisée à l\\'état NORMAL.';
      refreshState();
    }

    async function triggerLiveScenario() {
      const fb = document.getElementById('tx-feedback');
      fb.style.color = '#fbbf24';
      fb.textContent = 'Tir contrôlé lancé depuis 192.168.137.135 vers 192.168.137.1:8080 (observation ML en cours)...';
      await fetch('/live/v1/trigger-scenario', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source_ip: '192.168.137.135', duration_seconds: 12, rate_rps: 25})
      });
    }

    async function refreshState() {
      try {
        const res = await fetch('/live/v1/summary');
        const s = await res.json();

        const st = s.remediator.state;
        const badge = document.getElementById('state-badge');
        badge.textContent = 'ÉTAT : ' + st;
        badge.className = 'badge state-' + st;

        // Comptes et transactions
        document.getElementById('inv-status').textContent =
          (s.ledger.total_cents / 100).toFixed(2) + ' EUR (' + (s.ledger.consistent ? 'INTÈGRE' : 'ERREUR') + ')';
        const accs = s.ledger.accounts || {};
        if (accs['ACC-FR-001']) document.getElementById('bal-1').textContent = (accs['ACC-FR-001'].balance_cents / 100).toFixed(2) + ' EUR';
        if (accs['ACC-FR-002']) document.getElementById('bal-2').textContent = (accs['ACC-FR-002'].balance_cents / 100).toFixed(2) + ' EUR';
        document.getElementById('tx-count').textContent = s.ledger.transactions.length;

        // ML
        const ml = s.detector;
        const feat = s.telemetry.features || {};
        document.getElementById('ml-score').textContent = (ml.last_score || 0).toFixed(4);
        document.getElementById('ml-score').style.color = ml.last_is_anomaly ? '#f87171' : '#34d399';
        document.getElementById('ml-consec').textContent = ml.consecutive_anomalies + ' / 2';
        document.getElementById('feat-rps').textContent = (feat.req_rate_rps || 0).toFixed(1) + ' req/s';
        document.getElementById('feat-lat').textContent = (feat.latency_p95_ms || 0).toFixed(1) + ' ms';
        document.getElementById('feat-sat').textContent = Math.round((feat.cpu_worker_saturation || 0) * 100) + '%';
        document.getElementById('feat-ip').textContent = s.telemetry.dominant_source_ip || '127.0.0.1';

        // WAF & Remediator
        document.getElementById('waf-profile').textContent = s.waf.rate_limit_profile;
        const blockedList = s.waf.active_blocked_ips || [];
        document.getElementById('waf-blocked-ips').textContent =
          blockedList.length ? blockedList.map(x => x.ip_address).join(', ') : 'Aucune';
        const totalBlocked = (s.waf.metrics.waf_blocked_dynamic_ip_total || 0) + (s.waf.metrics.waf_blocked_ratelimit_total || 0);
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
          document.getElementById('step-t0-txt').textContent = 'PASS (' + s.ledger.transactions[0].transaction_id + ')';
        }
        if ((feat.req_rate_rps || 0) > 5 || totalBlocked > 0 || blockedList.length > 0) {
          document.getElementById('step-t1').classList.add('done');
          document.getElementById('step-t1-txt').textContent = 'Actif (' + (s.telemetry.dominant_source_ip || '2e PC') + ')';
        }
        if ((feat.latency_p95_ms || 0) > 60 || blockedList.length > 0) {
          document.getElementById('step-t2').classList.add('done');
          document.getElementById('step-t2-txt').textContent = 'Observée';
        }
        if (ml.anomalies_total > 0 || blockedList.length > 0) {
          document.getElementById('step-t3').classList.add('done');
          document.getElementById('step-t3-txt').textContent = 'Confirmée (IsolationForest)';
        }
        if (blockedList.length > 0) {
          document.getElementById('step-t4').classList.add('done');
          document.getElementById('step-t4-txt').textContent = 'IP ' + blockedList[0].ip_address + ' bloquée';
        }
        if (st === 'RECOVERED' && lastProbe) {
          document.getElementById('step-t5').classList.add('done');
          document.getElementById('step-t5-txt').textContent = 'RECOVERED (' + lastProbe.transaction_id + ')';
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
  <title>PC ATTAQUANT (Groupe 2) — Console de Tir Contrôlé RESILIENCE-G2</title>
  <style>
    body { font-family: 'Segoe UI', sans-serif; background: #111827; color: #f3f4f6; padding: 24px; max-width: 820px; margin: 0 auto; }
    .card { background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
    h1 { color: #f87171; font-size: 1.35rem; margin-bottom: 6px; }
    button { background: #ef4444; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 0.95rem; margin-right: 10px; }
    button.stop { background: #f59e0b; color: #111; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }
    .stat-box { background: #111827; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #374151; }
    .stat-box strong { display: block; font-size: 1.4rem; font-family: Consolas, monospace; margin-top: 4px; }
    pre { background: #090d16; padding: 12px; border-radius: 8px; overflow-x: auto; font-family: Consolas, monospace; font-size: 0.82rem; color: #93c5fd; }
  </style>
</head>
<body>
  <div class="card">
    <h1>PC ATTAQUANT — Scénario Borné L7 (Groupe 2 — RESILIENCE-G2)</h1>
    <p>Cible autorisée unique : <strong>http://192.168.137.1:8080/api/v1/transactions/verify-batch</strong></p>
    <p style="color:#9ca3af;font-size:0.88rem;margin-top:4px;">Votre adresse IP détectée par le WAF : <strong id="my-ip" style="color:#fbbf24">Détection...</strong></p>
    <div style="margin-top:16px;">
      <button onclick="startScenario()">Lancer le Tir Contrôlé (20s / 25 req/s)</button>
      <button class="stop" onclick="stopScenario()">Arrêt d'Urgence Immédiat (Kill-Switch)</button>
    </div>
    <div class="stats">
      <div class="stat-box"><span>Requêtes Envoyées</span><strong id="cnt-total">0</strong></div>
      <div class="stat-box"><span style="color:#fbbf24">200 OK (Passées)</span><strong id="cnt-200" style="color:#fbbf24">0</strong></div>
      <div class="stat-box"><span style="color:#34d399">403 Bloqué WAF AIOps</span><strong id="cnt-403" style="color:#34d399">0</strong></div>
      <div class="stat-box"><span style="color:#60a5fa">429 Rate-Limit</span><strong id="cnt-429" style="color:#60a5fa">0</strong></div>
    </div>
    <p id="status-msg" style="margin-top:14px;font-weight:600;color:#6ee7b7;"></p>
  </div>

  <div class="card">
    <h2 style="font-size:1rem;color:#93c5fd;margin-bottom:8px;">Option Terminal PowerShell depuis le 2e PC (192.168.137.135) :</h2>
    <pre>irm http://192.168.137.1:8080/attacker.ps1 | iex</pre>
  </div>

  <script>
    let running = false;
    let timerId = null;
    let counts = {total: 0, c200: 0, c403: 0, c429: 0};

    fetch('/live/v1/whoami').then(r => r.json()).then(d => {
      document.getElementById('my-ip').textContent = d.client_ip;
    });

    async function sendOne() {
      if (!running) return;
      counts.total++;
      document.getElementById('cnt-total').textContent = counts.total;
      try {
        const r = await fetch('/api/v1/transactions/verify-batch', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({batch_size: 30, iterations: 40000, audit_profile: 'deep_verification'})
        });
        if (r.status === 200) counts.c200++;
        else if (r.status === 403) counts.c403++;
        else if (r.status === 429) counts.c429++;
        document.getElementById('cnt-200').textContent = counts.c200;
        document.getElementById('cnt-403').textContent = counts.c403;
        document.getElementById('cnt-429').textContent = counts.c429;
        if (counts.c403 > 0) {
          document.getElementById('status-msg').textContent =
            'REMÉDIATION AUTONOME DÉTECTÉE : Votre IP est maintenant bloquée dynamiquement par le WAF (HTTP 403) !';
        }
      } catch (e) {}
    }

    function startScenario() {
      if (running) return;
      running = true;
      counts = {total: 0, c200: 0, c403: 0, c429: 0};
      document.getElementById('status-msg').textContent = 'Tir contrôlé en cours vers 192.168.137.1:8080...';
      timerId = setInterval(() => {
        for (let i = 0; i < 3; i++) sendOne();
      }, 120);
      setTimeout(() => {
        if (running) stopScenario('Tir borné terminé (plafond 20s atteint).');
      }, 20000);
    }

    function stopScenario(msg) {
      running = false;
      if (timerId) clearInterval(timerId);
      document.getElementById('status-msg').textContent = msg || 'Arrêt d\\'urgence activé.';
    }
  </script>
</body>
</html>
"""


ATTACKER_POWERSHELL_SCRIPT = """# Script de Tir Contrôlé Borné — Groupe 2 (RESILIENCE-G2)
$TargetUrl = "http://192.168.137.1:8080/api/v1/transactions/verify-batch"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PROJECT RESILIENCE-ALPHA (G2) - TIR CONTROLE DEPUIS 2e PC" -ForegroundColor Cyan
Write-Host " Cible autorisee : $TargetUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$Body = '{"batch_size":30,"iterations":40000,"audit_profile":"deep_verification"}'
$Count200 = 0
$Count403 = 0
$Count429 = 0
$Start = Get-Date

for ($i = 1; $i -le 140; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $TargetUrl -Method POST -Body $Body -ContentType "application/json" -TimeoutSec 3 -UseBasicParsing
        if ($resp.StatusCode -eq 200) {
            $Count200++
            Write-Host "[$i] HTTP 200 - Charge L7 recue par l'API (Saturation en cours...)" -ForegroundColor Yellow
        }
    } catch {
        $code = 0
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
        }
        if ($code -eq 403) {
            $Count403++
            Write-Host "[$i] HTTP 403 FORBIDDEN - IP BLOQUEE DYNAMIQUEMENT PAR LE WAF AIOPS !" -ForegroundColor Green
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
Write-Host " Requetes passees (200 OK)          : $Count200" -ForegroundColor Yellow
Write-Host " Requetes bloquees WAF AIOps (403)  : $Count403" -ForegroundColor Green
Write-Host " Requetes limitees Rate-Limit (429) : $Count429" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
"""


class LiveResilienceCluster:
    """Cluster temps réel exposant les microservices sur 192.168.137.1 et 127.0.0.1."""

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
        self.rag_app = create_rag_app()

        self._attach_live_routes(self.waf_app)
        self.frontend_app = Flask("resilience_frontend_live")
        self._attach_live_routes(self.frontend_app)

        self._running = True
        self._servers = []

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

    def _attach_live_routes(self, app: Flask) -> None:
        @app.route("/", methods=["GET"])
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

        @app.route("/live/v1/summary", methods=["GET"])
        def live_summary() -> Tuple[Response, int]:
            win = self.api_state.compute_window_telemetry(5.0)
            suspect_ip = self.waf_engine.get_dominant_suspect_ip(15.0)
            if suspect_ip and suspect_ip not in ("127.0.0.1", "192.168.137.1"):
                win["dominant_source_ip"] = suspect_ip
            last_probe = self.orchestrator.last_verified_transaction
            if last_probe and "transaction_id" not in last_probe and "tx_id" in last_probe:
                last_probe = {**last_probe, "transaction_id": last_probe["tx_id"]}
            return jsonify(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "telemetry": win,
                    "detector": {
                        "last_score": self.detector.last_score,
                        "last_is_anomaly": self.detector.last_is_anomaly,
                        "consecutive_anomalies": self.detector.consecutive_anomalies,
                        "anomalies_total": self.detector.anomalies_total,
                        "inferences_total": self.detector.inferences_total,
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
                }
            ), 200

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
            with self.waf_engine.lock:
                self.waf_engine.dynamic_blocklist.clear()
                self.waf_engine.rate_limit_profile = "normal"
                self.waf_engine.request_logs.clear()
            self.api_state.recycle_workers()
            self.detector.reset_state()
            with self.orchestrator.lock:
                self.orchestrator._transition_state("NORMAL", "Réinitialisation manuelle de la démonstration.")
                self.orchestrator.current_incident = None
                self.orchestrator.perturbation_started_epoch = None
            return jsonify({"status": "RESET_OK"}), 200

        @app.route("/live/v1/trigger-scenario", methods=["POST"])
        def trigger_scenario() -> Tuple[Response, int]:
            from scenarios.controlled_attack import run_bounded_resilience_scenario
            body = request.get_json(silent=True) or {}
            src_ip = str(body.get("source_ip", "192.168.137.135"))
            dur = float(body.get("duration_seconds", 12.0))
            rps = float(body.get("rate_rps", 25.0))

            def _bg_run() -> None:
                run_bounded_resilience_scenario(
                    target_base_url="http://192.168.137.1:8080",
                    duration_seconds=dur,
                    rate_rps=rps,
                    concurrency=4,
                    simulated_source_ip=src_ip,
                    confirmed_lab=True,
                )

            threading.Thread(target=_bg_run, name="bg-scenario", daemon=True).start()
            return jsonify({"status": "SCENARIO_STARTED", "source_ip": src_ip, "target": "http://192.168.137.1:8080"}), 202

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
        """Boucle temps réel d'observation et de détection ML toutes les 2 secondes."""
        while self._running:
            try:
                win = self.api_state.compute_window_telemetry(5.0)
                suspect_ip = self.waf_engine.get_dominant_suspect_ip(15.0)
                if suspect_ip and suspect_ip not in ("127.0.0.1", "192.168.137.1"):
                    win["dominant_source_ip"] = suspect_ip

                ml_event = self.detector.evaluate_window(win, push_to_remediator=False)
                # Alimente l'automate de remédiation si une anomalie est détectée ou si l'état est NORMAL/SUSPECT
                if ml_event.get("is_anomaly") or self.orchestrator.state in ("NORMAL", "SUSPECT"):
                    self.orchestrator.handle_anomaly_event(ml_event)
            except Exception as exc:
                print(f"[AIOPS-LOOP-WARN] {exc}", file=sys.stderr)
            time.sleep(2.0)

    def start(self) -> None:
        # Exécute immédiatement la transaction initiale T0 pour que l'état initial soit prêt
        t0_info = self._execute_operator_payment("T0", 5000)
        print(f"[RESILIENCE-G2] Transaction initiale T0 engagée : {t0_info['transaction']['transaction_id']} (50,00 EUR)")

        services = [
            ("waf-gateway", self.waf_app, 8080),
            ("frontend-ui", self.frontend_app, 3000),
            ("api", self.api_app, 8001),
            ("auth", self.auth_app, 8002),
            ("detector", self.detector_app, 8003),
            ("remediator", self.remediator_app, 8004),
            ("executor", self.executor_app, 8005),
            ("rag", self.rag_app, 8006),
        ]

        for name, flask_app, port in services:
            srv = make_server("0.0.0.0", port, flask_app, threaded=True)
            t = threading.Thread(target=srv.serve_forever, name=f"srv-{name}", daemon=True)
            t.start()
            self._servers.append((name, port, srv))
            print(f"[RESILIENCE-G2] Service '{name}' actif sur http://192.168.137.1:{port} (et http://127.0.0.1:{port})")

        aiops_thread = threading.Thread(target=self._aiops_loop, name="aiops-loop", daemon=True)
        aiops_thread.start()
        keepalive_thread = threading.Thread(target=self._hotspot_keepalive_loop, name="hotspot-keepalive", daemon=True)
        keepalive_thread.start()
        print("[RESILIENCE-G2] Boucle AIOps IsolationForest & Keep-Alive Hotspot actives.")


if __name__ == "__main__":
    cluster = LiveResilienceCluster()
    cluster.start()
    print("\n==================================================================")
    print(" PLATEFORME PROJECT RESILIENCE-ALPHA (GROUPE 2) EN LIGNE")
    print(" - Dashboard Hôte & SOC : http://127.0.0.1:3000  | http://192.168.137.1:3000")
    print(" - Passerelle WAF       : http://127.0.0.1:8080  | http://192.168.137.1:8080")
    print(" - Console Tir 2e PC    : http://192.168.137.1:8080/attacker")
    print(" - Commande PS 2e PC    : irm http://192.168.137.1:8080/attacker.ps1 | iex")
    print("==================================================================\n")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[RESILIENCE-G2] Arrêt demandé.")
