# Methodology

This document covers evaluation methodology only: how the entity-based split is implemented, what metrics are reported and why, and how the rule-based and learned signals are validated independently before being correlated. For dataset structure and the *rationale* for the entity split, see `DATA.md`. For module boundaries, see `ARCHITECTURE.md`.

---

## 1. Entity-based train/test split

### Why (brief recap)

Elliptic labels are inherited from the real-world entity an address belongs to. A random transaction-level split lets the same entity appear in both train and test, so a model can memorize entity-level patterns instead of generalizing — invalidating any accuracy claim for the actual use case (tracing a wallet the system has never seen).

### How it's implemented

1. **Define "entity" operationally.** Using Elliptic++'s actor/address dataset, group addresses/transactions by their underlying actor/entity identifier where available. Where entity identity isn't directly labeled, use connected-component clustering on the transaction graph as a conservative proxy — treat tightly-connected address clusters as belonging to one entity for split purposes, erring toward larger (safer) entity groupings rather than risking a false split.
   - **Hub-node safeguard:** raw connected-component clustering on a Bitcoin transaction graph can collapse into a single giant component, since high-degree hub addresses (major exchange hot wallets) connect to huge numbers of otherwise-unrelated addresses. Before computing components, identify and exclude/cap known high-degree hub addresses (e.g. by a degree threshold) from the component-forming step so one hub doesn't merge thousands of unrelated entities into one blob and unbalance or shrink the usable split. This exclusion step and its threshold are logged alongside the rest of the split methodology, same as the leakage check below.
2. **Split at the entity level, not the transaction level.** Randomly assign entire entities to train or test (e.g., 70/30 or 80/20 split, to be finalized once the full entity graph is built in Phase 1). No entity may have any of its addresses/transactions in both sets.
3. **Verify no leakage post-split.** After splitting, programmatically confirm that no address/transaction/entity ID appears in both the train and test sets. This check is run automatically, not just visually inspected, and its result is logged as part of the training run output.
4. **Time-awareness (secondary check).** Elliptic transactions have a time-step structure. Where feasible, prefer a split that also respects time ordering (train on earlier time-steps, test on later ones) in addition to entity separation, since this better simulates the real deployment scenario of tracing wallets whose activity postdates model training. If entity- and time-based splitting conflict in a way that shrinks the usable test set too much, entity-safety takes priority — a smaller but leakage-free test set is preferred over a larger one with entity leakage.

### What gets reported

Every reported metric in this project states explicitly that it comes from an entity-based split. Any metric that doesn't (e.g., a quick sanity-check run during development) is labeled as such and never presented as the project's headline result.

---

## 2. Metrics

Given the PS's evaluation emphasis — catching real fraud cases, in a domain with severe class imbalance (illicit transactions are a small minority) — accuracy alone is not reported as a meaningful metric; it can look high while missing most actual fraud.

**Primary metrics:**
- **Recall (illicit class)** — of all actually-illicit wallets/transactions in the test set, how many did the system flag (confirmed or watch)? This is weighted most heavily, since missing real fraud cases has direct real-world cost (delayed asset freezing, lost evidence).
- **Precision (illicit class)** — of everything flagged, how much was actually illicit? Reported alongside recall so a high-recall/low-precision system (flagging everything) isn't mistaken for a good result.
- **F1 score (illicit class)** — single combined number for quick comparison across model iterations, but never reported alone without the underlying precision/recall.

**Secondary metrics:**
- **Confirmed vs. watch breakdown** — what fraction of true positives land in the "confirmed" (both signals agree) tier vs. "watch" (single signal) tier. This directly measures whether the two-signal correlation principle is adding value or just being conservative.
- **Per-signal recall/precision** (rule-based alone, learned alone) — reported separately before correlation, so the correlation layer's effect can be measured against each individual signal rather than assumed.

**Explicitly not used as a headline metric:** raw accuracy, due to class imbalance; and any metric computed on a non-entity-safe split, for the reasons above.

---

## 3. Independent validation of each signal before correlation

The correlation layer (`ARCHITECTURE.md` Module 4) is only meaningful if each input signal is independently validated first — otherwise "two signals agreeing" could just mean "two correlated, non-independent measurements agreeing with each other," which isn't stronger evidence.

**Rule-based signal (3a):**
- Each heuristic (peel chain, rapid fan-out, mixer-adjacent hop) is validated separately against known-pattern examples — either literature-documented laundering patterns or manually constructed synthetic test cases — before being run against the full dataset.
- False-positive rate of each heuristic is checked against clearly-licit wallets in the test set, to catch heuristics that are too aggressive.

**Learned signal (3b):**
- Evaluated on the entity-safe test split using the metrics in Section 2, independently of anything the rule-based engine outputs.
- Compared against a simple baseline (e.g., random forest on the 166 handcrafted features) to confirm any added model complexity (e.g., a GNN) is actually earning its keep over the baseline.

**Independence check:**
- Before finalizing the correlation layer, measure the overlap between rule-based flags and learned-signal flags on the test set. If overlap is very high, the two signals may not be adding independent information, and this is documented honestly rather than presented as if two-signal agreement were stronger evidence than it actually is in practice.

---

## 4. What "confirmed" and "watch" mean, precisely

- **Confirmed:** rule-based signal flags the wallet AND learned-signal confidence exceeds a threshold (threshold value to be tuned during Phase 4/5 and documented once finalized, not left as an unstated magic number).
- **Watch:** exactly one of the two signals flags the wallet.
- **None:** neither signal flags the wallet.

These thresholds and their tuning process are logged (not just the final values) so the decision is auditable rather than presented as an unexplained cutoff.

**Language caution for reporting:** "Confirmed" here means *two independent, imperfect signals agree* — it is not legal proof and should never be presented or narrated as investigation-grade certainty, given this maps to a real law-enforcement use case (I4C). Module 6's report output and any demo narration should state this explicitly (e.g. "confirmed = flagged by both an independent heuristic and a learned model; an investigative lead, not a determination of guilt"), consistent with the same honesty discipline already applied to the `elliptic-derived` vs `supplementary-source` confidence tags in `DATA.md`/`ARCHITECTURE.md`.
