# DEPLOY.md — Render deployment (two services)

This repo deploys as **two independent Render web services** that talk over HTTP.
Neither one needs the other at build time.

| Service | What it is | Start command |
|---|---|---|
| **Node/web app** | Express + Vite SPA + API proxy (`server.ts`) | `npm start` (runs `dist/server.mjs`) |
| **Python API** | FastAPI inference pipeline (`backend/ledgr/service.py`) | `uvicorn ledgr.service:app --host 0.0.0.0 --port $PORT` |

The Python service is the same artifact as `backend/Dockerfile` (which pins 7860
for Hugging Face Spaces — on Render, use `$PORT` instead).

---

## 1. Node service — environment variables

Set these in the Render dashboard under the service's **Environment** tab.

| Variable | Required? | Default if unset | One-line description |
|---|---|---|---|
| `PYTHON_API_URL` | **Yes** | `http://localhost:8000` | Base URL of the Python service, e.g. `https://ledgr-api.onrender.com`. Without it the proxy calls its own localhost and every trace fails. |
| `NODE_ENV` | No — **do not set it** | Render sets `production` at runtime | Switches off the Vite dev middleware and serves the built `dist/`. See §3. |
| `PORT` | No — **do not set it** | Render injects it (documented default `10000`) | Port the process listens on. The code reads `Number(process.env.PORT) \|\| 3000`. |
| `GEMINI_API_KEY` | No | unset | Enables optional LLM report prose. Without it the app degrades gracefully — no core pipeline feature needs it. |
| `VERCEL` | No | unset | Set **only** on Vercel. When truthy the local server is not started. Leave unset on Render. |
| `VITE_API_URL` | No | `""` (empty) | Must stay **empty**. The browser calls `/api/*` on its own origin and Express proxies to Python. Setting it to the Python origin makes the browser bypass Express and 404. |
| `DISABLE_HMR` | No | unset | Dev-only (Vite HMR). Irrelevant in production. |

**Build vs start commands (Node service)**

- Build: `npm ci && npm run build`
- Start: `npm start`

---

## 2. Python service — environment variables

| Variable | Required? | Default | One-line description |
|---|---|---|---|
| `PYTHONPATH` | Yes on Render | `/opt/render/project` | So `ledgr.*` imports resolve when uvicorn runs from the repo root (`--app-dir backend` is an equivalent alternative). |
| `LEDGR_ARTIFACTS_DIR` | No | `<repo>/artifacts` | Where `graph_index.pkl`, `learned_model.joblib`, `feature_lookup.pkl` live. These are **git-LFS** files — confirm the build actually pulled them. |
| `LEDGR_DATA_DIR` | No | `<repo>/data/raw` | Raw Elliptic CSVs. |
| `LEDGR_LIVE_TRACING` | No | `1` (on) | `0` disables all on-demand block-explorer lookups. |
| `LEDGR_PEEL_MIN_HOPS` / `LEDGR_FANOUT_MIN_OUT` / `LEDGR_MIXER_MAX_HOPS` | No | tuned defaults | Rule-engine thresholds. **Leave at defaults** — these are the validated values; changing them changes rule output. |

The Python service is stateless apart from the artifacts, so no disk is required.

---

## 3. `NODE_ENV` — what actually happens, and why not to set it yourself

**What Render does (from Render's "Default Environment Variables" docs):**

> Node.js — `NODE_ENV` = `production` (**runtime only**)
> `PORT` — "For web services, specify the port that your HTTP server binds to. The default port is 10000."

So on Render's native Node runtime, `NODE_ENV=production` **is** already set at
runtime and the app takes the static-`dist/` branch with no action from you.

**Do not add `NODE_ENV=production` to the dashboard yourself.** Verified locally:
npm skips `devDependencies` when `NODE_ENV=production` is set during install —

```
npm install                      -> added 43 packages   (dev deps included)
NODE_ENV=production npm install  -> added  1 package    (dev deps OMITTED)
```

If a service-level `NODE_ENV=production` also applied at build time, `vite` and
`esbuild` would be missing and `npm run build` would fail outright. If you must
set it, use `npm ci --include=dev && npm run build` as the build command.

**If `NODE_ENV` is not `production` at runtime**, the process takes the dev branch
and calls `createViteServer({ middlewareMode: true })`. That import is now
**dynamic**, so on a production-only install it fails at that point with a clear
`ERR_MODULE_NOT_FOUND` for `vite` rather than crashing at import time — the API
routes registered before it still work, but no frontend is served. The startup
log makes the mode explicit:

```
[startup] NODE_ENV=production -> mode=production (serving dist/); PORT=10000 -> listening on 10000; PYTHON_API_URL=…; demo_cache entries=4
```

**Always read that line first** when diagnosing a Render deploy.

---

## 4. `demo_cache.json` — how it is located

`server.ts` tries three candidate paths in order and logs which one worked:

1. `<dir of server.mjs>/src/data/demo_cache.json` — dev (`tsx server.ts` from the repo root)
2. `<dir of server.mjs>/../src/data/demo_cache.json` — **production** (bundle lives in `dist/`)
3. `<process.cwd()>/src/data/demo_cache.json` — launched from the repo root

If none resolve, the app logs a warning listing all three and continues with an
empty cache: preset addresses then miss the cache and are traced live against
Python. That fallback is intentional and verified — the service never fails to
start because of a missing demo cache.

`demo_cache.json` holds precomputed demo traces, not secrets, and is committed.
Note `.dockerignore` excludes it — irrelevant for Render (which ignores
`.dockerignore` unless building a Dockerfile), but relevant if you containerise
the Node app.

---

## 5. Local production-mode check (run this as a smoke test)

```bash
NODE_ENV=production PORT=5000 npm run build
NODE_ENV=production PORT=5000 PYTHON_API_URL=http://localhost:8000 npm start
curl -s localhost:5000/api/health          # {"status":"ok",...}
curl -s localhost:5000/ | grep assets/      # hashed bundle => dist/ is being served
```

Then, against a running Python service:

- a **preset** address must log `[CACHE HIT] Serving precomputed data for preset: …`
- a **non-preset** address must return `source:"pipeline"` with `trace.source` of
  `elliptic-indexed` (in the dataset) or `live-lookup` (block explorers)
