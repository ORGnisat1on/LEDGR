import React, { useState } from 'react';
import { X, Shield, FileText, Upload, Plus, CheckCircle2, ChevronRight, AlertCircle, Sparkles } from 'lucide-react';
import { CASE_STUDIES } from '../data/mockCases';
import { Complaint } from '../types';

interface ComplaintIntakeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadCase: (caseId: string) => void;
  onSubmitCustom: (complaint: Complaint) => void;
  onRunBatch: (addresses: string[]) => void;
}

export const ComplaintIntakeModal: React.FC<ComplaintIntakeModalProps> = ({
  isOpen,
  onClose,
  onLoadCase,
  onSubmitCustom,
  onRunBatch
}) => {
  const [activeTab, setActiveTab] = useState<'presets' | 'custom' | 'bulk'>('presets');

  // Custom complaint form state
  const [victimName, setVictimName] = useState('');
  const [victimState, setVictimState] = useState('Delhi (NCR)');
  const [policeStation, setPoliceStation] = useState('');
  const [scamCategory, setScamCategory] = useState<Complaint['scamCategory']>('Pig Butchering / Investment');
  const [amountInr, setAmountInr] = useState('2500000');
  const [suspectAddress, setSuspectAddress] = useState('');
  const [suspectTxHash, setSuspectTxHash] = useState('');
  const [narrative, setNarrative] = useState('');

  // Bulk state
  const [bulkInput, setBulkInput] = useState(
    `1SyndicateDelhiVictimAddr111111111\n1SyndicatePuneVictimAddr2222222222\n1SyndicateBlrVictimAddr33333333333`
  );

  if (!isOpen) return null;

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!suspectAddress.trim()) return;

    const inr = Number(amountInr) || 100000;
    const btc = Number((inr / 894800).toFixed(4));
    const randomAck = `NCRP-2026-${victimState.substring(0, 2).toUpperCase()}-${Math.floor(10000 + Math.random() * 90000)}`;

    const newComplaint: Complaint = {
      id: `complaint-${Date.now()}`,
      ackNumber: randomAck,
      victimName: victimName || 'Citizen Complainant',
      victimState: victimState || 'General NCRP Intake',
      policeStation: policeStation || 'State Cyber Crime Police Station',
      reportedDate: new Date().toISOString().replace('T', ' ').substring(0, 16) + ' IST',
      scamCategory,
      amountInr: inr,
      amountBtc: btc,
      suspectAddress: suspectAddress.trim(),
      suspectTxHash: suspectTxHash.trim() || `tx_${Math.random().toString(16).substring(2, 10)}`,
      narrative: narrative || 'Complaint registered on National Cyber Crime Reporting Portal (NCRP).'
    };

    onSubmitCustom(newComplaint);
    onClose();
  };

  const handleBulkSubmit = () => {
    const list = bulkInput
      .split('\n')
      .map(s => s.trim())
      .filter(s => s.length > 10);
    if (list.length > 0) {
      onRunBatch(list);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-[#0e0e12] rounded-2xl shadow-2xl border border-zinc-800/80 w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-[#121217] text-white px-5 py-4 flex items-center justify-between border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-950/50 border border-indigo-800/60 flex items-center justify-center text-sky-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Complaint Intake
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

        {/* Tab Selector */}
        <div className="flex border-b border-zinc-800/80 bg-[#121217] text-xs font-semibold">
          <button
            onClick={() => setActiveTab('presets')}
            className={`flex-1 py-3 px-4 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 cursor-pointer ${
              activeTab === 'presets'
                ? 'border-indigo-500 bg-[#16161d] text-indigo-300 font-bold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Presets</span>
          </button>
          <button
            onClick={() => setActiveTab('custom')}
            className={`flex-1 py-3 px-4 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 cursor-pointer ${
              activeTab === 'custom'
                ? 'border-indigo-500 bg-[#16161d] text-indigo-300 font-bold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Plus className="w-4 h-4 text-emerald-400" />
            <span>Single Suspect Intake</span>
          </button>
          <button
            onClick={() => setActiveTab('bulk')}
            className={`flex-1 py-3 px-4 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 cursor-pointer ${
              activeTab === 'bulk'
                ? 'border-indigo-500 bg-[#16161d] text-indigo-300 font-bold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Upload className="w-4 h-4 text-amber-400" />
            <span>Bulk CSV / Convergence</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-5 max-h-[500px] overflow-y-auto text-zinc-300">
          {activeTab === 'presets' && (
            <div className="space-y-3">
              <p className="text-xs text-zinc-400">
                Select a verified forensic case study modeling distinct cybercrime typologies from the I4C / CIS Division operational log:
              </p>

              <div className="grid grid-cols-1 gap-2.5">
                {CASE_STUDIES.map(cs => (
                  <div
                    key={cs.id}
                    onClick={() => {
                      onLoadCase(cs.id);
                      onClose();
                    }}
                    className="p-3.5 rounded-xl border border-zinc-800/80 bg-[#141418] hover:border-indigo-500/60 hover:bg-[#181820] cursor-pointer transition-all flex items-start justify-between gap-3 group"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white group-hover:text-indigo-300">
                          {cs.name}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.2 rounded-md border ${
                          cs.trace.verdict === 'confirmed'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                            : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        }`}>
                          {cs.trace.verdict === 'confirmed' ? 'Confirmed Risk' : 'Licit Negative Control'}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 line-clamp-2">
                        {cs.description}
                      </p>
                      <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-zinc-400 pt-1">
                        <span>Ack: <strong className="text-zinc-300">{cs.trace.complaint?.ackNumber}</strong></span>
                        <span>Amount: <strong className="text-zinc-300">₹{(cs.trace.complaint?.amountInr || 0).toLocaleString('en-IN')}</strong></span>
                        <span>Destination: <strong className="text-indigo-400">{cs.trace.attribution.name}</strong></span>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-zinc-500 group-hover:text-indigo-400 shrink-0 mt-2" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'custom' && (
            <form onSubmit={handleCustomSubmit} className="space-y-3.5 text-xs">
              <div className="p-3 bg-amber-950/30 rounded-xl border border-amber-800/50 text-amber-200 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  Notice: NCRP mock environment. Inputting a Bitcoin wallet address will execute real-time graph traversal, peel chain / fan-out / mixer detection, and VASP attribution.
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-zinc-300 block mb-1">Victim Name:</label>
                  <input
                    type="text"
                    required
                    value={victimName}
                    onChange={e => setVictimName(e.target.value)}
                    placeholder="e.g. Vikramaditya Sen"
                    className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="font-semibold text-zinc-300 block mb-1">State / UT Cyber Cell:</label>
                  <select
                    value={victimState}
                    onChange={e => setVictimState(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="Delhi (NCR)">Delhi (NCR)</option>
                    <option value="Maharashtra">Maharashtra</option>
                    <option value="Karnataka">Karnataka</option>
                    <option value="Tamil Nadu">Tamil Nadu</option>
                    <option value="Uttar Pradesh">Uttar Pradesh</option>
                    <option value="Telangana">Telangana</option>
                    <option value="Gujarat">Gujarat</option>
                    <option value="West Bengal">West Bengal</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-zinc-300 block mb-1">Scam Typology Category:</label>
                  <select
                    value={scamCategory}
                    onChange={e => setScamCategory(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="Pig Butchering / Investment">Pig Butchering (Investment / Quant App)</option>
                    <option value="Telegram Task Fraud">Telegram Task / Rating Fraud</option>
                    <option value="Ransomware Extortion">Ransomware Extortion</option>
                    <option value="Fake Loan App">Fake Loan App Extortion</option>
                    <option value="E-Commerce Scam">E-Commerce Merchant Fraud</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-zinc-300 block mb-1">Defrauded Amount (INR):</label>
                  <input
                    type="number"
                    required
                    value={amountInr}
                    onChange={e => setAmountInr(e.target.value)}
                    placeholder="e.g. 1500000"
                    className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-200 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-zinc-300 block mb-1">
                  Reported Suspect Bitcoin Wallet Address: *
                </label>
                <input
                  type="text"
                  required
                  value={suspectAddress}
                  onChange={e => setSuspectAddress(e.target.value)}
                  placeholder="e.g. 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or bc1q..."
                  className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-sky-400 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-zinc-300 block mb-1">Transaction TxID (Optional):</label>
                <input
                  type="text"
                  value={suspectTxHash}
                  onChange={e => setSuspectTxHash(e.target.value)}
                  placeholder="e.g. 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
                  className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-300 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-zinc-300 block mb-1">Complaint Brief Narrative:</label>
                <textarea
                  rows={2}
                  value={narrative}
                  onChange={e => setNarrative(e.target.value)}
                  placeholder="Complainant was instructed via Telegram group to deposit funds..."
                  className="w-full px-3 py-1.5 rounded-xl border border-zinc-800 bg-[#141418] text-zinc-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 font-semibold shadow-md shadow-indigo-950/40 cursor-pointer"
                >
                  Submit & Ingest for Tracing
                </button>
              </div>
            </form>
          )}

          {activeTab === 'bulk' && (
            <div className="space-y-3 text-xs">
              <div className="p-3 bg-indigo-950/30 rounded-xl border border-indigo-800/50 text-indigo-200">
                <span className="font-bold block mb-1">Bulk Wallet Tracing & Convergence (SCOPE.md Stretch Goal):</span>
                <p className="text-zinc-300">
                  Paste multiple suspect addresses (one per line) or upload a complaint CSV. The system runs Modules 1–4 across all addresses and evaluates Module 5 <strong>Cross-Wallet Convergence</strong> to detect whether separate victims' funds land at the same exchange deposit cluster!
                </p>
              </div>

              <div>
                <label className="font-semibold text-zinc-300 block mb-1">
                  Suspect Wallet Addresses (One per line):
                </label>
                <textarea
                  rows={5}
                  value={bulkInput}
                  onChange={e => setBulkInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-zinc-800 bg-[#141418] font-mono text-xs text-sky-400 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-zinc-400 font-mono">
                  Addresses detected: {bulkInput.split('\n').filter(s => s.trim().length > 10).length}
                </span>
                <button
                  onClick={handleBulkSubmit}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 font-semibold shadow-md shadow-indigo-950/40 cursor-pointer"
                >
                  Run Batch Trace & Detect Convergence
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
