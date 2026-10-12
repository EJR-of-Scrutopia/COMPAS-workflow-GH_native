// The column as specced, in the steel chosen (Param, 2026-10-12: "i also would
// like the column to have a thickness and shape to have what we have specced
// also. if we can choose different steel for that would be good too"). Pure,
// so it runs under node in the tests as it does in the page. The catalogue is
// /api/column-steel's answer: tubes, grades, finishes and the spec.

const byKey = (rows, key) => rows.find((row) => row.key === key) || null;

function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// The tube nearest a diameter, mm (his answer: each study starts at the tube
// nearest the one its export swept); null for no diameter.
export function nearestTube(tubes, diameterMm) {
  const wanted = Number(diameterMm);
  if (diameterMm == null || !(wanted > 0) || !tubes.length) return null;
  let best = tubes[0];
  for (const tube of tubes) {
    if (Math.abs(tube.diameter_mm - wanted) < Math.abs(best.diameter_mm - wanted)) best = tube;
  }
  return best.key;
}

// A study's tube, grade and finish: what it was given if the catalogue still
// holds it, else the tube nearest its export in the spec's steel and finish. A
// grade that wears one finish (stainless) wears it whatever was picked.
export function columnChoice(stored, catalogue, exportDiameterMm) {
  const spec = catalogue.spec;
  const kept = stored || {};
  const tube = byKey(catalogue.tubes, kept.tube) ? kept.tube
    : nearestTube(catalogue.tubes, exportDiameterMm) || spec.tube;
  const grade = byKey(catalogue.grades, kept.grade) ? kept.grade : spec.grade;
  const bound = byKey(catalogue.grades, grade).finish;
  const finish = bound || (byKey(catalogue.finishes, kept.finish) ? kept.finish : spec.finish);
  return { tube, grade, finish };
}

// The tube a run and its re-judging take: diameter and wall, mm, and the steel.
export function columnTube(catalogue, choice, wallMm) {
  const grade = byKey(catalogue.grades, choice.grade);
  return {
    key: choice.tube, diameter: byKey(catalogue.tubes, choice.tube).diameter_mm,
    wall: Number(wallMm), grade: choice.grade,
    steel: { fy: grade.fy_mpa, e: grade.e_mpa, alpha: grade.alpha, lambda0: grade.lambda0 },
  };
}

// How the tube is drawn: its outer and inner radius, metres, and its finish.
export function columnLook(catalogue, choice, wallMm) {
  const diameter = byKey(catalogue.tubes, choice.tube).diameter_mm;
  const wall = Math.min(Math.max(Number(wallMm) || 0, 0), diameter / 2);
  return { outer: diameter / 2000, inner: (diameter - 2 * wall) / 2000,
           render: byKey(catalogue.finishes, choice.finish).render };
}

export function columnOptionsHtml(rows, selected) {
  return rows.map((row) => `<option value="${escapeHtml(row.key)}"`
    + `${row.key === selected ? " selected" : ""}>${escapeHtml(row.label)}</option>`).join("");
}
