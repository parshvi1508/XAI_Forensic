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
      <header className="border-b border-[#252d38] px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-mono text-sm font-bold tracking-[0.2em] uppercase text-[#58a6ff]">
            XAI Forensics
          </h1>
          <p className="font-sans text-sm text-[#96a8be] mt-1 leading-snug">
            Token attribution - counterfactual flip - dual-model disagreement
          </p>
        </div>
        {hasAnyResult && !loading && (
          <span className="font-mono text-[10px] tracking-widest uppercase text-[#3ecf6f] border border-[#1e4030] bg-[#0d1f17] rounded px-2 py-1">
            Analysis complete
          </span>
        )}
      </header>

      <main className="px-8 py-10 max-w-7xl mx-auto space-y-10">

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

        {/* Panels */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <WhyPanel     data={results.why}     error={errors.why}     loading={loading} />
          <FlipPanel    data={results.flip}    error={errors.flip}    loading={loading} />
          <DisagreePanel data={results.disagree} error={errors.disagree} loading={loading} />
        </section>
      </main>
    </div>
  );
}

/* ---- shared primitives ---- */

function PanelShell({ id, title, tag, description, children }) {
  return (
    <div
      id={id}
      className="bg-[#0d1117] border border-[#252d38] rounded-lg p-6 space-y-5 min-h-[280px] flex flex-col"
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
        {description && (
          <p className="font-sans text-sm text-[#96a8be] leading-relaxed">{description}</p>
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
      <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
        {label}
      </span>
      <span className={`font-mono block text-base font-semibold break-words ${valueColor}`}>{value}</span>
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

function WhyPanel({ data, error, loading }) {
  return (
    <PanelShell
      id="panel-why"
      title="WHY"
      tag="01 - Attribution"
      description="Which tokens pushed the model toward its prediction, and by how much."
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
              label="Predicted label"
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

          {Array.isArray(data.tokens) && data.tokens.length > 0 ? (
            <div className="space-y-2">
              <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
                Token weights
              </span>
              <TokenBars tokens={data.tokens} />
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
              className="font-mono w-[6.5rem] shrink-0 truncate text-sm text-[#b0c0d4] font-medium"
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
            <span className={`font-mono w-14 text-right font-semibold tabular-nums text-sm ${numColor}`}>
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
    >
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {/* Before removal */}
          <div className="space-y-1">
            <span className="font-mono block text-[10px] tracking-[0.18em] uppercase text-[#5a6a7e] font-semibold">
              Before removal
            </span>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Label" value={data.original_label ?? "-"} />
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
                label="Label"
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
            label="Confidence delta"
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
    >
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
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

          <Field
            label="Divergence score"
            value={
              typeof data.divergence === "number"
                ? data.divergence.toFixed(4)
                : data.divergence ?? "-"
            }
            highlight={
              typeof data.divergence === "number"
                ? data.divergence > 0.3 ? "yellow"
                : data.divergence > 0.1 ? "blue"
                : null
                : null
            }
          />

          <StatusRow
            label="Models agree"
            value={data.models_agree !== undefined ? (agreed ? "YES" : "NO") : "-"}
            highlight={agreed ? "green" : "yellow"}
          />

          {/* Interpretation */}
          {data.models_agree !== undefined && (
            <p className="font-sans text-sm text-[#96a8be] leading-relaxed pt-1">
              {data.models_agree === false
                ? "The models disagree. This sentence is ambiguous across training domains."
                : typeof data.divergence === "number" && data.divergence >= 0.1
                ? "The models agree on the verdict, but confidence differs across training domains."
                : "Both models reached a similar conclusion. The verdict is relatively stable."}
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
