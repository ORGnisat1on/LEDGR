/**
 * LEDGR
 */

import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SignalCorrelationCard } from './components/SignalCorrelationCard';
import { AttributionCard } from './components/AttributionCard';
import { GraphVisualizer } from './components/GraphVisualizer';
import { NodeInspector } from './components/NodeInspector';
import { ComplaintIntakeModal } from './components/ComplaintIntakeModal';
import { WatchlistMonitor } from './components/WatchlistMonitor';
import { BulkConvergenceView } from './components/BulkConvergenceView';
import { MethodologyModal } from './components/MethodologyModal';
import { InvestigationReportModal } from './components/InvestigationReportModal';

import { CASE_STUDIES, INITIAL_WATCHLIST } from './data/mockCases';
import { ForensicEngine } from './services/analyzer';
import { TraceResult, WalletNode, WatchlistItem, Complaint } from './types';
import { Search, ShieldAlert, ArrowRight, RefreshCw, FileText, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function App() {
  const [activeCaseId, setActiveCaseId] = useState<string>('case-1');
  const [trace, setTrace] = useState<TraceResult>(CASE_STUDIES[0].trace);
  const [selectedNode, setSelectedNode] = useState<WalletNode | null>(null);
  const [hopFilter, setHopFilter] = useState<number>(4);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isTracing, setIsTracing] = useState<boolean>(false);

  // Watchlist state
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>(INITIAL_WATCHLIST);

  // Modal open states
  const [isIntakeOpen, setIsIntakeOpen] = useState<boolean>(false);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState<boolean>(false);
  const [isConvergenceOpen, setIsConvergenceOpen] = useState<boolean>(false);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState<boolean>(false);
  const [isReportOpen, setIsReportOpen] = useState<boolean>(false);

  // Default selected node to root suspect node whenever trace changes
  useEffect(() => {
    if (trace.nodes.length > 0) {
      const root = trace.nodes.find(n => n.type === 'suspect_root') || trace.nodes[0];
      setSelectedNode(root);
    }
  }, [trace]);

  // Load a pre-set case study
  const handleSelectCase = async (caseId: string) => {
    setActiveCaseId(caseId);
    const found = CASE_STUDIES.find(c => c.id === caseId);
    if (found) {
      setTrace(found.trace);
      setHopFilter(found.trace.hopDepth || 3);
    }
  };

  // Run trace for custom address or complaint
  const handleTraceAddress = async (address: string, customComplaint?: Complaint) => {
    setIsTracing(true);
    try {
      const result = await ForensicEngine.traceAddress(address, hopFilter, customComplaint);
      setTrace(result);
      setActiveCaseId('custom');

      // Auto add confirmed/watch wallets to watchlist if not present
      if (result.verdict !== 'none') {
        const exists = watchlist.some(w => w.address.toLowerCase() === address.toLowerCase());
        if (!exists) {
          const newItem: WatchlistItem = {
            address: result.targetAddress,
            label: result.complaint?.victimName ? `${result.complaint.victimName} Suspect` : 'Reported Suspect Wallet',
            ackNumber: result.complaint?.ackNumber || `NCRP-2026-IN-${Math.floor(10000 + Math.random() * 90000)}`,
            victimName: result.complaint?.victimName || 'Citizen Complainant',
            dateAdded: new Date().toISOString().substring(0, 10),
            verdict: result.verdict,
            category: result.complaint?.scamCategory || 'Cyber Financial Fraud',
            amountInr: result.complaint?.amountInr || 1500000
          };
          setWatchlist(prev => [newItem, ...prev]);
        }
      }
    } catch (err) {
      console.error("Tracing error:", err);
    } finally {
      setIsTracing(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    handleTraceAddress(searchQuery.trim());
  };

  const unconfirmedAlertCount = watchlist.filter(w => !!w.unconfirmedAlert).length;

  return (
    <div className="min-h-screen bg-[#050505] text-[#ededed] flex flex-col antialiased">
      {/* Top Header */}
      <Header
        activeCaseId={activeCaseId}
        onSelectCase={handleSelectCase}
        onOpenIntake={() => setIsIntakeOpen(true)}
        onOpenWatchlist={() => setIsWatchlistOpen(true)}
        onOpenConvergence={() => setIsConvergenceOpen(true)}
        onOpenMethodology={() => setIsMethodologyOpen(true)}
        onOpenReport={() => setIsReportOpen(true)}
        unconfirmedAlertCount={unconfirmedAlertCount}
      />

      {/* Main Container */}
      <main className="max-w-7xl w-full mx-auto px-4 py-4 space-y-4 flex-1">
        {/* Case Switcher & Search Bar */}
        <div className="bg-[#0e0e12] p-3.5 rounded-2xl border border-zinc-800/80 shadow-lg shadow-black/20 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Quick Case Study Buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-zinc-400 mr-1 uppercase tracking-wider">
              Presets:
            </span>
            {CASE_STUDIES.map(cs => {
              const isActive = activeCaseId === cs.id;
              return (
                <button
                  key={cs.id}
                  onClick={() => handleSelectCase(cs.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer ${
                    isActive
                      ? 'bg-zinc-800 text-white border border-zinc-700 shadow-xs'
                      : 'bg-[#141418] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 border border-zinc-800/80'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${
                    cs.trace.verdict === 'confirmed' ? 'bg-rose-500 shadow-xs shadow-rose-500/50' : 'bg-emerald-400 shadow-xs shadow-emerald-400/50'
                  }`} />
                  <span>{cs.id === 'case-1' ? 'Pig Butchering' : cs.id === 'case-2' ? 'Task Scam' : cs.id === 'case-3' ? 'Ransomware' : 'Licit Control'}</span>
                </button>
              );
            })}
          </div>

          {/* Search / Custom Address Bar */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-1.5 min-w-[300px]">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Trace Bitcoin address..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-[#141418] border border-zinc-800 rounded-xl focus:border-indigo-500 focus:outline-none font-mono text-zinc-200 placeholder-zinc-500"
              />
            </div>
            <button
              type="submit"
              disabled={isTracing}
              className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-950/40 flex items-center gap-1 transition-colors disabled:opacity-60 shrink-0 cursor-pointer"
            >
              {isTracing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <span>Analyze</span>
              )}
            </button>
          </form>
        </div>

        {/* Active Investigation Case Banner */}
        <div className="bg-gradient-to-r from-[#121217] via-[#161622] to-[#121217] text-white p-4 rounded-2xl shadow-xl border border-zinc-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-mono font-bold bg-indigo-500/10 text-indigo-300 px-2.5 py-0.5 rounded-md border border-indigo-500/30">
                {trace.complaint?.ackNumber || 'CASE'}
              </span>
              <span className="text-xs font-medium text-zinc-400">
                {trace.complaint?.victimState}
              </span>
              <span className="text-[11px] font-semibold text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-md border border-amber-500/30">
                {trace.complaint?.scamCategory}
              </span>
            </div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <span>{trace.complaint?.victimName}</span>
              <span className="text-xs font-normal text-zinc-400">
                (₹{(trace.complaint?.amountInr || 0).toLocaleString('en-IN')} / {trace.complaint?.amountBtc} BTC)
              </span>
            </h2>
            <div className="text-xs font-mono text-zinc-400 truncate max-w-2xl">
              Target: <span className="text-sky-400 select-all font-semibold">{trace.targetAddress}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setIsReportOpen(true)}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-indigo-950/40 transition-colors cursor-pointer"
            >
              <FileText className="w-4 h-4 text-amber-300" />
              <span>Dossier</span>
            </button>
          </div>
        </div>

        {/* Dual Column Workspace Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
          {/* Left Column (2/3 width): Interactive Subgraph & Correlation Card */}
          <div className="lg:col-span-2 space-y-4">
            {/* Interactive Graph Visualizer */}
            <GraphVisualizer
              trace={trace}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
              hopFilter={hopFilter}
              onHopFilterChange={setHopFilter}
            />

            {/* Core Load-Bearing Correlation Engine Card */}
            <SignalCorrelationCard trace={trace} />
          </div>

          {/* Right Column (1/3 width): VASP Attribution & Node Inspector */}
          <div className="space-y-4">
            {/* Module 5 VASP Attribution Card */}
            <AttributionCard
              trace={trace}
              onOpenReport={() => setIsReportOpen(true)}
            />

            {/* Wallet Node Deep Dive Inspector */}
            <NodeInspector
              node={selectedNode}
              edges={trace.edges}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 bg-[#09090b] py-3 px-4 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-2 text-zinc-500 font-mono text-[11px]">
          <span className="font-bold text-zinc-400">LEDGR</span>
          <span>Dual-Signal Correlation & Graph Analytics</span>
        </div>
      </footer>

      {/* Modals */}
      <ComplaintIntakeModal
        isOpen={isIntakeOpen}
        onClose={() => setIsIntakeOpen(false)}
        onLoadCase={handleSelectCase}
        onSubmitCustom={c => handleTraceAddress(c.suspectAddress, c)}
        onRunBatch={() => {
          setIsConvergenceOpen(true);
        }}
      />

      <WatchlistMonitor
        isOpen={isWatchlistOpen}
        onClose={() => setIsWatchlistOpen(false)}
        watchlist={watchlist}
        onTraceAddress={addr => handleTraceAddress(addr)}
      />

      <BulkConvergenceView
        isOpen={isConvergenceOpen}
        onClose={() => setIsConvergenceOpen(false)}
        onTraceAddress={addr => handleTraceAddress(addr)}
      />

      <MethodologyModal
        isOpen={isMethodologyOpen}
        onClose={() => setIsMethodologyOpen(false)}
      />

      <InvestigationReportModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        trace={trace}
      />
    </div>
  );
}
