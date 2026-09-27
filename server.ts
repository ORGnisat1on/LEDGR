import express from 'express';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
// NOTE: `vite` is deliberately NOT imported here. It is a devDependency, and a
// top-level static import of it is evaluated when the bundle boots — which made a
// production-only install (`npm ci --omit=dev`) crash with ERR_MODULE_NOT_FOUND
// even though Vite is never used in production. It is now imported dynamically
// inside startLocalServer().
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';
import { CLUSTERS_FETCH_TIMEOUT_SECONDS, LIVE_FETCH_TIMEOUT_SECONDS, MEMPOOL_FETCH_TIMEOUT_SECONDS } from './src/config/constants';
import { mapProxyFailure, mapMempoolFailure } from './proxyOutcome';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// Demo cache: precomputed traces for the preset/case-study addresses.
//
// PATH NOTE (2026-09-27): this used to be read from `path.join(__dirname, 'src',
// 'data', 'demo_cache.json')` alone. That is correct for `npm run dev` (tsx runs
// server.ts from the project root, so __dirname IS the root) but WRONG for
// `npm start`: the esbuild bundle lives at dist/server.mjs, so __dirname is
// <root>/dist and it looked for <root>/dist/src/data/demo_cache.json, which the
// Vite build never creates. The file was silently missing in production — the
// try/catch swallowed it and every preset address fell through to a live Python
// lookup. Candidates are tried in order so the same code works unbundled, bundled
// and when launched from a different working directory.
const DEMO_CACHE_CANDIDATES = [
  path.join(__dirname, 'src', 'data', 'demo_cache.json'),        // dev: tsx server.ts from root
  path.join(__dirname, '..', 'src', 'data', 'demo_cache.json'),   // prod: dist/server.mjs -> root
  path.join(process.cwd(), 'src', 'data', 'demo_cache.json'),     // launched from the root
];

let demoCache: any = {};
{
  const tried: string[] = [];
  for (const candidate of DEMO_CACHE_CANDIDATES) {
    tried.push(candidate);
    try {
      if (!fs.existsSync(candidate)) continue;
      demoCache = JSON.parse(fs.readFileSync(candidate, 'utf8'));
      console.log(`Loaded demo_cache.json (${Object.keys(demoCache).length} presets) from ${candidate}`);
      break;
    } catch (e) {
      console.warn(`Could not parse demo_cache.json at ${candidate}`, e);
    }
  }
  if (Object.keys(demoCache).length === 0) {
    // Visible in Render's log stream. The documented, intended behaviour is a
    // graceful fallback: demoCache stays {} and preset addresses simply miss the
    // cache and are traced live against the Python backend. It must never throw
    // or take the service down.
    console.warn(
      'Could not load demo_cache.json. Demo presets will fallback to live Python backend. Tried:\n  ' +
      tried.join('\n  '),
    );
  }
}

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
    const { address, hop_depth } = req.body || {};
    if (!address || typeof address !== 'string') {
      return res.status(400).json({ error: 'address is required' });
    }
    if (hop_depth === undefined) {
      console.warn(`[WARN] hop_depth was undefined in request to /api/trace, falling back to default 2`);
    }
    const hop = Number.isFinite(hop_depth) ? Math.max(1, Math.min(10, Number(hop_depth))) : 2;

    const normAddress = address.trim();
    // Cache hit for demo presets (case-insensitive key match)
    const cachedKey = Object.keys(demoCache).find(k => k.toLowerCase() === normAddress.toLowerCase());
    if (cachedKey) {
      console.log(`[CACHE HIT] Serving precomputed data for preset: ${cachedKey}`);
      const cached = demoCache[cachedKey];
      return res.json({
        source: 'pipeline',
        available: true,
        data: { address: normAddress, hopDepth: hop, trace: cached.trace, rules: cached.rules, score: cached.score, verdict: cached.verdict, attribution: cached.attribution },
      });
    }

    const pyBase = process.env.PYTHON_API_URL || 'http://localhost:8000';

    const py = async (path: string, init?: RequestInit) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), LIVE_FETCH_TIMEOUT_SECONDS * 1000);
      try {
        const r = await fetch(`${pyBase}${path}`, { signal: controller.signal, ...init });
        if (!r.ok) {
          // Keep the machine-readable body: the pipeline returns a structured
          // `detail` ({kind, retryable, message}) for live-source failures, and
          // without this the only way to tell "rate-limited" from "unreachable"
          // would be the status code — which is exactly the ambiguity the
          // hardening pass removed.
          let body: any = null;
          try { body = await r.json(); } catch { /* non-JSON error body */ }
          const err: any = new Error(`${path} -> ${r.status}`);
          err.status = r.status;
          err.body = body;
          throw err;
        }
        return await r.json();
      } finally {
        clearTimeout(timeoutId);
      }
    };

    // Cluster lookups must not fail the whole trace, but their failure must stay
    // visible: 'no sourced exchange match' is a CONCLUSION, and we may only state
    // it when the lookup actually completed. A failed lookup is reported as
    // attribution_status: 'lookup-failed' so the UI can say "could not check"
    // instead of "no match".
    const clusterAttempt = (promise: Promise<any>, label: string) =>
      promise.then(
        (data: any) => ({ ok: true as const, data }),
        (e: any) => {
          if (e?.name === 'AbortError') throw e;
          console.warn(
            `[api/trace] ${label} lookup failed (${e?.status ?? e?.name ?? 'unknown'}) — ` +
            `attribution conclusion unavailable; it will NOT be reported as "no match"`,
          );
          return { ok: false as const, status: e?.status ?? null };
        },
      );

    try {
      const fetchPromise = Promise.all([
        py('/trace', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: normAddress, hop_depth: hop }) }),
        py('/rules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: normAddress, hop_depth: hop }) }),
        py('/score', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: normAddress }) }).catch((e) => { if (e.name === 'AbortError') throw e; return null; }),
        py('/verdict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: normAddress, hop_depth: hop }) }),
        clusterAttempt(py('/clusters'), '/clusters'),
      ]);

      let globalTimeoutId: NodeJS.Timeout;
      const globalTimeout = new Promise((_, reject) => {
        globalTimeoutId = setTimeout(() => {
          const e = new Error('Global request timeout');
          e.name = 'AbortError';
          reject(e);
        }, 55000);
      });

      const [trace, rules, score, verdict, clustersAttempt] = await Promise.race([fetchPromise, globalTimeout]) as any;
      const clusters = clustersAttempt?.ok ? clustersAttempt.data : null;
      // Default: the indexed cluster report WAS checked and had no match for this
      // wallet. Flipped to 'lookup-failed' if either lookup could not complete.
      let attributionStatus: 'matched' | 'no-match' | 'lookup-failed' =
        clustersAttempt?.ok === false ? 'lookup-failed' : 'no-match';

      let seedCluster = clusters?.clusters?.find((c: any) =>
        (c.members_sample || []).includes(normAddress)
      );
      if (seedCluster) attributionStatus = 'matched';

      if (!seedCluster && trace?.source === 'live-lookup') {
        const liveAttempt = await Promise.race([
          clusterAttempt(py(`/clusters/live?address=${encodeURIComponent(normAddress)}`), '/clusters/live'),
          globalTimeout
        ]) as any;
        if (liveAttempt?.ok === false) {
          attributionStatus = 'lookup-failed';
        } else {
          seedCluster = liveAttempt?.data?.clusters?.find((c: any) =>
            (c.members_sample || []).includes(normAddress)
          );
          if (seedCluster) attributionStatus = 'matched';
        }
      }
      
      clearTimeout(globalTimeoutId!);
      
      return res.json({
        source: 'pipeline',
        available: true,
        data: {
          address: normAddress,
          hopDepth: hop,
          trace,
          rules,
          score,
          verdict,
          attribution: seedCluster?.attribution ?? null,
          attribution_status: attributionStatus,
        },
      });
    } catch (err: any) {
      // The failure → envelope mapping lives in proxyOutcome.ts (pure, unit-tested
      // in test/proxy-outcome.test.ts) because server.ts starts a listener on
      // import and therefore cannot be imported by a test.
      return res.json(mapProxyFailure(err, { address: normAddress, hopDepth: hop, timeoutSeconds: LIVE_FETCH_TIMEOUT_SECONDS }));
    }
  });

  // Phase R6: real cluster/attribution output from the Python pipeline (R6).
  // Falls back explicitly (never silently) when the Python service is down.
  app.get('/api/clusters', async (_req, res) => {
    const pyBase = process.env.PYTHON_API_URL || 'http://localhost:8000';
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CLUSTERS_FETCH_TIMEOUT_SECONDS * 1000);
      const response = await fetch(`${pyBase}/clusters`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (response.ok) {
        const report = await response.json();
        return res.json({ source: 'pipeline', available: true, report });
      }
      return res.json({
        source: 'fallback',
        available: false,
        note: `Clustering service responded ${response.status} — no cluster data is shown. Check the Python backend logs.`,
      });
    } catch {
      return res.json({
        source: 'fallback',
        available: false,
        note: 'Python clustering service unreachable — no cluster data is shown. Start the backend with: cd backend && uvicorn ledgr.service:app --reload',
      });
    }
  });

  // Live mempool query proxy (for real-time unconfirmed tx checking).
  //
  // HONESTY CONTRACT (2026-09-26 hardening): a failed lookup is NOT
  // "no unconfirmed transactions". It returns `success:false` with a
  // machine-readable `reason`, and the client must show the reason instead of
  // reporting a clean result. `success:true` with an empty list is the ONLY
  // response that means "no unconfirmed transactions right now".
  app.get('/api/mempool/address/:address', async (req, res) => {
    const { address } = req.params;
    try {
      // Query public mempool.space API with short timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), MEMPOOL_FETCH_TIMEOUT_SECONDS * 1000);
      
      const response = await fetch(`https://mempool.space/api/address/${encodeURIComponent(address)}/txs/mempool`, {
        signal: controller.signal,
        headers: { 'Accept': 'application/json' }
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const txs = await response.json();
        if (!Array.isArray(txs)) {
          // A 200 that is not a transaction list is not usable data; say so
          // rather than coercing it into "no transactions".
          return res.json(mapMempoolFailure('api-error'));
        }
        return res.json({ success: true, txs, live: true });
      }
      if (response.status === 429) {
        return res.json(mapMempoolFailure('rate-limited', { status: 429 }));
      }
      return res.json(mapMempoolFailure('api-error', { status: response.status }));
    } catch (err: any) {
      const timedOut = err?.name === 'AbortError';
      return res.json(mapMempoolFailure(
        timedOut ? 'timeout' : 'unreachable',
        { timeoutSeconds: MEMPOOL_FETCH_TIMEOUT_SECONDS },
      ));
    }
  });

// Vite middleware in dev or static files in production
async function startLocalServer() {
  // Render (and most PaaS providers) inject PORT and route the load balancer to
  // whatever it says — Render's documented default is 10000. Hardcoding 3000 here
  // meant the process listened on a port nothing was forwarding to, so every
  // request 502'd. PORT is always a *string* in the environment, hence Number().
  const PORT = Number(process.env.PORT) || 3000;
  const isProduction = process.env.NODE_ENV === "production";

  // Logged explicitly: Render shows stdout/stderr in its log stream, so this is
  // how you confirm at a glance which mode the service booted in and where it is
  // actually listening (and whether demo_cache.json was found).
  console.log(
    `[startup] NODE_ENV=${process.env.NODE_ENV ?? "(unset)"} -> mode=${isProduction ? "production (serving dist/)" : "development (Vite middleware)"}; ` +
    `PORT=${process.env.PORT ?? "(unset)"} -> listening on ${PORT}; ` +
    `PYTHON_API_URL=${process.env.PYTHON_API_URL ?? "(unset, using http://localhost:8000)"}; ` +
    `demo_cache entries=${Object.keys(demoCache).length}`,
  );

  if (!isProduction) {
    // DYNAMIC import on purpose. A static top-level `import ... from "vite"`
    // made the production bundle import a devDependency at startup, so a
    // production-only install (`npm ci --omit=dev`, which is what npm does when
    // NODE_ENV=production is set) crashed with ERR_MODULE_NOT_FOUND before
    // serving anything — even though Vite is never used in production mode.
    // esbuild keeps this external (--packages=external); it is only evaluated
    // when this branch actually runs.
    const { createServer: createViteServer } = await import("vite");
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

if (!process.env.VERCEL) {
  startLocalServer();
}

export default app;
