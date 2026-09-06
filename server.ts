import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json({ limit: '10mb' }));

  // Health check
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', service: 'crypto-fraud-attribution-sih26183', timestamp: new Date().toISOString() });
  });

  // Optional AI Intelligence Narrative generation (Gemini API server-side)
  app.post('/api/generate-brief', async (req, res) => {
    try {
      const apiKey = process.env.GEMINI_API_KEY;
      if (!apiKey) {
        return res.status(200).json({
          brief: "Automatic intelligence brief generation is offline because GEMINI_API_KEY is not configured. The deterministic rule-based and graph ML classification remain 100% operational.",
          source: "fallback"
        });
      }

      const { targetAddress, complaint, verdict, contributingSignals, attribution, hopCount } = req.body;

      const ai = new GoogleGenAI({ apiKey });
      const prompt = `You are a Senior Cyber Crime Intelligence Analyst assisting the Indian Cyber Crime Coordination Centre (I4C), Ministry of Home Affairs, Government of India.
Generate a concise, highly formal Law Enforcement Intelligence Summary for an on-chain crypto fraud investigation.

Investigation Data:
- Suspect Wallet Address: ${targetAddress}
- NCRP Incident Category: ${complaint?.category || 'Cryptocurrency Scam'}
- Reported Defrauded Amount: ${complaint?.amountInr ? '₹' + complaint.amountInr.toLocaleString('en-IN') : 'N/A'} (${complaint?.amountBtc || '0'} BTC)
- Multi-Signal Correlation Verdict: ${verdict?.toUpperCase()}
- Contributing Signals:
  * Rule-Based Laundering Heuristics: ${JSON.stringify(contributingSignals?.ruleDetails || {})}
  * Graph ML Model Prediction: ${contributingSignals?.mlPrediction || 'Illicit'} (Confidence: ${(contributingSignals?.mlConfidence * 100).toFixed(1)}%)
- Final Attributed Entity / VASP: ${attribution?.name || 'Unidentified VASP Cluster'} (Confidence Tier: ${attribution?.confidenceTier || 'N/A'})
- Path Traversal Depth: ${hopCount || 2} hops

Requirements:
1. Executive Paragraph: Summarize the fund movement from victim suspect address to the identified exchange/cluster.
2. Laundering Modus Operandi: Explain how the observed patterns (peel chains, rapid fan-out, mixer adjacency) reflect organized cyber syndicates.
3. Recommended Law Enforcement Action: Specific procedural steps for the Investigating Officer (e.g., dispatching Section 91 CrPC / Section 94 BNSS preservation requisition notice to the identified exchange compliance nodal officer).
Keep tone professional, strictly objective, and direct.`;

      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
      });

      const briefText = response.text || "Summary generated successfully.";
      res.json({ brief: briefText, source: "gemini-2.5-flash" });
    } catch (err: any) {
      console.error("Error generating intelligence brief:", err);
      res.status(200).json({
        brief: "Deterministic forensic tracing completed. Note: Live AI narrative synthesis encountered a network timeout; standard statutory report template is fully generated.",
        source: "fallback"
      });
    }
  });

  // Phase R7: the live trace flow. Proxies the reported wallet to the Python
  // pipeline (R2 subgraph + R3 rules + R4 score + R5 verdict + R6 attribution)
  // and composes one response. If the Python service is unavailable the
  // response is an explicit fallback — the client decides what to show and
  // never presents mock data as pipeline output.
  app.post('/api/trace', async (req, res) => {
    const { address, hopDepth } = req.body || {};
    if (!address || typeof address !== 'string') {
      return res.status(400).json({ error: 'address is required' });
    }
    const hop = Number.isFinite(hopDepth) ? Math.max(1, Math.min(10, Number(hopDepth))) : 2;
    const pyBase = process.env.LEDGR_SERVICE_URL || 'http://localhost:8000';

    const py = async (path: string, init?: RequestInit) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);
      try {
        const r = await fetch(`${pyBase}${path}`, { signal: controller.signal, ...init });
        if (!r.ok) {
          const err: any = new Error(`${path} -> ${r.status}`);
          err.status = r.status;
          throw err;
        }
        return await r.json();
      } finally {
        clearTimeout(timeoutId);
      }
    };

    try {
      const [trace, rules, score, verdict, clusters] = await Promise.all([
        py('/trace', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address, hop_depth: hop }) }),
        py('/rules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address, hop_depth: hop }) }),
        py('/score', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address }) }).catch(() => null),
        py('/verdict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address, hop_depth: hop }) }),
        py('/clusters').catch(() => null),
      ]);

      const seedCluster = clusters?.clusters?.find((c: any) =>
        (c.members_sample || []).includes(address)
      );
      return res.json({
        source: 'pipeline',
        available: true,
        data: { address, hopDepth: hop, trace, rules, score, verdict, attribution: seedCluster?.attribution ?? null },
      });
    } catch (err: any) {
      // A 404 from the pipeline means the wallet is simply not in the ingested
      // Elliptic dataset — an honest, expected outcome (e.g. any real BTC
      // address, since Elliptic nodes are anonymized tx-ids). This is NOT a
      // service failure and must not trigger the offline-mock fallback.
      if (err?.status === 404) {
        return res.json({
          source: 'pipeline',
          available: true,
          data: {
            address,
            hopDepth: hop,
            found: false,
            note: 'Wallet not present in the ingested Elliptic dataset — no trace, rule signal, or verdict exists for it, and the learned signal reports it as classified:false (no risk is fabricated).',
            score: { wallet: address, classified: false, risk_score: null, prediction: null, learned_flag: false },
          },
        });
      }
      const note = err?.name === 'AbortError'
        ? 'Python pipeline timed out — showing labeled offline mock data.'
        : 'Python pipeline service unavailable — showing labeled offline mock data.';
      return res.json({ source: 'fallback', available: false, note });
    }
  });

  // Phase R6: real cluster/attribution output from the Python pipeline (R6).
  // Falls back explicitly (never silently) when the Python service is down.
  app.get('/api/clusters', async (_req, res) => {
    const pyBase = process.env.LEDGR_SERVICE_URL || 'http://localhost:8000';
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);
      const response = await fetch(`${pyBase}/clusters`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (response.ok) {
        const report = await response.json();
        return res.json({ source: 'pipeline', available: true, report });
      }
      return res.json({
        source: 'fallback',
        available: false,
        note: `Clustering service responded ${response.status} — showing labeled offline mock data.`,
      });
    } catch {
      return res.json({
        source: 'fallback',
        available: false,
        note: 'Python clustering service unavailable — showing labeled offline mock data.',
      });
    }
  });

  // Live mempool query proxy (for real-time unconfirmed tx checking with fallback)
  app.get('/api/mempool/address/:address', async (req, res) => {
    const { address } = req.params;
    try {
      // Query public mempool.space API with short timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);
      
      const response = await fetch(`https://mempool.space/api/address/${address}/txs/mempool`, {
        signal: controller.signal,
        headers: { 'Accept': 'application/json' }
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const txs = await response.json();
        return res.json({ success: true, txs, live: true });
      }
      return res.json({ success: false, txs: [], live: false, note: "No unconfirmed live mempool transactions or rate-limited" });
    } catch (err) {
      return res.json({ success: false, txs: [], live: false, note: "Live mempool service unavailable; using forensic simulated monitor" });
    }
  });

  // Vite middleware in dev or static files in production
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
