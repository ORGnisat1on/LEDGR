import { useState, useEffect, useCallback, useRef } from 'react';

export interface MempoolTx {
  txid: string;
  version: number;
  locktime: number;
  vin: Array<{
    txid: string;
    vout: number;
    prevout: {
      scriptpubkey: string;
      scriptpubkey_asm: string;
      scriptpubkey_type: string;
      scriptpubkey_address: string;
      value: number; // satoshis
    };
    scriptsig: string;
    scriptsig_asm: string;
    is_coinbase: boolean;
    sequence: number;
  }>;
  vout: Array<{
    scriptpubkey: string;
    scriptpubkey_asm: string;
    scriptpubkey_type: string;
    scriptpubkey_address: string;
    value: number; // satoshis
  }>;
  size: number;
  weight: number;
  sigops: number;
  fee: number; // satoshis
  status: {
    confirmed: boolean;
  };
}

/**
 * Why the live mempool answer is UNKNOWN for a poll. These describe the REQUEST
 * (transient service problems), never the address's activity level — a failed
 * lookup must never be presented as "no unconfirmed transactions".
 */
export type MempoolUnavailableReason = 'rate-limited' | 'timeout' | 'api-error' | 'unreachable';

const MEMPOOL_REASON_LABEL: Record<MempoolUnavailableReason, string> = {
  'rate-limited': 'the public mempool service rate-limited the request',
  'timeout': 'the public mempool service did not respond in time',
  'api-error': 'the public mempool service returned an error',
  'unreachable': 'the public mempool service is unreachable',
};

export interface MempoolApiResponse {
  success: boolean;
  txs: MempoolTx[];
  live: boolean;
  note?: string;
  /**
   * Present when `success` is false: WHY the answer is unknown. The proxy
   * guarantees `success:false` means "could not check", never "nothing found".
   */
  reason?: MempoolUnavailableReason;
  retryable?: boolean;
}

export interface UnconfirmedAlert {
  txHash: string;
  direction: 'incoming' | 'outgoing';
  amountBtc: number;
  amountInr: number;
  detectedAt: string; // ISO timestamp when detected
  status: 'unconfirmed_mempool';
  feeRateSatVb: number;
  counterpartyAddress: string;
}

export interface MempoolPollingState {
  alert: UnconfirmedAlert | null;
  isLoading: boolean;
  error: string | null;
  /** Machine-readable cause behind `error`, for UI copy that must not guess. */
  unavailableReason: MempoolUnavailableReason | null;
  /**
   * Timestamp of the last poll that ACTUALLY SUCCEEDED. A failed poll does not
   * update it, so the UI can never present unknown data as fresh.
   */
  lastPolledAt: number | null;
}

interface UseMempoolPollingOptions {
  address: string;
  enabled?: boolean;
  intervalMs?: number;
  btcToInrRate?: number;
  onAlert?: (alert: UnconfirmedAlert) => void;
}

const SATOSHIS_PER_BTC = 100_000_000;
const DEFAULT_INTERVAL_MS = 30_000; // 30 seconds - respectful of mempool.space rate limits
const DEFAULT_BTC_TO_INR = 894800; // approximate rate, can be overridden

/**
 * The part of the poll state machine that decides what a poll RESPONSE does to
 * the current state — extracted as a pure function so the honesty invariant can
 * be regression-tested without a DOM (the repo has no jsdom / react-test-renderer,
 * and adding a test framework is out of scope for this change).
 *
 * The hook below calls this directly, so the tested function IS the shipped
 * logic, not a re-implementation of it.
 */
export interface MempoolStateCore {
  alert: UnconfirmedAlert | null;
  error: string | null;
  unavailableReason: MempoolUnavailableReason | null;
  /** Timestamp of the last SUCCESSFUL poll. */
  lastPolledAt: number | null;
}

export interface MempoolPollTransition {
  alert: UnconfirmedAlert | null;
  error: string | null;
  unavailableReason: MempoolUnavailableReason | null;
  lastPolledAt: number | null;
  /** True only for a poll that actually succeeded; drives data freshness. */
  ok: boolean;
  /** Transactions the hook must still scan for a new alert (empty on failure). */
  txs: MempoolTx[];
}

const UNKNOWN_SUFFIX =
  'Unconfirmed activity is UNKNOWN for this poll; this is NOT a "no unconfirmed transactions" result.';

export function applyMempoolPoll(
  prev: MempoolStateCore,
  payload: any,
  now: number,
): MempoolPollTransition {
  // A body we cannot read is not an empty mempool.
  if (!payload || typeof payload !== 'object') {
    return {
      ...prev,
      error: 'Live mempool service returned an unreadable response — unconfirmed activity is UNKNOWN for this poll. This is NOT a "no unconfirmed transactions" result.',
      unavailableReason: 'api-error',
      ok: false,
      txs: [],
    };
  }

  // HONESTY GATE: `success:false` means "could not check", never "nothing found".
  // It must not clear an alert (that would delete a real signal) and must not
  // advance the freshness timestamp (unknown data is not fresh data).
  if (payload.success === false) {
    const reason: MempoolUnavailableReason = payload.reason ?? 'api-error';
    return {
      ...prev,
      error: `Live mempool check unavailable — ${MEMPOOL_REASON_LABEL[reason]}. ${UNKNOWN_SUFFIX} Any previously detected alert is kept until a poll succeeds.`,
      unavailableReason: reason,
      ok: false,
      txs: [],
    };
  }

  const txs: MempoolTx[] = Array.isArray(payload.txs) ? payload.txs : [];
  // A successful poll is the ONLY case that may clear a raised alert (a genuine
  // "no unconfirmed transactions" answer) and the only case that advances
  // data freshness.
  return {
    alert: txs.length === 0 ? null : prev.alert,
    error: null,
    unavailableReason: null,
    lastPolledAt: now,
    ok: true,
    txs,
  };
}

/**
 * Custom hook for polling mempool.space via our proxy endpoint for unconfirmed transactions
 * on a specific Bitcoin address.
 *
 * Rate limit consideration: mempool.space public API recommends not polling faster than
 * 30 seconds per address. With N addresses, we poll each independently at 30s intervals.
 * For a watchlist of 4 addresses: 4 req/30s = 8 req/min = 480 req/hr, well within free tier.
 */
export function useMempoolPolling({
  address,
  enabled = true,
  intervalMs = DEFAULT_INTERVAL_MS,
  btcToInrRate = DEFAULT_BTC_TO_INR,
  onAlert,
}: UseMempoolPollingOptions): MempoolPollingState {
  const [alert, setAlert] = useState<UnconfirmedAlert | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailableReason, setUnavailableReason] = useState<MempoolUnavailableReason | null>(null);
  const [lastPolledAt, setLastPolledAt] = useState<number | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  // Clean up on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const poll = useCallback(async () => {
    if (!mountedRef.current) return;

    abortControllerRef.current = new AbortController();
    setIsLoading(true);
    setError(null);
    setUnavailableReason(null);

    try {
      const API_URL = (import.meta as any)?.env?.VITE_API_URL ?? "";
      const response = await fetch(`${API_URL}/api/mempool/address/${encodeURIComponent(address)}`, {
        signal: abortControllerRef.current.signal,
        headers: { 'Accept': 'application/json' },
      });

      if (!mountedRef.current) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: MempoolApiResponse = await response.json().catch(() => null);

      // Single decision point: applyMempoolPoll owns the honesty invariant
      // (a failed poll must not clear a raised alert and must not advance the
      // freshness timestamp). It is pure and exported so it can be tested
      // directly — see the 429 regression tests in test/mempool-poll.test.ts.
      const next = applyMempoolPoll(
        { alert, error, unavailableReason, lastPolledAt },
        data,
        Date.now(),
      );
      if (!mountedRef.current) return;

      setError(next.error);
      setUnavailableReason(next.unavailableReason);
      if (next.ok) setLastPolledAt(next.lastPolledAt);

      if (!next.ok) {
        // Keep the existing alert on purpose: a throttled/failed poll deleting a
        // real unconfirmed-tx signal is the bug this gate exists to prevent.
        return;
      }
      if (next.alert === null && alert !== null) {
        // The ONLY case in which a previously raised alert may be cleared: a
        // successful poll that found no unconfirmed transactions.
        setAlert(null);
      }
      if (next.txs.length === 0) return;

      // Process transactions to find ones involving our watched address
      // For each tx, determine if it's incoming or outgoing relative to the watched address
      const watchedAddrLower = address.toLowerCase();

      for (const tx of next.txs) {
        let isIncoming = false;
        let isOutgoing = false;
        let amountSats = 0;
        let counterpartyAddress = '';

        // Check outputs (vout) - if our address receives, it's incoming
        for (const vout of tx.vout) {
          if (vout.scriptpubkey_address?.toLowerCase() === watchedAddrLower) {
            isIncoming = true;
            amountSats += vout.value;
          }
        }

        // Check inputs (vin) - if our address spends, it's outgoing
        for (const vin of tx.vin) {
          if (vin.prevout?.scriptpubkey_address?.toLowerCase() === watchedAddrLower) {
            isOutgoing = true;
            amountSats += vin.prevout.value;
          }
        }

        // If neither incoming nor outgoing (shouldn't happen for our address), skip
        if (!isIncoming && !isOutgoing) continue;

        // Determine counterparty address
        if (isIncoming) {
          // Counterparty is the sender (from vin)
          const senderVin = tx.vin[0];
          if (senderVin?.prevout?.scriptpubkey_address) {
            counterpartyAddress = senderVin.prevout.scriptpubkey_address;
          }
        } else if (isOutgoing) {
          // Counterparty is the receiver (first vout that's not our address)
          const otherVout = tx.vout.find(v => v.scriptpubkey_address?.toLowerCase() !== watchedAddrLower);
          if (otherVout?.scriptpubkey_address) {
            counterpartyAddress = otherVout.scriptpubkey_address;
          }
        }

        // Calculate fee rate in sat/vB
        const feeRateSatVb = tx.weight > 0 ? Math.round((tx.fee / tx.weight) * 4) : 0;

        // Create alert object
        const detectedAt = new Date().toISOString();
        const amountBtc = amountSats / SATOSHIS_PER_BTC;
        const amountInr = Math.round(amountBtc * btcToInrRate);

        const newAlert: UnconfirmedAlert = {
          txHash: tx.txid,
          direction: isIncoming ? 'incoming' : 'outgoing',
          amountBtc: Number(amountBtc.toFixed(8)),
          amountInr,
          detectedAt,
          status: 'unconfirmed_mempool',
          feeRateSatVb,
          counterpartyAddress: counterpartyAddress || 'Unknown',
        };

        if (!mountedRef.current) return;

        setAlert(newAlert);
        onAlert?.(newAlert);
        break; // Only alert on the first relevant transaction (most recent)
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof Error && err.name === 'AbortError') return;
      // A transport-level failure is also "unknown", not "no activity": keep the
      // last known alert and do NOT advance the freshness timestamp.
      const msg = err instanceof Error ? err.message : 'Unknown error';
      const timedOut = msg.toLowerCase().includes('abort');
      setUnavailableReason(timedOut ? 'timeout' : 'unreachable');
      setError(
        `Live mempool check failed (${msg}) — unconfirmed activity is UNKNOWN for this poll; ` +
        `this is NOT a "no unconfirmed transactions" result. Any previously detected alert is kept.`,
      );
      // Don't clear existing alert on error - keep showing last known state
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [address, btcToInrRate, onAlert, alert]);

  // Start/stop polling based on enabled state
  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Initial poll
    poll();

    // Set up interval
    intervalRef.current = setInterval(poll, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, intervalMs, poll]);

  return {
    alert,
    isLoading,
    error,
    unavailableReason,
    lastPolledAt,
  };
}