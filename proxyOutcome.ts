/**
 * Pure mapping from a Python-pipeline failure to the JSON envelope the client
 * consumes (`src/services/analyzer.ts` → `src/App.tsx`).
 *
 * It is a separate, side-effect-free module (not inline in server.ts) for one
 * reason: `server.ts` calls `app.listen()` on import, so a mapping that only
 * existed there could not be regression-tested. Every branch below is covered by
 * test/proxy-outcome.test.ts, because each one is a DIFFERENT honest state and
 * collapsing two of them is the exact defect this mapping exists to prevent:
 *
 *   404                        → the wallet is not in the ingested Elliptic
 *                                dataset (or live tracing is off): an honest
 *                                answer, not a service failure
 *   AbortError (our own timer)  → the request was SLOW (retryable), which is not
 *                                the same claim as "the service is down"
 *   429 / 503 + retryable:true  → the block explorers are rate-limiting /
 *                                timing out / erroring. The pipeline IS
 *                                reachable and NOTHING was concluded about the
 *                                address — must never read as "invalid address"
 *   400 / 422                  → the pipeline REJECTED the request: a client
 *                                problem, not an outage
 *   other status (e.g. 500)    → the pipeline answered with an unclassifiable
 *                                internal error — not "unreachable"
 *   no status at all           → genuinely unreachable (connection refused, DNS)
 *
 * Invariant enforced by the tests: no operational-failure note may contain a
 * phrase asserting something about the address ("not valid", "no on-chain
 * history", ...). We know nothing about the address in those states.
 */

export const DEFAULT_PIPELINE_TIMEOUT_SECONDS = 30;

export interface ProxyFailureContext {
  address: string;
  hopDepth: number;
  timeoutSeconds?: number;
}

export interface RetryableEnvelope {
  source: 'retryable';
  available: false;
  kind: string;
  note: string;
}

export interface InvalidInputEnvelope {
  source: 'invalid-input';
  available: false;
  kind: string;
  note: string;
}

export interface DatasetMissEnvelope {
  source: 'pipeline';
  available: true;
  data: {
    address: string;
    hopDepth: number;
    found: false;
    note: string;
    score: Record<string, unknown>;
  };
}

export interface UnavailableEnvelope {
  source: 'fallback';
  available: false;
  kind: string;
  note: string;
}

export type ProxyFailureEnvelope =
  | RetryableEnvelope
  | InvalidInputEnvelope
  | DatasetMissEnvelope
  | UnavailableEnvelope;

/** Error shape thrown by the proxy's `py()` helper (see server.ts). */
export interface PipelineHttpError {
  status?: number;
  body?: any;
  name?: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// Live mempool monitor (`GET /api/mempool/address/:address`)
// ---------------------------------------------------------------------------

/**
 * Why the mempool answer is UNKNOWN for a poll. Each is a transient REQUEST
 * failure — none of them is evidence about the address's activity level.
 */
export type MempoolUnavailableReason = 'rate-limited' | 'timeout' | 'api-error' | 'unreachable';

export interface MempoolUnavailableEnvelope {
  success: false;
  txs: [];
  live: false;
  reason: MempoolUnavailableReason;
  /** Always true today; present so the client never has to guess about retry. */
  retryable: true;
  note: string;
}

export function mapMempoolFailure(
  reason: MempoolUnavailableReason,
  opts: { status?: number; timeoutSeconds?: number } = {},
): MempoolUnavailableEnvelope {
  const unknownSuffix = 'unconfirmed activity is UNKNOWN for this poll (not "no activity").';
  const notes: Record<MempoolUnavailableReason, string> = {
    'rate-limited': `Live mempool service rate-limited this request (HTTP ${opts.status ?? 429}) — ${unknownSuffix} It will be retried on the next tick.`,
    'timeout': `Live mempool service did not respond within ${opts.timeoutSeconds ?? 10}s — ${unknownSuffix}`,
    'api-error': `Live mempool service returned an error${opts.status ? ` (HTTP ${opts.status})` : ''} — ${unknownSuffix}`,
    'unreachable': `Live mempool service is unreachable — ${unknownSuffix}`,
  };
  return { success: false, txs: [], live: false, reason, retryable: true, note: notes[reason] };
}

export function mapProxyFailure(
  err: PipelineHttpError | null | undefined,
  ctx: ProxyFailureContext,
): ProxyFailureEnvelope {
  const status = err?.status;
  const detail = err?.body?.detail;
  const detailMessage = typeof detail === 'string' ? detail : detail?.message;
  const detailKind = typeof detail === 'object' && detail ? detail.kind : null;
  const timeoutSeconds = ctx.timeoutSeconds ?? DEFAULT_PIPELINE_TIMEOUT_SECONDS;

  // 1. Not in the ingested dataset (or live tracing disabled): an honest answer.
  if (status === 404) {
    return {
      source: 'pipeline',
      available: true,
      data: {
        address: ctx.address,
        hopDepth: ctx.hopDepth,
        found: false,
        note: 'Wallet not present in the ingested Elliptic dataset — no trace, rule signal, or verdict exists for it, and the learned signal reports it as classified:false (no risk is fabricated).'
          + (detailMessage ? ` (Pipeline: ${detailMessage})` : ''),
        score: {
          wallet: ctx.address,
          classified: false,
          risk_score: null,
          prediction: null,
          learned_flag: false,
        },
      },
    };
  }

  // 2. Our own abort: the request was slow. Retryable, and NOT "down".
  if (err?.name === 'AbortError') {
    return {
      source: 'retryable',
      available: false,
      kind: 'timeout',
      note: `Python pipeline did not answer within ${timeoutSeconds} s — the request was slow, which is NOT the same as the service being down, and says nothing about the address. No new trace data is shown; the previous view (if any) remains on screen unchanged. Retry; a lower hop depth is faster.`,
    };
  }

  // 3. Live sources unavailable: the pipeline is up and said so (retryable).
  if (status === 429 || (status === 503 && detail?.retryable === true)) {
    return {
      source: 'retryable',
      available: false,
      kind: detailKind ?? (status === 429 ? 'rate-limited' : 'api-error'),
      note: detailMessage
        ?? `Python pipeline reports the public block explorers are unavailable (HTTP ${status}) — this says nothing about the address; no conclusion about it was reached. No new trace data is shown; retry shortly.`,
    };
  }

  // 4. The pipeline rejected the request: a client problem, not an outage.
  if (status === 400 || status === 422) {
    return {
      source: 'invalid-input',
      available: false,
      kind: detailKind ?? 'invalid-request',
      note: detailMessage
        ?? 'The pipeline rejected this request as invalid (not a service failure). Nothing was looked up; no signal is computed.',
    };
  }

  // 5. The pipeline answered with an internal error: NOT "unreachable".
  if (typeof status === 'number') {
    return {
      source: 'fallback',
      available: false,
      kind: 'service-error',
      note: `Python pipeline responded with HTTP ${status} (an internal error) — no new trace data is shown; the previous view (if any) remains on screen unchanged. Check the Python backend logs. This says nothing about the address.`,
    };
  }

  // 6. No HTTP response at all: genuinely unreachable.
  return {
    source: 'fallback',
    available: false,
    kind: 'unreachable',
    note: 'Python pipeline service unreachable — no new trace data is shown; the previous view (if any) remains on screen unchanged. Start the backend with: cd backend && uvicorn ledgr.service:app --reload',
  };
}
