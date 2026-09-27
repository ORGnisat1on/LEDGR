/**
 * test/pipeline-failure-modes.test.ts
 *
 * Regression tests for the arbitrary/live Bitcoin-address path (hardened
 * 2026-09-26), covering both ends of the wire:
 *
 *   1. `proxyOutcome.ts` — the REAL failure → envelope mapping used by
 *      `server.ts` `POST /api/trace`, for every distinct operational state:
 *      404 dataset-miss, our own AbortError (slow), 429, 503 + retryable,
 *      400/422 rejected request, unclassifiable 5xx, no-response-at-all.
 *   2. `src/services/analyzer.ts` — the REAL envelope → outcome mapping the UI
 *      branches on, including the backend's own `invalid-address-format` answer
 *      and a failed cluster lookup.
 *
 * The bug class under test is "one honest failure mode masquerading as another".
 * On 2026-09-26 a live lookup that both explorers *rate-limited* (HTTP 429)
 * was reported to the user as a 200 with "invalid Bitcoin address" — a
 * fabricated claim about an address that was never actually rejected. The
 * strongest assertion here is therefore negative: for every operational state,
 * the envelope must NOT assert anything about the address.
 *
 * The final block drives the full interleaved sequence valid → rate-limited →
 * malformed → valid THROUGH THE REAL `runPipelineTrace` in one process (the
 * "works once, breaks on reuse" pattern a fresh process per case would miss).
 *
 * Run with: npx tsx --test test/pipeline-failure-modes.test.ts
 * (Node's built-in test runner; no network access is used.)
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { mapProxyFailure, mapMempoolFailure } from '../proxyOutcome';
import { mapPipelineEnvelope, runPipelineTrace } from '../src/services/analyzer';

const ADDRESS = '34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo';
const CTX = { address: ADDRESS, hopDepth: 2, timeoutSeconds: 30 };

/**
 * Phrases that would assert something about the ADDRESS rather than about the
 * request. None may appear in an operational-failure note: in those states the
 * system learned nothing about the address.
 */
const ADDRESS_CLAIMING_PHRASES = [
  'not a valid',
  'not valid',
  'not recognised',
  'not recognized',
  'no on-chain history',
  'no on-chain',
  'invalid address',
  'does not exist',
];

/** Asserts an envelope never claims to know anything about the address. */
function assertNoAddressClaim(envelope: { note?: string }) {
  const note = (envelope.note ?? '').toLowerCase();
  for (const phrase of ADDRESS_CLAIMING_PHRASES) {
    assert.ok(
      !note.includes(phrase),
      `operational-failure note claims something about the address ("${phrase}"): ${envelope.note}`,
    );
  }
}

/** Builds the error object shape thrown by server.ts's `py()` helper. */
function httpError(status: number, detail?: any) {
  return { status, body: detail === undefined ? null : { detail } };
}

// ---------------------------------------------------------------------------
// 1. Proxy: failure → envelope mapping (the real function used by server.ts)
// ---------------------------------------------------------------------------

describe('mapProxyFailure — every operational state stays distinct', () => {
  it('404 (not in the ingested dataset) is an honest answer, not a failure', () => {
    const env = mapProxyFailure(httpError(404), CTX) as any;
    assert.equal(env.source, 'pipeline');
    assert.equal(env.available, true);
    assert.equal(env.data.found, false);
    // The learned signal must report "not classified", never a fabricated zero.
    assert.equal(env.data.score.classified, false);
    assert.equal(env.data.score.risk_score, null);
  });

  it('404 keeps the pipeline explanation (e.g. live tracing disabled) when present', () => {
    const env = mapProxyFailure(httpError(404, 'Live tracing is disabled (LEDGR_LIVE_TRACING=0)'), CTX) as any;
    assert.equal(env.source, 'pipeline');
    assert.ok(env.data.note.includes('Live tracing is disabled'));
  });

  it('our own AbortError is a TIMEOUT (slow), not an outage and not the address', () => {
    const env = mapProxyFailure({ name: 'AbortError' }, CTX) as any;
    assert.equal(env.source, 'retryable');
    assert.equal(env.kind, 'timeout');
    assert.equal(env.available, false);
    assertNoAddressClaim(env);
  });

  it('429 is rate-limited and retryable — never "invalid address"', () => {
    const env = mapProxyFailure(httpError(429), CTX) as any;
    assert.equal(env.source, 'retryable');
    assert.equal(env.kind, 'rate-limited');
    assert.equal(env.available, false);
    assertNoAddressClaim(env);
  });

  it("503 with a structured retryable detail keeps the pipeline's own kind", () => {
    const env = mapProxyFailure(
      httpError(503, { kind: 'rate-limited', retryable: true, message: 'both live sources failed (rate-limited)' }),
      CTX,
    ) as any;
    assert.equal(env.source, 'retryable');
    assert.equal(env.kind, 'rate-limited');
    // The pipeline's message is preferred: it names the actual cause.
    assert.ok(env.note.includes('both live sources failed'));
    assertNoAddressClaim(env);
  });

  it('503 timeout from the pipeline is reported as a timeout', () => {
    const env = mapProxyFailure(
      httpError(503, { kind: 'timeout', retryable: true, message: 'live sources timed out' }),
      CTX,
    ) as any;
    assert.equal(env.kind, 'timeout');
    assertNoAddressClaim(env);
  });

  it('400/422 is an invalid REQUEST, not a service outage', () => {
    for (const status of [400, 422]) {
      const env = mapProxyFailure(httpError(status), CTX) as any;
      assert.equal(env.source, 'invalid-input', `status ${status}`);
      assert.equal(env.available, false);
      assert.ok(env.note.toLowerCase().includes('not a service failure'));
    }
  });

  it('400 with a pipeline detail keeps the detail message and kind', () => {
    const env = mapProxyFailure(
      httpError(400, { kind: 'invalid-request', retryable: false, message: 'hop_depth out of range' }),
      CTX,
    ) as any;
    assert.equal(env.source, 'invalid-input');
    assert.equal(env.kind, 'invalid-request');
    assert.equal(env.note, 'hop_depth out of range');
  });

  it('an unclassifiable 5xx is an internal error, NOT "unreachable"', () => {
    const env = mapProxyFailure(httpError(500), CTX) as any;
    assert.equal(env.source, 'fallback');
    assert.equal(env.kind, 'service-error');
    assert.ok(!env.note.toLowerCase().includes('unreachable'));
    assertNoAddressClaim(env);
  });

  it('no HTTP response at all is genuinely unreachable', () => {
    // Node's fetch throws a TypeError with no status when the connection fails.
    const env = mapProxyFailure({ name: 'TypeError', message: 'fetch failed' }, CTX) as any;
    assert.equal(env.source, 'fallback');
    assert.equal(env.kind, 'unreachable');
    assert.ok(env.note.toLowerCase().includes('unreachable'));
  });

  it('a null error still maps to a state rather than throwing', () => {
    const env = mapProxyFailure(undefined, CTX) as any;
    assert.equal(env.source, 'fallback');
    assert.equal(env.kind, 'unreachable');
  });

  it('no operational state carries a trace (nothing is ever fabricated)', () => {
    const failures = [
      httpError(429),
      httpError(503, { kind: 'api-error', retryable: true, message: 'explorer outage' }),
      { name: 'AbortError' },
      httpError(400),
      httpError(500),
      { name: 'TypeError' },
    ];
    for (const failure of failures) {
      const env = mapProxyFailure(failure, CTX) as any;
      assert.equal(env.trace, undefined, 'operational failure must not carry a trace');
      assert.equal(env.data?.trace, undefined);
      assert.equal(env.available, false);
    }
  });

  it('the transient states are distinguishable by kind, not just by text', () => {
    assert.equal((mapProxyFailure({ name: 'AbortError' }, CTX) as any).kind, 'timeout');
    assert.equal((mapProxyFailure(httpError(429), CTX) as any).kind, 'rate-limited');
    assert.equal((mapProxyFailure(httpError(500), CTX) as any).kind, 'service-error');
  });
});

// ---------------------------------------------------------------------------
// 2. Analyzer: envelope → UI outcome mapping (the real function used by App.tsx)
// ---------------------------------------------------------------------------

/** A minimal but complete pipeline envelope, reused by the mapping tests. */
function pipelineEnvelope(overrides: any = {}) {
  return {
    source: 'pipeline',
    available: true,
    data: {
      address: ADDRESS,
      hopDepth: 2,
      trace: {
        nodes: [{ id: ADDRESS, hop: 0, label: -1, time_step: 43 }],
        edges: [],
        stats: { node_count: 1, edge_count: 0, hop_depth_requested: 2, max_hop_reached: 0, illicit_nodes: 0, licit_nodes: 0, unknown_nodes: 1 },
      },
      rules: { rule_score: 0, rules_fired: [] },
      verdict: { verdict: 'none', confirmed: false, watch: false },
      attribution: null,
      attribution_status: 'no-match',
      ...overrides,
    },
  };
}

describe('mapPipelineEnvelope — service-level envelopes map to honest outcomes', () => {
  it('retryable/rate-limited maps to the retryable outcome with no trace', () => {
    const outcome = mapPipelineEnvelope(
      mapProxyFailure(httpError(503, { kind: 'rate-limited', retryable: true, message: 'both live sources failed (rate-limited: 429)' }), CTX),
      ADDRESS,
      2,
    ) as any;
    assert.equal(outcome.source, 'retryable');
    assert.equal(outcome.kind, 'rate-limited');
    assert.equal(outcome.trace, undefined, 'a retryable outcome must never carry a trace');
    assertNoAddressClaim(outcome);
  });

  it('retryable/timeout maps to retryable, NOT to "unavailable"', () => {
    const outcome = mapPipelineEnvelope(mapProxyFailure({ name: 'AbortError' }, CTX), ADDRESS, 2) as any;
    assert.equal(outcome.source, 'retryable');
    assert.equal(outcome.kind, 'timeout');
    assert.notEqual(outcome.source, 'fallback');
  });

  it('invalid-input maps to invalid_input, NOT to "pipeline unavailable"', () => {
    const outcome = mapPipelineEnvelope(mapProxyFailure(httpError(400), CTX), ADDRESS, 2) as any;
    assert.equal(outcome.source, 'invalid_input');
    assert.notEqual(outcome.source, 'fallback');
    assert.equal(outcome.trace, undefined);
  });

  it('unreachable maps to fallback', () => {
    const outcome = mapPipelineEnvelope(mapProxyFailure({ name: 'TypeError' }, CTX), ADDRESS, 2) as any;
    assert.equal(outcome.source, 'fallback');
    assert.equal(outcome.trace, undefined);
  });

  it("the backend's invalid-address-format answer maps to 'empty' with a clear note", () => {
    // What the real backend returns for a malformed paste: HTTP 200, its own
    // source, no graph. A statement about the INPUT, not about the chain.
    const outcome = mapPipelineEnvelope(
      pipelineEnvelope({
        address: 'nonsense',
        trace: {
          source: 'invalid-address-format',
          network_attempted: false,
          format_reason: 'not a mainnet address (no valid base58/bech32 form)',
          note: 'Not a valid mainnet Bitcoin address — nothing was looked up and no signal is computed.',
        },
      }),
      'nonsense',
      2,
    ) as any;
    assert.equal(outcome.source, 'empty');
    assert.equal(outcome.trace, undefined);
    assert.ok(outcome.note.toLowerCase().includes('not a valid mainnet bitcoin address'));
  });

  it("the backend's rate-limited answer (older shape) can never read as 'empty'", () => {
    // Defensive: if an older/other backend ever returned an operational failure
    // source inside a 200 pipeline envelope, it must surface as retryable rather
    // than as the "nothing exists for this address" conclusion.
    const outcome = mapPipelineEnvelope(
      pipelineEnvelope({ trace: { source: 'rate-limited', note: 'both sources throttled' } }),
      ADDRESS,
      2,
    ) as any;
    assert.notEqual(outcome.source, 'empty');
    assert.equal(outcome.source, 'retryable');
  });

  it('a failed cluster lookup is NOT reported as "no sourced exchange match"', () => {
    // The pipeline answered, but /clusters did not. "No match" would be a
    // conclusion we did not reach.
    const outcome = mapPipelineEnvelope(pipelineEnvelope({ attribution_status: 'lookup-failed' }), ADDRESS, 2) as any;
    assert.equal(outcome.source, 'pipeline');
    const attributionText = JSON.stringify(outcome.trace.attribution ?? {}).toLowerCase();
    assert.ok(
      !attributionText.includes('no sourced exchange match'),
      'a failed lookup must not claim "no sourced exchange match"',
    );
    assert.ok(attributionText.includes('lookup'), 'the citation must say the lookup was unavailable');
  });

  it('a completed cluster lookup with no match still says "no sourced exchange match"', () => {
    const outcome = mapPipelineEnvelope(pipelineEnvelope(), ADDRESS, 2) as any;
    assert.equal(outcome.source, 'pipeline');
    const text = JSON.stringify(outcome.trace.attribution ?? {}).toLowerCase();
    assert.ok(text.includes('no sourced exchange match'));
  });
});


// ---------------------------------------------------------------------------
// 3. The full interleaved sequence through the REAL runPipelineTrace, one process
// ---------------------------------------------------------------------------

/** Replays a queue of proxy envelopes in order through a stubbed global fetch. */
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

const FULL_RESULT = pipelineEnvelope({
  trace: {
    nodes: [
      { id: ADDRESS, hop: 0, label: 1, time_step: 43 },
      { id: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', hop: 1, label: 0, time_step: 43 },
    ],
    edges: [{ src: ADDRESS, dst: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa' }],
    stats: { node_count: 2, edge_count: 1, hop_depth_requested: 2, max_hop_reached: 1, illicit_nodes: 1, licit_nodes: 1, unknown_nodes: 0 },
  },
  rules: { rule_score: 3, rules_fired: ['R1', 'R2'] },
  score: { wallet: ADDRESS, classified: true, risk_score: 0.8, prediction: 1, learned_flag: true },
  verdict: { verdict: 'confirmed', confirmed: true, watch: false, confidence: 0.9 },
});

describe('runPipelineTrace — valid → rate-limited → malformed → valid in one session', () => {
  it('each step reaches its own correct state, with no state leaking across', async () => {
    const rateLimited = mapProxyFailure(
      httpError(503, {
        kind: 'rate-limited',
        retryable: true,
        message: 'live fetch failed: both live sources failed (blockstream: rate-limited — 429; blockcypher: rate-limited — 429)',
      }),
      CTX,
    );
    const malformed = pipelineEnvelope({
      address: 'nonsense',
      trace: {
        source: 'invalid-address-format',
        network_attempted: false,
        format_reason: 'not a mainnet address (no valid base58/bech32 form)',
        note: 'Not a valid mainnet Bitcoin address — nothing was looked up and no signal is computed (no block-explorer request was made).',
      },
    });

    const { calls, restore } = stubFetchWithQueue([FULL_RESULT, rateLimited, malformed, FULL_RESULT]);
    try {
      const first = await runPipelineTrace(ADDRESS, 2) as any;
      assert.equal(first.source, 'pipeline');
      assert.ok(first.trace.nodes.length > 0);

      // The rate-limited step must NOT be shown as "invalid address" or as a
      // "nothing exists for this address" conclusion — the 2026-09-26 bug.
      const second = await runPipelineTrace(ADDRESS, 2) as any;
      assert.equal(second.source, 'retryable');
      assert.equal(second.kind, 'rate-limited');
      assert.equal(second.trace, undefined, 'no trace may be attached to a retryable outcome');
      assertNoAddressClaim(second);

      // The malformed step is a different state again: about the INPUT, not the
      // chain, and not a service failure.
      const third = await runPipelineTrace('nonsense', 2) as any;
      assert.equal(third.source, 'empty');
      assert.equal(third.trace, undefined);
      assert.ok(third.note.toLowerCase().includes('not a valid mainnet bitcoin address'));

      // And the session recovers: a later valid address still traces normally.
      const fourth = await runPipelineTrace(ADDRESS, 2) as any;
      assert.equal(fourth.source, 'pipeline');
      assert.ok(fourth.trace.nodes.length > 0);

      assert.deepEqual(calls, [ADDRESS, ADDRESS, 'nonsense', ADDRESS]);
    } finally {
      restore();
    }
  });

  it('a service outage between two good traces does not poison the session', async () => {
    const down = mapProxyFailure({ name: 'TypeError', message: 'fetch failed' }, CTX);
    const { restore } = stubFetchWithQueue([FULL_RESULT, down, FULL_RESULT]);
    try {
      assert.equal((await runPipelineTrace(ADDRESS, 2) as any).source, 'pipeline');
      const middle = await runPipelineTrace(ADDRESS, 2) as any;
      assert.equal(middle.source, 'fallback');
      assertNoAddressClaim(middle);
      assert.equal((await runPipelineTrace(ADDRESS, 2) as any).source, 'pipeline');
    } finally {
      restore();
    }
  });

  it('a non-JSON proxy response is reported as a proxy failure, not a crash', async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () => ({
      ok: false,
      status: 413,
      json: async () => { throw new Error('Unexpected token < in JSON'); },
    })) as unknown as typeof fetch;
    try {
      const outcome = await runPipelineTrace(ADDRESS, 2) as any;
      assert.equal(outcome.source, 'fallback');
      assert.equal(outcome.trace, undefined);
      assert.ok(outcome.note.includes('413'));
      assertNoAddressClaim(outcome);
    } finally {
      globalThis.fetch = original;
    }
  });
});

// ---------------------------------------------------------------------------
// 4. The live mempool monitor: a failed poll is NOT "no unconfirmed activity"
// ---------------------------------------------------------------------------

describe('mapMempoolFailure — a failed poll is never reported as a clean result', () => {
  const reasons = ['rate-limited', 'timeout', 'api-error', 'unreachable'] as const;

  for (const reason of reasons) {
    it(`${reason} returns success:false with a machine-readable reason`, () => {
      const env = mapMempoolFailure(reason, { status: 429, timeoutSeconds: 8 });
      assert.equal(env.success, false);
      assert.equal(env.reason, reason);
      assert.equal(env.retryable, true);
      assert.deepEqual(env.txs, []);
      // The note must state that the state is UNKNOWN and explicitly deny
      // meaning "no activity" — this is what stops the client from clearing a
      // previously raised UNCONFIRMED TX alert on a rate limit.
      assert.ok(env.note.includes('UNKNOWN'), env.note);
      assert.ok(env.note.toLowerCase().includes('not "no activity"'), env.note);
    });
  }

  it('a rate-limited poll and an unreachable poll are distinguishable by reason', () => {
    assert.equal(mapMempoolFailure('rate-limited').reason, 'rate-limited');
    assert.equal(mapMempoolFailure('unreachable').reason, 'unreachable');
    assert.notEqual(mapMempoolFailure('rate-limited').note, mapMempoolFailure('unreachable').note);
  });

  it('no failure envelope can be mistaken for "no transactions" — the fields differ', () => {
    // The only "no unconfirmed transactions" answer is success:true + txs:[].
    const clean = { success: true, txs: [], live: true };
    for (const reason of reasons) {
      const failed = mapMempoolFailure(reason) as any;
      assert.notEqual(failed.success, clean.success, reason);
      assert.equal(typeof failed.reason, 'string', reason);
    }
  });
});
