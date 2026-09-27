/**
 * Live pipeline trace mapping — consumes the Python FastAPI pipeline output
 * (rules, score, verdict, attribution coming from the backend Modules
 * 3a/3b/4/5** and maps it to the frontend `TraceResult` contract. No data
 * is fabricated here: when the backend is unreachable the caller receives an
 * explicit `fallback` envelope, and when the pipeline honestly answers that
 * there is nothing to trace it receives an explicit `empty` envelope (see
 * `runPipelineTrace`) — neither carries a trace.
 */

import { TraceResult, WalletNode, TransactionEdge, RiskVerdict, RuleFlag, MlPrediction, ConfidenceTier, Complaint } from '../types';

// ---------------------------------------------------------------------------
// Phase R7 — live pipeline trace (real Python pipeline, not the mock engine)
// ---------------------------------------------------------------------------

/** Raw shapes returned by the FastAPI pipeline (subset the UI consumes). */
interface PipelineTraceNode { id: string; hop: number; label: number; time_step: number }
interface PipelineTrace { nodes: PipelineTraceNode[]; edges: { src: string; dst: string }[]; stats: Record<string, number> }
interface PipelineRules { rule_score: number; rule_flag: string; rules_fired: string[]; contributing_signals: Record<string, { fired: boolean; evidence: any }> }
interface PipelineScore { classified: boolean; risk_score: number | null; prediction: string | null; flag_threshold?: number }
interface PipelineVerdict { verdict: string; contributing_signals: any }
interface PipelineAttribution { name: string; category: string; confidence_tier: string; source_name: string; jurisdiction?: string | null }

/** Pipeline succeeded — real data attached. */
export interface TraceOutcomePipeline {
  source: 'pipeline';
  trace: TraceResult;
}

/**
 * Python service unreachable or returned an error envelope.
 * NO trace is attached — the caller must show an honest "pipeline
 * unavailable" state and MUST NOT fabricate data to fill the gap.
 */
export interface TraceOutcomeFallback {
  source: 'fallback';
  note: string;
  // Deliberately no `trace` field — callers that branch on source will get a
  // type error if they try to access one, making silent mock-use impossible.
}

/**
 * The pipeline answered honestly that there is nothing to trace for this
 * address: it is not in the ingested Elliptic dataset and the block explorers
 * returned no on-chain history (or rejected the address shape itself).
 *
 * This is a valid *answer*, not a service failure — the caller must present it
 * as such (it must NOT show "pipeline unavailable") and must NOT fabricate a
 * trace to fill the gap. Deliberately no `trace` field.
 */
export interface TraceOutcomeEmpty {
  source: 'empty';
  note: string;
}

/**
 * The pipeline answered with a subgraph but without a complete signal set —
 * e.g. one of the parallel signal calls returned a no-data envelope. Showing
 * that graph with the rule/ML fields defaulted to 0 would read as "no rules
 * fired"/"risk 0", i.e. a fabricated claim, so no trace is attached at all.
 * Deliberately no `trace` field.
 */
export interface TraceOutcomeIncomplete {
  source: 'incomplete';
  note: string;
}

/**
 * The Python service is REACHABLE but the public block explorers could not
 * answer right now (HTTP 429 rate-limit, a timeout, or an explorer outage) —
 * or the proxy itself timed out waiting.
 *
 * This is a transient, retryable state and says NOTHING about the address: it
 * must never be presented as "invalid address", "no history", or "no rules
 * fired", and no trace is attached (the user must retry).
 */
export interface TraceOutcomeRetryable {
  source: 'retryable';
  /** Machine-readable cause: rate-limited | timeout | api-error | service-error. */
  kind: string;
  note: string;
  // Deliberately no `trace` field.
}

/**
 * The pipeline rejected the REQUEST itself (bad/oversized input, wrong shape) —
 * a client problem, not a service failure, and not a statement about the chain.
 */
export interface TraceOutcomeInvalidInput {
  source: 'invalid_input';
  note: string;
  // Deliberately no `trace` field.
}

export type TraceOutcome =
  | TraceOutcomePipeline
  | TraceOutcomeFallback
  | TraceOutcomeEmpty
  | TraceOutcomeIncomplete
  | TraceOutcomeRetryable
  | TraceOutcomeInvalidInput;

const LABEL_TEXT: Record<number, string> = {
  1: 'Illicit-labeled transaction (Elliptic)',
  0: 'Licit-labeled transaction (Elliptic)',
  [-1]: 'Unlabeled transaction (Elliptic)',
};

/**
 * Operational-failure `source` values the pipeline may report. They describe the
 * REQUEST (transient explorer problems), never the address — see the state table
 * in runPipelineTrace's docstring.
 */
const PIPELINE_FAILURE_SOURCES = new Set(['rate-limited', 'timeout', 'api-error']);

/**
 * Human-readable reason for a failed cluster/attribution lookup, used in the
 * attribution citation so the UI can state WHY the check produced no verdict
 * (never implying "we looked and found nothing").
 */
function attributionStatusReason(status?: string): string {
  if (status === 'lookup-failed') return ' (the cluster service was rate-limited, timed out or returned an error)';
  return '';
}

/**
 * Run the reported wallet through the real pipeline via the Node proxy
 * (`POST /api/trace`) and map the response to the `TraceOutcome` contract.
 *
 * Returned states are deliberately distinct and never collapsed:
 *   'pipeline'      — full real result (subgraph + rule signal + verdict)
 *   'empty'         — the pipeline answered: nothing exists to trace for this
 *                      address (honest answer, NOT a service failure)
 *   'incomplete'    — the pipeline answered with a subgraph but an incomplete
 *                      signal set (e.g. one parallel call came back empty)
 *   'retryable'     — the pipeline is reachable but the public block explorers
 *                      are rate-limiting / timing out / down (transient; the
 *                      address was never concluded on)
 *   'invalid_input' — the pipeline REJECTED the request (client problem)
 *   'fallback'      — the Python service is unreachable / errored
 *
 * Every non-'pipeline' outcome carries NO trace: this function never fabricates
 * data to fill the gap, and the caller is responsible for surfacing the
 * corresponding honest UI state.
 *
 * Principle: LEDGR's identity is "never fabricate results" — and, equally,
 * "never let one honest failure mode masquerade as another".
 */
export async function runPipelineTrace(
  address: string,
  hopDepth: number,
  customComplaint?: Complaint   // passed through to liveTrace.complaint in the pipeline-success path
): Promise<TraceOutcome> {
  // `import.meta.env` only exists under Vite. Optional access keeps identical
  // behaviour in the browser while letting the real mapping be exercised by
  // plain-Node regression tests (see test/pipeline-sequenced-traces.test.ts).
  const API_URL = (import.meta as any)?.env?.VITE_API_URL ?? "";
  const response = await fetch(`${API_URL}/api/trace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      address: address.trim(),
      hop_depth: hopDepth
    })
  });

  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    // A non-JSON body means the PROXY itself failed (e.g. an Express 413 for an
    // oversized body, or a crash) — a different failure from "the pipeline said
    // something", and it must be reported as such rather than surfacing as a
    // generic unexpected error.
    return {
      source: 'fallback',
      note: `Proxy responded HTTP ${response.status} with a non-JSON body — the request did not reach the pipeline, so nothing is known about this address. No trace data is shown; check the Node server logs.`,
    };
  }

  try {
    return mapPipelineEnvelope(payload, address, hopDepth, customComplaint);
  } catch (err) {
    // Last-resort net. A response shape this mapper does not understand must
    // surface as an explicit, diagnosable fallback — never as fabricated data
    // and never as the App's generic "unexpected error" message.
    return {
      source: 'fallback',
      note: `Python pipeline answered with a response this UI could not map (${(err as Error)?.message ?? String(err)}) — no trace data is shown.`,
    };
  }
}

/**
 * Pure response mapper — no network access, no browser globals, so it is
 * directly regression-testable (see test/pipeline-sequenced-traces.test.ts).
 *
 * Why the guards below exist: the Node proxy (`server.ts` `POST /api/trace`)
 * composes its envelope from five *independent* Python calls (`/trace`,
 * `/rules`, `/score`, `/verdict`, `/clusters`). Any of those can legitimately
 * come back without a graph — the backend reports "no such wallet / no
 * on-chain history" as `{source: 'not-found-on-chain', note, address}`, and its
 * 404 branch as `{found: false, note, score}` — so an envelope tagged
 * `source: 'pipeline'` does NOT guarantee that `data.trace.nodes`,
 * `data.trace.edges`, `data.rules.rules_fired` or `data.verdict.verdict` exist.
 *
 * Previously those fields were dereferenced unconditionally, so an honest
 * "nothing to trace" answer (or one rate-limited parallel signal call) threw a
 * TypeError inside this mapper; the caller caught it and mislabelled the
 * request as "pipeline unavailable — unexpected error" even though the
 * pipeline had answered 200 with a correct result. Each case is handled
 * explicitly below instead.
 */
export function mapPipelineEnvelope(
  payload: any,
  address: string,
  hopDepth: number,
  customComplaint?: Complaint,
): TraceOutcome {
  // No mock/fallback engine exists to fill the gap — returning fabricated data as if
  // it were real pipeline output violates the project's core "no fabrication" rule
  // (AGENTS.md "No placeholders or mocks standing in for real implementation").
  // Each service-level source gets its own honest outcome; none of them may be
  // folded into another (see the state table in runPipelineTrace's docstring).
  if (payload?.source === 'retryable') {
    // The pipeline is up; the block explorers are rate-limiting / down / slow.
    return {
      source: 'retryable',
      kind: payload.kind ?? 'unknown',
      note: payload.note
        ?? 'The block explorers are temporarily unavailable — nothing can be concluded about this address right now. Retry shortly.',
    };
  }
  if (payload?.source === 'invalid-input') {
    // The request was rejected by the pipeline/proxy (bad input) — a client
    // problem, distinct from both "unreachable" and "no such address".
    return {
      source: 'invalid_input',
      note: payload.note ?? 'The pipeline rejected this request as invalid — nothing was looked up.',
    };
  }
  if (payload?.source !== 'pipeline' || !payload?.data) {
    return {
      source: 'fallback',
      note: payload?.note ?? 'Python pipeline service unavailable — no trace data available. Start the backend with: cd backend && uvicorn ledgr.service:app --reload',
    };
  }

  const data = payload.data as {
    trace?: PipelineTrace & { source?: string; note?: string; format_reason?: string };
    rules?: PipelineRules;
    score?: PipelineScore | null;
    verdict?: PipelineVerdict;
    attribution?: PipelineAttribution | null;
    attribution_status?: 'matched' | 'no-match' | 'lookup-failed';
  };
  const { trace, rules, score, verdict, attribution } = data;

  // The pipeline's own INVALID-INPUT answer (malformed / non-mainnet address, or
  // an address both explorers rejected). It arrives as a 200 with its own source
  // and no graph. This is a statement about the INPUT — NOT about the chain, so it
  // must not be reported as "no on-chain history" (and, before the 2026-09-26
  // hardening, a rate-limited lookup could land in this very bucket).
  if (trace?.source === 'invalid-address-format') {
    return {
      source: 'empty',
      note: trace?.note
        ?? `Not a valid mainnet Bitcoin address${trace?.format_reason ? ` (${trace.format_reason})` : ''} — nothing was looked up and no signal is computed.`,
    };
  }

  // Defence in depth: a pipeline that reports an OPERATIONAL failure inside a
  // 200 envelope (an older/other backend, or a future refactor) must never be
  // read as "nothing exists for this address". These are transient states about
  // the REQUEST, not conclusions about the address.
  if (trace?.source && PIPELINE_FAILURE_SOURCES.has(trace.source)) {
    return {
      source: 'retryable',
      kind: trace.source,
      note: trace?.note
        ?? `The block explorers could not answer this lookup right now (${trace.source}) — nothing was concluded about the address. Retry shortly.`,
    };
  }

  const graphAvailable = Array.isArray(trace?.nodes) && Array.isArray(trace?.edges);

  if (!graphAvailable) {
    // Honest answer from the pipeline itself: not in the ingested Elliptic
    // dataset and no on-chain history (or the explorers rejected the address
    // shape). Report it as such — no trace is fabricated and this is NOT a
    // service outage. The backend's own note is preferred verbatim.
    return {
      source: 'empty',
      note: trace?.note
        ?? (data as any).note
        ?? `No trace exists for ${address.trim()}: it is not present in the ingested Elliptic dataset and the block explorers returned no on-chain history. No signal was computed (nothing fabricated).`,
    };
  }

  const ruleSignalAvailable =
    !!rules && typeof rules.rule_score === 'number' && Array.isArray(rules.rules_fired);
  const verdictAvailable = !!verdict && typeof verdict.verdict === 'string';

  if (!ruleSignalAvailable || !verdictAvailable) {
    // A subgraph came back but one of the independent signal calls did not
    // (routine on live lookups when a parallel call is rate-limited or times
    // out). Defaulting the missing fields to 0 would render as "no rules
    // fired"/"risk 0" — a fabricated claim — so nothing is shown instead.
    const missing = [
      ruleSignalAvailable ? null : 'rule-based signal',
      verdictAvailable ? null : 'correlation verdict',
    ].filter(Boolean).join(' and ');
    return {
      source: 'incomplete',
      note: `Pipeline returned a subgraph for ${address.trim()} but no ${missing} — no trace is shown rather than a result with fabricated signal values. Retry; if it persists, check the Python backend logs.`,
    };
  }

  const t = trace as PipelineTrace;
  // Narrowed by the guards above: a full graph is only mapped when both signal
  // blocks are complete, so neither alias can be undefined here.
  const r = rules as PipelineRules;
  const v = verdict as PipelineVerdict;
  const stats = t.stats || {};
  const seedRisk = score?.classified && typeof score.risk_score === 'number' ? score.risk_score : 0;

  // Honest mapping: the Elliptic dataset carries no BTC amounts, so monetary
  // fields are 0 rather than fabricated; per-node signals are only attached to
  // the reported wallet (`evaluated: true`), subgraph members stay structural.
  const nodes: WalletNode[] = t.nodes.map((n) => ({
    id: n.id,
    label: LABEL_TEXT[n.label] ?? 'Unlabeled transaction (Elliptic)',
    type: n.hop === 0 ? 'suspect_root' : 'intermediary',
    hop: n.hop,
    balanceBtc: 0,
    totalReceivedBtc: 0,
    totalSentBtc: 0,
    txCount: 0,
    firstSeen: n.time_step >= 0 ? `time-step ${n.time_step}` : 'unknown',
    lastSeen: n.time_step >= 0 ? `time-step ${n.time_step}` : 'unknown',
    ruleFlag: 'none',
    ruleReasons: [],
    mlScore: 0,
    mlPrediction: 'unknown',
    verdict: 'none',
    evaluated: false,
  }));

  const seed = nodes.find((n) => n.id === address.trim()) ?? nodes[0];
  if (seed) {
    seed.ruleFlag = (r.rule_score >= 60 ? 'high' : r.rule_score > 0 ? 'low' : 'none') as RuleFlag;
    seed.ruleReasons = r.rules_fired;
    seed.mlScore = seedRisk;
    seed.mlPrediction = score?.prediction === 'illicit' ? 'illicit' : score?.prediction === 'licit' ? 'licit' : 'unknown';
    seed.verdict = (v.verdict as RiskVerdict) ?? 'none';
    seed.evaluated = true;
  }

  const edges: TransactionEdge[] = t.edges.map((e, i) => ({
    id: `pe-${i}`,
    from: e.src,
    to: e.dst,
    txHash: `${e.src}->${e.dst}`,
    amountBtc: 0,
    amountInr: 0,
    timestamp: 'unknown',
    feeBtc: 0,
    hop: 0,
  }));

  const cs = r.contributing_signals || {};
  const fired = (k: string) => !!cs[k]?.fired;
  const ev = (k: string) => cs[k]?.evidence ?? {};
  const heuristicsSummary = r.rules_fired.length
    ? r.rules_fired.map((rule) => `${rule} fired: ${JSON.stringify(ev(rule))}`)
    : ['No rule-based heuristic fired for the reported wallet.'];

  // "No sourced exchange match" is a CONCLUSION — it is only honest when the
  // cluster lookup actually completed. When it failed (rate-limited/down), saying
  // "no match" would be a confident wrong state, so the UI is told the check
  // could not be made instead.
  const attributionLookupFailed = !attribution && data.attribution_status === 'lookup-failed';

  const liveAttribution = {
    name: attributionLookupFailed
      ? 'Attribution lookup unavailable — the cluster lookup did not complete, so NO match conclusion was reached (retry later)'
      : attribution?.name ?? 'Unattributed (no sourced exchange match)',
    category: (attribution?.category as any) ?? 'Unknown',
    confidenceTier: (attribution?.confidence_tier as ConfidenceTier) ?? 'unattributed',
    sourceCitation: attributionLookupFailed
      ? `Cluster lookup did not complete${attributionStatusReason(data.attribution_status)}; it is not known whether this wallet matches a known exchange/VASP cluster.`
      : attribution?.source_name ?? 'Unattributed (no supplementary source matched)',
    depositAddress: address.trim(),
    riskLevel: (v.verdict === 'confirmed' ? 'CRITICAL' : v.verdict === 'watch' ? 'ELEVATED' : 'LOW') as 'CRITICAL' | 'ELEVATED' | 'LOW',
    jurisdiction: attribution?.jurisdiction ?? 'Unknown',
    complianceNoticeTarget: {
      legalEntity: attribution?.name ?? 'Unattributed entity',
      grievanceOfficerEmail: 'Not available — no supplementary source matched this cluster',
      statutoryReference: 'Section 91 CrPC / Section 94 BNSS (as applicable)',
    },
  };

  const liveTrace: TraceResult = {
    targetAddress: address.trim(),
    complaint: customComplaint,
    nodes,
    edges,
    verdict: (v.verdict as RiskVerdict) ?? 'none',
    hopDepth: stats.hop_depth_requested ?? hopDepth,
    contributingSignals: {
      ruleScore: r.rule_score,
      ruleFlag: (r.rule_score >= 60 ? 'high' : r.rule_score > 0 ? 'low' : 'none') as RuleFlag,
      ruleDetails: {
        peelChainDetected: fired('peel_chain'),
        peelChainDetails: fired('peel_chain') ? JSON.stringify(ev('peel_chain')) : undefined,
        rapidFanOutDetected: fired('rapid_fan_out'),
        fanOutDetails: fired('rapid_fan_out') ? JSON.stringify(ev('rapid_fan_out')) : undefined,
        mixerProximityDetected: fired('mixer_adjacent'),
        mixerDetails: fired('mixer_adjacent') ? JSON.stringify(ev('mixer_adjacent')) : undefined,
        heuristicsSummary,
      },
      mlScore: seedRisk,
      mlPrediction: (score?.prediction as MlPrediction) ?? 'unknown',
      mlConfidence: seedRisk,
      featureHighlights: [],
    },
    attribution: liveAttribution,
    summaryStats: {
      totalTrackedBtc: 0,
      totalTrackedInr: 0,
      hopCount: stats.max_hop_reached ?? hopDepth,
      attributedVasp: liveAttribution.name,
      confirmedIllicitNodes: stats.illicit_nodes ?? 0,
      watchNodes: 0,
      peelHopsCount: 0,
    },
  };

  return { source: 'pipeline', trace: liveTrace };
}
