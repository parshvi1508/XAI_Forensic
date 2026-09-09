import {
  loadStabilityData,
  loadDeletionData,
  computeCategoryStats,
  computeDeletionStats,
  findCounterexamples,
} from "./load-audit-data";

function jaccardColor(val) {
  if (val >= 0.8) return "text-[#3ecf6f]";
  if (val >= 0.6) return "text-[#e0a052]";
  return "text-[#e05252]";
}

function jaccardBg(val) {
  if (val >= 0.8) return "bg-[#0d1f17] border-[#1e4030]";
  if (val >= 0.6) return "bg-[#1a1400] border-[#3a2e00]";
  return "bg-[#1a0d0d] border-[#5c2020]";
}

function formatCategory(cat) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatCard({ label, value, status }) {
  const border =
    status === "pass" ? "border-[#1e4030]" :
    status === "fail" ? "border-[#5c2020]" :
    "border-[#252d38]";
  const bg =
    status === "pass" ? "bg-[#0d1f17]" :
    status === "fail" ? "bg-[#1a0d0d]" :
    "bg-[#0c0e12]";
  const valueColor =
    status === "pass" ? "text-[#3ecf6f]" :
    status === "fail" ? "text-[#e05252]" :
    "text-[#dce3ec]";

  return (
    <div className={`border rounded-md px-4 py-3 ${border} ${bg}`}>
      <p className="font-sans text-[11px] text-[#5a6a7e] mb-1">{label}</p>
      <p className={`font-mono text-xl font-bold tabular-nums ${valueColor}`}>{value}</p>
    </div>
  );
}

export default function AuditPage() {
  const stabilityData = loadStabilityData();
  const deletionData = loadDeletionData();
  const categoryStats = computeCategoryStats(stabilityData);
  const deletionStats = computeDeletionStats(deletionData);
  const counterexamples = findCounterexamples(deletionData);

  const meanJaccard = stabilityData.length
    ? stabilityData.reduce((s, r) => s + r.jaccard, 0) / stabilityData.length
    : 0;
  const perfectCount = stabilityData.filter((r) => r.jaccard >= 0.9999).length;
  const dirCorrectRate = deletionStats ? deletionStats.directionCorrectRate : 0;
  const flipRate = deletionStats ? deletionStats.flipRate : 0;

  const noData = stabilityData.length === 0 && deletionData.length === 0;

  return (
    <div className="min-h-screen bg-[#080a0c] text-[#dce3ec]">
      <header className="border-b border-[#252d38] px-4 sm:px-6 lg:px-8 py-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <a href="/" className="font-mono text-sm font-bold tracking-[0.2em] uppercase text-[#58a6ff] hover:underline">
            XAI Forensics
          </a>
          <p className="font-sans text-sm text-[#96a8be] mt-1 leading-snug">
            Pre-registered audit results: {stabilityData.length} inputs, 5 seeds, {stabilityData.length * 5} LIME runs
          </p>
        </div>
        <div className="flex items-center gap-4">
          <a href="/" className="font-mono text-[11px] text-[#96a8be] hover:text-[#58a6ff] transition-colors tracking-wide">
            Back to Tool
          </a>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">

        {noData && (
          <section className="border border-[#252d38] rounded-md bg-[#0c0e12] p-6 text-center">
            <p className="font-mono text-sm text-[#e0a052]">
              No audit data found. Run <code className="bg-[#1a1f28] px-1.5 py-0.5 rounded text-[#58a6ff]">make audit</code> or <code className="bg-[#1a1f28] px-1.5 py-0.5 rounded text-[#58a6ff]">lime-audit run</code> to generate results.
            </p>
          </section>
        )}

        {!noData && (
          <>
            {/* Summary stats */}
            <section>
              <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
                Summary
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard
                  label="Mean Jaccard (top-5)"
                  value={meanJaccard.toFixed(2)}
                  status={meanJaccard >= 0.6 ? "pass" : "fail"}
                />
                <StatCard
                  label="Direction Correct"
                  value={`${(dirCorrectRate * 100).toFixed(1)}%`}
                  status={dirCorrectRate >= 0.7 ? "pass" : "fail"}
                />
                <StatCard
                  label="Label Flip Rate"
                  value={`${(flipRate * 100).toFixed(1)}%`}
                  status="neutral"
                />
                <StatCard
                  label="Perfect Stability"
                  value={`${perfectCount}/${stabilityData.length}`}
                  status="neutral"
                />
              </div>
            </section>

            {/* Category heatmap */}
            {categoryStats.length > 0 && (
              <section>
                <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
                  Stability by Category
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {categoryStats.map((c) => (
                    <div
                      key={c.category}
                      className={`border rounded-md px-4 py-3 ${jaccardBg(c.jaccard)}`}
                    >
                      <p className="font-sans text-xs text-[#96a8be] mb-1">{c.label} ({c.count})</p>
                      <p className={`font-mono text-lg font-bold tabular-nums ${jaccardColor(c.jaccard)}`}>
                        {c.jaccard.toFixed(4)}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Full results table */}
            <section>
              <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
                Per-Input Stability ({stabilityData.length} inputs, 5 seeds each)
              </h2>
              <div className="overflow-x-auto rounded-md border border-[#252d38]">
                <table className="w-full text-sm" role="table">
                  <thead>
                    <tr className="border-b border-[#252d38] bg-[#0c0e12]">
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-left px-3 py-2">ID</th>
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-left px-3 py-2">Category</th>
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-left px-3 py-2">Text</th>
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-right px-3 py-2">Mean Jaccard</th>
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-right px-3 py-2">Min Jaccard</th>
                      {stabilityData.some((r) => r.ciLower != null) && (
                        <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-right px-3 py-2">95% CI</th>
                      )}
                      <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-center px-3 py-2">Top-1 Unanimous</th>
                      {stabilityData.some((r) => r.tokenMismatch != null) && (
                        <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-right px-3 py-2">Token Mismatch</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {stabilityData.map((row) => (
                      <tr key={row.id} className="border-b border-[#1a1f28] hover:bg-[#0c0e12] transition-colors">
                        <td className="font-mono text-xs text-[#96a8be] px-3 py-2 tabular-nums">{row.id}</td>
                        <td className="font-sans text-xs text-[#96a8be] px-3 py-2">{formatCategory(row.category)}</td>
                        <td className="font-sans text-xs text-[#dce3ec] px-3 py-2 max-w-[300px] truncate" title={row.text}>{row.text}</td>
                        <td className={`font-mono text-xs font-semibold text-right px-3 py-2 tabular-nums ${jaccardColor(row.jaccard)}`}>
                          {row.jaccard.toFixed(4)}
                        </td>
                        <td className={`font-mono text-xs text-right px-3 py-2 tabular-nums ${jaccardColor(row.minJaccard)}`}>
                          {row.minJaccard.toFixed(4)}
                        </td>
                        {stabilityData.some((r) => r.ciLower != null) && (
                          <td className="font-mono text-xs text-right px-3 py-2 tabular-nums text-[#96a8be]">
                            {row.ciLower != null ? `[${row.ciLower.toFixed(2)}, ${row.ciUpper.toFixed(2)}]` : "—"}
                          </td>
                        )}
                        <td className="font-mono text-xs text-center px-3 py-2">
                          {row.unanimous ? (
                            <span className="text-[#3ecf6f]">Yes</span>
                          ) : (
                            <span className="text-[#e05252]">No</span>
                          )}
                        </td>
                        {stabilityData.some((r) => r.tokenMismatch != null) && (
                          <td className="font-mono text-xs text-right px-3 py-2 tabular-nums text-[#e0a052]">
                            {row.tokenMismatch != null ? `+${row.tokenMismatch}` : "—"}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Deletion faithfulness summary */}
            {deletionStats && (
              <section>
                <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
                  Deletion Faithfulness
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                  <StatCard
                    label="Tested"
                    value={deletionStats.total}
                    status="neutral"
                  />
                  <StatCard
                    label="Direction Correct"
                    value={`${(deletionStats.directionCorrectRate * 100).toFixed(1)}%`}
                    status={deletionStats.directionCorrectRate >= 0.7 ? "pass" : "fail"}
                  />
                  <StatCard
                    label="Label Flips"
                    value={`${deletionStats.flipCount}/${deletionStats.total}`}
                    status="neutral"
                  />
                  <StatCard
                    label="Mean |Delta|"
                    value={deletionStats.meanAbsDelta.toFixed(4)}
                    status="neutral"
                  />
                </div>
              </section>
            )}

            {/* Counterexamples */}
            {counterexamples.length > 0 && (
              <section>
                <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
                  Direction-Incorrect Counterexamples ({counterexamples.length} of {deletionStats?.total || "?"})
                </h2>
                <p className="font-sans text-sm text-[#96a8be] mb-4 leading-relaxed">
                  In these cases, LIME predicted that removing a token would shift the score in one direction,
                  but the actual effect went the opposite way. This happens when the model has redundant evidence
                  and no single token is individually necessary for the prediction.
                </p>
                <div className="space-y-4">
                  {counterexamples.map((ex) => (
                    <div key={`${ex.id}-${ex.removedToken}`} className="border border-[#252d38] rounded-md bg-[#0c0e12] p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-sans text-sm text-[#dce3ec]">
                          <span className="font-mono text-[#5a6a7e] mr-2">#{ex.id}</span>
                          &ldquo;{ex.text}&rdquo;
                        </p>
                        <span className="font-mono text-[10px] tracking-wider uppercase text-[#e05252] border border-[#5c2020] bg-[#1a0d0d] rounded px-2 py-0.5 shrink-0">
                          Direction Incorrect
                        </span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div>
                          <span className="font-mono text-[10px] text-[#5a6a7e] uppercase tracking-wider block mb-0.5">Removed Token</span>
                          <span className="font-mono font-semibold text-[#e0a052]">{ex.removedToken}</span>
                        </div>
                        <div>
                          <span className="font-mono text-[10px] text-[#5a6a7e] uppercase tracking-wider block mb-0.5">LIME Weight</span>
                          <span className={`font-mono font-semibold tabular-nums ${ex.limeWeight >= 0 ? "text-[#3ecf6f]" : "text-[#e05252]"}`}>
                            {ex.limeWeight >= 0 ? "+" : ""}{ex.limeWeight.toFixed(4)}
                          </span>
                        </div>
                        <div>
                          <span className="font-mono text-[10px] text-[#5a6a7e] uppercase tracking-wider block mb-0.5">Actual Delta</span>
                          <span className="font-mono font-semibold tabular-nums text-[#dce3ec]">
                            {ex.delta >= 0 ? "+" : ""}{ex.delta.toFixed(6)}
                          </span>
                        </div>
                        <div>
                          <span className="font-mono text-[10px] text-[#5a6a7e] uppercase tracking-wider block mb-0.5">Label Change</span>
                          <span className="font-mono font-semibold text-[#96a8be]">
                            {ex.originalLabel === ex.modifiedLabel ? "No flip" : `${ex.originalLabel} → ${ex.modifiedLabel}`}
                          </span>
                        </div>
                      </div>
                      <p className="font-sans text-xs text-[#96a8be] leading-relaxed">{ex.explanation}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Methodology note */}
            <section className="border-t border-[#252d38] pt-8">
              <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-3">
                Methodology
              </h2>
              <div className="font-sans text-sm text-[#96a8be] space-y-2 leading-relaxed">
                <p>
                  Protocol pre-registered before data collection. {stabilityData.length} inputs across {categoryStats.length} categories,
                  each run through LIME with 5 different random seeds (42, 123, 456, 789, 1024)
                  producing {stabilityData.length * 5} total LIME attribution sets.
                </p>
                <p>
                  Stability measured via pairwise Jaccard similarity on top-5 tokens across all
                  C(5,2)=10 seed pairs per input. Faithfulness measured via single-token deletion:
                  remove the highest-weighted token and measure whether the confidence shift matches
                  the predicted direction.
                </p>
                <p>
                  Thresholds: Jaccard &ge; 0.6 (pass), direction correctness &ge; 70% (pass).
                  Full protocol and failure analysis available in the repository.
                </p>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
