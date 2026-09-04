import React from 'react';
import { Building2, Copy, Check, ShieldAlert, Globe, Mail, FileCheck, ExternalLink } from 'lucide-react';
import { TraceResult } from '../types';

interface AttributionCardProps {
  trace: TraceResult;
  onOpenReport: () => void;
}

export const AttributionCard: React.FC<AttributionCardProps> = ({ trace, onOpenReport }) => {
  const [copied, setCopied] = React.useState(false);
  const { attribution, summaryStats } = trace;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isSupplementary = attribution.confidenceTier === 'supplementary-source';

  return (
    <div className="bg-[#0e0e12] rounded-2xl border border-zinc-800/80 shadow-lg shadow-black/20 overflow-hidden">
      <div className="px-4 py-3 bg-[#121217] border-b border-zinc-800/80 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-indigo-400" />
          <h2 className="text-sm font-bold text-white tracking-tight">
            Destination Attribution
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-lg border flex items-center gap-1 ${
            isSupplementary
              ? 'bg-amber-950/30 text-amber-300 border-amber-800/50'
              : 'bg-indigo-950/30 text-indigo-300 border-indigo-800/50'
          }`}>
            <span className="text-zinc-400">Confidence:</span>
            <strong>{attribution.confidenceTier}</strong>
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Main Entity Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 rounded-xl bg-gradient-to-r from-[#15151c] to-[#121217] border border-zinc-800 text-white">
          <div className="space-y-1">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Destination Entity
            </span>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-white tracking-tight">
                {attribution.name}
              </h3>
              <span className="text-[10px] font-bold bg-rose-500/20 text-rose-300 px-2 py-0.5 rounded-md border border-rose-500/40">
                {attribution.riskLevel} PRIORITY
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              {attribution.sourceCitation}
            </p>
          </div>

          <div className="sm:text-right shrink-0">
            <span className="text-[11px] text-zinc-400 block">Funds Traversed</span>
            <span className="text-base font-bold text-amber-400 font-mono">
              {summaryStats.totalTrackedBtc} BTC
            </span>
            <span className="text-xs text-zinc-400 block font-mono">
              (₹{(summaryStats.totalTrackedInr).toLocaleString('en-IN')})
            </span>
          </div>
        </div>

        {/* Deposit Address Details & Compliance Target */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 bg-[#141418] rounded-xl border border-zinc-800/80 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-300">Target Deposit Wallet:</span>
              <button
                onClick={() => handleCopy(attribution.depositAddress)}
                className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <div className="p-2 bg-[#0c0c0e] rounded-lg border border-zinc-800 font-mono text-[11px] text-zinc-200 break-all select-all">
              {attribution.depositAddress}
            </div>
            <div className="flex items-center justify-between text-zinc-500 pt-1 text-[11px]">
              <span>Jurisdiction:</span>
              <span className="font-medium text-zinc-300">{attribution.jurisdiction}</span>
            </div>
          </div>

          <div className="p-3 bg-[#141418] rounded-xl border border-zinc-800/80 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-300">Compliance Nodal:</span>
              <span className="text-[11px] text-emerald-300 bg-emerald-950/40 px-1.5 py-0.5 rounded-md border border-emerald-800/50 font-medium">
                Verified Contact
              </span>
            </div>
            <div className="p-2 bg-[#0c0c0e] rounded-lg border border-zinc-800 text-[11px] space-y-1">
              <div className="text-zinc-200 font-medium">{attribution.complianceNoticeTarget.legalEntity}</div>
              <div className="text-indigo-400 font-mono text-[11px] flex items-center gap-1">
                <Mail className="w-3 h-3 text-zinc-500" />
                {attribution.complianceNoticeTarget.grievanceOfficerEmail}
              </div>
            </div>
            <div className="flex items-center justify-between text-zinc-500 pt-1 text-[11px]">
              <span>Statutory:</span>
              <span className="font-medium text-zinc-300">Sec 91 CrPC / 94 BNSS</span>
            </div>
          </div>
        </div>

        {/* Action button */}
        <div className="flex items-center justify-end pt-1">
          <button
            onClick={onOpenReport}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 shadow-md shadow-indigo-950/40 transition-colors cursor-pointer"
          >
            <FileCheck className="w-4 h-4 text-white" />
            <span>Generate Freeze Notice</span>
          </button>
        </div>
      </div>
    </div>
  );
};
