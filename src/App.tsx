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
import { runPipelineTrace } from './services/analyzer';
import { LIVE_FETCH_TIMEOUT_SECONDS } from './config/constants';
import { TraceResult, WalletNode, WatchlistItem, Complaint } from './types';
import { Search, ShieldAlert, ArrowRight, RefreshCw, FileText, CheckCircle2, AlertTriangle, Database } from 'lucide-react';

export default function App() {
  const [activeCaseId, setActiveCaseId] = useState<string>('case-1');
  const [trace, setTrace] = useState<TraceResult>(CASE_STUDIES[0].trace);
  // Where the current trace came from.
  // 'pipeline'             — real Python pipeline output
  // 'mock'                 — pre-set demonstration case (explicitly labeled)
  // 'pipeline_empty'       — the pipeline answered: nothing exists to trace for
  //                          that address (honest answer, NOT a service failure)
  // 'pipeline_incomplete'  — the pipeline answered with a subgraph but not a
  //                          complete signal set; nothing shown rather than a
  //                          partial result with fabricated signal values
  // 'pipeline_retryable'   — the pipeline is up but the public block explorers
  //                          are rate-limiting / timing out / down (transient;
  //                          nothing concluded about the address — RETRY)
  // 'pipeline_invalid_input' — the pipeline rejected the request as invalid
  //                          (client problem, not a service failure)
  // 'pipeline_unavailable' — backend not reachable/errored; trace state is unchanged (no fabricated data)
  const [dataSource, setDataSource] = useState<
    'pipeline' | 'mock' | 'pipeline_empty' | 'pipeline_incomplete' | 'pipeline_retryable' | 'pipeline_invalid_input' | 'pipeline_unavailable'
  >('mock');
  const [dataNote, setDataNote] = useState<string | null>(null);
  // Machine-readable cause of a transient pipeline failure, used only for the
  // retryable banner: 'rate-limited' | 'timeout' | 'api-error' | 'service-error'
  // | 'unknown'. Kept separate from dataNote so the UI can distinguish a rate
  // limit from a timeout without string-matching the human-readable text.
  const [failureKind, setFailureKind] = useState<string | null>(null);
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
      setDataSource('mock');
      setDataNote('Pre-set demonstration case (mock data). Enter a wallet address to run the real pipeline.');
      setHopFilter(found.trace.hopDepth || 3);
    }
  };

  // Run trace for custom address or complaint — live pipeline only (R7).
  // If the Python service is unavailable, show an honest error; do NOT fall
  // through to mock/fabricated data.
  const handleTraceAddress = async (address: string, customComplaint?: Complaint) => {
    setIsTracing(true);
    try {
      const outcome = await runPipelineTrace(address, hopFilter, customComplaint);
      setActiveCaseId('custom');

      if (outcome.source === 'pipeline') {
        setTrace(outcome.trace);
        setDataSource('pipeline');
        setDataNote(null);
        setFailureKind(null);

        // Auto-add confirmed/watch wallets to watchlist
        const result = outcome.trace;
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
      } else if (outcome.source === 'empty' || outcome.source === 'incomplete') {
        // The pipeline answered, but with nothing that can be drawn: either an
        // honest "no such wallet / no on-chain history / not a valid address"
        // answer ('empty'), or a subgraph without a complete signal set
        // ('incomplete'). Neither is a service failure, so neither may be shown
        // as "pipeline unavailable", and no trace is fabricated to fill the gap —
        // the note explains which case it is while the previous view stays on screen.
        setDataSource(outcome.source === 'empty' ? 'pipeline_empty' : 'pipeline_incomplete');
        setDataNote(`${outcome.note} No new trace data is shown; the previous view remains on screen unchanged.`);
      } else if (outcome.source === 'retryable') {
        // The pipeline is REACHABLE; the public block explorers could not answer
        // (rate-limited / timed out / down). This is transient and says nothing
        // about the address, so it is never shown as "invalid address" or as a
        // "no such wallet" conclusion — the user is told to RETRY.
        setDataSource('pipeline_retryable');
        setFailureKind(outcome.kind);
        setDataNote(`${outcome.note} No new trace data is shown; the previous view remains on screen unchanged.`);
      } else if (outcome.source === 'invalid_input') {
        // The pipeline REJECTED the request (bad input) — a client problem, not
        // a service failure and not a claim about the chain.
        setDataSource('pipeline_invalid_input');
        setFailureKind(null);
        setDataNote(outcome.note);
      } else {
        setDataSource('pipeline_unavailable');
        setFailureKind(null);
        setDataNote(outcome.note);
      }
    } catch (err) {
      console.error('Tracing error:', err);
      setDataSource('pipeline_unavailable');
      setFailureKind(null);
      setDataNote('Unexpected error contacting the pipeline — check the browser console.');
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

        {/* Live-trace in-progress status — real state only, no fabricated progress. */}
        {isTracing && (
          <div className="flex items-center gap-2 text-xs text-sky-300 bg-sky-950/30 border border-sky-800/50 rounded-xl px-3 py-2">
            <RefreshCw className="w-3.5 h-3.5 animate-spin shrink-0" />
            <span>
              Tracing live wallet — this can take up to {LIVE_FETCH_TIMEOUT_SECONDS}s. The previous view
              (if any) remains on screen until the pipeline responds or the request times out.
            </span>
          </div>
        )}

        {/* Data source banner: only shown for live pipeline results or error notices.
            Each failure state gets its OWN banner: a rate-limited/timed-out lookup is
            transient and retryable, and must not be rendered as "invalid address",
            "no such wallet", or "service down" (see AGENTS.md: never let one honest
            failure mode masquerade as another). */}
        {dataSource !== 'mock' && (
          <div className={`p-3 rounded-2xl border text-xs flex items-start gap-2 ${
            dataSource === 'pipeline'
              ? 'bg-teal-950/30 border-teal-800/60 text-teal-300'
              : dataSource === 'pipeline_retryable'
                ? 'bg-amber-950/40 border-amber-700/60 text-amber-300'
                : dataSource === 'pipeline_unavailable'
                  ? 'bg-rose-950/40 border-rose-700/60 text-rose-300'
                  : 'bg-amber-950/30 border-amber-800/60 text-amber-300'
          }`}>
            <Database className="w-4 h-4 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <div className="font-bold uppercase tracking-wider">
                {dataSource === 'pipeline'
                  ? 'Live pipeline output — real subgraph, rules, learned signal and correlation'
                  : dataSource === 'pipeline_empty'
                    ? 'Pipeline answered — no trace exists for this address (no fabrication)'
                    : dataSource === 'pipeline_incomplete'
                      ? '⚠ Pipeline answered with an incomplete signal set — nothing shown (no fabrication)'
                      : dataSource === 'pipeline_retryable'
                        ? `⚠ Block explorers unavailable right now (${failureKind ?? 'transient failure'}) — nothing was concluded about this address; RETRY`
                        : dataSource === 'pipeline_invalid_input'
                          ? '⚠ Request rejected as invalid — nothing was looked up (not a service failure)'
                          : '⚠ Pipeline unavailable — no trace data shown (no fabrication)'}
              </div>
              <p className="opacity-80">
                {dataNote ?? (dataSource === 'pipeline'
                  ? 'Evaluated for the reported wallet; subgraph members are shown structurally (Elliptic carries no BTC amounts, so monetary fields are 0, not fabricated).'
                  : 'Start the Python service: cd backend && uvicorn ledgr.service:app --reload — then re-submit the address.')}
              </p>
            </div>
          </div>
        )}

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
          <span className="text-amber-500/80">
            Learned signal validated only on the time-respecting entity-safe split (test time-steps 45–49); wallets outside that regime are not validated — &quot;confirmed&quot; means two imperfect signals agree, not proof of guilt.
          </span>
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
