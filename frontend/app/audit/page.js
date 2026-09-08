"use client";

const STABILITY_DATA = [
  { id: 1, category: "negation_minimal_pairs", text: "I am not entirely unhappy with this result.", jaccard: 0.5714, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 2, category: "negation_minimal_pairs", text: "This is not good.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 3, category: "negation_minimal_pairs", text: "This is good.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 4, category: "negation_minimal_pairs", text: "I would not recommend this to anyone.", jaccard: 0.6857, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 5, category: "negation_minimal_pairs", text: "Nothing about this experience was disappointing.", jaccard: 0.7333, minJaccard: 0.6667, stable: true, unanimous: false },
  { id: 6, category: "lexical_shortcuts", text: "The movie was terrible but I loved every minute of it.", jaccard: 0.5, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 7, category: "lexical_shortcuts", text: "Excellent packaging, but the product itself is useless.", jaccard: 0.7667, minJaccard: 0.6667, stable: true, unanimous: true },
  { id: 8, category: "lexical_shortcuts", text: "I love how badly this was designed.", jaccard: 0.8, minJaccard: 0.6667, stable: true, unanimous: true },
  { id: 9, category: "lexical_shortcuts", text: "Fine.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 10, category: "lexical_shortcuts", text: "Absolutely phenomenal waste of my time.", jaccard: 0.8, minJaccard: 0.6667, stable: true, unanimous: true },
  { id: 11, category: "ambiguity", text: "It was okay, I guess.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 12, category: "ambiguity", text: "That is one way to do it.", jaccard: 0.8667, minJaccard: 0.6667, stable: true, unanimous: false },
  { id: 13, category: "ambiguity", text: "I have seen worse.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 14, category: "ambiguity", text: "The service was exactly what I expected.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: false },
  { id: 15, category: "ambiguity", text: "It is what it is.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 16, category: "distribution_style_shift", text: "ngl this slaps fr fr no cap", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: false },
  { id: 17, category: "distribution_style_shift", text: "The patient presents with acute exacerbation of chronic symptoms.", jaccard: 0.5714, minJaccard: 0.4286, stable: true, unanimous: false },
  { id: 18, category: "distribution_style_shift", text: "Revenue increased 12% YoY driven by strong Q4 performance.", jaccard: 0.5714, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 19, category: "distribution_style_shift", text: "lmaooo this is so bad its good", jaccard: 0.6762, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 20, category: "distribution_style_shift", text: "Per the attached memo, please advise on next steps.", jaccard: 0.8, minJaccard: 0.6667, stable: true, unanimous: false },
  { id: 21, category: "strong_baselines", text: "This is the best product I have ever purchased.", jaccard: 0.4643, minJaccard: 0.25, stable: true, unanimous: false },
  { id: 22, category: "strong_baselines", text: "Terrible experience, complete waste of money.", jaccard: 0.7, minJaccard: 0.6667, stable: true, unanimous: true },
  { id: 23, category: "strong_baselines", text: "I absolutely love everything about this.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: false },
  { id: 24, category: "strong_baselines", text: "This is awful and I regret buying it.", jaccard: 0.5238, minJaccard: 0.4286, stable: true, unanimous: false },
  { id: 25, category: "strong_baselines", text: "The quality exceeded all my expectations and I am thrilled.", jaccard: 0.6762, minJaccard: 0.4286, stable: true, unanimous: true },
  { id: 26, category: "edge_cases", text: "good good good good good", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 27, category: "edge_cases", text: "The the the the movie was great.", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
  { id: 28, category: "edge_cases", text: "I think that maybe it could possibly be somewhat decent.", jaccard: 0.7714, minJaccard: 0.4286, stable: true, unanimous: false },
  { id: 29, category: "edge_cases", text: "Amazing! Horrible! Amazing! Horrible!", jaccard: 1.0, minJaccard: 1.0, stable: true, unanimous: true },
];

const CATEGORY_JACCARD = [
  { category: "negation_minimal_pairs", label: "Negation", jaccard: 0.7981 },
  { category: "lexical_shortcuts", label: "Lexical Shortcuts", jaccard: 0.7733 },
  { category: "ambiguity", label: "Ambiguity", jaccard: 0.9733 },
  { category: "distribution_style_shift", label: "Distribution Shift", jaccard: 0.7238 },
  { category: "strong_baselines", label: "Strong Baselines", jaccard: 0.6729 },
  { category: "edge_cases", label: "Edge Cases", jaccard: 0.9428 },
];

const COUNTEREXAMPLES = [
  {
    id: 5,
    text: "Nothing about this experience was disappointing.",
    removedToken: "experience",
    limeWeight: -0.1825,
    originalLabel: "positive",
    originalScore: 0.9921,
    modifiedLabel: "positive",
    modifiedScore: 0.9896,
    delta: -0.0024,
    explanation: "LIME assigned a negative weight to 'experience' (predicting removal would increase positive score), but removing it slightly decreased the positive score instead. The model's confidence was so high that removing any single token had negligible effect.",
  },
  {
    id: 22,
    text: "Terrible experience, complete waste of money.",
    removedToken: "Terrible",
    limeWeight: -0.3175,
    originalLabel: "negative",
    originalScore: 0.0002,
    modifiedLabel: "negative",
    modifiedScore: 0.0002,
    delta: -0.000002,
    explanation: "LIME assigned a negative weight to 'Terrible' (predicting removal would increase positive score), but removing it had virtually zero effect. The remaining tokens ('complete waste of money') are sufficient to maintain the negative prediction with near-identical confidence.",
  },
  {
    id: 26,
    text: "good good good good good",
    removedToken: "good",
    limeWeight: 0.0210,
    originalLabel: "positive",
    originalScore: 0.9998,
    modifiedLabel: "positive",
    modifiedScore: 0.9998,
    delta: 0.000001,
    explanation: "LIME assigned a positive weight to 'good' (predicting removal would decrease positive score), but removing one instance of 'good' from five had no measurable effect. Redundant evidence means no single token is individually necessary.",
  },
];

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

export default function AuditPage() {
  return (
    <div className="min-h-screen bg-[#080a0c] text-[#dce3ec]">
      <header className="border-b border-[#252d38] px-4 sm:px-6 lg:px-8 py-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <a href="/" className="font-mono text-sm font-bold tracking-[0.2em] uppercase text-[#58a6ff] hover:underline">
            XAI Forensics
          </a>
          <p className="font-sans text-sm text-[#96a8be] mt-1 leading-snug">
            Pre-registered audit results: 30 inputs, 5 seeds, 150 LIME runs
          </p>
        </div>
        <div className="flex items-center gap-4">
          <a href="/" className="font-mono text-[11px] text-[#96a8be] hover:text-[#58a6ff] transition-colors tracking-wide">
            Back to Tool
          </a>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">

        {/* Summary stats */}
        <section>
          <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
            Summary
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Mean Jaccard (top-5)" value="0.81" status="pass" />
            <StatCard label="Direction Correct" value="89.3%" status="pass" />
            <StatCard label="Label Flip Rate" value="39.3%" status="neutral" />
            <StatCard label="Perfect Stability" value="12/29" status="neutral" />
          </div>
        </section>

        {/* Category heatmap */}
        <section>
          <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
            Stability by Category
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {CATEGORY_JACCARD.map((c) => (
              <div
                key={c.category}
                className={`border rounded-md px-4 py-3 ${jaccardBg(c.jaccard)}`}
              >
                <p className="font-sans text-xs text-[#96a8be] mb-1">{c.label}</p>
                <p className={`font-mono text-lg font-bold tabular-nums ${jaccardColor(c.jaccard)}`}>
                  {c.jaccard.toFixed(4)}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Full results table */}
        <section>
          <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
            Per-Input Stability (29 inputs, 5 seeds each)
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
                  <th className="font-mono text-[10px] tracking-wider uppercase text-[#5a6a7e] text-center px-3 py-2">Top-1 Unanimous</th>
                </tr>
              </thead>
              <tbody>
                {STABILITY_DATA.map((row) => (
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
                    <td className="font-mono text-xs text-center px-3 py-2">
                      {row.unanimous ? (
                        <span className="text-[#3ecf6f]">Yes</span>
                      ) : (
                        <span className="text-[#e05252]">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Counterexamples */}
        <section>
          <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-4">
            Direction-Incorrect Counterexamples (3 of 28)
          </h2>
          <p className="font-sans text-sm text-[#96a8be] mb-4 leading-relaxed">
            In these cases, LIME predicted that removing a token would shift the score in one direction,
            but the actual effect went the opposite way. This happens when the model has redundant evidence
            and no single token is individually necessary for the prediction.
          </p>
          <div className="space-y-4">
            {COUNTEREXAMPLES.map((ex) => (
              <div key={ex.id} className="border border-[#252d38] rounded-md bg-[#0c0e12] p-4 space-y-3">
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
                      {ex.originalLabel === ex.modifiedLabel ? "No flip" : `${ex.originalLabel} -> ${ex.modifiedLabel}`}
                    </span>
                  </div>
                </div>
                <p className="font-sans text-xs text-[#96a8be] leading-relaxed">{ex.explanation}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Methodology note */}
        <section className="border-t border-[#252d38] pt-8">
          <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-[#58a6ff] font-semibold mb-3">
            Methodology
          </h2>
          <div className="font-sans text-sm text-[#96a8be] space-y-2 leading-relaxed">
            <p>
              Protocol pre-registered before data collection. 30 inputs across 6 categories,
              each run through LIME with 5 different random seeds (42, 123, 456, 789, 1024)
              producing 150 total LIME attribution sets.
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

      </main>
    </div>
  );
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
