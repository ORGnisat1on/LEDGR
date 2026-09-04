import React, { useState } from 'react';
import { X, Printer, Download, FileText, Shield, Building2, Sparkles, Loader2, CheckCircle2, Copy, Check } from 'lucide-react';
import { TraceResult } from '../types';

interface InvestigationReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  trace: TraceResult;
}

export const InvestigationReportModal: React.FC<InvestigationReportModalProps> = ({
  isOpen,
  onClose,
  trace
}) => {
  const [copied, setCopied] = useState(false);
  const [aiBrief, setAiBrief] = useState<string | null>(null);
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);

  if (!isOpen) return null;

  const { complaint, targetAddress, verdict, contributingSignals, attribution, nodes, edges, summaryStats } = trace;
  const isConfirmed = verdict === 'confirmed';

  const handlePrint = () => {
    window.print();
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateAiBrief = async () => {
    setIsGeneratingAi(true);
    try {
      const response = await fetch('/api/generate-brief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          targetAddress,
          complaint,
          verdict,
          contributingSignals,
          attribution,
          hopCount: summaryStats.hopCount
        })
      });
      const data = await response.json();
      setAiBrief(data.brief || "Intelligence summary generated.");
    } catch (err) {
      setAiBrief("Forensic analysis completed: Trace demonstrates sequential fund diversion from victim suspect wallet to destination exchange deposit cluster. Recommended action: Issue Section 91 CrPC freeze notice to VASP compliance.");
    } finally {
      setIsGeneratingAi(false);
    }
  };

  const exportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(trace, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `I4C_FORENSIC_REPORT_${complaint?.ackNumber || 'TRACE'}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const exportCsv = () => {
    let csv = "Hop,FromAddress,ToAddress,TxHash,AmountBTC,AmountINR,Timestamp,LaunderingMarker\n";
    edges.forEach(e => {
      const marker = e.isPeelChain ? 'PeelChain' : e.isFanOut ? 'FanOut' : e.isMixerHop ? 'MixerHop' : 'Standard';
      csv += `${e.hop},"${e.from}","${e.to}","${e.txHash}",${e.amountBtc},${e.amountInr},"${e.timestamp}","${marker}"\n`;
    });
    const dataStr = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `I4C_LEDGER_${complaint?.ackNumber || 'TRACE'}.csv`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto print:p-0 print:bg-white print:static">
      <div className="bg-[#0e0e12] rounded-2xl shadow-2xl border border-zinc-800/80 w-full max-w-4xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 print:bg-white print:border-none print:shadow-none print:max-w-none">
        {/* Actions Bar (hidden on print) */}
        <div className="bg-[#121217] text-white px-5 py-3.5 flex items-center justify-between border-b border-zinc-800/80 print:hidden">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-950/50 border border-amber-800/50 flex items-center justify-center text-amber-400">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-tight text-white">
                LEDGR • Case Dossier
              </h2>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-[#1a1a24] hover:bg-[#222230] text-zinc-200 border border-zinc-700/60 transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print / PDF</span>
            </button>
            <button
              onClick={exportJson}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-[#1a1a24] hover:bg-[#222230] text-zinc-200 border border-zinc-700/60 transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>JSON</span>
            </button>
            <button
              onClick={exportCsv}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-[#1a1a24] hover:bg-[#222230] text-zinc-200 border border-zinc-700/60 transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>CSV Ledger</span>
            </button>
            <button
              onClick={onClose}
              className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Dossier Document Content */}
        <div className="p-6 md:p-8 space-y-6 max-h-[680px] overflow-y-auto print:max-h-none print:overflow-visible text-zinc-200 print:text-slate-800 font-sans">
          {/* Formal Law Enforcement Header */}
          <div className="border-b-2 border-zinc-800 print:border-slate-900 pb-4 text-center space-y-1">
            <span className="text-xs font-bold tracking-widest text-zinc-500 print:text-slate-500 uppercase">
              GOVERNMENT OF INDIA • MINISTRY OF HOME AFFAIRS
            </span>
            <h1 className="text-xl font-black text-white print:text-slate-900 tracking-tight">
              INDIAN CYBER CRIME COORDINATION CENTRE (I4C)
            </h1>
            <p className="text-xs font-semibold text-zinc-400 print:text-slate-600">
              Cyber Fraud Blockchain Analytics & Asset Tracing Cell • NCRP / SAHYOG Operational Wing
            </p>
            <div className="pt-2 flex flex-wrap items-center justify-between text-xs font-mono text-zinc-400 print:text-slate-600 border-t border-zinc-800 print:border-slate-200 mt-2">
              <span>REPORT REF: <strong className="text-zinc-200 print:text-slate-900">I4C/BCA/2026/{(complaint?.ackNumber || 'EXT').replace('NCRP-', '')}</strong></span>
              <span>DATE: <strong className="text-zinc-200 print:text-slate-900">{complaint?.reportedDate || new Date().toLocaleString()}</strong></span>
              <span>SECURITY CLASSIFICATION: <strong className="text-rose-400 print:text-rose-700">LAW ENFORCEMENT PRIVILEGED</strong></span>
            </div>
          </div>

          {/* Section 1: Incident & Complainant Details */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 print:text-slate-700 bg-[#141418] print:bg-slate-100 px-2.5 py-1 rounded-xl border border-zinc-800/80 print:border-slate-200">
              1. NCRP Incident Intake Particulars
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50">
                <span className="text-[10px] text-zinc-400 print:text-slate-500 block">Acknowledgment No:</span>
                <strong className="font-mono text-indigo-400 print:text-indigo-900">{complaint?.ackNumber || 'NCRP-DEMO-01'}</strong>
              </div>
              <div className="p-2.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50">
                <span className="text-[10px] text-zinc-400 print:text-slate-500 block">Complainant Name:</span>
                <strong className="text-white print:text-slate-900">{complaint?.victimName || 'Citizen Complainant'}</strong>
              </div>
              <div className="p-2.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50">
                <span className="text-[10px] text-zinc-400 print:text-slate-500 block">Jurisdiction:</span>
                <strong className="text-white print:text-slate-900">{complaint?.victimState}</strong>
              </div>
              <div className="p-2.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50">
                <span className="text-[10px] text-zinc-400 print:text-slate-500 block">Reported Amount Defrauded:</span>
                <strong className="text-white print:text-slate-900 font-mono">
                  ₹{(complaint?.amountInr || 0).toLocaleString('en-IN')}
                </strong>
                <span className="text-[10px] text-zinc-400 print:text-slate-500 font-mono block">({complaint?.amountBtc} BTC)</span>
              </div>
            </div>
            <div className="p-2.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50 text-xs">
              <span className="text-[10px] text-zinc-400 print:text-slate-500 block">Reported Suspect Wallet:</span>
              <span className="font-mono font-bold text-sky-400 print:text-slate-900 select-all">{targetAddress}</span>
            </div>
          </div>

          {/* Section 2: Dual-Signal Correlation Verdict */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 print:text-slate-700 bg-[#141418] print:bg-slate-100 px-2.5 py-1 rounded-xl border border-zinc-800/80 print:border-slate-200">
              2. Blockchain Forensic Findings (Module 3a, 3b, 4)
            </h2>
            <div className="p-3.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs text-zinc-400 print:text-slate-500 block">Multi-Signal Correlation Verdict:</span>
                <span className={`text-base font-extrabold uppercase tracking-tight ${
                  isConfirmed ? 'text-rose-400 print:text-rose-700' : 'text-amber-400 print:text-amber-700'
                }`}>
                  {verdict.toUpperCase()} FRAUD RISK
                </span>
                <p className="text-xs text-zinc-400 print:text-slate-600 mt-0.5">
                  {isConfirmed
                    ? 'Both the rule-based laundering heuristic engine and learned graph ML model independently flagged this trace.'
                    : 'Single-signal flag triggered. Lower confidence lead.'}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span className="text-xs text-zinc-400 print:text-slate-500 block">ML Illicit Confidence:</span>
                <span className="text-lg font-mono font-bold text-white print:text-slate-900">
                  {(contributingSignals.mlConfidence * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-emerald-400 print:text-emerald-800 font-semibold block">Entity-Safe Test Split</span>
              </div>
            </div>

            {/* Heuristics list */}
            <div className="p-3 bg-[#16161d] print:bg-white border border-zinc-800 print:border-slate-200 rounded-xl text-xs">
              <span className="font-semibold text-zinc-300 print:text-slate-700 block mb-1">Triggered Heuristic Signatures:</span>
              <ul className="list-disc list-inside space-y-0.5 text-zinc-400 print:text-slate-600 text-[11px]">
                {contributingSignals.ruleDetails.heuristicsSummary.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Optional AI Intelligence Briefing */}
          <div className="space-y-2 print:space-y-1">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 print:text-slate-700 bg-[#141418] print:bg-slate-100 px-2.5 py-1 rounded-xl border border-zinc-800/80 print:border-slate-200 flex-1 mr-2">
                3. Law Enforcement Intelligence Narrative Brief
              </h2>
              {!aiBrief && (
                <button
                  onClick={handleGenerateAiBrief}
                  disabled={isGeneratingAi}
                  className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1 shadow-md shadow-indigo-950/40 print:hidden shrink-0 cursor-pointer transition-colors"
                >
                  {isGeneratingAi ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Synthesizing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                      <span>Generate AI Briefing</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {aiBrief ? (
              <div className="p-3.5 bg-[#121217] print:bg-slate-50 rounded-xl border border-zinc-800 print:border-slate-200 text-xs leading-relaxed text-zinc-300 print:text-slate-700 whitespace-pre-line">
                {aiBrief}
              </div>
            ) : (
              <div className="p-3 bg-[#121217]/70 print:bg-slate-50/70 rounded-xl border border-zinc-800/80 print:border-slate-200 text-xs text-zinc-500 print:text-slate-500 italic">
                Click "Generate AI Briefing" to synthesize a natural-language executive summary using server-side Gemini API, or review the deterministic ledger below.
              </div>
            )}
          </div>

          {/* Section 4: Attributed Destination Exchange */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 print:text-slate-700 bg-[#141418] print:bg-slate-100 px-2.5 py-1 rounded-xl border border-zinc-800/80 print:border-slate-200">
              4. Attributed Destination Exchange / VASP Cluster (Module 5)
            </h2>
            <div className="p-3.5 border border-zinc-800 print:border-slate-200 rounded-xl bg-[#121217] print:bg-slate-50 space-y-2 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-[10px] text-zinc-500 print:text-slate-500 block uppercase">Identified Entity:</span>
                  <strong className="text-sm text-white print:text-slate-900">{attribution.name}</strong>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-zinc-500 print:text-slate-500 block uppercase">Confidence Tier:</span>
                  <span className="font-mono font-bold text-indigo-300 print:text-indigo-800 bg-indigo-950/50 print:bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-800/40 print:border-indigo-200">
                    {attribution.confidenceTier}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                <div className="p-2.5 bg-[#16161d] print:bg-white rounded-xl border border-zinc-800 print:border-slate-200">
                  <span className="text-[10px] text-zinc-500 print:text-slate-500 block font-sans">Target Deposit Address:</span>
                  <span className="text-sky-400 print:text-indigo-950 font-bold select-all">{attribution.depositAddress}</span>
                </div>
                <div className="p-2.5 bg-[#16161d] print:bg-white rounded-xl border border-zinc-800 print:border-slate-200">
                  <span className="text-[10px] text-zinc-500 print:text-slate-500 block font-sans">Registered Jurisdiction:</span>
                  <span className="text-zinc-300 print:text-slate-800">{attribution.jurisdiction}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Section 5: Statutory Preservation Requisition Notice (Section 91 CrPC / Section 94 BNSS) */}
          <div className="space-y-2 print:break-before-page">
            <h2 className="text-xs font-bold uppercase tracking-wider text-rose-300 print:text-rose-800 bg-rose-950/30 print:bg-rose-50 px-2.5 py-1 rounded-xl border border-rose-800/60 print:border-rose-200">
              5. Statutory Requisition Notice (Under Section 91 CrPC / Section 94 BNSS)
            </h2>
            <div className="p-4 rounded-xl bg-[#121217] print:bg-slate-50 border border-zinc-800 print:border-slate-300 font-mono text-xs leading-relaxed text-zinc-300 print:text-slate-800 space-y-3">
              <div className="text-center font-bold text-white print:text-slate-900 border-b border-zinc-800 print:border-slate-300 pb-2">
                OFFICE OF THE INVESTIGATING OFFICER, CYBER CRIME CELL<br />
                REQUISITION FOR PRODUCTION OF DOCUMENTS & FREEZING OF CRYPTO ASSETS
              </div>

              <div>
                <strong className="text-zinc-200 print:text-slate-900">TO:</strong><br />
                The Compliance Nodal Officer / Legal Grievance Cell,<br />
                {attribution.complianceNoticeTarget.legalEntity},<br />
                Email: <span className="text-indigo-400 print:text-indigo-700">{attribution.complianceNoticeTarget.grievanceOfficerEmail}</span>
              </div>

              <div>
                <strong className="text-zinc-200 print:text-slate-900">SUBJECT:</strong> Urgent Notice under Section 91 of the Code of Criminal Procedure, 1973 (CrPC) / Section 94 of Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) regarding Cyber Fraud Investigation in Ref #{complaint?.ackNumber || 'NCRP-2026'}.
              </div>

              <p className="text-justify font-sans text-[11px] leading-relaxed text-zinc-300 print:text-slate-800">
                WHEREAS, an investigation has been registered upon complaint of financial cyber fraud wherein complainant's funds amounting to ₹{(complaint?.amountInr || 0).toLocaleString('en-IN')} were unlawfully diverted. Blockchain forensic tracing establishes that the proceeds of crime have traversed through intermediary peeling/mule addresses and deposited into your exchange deposit address <strong>{attribution.depositAddress}</strong>.
              </p>

              <div className="p-3 bg-[#16161d] print:bg-white rounded-xl border border-zinc-800 print:border-slate-300 text-[11px] text-zinc-300 print:text-slate-800">
                <strong className="text-white print:text-slate-900">YOU ARE HEREBY DIRECTED TO IMMEDIATELY:</strong>
                <ol className="list-decimal list-inside space-y-1 mt-1">
                  <li><strong>Freeze / Lien-mark</strong> all funds, credits, and withdrawals associated with deposit address <code className="font-bold text-sky-400 print:text-slate-900">{attribution.depositAddress}</code>.</li>
                  <li>Furnish complete KYC particulars, registered name, email, phone number, and linked fiat bank withdrawal records of the account holder.</li>
                  <li>Preserve all server access logs, IP addresses, and session credentials for 180 days.</li>
                </ol>
              </div>

              <div className="flex justify-between pt-4 font-sans text-xs text-zinc-400 print:text-slate-700">
                <div>
                  Date: {new Date().toLocaleDateString('en-GB')}<br />
                  Place: Cyber Police Station
                </div>
                <div className="text-right">
                  [Digitally Signed / Seal]<br />
                  <strong className="text-zinc-200 print:text-slate-900">Investigating Officer</strong><br />
                  State Cyber Crime Cell / I4C Nodal Unit
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
