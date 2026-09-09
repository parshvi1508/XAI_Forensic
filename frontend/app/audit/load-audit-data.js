import { readFileSync, existsSync } from "fs";
import { join } from "path";

const AUDIT_DIR = join(process.cwd(), "..", "audit", "results");

function parseCSV(text) {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = [];
    let current = "";
    let inQuotes = false;
    for (const ch of line) {
      if (ch === '"') {
        inQuotes = !inQuotes;
      } else if (ch === "," && !inQuotes) {
        values.push(current);
        current = "";
      } else {
        current += ch;
      }
    }
    values.push(current);
    const row = {};
    headers.forEach((h, i) => {
      row[h.trim()] = (values[i] || "").trim();
    });
    return row;
  });
}

function safeFloat(val) {
  if (val === "" || val === "NaN" || val === "nan" || val == null) return null;
  const n = parseFloat(val);
  return isNaN(n) ? null : n;
}

export function loadStabilityData() {
  const path = join(AUDIT_DIR, "stability_metrics.csv");
  if (!existsSync(path)) return [];
  const rows = parseCSV(readFileSync(path, "utf-8"));
  return rows.map((r) => ({
    id: parseInt(r.input_id),
    category: r.category,
    text: r.text,
    jaccard: safeFloat(r.mean_jaccard_top5) ?? 0,
    minJaccard: safeFloat(r.min_jaccard_top5) ?? 0,
    kendallTau: safeFloat(r.mean_kendall_tau),
    stable: r.label_stable === "True",
    unanimous: r.top1_unanimous === "True",
    ciLower: safeFloat(r.jaccard_ci_lower),
    ciUpper: safeFloat(r.jaccard_ci_upper),
    limeTokenCount: safeFloat(r.lime_token_count),
    wordpieceTokenCount: safeFloat(r.wordpiece_token_count),
    tokenMismatch: safeFloat(r.token_mismatch),
  }));
}

export function loadDeletionData() {
  const path = join(AUDIT_DIR, "deletion_faithfulness.csv");
  if (!existsSync(path)) return [];
  const rows = parseCSV(readFileSync(path, "utf-8"));
  return rows
    .filter((r) => r.status !== "skipped_empty" && r.input_id)
    .map((r) => ({
      id: parseInt(r.input_id),
      category: r.category,
      text: r.text,
      removedToken: r.removed_token,
      limeWeight: safeFloat(r.token_lime_weight) ?? 0,
      originalLabel: r.original_label,
      originalScore: safeFloat(r.original_positive_score) ?? 0,
      modifiedLabel: r.modified_label,
      modifiedScore: safeFloat(r.modified_positive_score) ?? 0,
      delta: safeFloat(r.confidence_delta) ?? 0,
      flipped: r.label_flipped === "True",
      directionCorrect: r.direction_correct === "True",
      removedTop3: r.removed_top3 || null,
      deltaTop3: safeFloat(r.delta_top3),
      flippedTop3: r.flipped_top3 === "True",
      removedTop5: r.removed_top5 || null,
      deltaTop5: safeFloat(r.delta_top5),
      flippedTop5: r.flipped_top5 === "True",
    }));
}

export function loadSummary() {
  const path = join(AUDIT_DIR, "summary.json");
  if (!existsSync(path)) return null;
  const raw = readFileSync(path, "utf-8").replace(/\bNaN\b/g, "null");
  return JSON.parse(raw);
}

export function computeCategoryStats(stabilityData) {
  const cats = {};
  for (const row of stabilityData) {
    if (!cats[row.category]) {
      cats[row.category] = { jaccards: [], label: formatCategory(row.category) };
    }
    cats[row.category].jaccards.push(row.jaccard);
  }
  return Object.entries(cats).map(([category, data]) => ({
    category,
    label: data.label,
    jaccard: data.jaccards.reduce((a, b) => a + b, 0) / data.jaccards.length,
    count: data.jaccards.length,
  }));
}

export function computeDeletionStats(deletionData) {
  const tested = deletionData.filter((d) => d.originalLabel);
  if (!tested.length) return null;
  const dirCorrect = tested.filter((d) => d.directionCorrect).length;
  const flipped = tested.filter((d) => d.flipped).length;
  const deltas = tested.map((d) => Math.abs(d.delta));
  const meanDelta = deltas.reduce((a, b) => a + b, 0) / deltas.length;
  return {
    total: tested.length,
    directionCorrectCount: dirCorrect,
    directionCorrectRate: dirCorrect / tested.length,
    flipCount: flipped,
    flipRate: flipped / tested.length,
    meanAbsDelta: meanDelta,
  };
}

export function findCounterexamples(deletionData) {
  return deletionData
    .filter((d) => !d.directionCorrect && d.originalLabel)
    .map((d) => ({
      ...d,
      explanation: generateExplanation(d),
    }));
}

function generateExplanation(d) {
  const absDelta = Math.abs(d.delta);
  if (absDelta < 0.01) {
    if (d.limeWeight < 0) {
      return `LIME assigned a negative weight to "${d.removedToken}" (predicting removal would increase positive score), but removing it ${absDelta < 0.001 ? "had virtually zero effect" : "slightly decreased the positive score"}. The model's confidence was so high that removing any single token had negligible effect.`;
    }
    return `LIME assigned a positive weight to "${d.removedToken}" (predicting removal would decrease positive score), but removing it had virtually zero effect. Redundant evidence means no single token is individually necessary.`;
  }
  return `LIME predicted removing "${d.removedToken}" would shift the score in the ${d.limeWeight > 0 ? "negative" : "positive"} direction, but the actual shift went the opposite way with a delta of ${d.delta.toFixed(4)}.`;
}

function formatCategory(cat) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
