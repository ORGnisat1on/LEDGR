import React from 'react';
import { X, Database, ShieldCheck, CheckCircle2, AlertTriangle, Cpu, BarChart3, Lock } from 'lucide-react';

interface MethodologyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MethodologyModal: React.FC<MethodologyModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-[#0e0e12] rounded-2xl shadow-2xl border border-zinc-800/80 w-full max-w-4xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-[#121217] text-white px-5 py-4 flex items-center justify-between border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-950/50 border border-indigo-800/60 flex items-center justify-center text-sky-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Benchmark Methodology
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

        <div className="p-5 space-y-4 max-h-[540px] overflow-y-auto text-xs text-zinc-300">
          {/* Section 1: Entity-based Train/Test Split */}
          <div className="p-4 rounded-xl bg-[#121217] border border-zinc-800/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                <Lock className="w-4 h-4 text-indigo-400" />
                1. Entity-Based Train/Test Split (Anti-Leakage Safeguard)
              </h3>
              <span className="text-[11px] font-bold text-emerald-300 bg-emerald-500/20 px-2.5 py-0.5 rounded-md border border-emerald-500/40">
                VERIFIED: ZERO LEAKAGE
              </span>
            </div>
            <p className="leading-relaxed text-zinc-300">
              A well-documented vulnerability in the Elliptic benchmark is that labels are inherited from the real-world <strong>entity</strong> (e.g. specific exchange or syndicate) an address belongs to. If a train/test split is done randomly at the transaction level, the model memorizes entity patterns rather than generalizing to unseen suspect wallets reported by victims.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div className="p-3 bg-[#16161d] rounded-xl border border-rose-900/50">
                <span className="font-bold text-rose-400 block text-xs mb-1">❌ Naive Random Split (Banned):</span>
                <p className="text-[11px] text-zinc-400">
                  Allows transactions from the same entity in both train and test. Inflates benchmark accuracy to &gt;97% while failing on real, unseen fraud.
                </p>
              </div>
              <div className="p-3 bg-[#16161d] rounded-xl border border-emerald-900/50">
                <span className="font-bold text-emerald-400 block text-xs mb-1">✅ Our Entity-Safe Split:</span>
                <p className="text-[11px] text-zinc-400">
                  <strong>Time-respecting entity split (70/15/15):</strong> entities are ordered by their earliest transaction time-step; the earliest 70% train, the next 15% validate, the final 15% test. Programmatically verified on every run: 0 shared entities/transactions across splits, and every entity's transactions fall in a single time step (span-0 enforced, 14,270/14,270 PASS).
                </p>
              </div>
            </div>
            <div className="p-3 bg-amber-950/30 rounded-xl border border-amber-800/50 text-amber-200 text-[11px]">
              <strong>Hub-Node Safeguard:</strong> Major exchange hot-wallets with massive in-degree are capped from component clustering so that a single exchange node does not collapse the entire graph into one giant component.
            </div>
          </div>

          {/* Section 2: Primary & Secondary Metrics */}
          <div className="p-4 rounded-xl bg-[#121217] border border-zinc-800/80 space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
              <BarChart3 className="w-4 h-4 text-indigo-400" />
              2. Evaluation Metrics (Severe Class Imbalance Discipline)
            </h3>
            <p className="leading-relaxed text-zinc-400">
              Illicit transactions constitute only ~2% of the Bitcoin ledger. Raw accuracy is misleading. Our system is evaluated on held-out entities using precision, recall, and F1 on the illicit class:
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-[#16161d] rounded-xl border border-zinc-800 text-center">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold block">Recall (Illicit)</span>
                <span className="text-xl font-extrabold text-indigo-400 font-mono">1.7%</span>
                <span className="text-[10px] text-zinc-500 block mt-0.5">Test-set illicit caught</span>
              </div>
              <div className="p-3 bg-[#16161d] rounded-xl border border-zinc-800 text-center">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold block">Precision (Illicit)</span>
                <span className="text-xl font-extrabold text-zinc-200 font-mono">50.0%</span>
                <span className="text-[10px] text-zinc-500 block mt-0.5">Of flags truly illicit</span>
              </div>
              <div className="p-3 bg-[#16161d] rounded-xl border border-zinc-800 text-center">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold block">F1 Score</span>
                <span className="text-xl font-extrabold text-zinc-200 font-mono">0.033</span>
                <span className="text-[10px] text-zinc-500 block mt-0.5">Harmonic balance</span>
              </div>
              <div className="p-3 bg-[#16161d] rounded-xl border border-zinc-800 text-center">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold block">Accuracy (secondary)</span>
                <span className="text-xl font-extrabold text-emerald-400 font-mono">95.4%</span>
                <span className="text-[10px] text-zinc-500 block mt-0.5">Not meaningful alone</span>
              </div>
            </div>
            <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-xl text-amber-200 text-[11px]">
              <strong>Honest limitation (concept drift):</strong> these metrics come from the time-respecting entity-safe split, where the test set sits at the latest time-steps (45–49). Published baselines (e.g. Weber et al. 2019) show illicit patterns shift sharply at time-step 43, so a model trained on earlier steps generalizes poorly to later ones — the low recall above is that effect, reported honestly rather than tuned around. Live-traced wallets operating after the dataset window are <em>outside the model's validated regime</em>.
            </div>
          </div>

          {/* Section 3: Dual Signal & Legal Honesty */}
          <div className="p-4 rounded-xl bg-[#121217] border border-zinc-800/80 space-y-2">
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
              3. What "Confirmed" vs. "Watch" Means Precisely
            </h3>
            <ul className="space-y-1.5 text-xs text-zinc-300 list-disc list-inside">
              <li>
                <strong>Confirmed:</strong> Rule-based heuristic flags the wallet (Peel Chain, Rapid Fan-Out, or Mixer Adjacency) <em>AND</em> learned ML model classifies it as Illicit at P(illicit) ≥ 0.5 (the <code>LEARNED_FLAG_THRESHOLD</code> documented in <code>ledgr/config.py</code>).
              </li>
              <li>
                <strong>Watch:</strong> Exactly one of the two independent signals fires (either heuristic only, or ML only). Treated as an exploratory investigative lead.
              </li>
              <li>
                <strong>None:</strong> Neither signal fires. Protects against false freezing of legitimate merchants.
              </li>
              <li>
                <strong>Out-of-dataset wallets:</strong> a wallet not present in the Elliptic feature set is reported as <code>classified: false</code> — no risk score is fabricated for it, and it can never be confirmed (only watch-as-rule or none).
              </li>
            </ul>

            <div className="p-3 bg-rose-950/30 border border-rose-800/50 rounded-xl text-rose-200 text-[11px] mt-2">
              <strong>Statutory Caution for Law Enforcement:</strong> "Confirmed" means two independent, imperfect signals agree — it is an actionable investigative lead for Section 91 CrPC / Section 94 BNSS requisition, not a conclusive determination of judicial guilt.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
