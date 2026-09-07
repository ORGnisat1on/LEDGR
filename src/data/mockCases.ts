/**
 * Forensic Datasets & Pre-indexed Case Studies
 * Derived from Bitcoin transaction graph topology & Elliptic feature representations
 */

import { TraceResult, Complaint, WatchlistItem, ConvergenceCluster } from '../types';

export const CASE_STUDIES: {
  id: string;
  name: string;
  description: string;
  category: Complaint['scamCategory'];
  address: string;
  trace: TraceResult;
}[] = [
  {
    id: 'case-1',
    name: 'Case #1: Pig Butchering (Sha Zhu Pan) Peel Chain',
    description: 'Victim lured into fake "Forex-BTC Quant Yield" portal. Funds peeled sequentially through 4 intermediary hops to avoid AML alert thresholds before landing in an exchange deposit wallet.',
    category: 'Pig Butchering / Investment',
    address: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
    trace: {
      targetAddress: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
      hopDepth: 4,
      verdict: 'confirmed',
      complaint: {
        id: 'case-1',
        ackNumber: 'NCRP-2026-DL-89102',
        victimName: 'Rameshwar K. Sharma',
        victimState: 'Delhi (NCR)',
        policeStation: 'Cyber Crime Police Station, Dwarka',
        reportedDate: '2026-08-28 11:24 IST',
        scamCategory: 'Pig Butchering / Investment',
        amountInr: 4850000,
        amountBtc: 5.42,
        suspectAddress: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
        suspectTxHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        narrative: 'Complainant was contacted via WhatsApp by a person pretending to be an investment advisor named "Sophia Tan". Complainant transferred INR into bank accounts provided on Telegram, which converted to 5.42 BTC and sent to suspect wallet. Fraudster stopped responding when withdrawal was requested.'
      },
      contributingSignals: {
        ruleScore: 96,
        ruleFlag: 'high',
        ruleDetails: {
          peelChainDetected: true,
          peelChainDetails: 'Forwarding ratio 94.8% with 3 consecutive low-value peel outputs (<6% value) typical of automated peeling laundering software.',
          rapidFanOutDetected: false,
          mixerProximityDetected: false,
          heuristicsSummary: [
            'Peel chain signature: 3 sequential asymmetric forward splits',
            'Forward value preservation: 94.8% forwarded downstream',
            'Peel retention: Change output values avg 0.22 BTC sent to auxiliary burner'
          ]
        },
        mlScore: 0.954,
        mlPrediction: 'illicit',
        mlConfidence: 0.954,
        featureHighlights: [
          { name: 'in_degree_norm', value: 1.0, impact: 'negative', description: 'Single lump-sum input from victim source' },
          { name: 'out_degree_norm', value: 2.0, impact: 'negative', description: 'Strict 2-output structure (1 forward + 1 peel)' },
          { name: 'gini_out_flow', value: 0.91, impact: 'negative', description: 'Extreme inequality between forward and change outputs' },
          { name: 'mean_timestamp_delta', value: '412 sec', impact: 'negative', description: 'Automated script forwarding interval' },
          { name: 'clustering_coefficient', value: 0.02, impact: 'neutral', description: 'Linear tree topology typical of peel chains' }
        ]
      },
      attribution: {
        name: 'Binance Hot Wallet 14 (Deposit Sub-Cluster)',
        category: 'VASP',
        confidenceTier: 'supplementary-source',
        sourceCitation: 'Public VASP Hot-Wallet Registry & FIU-IND Exchange Directory 2026',
        depositAddress: '1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s',
        riskLevel: 'CRITICAL',
        jurisdiction: 'Cayman Islands / FIU-IND Registered Offshore Entity',
        complianceNoticeTarget: {
          legalEntity: 'Binance Holdings Ltd. (Compliance & Law Enforcement Response Team)',
          grievanceOfficerEmail: 'case-inquiry@binance.com / lawenforcement@binance.com',
          statutoryReference: 'Section 91 of Code of Criminal Procedure, 1973 (CrPC) / Section 94 Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)'
        }
      },
      summaryStats: {
        totalTrackedBtc: 5.42,
        totalTrackedInr: 4850000,
        hopCount: 4,
        attributedVasp: 'Binance Hot Wallet 14',
        confirmedIllicitNodes: 5,
        watchNodes: 2,
        peelHopsCount: 3
      },
      nodes: [
        {
          id: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
          label: 'Suspect Root (Victim Inflow)',
          type: 'suspect_root',
          hop: 0,
          balanceBtc: 0.001,
          totalReceivedBtc: 5.42,
          totalSentBtc: 5.419,
          txCount: 2,
          firstSeen: '2026-08-28 09:12',
          lastSeen: '2026-08-28 09:20',
          ruleFlag: 'high',
          ruleReasons: ['Reported victim deposit address', 'Immediate total drain after receipt'],
          mlScore: 0.942,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 100,
          y: 220
        },
        {
          id: '1PeelHop1xY98mQw7uRk52oKmnJ2189as1',
          label: 'Peel Hop 1 (Main Forward)',
          type: 'intermediary',
          hop: 1,
          balanceBtc: 0.002,
          totalReceivedBtc: 5.20,
          totalSentBtc: 5.198,
          txCount: 4,
          firstSeen: '2026-08-28 09:35',
          lastSeen: '2026-08-28 09:42',
          ruleFlag: 'high',
          ruleReasons: ['Peel forward split ratio 95.9%'],
          mlScore: 0.961,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 280,
          y: 160
        },
        {
          id: '1PeelChg1abc98234kjhsdf89234jklnsf',
          label: 'Peel Change 1 (Mule Cache)',
          type: 'peel_change',
          hop: 1,
          balanceBtc: 0.219,
          totalReceivedBtc: 0.22,
          totalSentBtc: 0.001,
          txCount: 1,
          firstSeen: '2026-08-28 09:35',
          lastSeen: '2026-08-28 09:35',
          ruleFlag: 'low',
          ruleReasons: ['Small peel-off change wallet'],
          mlScore: 0.612,
          mlPrediction: 'illicit',
          verdict: 'watch',
          x: 280,
          y: 320
        },
        {
          id: '1PeelHop2aB87xZ12mn90lkjh34567asdf',
          label: 'Peel Hop 2 (Main Forward)',
          type: 'intermediary',
          hop: 2,
          balanceBtc: 0.001,
          totalReceivedBtc: 4.95,
          totalSentBtc: 4.949,
          txCount: 3,
          firstSeen: '2026-08-28 10:04',
          lastSeen: '2026-08-28 10:11',
          ruleFlag: 'high',
          ruleReasons: ['Peel forward split ratio 95.1%'],
          mlScore: 0.958,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 460,
          y: 160
        },
        {
          id: '1PeelChg2bcd34567asdf98765lkjh1234',
          label: 'Peel Change 2 (Mule Cache)',
          type: 'peel_change',
          hop: 2,
          balanceBtc: 0.249,
          totalReceivedBtc: 0.25,
          totalSentBtc: 0.001,
          txCount: 1,
          firstSeen: '2026-08-28 10:04',
          lastSeen: '2026-08-28 10:04',
          ruleFlag: 'low',
          ruleReasons: ['Small peel-off change wallet'],
          mlScore: 0.589,
          mlPrediction: 'illicit',
          verdict: 'watch',
          x: 460,
          y: 320
        },
        {
          id: '1PeelHop3cDef4567890qwertyuiopasdf',
          label: 'Peel Hop 3 (Staging Wallet)',
          type: 'intermediary',
          hop: 3,
          balanceBtc: 0.001,
          totalReceivedBtc: 4.60,
          totalSentBtc: 4.599,
          txCount: 2,
          firstSeen: '2026-08-28 10:32',
          lastSeen: '2026-08-28 10:45',
          ruleFlag: 'high',
          ruleReasons: ['Final aggregation before VASP deposit'],
          mlScore: 0.949,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 640,
          y: 160
        },
        {
          id: '1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s',
          label: 'Binance Deposit Cluster #14',
          type: 'exchange_deposit',
          hop: 4,
          balanceBtc: 421.84,
          totalReceivedBtc: 18452.12,
          totalSentBtc: 18030.28,
          txCount: 9481,
          firstSeen: '2023-04-10',
          lastSeen: '2026-08-28 11:15',
          ruleFlag: 'none',
          ruleReasons: ['Known high-degree exchange aggregation hub'],
          mlScore: 0.24,
          mlPrediction: 'licit',
          verdict: 'none',
          attribution: {
            name: 'Binance Hot Wallet 14',
            category: 'VASP',
            confidenceTier: 'supplementary-source',
            sourceName: 'Public VASP Hot-Wallet Registry',
            jurisdiction: 'Cayman Islands / Global',
            complianceEmail: 'lawenforcement@binance.com'
          },
          x: 820,
          y: 220
        }
      ],
      edges: [
        {
          id: 'e1-main',
          from: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
          to: '1PeelHop1xY98mQw7uRk52oKmnJ2189as1',
          txHash: 'a12e34fa98bc56de12f3456789abcdef0123456789abcdef0123456789abcdef',
          amountBtc: 5.20,
          amountInr: 4652000,
          timestamp: '2026-08-28 09:35',
          feeBtc: 0.0001,
          hop: 1,
          isPeelChain: true,
          note: 'Primary peel forward (95.9%)'
        },
        {
          id: 'e1-peel',
          from: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
          to: '1PeelChg1abc98234kjhsdf89234jklnsf',
          txHash: 'a12e34fa98bc56de12f3456789abcdef0123456789abcdef0123456789abcdef',
          amountBtc: 0.22,
          amountInr: 196800,
          timestamp: '2026-08-28 09:35',
          feeBtc: 0.0001,
          hop: 1,
          isPeelChain: true,
          note: 'Peel change output (4.1%)'
        },
        {
          id: 'e2-main',
          from: '1PeelHop1xY98mQw7uRk52oKmnJ2189as1',
          to: '1PeelHop2aB87xZ12mn90lkjh34567asdf',
          txHash: 'b23f45ab09cd67ef2301456789bcdef0123456789abcdef0123456789abcdef',
          amountBtc: 4.95,
          amountInr: 4428000,
          timestamp: '2026-08-28 10:04',
          feeBtc: 0.0001,
          hop: 2,
          isPeelChain: true,
          note: 'Secondary peel forward (95.1%)'
        },
        {
          id: 'e2-peel',
          from: '1PeelHop1xY98mQw7uRk52oKmnJ2189as1',
          to: '1PeelChg2bcd34567asdf98765lkjh1234',
          txHash: 'b23f45ab09cd67ef2301456789bcdef0123456789abcdef0123456789abcdef',
          amountBtc: 0.25,
          amountInr: 223700,
          timestamp: '2026-08-28 10:04',
          feeBtc: 0.0001,
          hop: 2,
          isPeelChain: true,
          note: 'Peel change output (4.9%)'
        },
        {
          id: 'e3-main',
          from: '1PeelHop2aB87xZ12mn90lkjh34567asdf',
          to: '1PeelHop3cDef4567890qwertyuiopasdf',
          txHash: 'c34a56bc10de78fa3412567890cdef0123456789abcdef0123456789abcdef',
          amountBtc: 4.60,
          amountInr: 4115000,
          timestamp: '2026-08-28 10:32',
          feeBtc: 0.0001,
          hop: 3,
          isPeelChain: true,
          note: 'Tertiary peel forward (92.9%)'
        },
        {
          id: 'e4-deposit',
          from: '1PeelHop3cDef4567890qwertyuiopasdf',
          to: '1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s',
          txHash: 'd45b67cd21ef89ab4523678901def0123456789abcdef0123456789abcdef',
          amountBtc: 4.58,
          amountInr: 4097000,
          timestamp: '2026-08-28 10:58',
          feeBtc: 0.0002,
          hop: 4,
          isPeelChain: false,
          note: 'Direct VASP deposit transaction'
        }
      ]
    }
  },
  {
    id: 'case-2',
    name: 'Case #2: Telegram "Task Scam" Rapid Fan-Out',
    description: 'Victim extorted via fake YouTube rating / travel review task scam. Received funds are immediately disbursed across 6 mule accounts within 180 seconds to frustrate chain tracing.',
    category: 'Telegram Task Fraud',
    address: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
    trace: {
      targetAddress: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
      hopDepth: 2,
      verdict: 'confirmed',
      complaint: {
        id: 'case-2',
        ackNumber: 'NCRP-2026-MH-44219',
        victimName: 'Sneha Priyadarshini',
        victimState: 'Maharashtra',
        policeStation: 'Cyber Police Station, BKC, Mumbai',
        reportedDate: '2026-08-25 16:40 IST',
        scamCategory: 'Telegram Task Fraud',
        amountInr: 1820000,
        amountBtc: 2.05,
        suspectAddress: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
        suspectTxHash: 'f45c789a01de23bc45678901abcdef0123456789abcdef0123456789abcdef01',
        narrative: 'Complainant was added to a Telegram group offering ₹5,000/day for rating hotels on Google Maps. Initial small earnings were credited via UPI, followed by a demand for "prepaid task security deposits" totaling ₹18.2 Lakhs paid into cryptocurrency.'
      },
      contributingSignals: {
        ruleScore: 92,
        ruleFlag: 'high',
        ruleDetails: {
          peelChainDetected: false,
          rapidFanOutDetected: true,
          fanOutDetails: 'Extreme dispersion velocity: 6 outgoing transactions broadcast within 140 seconds of incoming transaction block confirmation.',
          mixerProximityDetected: false,
          heuristicsSummary: [
            'Rapid fan-out trigger: 6 mule destination addresses in < 3 minutes',
            'Symmetric splitting: Equal disbursement across mule addresses (avg 0.33 BTC each)',
            'Co-spending convergence: Multiple outputs recombine at KuCoin aggregator'
          ]
        },
        mlScore: 0.918,
        mlPrediction: 'illicit',
        mlConfidence: 0.918,
        featureHighlights: [
          { name: 'out_degree_norm', value: 6.0, impact: 'negative', description: 'High out-degree dispersion to unassociated wallets' },
          { name: 'dispersion_velocity_tx_per_min', value: 2.57, impact: 'negative', description: 'Automated rapid dissemination' },
          { name: 'entropy_outgoing_amounts', value: 0.98, impact: 'negative', description: 'Near identical amounts split to mules' },
          { name: 'neighbor_illicit_ratio', value: 0.83, impact: 'negative', description: '83% of neighborhood labeled illicit by Elliptic GNN' }
        ]
      },
      attribution: {
        name: 'KuCoin Global Hot Wallet Cluster',
        category: 'VASP',
        confidenceTier: 'supplementary-source',
        sourceCitation: 'Public Exchange Cluster Intel / OFAC-I4C Crypto Forensics Database',
        depositAddress: '3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5',
        riskLevel: 'CRITICAL',
        jurisdiction: 'Seychelles / International',
        complianceNoticeTarget: {
          legalEntity: 'KuCoin Technology Services Ltd.',
          grievanceOfficerEmail: 'compliance@kucoin.com / legal@kucoin.com',
          statutoryReference: 'Section 91 CrPC / Section 94 BNSS Legal Preservation Notice'
        }
      },
      summaryStats: {
        totalTrackedBtc: 2.05,
        totalTrackedInr: 1820000,
        hopCount: 2,
        attributedVasp: 'KuCoin Global Hot Wallet',
        confirmedIllicitNodes: 7,
        watchNodes: 1,
        peelHopsCount: 0
      },
      nodes: [
        {
          id: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          label: 'Suspect Root (Task Scam)',
          type: 'suspect_root',
          hop: 0,
          balanceBtc: 0.001,
          totalReceivedBtc: 2.05,
          totalSentBtc: 2.049,
          txCount: 7,
          firstSeen: '2026-08-25 15:10',
          lastSeen: '2026-08-25 15:14',
          ruleFlag: 'high',
          ruleReasons: ['Dispersed 6 transactions within 140 seconds'],
          mlScore: 0.918,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 100,
          y: 220
        },
        {
          id: '3MuleAddr11111111111111111111111111',
          label: 'Mule Wallet 1',
          type: 'fan_out_mule',
          hop: 1,
          balanceBtc: 0.001,
          totalReceivedBtc: 0.35,
          totalSentBtc: 0.349,
          txCount: 2,
          firstSeen: '2026-08-25 15:12',
          lastSeen: '2026-08-25 15:30',
          ruleFlag: 'high',
          ruleReasons: ['Short-lived mule burner wallet'],
          mlScore: 0.884,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 380,
          y: 80
        },
        {
          id: '3MuleAddr22222222222222222222222222',
          label: 'Mule Wallet 2',
          type: 'fan_out_mule',
          hop: 1,
          balanceBtc: 0.001,
          totalReceivedBtc: 0.34,
          totalSentBtc: 0.339,
          txCount: 2,
          firstSeen: '2026-08-25 15:12',
          lastSeen: '2026-08-25 15:32',
          ruleFlag: 'high',
          ruleReasons: ['Short-lived mule burner wallet'],
          mlScore: 0.871,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 380,
          y: 150
        },
        {
          id: '3MuleAddr33333333333333333333333333',
          label: 'Mule Wallet 3',
          type: 'fan_out_mule',
          hop: 1,
          balanceBtc: 0.001,
          totalReceivedBtc: 0.34,
          totalSentBtc: 0.339,
          txCount: 2,
          firstSeen: '2026-08-25 15:13',
          lastSeen: '2026-08-25 15:35',
          ruleFlag: 'high',
          ruleReasons: ['Short-lived mule burner wallet'],
          mlScore: 0.892,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 380,
          y: 220
        },
        {
          id: '3MuleAddr44444444444444444444444444',
          label: 'Mule Wallet 4',
          type: 'fan_out_mule',
          hop: 1,
          balanceBtc: 0.001,
          totalReceivedBtc: 0.34,
          totalSentBtc: 0.339,
          txCount: 2,
          firstSeen: '2026-08-25 15:13',
          lastSeen: '2026-08-25 15:38',
          ruleFlag: 'high',
          ruleReasons: ['Short-lived mule burner wallet'],
          mlScore: 0.865,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 380,
          y: 290
        },
        {
          id: '3MuleAddr55555555555555555555555555',
          label: 'Mule Wallet 5',
          type: 'fan_out_mule',
          hop: 1,
          balanceBtc: 0.001,
          totalReceivedBtc: 0.34,
          totalSentBtc: 0.339,
          txCount: 2,
          firstSeen: '2026-08-25 15:14',
          lastSeen: '2026-08-25 15:40',
          ruleFlag: 'high',
          ruleReasons: ['Short-lived mule burner wallet'],
          mlScore: 0.880,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 380,
          y: 360
        },
        {
          id: '3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5',
          label: 'KuCoin Aggregator Deposit',
          type: 'exchange_deposit',
          hop: 2,
          balanceBtc: 189.4,
          totalReceivedBtc: 9240.5,
          totalSentBtc: 9051.1,
          txCount: 3812,
          firstSeen: '2024-01-15',
          lastSeen: '2026-08-25 16:05',
          ruleFlag: 'none',
          ruleReasons: ['High-degree exchange sweep account'],
          mlScore: 0.22,
          mlPrediction: 'licit',
          verdict: 'none',
          attribution: {
            name: 'KuCoin Global Hot Wallet',
            category: 'VASP',
            confidenceTier: 'supplementary-source',
            sourceName: 'Community Tagged VASP Registry',
            jurisdiction: 'Seychelles',
            complianceEmail: 'compliance@kucoin.com'
          },
          x: 720,
          y: 220
        }
      ],
      edges: [
        {
          id: 'ef1',
          from: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          to: '3MuleAddr11111111111111111111111111',
          txHash: 'tx1-fanout-001',
          amountBtc: 0.35,
          amountInr: 310000,
          timestamp: '2026-08-25 15:12',
          feeBtc: 0.00008,
          hop: 1,
          isFanOut: true
        },
        {
          id: 'ef2',
          from: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          to: '3MuleAddr22222222222222222222222222',
          txHash: 'tx1-fanout-002',
          amountBtc: 0.34,
          amountInr: 302000,
          timestamp: '2026-08-25 15:12',
          feeBtc: 0.00008,
          hop: 1,
          isFanOut: true
        },
        {
          id: 'ef3',
          from: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          to: '3MuleAddr33333333333333333333333333',
          txHash: 'tx1-fanout-003',
          amountBtc: 0.34,
          amountInr: 302000,
          timestamp: '2026-08-25 15:13',
          feeBtc: 0.00008,
          hop: 1,
          isFanOut: true
        },
        {
          id: 'ef4',
          from: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          to: '3MuleAddr44444444444444444444444444',
          txHash: 'tx1-fanout-004',
          amountBtc: 0.34,
          amountInr: 302000,
          timestamp: '2026-08-25 15:13',
          feeBtc: 0.00008,
          hop: 1,
          isFanOut: true
        },
        {
          id: 'ef5',
          from: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
          to: '3MuleAddr55555555555555555555555555',
          txHash: 'tx1-fanout-005',
          amountBtc: 0.34,
          amountInr: 302000,
          timestamp: '2026-08-25 15:14',
          feeBtc: 0.00008,
          hop: 1,
          isFanOut: true
        },
        {
          id: 'em1-recombine',
          from: '3MuleAddr11111111111111111111111111',
          to: '3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5',
          txHash: 'tx-kucoin-dep-01',
          amountBtc: 0.349,
          amountInr: 309000,
          timestamp: '2026-08-25 15:45',
          feeBtc: 0.0001,
          hop: 2,
          note: 'Mule aggregation deposit'
        },
        {
          id: 'em2-recombine',
          from: '3MuleAddr22222222222222222222222222',
          to: '3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5',
          txHash: 'tx-kucoin-dep-02',
          amountBtc: 0.339,
          amountInr: 301000,
          timestamp: '2026-08-25 15:48',
          feeBtc: 0.0001,
          hop: 2,
          note: 'Mule aggregation deposit'
        },
        {
          id: 'em3-recombine',
          from: '3MuleAddr33333333333333333333333333',
          to: '3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5',
          txHash: 'tx-kucoin-dep-03',
          amountBtc: 0.339,
          amountInr: 301000,
          timestamp: '2026-08-25 15:52',
          feeBtc: 0.0001,
          hop: 2,
          note: 'Mule aggregation deposit'
        }
      ]
    }
  },
  {
    id: 'case-3',
    name: 'Case #3: Ransomware Extortion Mixer Hop',
    description: 'Hospital chain in Bengaluru hit with ransomware encryption. Ransom payment was directed through a Wasabi CoinJoin mixer hop to obfuscate UTXO lineage before exiting at OKX.',
    category: 'Ransomware Extortion',
    address: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
    trace: {
      targetAddress: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
      hopDepth: 3,
      verdict: 'confirmed',
      complaint: {
        id: 'case-3',
        ackNumber: 'NCRP-2026-KA-77301',
        victimName: 'Dr. Anand M. Rao (Hospital CIO)',
        victimState: 'Karnataka',
        policeStation: 'CID Cyber Crime Division, Bengaluru',
        reportedDate: '2026-08-19 08:30 IST',
        scamCategory: 'Ransomware Extortion',
        amountInr: 12000000,
        amountBtc: 13.5,
        suspectAddress: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
        suspectTxHash: '99887766554433221100aabbccddeeff00112233445566778899aabbccddeeff',
        narrative: 'Hospital PACS and patient database servers encrypted by Akira Ransomware variant. Threat actors demanded 13.5 BTC within 48 hours to provide decryption keys. Ransom was paid from emergency funds.'
      },
      contributingSignals: {
        ruleScore: 98,
        ruleFlag: 'high',
        ruleDetails: {
          peelChainDetected: false,
          rapidFanOutDetected: false,
          mixerProximityDetected: true,
          mixerDetails: 'Proximity hop 1: Direct transfer to Wasabi 2.0 CoinJoin Coordinator input script with 50+ equalized denomination outputs.',
          heuristicsSummary: [
            'Mixer adjacency flag: 1-hop distance to CoinJoin mixing pool',
            'Denomination equalization: 0.1 BTC standardized CoinJoin outputs',
            'Utxo peeling & re-assembly into exchange deposit cluster'
          ]
        },
        mlScore: 0.981,
        mlPrediction: 'illicit',
        mlConfidence: 0.981,
        featureHighlights: [
          { name: 'mixer_adjacent_distance', value: 1, impact: 'negative', description: 'Direct input to CoinJoin coordinator' },
          { name: 'equalized_output_entropy', value: 0.99, impact: 'negative', description: '50 identical output amounts (Wasabi pattern)' },
          { name: 'elliptic_cluster_risk', value: 'High Illicit', impact: 'negative', description: 'Associated with known threat actor entity' }
        ]
      },
      attribution: {
        name: 'OKX Exchange Aggregator',
        category: 'VASP',
        confidenceTier: 'supplementary-source',
        sourceCitation: 'Public Exchange Hot-Wallet Intelligence & Blockchain Analytics Cluster',
        depositAddress: 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4',
        riskLevel: 'CRITICAL',
        jurisdiction: 'Seychelles / Global',
        complianceNoticeTarget: {
          legalEntity: 'Aux Cayes FinTech Co. Ltd. (OKX Compliance)',
          grievanceOfficerEmail: 'compliance@okx.com',
          statutoryReference: 'Section 91 CrPC / Section 94 BNSS Emergency Seizure Warrant'
        }
      },
      summaryStats: {
        totalTrackedBtc: 13.5,
        totalTrackedInr: 12000000,
        hopCount: 3,
        attributedVasp: 'OKX Exchange Aggregator',
        confirmedIllicitNodes: 4,
        watchNodes: 1,
        peelHopsCount: 0
      },
      nodes: [
        {
          id: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
          label: 'Suspect Root (Ransomware Extortion)',
          type: 'suspect_root',
          hop: 0,
          balanceBtc: 0.001,
          totalReceivedBtc: 13.5,
          totalSentBtc: 13.499,
          txCount: 1,
          firstSeen: '2026-08-19 07:15',
          lastSeen: '2026-08-19 07:45',
          ruleFlag: 'high',
          ruleReasons: ['Ransomware extortion victim deposit'],
          mlScore: 0.981,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 100,
          y: 220
        },
        {
          id: 'bc1qwasabi20coordinatorpool98234kjhsdf',
          label: 'Wasabi 2.0 CoinJoin Mixer Pool',
          type: 'mixer_service',
          hop: 1,
          balanceBtc: 84.12,
          totalReceivedBtc: 4210.0,
          totalSentBtc: 4125.88,
          txCount: 890,
          firstSeen: '2024-08-01',
          lastSeen: '2026-08-19 08:12',
          ruleFlag: 'high',
          ruleReasons: ['Known CoinJoin anonymization service pool'],
          mlScore: 0.992,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          attribution: {
            name: 'Wasabi CoinJoin Protocol',
            category: 'Mixer',
            confidenceTier: 'elliptic-derived',
            sourceName: 'Heuristic & Elliptic Anonymizer Model'
          },
          x: 380,
          y: 220
        },
        {
          id: 'bc1qrecombinedmulehop222222222222222',
          label: 'Recombined Mule Address',
          type: 'intermediary',
          hop: 2,
          balanceBtc: 0.002,
          totalReceivedBtc: 12.8,
          totalSentBtc: 12.798,
          txCount: 3,
          firstSeen: '2026-08-19 09:10',
          lastSeen: '2026-08-19 09:30',
          ruleFlag: 'high',
          ruleReasons: ['Post-mix recombination output hop'],
          mlScore: 0.924,
          mlPrediction: 'illicit',
          verdict: 'confirmed',
          x: 600,
          y: 220
        },
        {
          id: 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4',
          label: 'OKX Deposit Cluster #09',
          type: 'exchange_deposit',
          hop: 3,
          balanceBtc: 512.9,
          totalReceivedBtc: 14200.0,
          totalSentBtc: 13687.1,
          txCount: 5410,
          firstSeen: '2023-11-20',
          lastSeen: '2026-08-19 10:15',
          ruleFlag: 'none',
          ruleReasons: ['High-degree exchange sweep address'],
          mlScore: 0.28,
          mlPrediction: 'licit',
          verdict: 'none',
          attribution: {
            name: 'OKX Exchange Aggregator',
            category: 'VASP',
            confidenceTier: 'supplementary-source',
            sourceName: 'Public Exchange Hot-Wallet Intelligence',
            jurisdiction: 'Seychelles / Global',
            complianceEmail: 'compliance@okx.com'
          },
          x: 820,
          y: 220
        }
      ],
      edges: [
        {
          id: 'er1',
          from: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
          to: 'bc1qwasabi20coordinatorpool98234kjhsdf',
          txHash: 'tx-ransom-wasabi-in-01',
          amountBtc: 13.49,
          amountInr: 11990000,
          timestamp: '2026-08-19 07:45',
          feeBtc: 0.005,
          hop: 1,
          isMixerHop: true,
          note: 'Direct deposit into CoinJoin mixing round'
        },
        {
          id: 'er2',
          from: 'bc1qwasabi20coordinatorpool98234kjhsdf',
          to: 'bc1qrecombinedmulehop222222222222222',
          txHash: 'tx-ransom-wasabi-out-02',
          amountBtc: 12.8,
          amountInr: 11370000,
          timestamp: '2026-08-19 09:10',
          feeBtc: 0.004,
          hop: 2,
          isMixerHop: true,
          note: 'De-anonymized output recombined via common-ownership graph'
        },
        {
          id: 'er3',
          from: 'bc1qrecombinedmulehop222222222222222',
          to: 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4',
          txHash: 'tx-okx-deposit-03',
          amountBtc: 12.79,
          amountInr: 11360000,
          timestamp: '2026-08-19 09:55',
          feeBtc: 0.001,
          hop: 3,
          note: 'Deposit to OKX account'
        }
      ]
    }
  },
  {
    id: 'case-4',
    name: 'Case #4: Licit E-Commerce Merchant (Negative Control)',
    description: 'Genuine merchant processing everyday payments. Demonstrates false positive suppression: balanced payments, no peeling, no mixer adjacency. Neither signal fires, resulting in Licit / None.',
    category: 'Licit Commercial',
    address: '1BitPayMerchantCommercialGateway9988',
    trace: {
      targetAddress: '1BitPayMerchantCommercialGateway9988',
      hopDepth: 2,
      verdict: 'none',
      complaint: {
        id: 'case-4',
        ackNumber: 'NCRP-2026-TN-11004',
        victimName: 'Suresh V. Balaji (Consumer Inquiry)',
        victimState: 'Tamil Nadu',
        policeStation: 'Cyber Crime Police Station, Chennai',
        reportedDate: '2026-08-15 14:10 IST',
        scamCategory: 'E-Commerce Scam',
        amountInr: 250000,
        amountBtc: 0.28,
        suspectAddress: '1BitPayMerchantCommercialGateway9988',
        suspectTxHash: '11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
        narrative: 'Buyer reported address after delayed delivery from an electronics hardware store. Tracing demonstrates that this is a recognized licensed payment gateway handling ordinary e-commerce payments.'
      },
      contributingSignals: {
        ruleScore: 12,
        ruleFlag: 'none',
        ruleDetails: {
          peelChainDetected: false,
          rapidFanOutDetected: false,
          mixerProximityDetected: false,
          heuristicsSummary: [
            'Zero laundering heuristics triggered',
            'Normal merchant fan-in/fan-out profile',
            'No mixer adjacency or rapid dispersion detected'
          ]
        },
        mlScore: 0.033,
        mlPrediction: 'licit',
        mlConfidence: 0.967,
        featureHighlights: [
          { name: 'in_degree_norm', value: 42.0, impact: 'positive', description: 'Multiple customer payments typical of merchant' },
          { name: 'out_degree_norm', value: 3.0, impact: 'positive', description: 'Standard settlement to payroll/liquidity' },
          { name: 'clustering_coefficient', value: 0.44, impact: 'positive', description: 'Dense commercial network topology' },
          { name: 'temporal_regularity', value: 'Regular 24h cycle', impact: 'positive', description: 'Business hours transaction pattern' }
        ]
      },
      attribution: {
        name: 'BitPay Commercial Merchant Gateway',
        category: 'Merchant',
        confidenceTier: 'elliptic-derived',
        sourceCitation: 'Elliptic Actor Database & Merchant Directory',
        depositAddress: '1BitPayMerchantCommercialGateway9988',
        riskLevel: 'LOW',
        jurisdiction: 'United States / Regulated MSB',
        complianceNoticeTarget: {
          legalEntity: 'BitPay Inc. Merchant Operations',
          grievanceOfficerEmail: 'merchant-support@bitpay.com',
          statutoryReference: 'Routine Commercial Information Request'
        }
      },
      summaryStats: {
        totalTrackedBtc: 0.28,
        totalTrackedInr: 250000,
        hopCount: 2,
        attributedVasp: 'BitPay Commercial Gateway',
        confirmedIllicitNodes: 0,
        watchNodes: 0,
        peelHopsCount: 0
      },
      nodes: [
        {
          id: '1BitPayMerchantCommercialGateway9988',
          label: 'Merchant Root (BitPay Gateway)',
          type: 'licit_merchant',
          hop: 0,
          balanceBtc: 14.5,
          totalReceivedBtc: 85.2,
          totalSentBtc: 70.7,
          txCount: 42,
          firstSeen: '2025-01-10',
          lastSeen: '2026-08-15 13:45',
          ruleFlag: 'none',
          ruleReasons: ['Clean commercial payment history'],
          mlScore: 0.033,
          mlPrediction: 'licit',
          verdict: 'none',
          attribution: {
            name: 'BitPay Commercial Merchant Gateway',
            category: 'Merchant',
            confidenceTier: 'elliptic-derived',
            sourceName: 'Elliptic Actor Dataset (Licit Entity)'
          },
          x: 150,
          y: 220
        },
        {
          id: '1LicitSettlementPayroll1234567890as',
          label: 'Merchant Settlement Account',
          type: 'licit_merchant',
          hop: 1,
          balanceBtc: 8.2,
          totalReceivedBtc: 65.0,
          totalSentBtc: 56.8,
          txCount: 18,
          firstSeen: '2025-02-01',
          lastSeen: '2026-08-15 14:00',
          ruleFlag: 'none',
          ruleReasons: ['Verified business payout address'],
          mlScore: 0.021,
          mlPrediction: 'licit',
          verdict: 'none',
          x: 450,
          y: 220
        },
        {
          id: '1KrakenLicitTreasuryVault8899aabbcc',
          label: 'Kraken Regulated Custody Vault',
          type: 'exchange_hot_wallet',
          hop: 2,
          balanceBtc: 890.1,
          totalReceivedBtc: 34500.0,
          totalSentBtc: 33609.9,
          txCount: 12000,
          firstSeen: '2022-05-15',
          lastSeen: '2026-08-15 15:30',
          ruleFlag: 'none',
          ruleReasons: ['FinCEN/FIU regulated exchange vault'],
          mlScore: 0.05,
          mlPrediction: 'licit',
          verdict: 'none',
          x: 750,
          y: 220
        }
      ],
      edges: [
        {
          id: 'el1',
          from: '1BitPayMerchantCommercialGateway9988',
          to: '1LicitSettlementPayroll1234567890as',
          txHash: 'tx-licit-settle-01',
          amountBtc: 0.28,
          amountInr: 250000,
          timestamp: '2026-08-15 13:55',
          feeBtc: 0.00005,
          hop: 1,
          note: 'Merchant daily sales aggregation'
        },
        {
          id: 'el2',
          from: '1LicitSettlementPayroll1234567890as',
          to: '1KrakenLicitTreasuryVault8899aabbcc',
          txHash: 'tx-licit-treasury-02',
          amountBtc: 0.279,
          amountInr: 249000,
          timestamp: '2026-08-15 14:15',
          feeBtc: 0.00005,
          hop: 2,
          note: 'Banking liquidity sweep'
        }
      ]
    }
  }
];

export const INITIAL_WATCHLIST: WatchlistItem[] = [
  {
    address: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
    label: 'Sha Zhu Pan Quant Scam Root',
    ackNumber: 'NCRP-2026-DL-89102',
    victimName: 'Rameshwar K. Sharma',
    dateAdded: '2026-08-28',
    verdict: 'confirmed',
    category: 'Pig Butchering / Investment',
    amountInr: 4850000
  },
  {
    address: '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy',
    label: 'Telegram Task Scam Dispersion Wallet',
    ackNumber: 'NCRP-2026-MH-44219',
    victimName: 'Sneha Priyadarshini',
    dateAdded: '2026-08-25',
    verdict: 'confirmed',
    category: 'Telegram Task Fraud',
    amountInr: 1820000
  },
  {
    address: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
    label: 'Akira Ransomware Hospital Threat Actor',
    ackNumber: 'NCRP-2026-KA-77301',
    victimName: 'Dr. Anand M. Rao',
    dateAdded: '2026-08-19',
    verdict: 'confirmed',
    category: 'Ransomware Extortion',
    amountInr: 12000000
  },
  {
    address: '1PeelChg1abc98234kjhsdf89234jklnsf',
    label: 'Pig Butchering Peel Change Mule',
    ackNumber: 'NCRP-2026-DL-89102',
    victimName: 'Rameshwar K. Sharma',
    dateAdded: '2026-08-28',
    verdict: 'watch',
    category: 'Pig Butchering / Investment',
    amountInr: 196800
  }
];

export const CONVERGENCE_CLUSTERS: ConvergenceCluster[] = [
  {
    id: 'syndicate-htx-01',
    name: 'Syndicate "Golden Triangle" Hub - HTX/Huobi Hot Cluster',
    clusterDepositAddress: '1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ',
    jurisdiction: 'Seychelles / Hong Kong Corridor',
    totalCombinedLossInr: 8940000,
    totalCombinedLossBtc: 9.98,
    syndicateProfile: 'High-volume Southeast Asian cyber syndicate operating coordinated pig-butchering and task-fraud operations targeting Indian cyber space. Funds originate from different states but merge at the same deposit sub-account.',
    convergingCases: [
      {
        ackNumber: 'NCRP-2026-DL-90112',
        victimName: 'Amit Saxena (Delhi)',
        state: 'Delhi',
        scamType: 'Fake Stock Trading App ("BlackRock VIP")',
        amountInr: 3400000,
        amountBtc: 3.80,
        initialSuspectAddress: '1SyndicateDelhiVictimAddr111111111',
        hopsToConvergence: 3
      },
      {
        ackNumber: 'NCRP-2026-MH-91204',
        victimName: 'Kavita Deshmukh (Pune)',
        state: 'Maharashtra',
        scamType: 'Instagram Part-Time Job Scam',
        amountInr: 2140000,
        amountBtc: 2.39,
        initialSuspectAddress: '1SyndicatePuneVictimAddr2222222222',
        hopsToConvergence: 2
      },
      {
        ackNumber: 'NCRP-2026-KA-92088',
        victimName: 'Siddharth Iyer (Bengaluru)',
        state: 'Karnataka',
        scamType: 'Crypto Forex Arbitrage Bot Scam',
        amountInr: 3400000,
        amountBtc: 3.79,
        initialSuspectAddress: '1SyndicateBlrVictimAddr33333333333',
        hopsToConvergence: 3
      }
    ]
  }
];
