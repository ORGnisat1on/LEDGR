/**
 * test/mempool-poll.test.ts
 *
 * Module 1b — Watchlist Monitoring: the 429-does-not-clear-an-alert invariant.
 *
 * THE BUG THIS PROTECTS AGAINST: mempool.space is polled every 30 s per address
 * and is a free public API, so it rate-limits regularly. Before the 2026-09-26
 * hardening, a non-OK response was folded into the same branch as an empty
 * mempool, so a throttled poll (a) displayed as "no unconfirmed transactions"
 * and (b) CLEARED an already-raised UNCONFIRMED TX alert. In an
 * fraud-investigation tool that is the worst kind of bug: a service failure
 * silently deleted a real signal about pending criminal funds and replaced it
 * with a clean-looking result.
 *
 * The state transition that decides this lives in `src/hooks/useMempoolPolling.ts`
 * as the pure, exported `applyMempoolPoll`, which the hook itself calls — so
 * these tests exercise the shipped logic, not a re-implementation. (A DOM-level
 * test is not possible here: the repo has no jsdom / react-test-renderer and
 * adding a test framework is out of scope.)
 *
 * Run with: npx tsx --test test/mempool-poll.test.ts
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { applyMempoolPoll } from '../src/hooks/useMempoolPolling';
import { mapMempoolFailure } from '../proxyOutcome';

const T0 = 1_700_000_000_000;
const T1 = T0 + 30_000;
const T2 = T1 + 30_000;

/** A live, already-raised UNCONFIRMED TX alert (as a previous poll produced). */
function activeAlert() {
  return {
    txHash: 'aa'.repeat(32),
    direction: 'outgoing' as const,
    amountBtc: 0.25,
    amountInr: 223700,
    detectedAt: '2026-09-27T06:00:00.000Z',
    status: 'unconfirmed_mempool' as const,
    feeRateSatVb: 12,
    counterpartyAddress: 'bc1qexamplecounterpartyaddress000000000000000',
  };
}

/** State after a first, SUCCESSFUL poll that raised the alert. */
function stateWithLiveAlert() {
  return { alert: activeAlert(), error: null, unavailableReason: null, lastPolledAt: T0 };
}

const RATE_LIMITED = mapMempoolFailure('rate-limited', { status: 429 });

describe('applyMempoolPoll — a rate-limited poll must NOT clear a live alert', () => {
  it('429: the alert survives and the "last successful check" timestamp does not advance', () => {
    const prev = stateWithLiveAlert();
    const next = applyMempoolPoll(prev as any, RATE_LIMITED, T1);

    // THE assertion that matters: the signal is still there.
    assert.deepEqual(next.alert, prev.alert, 'a 429 must never clear a live alert');
    // And the data is not presented as fresh.
    assert.equal(next.lastPolledAt, T0, 'a 429 must not advance the freshness timestamp');
    assert.equal(next.ok, false);
  });

  it('429: the UI is told the state is unknown, with a machine-readable reason', () => {
    const next = applyMempoolPoll(stateWithLiveAlert() as any, RATE_LIMITED, T1);
    assert.equal(next.unavailableReason, 'rate-limited');
    assert.ok(next.error, 'a failed poll must surface an error message');
    assert.ok(next.error!.toLowerCase().includes('unknown'), 'the message must say the state is unknown');
    assert.ok(
      next.error!.toLowerCase().includes('not a "no unconfirmed transactions" result'),
      'the message must explicitly deny meaning "no activity"',
    );
    assert.ok(next.error!.toLowerCase().includes('alert is kept'));
  });

  it('a genuine 429 envelope from the proxy — not just the mapped one — is treated the same', () => {
    // Exactly what server.ts returns for HTTP 429 from mempool.space.
    const raw = {
      success: false, txs: [], live: false, reason: 'rate-limited', retryable: true,
      note: 'Live mempool service rate-limited this request (HTTP 429) …',
    };
    const next = applyMempoolPoll(stateWithLiveAlert() as any, raw, T1);
    assert.deepEqual(next.alert, activeAlert());
    assert.equal(next.lastPolledAt, T0);
    assert.equal(next.unavailableReason, 'rate-limited');
  });

  it('every failure reason preserves the alert and the timestamp', () => {
    for (const reason of ['rate-limited', 'timeout', 'api-error', 'unreachable'] as const) {
      const next = applyMempoolPoll(stateWithLiveAlert() as any, mapMempoolFailure(reason), T1);
      assert.deepEqual(next.alert, activeAlert(), `${reason} cleared the alert`);
      assert.equal(next.lastPolledAt, T0, `${reason} advanced the timestamp`);
      assert.equal(next.unavailableReason, reason);
      assert.equal(next.ok, false);
    }
  });

  it('an unreadable body also preserves the alert (it is not an empty mempool)', () => {
    for (const payload of [null, undefined, 'not json', 42]) {
      const next = applyMempoolPoll(stateWithLiveAlert() as any, payload, T1);
      assert.deepEqual(next.alert, activeAlert(), `payload ${String(payload)} cleared the alert`);
      assert.equal(next.lastPolledAt, T0);
      assert.equal(next.ok, false);
    }
  });

  it('a failure envelope with no reason fails safe (api-error, not "clean")', () => {
    const next = applyMempoolPoll(stateWithLiveAlert() as any, { success: false, txs: [] }, T1);
    assert.deepEqual(next.alert, activeAlert());
    assert.equal(next.unavailableReason, 'api-error');
    assert.equal(next.lastPolledAt, T0);
  });
});

describe('applyMempoolPoll — only a successful poll may clear an alert', () => {
  it('a successful poll with zero transactions DOES clear the alert and advances time', () => {
    const next = applyMempoolPoll(
      stateWithLiveAlert() as any,
      { success: true, txs: [], live: true },
      T1,
    );
    assert.equal(next.alert, null, 'a real empty mempool is the one case that clears');
    assert.equal(next.lastPolledAt, T1);
    assert.equal(next.error, null);
    assert.equal(next.unavailableReason, null);
    assert.equal(next.ok, true);
  });

  it('a successful poll WITH transactions keeps the alert for the caller to re-evaluate', () => {
    const txs = [{ txid: 'bb'.repeat(32), vin: [], vout: [], weight: 400, fee: 1000 }];
    const next = applyMempoolPoll(stateWithLiveAlert() as any, { success: true, txs, live: true }, T1);
    assert.deepEqual(next.alert, activeAlert());
    assert.deepEqual(next.txs, txs, 'the hook must receive the txs to scan');
    assert.equal(next.lastPolledAt, T1);
  });

  it('full sequence: alert raised -> 429 (kept, time frozen) -> success+empty (cleared)', () => {
    // The real-world sequence an investigator would see.
    const step1 = applyMempoolPoll(
      { alert: null, error: null, unavailableReason: null, lastPolledAt: null } as any,
      { success: true, txs: [{ txid: 'cc' }], live: true },
      T0,
    );
    assert.equal(step1.ok, true);
    const withAlert = { ...step1, alert: activeAlert(), lastPolledAt: T0 };

    const step2 = applyMempoolPoll(withAlert as any, RATE_LIMITED, T1);
    assert.deepEqual(step2.alert, activeAlert());
    assert.equal(step2.lastPolledAt, T0);

    const step3 = applyMempoolPoll(step2 as any, { success: true, txs: [], live: true }, T2);
    assert.equal(step3.alert, null);
    assert.equal(step3.lastPolledAt, T2);
    assert.equal(step3.error, null);
  });
});
