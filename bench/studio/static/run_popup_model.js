// The mechanism pop-up's Cost and Graphs (spec 2026-10-11 one Cable net tab,
// sections 8.2 and 8.3): the run's mechanism priced as one spooling mechanism,
// the spools, the cabinets and the total; and two graphs over the run's
// captures, the worst wire against one spool's pull and the worst offset
// against the tolerance, each limit a dashed line at its place. Pure, and
// tested under node.

import { escapeHtml } from "./labels.js";

function pounds(n, places = 0) {
  return "£" + Number(n).toLocaleString("en-GB", { minimumFractionDigits: places,
                                                   maximumFractionDigits: places });
}

// The cost (section 8.2), a row each: what it is, its figure, a note.
export function costHtml(cost) {
  if (!cost) return "";
  const row = (name, value, note = "", title = "") =>
    `<tr${title ? ` title="${escapeHtml(title)}"` : ""}><th>${escapeHtml(name)}</th>`
    + `<td>${value}</td><td>${escapeHtml(note)}</td></tr>`;
  const rows = [];
  const one = cost.spool_gbp == null ? "unpriced" : pounds(cost.spool_gbp, 2);
  rows.push(row("One spool", one, cost.described || ""));
  rows.push(row("Spools", cost.spools + " × " + one,
                cost.spool_gbp == null ? "" : pounds(cost.spool_gbp * cost.spools)));
  rows.push(row("Cabinets", String(cost.cabinets), pounds(cost.cabinets_gbp)));
  rows.push(row("Total", pounds(cost.total_gbp), "VAT excluded"));
  if (cost.unpriced > 0) {
    rows.push(row("Unpriced", cost.unpriced + (cost.unpriced === 1 ? " part" : " parts"), "",
                  (cost.unpriced_parts || []).join(", ")));
  }
  return "<table>" + rows.join("") + "</table>";
}

function worst(values) {
  let most = 0;
  for (let i = 0; values && i < values.length; i++) if (values[i] > most) most = values[i];
  return most;
}

// The two series the graphs draw (section 8.3): at each capture, the largest
// wire tension, N, and the largest offset from the design, mm.
export function graphSeries(sim) {
  const captures = (sim && sim.captures) || [];
  return { wire: captures.map((c) => worst(c.wireTension)),
           offset: captures.map((c) => worst(c.deviation)) };
}

const W = 400;
const H = 130;
const LEFT = 8;
const RIGHT = 8;
const TOP = 22;
const BOTTOM = 8;

function figure(n) {
  const v = Number(n);
  return Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en-GB") : String(Number(v.toFixed(2)));
}

// One graph: the values across the captures as a line, the limit (when there
// is one) as a dashed line at its place, the scale from nought to the larger
// of the two.
export function graphSvg(values, limit, { title = "", limitText = "" } = {}) {
  const list = (values || []).map(Number);
  const top = Math.max(...list, limit == null ? 0 : Number(limit), 0) || 1;
  const x = (i) => LEFT + (list.length > 1 ? i / (list.length - 1) : 0.5) * (W - LEFT - RIGHT);
  const y = (v) => TOP + (1 - v / top) * (H - TOP - BOTTOM);
  const points = list.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1)).join(" ");
  const parts = [`<svg viewBox="0 0 ${W} ${H}" width="100%" class="run-graph">`,
    `<text x="${LEFT}" y="12" class="graph-title">${escapeHtml(title)}</text>`,
    `<text x="${W - RIGHT}" y="12" text-anchor="end" class="graph-scale">${figure(top)}</text>`,
    `<line x1="${LEFT}" y1="${H - BOTTOM}" x2="${W - RIGHT}" y2="${H - BOTTOM}" class="graph-axis"/>`];
  if (limit != null && Number(limit) > 0) {
    const at = y(Number(limit)).toFixed(1);
    parts.push(`<line x1="${LEFT}" y1="${at}" x2="${W - RIGHT}" y2="${at}" class="graph-limit" `
      + 'stroke-dasharray="4 3"/>');
    parts.push(`<text x="${W - RIGHT}" y="${(Number(at) - 3).toFixed(1)}" text-anchor="end" `
      + `class="graph-limit-text">${escapeHtml(limitText)}</text>`);
  }
  if (list.length) parts.push(`<polyline points="${points}" class="graph-line" fill="none"/>`);
  parts.push("</svg>");
  return parts.join("");
}

// The Graphs tab: the worst wire against one spool's pull (have, N, or null
// for a run with no mechanism) and the worst offset against the tolerance.
export function graphsHtml(sim, have, tolerance) {
  if (!sim) return "";
  const series = graphSeries(sim);
  const pull = have == null ? null : Number(have);
  return graphSvg(series.wire, pull, { title: "worst wire, N",
    limitText: pull == null ? "" : "one spool " + Math.round(pull).toLocaleString("en-GB") + " N" })
    + graphSvg(series.offset, Number(tolerance), { title: "worst offset, mm",
      limitText: "tolerance " + Number(tolerance) + " mm" });
}
