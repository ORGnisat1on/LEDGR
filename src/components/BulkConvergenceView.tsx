import React from 'react';
import { X, GitMerge, ShieldAlert, Building2, Database } from 'lucide-react';
import { CONVERGENCE_CLUSTERS } from '../data/mockCases';
import { ConfidenceTier } from '../types';

/** Real cluster row served by the Python pipeline (Phase R6). */
interface PipelineCluster {
  cluster_id: string;
  confidence_tier: 'elliptic-derived' | 'supplementary-source';
  n_wallets: number;
  label_counts: { illicit: number; licit: number; unknown: number };
  illicit_fraction: number;
  members_sample: string[];
  attribution: {
    name: string;
    category: string;
    confidence_tier: ConfidenceTier;
    source_name: string;
    jurisdiction?: string | null;
  } | null;
  verdict_counts?: { confirmed: number; watch: number; none: number };
}

interface ClustersPayload {
  source: 'pipeline' | 'fallback';
  available: boolean;
  note?: string;
  report?: {
    n_clusters: number;
    n_wallets: number;
    exchange_list_loaded: boolean;
    clusters: PipelineCluster[];
    supplementary_matches: { cluster_id: string; name: string; source: string }[];
  };
}

const TIER_STYLES: Record<ConfidenceTier, { label: string; badge: string; dot: string }> = {
  'elliptic-derived': {
    label: 'elliptic-derived',
    badge: 'text-teal-300 bg-teal-950/50 border-teal-700/50',
    dot: 'bg-teal-400',
  },
  'supplementary-source': {
    label: 'supplementary-source',
    badge: 'text-amber-300 bg-amber-950/50 border-amber-700/50',
    dot: 'bg-amber-400',
  },
  'unattributed': {
    label: 'unattributed',
    badge: 'text-zinc-400 bg-zinc-950/50 border-zinc-700/50',
    dot: 'bg-zinc-500',
  },
};

const TierBadge: React.FC<{ tier: ConfidenceTier }> = ({ tier }) => {
  const s = TIER_STYLES[tier] ?? TIER_STYLES['elliptic-derived'];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold font-mono px-2 py-0.5 rounded-md border ${s.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
};

interface BulkConvergenceViewProps {
  isOpen: boolean;
  onClose: () => void;
  onTraceAddress: (address: string) => void;
}

export const BulkConvergenceView: React.FC<BulkConvergenceViewProps> = ({
  isOpen,
  onClose,
  onTraceAddress
}) => {
  const [payload, setPayload] = React.useState<ClustersPayload | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoading(true);
    const API_URL = import.meta.env.VITE_API_URL || "";
    fetch(`${API_URL}/api/clusters`)
      .then((r) => r.json())
      .then((data: ClustersPayload) => { if (!cancelled) setPayload(data); })
      .catch(() => { if (!cancelled) setPayload({ source: 'fallback', available: false, note: 'Clustering service unreachable — no cluster data is shown. Start the backend and retry.' }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [isOpen]);

  const cluster = CONVERGENCE_CLUSTERS[0];
  const isPipeline = payload?.source === 'pipeline' && !!payload.report;
  const report = payload?.report;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-[#0e0e12] rounded-2xl shadow-2xl border border-zinc-800/80 w-full max-w-4xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-[#121217] text-white px-5 py-4 flex items-center justify-between border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-950/50 border border-indigo-800/60 flex items-center justify-center text-sky-400">
              <GitMerge className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Wallet Clustering &amp; Attribution
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

        <div className="p-5 space-y-4 max-h-[520px] overflow-y-auto text-zinc-300">
          {/* Data-source banner: real pipeline vs explicitly-labeled mock */}
          {loading && (
            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-400 flex items-center gap-2">
              <Database className="w-4 h-4 animate-pulse" /> Loading cluster report…
            </div>
          )}
          {!loading && payload && !isPipeline && (
            <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-800/60 text-xs text-amber-300 space-y-1">
              <div className="font-bold uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" /> Offline mock data — not live pipeline output
              </div>
              <p className="text-amber-200/80">{payload.note}</p>
              <p className="text-amber-200/60">
                Run <code className="font-mono">backend/scripts/build_clusters.py</code> and start the
                Python service to see real Elliptic-derived clusters here.
              </p>
            </div>
          )}
          {!loading && isPipeline && report && (
            <div className="p-3 rounded-xl bg-teal-950/30 border border-teal-800/60 text-xs text-teal-300 space-y-1">
              <div className="font-bold uppercase tracking-wider flex items-center gap-2">
                <Database className="w-4 h-4" /> Live pipeline output — Elliptic-derived clustering
              </div>
              <p className="text-teal-200/80">
                {report.n_clusters} clusters over {report.n_wallets} wallets. Supplementary
                named-exchange attribution is a separate, lower-confidence source
                {report.exchange_list_loaded ? '' : ' (no sourced exchange list loaded — none attached)'}.
              </p>
            </div>
          )}

          {/* REAL pipeline clusters */}
          {!loading && isPipeline && report && report.clusters.map((c) => (
            <div key={c.cluster_id} className="p-4 rounded-xl bg-[#121217] border border-zinc-800/80 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-zinc-400">{c.cluster_id}</span>
                  <TierBadge tier={c.confidence_tier} />
                </div>
                <span className="text-[10px] font-mono text-zinc-500">{c.n_wallets} wallets</span>
              </div>

              {c.attribution && (
                <div className="p-2.5 rounded-lg bg-indigo-950/50 border border-indigo-800/50 text-xs flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <Building2 className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="font-bold text-white">{c.attribution.name}</div>
                      <div className="text-[10px] font-mono text-zinc-400">
                        source: {c.attribution.source_name}
                        {c.attribution.jurisdiction ? ` • ${c.attribution.jurisdiction}` : ''}
                      </div>
                    </div>
                  </div>
                  <TierBadge tier={c.attribution.confidence_tier} />
                </div>
              )}

              <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
                <div className="p-2 rounded-lg bg-rose-950/30 border border-rose-900/50">
                  <div className="font-bold text-rose-300 font-mono">{c.label_counts.illicit}</div>
                  <div className="text-[10px] text-zinc-500">illicit</div>
                </div>
                <div className="p-2 rounded-lg bg-emerald-950/30 border border-emerald-900/50">
                  <div className="font-bold text-emerald-300 font-mono">{c.label_counts.licit}</div>
                  <div className="text-[10px] text-zinc-500">licit</div>
                </div>
                <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                  <div className="font-bold text-zinc-300 font-mono">{c.label_counts.unknown}</div>
                  <div className="text-[10px] text-zinc-500">unknown</div>
                </div>
              </div>

              {c.verdict_counts && (
                <div className="flex gap-2 text-[10px] font-mono text-zinc-400">
                  <span className="px-2 py-0.5 rounded bg-rose-950/40 text-rose-300">confirmed: {c.verdict_counts.confirmed}</span>
                  <span className="px-2 py-0.5 rounded bg-amber-950/40 text-amber-300">watch: {c.verdict_counts.watch}</span>
                  <span className="px-2 py-0.5 rounded bg-zinc-900 text-zinc-400">none: {c.verdict_counts.none}</span>
                </div>
              )}

              <div className="space-y-1">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">Member wallets</div>
                {c.members_sample.map((m) => (
                  <button
                    key={m}
                    onClick={() => onTraceAddress(m)}
                    className="w-full text-left font-mono text-[10px] text-indigo-300 hover:text-indigo-200 hover:bg-indigo-950/40 rounded px-2 py-1 transition-colors cursor-pointer truncate"
                  >
                    {m}
                  </button>
                ))}
                {c.n_wallets > c.members_sample.length && (
                  <div className="text-[10px] text-zinc-600 font-mono">
                    +{c.n_wallets - c.members_sample.length} more wallets in this cluster
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* MOCK fallback (only when the pipeline is unavailable) */}
          {!loading && payload && !isPipeline && (
            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/60 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
                  <h3 className="text-sm font-bold text-rose-300">
                    Detected Cross-State Syndicate Convergence Hub
                  </h3>
                </div>
                <span className="text-xs font-bold text-rose-300 font-mono bg-rose-900/40 px-2.5 py-0.5 rounded-md border border-rose-700/50">
                  {cluster.convergingCases.length} VICTIMS MERGED
                </span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {cluster.syndicateProfile}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
