# Live Demo Playbook (SIH26183)

Which wallets to use in the demo, and why. This is the *curated* set used in the
prior verification passes — it is not a promise about arbitrary wallets.

> **Read this first:** the learned signal's real-data recall is **0.017** (see
> README caveat c). A randomly chosen illicit wallet is very unlikely to be
> flagged. **The demo must not rely on picking an illicit wallet live on the spot.**
> Use the specific addresses below — each was verified to reach the tier it is
> listed under.

## A. In-dataset wallets (work from the pre-indexed Elliptic graph, no network)

These are node-ids in the Elliptic dataset (not real BTC addresses). They trace
and verdict offline from `artifacts/graph_index.pkl`.

| Address | True label | What it demonstrates |
|---|---|---|
| `298938351` | illicit | **CONFIRMED** — peel-chain rule fires AND learned risk = 1.0 agree: a genuine `confirmed` verdict |
| `54824221` | illicit | **CONFIRMED** — peel-chain + learned (risk 1.0) |
| `209710576` | illicit | **CONFIRMED** — peel-chain + learned (risk 0.995) |
| `232629023` | illicit | **WATCH** — learned signal only (no rule fires): the one-signal hit is a lead, not confirmed |
| `230389796` | illicit | **WATCH** — learned signal only |
| `232438397` | licit | **WATCH, false-positive case** — retail-style wallet the `peel_chain` rule flags but the learned model does not: shows why agreement is required |

Note the `232438397` row is the *deliberate* demonstration: a licit wallet
tripping one imperfect rule stays at `watch`, never `confirmed`, because the
two-signal correlation requires independent agreement.

## B. Live-lookup wallets (need network — R9 Blockstream/BlockCypher)

These are real Bitcoin addresses, not in the Elliptic dataset. They trace
through the **live-lookup** path (real on-chain counterparties). They get no
learned risk and no `confirmed` verdict — the live verdict is capped at
`watch` because only one signal (rules) can run on a real address.

| Address | Real-world identity |
|---|---|
| `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` | Genesis / Satoshi address (traces live, honest verdict) |
| `34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` | Binance cold wallet |
| `3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6` | Binance cold wallet (2) |
| `bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2` | Robinhood cold wallet |
| `bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97` | Bitfinex cold wallet |
| `1CY7fykRLWXeSbKB885Kr4KjQxmDdvW923` | OKX cold wallet |
| `162bzZT2hJfv5Gm3ZmWfWfHJjCtMD6rHhw` | gate.io cold wallet |
| `1FfmbHfnpaZjKFvyi1okTjJJusN455paPH` | Mt. Gox cold wallet (drained 2018) |

These same addresses are what the `data/exchanges.txt` hot-wallet list points at
— so a **live** trace of one of them is the only path where named-exchange
attribution can actually appear (see README caveat b).

## C. What the any-address trace looks like

An in-dataset address that is *not* flagged shows `none` — that is the honest
baseline and is fine to show. A non-existent address returns `not-found-on-chain`
(in valid address). A network-down live lookup returns a labeled `unavailable`
fallback, never a fake result.

## Rules of the demo

1. **Pre-select the tier.** Don't rely on the live faucet; use the curated set.
2. **Show confirmed last.** It is the rare, hard-won result (`298938351`, etc.).
3. **Show `232438397` on purpose** to explain why `confirmed` needs two signals.
4. **Frame the 0.017 recall correctly**: it is why the correlation layer exists,
   not a failure (README caveat c).