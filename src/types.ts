/**
 * Types for LEDGR
 */

export type RiskVerdict = 'confirmed' | 'watch' | 'none';
export type RuleFlag = 'high' | 'low' | 'none';
export type MlPrediction = 'illicit' | 'licit' | 'unknown';
export type ConfidenceTier = 'elliptic-derived' | 'supplementary-source';

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
    category: 'VASP' | 'Mixer' | 'Merchant' | 'Private';
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
