import React, { useState, useEffect, useCallback } from 'react';

const STATE_BADGE_STYLES = {
  NORMAL: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
  SUSPECT: 'bg-amber-500/20 text-amber-300 border-amber-500/50',
  INCIDENT: 'bg-red-600/30 text-red-200 border-red-500 animate-pulse',
  REMEDIATING: 'bg-orange-500/30 text-orange-200 border-orange-400',
  VERIFYING: 'bg-sky-500/30 text-sky-200 border-sky-400',
  RECOVERED: 'bg-teal-500/25 text-teal-200 border-teal-400',
  FAILED: 'bg-rose-900/60 text-rose-200 border-rose-500'
};

export default function App() {
  const [gatewayUrl] = useState(() => window.RESILIENCE_API_BASE || '');
  const [socData, setSocData] = useState(null);
  const [connectionError, setConnectionError] = useState(null);

  // Authentification & Paiement Métier
  const [username, setUsername] = useState('operator_alpha');
  const [password, setPassword] = useState('FictiveOp#2026!');
  const [jwtToken, setJwtToken] = useState('');
  const [accounts, setAccounts] = useState([]);
  const [invariant, setInvariant] = useState(null);
  const [transactions, setTransactions] = useState([]);

  // Formulaire de transaction fictive
  const [sourceAccount, setSourceAccount] = useState('ACC-FR-001');
  const [targetAccount, setTargetAccount] = useState('ACC-FR-002');
  const [amountCents, setAmountCents] = useState(2500);
  const [idempotencyKey, setIdempotencyKey] = useState(() => `idem-${Date.now()}`);
  const [description, setDescription] = useState('Règlement partenaire fictif RESILIENCE-ALPHA');
  const [txResult, setTxResult] = useState(null);

  // Assistant RAG Local
  const [ragQuestion, setRagQuestion] = useState("Quelles sont les étapes de remédiation autonome et comment l'état RECOVERED est-il prouvé ?");
  const [ragResponse, setRagResponse] = useState(null);
  const [ragLoading, setRagLoading] = useState(false);

  const fetchSocSnapshot = useCallback(async () => {
    try {
      const resp = await fetch(`${gatewayUrl}/soc/v1/dashboard`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setSocData(json);
      setConnectionError(null);
    } catch (err) {
      setConnectionError(`Passerelle SOC injoignable (${err.message}) — aucune donnée simulée n'est affichée.`);
    }
  }, [gatewayUrl]);

  const fetchBusinessData = useCallback(async (token) => {
    if (!token) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [accResp, txResp] = await Promise.all([
        fetch(`${gatewayUrl}/api/v1/accounts`, { headers }),
        fetch(`${gatewayUrl}/api/v1/transactions?limit=15`, { headers })
      ]);
      if (accResp.ok) {
        const accJson = await accResp.json();
        setAccounts(accJson.accounts || []);
        setInvariant(accJson.invariant || null);
      }
      if (txResp.ok) {
        const txJson = await txResp.json();
        setTransactions(txJson.transactions || []);
      }
    } catch (_) {
      // Les erreurs réseau sont visibles dans la bannière d'état
    }
  }, [gatewayUrl]);

  useEffect(() => {
    fetchSocSnapshot();
    const timer = setInterval(fetchSocSnapshot, 2000);
    return () => clearInterval(timer);
  }, [fetchSocSnapshot]);

  useEffect(() => {
    if (jwtToken) {
      fetchBusinessData(jwtToken);
      const timer = setInterval(() => fetchBusinessData(jwtToken), 3000);
      return () => clearInterval(timer);
    }
  }, [jwtToken, fetchBusinessData]);

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const resp = await fetch(`${gatewayUrl}/auth/v1/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await resp.json();
      if (resp.ok && data.access_token) {
        setJwtToken(data.access_token);
        fetchBusinessData(data.access_token);
      } else {
        setTxResult({ ok: false, status: resp.status, payload: data });
      }
    } catch (err) {
      setTxResult({ ok: false, status: 0, payload: { error: err.message } });
    }
  };

  const handleCreateTransaction = async (e, reuseKey = false) => {
    if (e) e.preventDefault();
    const keyToUse = reuseKey ? idempotencyKey : `idem-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    if (!reuseKey) setIdempotencyKey(keyToUse);

    try {
      const resp = await fetch(`${gatewayUrl}/api/v1/transactions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${jwtToken}`,
          'Idempotency-Key': keyToUse
        },
        body: JSON.stringify({
          source_account_id: sourceAccount,
          target_account_id: targetAccount,
          amount_cents: Number(amountCents),
          currency: 'EUR',
          description
        })
      });
      const data = await resp.json();
      setTxResult({ ok: resp.ok, status: resp.status, payload: data });
      fetchBusinessData(jwtToken);
      fetchSocSnapshot();
    } catch (err) {
      setTxResult({ ok: false, status: 503, payload: { error: err.message } });
    }
  };

  const handleTriggerProbe = async () => {
    try {
      await fetch(`${gatewayUrl}/soc/v1/probe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: 'OPERATOR_VERIFICATION_PROBE' })
      });
      fetchSocSnapshot();
      if (jwtToken) fetchBusinessData(jwtToken);
    } catch (_) {}
  };

  const handleQueryRag = async (e) => {
    e.preventDefault();
    setRagLoading(true);
    try {
      const resp = await fetch(`${gatewayUrl}/rag/v1/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: ragQuestion, top_k: 3 })
      });
      const data = await resp.json();
      setRagResponse(data);
    } catch (err) {
      setRagResponse({ error: err.message });
    } finally {
      setRagLoading(false);
    }
  };

  const automatonState = socData?.automaton_state || 'UNKNOWN';
  const currentIncident = socData?.current_incident;
  const lastVerifiedTx = socData?.last_verified_transaction;
  const lastMl = socData?.last_ml_event;
  const wafStatus = socData?.waf_status;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* En-tête de supervision */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 text-xs font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 rounded">
              PROJECT RESILIENCE-ALPHA
            </span>
            <span className="text-xs text-slate-400">
              Cyber-Résilience, Détection ML IsolationForest &amp; Zero-Touch Recovery
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white mt-1">
            Console Unifiée de Paiement Métier &amp; Supervision SOC / AIOps
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-slate-400">État Automate d&apos;Incident</div>
            <div className={`mt-1 inline-block px-3 py-1 rounded border text-sm font-bold ${STATE_BADGE_STYLES[automatonState] || 'bg-slate-800 text-slate-300'}`}>
              {automatonState}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-400">Disponibilité Métier</div>
            <div className={`mt-1 inline-block px-3 py-1 rounded text-sm font-semibold ${
              socData?.business_availability === 'OPERATIONAL'
                ? 'bg-emerald-500/20 text-emerald-300'
                : 'bg-red-500/30 text-red-200'
            }`}>
              {socData?.business_availability || 'NON CONNECTÉ'}
            </div>
          </div>
        </div>
      </header>

      {connectionError && (
        <div className="p-4 rounded-lg bg-red-950/60 border border-red-500/50 text-red-200 text-sm">
          <strong>État réel de connexion :</strong> {connectionError}
        </div>
      )}

      {/* Bandeau des 4 indicateurs critiques exigés */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs uppercase text-slate-400 font-semibold">1. Score ML (Isolation Forest)</div>
          <div className="text-2xl font-bold mt-1">
            {lastMl ? Number(lastMl.anomaly_score).toFixed(4) : 'En attente'}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Seuil calibré : <code className="text-indigo-300">{lastMl?.decision_threshold ?? '-0.1176'}</code> |{' '}
            Anomalie : <strong className={lastMl?.is_anomaly ? 'text-red-400' : 'text-emerald-400'}>
              {lastMl ? (lastMl.is_anomaly ? `OUI (${lastMl.consecutive_anomalies} fen.)` : 'NON') : 'N/A'}
            </strong>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs uppercase text-slate-400 font-semibold">2. Temps Mesurés (MTTD / MTTR)</div>
          <div className="text-2xl font-bold mt-1 text-sky-300">
            MTTD: {currentIncident?.mttd_seconds ?? socData?.metrics?.remediator_last_mttd_seconds ?? 0}s | MTTR: {currentIncident?.mttr_seconds ?? socData?.metrics?.remediator_last_mttr_seconds ?? 0}s
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Reprises prouvées : <strong>{socData?.metrics?.remediator_recoveries_total ?? 0}</strong> | Échecs : <strong>{socData?.metrics?.remediator_failures_total ?? 0}</strong>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs uppercase text-slate-400 font-semibold">3. Passerelle WAF Dynamique</div>
          <div className="text-2xl font-bold mt-1 text-amber-300">
            Profil : {wafStatus?.rate_limit_profile || 'normal'}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            IPs bloquées : <strong>{wafStatus?.active_blocked_ips?.length ?? 0}</strong> | Rejets WAF :{' '}
            <strong>
              {(wafStatus?.metrics?.waf_blocked_dynamic_ip_total ?? 0) +
                (wafStatus?.metrics?.waf_blocked_signature_total ?? 0) +
                (wafStatus?.metrics?.waf_blocked_ratelimit_total ?? 0)}
            </strong>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs uppercase text-slate-400 font-semibold">4. Dernière Transaction Vérifiée (Preuve)</div>
          <div className="text-lg font-bold mt-1 text-emerald-300 truncate">
            {lastVerifiedTx ? lastVerifiedTx.tx_id : 'Aucune sonde exécutée'}
          </div>
          <div className="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>
              {lastVerifiedTx
                ? `${lastVerifiedTx.amount_formatted} (Lat: ${lastVerifiedTx.proof?.post_recovery_latency_ms} ms)`
                : 'Lancez une sonde ou un paiement'}
            </span>
            <button
              onClick={handleTriggerProbe}
              className="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium"
            >
              Tester Sonde
            </button>
          </div>
        </div>
      </section>

      {/* Grille principale : Portail de Paiement Métier (Gauche) & Incident/SOC (Droite) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Colonne Gauche : Plateforme de Paiement Fictive */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-lg font-bold text-white border-b border-slate-800 pb-2">
              Portail de Paiement Métier (Centimes Exacts &amp; Idempotence)
            </h2>

            {!jwtToken ? (
              <form onSubmit={handleLogin} className="space-y-3">
                <div className="text-xs text-slate-400">
                  Authentification JWT requise auprès de <code>services/auth</code> :
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Utilisateur"
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm"
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Mot de passe"
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm"
                  />
                </div>
                <button
                  type="submit"
                  className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 rounded font-semibold text-sm"
                >
                  Se connecter (Obtenir Jeton JWT HS256)
                </button>
              </form>
            ) : (
              <form onSubmit={(e) => handleCreateTransaction(e, false)} className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-400">Compte Émetteur</label>
                    <input
                      type="text"
                      value={sourceAccount}
                      onChange={(e) => setSourceAccount(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Compte Bénéficiaire</label>
                    <input
                      type="text"
                      value={targetAccount}
                      onChange={(e) => setTargetAccount(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-400">Montant (Centimes entiers)</label>
                    <input
                      type="number"
                      value={amountCents}
                      onChange={(e) => setAmountCents(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Clé d&apos;Idempotence</label>
                    <input
                      type="text"
                      value={idempotencyKey}
                      onChange={(e) => setIdempotencyKey(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-sm font-mono"
                    />
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 rounded font-semibold text-sm"
                  >
                    Exécuter Transaction ({(Number(amountCents) / 100).toFixed(2)} EUR)
                  </button>
                  <button
                    type="button"
                    onClick={(e) => handleCreateTransaction(e, true)}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded text-xs"
                  >
                    Rejouer même clé (Test Idempotence)
                  </button>
                </div>
              </form>
            )}

            {txResult && (
              <div className={`p-3 rounded text-xs font-mono border ${
                txResult.ok ? 'bg-emerald-950/50 border-emerald-600/50 text-emerald-200' : 'bg-red-950/50 border-red-600/50 text-red-200'
              }`}>
                <div>HTTP {txResult.status} | Rejeu Idempotent : {String(Boolean(txResult.payload?.idempotent_replay))}</div>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(txResult.payload, null, 2)}</pre>
              </div>
            )}

            {/* Soldes des comptes & Invariant comptable */}
            {accounts.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-300">Comptes &amp; Invariant Comptable</span>
                  <span className={invariant?.consistent ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                    {invariant?.consistent ? 'INVARIANT OK' : 'ALERTE INTÉGRITÉ'} ({(invariant?.actual_total_cents / 100).toFixed(2)} EUR)
                  </span>
                </div>
                <div className="space-y-1 max-h-36 overflow-y-auto text-xs">
                  {accounts.map((acc) => (
                    <div key={acc.account_id} className="flex justify-between bg-slate-950 px-2.5 py-1.5 rounded">
                      <span className="font-mono text-slate-300">{acc.account_id}</span>
                      <span className="font-semibold text-emerald-300">{acc.balance_formatted}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Assistant RAG Local */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <h2 className="text-lg font-bold text-white border-b border-slate-800 pb-2">
              Assistant Opérateur RAG Local (Ollama + LangChain — Sans Privilège)
            </h2>
            <form onSubmit={handleQueryRag} className="flex gap-2">
              <input
                type="text"
                value={ragQuestion}
                onChange={(e) => setRagQuestion(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm"
                placeholder="Poser une question sur les procédures ou l'architecture..."
              />
              <button
                type="submit"
                disabled={ragLoading}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-semibold"
              >
                {ragLoading ? '...' : 'Interroger'}
              </button>
            </form>
            {ragResponse && (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs space-y-2">
                <div className="flex justify-between text-slate-400">
                  <span>Statut LLM : <code>{ragResponse.llm_status || 'N/A'}</code></span>
                  <span>Score max : <code>{ragResponse.max_similarity_score ?? 'N/A'}</code></span>
                </div>
                <div className="text-slate-200 whitespace-pre-wrap">{ragResponse.answer || ragResponse.error}</div>
                {ragResponse.citations?.length > 0 && (
                  <div className="text-indigo-300 font-mono">
                    Sources citées : {ragResponse.citations.join(' | ')}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Colonne Droite : Incident Courant, Action Engagée & Chronologie SOC Corrélée */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-lg font-bold text-white border-b border-slate-800 pb-2">
              Détail de l&apos;Incident Courant, Décision AIOps &amp; Preuve de Reprise
            </h2>

            {currentIncident ? (
              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 bg-slate-950 p-3 rounded border border-slate-800">
                  <div>
                    <span className="text-slate-400 block">ID Incident</span>
                    <strong className="font-mono text-white">{currentIncident.incident_id}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">IP Source Corrélée</span>
                    <strong className="font-mono text-amber-300">{currentIncident.suspect_ip}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Tentatives Exécuteur</span>
                    <strong>{currentIncident.remediation_attempts} / {currentIncident.max_attempts}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Transaction Preuve</span>
                    <strong className="font-mono text-emerald-300">{currentIncident.recovery_tx_id || 'En cours'}</strong>
                  </div>
                </div>

                {currentIncident.executed_actions?.length > 0 && (
                  <div>
                    <div className="font-semibold text-slate-300 mb-1">Actions Confinées Exécutées (Signées HMAC-SHA256) :</div>
                    <div className="space-y-1">
                      {currentIncident.executed_actions.map((act, idx) => (
                        <div key={idx} className="flex justify-between bg-slate-950 px-3 py-1.5 rounded border border-slate-800 font-mono">
                          <span className="text-indigo-300">{act.action}({JSON.stringify(act.parameters)})</span>
                          <span className={act.status_code === 200 ? 'text-emerald-400' : 'text-red-400'}>
                            HTTP {act.status_code} | Audit #{act.response?.audit_entry_hash?.slice(0, 10)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {currentIncident.recovery_proof && (
                  <div className="p-3 bg-emerald-950/40 border border-emerald-500/40 rounded space-y-1">
                    <div className="font-bold text-emerald-300">
                      PREUVE MÉTIER POST-INCIDENT VALIDÉE ({currentIncident.recovery_proof.probe_tx_id})
                    </div>
                    <div>
                      Persistance DB : <strong>{String(currentIncident.recovery_proof.persisted_in_db)}</strong> |{' '}
                      Anti-Doublon Idempotent : <strong>{String(currentIncident.recovery_proof.idempotency_duplicate_prevented)}</strong> |{' '}
                      Invariant Comptable : <strong>{String(currentIncident.recovery_proof.accounting_invariant_verified)}</strong> |{' '}
                      Latence Post-Reprise : <strong>{currentIncident.recovery_proof.post_recovery_latency_ms} ms</strong>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-slate-400 py-4">
                Aucun incident actif. Le modèle <code>IsolationForest</code> supervise les fenêtres de télémétrie en continu.
              </div>
            )}
          </div>

          {/* Chronologie SOC Corrélée */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <h2 className="text-lg font-bold text-white border-b border-slate-800 pb-2">
              Chronologie SOC Corrélée (Source → Dégradation → Score ML → Remédiation → Preuve Métier)
            </h2>
            <div className="space-y-2 max-h-96 overflow-y-auto text-xs">
              {(socData?.timeline || []).map((item) => (
                <div key={item.timeline_id} className="p-2.5 bg-slate-950 border border-slate-800 rounded flex flex-col gap-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-indigo-300">
                      [{item.stage}] {item.event_type}
                    </span>
                    <span className="text-slate-400 font-mono">{item.timestamp}</span>
                  </div>
                  <div className="text-slate-200">{item.message}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
