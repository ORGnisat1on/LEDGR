import React from 'react';
import { Shield, AlertTriangle, Radio, FileText, Database, Activity, GitMerge } from 'lucide-react';

interface HeaderProps {
  activeCaseId: string;
  onSelectCase: (caseId: string) => void;
  onOpenIntake: () => void;
  onOpenWatchlist: () => void;
  onOpenConvergence: () => void;
  onOpenMethodology: () => void;
  onOpenReport: () => void;
  unconfirmedAlertCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeCaseId,
  onSelectCase,
  onOpenIntake,
  onOpenWatchlist,
  onOpenConvergence,
  onOpenMethodology,
  onOpenReport,
  unconfirmedAlertCount
}) => {
  return (
    <header className="border-b border-zinc-800/80 bg-[#09090b] shadow-lg shadow-black/40 sticky top-0 z-40">
      {/* Main Nav */}
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#121215] flex items-center justify-center text-white shadow-md border border-zinc-800">
            <Shield className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <h1 className="text-xl font-black text-white tracking-wider leading-none">
              LEDGR
            </h1>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            id="btn-open-intake"
            onClick={onOpenIntake}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 shadow-md shadow-indigo-950/40 transition-colors cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Intake</span>
          </button>

          <button
            id="btn-open-watchlist"
            onClick={onOpenWatchlist}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl border transition-colors cursor-pointer ${
              unconfirmedAlertCount > 0
                ? 'bg-amber-950/40 text-amber-200 border-amber-800/80 hover:bg-amber-900/40 font-semibold'
                : 'bg-[#121215] text-zinc-300 border-zinc-800 hover:bg-zinc-800/80 hover:text-white'
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${unconfirmedAlertCount > 0 ? 'text-amber-400 animate-spin' : 'text-zinc-400'}`} />
            <span>Mempool</span>
            {unconfirmedAlertCount > 0 && (
              <span className="bg-amber-500 text-zinc-950 text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                {unconfirmedAlertCount}
              </span>
            )}
          </button>

          <button
            id="btn-open-convergence"
            onClick={onOpenConvergence}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl bg-[#121215] text-zinc-300 border border-zinc-800 hover:bg-zinc-800/80 hover:text-white transition-colors cursor-pointer"
          >
            <GitMerge className="w-3.5 h-3.5 text-indigo-400" />
            <span>Convergence</span>
          </button>

          <button
            id="btn-open-methodology"
            onClick={onOpenMethodology}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl bg-[#121217] text-zinc-300 border border-zinc-800 hover:bg-zinc-800/80 hover:text-white transition-colors cursor-pointer"
          >
            <Database className="w-3.5 h-3.5 text-zinc-400" />
            <span>Benchmark</span>
          </button>

          <button
            id="btn-open-report"
            onClick={onOpenReport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl bg-zinc-800 text-zinc-100 hover:bg-zinc-700 border border-zinc-700/80 shadow-md shadow-black/30 transition-colors cursor-pointer"
          >
            <FileText className="w-3.5 h-3.5 text-amber-400" />
            <span>Dossier</span>
          </button>
        </div>
      </div>
    </header>
  );
};
