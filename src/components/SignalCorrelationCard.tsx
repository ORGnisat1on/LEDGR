import React from 'react';
import { ShieldCheck, AlertOctagon, HelpCircle, CheckCircle2, ChevronRight, Layers, Sparkles, Filter } from 'lucide-react';
import { TraceResult } from '../types';

interface SignalCorrelationCardProps {
  trace: TraceResult;
}

export const SignalCorrelationCard: React.FC<SignalCorrelationCardProps> = ({ trace }) => {
  const { verdict, contributingSignals } = trace;
  const isConfirmed = verdict === 'confirmed';
  const isWatch = verdict === 'watch';
  const isNone = verdict === 'none';

  return (
    <div className="bg-[#0e0e12] rounded-2xl border border-zinc-800/80 shadow-lg shadow-black/20 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-[#121217] border-b border-zinc-800/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <h2 className="text-sm font-bold text-white tracking-tight">
            Dual-Signal Correlation
          </h2>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Core Correlation Matrix Visualizer */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-stretch">
          {/* Rule-based Heuristics */}
          <div className={`p-3.5 rounded-xl border flex flex-col justify-between transition-colors ${
            contributingSignals.ruleFlag === 'high'
              ? 'bg-rose-950/20 border-rose-800/50 text-zinc-200'
              : contributingSignals.ruleFlag === 'low'
              ? 'bg-amber-950/20 border-amber-800/50 text-zinc-200'
              : 'bg-[#141418] border-zinc-800/80 text-zinc-200'
          }`}>
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5 text-zinc-400" />
                  Rule Heuristics
                </span>
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md uppercase ${
                  contributingSignals.ruleFlag === 'high'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    : contributingSignals.ruleFlag === 'low'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                }`}>
                  {contributingSignals.ruleFlag === 'high' ? 'Flag: High' : contributingSignals.ruleFlag === 'low' ? 'Flag: Low' : 'Flag: None'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Peel Chain Pattern:</span>
                  <strong className={contributingSignals.ruleDetails.peelChainDetected ? 'text-rose-400' : 'text-zinc-500'}>
                    {contributingSignals.ruleDetails.peelChainDetected ? 'DETECTED' : 'Not detected'}
                  </strong>
                </div>
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Rapid Fan-Out:</span>
                  <strong className={contributingSignals.ruleDetails.rapidFanOutDetected ? 'text-rose-400' : 'text-zinc-500'}>
                    {contributingSignals.ruleDetails.rapidFanOutDetected ? 'DETECTED' : 'Not detected'}
                  </strong>
                </div>
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Mixer Proximity (≤2 hops):</span>
                  <strong className={contributingSignals.ruleDetails.mixerProximityDetected ? 'text-rose-400' : 'text-zinc-500'}>
                    {contributingSignals.ruleDetails.mixerProximityDetected ? 'DETECTED' : 'Clean'}
                  </strong>
                </div>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-zinc-800/80 text-[11px] text-zinc-400">
              Heuristic Score: <strong className="text-zinc-200">{contributingSignals.ruleScore}/100</strong>
            </div>
          </div>

          {/* Graph ML */}
          <div className={`p-3.5 rounded-xl border flex flex-col justify-between transition-colors ${
            contributingSignals.mlPrediction === 'illicit'
              ? 'bg-rose-950/20 border-rose-800/50 text-zinc-200'
              : 'bg-emerald-950/20 border-emerald-800/50 text-zinc-200'
          }`}>
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  Graph ML
                </span>
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md uppercase ${
                  contributingSignals.mlPrediction === 'illicit'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                }`}>
                  {contributingSignals.mlPrediction.toUpperCase()}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Illicit Probability:</span>
                  <strong className="text-zinc-200 font-mono">
                    {(contributingSignals.mlConfidence * 100).toFixed(1)}%
                  </strong>
                </div>
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Evaluation Split:</span>
                  <span className="text-emerald-300 font-medium text-[11px] bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/50">
                    Entity-Safe
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-400">
                  <span>Primary Feature:</span>
                  <span className="text-zinc-300 font-mono text-[11px]">
                    {contributingSignals.featureHighlights[0]?.name || 'neighbor_illicit'}
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-zinc-800/80 text-[11px] text-zinc-400">
              Model: <strong className="text-zinc-200">Random Forest + Graph Embeddings</strong>
            </div>
          </div>

          {/* Final Verdict */}
          <div className={`p-4 rounded-xl border-2 flex flex-col justify-between transition-colors ${
            isConfirmed
              ? 'bg-rose-950/25 border-rose-600/70 shadow-lg shadow-rose-950/30'
              : isWatch
              ? 'bg-amber-950/25 border-amber-600/70 shadow-lg shadow-amber-950/30'
              : 'bg-emerald-950/25 border-emerald-600/70 shadow-lg shadow-emerald-950/30'
          }`}>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block mb-1">
                Verdict
              </span>
              <div className="flex items-center gap-2 mb-2">
                {isConfirmed && <AlertOctagon className="w-6 h-6 text-rose-400 shrink-0" />}
                {isWatch && <HelpCircle className="w-6 h-6 text-amber-400 shrink-0" />}
                {isNone && <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />}
                <div>
                  <h3 className={`text-base font-extrabold tracking-tight ${
                    isConfirmed ? 'text-rose-300' : isWatch ? 'text-amber-300' : 'text-emerald-300'
                  }`}>
                    {isConfirmed ? 'CONFIRMED RISK' : isWatch ? 'WATCHLIST' : 'LICIT'}
                  </h3>
                  <span className="text-[11px] text-zinc-400 font-medium">
                    {isConfirmed
                      ? 'Both signals concur'
                      : isWatch
                      ? 'Single signal detected'
                      : 'Neither signal detected'}
                  </span>
                </div>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {isConfirmed
                  ? 'High evidentiary confidence. Both rule heuristics and ML model concur on illicit flow.'
                  : isWatch
                  ? 'Single signal detected. Flagged for observation; secondary confirmation recommended.'
                  : 'Transaction behavior consistent with standard licit activity.'}
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-zinc-800/80 text-[11px] font-mono text-zinc-400 flex items-center justify-between">
              <span>Decision:</span>
              <span className="font-bold text-white">
                {isConfirmed ? 'DUAL_CONFIRM_HIT' : isWatch ? 'SINGLE_SIGNAL_LEAD' : 'CLEAN'}
              </span>
            </div>
          </div>
        </div>

        {/* Contributing Evidence Summary Bar */}
        <div className="bg-[#141418] p-3.5 rounded-xl border border-zinc-800/80">
          <h4 className="text-xs font-semibold text-zinc-300 mb-1.5 flex items-center gap-1.5">
            <span>Evidence Trail:</span>
          </h4>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-zinc-400">
            {contributingSignals.ruleDetails.heuristicsSummary.map((item, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <ChevronRight className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                <span className="text-zinc-300">{item}</span>
              </li>
            ))}
            <li className="flex items-start gap-1.5">
              <ChevronRight className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
              <span className="text-zinc-300">
                ML Model Output: <strong className="text-white">{contributingSignals.mlPrediction.toUpperCase()}</strong> ({(contributingSignals.mlConfidence * 100).toFixed(1)}% confidence)
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
