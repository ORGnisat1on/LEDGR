# Demo Script — SIH26183 (R10 Final)

**Audience:** SIH judges / evaluators
**Duration:** 5–7 minutes live walkthrough
**Mode:** Dashboard running locally (backend + frontend), backend API also callable directly

---

## Walkthrough Order (suggested)

### 1. Open Dashboard → Methodology Modal (30 sec)
**Do this first.** Click "Benchmark Methodology" in the header.
- Shows the **honest metrics upfront**: Illicit recall **1.7%**, Precision **50.0%**, F1 **0.033** (time-respecting entity-safe split, test at time-steps 45–49).
- Shows the **Weber et al. (2019)** concept-drift citation (time-step 43 Abraxas shutdown).
- Shows the **legal framing**: "Confirmed = two independent imperfect signals agree; an investigative lead, not a determination of guilt" (Section 91 CrPC / Section 94 BNSS).
- Shows **out-of-dataset disclosure**: wallets not in Elliptic feature set → `classified: false`, no risk fabricated.

> **Why first:** It frames everything that follows. The judge sees the honesty layer before any result, so no metric can be misread as overclaiming.

---

### 2. Live Wallet Trace — In-Dataset "Confirmed" (60 sec)
**Address:** `298938351` (Elliptic node-id, true label: illicit)

**Click Trace.** Observe:
- **Source:** `elliptic-indexed` (no network call, instant)
- **Trace graph:** peel-chain structure visible (repeated large-forward + small-peel hops)
- **Rules panel:** `peel_chain: true`, `rapid_fan_out: false`, `mixer_adjacent: false` (dormant — by design)
- **Learned signal:** `risk_score: 1.0`, `learned_flag: true`, `classified: true`
- **Verdict:** **CONFIRMED** (both signals agree)

**Narrate:** "This is the rare, hard-won `confirmed` — both the structural heuristic (peel chain) and the learned model independently flag this wallet. The correlation layer requires agreement precisely because neither signal alone is reliable enough."

---

### 3. Live Wallet Trace — In-Dataset "Watch" (Rule Only) (30 sec)
**Address:** `232438397` (Elliptic node-id, true label: **licit**)

**Click Trace.** Observe:
- **Rules panel:** `peel_chain: true` (false positive — retail-style wallet)
- **Learned signal:** `risk_score: 0.02`, `learned_flag: false`
- **Verdict:** **WATCH** (only rule fired)

**Narrate:** "This is a *licit* wallet that trips the peel-chain heuristic. Because the learned signal does not agree, it stays at `watch` — never escalated to `confirmed`. This is the correlation layer doing its job: one imperfect signal is not enough."

---

### 4. Live Wallet Trace — In-Dataset "Watch" (Learned Only) (30 sec)
**Address:** `232629023` (Elliptic node-id, true label: illicit)

**Click Trace.** Observe:
- **Rules panel:** all false
- **Learned signal:** `risk_score: 0.85`, `learned_flag: true`
- **Verdict:** **WATCH** (only learned fired)

**Narrate:** "The learned signal catches something the rules miss. Still `watch` — agreement required."

---

### 5. Live Lookup — Real BTC Address (Binance Cold Wallet) (60 sec)
**Address:** `34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` (from `data/exchanges.txt`, BitInfoCharts sourced)

**Enable** `LEDGR_LIVE_TRACING=1` (or confirm it's on).

**Important — set Hop Depth to 1 before Tracing:** Click `1H` on the **Depth** selector in the fund-flow graph toolbar (top of the graph card). This address's default hop depth of 2 was measured at **55–60 s+** — the frontier fans out to 6,755 counterparty addresses at hop 1 alone, well past the **30 s** proxy timeout (`LIVE_FETCH_TIMEOUT_SECONDS`). Hop depth **1** completes in **~2.5 s** and still demonstrates the live Blockstream/BlockCypher integration and the watch-verdict cap. **Then click Trace.** Observe:
- **Source:** `live-lookup` (real Blockstream/BlockCypher calls)
- **Trace graph:** real on-chain counterparties
- **Rules panel:** runs on live graph (peel-chain/fan-out if structure matches)
- **Learned signal:** `classified: false`, `note: "address not in Elliptic feature set..."`
- **Verdict:** **WATCH** at most (capped by code — live verdicts can never be `confirmed` because learned signal is unavailable)
- **Clusters:** click "View Clusters" → `GET /clusters/live` → `TIER_LIVE_UTXO` clusters via common-input/change-address heuristics
- **Attribution:** if a cluster matches `data/exchanges.txt`, shows `supplementary-source: "Binance cold wallet (BitInfoCharts, 2026-09-06)"` — visibly lower confidence than `elliptic-derived`

**Narrate:** "This is a real, current Bitcoin address. The learned model honestly says 'I cannot score this — it's outside my training data.' The verdict is capped at `watch`. Named-exchange attribution only works here because we have real BTC addresses to match against the BitInfoCharts-sourced hot-wallet list. On the indexed Elliptic graph, this matching is structurally impossible (anonymized node IDs) — and we surface that explicitly."

---

### 6. Non-Existent / Invalid Address (15 sec)
**Address:** `1InvalidAddressThatDoesNotExist123`

**Click Trace.** Observe:
- **Response:** `200 OK`, `source: "not-found-on-chain"`, `available: false`
- **Not a 503, not an error** — honest "no history found" response

**Narrate:** "Invalid but syntactically-valid addresses return an honest 'not found' — no fabricated data, no 503."

---

## Framing the 1.7% Recall (when it comes up)

**Do not apologize. Do not downplay. Frame it as a documented finding demonstrating rigor.**

> **Suggested language:**
> "The 1.7% illicit recall is not a defect — it's a *finding*. We caught temporal leakage in the standard Elliptic evaluation (random split gave ~94% recall, which is the leakage signature). We rebuilt the split to be time-respecting at the entity level (train 1–42, test 45–49), enforced span-0 programmatically, and the honest result is 1.7% recall. This matches the published literature: Weber et al. (2019) and GuiltyWalker document a concept-drift event at time-step 43 (Abraxas shutdown) that makes pre-shift features not generalize post-shift.
>
> The low recall is *exactly why* our correlation layer requires two independent signals to agree for a `confirmed` verdict. The rule engine adds 2 peel-chain catches beyond the ML's 2, giving a union recall of 3.45%. Neither signal alone is treated as sufficient. This is the methodology working as intended — an honest baseline, not a tuned one."

---

## Anticipated Judge Questions & Honest Answers

### Q1: "Why is recall so low (1.7%)? Does the ML model not work?"

**A:** "The low recall is a *documented finding*, not a failure. The Elliptic dataset has a known concept-drift event at time-step 43 (Abraxas market shutdown, Weber et al. 2019). A random train/test split leaks future entity patterns into training, inflating recall to ~94% — that's the leakage signature we caught. Our time-respecting entity-safe split (test at time-steps 45–49) gives the honest baseline: 1.7% recall, 50% precision, F1 0.033. This matches published literature on the same dataset. The correlation layer exists *because* neither signal alone is reliable — a wallet is only `confirmed` when both the rule-based heuristic and the learned model independently agree."

### Q2: "Does this work on real 2026 wallets? The dataset ends in 2018."

**A:** "The learned signal explicitly does *not* score live wallets — it returns `classified: false` with a note: 'address not in Elliptic feature set; model cannot score it and no risk is fabricated.' The dashboard surfaces this limitation in the Methodology modal and footer banner: 'live-traced wallets operating after the dataset window are outside the model's validated regime.' On live wallets, only the rule-based heuristics (peel-chain, rapid fan-out) run, and verdicts are capped at `watch` — they can never be `confirmed` because the learned signal is unavailable. This is enforced in code (`service.py`), not just documented."

### Q3: "What about mixers? You have a mixer-adjacent heuristic but no mixer addresses."

**A:** "We investigated this genuinely (2026-09-06). We checked Europol/Chainalysis ChipMixer reporting and the academic cryptocurrency tumbler literature. These sources describe *services* but publish no exact, verifiable Bitcoin addresses. Academic datasets exist but were not accessible to verify entry-by-entry. Per our sourcing rule (never fabricate), `data/mixers.txt` is intentionally empty and the `mixer_adjacent` heuristic stays dormant — it never fires on made-up addresses. This is a documented, closed investigation with a 'no' answer, not an open TODO. It's listed in SCOPE.md under 'Explicitly out of scope' as a completed investigation."

### Q4 (bonus): "Is this connected to SAHYOG/NCRP?"

**A:** "No. We have no access path to either platform. The input format is *designed to be compatible* with what such platforms would need, and the demo runs against a mocked complaint-intake interface. Any 'integration' language refers to format compatibility only — there are no live API calls to SAHYOG or NCRP anywhere in the codebase."

### Q5 (bonus): "Why Bitcoin only? What about Ethereum/DeFi?"

**A:** "Bitcoin-only is the committed MVP (SCOPE.md). Ethereum is a stretch goal — a separate code path because the address/UTXO model is fundamentally different. DeFi protocols, cross-chain bridges, and privacy chains are explicitly out of scope. The architecture is designed to extend (Module 1/2 would need chain-specific ingestion; Modules 3–6 are largely chain-agnostic if fed a normalized graph), but nothing beyond Bitcoin is implemented."

---

## Demo Checklist (pre-flight)

- [ ] Backend running: `LEDGR_LIVE_TRACING=1 uvicorn ledgr.service:app --reload` (port 8000)
- [ ] Frontend running: `npm run dev` (port 3000, proxies `/api/*` to backend)
- [ ] Methodology modal renders (click "Benchmark Methodology" in header)
- [ ] In-dataset addresses work: `298938351` → CONFIRMED, `232438397` → WATCH (rule only), `232629023` → WATCH (learned only)
- [ ] Live lookup works: `34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` → **set Hop Depth to `1` first** (click `1H` on the Depth selector; the default hop depth 2 exceeds the 30 s timeout on this address — measured 55–60 s+ vs ~2.5 s at 1H), then live-lookup, clusters button works, attribution shows
- [ ] Invalid address: `1InvalidAddressThatDoesNotExist123` → not-found-on-chain (200, not 503)
- [ ] Footer honesty banner visible: "Validated regime: Elliptic time-steps 1–49 (through ~2018) | Confirmed = two imperfect signals agree, not proof of guilt"

---

## Files Referenced in Demo

| File | Role |
|------|------|
| `data/exchanges.txt` | 6 BitInfoCharts-sourced cold wallets (source + date per entry) |
| `data/mixers.txt` | Intentionally empty — investigation documented in header |
| `artifacts/model_eval.json` | Honest metrics (recall 0.017, precision 0.500, F1 0.033, confusion matrix) |
| `artifacts/split_verification.json` | 14,270/14,270 entities span-0, leakage_free=true |
| `artifacts/hardening_report.json` | 6/6 hardening checks PASS |
| `src/components/MethodologyModal.tsx` | Honesty-layer UI (verified visually 2026-09-06) |
| `backend/ledgr/service.py` | Live verdict cap (`live verdicts can never be confirmed`) |
| `backend/ledgr/config.py` | `LIVE_MAX_TXS_PER_ADDRESS=50`, `live_tracing_enabled()` toggle |

---

## If Something Goes Wrong

| Issue | Fallback |
|-------|----------|
| Live API rate-limited / down | Show in-dataset traces only (they're instant and deterministic). Explain live path is demo-only, capped by free-tier limits per SCOPE.md. |
| Frontend build fails | Call backend API directly via `curl`/Postman: `POST /trace`, `POST /verdict`, `GET /clusters/live`. All endpoints documented in `backend/README.md`. |
| Judge asks for untracked wallet | Have the curated set ready (DEMO.md Section A/B). Don't improvise — the honest metrics mean random illicit wallets likely return `none`. |
| "Why no mixer addresses?" | Point to `data/mixers.txt` header + SCOPE.md "Explicitly out of scope" entry. It's a closed investigation, not a gap. |

---

## One-Liner for Closing

> "We built an honest system: it catches temporal leakage, reports the real baseline (1.7% recall), requires two independent signals to agree before saying 'confirmed,' never fabricates risk for out-of-dataset wallets, and explicitly surfaces every limitation in the UI. The methodology *is* the product."

---

*Last updated: 2026-09-06 (R10 scope freeze)*