# Data

## Primary dataset: Elliptic / Elliptic++

### Elliptic (base dataset)

- ~203,769 Bitcoin transactions, 234,355 directed edges.
- Each transaction is labeled **licit**, **illicit**, or **unknown**.
- 166 handcrafted features per node (local transaction features + aggregated neighborhood features).
- Publicly available on Kaggle. Widely used as an academic benchmark in published AML/fraud-detection ML research (GCNs, random forests, self-supervised graph embeddings) — this is a citable, vetted source, not an obscure or unverified one.

### Elliptic++ (extension)

- Adds an **actor/wallet-address** dataset of ~822,000 Bitcoin addresses, layered on top of the base transaction graph.
- Directly relevant to this project because the problem statement is about **wallet-level** attribution (which exchange/VASP received a wallet's funds), not just transaction-level classification. The base Elliptic dataset alone only classifies transactions; Elliptic++ is what lets this project reason about addresses/wallets.
- **Explicit Boundary - No Real Address Mapping:** The Elliptic dataset completely anonymizes node IDs as arbitrary integers. There is no linkage from real Bitcoin addresses (such as known mixers) back to the anonymized integers in the dataset graph. Consequently, the `mixer_adjacent` rule cannot be evaluated or tuned against the historical Elliptic dataset. It can only be exercised on live-traced wallets during Phase R7 where real Bitcoin addresses are present.

### Access risk (check first, Phase 1 day 1)

Unlike the base Elliptic dataset (a straightforward Kaggle download), Elliptic++'s actor/address extension has historically required requesting access separately from the dataset's authors rather than a one-click download, and availability/terms can change. Since Module 2 (wallet-level graph construction) and Module 5 (clustering/attribution) both depend on it, confirm actual download access before committing the Phase 1 timeline to it. **Fallback if Elliptic++ is unavailable or delayed:** derive address-level structure directly from the base Elliptic transaction graph (transactions reference input/output addresses even without the full actor dataset), accepting a thinner wallet-level feature set until/unless Elliptic++ access comes through.

### Where each part is used

| Dataset component | Used for |
|---|---|
| Elliptic transaction graph + labels | Training/evaluating the learned signal (Module 3b) |
| Elliptic++ actor/address dataset | Wallet-level graph construction (Module 2) and clustering/attribution (Module 5) |
| Live block-explorer APIs (Blockstream.info, BlockCypher free tier — Bitcoin only) | Demo-time only — real, current transaction data for a small number of live-traced example wallets, layered on top of the static training graph |

---

## Known caveat: entity-based label leakage

**This must be handled explicitly in the methodology, not glossed over.**

A well-documented issue in the Elliptic dataset: labels are inherited from the underlying real-world **entity** (e.g., a specific exchange or actor) that an address/transaction belongs to, not assigned independently per transaction. If the train/test split is done **randomly at the transaction level**, transactions from the same entity can end up in both the training set and the test set. A model can then achieve high test accuracy by effectively **memorizing entity-level patterns** it already saw in training, rather than generalizing to genuinely unseen wallets/entities — which is exactly the case that matters for this project's actual use case (a victim reports a wallet the system has never seen before).

**Decision (binding for this project):** all evaluation splits for the learned signal (Module 3b) must be done **by entity, not by transaction.** Every transaction/address belonging to a given entity must be entirely in the training set or entirely in the test set — never split across both.

This is stated proactively rather than discovered late, because:
1. It directly determines whether the reported evaluation metrics mean anything for the real use case.
2. It signals genuine engagement with the domain literature rather than a naive benchmark run.

Implementation details of the entity-based split (how "entity" is defined operationally, how the split is verified to have no leakage) belong in `METHODOLOGY.md`, not here — this file documents *that* the caveat exists and *that* it's binding; `METHODOLOGY.md` documents *how* it's implemented.

---

## Supplementary data sources

For **named-exchange attribution** (which Elliptic's licit/illicit labels do not provide — see `SCOPE.md` point 4), the following supplementary sources may be used:
- Known exchange hot-wallet address lists (publicly available).
- Community-sourced wallet tagging services.

**These are documented and treated as a separate, lower-confidence data source from the core Elliptic-derived labels.** Any wallet cluster attributed to a named exchange via a supplementary source is tagged `supplementary-source` (lower confidence) in output, distinct from `elliptic-derived` (licit/illicit only, higher confidence, no name attached). See `ARCHITECTURE.md` Module 5 for how this distinction is carried through to reporting.

---

## Live demo data

For the live demo, free-tier public Bitcoin block explorer APIs (Blockstream.info, BlockCypher) are used to pull real, current transaction data for a **small number** of specific example wallets, traced live and shown layered on top of the static Elliptic training data. This is demo-time only and is not part of the training or evaluation pipeline — it exists to show the system tracing a real, current wallet rather than only replaying static historical data.
