/**
 * Types for LEDGR
 */

export type RiskVerdict = 'confirmed' | 'watch' | 'none';
export type RuleFlag = 'high' | 'low' | 'none';
export type MlPrediction = 'illicit' | 'licit' | 'unknown';
export type ConfidenceTier = 'elliptic-derived' | 'supplementary-source' | 'unattributed';
/**
 * Where a trace came from — set by the Python pipeline on the trace object
 * (`backend/ledgr/service.py`). `elliptic-indexed` = dataset fast path;
 * `live-lookup` = bounded real-chain fetch (lower confidence, ML unavailable);
 * `not-found-on-chain` = honest empty result. Demo/mock traces carry no source.
 */
export type TraceSource = 'elliptic-indexed' | 'live-lookup' | 'not-found-on-chain';

export interface Complaint {
  id: string;
  ackNumber: string; // e.g. NCRP-2026-DL-89102
  victimName: string;
  victimState: string;
  policeStation: string;
  reportedDate: string;
  scamCategory: 'Pig Butchering / Investment' | 'Telegram Task Fraud' | 'Ransomware Extortion' | 'Fake Loan App' | 'E-Commerce Scam' | 'Licit Commercial';
  amountInr: number;
  amountBtc: number;
  suspectAddress: string;
  suspectTxHash: string;
  narrative: string;
}

export interface WalletNode {
  id: string; // bitcoin address
  label: string;
  type: 'suspect_root' | 'intermediary' | 'peel_change' | 'fan_out_mule' | 'mixer_service' | 'exchange_deposit' | 'exchange_hot_wallet' | 'licit_merchant';
  hop: number;
  balanceBtc: number;
  totalReceivedBtc: number;
  totalSentBtc: number;
  txCount: number;
  firstSeen: string;
  lastSeen: string;
  ruleFlag: RuleFlag;
  ruleReasons: string[];
  mlScore: number; // 0 to 1
  mlPrediction: MlPrediction;
  verdict: RiskVerdict;
  /**
   * True only when the pipeline actually evaluated this wallet's signals.
   * Live pipeline traces evaluate the reported wallet; subgraph members are
   * shown structurally (label + hop) and are NOT fabricated signal values.
   */
  evaluated?: boolean;
  entityClusterId?: string;
  attribution?: {
    name: string;
    category: 'VASP' | 'Mixer' | 'Merchant' | 'Private' | 'Unknown';
    confidenceTier: ConfidenceTier;
    sourceName: string;
    jurisdiction?: string;
    complianceEmail?: string;
  };
  x?: number;
  y?: number;
}

export interface TransactionEdge {
  id: string;
  from: string;
  to: string;
  txHash: string;
  amountBtc: number;
  amountInr: number;
  timestamp: string;
  feeBtc: number;
  hop: number;
  isPeelChain?: boolean;
  isFanOut?: boolean;
  isMixerHop?: boolean;
  note?: string;
}

export interface FeatureHighlight {
  name: string;
  value: string | number;
  impact: 'positive' | 'negative' | 'neutral';
  description: string;
}

export interface TraceResult {
  targetAddress: string;
  complaint?: Complaint;
  /** Trace provenance from the pipeline (absent on demo/mock traces). */
  source?: TraceSource;
  /**
   * True only when the R9 live-lookup path hit its bounded fetch caps
   * (backend `meta.capped`: LIVE_MAX_COUNTERPARTY_FETCHES / LIVE_MAX_TXS_PER_ADDRESS
   * reached). Absent on `elliptic-indexed` traces (bounded by hop depth only —
   * nothing is truncated there) and on demo/mock traces. Never fabricated.
   * Note: the live graph's separate LIVE_MAX_NODES hard cap is logged
   * server-side only and is not currently present in the trace response.
   */
  fetchCapped?: boolean;
  nodes: WalletNode[];
  edges: TransactionEdge[];
  verdict: RiskVerdict;
  hopDepth: number;
  contributingSignals: {
    ruleScore: number; // 0-100
    ruleFlag: RuleFlag;
    ruleDetails: {
      peelChainDetected: boolean;
      peelChainDetails?: string;
      rapidFanOutDetected: boolean;
      fanOutDetails?: string;
      mixerProximityDetected: boolean;
      mixerDetails?: string;
      heuristicsSummary: string[];
    };
    mlScore: number; // 0-1
    mlPrediction: MlPrediction;
    mlConfidence: number; // percentage e.g. 0.954
    featureHighlights: FeatureHighlight[];
  };
  attribution: {
    name: string;
    category: 'VASP' | 'Mixer' | 'Merchant' | 'Private' | 'Unknown';
    confidenceTier: ConfidenceTier;
    sourceCitation: string;
    depositAddress: string;
    riskLevel: 'CRITICAL' | 'ELEVATED' | 'LOW';
    jurisdiction: string;
    complianceNoticeTarget: {
      legalEntity: string;
      grievanceOfficerEmail: string;
      statutoryReference: string;
    };
  };
  summaryStats: {
    totalTrackedBtc: number;
    totalTrackedInr: number;
    hopCount: number;
    attributedVasp: string;
    confirmedIllicitNodes: number;
    watchNodes: number;
    peelHopsCount: number;
  };
}

export interface WatchlistItem {
  address: string;
  label: string;
  ackNumber: string;
  victimName: string;
  dateAdded: string;
  verdict: RiskVerdict;
  category: string;
  amountInr: number;
  unconfirmedAlert?: {
    txHash: string;
    direction: 'incoming' | 'outgoing';
    amountBtc: number;
    amountInr: number;
    detectedAt: string;
    status: 'unconfirmed_mempool';
    feeRateSatVb: number;
    counterpartyAddress: string;
  };
}

export interface ConvergenceCluster {
  id: string;
  name: string;
  clusterDepositAddress: string;
  jurisdiction: string;
  convergingCases: {
    ackNumber: string;
    victimName: string;
    state: string;
    scamType: string;
    amountInr: number;
    amountBtc: number;
    initialSuspectAddress: string;
    hopsToConvergence: number;
  }[];
  totalCombinedLossInr: number;
  totalCombinedLossBtc: number;
  syndicateProfile: string;
}
