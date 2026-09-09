"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SAMPLE = "I am not entirely unhappy with this result.";

const INITIAL = { why: null, flip: null, disagree: null };
const ERRORS  = { why: null, flip: null, disagree: null };

export default function Home() {
  const [text, setText]       = useState(SAMPLE);
  const [results, setResults] = useState(INITIAL);
  const [errors, setErrors]   = useState(ERRORS);
  const [loading, setLoading] = useState(false);
  const [fatalError, setFatalError] = useState(null);

  async function post(endpoint) {
    const res = await fetch(`${API}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || `${endpoint} returned ${res.status}`);
    }
    return res.json();
  }

  const tooLong = text.length > 1000;

  async function analyse() {
    if (!text.trim() || tooLong) return;
    setLoading(true);
    setResults(INITIAL);
    setErrors(ERRORS);
    setFatalError(null);

    let settled;
    try {
      settled = await Promise.allSettled([
        post("why"),
        post("flip"),
        post("disagree"),
      ]);
    } catch (_) {
      // network-level failure before any response
      setFatalError("Cannot reach the backend. Make sure the server is running on http://localhost:8000.");
      setLoading(false);
      return;
    }

    const [whyResult, flipResult, disagreeResult] = settled;

    // If all three failed with a network error, show the banner
    const allFailed = settled.every((r) => r.status === "rejected");
    const networkError = settled.some((r) =>
      r.status === "rejected" && r.reason?.message?.includes("fetch")
    );
    if (allFailed && networkError) {
      setFatalError("Cannot reach the backend. Make sure the server is running on http://localhost:8000.");
      setLoading(false);
      return;
    }

    setResults({
      why:     whyResult.status     === "fulfilled" ? whyResult.value     : null,
      flip:    flipResult.status    === "fulfilled" ? flipResult.value    : null,
      disagree: disagreeResult.status === "fulfilled" ? disagreeResult.value : null,
    });
    setErrors({
      why:     whyResult.status     === "rejected" ? whyResult.reason.message     : null,
      flip:    flipResult.status    === "rejected" ? flipResult.reason.message    : null,
      disagree: disagreeResult.status === "rejected" ? disagreeResult.reason.message : null,
    });

    setLoading(false);
  }

  const hasAnyResult = results.why || results.flip || results.disagree;

  return (
    <div className="min-h-screen bg-[#080a0c] text-[#dce3ec]">

      {/* Header */}
      <header className="border-b border-[#252d38] px-4 sm:px-6 lg:px-8 py-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-sm font-bold tracking-[0.2em] uppercase text-[#58a6ff]">
            XAI Forensics
          </h1>
          <p className="font-sans text-sm text-[#96a8be] mt-1 leading-snug">
            Model decision inspection with attribution, counterfactuals, and disagreement
          </p>
        </div>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/parshvi1508/XAI_Forensic"
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[11px] text-[#96a8be] hover:text-[#58a6ff] transition-colors tracking-wide"
          >
            Source
          </a>
          <a
            href="https://jainparshvi-xai-forensics-backend.hf.space/docs"
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[11px] text-[#96a8be] hover:text-[#58a6ff] transition-colors tracking-wide"
          >
            API Docs
          </a>
          <a
            href="/audit"
            className="font-mono text-[11px] text-[#96a8be] hover:text-[#58a6ff] transition-colors tracking-wide"
          >
            Audit
          </a>
          {hasAnyResult && !loading && (
            <span className="font-mono text-[10px] tracking-widest uppercase text-[#3ecf6f] border border-[#1e4030] bg-[#0d1f17] rounded px-2 py-1 hidden sm:inline">
              Analysis complete
            </span>
          )}
        </div>
      </header>

      <main className="px-4 sm:px-6 lg:px-8 py-8 sm:py-10 max-w-7xl mx-auto space-y-8 sm:space-y-10">

        <HeroSection />

        <HowToRead />

        {/* Fatal / backend-down error */}
        {fatalError && (
          <div
            id="fatal-error-banner"
            className="flex items-start gap-3 bg-[#1a0d0d] border border-[#5c2020] rounded-md px-5 py-4"
          >
            <span className="font-mono text-[#e05252] text-xs mt-0.5 shrink-0 font-bold">[ERROR]</span>
            <p className="font-sans text-sm text-[#f0a0a0] leading-relaxed">{fatalError}</p>
          </div>
        )}

        {/* Input area */}
        <section className="space-y-4">
          <ExampleCards onSelect={(s) => setText(s)} />
          <div className="flex items-center justify-between">
            <label
              htmlFor="input-text"
              className="font-mono text-xs font-semibold tracking-[0.15em] uppercase text-[#a0b0c4]"
            >
              Input text
            </label>
            <span className={`font-mono text-[11px] tracking-wide ${tooLong ? "text-[#e05252] font-semibold" : "text-[#6b7a8d]"}`}>
              {text.length} / 1000
            </span>
          </div>
          <textarea
            id="input-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste or type text to analyse..."
            rows={4}
            className="
              font-sans w-full bg-[#0d1117] border border-[#2e3d50]
              rounded-md px-5 py-4 text-base text-[#dce3ec]
              placeholder-[#4a5e72]
              focus:outline-none focus:border-[#58a6ff] focus:ring-1 focus:ring-[#58a6ff]/30
              resize-vertical transition-colors leading-relaxed
            "
          />
          {tooLong && (
            <p className="font-sans text-sm text-[#e05252]">
              Text is too long. Keep input under 1000 characters for reliable analysis.
            </p>
          )}
          <div className="flex items-center gap-5">
            <button
              id="analyse-btn"
              onClick={analyse}
              disabled={loading || !text.trim() || tooLong}
              className="
                font-mono px-7 py-2.5 text-xs font-bold tracking-[0.15em] uppercase
                bg-[#58a6ff] text-[#080a0c] rounded-md
                hover:bg-[#79bbff]
                disabled:opacity-25 disabled:cursor-not-allowed
                transition-colors
              "
            >
              {loading ? "Analysing..." : "Analyse"}
            </button>
            {loading && (
              <span className="font-sans text-sm text-[#96a8be]">
                Running three forensic checks...
              </span>
            )}
          </div>
        </section>

        {/* Forensic summary */}
        <ForensicSummary results={results} />

        {/* Confidence note */}
        {hasAnyResult && !loading && (
          <p className="font-sans text-[12px] text-[#5a6a7e] leading-relaxed">
            Confidence is the model's own score for its current verdict. High confidence does not guarantee correctness.
          </p>
        )}

        {/* Panels */}
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          <WhyPanel     data={results.why}     error={errors.why}     loading={loading}  text={text} />
          <FlipPanel    data={results.flip}    error={errors.flip}    loading={loading} />
          <DisagreePanel data={results.disagree} error={errors.disagree} loading={loading} />
        </section>

        <MethodologySection />
      </main>
    </div>
  );
}

/* ---- shared primitives ---- */

function formatDuration(ms) {
  if (ms == null) return null;
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function PanelShell({ id, title, tag, description, durationMs, children }) {
  return (
    <div
      id={id}
      className="bg-[#0d1117] border border-[#252d38] rounded-lg p-4 sm:p-6 space-y-5 min-h-[280px] flex flex-col min-w-0"
    >
      {/* Panel header */}
      <div className="space-y-2 pb-4 border-b border-[#252d38]">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#5a6a7e] font-semibold">
            {tag}
          </span>
          <span className="font-mono text-xs font-bold text-[#58a6ff] tracking-[0.15em] uppercase">
            {title}
          </span>
        </div>
        {formatDuration(durationMs) && (
          <span className="font-mono text-[10px] text-[#5a6a7e] tracking-wide">
            Runtime: {formatDuration(durationMs)}
          </span>
        )}
        {description && (
          <p className="font-sans text-[15px] text-[#96a8be] leading-loose">{description}</p>
        )}
      </div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function Field({ label, value, highlight }) {
  const colorMap = {
    green:  "text-[#3ecf6f]",
    red:    "text-[#e05252]",
    yellow: "text-[#e0a052]",
    blue:   "text-[#58a6ff]",
  };
  const valueColor = highlight ? colorMap[highlight] : "text-[#dce3ec]";
  return (
    <div className="space-y-1.5">
      <span className="font-mono block text-[12px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
        {label}
      </span>
      <span className={`font-mono block text-lg font-semibold break-words ${valueColor}`}>{value}</span>
    </div>
  );
}

function StatusRow({ label, value, highlight }) {
  const colorMap = {
    green:  "text-[#3ecf6f] bg-[#0d1f17] border-[#1e4030]",
    red:    "text-[#e05252] bg-[#1a0d0d] border-[#3a1515]",
    yellow: "text-[#e0a052] bg-[#1a1400] border-[#3a2e00]",
  };
  const cls = highlight ? colorMap[highlight] : "text-[#dce3ec] bg-[#1c2128] border-[#2a3441]";
  return (
    <div className="flex items-center justify-between pt-4 mt-2 border-t border-[#252d38]">
      <span className="font-mono text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
        {label}
      </span>
      <span className={`font-mono text-xs font-bold tracking-widest px-2.5 py-1 rounded border ${cls}`}>
        {value}
      </span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-3 bg-[#1c2128] rounded w-1/3" />
      <div className="h-4 bg-[#1c2128] rounded w-2/3" />
      <div className="h-3 bg-[#1c2128] rounded w-1/4 mt-4" />
      <div className="h-4 bg-[#1c2128] rounded w-1/2" />
      <div className="h-3 bg-[#1c2128] rounded w-1/3 mt-4" />
      <div className="space-y-1.5 mt-1">
        {[70, 55, 40, 30].map((w, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="h-2.5 bg-[#1c2128] rounded w-16" />
            <div className="h-2 bg-[#1c2128] rounded flex-1" style={{ maxWidth: `${w}%` }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[140px] gap-2.5 text-center">
      <div className="w-10 h-px bg-[#2e3d50]" />
      <p className="font-sans text-sm text-[#5a6a7e]">Waiting for analysis</p>
      <div className="w-10 h-px bg-[#2e3d50]" />
    </div>
  );
}

function ErrorBox({ message }) {
  return (
    <div className="flex items-start gap-3 bg-[#1a0d0d] border border-[#3a1515] rounded px-4 py-3">
      <span className="font-mono text-[#e05252] text-[10px] font-bold shrink-0 mt-0.5">[ERR]</span>
      <p className="font-sans text-sm text-[#f0a0a0] leading-relaxed">{message}</p>
    </div>
  );
}

/* ---- WHY panel ---- */

function WhyPanel({ data, error, loading, text }) {
  return (
    <PanelShell
      id="panel-why"
      title="WHY"
      tag="01 - Attribution"
      description="Which tokens pushed the model toward its prediction, and by how much."
      durationMs={data?.duration_ms}
    >
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Model verdict"
              value={data.label ?? "-"}
              highlight={
                typeof data.label === "string"
                  ? data.label.toLowerCase().includes("pos") ? "green"
                  : data.label.toLowerCase().includes("neg") ? "red"
                  : "blue"
                  : null
              }
            />
            <Field
              label="Confidence"
              value={
                typeof data.confidence === "number"
                  ? `${(data.confidence * 100).toFixed(1)}%`
                  : data.confidence ?? "-"
              }
            />
          </div>

          {typeof data.confidence === "number" && data.confidence > 0.95 && (
            <div className="flex items-start gap-3 bg-[#1a1400] border border-[#3a2e00] rounded px-4 py-3">
              <span className="font-mono text-[#e0a052] text-[10px] font-bold shrink-0 mt-0.5">[WARN]</span>
              <p className="font-sans text-sm text-[#e0c080] leading-relaxed">
                Attribution unstable at this confidence level. The model found redundant
                evidence across multiple tokens. Prediction is reliable but the token
                breakdown is not. Audit data shows mean Jaccard similarity of 0.46 on
                inputs with confidence above 95%.
              </p>
            </div>
          )}

          {text && text.split(/\s+/).filter(Boolean).length > 50 && (
            <div className="flex items-start gap-3 bg-[#1a1400] border border-[#3a2e00] rounded px-4 py-3">
              <span className="font-mono text-[#e0a052] text-[10px] font-bold shrink-0 mt-0.5">[NOTE]</span>
              <p className="font-sans text-sm text-[#e0c080] leading-relaxed">
                Long input (50+ words). LIME perturbation space grows combinatorially
                with input length. Token attributions may be less stable.
              </p>
            </div>
          )}

          {Array.isArray(data.tokens) && data.tokens.length > 0 ? (
            <div className="space-y-2">
              {(() => {
                const st = data.tokens.reduce((a, b) => Math.abs(a.weight) >= Math.abs(b.weight) ? a : b);
                const dir = st.weight >= 0 ? "positive" : "negative";
                return (
                  <p className="font-sans text-[14px] text-[#b0c0d4] leading-loose mb-3">
                    The word <span className="font-mono font-semibold text-[#e0a052]">{st.token}</span> had the strongest pull toward the {dir} verdict. Green bars pushed the model toward positive. Red bars pushed toward negative.
                  </p>
                );
              })()}
              <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
                Word influence
              </span>
              <TokenBars tokens={data.tokens} />
              <p className="font-sans text-[12px] text-[#5a6a7e] leading-relaxed mt-2">
                These are LIME estimates. They show local influence on this prediction, not global model behavior.
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="font-sans text-sm text-[#5a6a7e]">No token data returned.</p>
              {data.tokens !== undefined && (
                <pre className="font-mono text-[10px] text-[#4a5568] bg-[#0a0d10] rounded px-2 py-1 overflow-x-auto">
                  {JSON.stringify(data.tokens, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </PanelShell>
  );
}

function TokenBars({ tokens }) {
  // accepts [[token, weight], ...] or [{token, weight}, ...]
  const rows = tokens.map((t) =>
    Array.isArray(t) ? { token: t[0], weight: t[1] } : t
  );
  const maxAbs = Math.max(...rows.map((t) => Math.abs(t.weight)), 0.0001);

  return (
    <div className="space-y-1.5">
      {rows.slice(0, 12).map((t, i) => {
        const pct     = (Math.abs(t.weight) / maxAbs) * 100;
        const positive = t.weight >= 0;
        const barColor = positive ? "bg-[#1e4d2e]" : "bg-[#4d1e1e]";
        const fillColor = positive ? "bg-[#3ecf6f]" : "bg-[#e05252]";
        const numColor  = positive ? "text-[#3ecf6f]" : "text-[#e05252]";
        return (
          <div key={i} className="flex items-center gap-2">
            <span
              className="font-mono w-16 sm:w-[6.5rem] shrink-0 truncate text-[13px] text-[#b0c0d4] font-medium"
              title={t.token}
            >
              {t.token}
            </span>
            <div className={`flex-1 ${barColor} rounded h-2.5 overflow-hidden`}>
              <div
                className={`h-full ${fillColor} rounded`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={`font-mono w-14 text-right font-semibold tabular-nums text-[13px] ${numColor}`}>
              {t.weight >= 0 ? "+" : ""}
              {typeof t.weight === "number" ? t.weight.toFixed(3) : t.weight}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ---- FLIP panel ---- */

function FlipPanel({ data, error, loading }) {
  return (
    <PanelShell
      id="panel-flip"
      title="FLIP"
      tag="02 - Counterfactual"
      description="Remove the highest-impact token and measure whether the prediction label changes."
      durationMs={data?.duration_ms}
    >
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {(() => {
            const word = data.key_word;
            const flipped = data.flipped;
            const shift = Math.round(Math.abs(data.delta) * 100);
            const origConf = Math.round(data.original_confidence * 100);
            const modConf = Math.round(data.modified_confidence * 100);
            let msg;
            if (flipped === true) {
              msg = `We removed the word "${word}" and ran the model again. The verdict flipped from ${data.original_label} to ${data.modified_label}. Model confidence went from ${origConf}% to ${modConf}%. One word controlled this verdict.`;
            } else if (shift >= 20) {
              msg = `We removed the word "${word}" and ran the model again. The verdict held, but model confidence shifted by ${shift} points. The prediction is sensitive to this word even though it did not flip.`;
            } else {
              msg = `We removed the word "${word}" and ran the model again. The verdict held and confidence barely changed. This prediction does not depend heavily on one word.`;
            }
            return (
              <p className="font-sans text-[14px] text-[#b0c0d4] leading-loose mb-3">{msg}</p>
            );
          })()}
          {/* Fragility badge */}
          {(() => {
            let fragLabel, fragCls;
            if (data.flipped === true) {
              fragLabel = "FRAGILITY: HIGH";
              fragCls = "text-[#e05252] bg-[#1a0d0d] border-[#3a1515]";
            } else if (typeof data.delta === "number" && Math.abs(data.delta) >= 0.2) {
              fragLabel = "FRAGILITY: MEDIUM";
              fragCls = "text-[#e0a052] bg-[#1a1400] border-[#3a2e00]";
            } else {
              fragLabel = "FRAGILITY: LOW";
              fragCls = "text-[#3ecf6f] bg-[#0d1f17] border-[#1e4030]";
            }
            return (
              <span className={`font-mono text-[11px] uppercase font-bold px-3 py-1 rounded border inline-block mb-2 ${fragCls}`}>
                {fragLabel}
              </span>
            );
          })()}
          {/* Before removal */}
          <div className="space-y-1">
            <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
              Before removal
            </span>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Verdict" value={data.original_label ?? "-"} />
              <Field
                label="Confidence"
                value={
                  typeof data.original_confidence === "number"
                    ? `${(data.original_confidence * 100).toFixed(1)}%`
                    : data.original_confidence ?? "-"
                }
              />
            </div>
          </div>

          {/* Removed word */}
          <Field
            label="Removed word"
            value={data.key_word ?? "-"}
            highlight="yellow"
          />

          {/* Text after removal */}
          <div className="space-y-1.5">
            <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
              Text after removal
            </span>
            <span className="font-sans block text-sm text-[#b8c8d8] bg-[#0a0d10] border border-[#2e3d50] rounded-md px-4 py-3 leading-relaxed break-words">
              {data.modified_text ?? "-"}
            </span>
          </div>

          {/* After removal */}
          <div className="space-y-1">
            <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
              After removal
            </span>
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Verdict"
                value={data.modified_label ?? "-"}
                highlight={
                  data.flipped === true ? "red" : null
                }
              />
              <Field
                label="Confidence"
                value={
                  typeof data.modified_confidence === "number"
                    ? `${(data.modified_confidence * 100).toFixed(1)}%`
                    : data.modified_confidence ?? "-"
                }
              />
            </div>
          </div>

          {/* Delta */}
          <Field
            label="Positive-score shift"
            value={
              typeof data.delta === "number"
                ? Math.abs(data.delta) < 0.001
                  ? "No meaningful confidence change"
                  : `${data.delta >= 0 ? "+" : ""}${(data.delta * 100).toFixed(1)}%`
                : data.delta ?? "-"
            }
            highlight={
              typeof data.delta === "number" && Math.abs(data.delta) >= 0.001
                ? data.delta < 0 ? "green" : "red"
                : null
            }
          />
          <p className="font-sans text-[12px] text-[#5a6a7e] leading-relaxed">
            This is the change in the model's positive-class score after removing the key word. A negative shift means the text became less positive to the model.
          </p>

          {/* Verdict flipped status */}
          <StatusRow
            label="Verdict changed"
            value={data.flipped === true ? "YES" : data.flipped === false ? "NO" : "-"}
            highlight={data.flipped === true ? "green" : data.flipped === false ? "red" : null}
          />

          {/* Interpretation */}
          {data.flipped !== undefined && (
            <p className="font-sans text-sm text-[#96a8be] leading-relaxed pt-1">
              {data.flipped === true
                ? "Removing one high-impact word changed the model verdict."
                : typeof data.delta === "number" && Math.abs(data.delta) >= 0.001
                ? "The verdict stayed the same, but confidence shifted."
                : "The verdict stayed stable after this removal."}
            </p>
          )}
        </div>
      )}
    </PanelShell>
  );
}

/* ---- DISAGREE panel ---- */

function DisagreePanel({ data, error, loading }) {
  const agreed = data?.models_agree === true;

  return (
    <PanelShell
      id="panel-disagree"
      title="DISAGREE"
      tag="03 - Dual-model"
      description="DistilBERT (formal) vs RoBERTa-Twitter (informal). Divergence reveals linguistic ambiguity."
      durationMs={data?.duration_ms}
    >
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {(() => {
            const posA = Math.round(data.model_a.positive_score * 100);
            const posB = Math.round(data.model_b.positive_score * 100);
            const gap = Math.round(data.divergence * 100);
            let msg;
            if (data.models_agree === false) {
              msg = `Model A gave this sentence a ${posA}% positive score. Model B gave it ${posB}%. They reached opposite verdicts. A gap this large means the sentence is genuinely ambiguous across training domains.`;
            } else if (gap >= 20) {
              msg = `Model A gave this sentence a ${posA}% positive score. Model B gave it ${posB}%. Both called it the same verdict but with a ${gap}-point confidence gap. The wording is clear enough to classify, but reads differently across formal and informal training data.`;
            } else if (gap >= 5) {
              msg = `Model A gave this sentence a ${posA}% positive score. Model B gave it ${posB}%. Both models agree with a small ${gap}-point gap. The sentence is reasonably stable across training domains.`;
            } else {
              msg = `Model A gave this sentence a ${posA}% positive score. Model B gave it ${posB}%. Both models read this text almost identically. This sentence is stable across training domains.`;
            }
            return (
              <p className="font-sans text-[14px] text-[#b0c0d4] leading-loose">{msg}</p>
            );
          })()}

          <ModelRow
            label="Model A - DistilBERT"
            result={data.model_a}
            accentColor="text-[#58a6ff]"
          />
          <ModelRow
            label="Model B - RoBERTa"
            result={data.model_b}
            accentColor="text-[#a78bfa]"
          />

          {typeof data.divergence === "number" && data.model_a?.positive_score != null && data.model_b?.positive_score != null && (() => {
            const x = Math.round(data.model_a.positive_score * 100);
            const y = Math.round(data.model_b.positive_score * 100);
            const z = Math.round(data.divergence * 100);
            const interp = data.divergence >= 0.5
              ? "The models read this text very differently."
              : data.divergence >= 0.2
              ? "The models differ meaningfully."
              : data.divergence >= 0.1
              ? "Small but visible difference across training domains."
              : "Both models read this text similarly.";
            const gapColor = data.divergence > 0.3 ? "text-[#e0a052]" : data.divergence > 0.1 ? "text-[#58a6ff]" : "text-[#6b7a8d]";
            return (
              <div className="bg-[#0a0d10] border border-[#2e3d50] rounded-md px-4 py-3 space-y-2">
                <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
                  Positive-score gap
                </span>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <span className="font-mono block text-[10px] text-[#58a6ff] uppercase tracking-wide">Model A</span>
                    <span className="font-mono block text-lg font-bold text-[#dce3ec]">{x}%</span>
                  </div>
                  <div>
                    <span className="font-mono block text-[10px] text-[#a78bfa] uppercase tracking-wide">Model B</span>
                    <span className="font-mono block text-lg font-bold text-[#dce3ec]">{y}%</span>
                  </div>
                  <div>
                    <span className="font-mono block text-[10px] text-[#5a6a7e] uppercase tracking-wide">Gap</span>
                    <span className={`font-mono block text-lg font-bold ${gapColor}`}>{z}pt</span>
                  </div>
                </div>
                <p className="font-sans text-[12px] text-[#6b7a8d] leading-relaxed">{interp}</p>
              </div>
            );
          })()}

          <StatusRow
            label="Second model agrees"
            value={data.models_agree !== undefined ? (agreed ? "YES" : "NO") : "-"}
            highlight={agreed ? "green" : "yellow"}
          />

          {/* Interpretation */}
          {data.models_agree !== undefined && (
            <p className="font-sans text-sm text-[#96a8be] leading-relaxed pt-1">
              {data.models_agree === false
                ? "The models reached different verdicts. This sentence is ambiguous across training domains."
                : typeof data.divergence === "number" && data.divergence >= 0.1
                ? "Both models agree on the verdict, but their confidence differs. The same sentence is read differently depending on training data."
                : "Both models agree strongly. This sentence is stable across training domains."}
            </p>
          )}
        </div>
      )}
    </PanelShell>
  );
}

function ModelRow({ label, result, accentColor }) {
  if (!result) {
    return (
      <div className="space-y-1.5">
        <span className={`font-mono block text-[10px] tracking-[0.18em] uppercase font-semibold ${accentColor}`}>
          {label}
        </span>
        <span className="font-sans text-sm text-[#5a6a7e]">-</span>
      </div>
    );
  }
  const predLabel = result.label ?? result;
  const conf      = result.confidence ?? result.score;
  const isPos =
    typeof predLabel === "string" &&
    predLabel.toLowerCase().includes("pos");
  const sentimentColor = isPos ? "text-[#3ecf6f]" : "text-[#e05252]";

  return (
    <div className="space-y-1.5">
      <span className={`font-mono block text-[10px] tracking-[0.18em] uppercase font-semibold ${accentColor}`}>
        {label}
      </span>
      <div className="flex items-center gap-2.5">
        <span className={`font-mono text-base font-bold ${sentimentColor}`}>{predLabel}</span>
        {typeof conf === "number" && (
          <span className="font-mono text-sm text-[#96a8be] tabular-nums">
            ({(conf * 100).toFixed(1)}%)
          </span>
        )}
      </div>
    </div>
  );
}

/* ---- Hero section ---- */

function HeroSection() {
  return (
    <section className="space-y-3 pb-2">
      <p className="font-sans text-xl sm:text-2xl font-semibold text-[#dce3ec] leading-snug">
        Stress-test a model decision before trusting it.
      </p>
      <p className="font-sans text-[15px] sm:text-[17px] text-[#96a8be] leading-relaxed">
        Inspect how a transformer sentiment classifier makes decisions using token attribution,
        counterfactual testing, and dual-model disagreement.
      </p>
      <p className="font-sans text-[13px] sm:text-[15px] text-[#6b7a8d] leading-relaxed">
        Sentiment is the test task. The project is about model behavior.
      </p>
    </section>
  );
}

function HowToRead() {
  return (
    <section className="bg-[#0d1117] border border-[#252d38] rounded-lg px-4 sm:px-5 py-4 space-y-2">
      <span className="font-mono block text-[10px] tracking-[0.2em] uppercase text-[#5a6a7e] font-semibold">
        How to read this
      </span>
      <ul className="font-sans text-sm text-[#96a8be] leading-relaxed space-y-1 list-none">
        <li><span className="font-mono text-[#58a6ff] font-bold">WHY</span> shows which words influenced the model verdict.</li>
        <li><span className="font-mono text-[#58a6ff] font-bold">FLIP</span> checks whether removing one influential word changes the verdict.</li>
        <li><span className="font-mono text-[#58a6ff] font-bold">DISAGREE</span> checks whether a second model trained on different text reaches the same conclusion.</li>
      </ul>
      <p className="font-sans text-[12px] text-[#6b7a8d] leading-relaxed">
        Explainable AI helps inspect how a model reached a decision, instead of only showing the final output.
      </p>
    </section>
  );
}

/* ---- Forensic summary ---- */

function ForensicSummary({ results }) {
  const { why, flip, disagree } = results;
  if (!why || !flip || !disagree) return null;

  const strongestToken =
    Array.isArray(why.tokens) && why.tokens.length > 0
      ? why.tokens.reduce((a, b) =>
          Math.abs(a.weight) >= Math.abs(b.weight) ? a : b
        )
      : null;

  const lines = [];

  // WHY summary
  if (why.label && typeof why.confidence === "number") {
    lines.push(
      `The model classified this text as ${why.label} with ${(why.confidence * 100).toFixed(1)}% confidence.`
    );
  }
  if (strongestToken) {
    const dir = strongestToken.weight >= 0 ? "positive" : "negative";
    lines.push(
      `The model treated "${strongestToken.token}" as the strongest signal, pushing toward the ${dir} class.`
    );
  }

  // FLIP summary
  if (flip.flipped === true) {
    lines.push(
      `Removing the word "${flip.key_word}" changed the verdict, suggesting the prediction depends on that single token.`
    );
  } else if (typeof flip.delta === "number" && Math.abs(flip.delta) >= 0.001) {
    lines.push(
      `Removing "${flip.key_word}" shifted confidence but did not change the verdict, indicating partial sensitivity.`
    );
  } else {
    lines.push(
      "No single word removal changed the verdict. The prediction appears stable."
    );
  }

  // DISAGREE summary
  if (disagree.models_agree === false) {
    lines.push(
      "The two models disagree on this text, suggesting linguistic ambiguity across training domains."
    );
  } else if (typeof disagree.divergence === "number" && disagree.divergence >= 0.1) {
    lines.push(
      "Both models agree on the label, but their confidence levels differ across training domains."
    );
  } else {
    lines.push(
      "Both models reached a similar conclusion with comparable confidence."
    );
  }

  return (
    <section className="bg-[#0d1117] border border-[#252d38] rounded-lg px-6 py-5 space-y-2">
      <span className="font-mono block text-[10px] tracking-[0.2em] uppercase text-[#58a6ff] font-semibold">
        Forensic summary
      </span>
      {(() => {
        let stabLabel, stabCls;
        if (flip.flipped === true && disagree.models_agree === false) {
          stabLabel = "FRAGILE AND DOMAIN-SENSITIVE";
          stabCls = "text-[#e05252] bg-[#1a0d0d] border-[#3a1515]";
        } else if (flip.flipped === true) {
          stabLabel = "FRAGILE";
          stabCls = "text-[#e05252] bg-[#1a0d0d] border-[#3a1515]";
        } else if (disagree.models_agree === false) {
          stabLabel = "DOMAIN-SENSITIVE";
          stabCls = "text-[#e0a052] bg-[#1a1400] border-[#3a2e00]";
        } else {
          stabLabel = "STABLE";
          stabCls = "text-[#3ecf6f] bg-[#0d1f17] border-[#1e4030]";
        }
        return (
          <span className={`font-mono text-[11px] uppercase font-bold px-3 py-1 rounded border inline-block mb-4 ${stabCls}`}>
            {stabLabel}
          </span>
        );
      })()}
      {lines.map((line, i) => (
        <p key={i} className="font-sans text-sm text-[#b8c8d8] leading-relaxed">
          {line}
        </p>
      ))}
      {why.duration_ms != null && flip.duration_ms != null && disagree.duration_ms != null && (
        <p className="font-mono text-[11px] text-[#5a6a7e] leading-relaxed pt-1">
          Runtime: WHY {formatDuration(why.duration_ms)}, FLIP {formatDuration(flip.duration_ms)}, DISAGREE {formatDuration(disagree.duration_ms)}. WHY is usually slowest because LIME runs many perturbed model calls.
        </p>
      )}
    </section>
  );
}

/* ---- Methodology section ---- */

function MethodCard({ title, children }) {
  return (
    <div className="bg-[#0d1117] border border-[#3a4a5e] rounded-lg px-5 py-4 space-y-2">
      <span className="font-mono block text-xs font-bold tracking-[0.15em] uppercase text-[#58a6ff]">
        {title}
      </span>
      <div className="font-sans text-sm text-[#96a8be] leading-relaxed space-y-1.5">
        {children}
      </div>
    </div>
  );
}

function MethodologySection() {
  return (
    <section className="space-y-4 pt-4 border-t border-[#252d38]">
      <span className="font-mono block text-[10px] tracking-[0.2em] uppercase text-[#5a6a7e] font-semibold">
        Methodology and tradeoffs
      </span>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MethodCard title="Why these models">
          <p>
            DistilBERT-SST2 is trained on formal movie-review sentiment text (SST-2 dataset).
            Twitter-RoBERTa is trained on 124 million tweets and handles informal tone, sarcasm, and slang.
          </p>
          <p>
            These two models were chosen because their different training domains
            can produce genuine disagreement on ambiguous or informal text.
          </p>
        </MethodCard>

        <MethodCard title="Why these methods">
          <p>
            LIME is a model-agnostic local explanation method. It perturbs the input and observes
            how predictions change, estimating token-level influence without accessing model internals.
          </p>
          <p>
            SHAP was considered but rejected for this MVP: it is slower on transformers and expensive
            on free-tier CPU. Attention weights are not treated as reliable explanations (Jain and Wallace, 2019).
          </p>
        </MethodCard>

        <MethodCard title="Why it takes time">
          <p>
            LIME runs approximately 300 perturbed model inference calls per explanation (15-45 seconds).
            FLIP reruns inference once per word in the input (2-10 seconds).
            DISAGREE runs two forward passes (under 1 second).
          </p>
          <p>
            All inference runs on CPU. The backend is deployed on Hugging Face Spaces free tier,
            which does not guarantee GPU availability.
          </p>
        </MethodCard>

        <MethodCard title="Known limitations">
          <p>
            LIME attribution is an approximation, not an exact causal explanation.
            Greedy word removal can create ungrammatical text after deletion.
            Counterfactual removal does not always flip the label on highly confident predictions.
          </p>
          <p>
            Input is limited to 1000 characters. The backend can have a 30-60 second cold start
            after inactivity. This tool is sentiment-specific and has only been tested on English text.
          </p>
        </MethodCard>
      </div>
    </section>
  );
}

/* ---- Example cards ---- */

const EXAMPLES = [
  {
    text: "I am not entirely unhappy with this result.",
    hint: "Double negation. Most models misread the sentiment direction.",
  },
  {
    text: "Great, another meeting that could have been an email.",
    hint: "Surface sarcasm. Positive tone, negative meaning.",
  },
  {
    text: "You are surprisingly competent for once.",
    hint: "Backhanded compliment. Mixed signals across training domains.",
  },
];

function ExampleCards({ onSelect }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
      {EXAMPLES.map((ex, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(ex.text)}
          className="bg-[#0d1117] border border-[#2e3d50] rounded-md px-4 py-3 text-left cursor-pointer hover:border-[#58a6ff] transition-colors"
        >
          <span className="font-mono block text-[13px] text-[#b0c0d4]">
            {ex.text}
          </span>
          <span className="font-sans block text-[12px] text-[#5a6a7e] mt-1">
            {ex.hint}
          </span>
        </button>
      ))}
    </div>
  );
}
