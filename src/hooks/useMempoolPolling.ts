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

export interface MempoolApiResponse {
  success: boolean;
  txs: MempoolTx[];
  live: boolean;
  note?: string;
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

    try {
      const API_URL = import.meta.env.VITE_API_URL || "";
      const response = await fetch(`${API_URL}/api/mempool/address/${encodeURIComponent(address)}`, {
        signal: abortControllerRef.current.signal,
        headers: { 'Accept': 'application/json' },
      });

      if (!mountedRef.current) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: MempoolApiResponse = await response.json();
      setLastPolledAt(Date.now());

      if (!data.success || !data.txs || data.txs.length === 0) {
        // No unconfirmed transactions - this is the normal case
        if (alert !== null) {
          setAlert(null);
        }
        return;
      }

      // Process transactions to find ones involving our watched address
      // For each tx, determine if it's incoming or outgoing relative to the watched address
      const watchedAddrLower = address.toLowerCase();

      for (const tx of data.txs) {
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
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
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
    lastPolledAt,
  };
}