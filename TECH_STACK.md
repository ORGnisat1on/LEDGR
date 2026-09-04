# Tech Stack — LEDGR (Crypto Fraud Attribution System, SIH26183)

This document specifies the actual technologies used in this repository, verified against the source code and configuration files.

## Overview

LEDGR is a blockchain analytics and attribution platform. It takes a suspect crypto wallet address, builds a local transaction subgraph, runs two independent risk signals (rule-based heuristics + graph ML), and attributes funds to a likely destination exchange/VASP cluster.

The repo is a **single full-stack TypeScript codebase**: an Express server that hosts a Vite-powered React SPA, with the entire forensic analysis engine implemented client-side in TypeScript.

## Frontend

| Technology | Version | Purpose | Where |
|---|---|---|---|
| React | ^19.0.1 | UI framework (function components + hooks, StrictMode) | `src/main.tsx`, `src/App.tsx`, `src/components/` |
| react-dom | ^19.0.1 | React renderer (client-side SPA, `createRoot`) | `src/main.tsx` |
| TypeScript | ~5.8.2 | Type-safe language across frontend and server | `tsconfig.json` |
| Tailwind CSS | ^4.1.14 | Styling (CSS-first config via `@import "tailwindcss"`) | `src/index.css` |
| @tailwindcss/vite | ^4.1.14 | Tailwind v4 Vite plugin integration | `vite.config.ts` |
| lucide-react | ^0.546.0 | Icon library | All components in `src/components/` |
| motion | ^12.23.24 | Animation library (Framer Motion successor) | `package.json` |

### Notable frontend details
- **No client-side routing library** — single-page app, modals/panels managed by state.
- **Graph visualization is custom-built** with SVG + React state (`src/components/GraphVisualizer.tsx`) — no third-party graph library (no D3, no Cytoscape, no vis.js).
- All imports use the `@/*` path alias mapped to the repo root (`tsconfig.json` + `vite.config.ts`).

## Backend / Server

| Technology | Version | Purpose | Where |
|---|---|---|---|
| Node.js | — | JavaScript runtime (ES2022 target) | `tsconfig.json` |
| Express | ^4.21.2 | HTTP server, JSON API, static file serving | `server.ts` |
| tsx | ^4.21.0 | TypeScript execution for dev (`npm run dev`) | `package.json` |
| dotenv | ^17.2.3 | Environment variable loading (`.env`) | `server.ts`, `.env.example` |

### API surface (`server.ts`)
- `GET /api/health` — health check.
- `POST /api/generate-brief` — optional server-side Gemini API call to generate a law-enforcement intelligence narrative (graceful fallback when no API key).
- `GET /api/mempool/address/:address` — proxy to the public **mempool.space** API for live unconfirmed Bitcoin transactions (4s timeout, graceful fallback to simulated monitor).
- In dev, Vite middleware serves the SPA; in production, Express serves static files from `dist/`.

## AI / LLM

| Technology | Version | Purpose | Where |
|---|---|---|---|
| @google/genai (Gemini SDK) | ^2.4.0 | Server-side narrative generation (`gemini-2.5-flash` model) | `server.ts` |

Per project policy (`README.md`), the LLM is **optional and non-critical** — it only generates report text. The core detection pipeline (rules + graph ML) is fully deterministic and never depends on an LLM.


## Build Tooling

| Technology | Version | Purpose | Where |
|---|---|---|---|
| Vite | ^6.2.3 | Dev server (HMR, middleware mode) + SPA bundler | `vite.config.ts`, `package.json` |
| @vitejs/plugin-react | ^5.0.4 | React Fast Refresh / JSX transform | `vite.config.ts` |
| esbuild | ^0.25.0 | Server bundling (`vite build` + esbuild → `dist/server.cjs`, CJS, packages external) | `package.json` build script |
| autoprefixer | ^10.4.21 | CSS vendor prefixing | `package.json` |
| @types/node | ^22.14.0 | Node.js type definitions | `package.json` |
| @types/express | ^4.17.21 | Express type definitions | `package.json` |

## Language & Compiler Configuration

- **TypeScript ~5.8.2**, `ES2022` target, `ESNext` modules, `bundler` module resolution.
- `jsx: react-jsx`, `isolatedModules`, `allowImportingTsExtensions`, `noEmit` (type-checking only; Vite/esbuild emit).
- `experimentalDecorators: true` enabled.
- Linting is type-check only: `npm run lint` → `tsc --noEmit`. No ESLint/Prettier configured.

## NPM Scripts

| Script | Command | Description |
|---|---|---|
| `dev` | `tsx server.ts` | Run Express + Vite middleware dev server (port 3000) |
| `build` | `vite build && esbuild server.ts --bundle ...` | Production build (client → `dist/`, server → `dist/server.cjs`) |
| `start` | `node dist/server.cjs` | Run production server |
| `preview` | `vite preview` | Preview the built client |
| `clean` | `rm -rf dist server.js` | Remove build artifacts |
| `lint` | `tsc --noEmit` | Type-check |

## External Data & Services

| Service | Role |
|---|---|
| Elliptic / Elliptic++ (Kaggle) | Primary dataset — Bitcoin transaction graph + actor labels for training/eval |
| mempool.space public API | Live mempool (unconfirmed Bitcoin tx) lookups, via server proxy |
| Blockstream.info / BlockCypher free-tier APIs | Optional live block-explorer tracing for demos (per README) |
| Gemini API (`gemini-2.5-flash`) | Optional AI-generated intelligence briefs |

## Environment Variables (`.env.example`)

- `GEMINI_API_KEY` — Gemini API access (optional; app degrades gracefully without it).
- `APP_URL` — hosted applet URL (AI Studio / Cloud Run).

## Deployment Context

- Originally built as a Google **AI Studio applet** (see `metadata.json`, `.env.example`, HMR-disable flag in `vite.config.ts`).
- Runs as a single Node process on port **3000**, binding `0.0.0.0`.
- No database, no paid infrastructure, no containerization in the current build.

## Explicitly NOT in the stack

- No client-side routing (React Router) or state management (Redux/Zustand) — plain React hooks.
- No graph visualization library — the transaction graph renderer is hand-rolled SVG.
- No database / persistence layer — all data is in-memory (`src/data/mockCases.ts` mock dataset) or fetched live.
- No test framework (no Jest/Vitest) or ESLint/Prettier tooling yet.
- No Streamlit (the README's "Streamlit or minimal React" decision resolved to **React**).

## Planned / Python-side stack (not yet in this repo)

Per `README.md`, the eventual graph-ML training pipeline will use **Python** with **NetworkX / PyTorch Geometric**; these are documented as the project's intended data-science stack but are not present in this repository yet.
