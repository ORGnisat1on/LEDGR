import React, { useState, useEffect, useMemo } from 'react';
import { X, Radio, AlertTriangle, Clock, ShieldAlert, ArrowUpRight, ArrowDownLeft, CheckCircle2, ExternalLink, WifiOff, Activity, Loader2 } from 'lucide-react';
import { WatchlistItem } from '../types';
import { useMempoolPolling, UnconfirmedAlert, MempoolUnavailableReason } from '../hooks/useMempoolPolling';

interface WatchlistMonitorProps {
  isOpen: boolean;
  onClose: () => void;
  watchlist: WatchlistItem[];
  onTraceAddress: (address: string) => void;
  onDismissAlert?: (address: string) => void;
}

// Memoized relative time formatter
function formatRelativeTime(isoTimestamp: string, now: number): string {
  const then = new Date(isoTimestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${Math.floor(diffHour / 24)}d ago`;
}

// Polling status indicator for each address
interface AddressPollingState {
  address: string;
  alert: UnconfirmedAlert | null;
  isLoading: boolean;
  error: string | null;
  /**
   * Why the last poll could not check. Non-null means the status cell must say
   * "unknown" rather than "no activity" (a rate limit is not a clean result).
   */
  unavailableReason: MempoolUnavailableReason | null;
  lastPolledAt: number | null;
}

export const WatchlistMonitor: React.FC<WatchlistMonitorProps> = ({
  isOpen,
  onClose,
  watchlist,
  onTraceAddress,
  onDismissAlert
}) => {
  // RULES-OF-HOOKS FIX (2026-09-27): the `if (!isOpen) return null` early return used
  // to sit ABOVE these hooks, so the component ran a different number of hooks
  // depending on whether the modal was open. That is what produced the
  // "Too many re-renders. React limits the number of renders to prevent an
  // infinite loop." crash the moment a user opened the monitor (and why a
  // teammate hid the trigger). All hooks now run unconditionally and the
  // early return happens after them.
  //
  // Current time for live relative timestamps - updates every 10s while modal open
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!isOpen) return; // no ticker while the monitor is closed
    const interval = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(interval);
  }, [isOpen]);

  // Polling state per address
  const [pollingStates, setPollingStates] = useState<Map<string, AddressPollingState>>(new Map());

  // Keep one polling-state entry per watchlist address, preserving any alert that
  // has already been raised for an address that is still watched.
  //
  // RENDER-LOOP FIX (2026-09-27): this effect previously depended on
  // `pollingStates` while calling `setPollingStates` with a freshly-built Map.
  // Because the Map identity changed on every call, the effect re-ran forever
  // (setState -> render -> new Map -> effect) — the "infinite useEffect loop" that
  // made a teammate hide this feature's trigger. Two changes stop it:
  //   1. depend on `watchlist` only (the state is read through the updater), and
  //   2. return the SAME Map when the watched address set is unchanged, so React
  //      bails out instead of scheduling another render.
  useEffect(() => {
    setPollingStates(prev => {
      const next = new Map<string, AddressPollingState>();

      for (const item of watchlist) {
        const existing = prev.get(item.address);
        next.set(item.address, {
          address: item.address,
          alert: existing?.alert ?? null,
          isLoading: existing?.isLoading ?? false,
          error: existing?.error ?? null,
          unavailableReason: existing?.unavailableReason ?? null,
          lastPolledAt: existing?.lastPolledAt ?? null,
        });
      }

      // Same addresses as before (the common case: nothing added/removed) →
      // keep the previous Map identity so React skips the re-render entirely.
      let unchanged = next.size === prev.size;
      if (unchanged) {
        for (const key of next.keys()) {
          if (!prev.has(key)) { unchanged = false; break; }
        }
      }
      return unchanged ? prev : next;
    });
  }, [watchlist]);

  // Update polling state from hook results
  const updatePollingState = (address: string, update: Partial<AddressPollingState>) => {
    setPollingStates(prev => {
      const next = new Map<string, AddressPollingState>(prev);
      const current = next.get(address);
      if (current) {
        const merged: AddressPollingState = { ...current, ...update };
        next.set(address, merged);
      }
      return next;
    });
  };

  // Memoized hook callbacks to avoid re-creating on each render
  const handleAlert = useMemo(() => (address: string) => (alert: UnconfirmedAlert) => {
    updatePollingState(address, { alert, isLoading: false, error: null });
  }, []);

  // RENDER-LOOP FIX (2026-09-27): this was memoized on `pollingStates`, so it got a
  // new identity on every poll tick. `MempoolPoller` lists `onTick` in its effect
  // deps, so each new identity re-fired the tick -> setState -> re-render cycle.
  // The existing alert is now read from the updater instead of a captured value, so
  // the memo can have stable, empty deps (and unknown addresses / no-op ticks
  // return the previous Map so React bails out).
  const handlePollingTick = useMemo(() => (address: string, state: { isLoading: boolean; error: string | null; unavailableReason: MempoolUnavailableReason | null; lastPolledAt: number | null }) => {
    setPollingStates(prev => {
      const current = prev.get(address);
      if (!current) return prev;
      // The tick never carries an alert: keep whatever is already raised.
      const merged: AddressPollingState = { ...current, ...state, alert: current.alert };
      const unchanged =
        merged.isLoading === current.isLoading &&
        merged.error === current.error &&
        merged.unavailableReason === current.unavailableReason &&
        merged.lastPolledAt === current.lastPolledAt;
      if (unchanged) return prev;
      const next = new Map<string, AddressPollingState>(prev);
      next.set(address, merged);
      return next;
    });
  }, []);

  // STABLE POLLER CALLBACKS FIX (2026-09-27): the per-address callbacks used to be
  // built inline in the JSX — `onAlert={handleAlert(item.address)}` — which creates a
  // NEW function identity on every parent render. `useMempoolPolling` keeps `onAlert`
  // in its `poll` useCallback deps, and `poll` is a dep of the polling effect, so
  // every parent re-render tore down and restarted the 30 s timer and re-polled
  // immediately; each tick updated parent state, which re-rendered, which looped.
  // That is the "infinite useEffect loop" that crashed the monitor on open.
  // Building the closures once per watchlist (memoised on already-stable deps) keeps
  // each poller's props referentially stable.
  const pollerCallbacks = useMemo(() => {
    const map = new Map<string, { onAlert: (a: UnconfirmedAlert) => void; onTick: (s: any) => void }>();
    for (const item of watchlist) {
      const address = item.address;
      map.set(address, {
        onAlert: (alert: UnconfirmedAlert) => handleAlert(address)(alert),
        onTick: (state: any) => handlePollingTick(address, state),
      });
    }
    return map;
  }, [watchlist, handleAlert, handlePollingTick]);

  // Separate hook calls per address - React hooks must be called at top level
  // We'll use a different pattern: render a child component per address that uses the hook
  // For now, we'll handle polling in a useEffect with manual fetch

  // Actually, let's use a simpler approach: render WatchlistRow components that each use the hook
  // This avoids the rules of hooks issue

  const alerts = watchlist.filter(w => {
    const state = pollingStates.get(w.address);
    return !!state?.alert;
  });

  // All hooks above have now run unconditionally (rules of hooks). Only now may
  // a closed monitor render nothing.
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-[#0e0e12] rounded-2xl shadow-2xl border border-zinc-800/80 w-full max-w-4xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-[#121217] text-white px-5 py-4 flex items-center justify-between border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-950/40 border border-amber-800/60 flex items-center justify-center text-amber-400">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Mempool Monitor
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Real-Time Alert Banner if an unconfirmed broadcast is intercepted */}
        {alerts.length > 0 && (
          <div className="bg-gradient-to-r from-rose-950 via-rose-900 to-rose-950 border-b border-rose-800 text-white px-5 py-3 flex flex-wrap items-center justify-between gap-3 animate-pulse">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-300 shrink-0" />
              <div>
                <span className="font-bold text-xs uppercase tracking-wider block text-rose-200">
                  🚨 URGENT MEMPOOL BROADCAST INTERCEPTED ({alerts.length} UNCONFIRMED EVENT{alerts.length > 1 ? 'S' : ''})
                </span>
                <span className="text-xs text-zinc-300">
                  A watchlisted suspect wallet has just broadcast a new transaction to the network. It is currently unconfirmed in the mempool.
                </span>
              </div>
            </div>
            <span className="text-xs font-mono bg-rose-900/90 text-rose-200 px-2.5 py-1 rounded-lg border border-rose-700 font-bold">
              EST. TIME TO BLOCK: ~8-12 MINS
            </span>
          </div>
        )}

        {/* Content */}
        <div className="p-5 space-y-4 max-h-[520px] overflow-y-auto text-zinc-300">
          {/* Active alerts section */}
          {alerts.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                Live Unconfirmed Mempool Transactions (Emergency Action)
              </h3>

              {alerts.map(item => {
                const state = pollingStates.get(item.address);
                const alert = state?.alert;
                const detectedAtStr = alert ? formatRelativeTime(alert.detectedAt, now) : 'Unknown';

                return (
                  <div
                    key={item.address}
                    className="p-4 rounded-xl bg-[#16141a] border-2 border-rose-500/60 space-y-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="bg-rose-500/20 border border-rose-500/40 text-rose-300 font-bold text-[10px] px-2 py-0.5 rounded-md uppercase">
                          {alert?.direction.toUpperCase()} BROADCAST
                        </span>
                        <span className="text-xs font-bold text-white">{item.label}</span>
                      </div>
                      <span className="text-xs text-zinc-400 font-mono flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-zinc-400" />
                        {detectedAtStr}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                      <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">Broadcast Amount:</span>
                        <strong className="text-sm font-mono text-rose-400">
                          {alert?.amountBtc} BTC
                        </strong>
                        <span className="text-[11px] text-zinc-400 block">
                          (₹{(alert?.amountInr || 0).toLocaleString('en-IN')})
                        </span>
                      </div>

                      <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">Fee Rate (Miner Priority):</span>
                        <strong className="text-sm font-mono text-zinc-200">
                          {alert?.feeRateSatVb} sat/vB
                        </strong>
                        <span className="text-[11px] text-zinc-400 block">Standard Next-Block Relay</span>
                      </div>

                      <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800">
                        <span className="text-[10px] text-zinc-400 block">NCRP Incident Ack:</span>
                        <strong className="text-xs font-mono text-indigo-400">
                          {item.ackNumber}
                        </strong>
                        <span className="text-[11px] text-zinc-300 block">{item.victimName}</span>
                      </div>
                    </div>

                    <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800 text-xs font-mono break-all text-zinc-300">
                      <span className="text-zinc-400 block text-[10px]">Destination / Counterparty Address:</span>
                      {alert?.counterpartyAddress}
                    </div>

                    <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                      <button
                        onClick={() => {
                          onTraceAddress(item.address);
                          onClose();
                        }}
                        className="px-3.5 py-1.5 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-500 shadow-md shadow-indigo-950/40 cursor-pointer transition-colors"
                      >
                        Trace Subgraph & Target VASP
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Persisted Watchlist Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Persisted Flagged Wallets (Module 4 Verdicts)
              </h3>
              <span className="text-xs text-zinc-400">
                Total Monitored: <strong className="text-zinc-200">{watchlist.length} addresses</strong>
              </span>
            </div>

            <div className="overflow-x-auto border border-zinc-800/80 rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#141418] border-b border-zinc-800/80 font-semibold text-zinc-400">
                  <tr>
                    <th className="p-2.5">Wallet Label & Address</th>
                    <th className="p-2.5">NCRP Ack #</th>
                    <th className="p-2.5">Verdict</th>
                    <th className="p-2.5">Defrauded (INR)</th>
                    <th className="p-2.5">Mempool Status</th>
                    <th className="p-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/80 text-zinc-300">
                  {watchlist.map(item => {
                    const state = pollingStates.get(item.address);
                    const alert = state?.alert;
                    const isLoading = state?.isLoading ?? false;
                    const error = state?.error;
                    const lastPolled = state?.lastPolledAt;

                    // Determine status display
                    let statusContent: React.ReactNode;
                    let statusClass = '';

                    if (alert) {
                      statusContent = (
                        <span className="inline-flex items-center gap-1 text-rose-400 font-bold text-[11px]">
                          <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
                          UNCONFIRMED TX
                        </span>
                      );
                      statusClass = 'border-rose-500/30';
                    } else if (error) {
                      // The poll could not complete: say WHY and that the state is
                      // unknown. It must never read as "no activity" (an empty
                      // emerald "Idle / Monitoring" would be a fabricated clean
                      // result — the exact defect this branch exists to prevent).
                      const reasonLabel = state?.unavailableReason
                        ? ` (${state.unavailableReason})`
                        : '';
                      statusContent = (
                        <span className="inline-flex items-center gap-1 text-amber-400 text-[11px]" title={error}>
                          <WifiOff className="w-3.5 h-3.5 text-amber-400" />
                          CHECK FAILED{reasonLabel} — STATUS UNKNOWN
                        </span>
                      );
                      statusClass = 'border-amber-500/30';
                    } else if (isLoading) {
                      statusContent = (
                        <span className="inline-flex items-center gap-1 text-sky-400 text-[11px]">
                          <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                          POLLING...
                        </span>
                      );
                      statusClass = 'border-sky-500/30';
                    } else {
                      statusContent = (
                        <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px]">
                          <Activity className="w-3.5 h-3.5 text-emerald-400" />
                          Idle / Monitoring
                        </span>
                      );
                      statusClass = 'border-emerald-500/30';
                    }

                    // Show last SUCCESSFUL poll time for transparency. A failed
                    // poll deliberately does not update it, so this can never
                    // imply that unknown data is fresh.
                    const lastPolledStr = lastPolled
                      ? `Last successful check: ${formatRelativeTime(new Date(lastPolled).toISOString(), now)}`
                      : (error
                        ? 'Never checked successfully yet — status unknown'
                        : 'Not yet polled');

                    return (
                      <tr key={item.address} className={`hover:bg-[#141419] transition-colors ${statusClass}`}>
                        <td className="p-2.5">
                          <div className="font-semibold text-white">{item.label}</div>
                          <div className="font-mono text-[11px] text-zinc-400">{item.address}</div>
                        </td>
                        <td className="p-2.5 font-mono text-indigo-400">{item.ackNumber}</td>
                        <td className="p-2.5">
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                            item.verdict === 'confirmed'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          }`}>
                            {item.verdict}
                          </span>
                        </td>
                        <td className="p-2.5 font-mono text-zinc-200">₹{item.amountInr.toLocaleString('en-IN')}</td>
                        <td className="p-2.5" title={lastPolledStr}>
                          {statusContent}
                        </td>
                        <td className="p-2.5 text-right">
                          <button
                            onClick={() => {
                              onTraceAddress(item.address);
                              onClose();
                            }}
                            className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-colors cursor-pointer"
                          >
                            Trace
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-address polling components - each uses the hook */}
          {watchlist.map(item => {
            const cbs = pollerCallbacks.get(item.address);
            if (!cbs) return null;
            return (
              <MempoolPoller
                key={item.address}
                address={item.address}
                onAlert={cbs.onAlert}
                onTick={cbs.onTick}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};

// Separate component for each address's polling to satisfy React hooks rules
interface MempoolPollerProps {
  address: string;
  onAlert: (alert: UnconfirmedAlert) => void;
  onTick: (state: { isLoading: boolean; error: string | null; unavailableReason: MempoolUnavailableReason | null; lastPolledAt: number | null }) => void;
}

const MempoolPoller: React.FC<MempoolPollerProps> = ({ address, onAlert, onTick }) => {
  const { alert, isLoading, error, unavailableReason, lastPolledAt } = useMempoolPolling({
    address,
    enabled: true,
    intervalMs: 30_000,
    onAlert,
  });

  // Sync state back to parent via callback
  React.useEffect(() => {
    onTick({ isLoading, error, unavailableReason, lastPolledAt });
  }, [isLoading, error, unavailableReason, lastPolledAt, onTick]);

  return null; // This component only manages polling, doesn't render anything
};

export default WatchlistMonitor;