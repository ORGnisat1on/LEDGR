import React, { useState } from 'react';
import { X, Copy, Check, ExternalLink, ShieldAlert, Cpu, ListFilter, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import { WalletNode, TransactionEdge } from '../types';

interface NodeInspectorProps {
  node: WalletNode | null;
  edges: TransactionEdge[];
  onClose: () => void;
}

export const NodeInspector: React.FC<NodeInspectorProps> = ({ node, edges, onClose }) => {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'features' | 'transactions'>('overview');

  if (!node) return null;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const incomingTxs = [...edges.filter(e => e.to === node.id)].sort((a, b) => b.amountBtc - a.amountBtc);
  const outgoingTxs = [...edges.filter(e => e.from === node.id)].sort((a, b) => b.amountBtc - a.amountBtc);

  const isConfirmed = node.verdict === 'confirmed';
  const isWatch = node.verdict === 'watch';

  return (
    <div className="bg-[#0e0e12] rounded-2xl border border-zinc-800/80 shadow-lg shadow-black/20 overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 bg-[#121217] text-white flex items-center justify-between border-b border-zinc-800/80">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
            isConfirmed ? 'bg-rose-500 animate-pulse shadow-sm shadow-rose-500/50' : isWatch ? 'bg-amber-400' : 'bg-emerald-400'
          }`} />
          <div className="truncate">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Node Profile
            </h3>
            <p className="text-sm font-bold text-white truncate">
              {node.label}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Address Bar */}
      <div className="px-4 py-2.5 bg-[#141418] border-b border-zinc-800/80 flex items-center justify-between gap-2">
        <div className="font-mono text-xs text-sky-400 truncate select-all font-semibold">
          {node.id}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => handleCopy(node.id)}
            className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-zinc-200 text-xs flex items-center gap-1 cursor-pointer"
            title="Copy address"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <a
            href={`https://blockstream.info/address/${node.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-zinc-200 text-xs"
            title="View in Blockstream.info explorer"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800/80 text-xs font-medium bg-[#0e0e12]">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex-1 py-2 text-center border-b-2 transition-colors cursor-pointer ${
            activeTab === 'overview'
              ? 'border-indigo-500 text-indigo-300 font-bold bg-[#141419]'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('features')}
          className={`flex-1 py-2 text-center border-b-2 transition-colors cursor-pointer ${
            activeTab === 'features'
              ? 'border-indigo-500 text-indigo-300 font-bold bg-[#141419]'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Features
        </button>
        <button
          onClick={() => setActiveTab('transactions')}
          className={`flex-1 py-2 text-center border-b-2 transition-colors cursor-pointer ${
            activeTab === 'transactions'
              ? 'border-indigo-500 text-indigo-300 font-bold bg-[#141419]'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Ledger ({incomingTxs.length + outgoingTxs.length})
        </button>
      </div>

      {/* Content Area */}
      <div className="p-4 overflow-y-auto max-h-[380px] text-xs space-y-4 text-zinc-300">
        {activeTab === 'overview' && (
          <>
            {/* Quick Metrics */}
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400 text-[10px] block">Hop from Suspect Root</span>
                <span className="font-bold text-white text-sm">
                  {node.hop === 0 ? '0 (Victim Root)' : `${node.hop} Hops`}
                </span>
              </div>
              <div className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400 text-[10px] block">Total Received</span>
                <span className="font-bold text-emerald-400 text-sm font-mono">
                  {node.totalReceivedBtc} BTC
                </span>
              </div>
              <div className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400 text-[10px] block">Total Sent</span>
                <span className="font-bold text-rose-400 text-sm font-mono">
                  {node.totalSentBtc} BTC
                </span>
              </div>
              <div className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400 text-[10px] block">Current Balance</span>
                <span className="font-bold text-amber-400 text-sm font-mono">
                  {node.balanceBtc} BTC
                </span>
              </div>
            </div>

            {/* Signal Status */}
            <div className="p-3 bg-[#141418] rounded-xl border border-zinc-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-300">Classification Verdict:</span>
                <span className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] ${
                  isConfirmed ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : isWatch ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                }`}>
                  {node.verdict}
                </span>
              </div>
              <div className="flex items-center justify-between text-zinc-400">
                <span>Rule-based Heuristics:</span>
                <strong className={node.ruleFlag === 'high' ? 'text-rose-400' : 'text-zinc-300'}>
                  Flag: {node.ruleFlag.toUpperCase()}
                </strong>
              </div>
              <div className="flex items-center justify-between text-zinc-400">
                <span>Learned ML Prediction:</span>
                <strong className={node.mlPrediction === 'illicit' ? 'text-rose-400' : 'text-emerald-400'}>
                  {node.mlPrediction.toUpperCase()} ({(node.mlScore * 100).toFixed(1)}%)
                </strong>
              </div>
            </div>

            {/* Heuristics list */}
            {node.ruleReasons.length > 0 && (
              <div>
                <span className="font-semibold text-zinc-300 block mb-1">Triggered Heuristics:</span>
                <ul className="list-disc list-inside space-y-1 text-zinc-400 pl-1">
                  {node.ruleReasons.map((reason, idx) => (
                    <li key={idx} className="text-zinc-300">{reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Attribution note if present */}
            {node.attribution && (
              <div className="p-3 bg-indigo-950/30 rounded-xl border border-indigo-800/50">
                <span className="font-bold text-indigo-300 block text-[11px] mb-1">
                  Entity Attribution: {node.attribution.name}
                </span>
                <div className="text-[11px] text-zinc-300 space-y-0.5">
                  <div>Source: {node.attribution.sourceName}</div>
                  <div>Confidence Tier: <strong className="font-mono text-indigo-300">{node.attribution.confidenceTier}</strong></div>
                  {node.attribution.complianceEmail && (
                    <div>Grievance Contact: <span className="font-mono text-sky-400">{node.attribution.complianceEmail}</span></div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'features' && (
          <div className="space-y-3">
            <p className="text-[11px] text-zinc-400">
              Selected handcrafted topological & neighborhood features from the 166-dimensional Elliptic benchmark representation:
            </p>
            <div className="space-y-1.5 font-mono text-[11px]">
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">in_degree (raw)</span>
                <span className="font-bold text-white">{incomingTxs.length}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">out_degree (raw)</span>
                <span className="font-bold text-white">{outgoingTxs.length}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">ml_node_illicit_score</span>
                <span className="font-bold text-rose-400">{node.mlScore.toFixed(4)}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">first_seen_timestamp</span>
                <span className="text-zinc-300">{node.firstSeen}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">last_seen_timestamp</span>
                <span className="text-zinc-300">{node.lastSeen}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#141418] rounded-xl border border-zinc-800/80">
                <span className="text-zinc-400">train_test_split_regime</span>
                <span className="text-emerald-400 font-bold">Entity-Safe Held-Out</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="space-y-3">
            {incomingTxs.length > 0 && (
              <div>
                <span className="font-semibold text-zinc-300 text-xs flex items-center gap-1 mb-1">
                  <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-400" />
                  Incoming Transactions ({incomingTxs.length})
                </span>
                <div className="space-y-1.5">
                  {incomingTxs.map(tx => (
                    <div key={tx.id} className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80 text-[11px]">
                      <div className="flex items-center justify-between font-mono font-bold text-emerald-400">
                        <span>+{tx.amountBtc} BTC</span>
                        <span className="text-zinc-400 font-normal text-[10px]">{tx.timestamp}</span>
                      </div>
                      <div className="text-zinc-400 truncate font-mono text-[10px] mt-0.5">
                        TxID: {tx.txHash}
                      </div>
                      {tx.note && <div className="text-rose-400 font-medium text-[10px] mt-0.5">{tx.note}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {outgoingTxs.length > 0 && (
              <div>
                <span className="font-semibold text-zinc-300 text-xs flex items-center gap-1 mb-1">
                  <ArrowUpRight className="w-3.5 h-3.5 text-rose-400" />
                  Outgoing Transactions ({outgoingTxs.length})
                </span>
                <div className="space-y-1.5">
                  {outgoingTxs.map(tx => (
                    <div key={tx.id} className="p-2.5 bg-[#141418] rounded-xl border border-zinc-800/80 text-[11px]">
                      <div className="flex items-center justify-between font-mono font-bold text-rose-400">
                        <span>-{tx.amountBtc} BTC</span>
                        <span className="text-zinc-400 font-normal text-[10px]">{tx.timestamp}</span>
                      </div>
                      <div className="text-zinc-400 truncate font-mono text-[10px] mt-0.5">
                        TxID: {tx.txHash}
                      </div>
                      {tx.note && <div className="text-rose-400 font-medium text-[10px] mt-0.5">{tx.note}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
