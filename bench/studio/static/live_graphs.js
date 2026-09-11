// The live graphs beside the take: what the model says is happening to the
// cables, the formwork, the columns and the supports at every instant of
// the animation, drawn as the animation plays and scrubbed with it.
//
// Param: "3 tiled graphs to the left in a mostly translucent window ...
// live the pre stress per cable building as a live graph, one shows the
// q load, another the column strain ... a super accurate precise model
// that i can use to test against a physical model ... maybe even a
// timeline scrubber after the sequence is run".
//
// Everything here is PURE: plain data in, series and chart specs out, no
// three.js and no DOM, so the whole model is testable under node the way
// fields.js and data_analysis.js are. studio.js owns the wiring and the
// plotting library; this module owns the numbers and their honesty.
//
// THE MODEL, and what it rests on. The documents carry three kinds of
// number and no others: the frames document has positions per frame
// (and, since the 2026-09-11 spec addendum, MAY carry the machine's own
// per-frame cable and column forces); the contract has the form-found
// thrust network's member force per edge, its nodal loads and its
// support reactions, and the exporter's final column forces; and the
// cut has every piece's geometry, from which its weight is exact. So:
//
//   cable force  = two parts. The SHARE OF THE PLACED WEIGHT: the thrust
//                  network was form-found under the shell's self-weight
//                  at a placeholder density (the live exports say so),
//                  and in a force density net at fixed geometry the
//                  forces scale linearly with the load, so each cable's
//                  share is its member force x placed weight / the load
//                  the network was solved for; the strike takes it off
//                  again. And the PRESTRESS: what the machine's reels put
//                  into the net before anything is cast, reached through
//                  the raise (reel 0..30 of the machine clock: slack;
//                  raise 30..60: tensioning; finish and hold: at
//                  prestress). No document states it, so it is a DIAL,
//                  a fraction of each cable's final thrust, written on
//                  the graph and set to the winch a physical model uses.
//                  Cable elasticity is NOT modelled. When the frames
//                  carry forces, those are used as they are and this
//                  model is not.
//   load         = the placed weight, exactly: each landed piece's
//                  mid-surface area x thickness x density x g, the same
//                  arithmetic staging.py uses per course, with the
//                  server's own per-course figure drawn as a check, and
//                  the areal q it comes from in the reading.
//   column force = the exporter's final column force, on the same
//                  prestress-and-share factor as the cables; strain is
//                  force over E x A with E stated on the graph and A
//                  from the exporter's own radius.
//   thrust       = the thrust network's support reactions, scaled from
//                  the load they were solved for to the shell's built
//                  weight, arriving as the strike hands the shell over.
//
// A physical model measures cable tension, formwork load, column strain
// and support thrust with instruments; these are the four numbers the
// digital twin predicts for the same instants, with every assumption
// written on the graph and exportable beside the data.

import { machineTime } from "./fields.js";

export const GRAVITY = 9.81;
// The column material the strain is read against. The exporter draws the
// columns as steel tubes of one radius and states no modulus, so this is
// an assumption and the graph says so.
export const COLUMN_MODULUS_PA = 210e9;
export const COLUMN_RADIUS_M = 0.05;
export const CABLE_TOP = 5;
export const SAMPLES = 480;
// The prestress dial's default: a tenth of each cable's final thrust.
export const PRESTRESS_DEFAULT = 0.1;
// The machine clock's phases (fields.js machineTime: 0..100). Reel 0..30
// lays the net out slack; raise 30..60 tensions it; finish and hold keep
// it at prestress.
export const RAISE_FROM = 30, RAISE_TO = 60;

function smooth(u) {
  const t = Math.max(0, Math.min(1, u));
  return t * t * (3 - 2 * t);
}

// A piece's mid-surface area: the faces whose vertices all index the mid
// list (the client extrudes a second skin at +n, and the faces that use
// both skins are the sides).
export function pieceMidArea(piece) {
  const n = piece.mid.length;
  let area = 0;
  for (const face of piece.faces) {
    if (face.some((i) => i >= n)) continue;
    for (let i = 2; i < face.length; i++) {
      const p = piece.mid[face[0]], q = piece.mid[face[i - 1]], r = piece.mid[face[i]];
      const ux = q[0] - p[0], uy = q[1] - p[1], uz = q[2] - p[2];
      const wx = r[0] - p[0], wy = r[1] - p[1], wz = r[2] - p[2];
      area += Math.hypot(uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx) / 2;
    }
  }
  return area;
}

export function meshArea(mesh) {
  const v = mesh.vertices;
  let area = 0;
  for (const face of mesh.faces) {
    for (let i = 2; i < face.length; i++) {
      const p = v[face[0]], q = v[face[i - 1]], r = v[face[i]];
      const ux = q[0] - p[0], uy = q[1] - p[1], uz = q[2] - p[2];
      const wx = r[0] - p[0], wy = r[1] - p[1], wz = r[2] - p[2];
      area += Math.hypot(uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx) / 2;
    }
  }
  return area;
}

// Every piece's weight and the instant it lands, in drop order. The
// pieces' own areas are normalised to the analysis mesh's, because the
// cut's subdivision adds a fraction of a per cent and the server's
// per-course figure is measured on the mesh.
export function pieceWeights(bundle, clock, thickness, density) {
  const pieces = bundle.pieces || [];
  const areas = pieces.map(pieceMidArea);
  const sum = areas.reduce((a, b) => a + b, 0);
  const mesh = bundle.analysis_mesh ? meshArea(bundle.analysis_mesh) : sum;
  const scale = sum > 0 && mesh > 0 ? mesh / sum : 1;
  return pieces.map((piece, order) => ({
    order, course: piece.course, areaM2: areas[order] * scale,
    weightN: areas[order] * scale * thickness * density * GRAVITY,
    landsAt: clock.opening + order * clock.step + clock.drop,
  }));
}

// The placed weight at t, in newtons, and the area under it.
export function placedAt(t, weights) {
  let weightN = 0, areaM2 = 0;
  for (const piece of weights) {
    if (t >= piece.landsAt) { weightN += piece.weightN; areaM2 += piece.areaM2; }
  }
  return { weightN, areaM2 };
}

// How far the raise has come at t: 0 slack, 1 at prestress. With a
// machine act it is the machine clock's raise phase; without one the
// inflation reveal stands in, linearly over the opening.
export function raiseFactor(t, clock) {
  if (clock.formwork > 0) {
    const m = machineTime(t, clock.formwork);
    return smooth((m - RAISE_FROM) / (RAISE_TO - RAISE_FROM));
  }
  return clock.opening > 0 ? Math.min(1, Math.max(0, t / clock.opening)) : 1;
}

// How far the strike has come at t: 0 standing, 1 struck.
export function strikeFactor(t, clock) {
  const build = t - clock.opening;
  const buildEnd = clock.pieces * clock.step + clock.drop;
  if (build <= buildEnd) return 0;
  return Math.min(1, (build - buildEnd) / clock.strike);
}

// The frames' own per-frame values (forces, columnForces), interpolated
// on the machine clock; null when the frames carry none.
function frameValuesAt(frames, key, m) {
  if (!frames || !frames.length || !Array.isArray(frames[0][key])) return null;
  let below = frames[0], above = frames[frames.length - 1];
  for (let i = 0; i < frames.length - 1; i++) {
    if (m >= frames[i].time && m <= frames[i + 1].time) {
      below = frames[i]; above = frames[i + 1]; break;
    }
  }
  const span = above.time - below.time;
  const u = span > 0 ? (m - below.time) / span : 0;
  return below[key].map((value, i) => value + (above[key][i] - value) * u);
}

function stats(values) {
  let min = Infinity, max = -Infinity, sum = 0;
  for (const v of values) { if (v < min) min = v; if (v > max) max = v; sum += v; }
  return { min: values.length ? min : 0, max: values.length ? max : 0,
    mean: values.length ? sum / values.length : 0 };
}

// The acts, for the x axis: what the picture is doing when.
export function acts(clock) {
  const buildEnd = clock.opening + clock.pieces * clock.step + clock.drop;
  return [
    { name: clock.formwork > 0 ? "formwork" : "reveal", from: 0, to: clock.opening },
    { name: "build", from: clock.opening, to: buildEnd },
    { name: "strike", from: buildEnd, to: buildEnd + clock.strike },
    { name: "stands", from: buildEnd + clock.strike, to: clock.duration },
  ];
}

// Everything the graphs draw, sampled over the take. clock is the
// studio's own numbers: { duration, opening, formwork, step, drop,
// strike, pieces } (the last two in seconds); formwork is the served document or null;
// columnForcesKN is the exporter's final force per column member (kN)
// or null; columnRadiusM the exporter's radius or null; prestress the
// dial, a fraction of each cable's final thrust.
export function buildLiveSeries(input) {
  const { bundle, clock, thickness, density } = input;
  const formwork = input.formwork || null;
  const frames = formwork && Array.isArray(formwork.frames) ? formwork.frames : null;
  const samples = input.samples || SAMPLES;
  const prestress = Number.isFinite(input.prestress) ? Math.max(0, input.prestress)
    : PRESTRESS_DEFAULT;
  const notes = [];
  const weights = pieceWeights(bundle, clock, thickness, density);
  const totalWeightN = weights.reduce((a, p) => a + p.weightN, 0);
  const t = new Array(samples);
  for (let k = 0; k < samples; k++) t[k] = clock.duration * k / (samples - 1);

  // The load the thrust network was form-found for: the contract's own
  // nodal loads, summed. This is what the placed weight is measured
  // against, and without it the placed weight cannot be distributed.
  const loads = Object.values(bundle.loads || {});
  const networkLoadN = loads.reduce((a, v) => a + Math.hypot(v[0], v[1], v[2]), 0);
  const loadScale = networkLoadN > 0 ? 1 / networkLoadN : null;
  if (!loadScale) {
    notes.push("the contract carries no nodal loads, so the placed weight "
      + "is not distributed to the cables or the columns; they are shown "
      + "at prestress");
  }
  // The one factor every force wears: the prestress reached through the
  // raise, plus the share of the placed weight while the net carries it.
  const factorAt = (t) => prestress * raiseFactor(t, clock) + (loadScale
    ? placedAt(t, weights).weightN * (1 - strikeFactor(t, clock)) * loadScale : 0);

  // ---- the load on the formwork ----
  const load = { kN: new Array(samples), areaM2: new Array(samples),
    qKNm2: thickness * density * GRAVITY / 1000, totalKN: totalWeightN / 1000,
    checks: [] };
  for (let k = 0; k < samples; k++) {
    const placed = placedAt(t[k], weights);
    const strike = strikeFactor(t[k], clock);
    load.kN[k] = placed.weightN * (1 - strike) / 1000;
    load.areaM2[k] = placed.areaM2;
  }
  // The server's own per-course figures, at the instant each course's
  // last piece lands: the client's arithmetic drawn against the solver's.
  const stages = bundle.staging && Array.isArray(bundle.staging.stages)
    ? bundle.staging.stages : [];
  stages.forEach((stage, index) => {
    const mine = weights.filter((p) => p.course <= index);
    if (!mine.length || typeof stage.formwork_carries_newtons !== "number") return;
    load.checks.push({ stage: index + 1, t: Math.max(...mine.map((p) => p.landsAt)),
      kN: stage.formwork_carries_newtons / 1000 });
  });

  // ---- the cables ----
  const memberForces = bundle.member_forces || [];
  const edgeCount = formwork && Array.isArray(formwork.edges)
    ? formwork.edges.length : memberForces.length;
  const thrustKN = memberForces.slice(0, edgeCount).map((f) => Math.abs(f) / 1000);
  const fromFrames = !!(frames && frames.length && Array.isArray(frames[0].forces));
  const ranked = thrustKN.map((f, i) => [f, i]).sort((a, b) => b[0] - a[0]);
  const top = ranked.slice(0, CABLE_TOP).map(([, i]) => i);
  const cables = { count: thrustKN.length, unit: "kN",
    source: fromFrames ? "frames" : "model", prestress,
    mean: new Array(samples), max: new Array(samples), min: new Array(samples),
    top: top.map((edge) => ({ edge, series: new Array(samples) })),
    thrust: stats(thrustKN), loadScale };
  for (let k = 0; k < samples; k++) {
    let forces;
    if (fromFrames && clock.formwork > 0 && t[k] <= clock.formwork) {
      forces = frameValuesAt(frames, "forces", machineTime(t[k], clock.formwork))
        .map((f) => Math.abs(f));
    } else {
      const factor = factorAt(t[k]);
      forces = thrustKN.map((f) => f * factor);
    }
    const s = stats(forces);
    cables.mean[k] = s.mean; cables.max[k] = s.max; cables.min[k] = s.min;
    cables.top.forEach((row) => { row.series[k] = forces[row.edge] || 0; });
  }
  if (fromFrames) {
    notes.push("cable forces during the formwork act are the frames' own, "
      + "as the machine's solver wrote them");
  }
  notes.push("cable force is each cable's share of the placed weight (its "
    + "form-found member force, scaled from the load the network was solved "
    + "for to what is placed: a force density net at fixed geometry) plus a "
    + "prestress of " + Math.round(prestress * 100) + "% of its final thrust, "
    + "reached through the raise; elasticity not modelled");

  // ---- the columns ----
  const columnForces = Array.isArray(input.columnForcesKN) ? input.columnForcesKN : [];
  const radius = input.columnRadiusM > 0 ? input.columnRadiusM : COLUMN_RADIUS_M;
  const areaM2 = Math.PI * radius * radius;
  const fromFramesColumns = !!(frames && frames.length && Array.isArray(frames[0].columnForces));
  const columns = { count: columnForces.length, unit: "kN",
    source: fromFramesColumns ? "frames" : (columnForces.length ? "model" : "none"),
    max: new Array(samples), mean: new Array(samples), min: new Array(samples),
    members: columnForces.length <= 6
      ? columnForces.map((_, index) => ({ index, series: new Array(samples) })) : [],
    strain: { modulusPa: COLUMN_MODULUS_PA, areaM2, radiusM: radius,
      microstrainMax: new Array(samples) } };
  for (let k = 0; k < samples; k++) {
    let forces;
    if (fromFramesColumns && clock.formwork > 0 && t[k] <= clock.formwork) {
      forces = frameValuesAt(frames, "columnForces", machineTime(t[k], clock.formwork))
        .map((f) => Math.abs(f));
    } else {
      const factor = factorAt(t[k]);
      forces = columnForces.map((f) => Math.abs(f) * factor);
    }
    const s = stats(forces);
    columns.max[k] = s.max; columns.mean[k] = s.mean; columns.min[k] = s.min;
    columns.members.forEach((row) => { row.series[k] = forces[row.index] || 0; });
    // Strain: force over E A, in microstrain.
    columns.strain.microstrainMax[k] = s.max * 1000 / (COLUMN_MODULUS_PA * areaM2) * 1e6;
  }
  if (columnForces.length) {
    notes.push("column force is the exporter's final figure on the cables' "
      + "own prestress and share factor; strain is force over E A with E "
      + (COLUMN_MODULUS_PA / 1e9).toFixed(0) + " GPa (steel, assumed) and a "
      + "solid section of radius " + (radius * 1000).toFixed(0) + " mm");
  } else {
    notes.push("no column forces: the contract's mould block carries none "
      + "for this study");
  }

  // ---- the supports ----
  const reactions = Object.values(bundle.reactions || {});
  const finalH = reactions.reduce((a, v) => a + Math.hypot(v[0], v[1]), 0) / 1000;
  const finalV = reactions.reduce((a, v) => a + Math.abs(v[2]), 0) / 1000;
  const shellScale = loadScale ? totalWeightN * loadScale : 1;
  const thrust = { horizontalKN: new Array(samples), verticalKN: new Array(samples),
    finalHorizontalKN: finalH * shellScale, finalVerticalKN: finalV * shellScale };
  for (let k = 0; k < samples; k++) {
    const handed = strikeFactor(t[k], clock);
    thrust.horizontalKN[k] = finalH * shellScale * handed;
    thrust.verticalKN[k] = finalV * shellScale * handed;
  }
  notes.push("thrust is the thrust network's support reactions scaled from "
    + "the load they were solved for to the built shell's weight, arriving "
    + "as the strike hands the shell over");

  return { t, acts: acts(clock), load, cables, columns, thrust, notes,
    weightsKN: weights.map((p) => p.weightN / 1000) };
}

// The value of a series at t: the nearest sample.
export function sampleAt(series, t, values) {
  const n = series.t.length;
  if (!n) return 0;
  const k = Math.round((n - 1) * Math.max(0, Math.min(1, t / (series.t[n - 1] || 1))));
  return values[k];
}

// ---------- the drawings ----------
// Not the plotting library's own look: no title boxes, no legend, no
// zero line, faint horizontal rules only, tight margins, monospaced
// numbers, the acts as faint bands under the lines, one cursor. The
// card's own header names the graph, its unit and the live reading.
export function liveLayout(series, theme, options) {
  const bands = series.acts.map((act, i) => ({
    type: "rect", xref: "x", yref: "paper", x0: act.from, x1: act.to, y0: 0, y1: 1,
    fillcolor: theme.ink, opacity: i % 2 ? 0.05 : 0.02, line: { width: 0 }, layer: "below",
  }));
  const cursor = {
    type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1,
    line: { color: theme.ink, width: 1 }, opacity: 0.7,
  };
  return {
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: theme.font, color: theme.ink2, size: 10 },
    margin: { l: 42, r: 10, t: 6, b: 18 },
    showlegend: false,
    // One box at the cursor listing every line, not a box per line.
    hovermode: "x unified",
    hoverlabel: { bgcolor: theme.scrim, bordercolor: theme.line,
      font: { family: theme.mono, color: theme.ink, size: 10 } },
    xaxis: { range: [0, series.t[series.t.length - 1]], showgrid: false,
      zeroline: false, ticks: "", tickfont: { family: theme.mono, size: 9 },
      color: theme.ink2, linecolor: theme.line, ticksuffix: " s", fixedrange: true,
      hoverformat: ".1f" },
    yaxis: { showgrid: true, gridcolor: theme.line, gridwidth: 1, zeroline: false,
      ticks: "", tickfont: { family: theme.mono, size: 9 }, color: theme.ink2,
      rangemode: "tozero", fixedrange: true, nticks: 4,
      ticksuffix: options && options.ticksuffix ? options.ticksuffix : "" },
    shapes: bands.concat([cursor]),
  };
}

function line(x, y, colour, width, name, dash) {
  return { x, y, type: "scatter", mode: "lines", name,
    line: { color: colour, width, dash: dash || "solid", shape: "linear" },
    hovertemplate: name + " %{y:.2f}<extra></extra>" };
}

// The edge of a band: no line, no hover of its own (a band's edges said
// "undefined 6.90" in the unified box before this existed).
function edge(x, y, name, fill, fillcolor) {
  const trace = { x, y, type: "scatter", mode: "lines", name,
    line: { width: 0 }, hoverinfo: "skip", showlegend: false };
  if (fill) { trace.fill = fill; trace.fillcolor = fillcolor; }
  return trace;
}

// The four cards' traces. Colours come from the theme (CSS tokens), so
// the graphs follow light and dark and never carry a hex of their own.
export function liveSpecs(series, theme) {
  const specs = [];
  const t = series.t;
  // 1. Cables: the band between least and most loaded, the mean, and the
  // five that carry most, each its own thin line.
  const cableTraces = [
    edge(t, series.cables.min, "least"),
    edge(t, series.cables.max, "most", "tonexty", theme.aFill),
  ];
  for (const row of series.cables.top) {
    cableTraces.push(line(t, row.series, theme.a, 0.8, "cable " + row.edge));
  }
  cableTraces.push(line(t, series.cables.mean, theme.ink, 1.4, "mean"));
  specs.push({ id: "live-cables", name: "Cable force", unit: "kN",
    reading: (k) => series.cables.max[k], readingLabel: "most loaded",
    data: cableTraces, layout: liveLayout(series, theme) });
  // 2. The load on the formwork, with the server's per-course figures.
  const loadTraces = [line(t, series.load.kN, theme.b, 1.6, "on the formwork")];
  if (series.load.checks.length) {
    loadTraces.push({ x: series.load.checks.map((c) => c.t),
      y: series.load.checks.map((c) => c.kN), type: "scatter", mode: "markers",
      name: "solver, per course", marker: { color: theme.ink, size: 4, symbol: "circle-open" },
      hovertemplate: "stage %{text}: %{y:.2f} kN<extra></extra>",
      text: series.load.checks.map((c) => String(c.stage)) });
  }
  specs.push({ id: "live-load", name: "Load on the formwork", unit: "kN",
    reading: (k) => series.load.kN[k], readingLabel: "placed",
    aside: () => "q " + series.load.qKNm2.toFixed(2) + " kN/m²",
    data: loadTraces, layout: liveLayout(series, theme) });
  // 3. Columns: force, with the strain on the reading. No card at all for
  // a study whose contract carries no column forces: an empty plot reads
  // as a fault, and the notes say why there is none.
  if (series.columns.source !== "none") {
    const columnTraces = series.columns.members.length
      ? series.columns.members.map((row) =>
        line(t, row.series, theme.c, 1.2, "column " + (row.index + 1)))
      : [edge(t, series.columns.min, "least"),
        edge(t, series.columns.max, "most", "tonexty", theme.cFill),
        line(t, series.columns.mean, theme.c, 1.4, "mean")];
    specs.push({ id: "live-columns", name: "Column force", unit: "kN",
      reading: (k) => series.columns.max[k], readingLabel: "most loaded",
      aside: (k) => series.columns.strain.microstrainMax[k].toFixed(1) + " µε",
      data: columnTraces, layout: liveLayout(series, theme) });
  }
  // 4. Thrust at the supports.
  specs.push({ id: "live-thrust", name: "Thrust at the supports", unit: "kN",
    reading: (k) => series.thrust.horizontalKN[k], readingLabel: "horizontal",
    aside: (k) => series.thrust.verticalKN[k].toFixed(1) + " kN vertical",
    data: [line(t, series.thrust.horizontalKN, theme.a, 1.6, "horizontal"),
      line(t, series.thrust.verticalKN, theme.b, 1.2, "vertical", "dot")],
    layout: liveLayout(series, theme) });
  return specs;
}

// The series as a sheet, one row per sample, for the physical model's
// own readings to be laid beside.
export function seriesToCsv(series, study) {
  const head = ["t_s", "load_kN", "placed_area_m2", "cable_mean_kN", "cable_max_kN",
    "cable_min_kN"];
  for (const row of series.cables.top) head.push("cable_" + row.edge + "_kN");
  head.push("column_max_kN", "column_mean_kN", "column_strain_max_microstrain");
  for (const row of series.columns.members) head.push("column_" + (row.index + 1) + "_kN");
  head.push("thrust_horizontal_kN", "thrust_vertical_kN");
  const lines = ["# " + study + ", prestress " + Math.round(series.cables.prestress * 100)
    + "% of final thrust, q " + series.load.qKNm2.toFixed(3) + " kN/m2",
  "# " + series.notes.join(" | "), head.join(",")];
  const f = (v) => (Math.round(v * 10000) / 10000).toString();
  for (let k = 0; k < series.t.length; k++) {
    const row = [f(series.t[k]), f(series.load.kN[k]), f(series.load.areaM2[k]),
      f(series.cables.mean[k]), f(series.cables.max[k]), f(series.cables.min[k])];
    for (const top of series.cables.top) row.push(f(top.series[k]));
    row.push(f(series.columns.max[k]), f(series.columns.mean[k]),
      f(series.columns.strain.microstrainMax[k]));
    for (const member of series.columns.members) row.push(f(member.series[k]));
    row.push(f(series.thrust.horizontalKN[k]), f(series.thrust.verticalKN[k]));
    lines.push(row.join(","));
  }
  return lines.join("\n") + "\n";
}
