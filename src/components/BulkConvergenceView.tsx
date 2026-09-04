import React from 'react';
import { X, GitMerge, ShieldAlert, ArrowRight, Building2, Download, Copy, Check, Users } from 'lucide-react';
import { CONVERGENCE_CLUSTERS } from '../data/mockCases';
import { ConvergenceCluster } from '../types';

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
  const [copied, setCopied] = React.useState(false);
  const cluster = CONVERGENCE_CLUSTERS[0];

  if (!isOpen) return null;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
                Syndicate Convergence
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
          {/* Syndicate Banner */}
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 text-xs">
              <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Total Aggregate Defrauded (Merged):</span>
                <span className="text-base font-bold text-white font-mono">
                  ₹{cluster.totalCombinedLossInr.toLocaleString('en-IN')}
                </span>
                <span className="text-xs font-mono text-zinc-400 ml-1">({cluster.totalCombinedLossBtc} BTC)</span>
              </div>
              <div className="p-2.5 bg-[#121217] rounded-xl border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Shared Destination VASP Deposit:</span>
                <div className="flex items-center justify-between gap-1 font-mono text-[11px] text-indigo-400 truncate">
                  <span className="truncate">{cluster.clusterDepositAddress}</span>
                  <button
                    onClick={() => handleCopy(cluster.clusterDepositAddress)}
                    className="p-1 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-white shrink-0 cursor-pointer"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
                <span className="text-[10px] text-zinc-400 block mt-0.5">Entity: <strong className="text-zinc-200">{cluster.name}</strong></span>
              </div>
            </div>
          </div>

          {/* Visual Convergence Funnel Flow */}
          <div className="p-4 bg-[#121217] rounded-xl border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-4 h-4 text-indigo-400" />
              Independent Complainant Inflow Traces
            </h4>

            <div className="grid grid-cols-1 gap-2.5">
              {cluster.convergingCases.map((c, idx) => (
                <div
                  key={c.ackNumber}
                  className="p-3 bg-[#16161d] rounded-xl border border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:border-indigo-500/50 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white">{c.victimName}</span>
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.2 rounded-md font-medium">
                        {c.state}
                      </span>
                      <span className="text-[10px] font-mono text-indigo-300 bg-indigo-950/50 px-1.5 py-0.2 rounded-md border border-indigo-800/40">
                        {c.ackNumber}
                      </span>
                    </div>
                    <div className="text-zinc-400 text-[11px]">
                      Modus Operandi: <strong className="text-zinc-300">{c.scamType}</strong>
                    </div>
                    <div className="font-mono text-[10px] text-zinc-500">
                      Initial Suspect Wallet: {c.initialSuspectAddress}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 sm:text-right shrink-0">
                    <div>
                      <div className="font-bold text-white font-mono">
                        ₹{c.amountInr.toLocaleString('en-IN')}
                      </div>
                      <div className="text-[10px] text-zinc-400 font-mono">
                        {c.amountBtc} BTC • {c.hopsToConvergence} hops to hub
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-indigo-400 hidden sm:block" />
                  </div>
                </div>
              ))}
            </div>

            {/* Destination node */}
            <div className="p-3 bg-indigo-950/60 border border-indigo-800/60 text-white rounded-xl flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5">
                <Building2 className="w-5 h-5 text-amber-400 shrink-0" />
                <div>
                  <div className="font-bold text-white text-sm">
                    Converged Exchange Cluster: {cluster.name}
                  </div>
                  <div className="text-indigo-300 text-[11px] font-mono truncate max-w-md">
                    Deposit Sub-Account: {cluster.clusterDepositAddress}
                  </div>
                </div>
              </div>
              <div className="text-right shrink-0">
                <span className="text-[10px] text-indigo-300 block uppercase font-medium">Syndicate Total</span>
                <span className="text-sm font-bold text-amber-400 font-mono">
                  {cluster.totalCombinedLossBtc} BTC
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
