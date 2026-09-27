/**
 * test/pipeline-sequenced-traces.test.ts
 *
 * Regression test for the reported bug class: "the pipeline connection breaks
 * after the first successful trace". Reproduced on 2026-09-26:
 *
 *   1. Trace an Elliptic-indexed address (e.g. `230425980`) -> succeeds.
 *   2. Trace a second address in the same session -> the UI shows
 *      "Pipeline unavailable — no trace data shown / Unexpected error
 *      contacting the pipeline", even though the pipeline answered HTTP 200.
 *
 * Actual root cause (evidence in the STATUS.md 2026-09-26 entry): the Node
 * proxy (`server.ts` `POST /api/trace`) composes one envelope from five
 * *independent* Python calls, so an envelope tagged `source: 'pipeline'` can
 * legitimately carry a "no-data" block (`{source:'not-found-on-chain', note,
 * address}`) with no `nodes`/`edges`/`rule_score`/`rules_fired`/`verdict`. The
 * frontend mapper dereferenced those fields unconditionally and threw a
 * TypeError, which the caller reported as a connection failure.
 *
 * This suite therefore does NOT re-implement the mapper (unlike
 * `pipeline-fallback.test.ts`): it imports the real functions from
 * `src/services/analyzer.ts` and drives them with the exact payload shapes
 * captured from the live proxy, in a SINGLE process, in sequence — precisely
 * the "works once, breaks on reuse" pattern that a fresh-process-per-case test
 * cannot catch.
 *
 * Payload fixtures below are verbatim-shaped captures of real responses from
 * `POST http://localhost:3000/api/trace` (2026-09-26):
 *   - `230425980`, `298938351`            -> full graph + rules + verdict
 *   - `invalid_xyz_123`                   -> trace/rules/verdict = not-found-on-chain
 *   - `34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` @ hop 2
 *                                         -> MIXED: trace = live-lookup (has nodes),
 *                                            rules/verdict = not-found-on-chain (no rule_score)
 *   - out-of-dataset 404 branch           -> { found: false, note, score }
 *
 * Run with: npx tsx --test test/pipeline-sequenced-traces.test.ts
 * (Node's built-in test runner; no network access is used.)
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { mapPipelineEnvelope, runPipelineTrace } from '../src/services/analyzer';

// ---------------------------------------------------------------------------
// Payload fixtures (shapes captured from the live proxy)
// ---------------------------------------------------------------------------

/** A complete result: subgraph + rule signal + correlation verdict. */
function fullPipelineData(address: string) {
  return {
    address,
    hopDepth: 2,
    trace: {
      nodes: [
        { id: address, hop: 0, label: -1, time_step: 43 },
        { id: `${address}-neighbour`, hop: 1, label: 1, time_step: 43 },
      ],
      edges: [{ src: address, dst: `${address}-neighbour` }],
      stats: { node_count: 2, edge_count: 1, hop_depth_requested: 2, max_hop_reached: 1, illicit_nodes: 1, licit_nodes: 0, unknown_nodes: 1 },
      source: 'elliptic-indexed',
    },
    rules: {
      rule_score: 40,
      rule_flag: 'low',
      rules_fired: ['peel_chain'],
      contributing_signals: { peel_chain: { fired: true, evidence: { hops: 3 } } },
      source: 'elliptic-indexed',
    },
    score: { wallet: address, classified: true, risk_score: 0.72, prediction: 'illicit', learned_flag: true },
    verdict: { wallet: address, verdict: 'watch', contributing_signals: {}, source: 'elliptic-indexed' },
    attribution: null,
  };
}

/** Real "nothing to trace" answer from the backend (invalid / no on-chain history). */
function notFoundData(address: string) {
  const block = {
    source: 'not-found-on-chain',
    note: 'Address is not valid / not recognized by the Bitcoin chain explorers — nothing to trace and no signal to compute.',
    address,
  };
  return {
    address,
    hopDepth: 2,
    trace: { ...block },
    rules: { ...block },
    score: { wallet: address, classified: false, risk_score: null, prediction: null, learned_flag: false, note: 'address not in Elliptic feature set; model cannot score it and no risk is fabricated.' },
    verdict: { ...block },
    attribution: null,
  };
}

/** The mixed envelope observed on a live wallet: graph present, signal calls came back empty. */
function mixedGraphWithoutRulesData(address: string) {
  return {
    address,
    hopDepth: 2,
    trace: {
      nodes: [{ id: address, hop: 0, label: -1, time_step: -1 }],
      edges: [],
      stats: { seed: address, node_count: 1, edge_count: 0, hop_depth_requested: 2, max_hop_reached: 0, illicit_nodes: 0, licit_nodes: 0, unknown_nodes: 1 },
      source: 'live-lookup',
      capped: true,
    },
    rules: {
      source: 'not-found-on-chain',
      note: 'Address is not valid / not recognized by the Bitcoin chain explorers — nothing to trace and no signal to compute.',
      address,
    },
    score: { wallet: address, classified: false, risk_score: null, prediction: null, learned_flag: false },
    verdict: {
      source: 'not-found-on-chain',
      note: 'Address is not valid / not recognized by the Bitcoin chain explorers — nothing to trace and no signal to compute.',
      address,
    },
    attribution: null,
  };
}

/** The proxy's 404 branch for a wallet absent from the ingested dataset. */
function datasetMissData(address: string) {
  return {
    address,
    hopDepth: 2,
    found: false,
    note: 'Wallet not present in the ingested Elliptic dataset — no trace, rule signal, or verdict exists for it, and the learned signal reports it as classified:false (no risk is fabricated).',
    score: { wallet: address, classified: false, risk_score: null, prediction: null, learned_flag: false },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Installs a fake global `fetch` that replays a queue of payloads in order and
 * records the addresses it was asked for — so one process can exercise the real
 * `runPipelineTrace` repeatedly (the reuse pattern under test).
 */
function stubFetchWithQueue(payloads: any[]) {
  const calls: string[] = [];
  const original = globalThis.fetch;
  let index = 0;
  globalThis.fetch = (async (_input: any, init?: any) => {
    const body = init?.body ? JSON.parse(init.body) : {};
    calls.push(body.address);
    const payload = payloads[Math.min(index, payloads.length - 1)];
    index += 1;
    return { ok: true, status: 200, json: async () => payload } as any;
  }) as typeof fetch;
  return { calls, restore: () => { globalThis.fetch = original; } };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('runPipelineTrace — sequenced traces in one process (reuse regression)', () => {

  it('traces two different indexed addresses back-to-back in the same process', async () => {
    const stub = stubFetchWithQueue([
      { source: 'pipeline', available: true, data: fullPipelineData('230425980') },
      { source: 'pipeline', available: true, data: fullPipelineData('298938351') },
    ]);
    try {
      const first = await runPipelineTrace('230425980', 2);
      const second = await runPipelineTrace('298938351', 2);

      assert.equal(first.source, 'pipeline', 'first trace must succeed');
      assert.equal(second.source, 'pipeline', 'second trace must succeed (no reuse breakage)');
      assert.deepEqual(stub.calls, ['230425980', '298938351']);
      if (first.source === 'pipeline' && second.source === 'pipeline') {
        assert.equal(first.trace.targetAddress, '230425980');
        assert.equal(second.trace.targetAddress, '298938351');
        assert.equal(second.trace.nodes.length, 2);
      }
    } finally {
      stub.restore();
    }
  });

  it('an indexed trace followed by a non-indexed address returns source:empty instead of throwing (the reported bug)', async () => {
    const stub = stubFetchWithQueue([
      { source: 'pipeline', available: true, data: fullPipelineData('230425980') },
      { source: 'pipeline', available: true, data: notFoundData('invalid_xyz_123') },
    ]);
    try {
      const first = await runPipelineTrace('230425980', 2);
      const second = await runPipelineTrace('invalid_xyz_123', 2);

      assert.equal(first.source, 'pipeline');
      assert.equal(second.source, 'empty', 'honest "nothing to trace" answer must NOT surface as an error');
      assert.ok(!('trace' in second), 'empty outcome MUST NOT carry a trace field');
      assert.match(second.note, /not valid|no on-chain|nothing to trace/i);
    } finally {
      stub.restore();
    }
  });

  it('keeps working after an empty answer — a third call in the same process still returns pipeline', async () => {
    const stub = stubFetchWithQueue([
      { source: 'pipeline', available: true, data: fullPipelineData('230425980') },
      { source: 'pipeline', available: true, data: notFoundData('invalid_xyz_123') },
      { source: 'pipeline', available: true, data: fullPipelineData('100197784') },
    ]);
    try {
      const a = await runPipelineTrace('230425980', 2);
      const b = await runPipelineTrace('invalid_xyz_123', 2);
      const c = await runPipelineTrace('100197784', 2);

      assert.deepEqual([a.source, b.source, c.source], ['pipeline', 'empty', 'pipeline']);
      if (c.source === 'pipeline') {
        assert.equal(c.trace.targetAddress, '100197784');
      }
    } finally {
      stub.restore();
    }
  });

  it('a subgraph without a complete signal set returns source:incomplete (no fabricated rule/ML values)', async () => {
    // Exact mixed shape captured on the live Binance cold wallet at hop depth 2.
    const stub = stubFetchWithQueue([
      { source: 'pipeline', available: true, data: mixedGraphWithoutRulesData('34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo') },
    ]);
    try {
      const outcome = await runPipelineTrace('34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo', 2);

      assert.equal(outcome.source, 'incomplete');
      assert.ok(!('trace' in outcome), 'incomplete outcome MUST NOT carry a trace field');
      assert.match(outcome.note, /rule-based signal/);
      assert.match(outcome.note, /fabricated signal values/);
    } finally {
      stub.restore();
    }
  });

  it('the proxy 404 branch (found:false) returns source:empty with the backend note, never a throw', async () => {
    const stub = stubFetchWithQueue([
      { source: 'pipeline', available: true, data: datasetMissData('9999999999999') },
      { source: 'pipeline', available: true, data: datasetMissData('9999999999998') },
    ]);
    try {
      const first = await runPipelineTrace('9999999999999', 2);
      const second = await runPipelineTrace('9999999999998', 2);

      assert.equal(first.source, 'empty');
      assert.equal(second.source, 'empty');
      assert.match(second.note, /not present in the ingested Elliptic dataset/);
    } finally {
      stub.restore();
    }
  });

  it('an unmappable response is reported honestly as a fallback naming the failure — not as an unexpected error', async () => {
    const stub = stubFetchWithQueue([
      {
        source: 'pipeline',
        available: true,
        data: {
          address: '230425980',
          hopDepth: 2,
          trace: { nodes: [null], edges: [], stats: {} },
          rules: { rule_score: 0, rule_flag: 'none', rules_fired: [], contributing_signals: {} },
          score: null,
          verdict: { verdict: 'none', contributing_signals: {} },
          attribution: null,
        },
      },
    ]);
    try {
      const outcome = await runPipelineTrace('230425980', 2);

      assert.equal(outcome.source, 'fallback');
      assert.ok(!('trace' in outcome));
      assert.match(outcome.note, /could not map/);
    } finally {
      stub.restore();
    }
  });

});

describe('mapPipelineEnvelope — shape contract', () => {

  it('returns fallback (no trace) when the service envelope carries no pipeline data', () => {
    const outcome = mapPipelineEnvelope(
      { source: 'fallback', available: false, note: 'Python pipeline timed out.' },
      '230425980', 2,
    );
    assert.equal(outcome.source, 'fallback');
    assert.ok(!('trace' in outcome));
  });

  it('passes the backend note through verbatim for an empty outcome', () => {
    const outcome = mapPipelineEnvelope(
      { source: 'pipeline', available: true, data: datasetMissData('9999999999999') },
      '9999999999999', 2,
    );
    assert.equal(outcome.source, 'empty');
    assert.match(outcome.note, /not present in the ingested Elliptic dataset/);
  });

  it('falls back to a descriptive note that names the traced address when the backend sends none', () => {
    const outcome = mapPipelineEnvelope(
      {
        source: 'pipeline',
        available: true,
        data: {
          address: ' 9999999999999 ',
          hopDepth: 2,
          trace: { source: 'not-found-on-chain', address: '9999999999999' },
          rules: { source: 'not-found-on-chain', address: '9999999999999' },
          score: null,
          verdict: { source: 'not-found-on-chain', address: '9999999999999' },
          attribution: null,
        },
      },
      ' 9999999999999 ', 2,
    );
    assert.equal(outcome.source, 'empty');
    assert.match(outcome.note, /9999999999999/);
    assert.match(outcome.note, /nothing fabricated/);
  });

});

