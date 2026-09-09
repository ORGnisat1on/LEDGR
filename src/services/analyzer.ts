/**
 * Live pipeline trace mapping — consumes the Python FastAPI pipeline output
 * (rules, score, verdict, attribution coming from the backend Modules
 * 3a/3b/4/5** and maps it to the frontend `TraceResult` contract. No data
 * is fabricated here: when the backend is unreachable, the caller receives
 * an explicit `fallback` envelope (see `runPipelineTrace`** with NO trace.
 */

import { TraceResult, TraceSource, WalletNode, TransactionEdge, RiskVerdict, RuleFlag, MlPrediction, ConfidenceTier, Complaint } from '../types';

// ---------------------------------------------------------------------------
// Phase R7 — live pipeline trace (real Python pipeline, not the mock engine)
// ---------------------------------------------------------------------------

/** Raw shapes returned by the FastAPI pipeline (subset the UI consumes). */
interface PipelineTraceNode { id: string; hop: number; label: number; time_step: number }
interface PipelineTrace { source?: string; capped?: boolean; nodes: PipelineTraceNode[]; edges: { src: string; dst: string }[]; stats: Record<string, number> }
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

export type TraceOutcome = TraceOutcomePipeline | TraceOutcomeFallback;

const LABEL_TEXT: Record<number, string> = {
  1: 'Illicit-labeled transaction (Elliptic)',
  0: 'Licit-labeled transaction (Elliptic)',
  [-1]: 'Unlabeled transaction (Elliptic)',
};

/**
 * Run the reported wallet through the real pipeline via the Node proxy
 * (`POST /api/trace`). Returns `source: 'fallback'` (with an explanatory
 * note and NO trace) when the Python service is unavailable. The caller
 * is responsible for surfacing an honest "pipeline unavailable" UI state —
 * this function never fabricates trace data to fill the gap.
 *
 * Principle: LEDGR's identity is "never fabricate results". The fallback
 * branch must not silently produce plausible-looking mock output.
 */
export async function runPipelineTrace(
  address: string,
  hopDepth: number,
  customComplaint?: Complaint   // passed through to liveTrace.complaint in the pipeline-success path
): Promise<TraceOutcome> {
  const response = await fetch('/api/trace', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      address: address.trim(),
      hop_depth: hopDepth
    })
  });
  const payload = await response.json();

  // No mock/fallback engine exists to fill the gap — returning fabricated data as if
  // it were real pipeline output violates the project's core "no fabrication" rule
  // (AGENTS.md "No placeholders or mocks standing in for real implementation").
  if (payload?.source !== 'pipeline' || !payload?.data) {
    return {
      source: 'fallback',
      note: payload?.note ?? 'Python pipeline service unavailable — no trace data available. Start the backend with: cd backend && uvicorn ledgr.service:app --reload',
    };
  }

  const { trace, rules, score, verdict, attribution } = payload.data as {
    trace: PipelineTrace; rules: PipelineRules;
    score: PipelineScore | null; verdict: PipelineVerdict; attribution: PipelineAttribution | null;
  };

  const stats = trace.stats || {};
  const seedRisk = score?.classified && typeof score.risk_score === 'number' ? score.risk_score : 0;

  // Honest mapping: the Elliptic dataset carries no BTC amounts, so monetary
  // fields are 0 rather than fabricated; per-node signals are only attached to
  // the reported wallet (`evaluated: true`), subgraph members stay structural.
  const nodes: WalletNode[] = trace.nodes.map((n) => ({
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
    seed.ruleFlag = (rules.rule_score >= 60 ? 'high' : rules.rule_score > 0 ? 'low' : 'none') as RuleFlag;
    seed.ruleReasons = rules.rules_fired;
    seed.mlScore = seedRisk;
    seed.mlPrediction = score?.prediction === 'illicit' ? 'illicit' : score?.prediction === 'licit' ? 'licit' : 'unknown';
    seed.verdict = (verdict.verdict as RiskVerdict) ?? 'none';
    seed.evaluated = true;
  }

  const edges: TransactionEdge[] = trace.edges.map((e, i) => ({
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

  const cs = rules.contributing_signals || {};
  const fired = (k: string) => !!cs[k]?.fired;
  const ev = (k: string) => cs[k]?.evidence ?? {};
  const heuristicsSummary = rules.rules_fired.length
    ? rules.rules_fired.map((r) => `${r} fired: ${JSON.stringify(ev(r))}`)
    : ['No rule-based heuristic fired for the reported wallet.'];

  const liveAttribution = {
    name: attribution?.name ?? 'Unattributed (no sourced exchange match)',
    category: (attribution?.category as any) ?? 'Unknown',
    confidenceTier: (attribution?.confidence_tier as ConfidenceTier) ?? 'unattributed',
    sourceCitation: attribution?.source_name ?? 'Unattributed (no supplementary source matched)',
    depositAddress: address.trim(),
    riskLevel: (verdict.verdict === 'confirmed' ? 'CRITICAL' : verdict.verdict === 'watch' ? 'ELEVATED' : 'LOW') as 'CRITICAL' | 'ELEVATED' | 'LOW',
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
    // Trace provenance (`elliptic-indexed` | `live-lookup` | `not-found-on-chain`),
    // set by the pipeline on the trace object — used by the graph to visually
    // distinguish live-looked-up wallets from indexed ones.
    source: trace?.source as TraceSource | undefined,
    // R9 honesty field: the live path spreads `meta` (incl. `capped`) into the
    // /trace response. Undefined on indexed/demo traces — no truncation concept
    // exists there, so no value is invented.
    fetchCapped: trace?.capped === true,
    nodes,
    edges,
    verdict: (verdict.verdict as RiskVerdict) ?? 'none',
    hopDepth: stats.hop_depth_requested ?? hopDepth,
    contributingSignals: {
      ruleScore: rules.rule_score,
      ruleFlag: (rules.rule_score >= 60 ? 'high' : rules.rule_score > 0 ? 'low' : 'none') as RuleFlag,
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
