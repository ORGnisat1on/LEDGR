import { ForensicEngine } from '../src/services/analyzer';
import { CASE_STUDIES } from '../src/data/mockCases';

async function main() {
  console.log('=== ForensicEngine live test ===\n');

  // 1. Known case-study addresses (mock-indexed path)
  for (const cs of CASE_STUDIES.slice(0, 3)) {
    const r = await ForensicEngine.traceAddress(cs.address);
    console.log(`[case-study] ${cs.address}`);
    console.log(`  verdict=${r.verdict} nodes=${r.nodes.length} edges=${r.edges.length} attribution=${r.attribution?.name} tier=${r.attribution?.confidenceTier}`);
    console.log(`  rule=${r.contributingSignals.ruleScore} ml=${r.contributingSignals.mlConfidence} hops=${r.summaryStats.hopCount}`);
  }

  // 2. Synthetic path — random unknown address
  const r2 = await ForensicEngine.traceAddress('bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh');
  console.log(`\n[synthetic] bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh`);
  console.log(`  verdict=${r2.verdict} nodes=${r2.nodes.length} edges=${r2.edges.length} attribution=${r2.attribution?.name}`);
  console.log(`  ruleScore=${r2.contributingSignals.ruleScore} mlScore=${r2.contributingSignals.mlScore}`);

  // 3. Hop-depth respected?
  const r3 = await ForensicEngine.traceAddress('some-random-unlisted-address-123', 5);
  console.log(`\n[hopDepth=5] requested=5 got=${r3.hopDepth} edges=${r3.edges.length}`);

  // 4. Custom complaint override
  const r4 = await ForensicEngine.traceAddress('random-addr-xyz', 2, {
    id: 'c1', ackNumber: 'NCRP-TEST', victimName: 'T', victimState: 'KA', policeStation: 'PS',
    reportedDate: '2026-09-03', scamCategory: 'Ransomware Extortion', amountInr: 500000, amountBtc: 0.5,
    suspectAddress: 'random-addr-xyz', suspectTxHash: 'tx1', narrative: 'n'
  });
  console.log(`\n[complaint override] category=${r4.complaint?.scamCategory} amountInr=${r4.complaint?.amountInr} (expected Ransomware/500000)`);
  console.log(`  mixerProximityDetected=${r4.contributingSignals.ruleDetails.mixerProximityDetected}`);

  // 5. Consistency: same address twice = identical deterministic result?
  const a = await ForensicEngine.traceAddress('determinism-check-addr');
  const b = await ForensicEngine.traceAddress('determinism-check-addr');
  console.log(`\n[determinism] identical=${JSON.stringify(a) === JSON.stringify(b)}`);
}
main().catch(e => { console.error('TEST FAILURE:', e); process.exit(1); });
