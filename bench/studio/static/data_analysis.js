// The Data sheet's Analysis tab and its Graphs: the study's figures,
// judged against the material's limits.
//
// Param, in September: "this new analysis tab actually helps us make
// sense of the data... It should also be aware of the material used to
// know its limits". And on 11 October 2026: "i dont think we need all
// this descriptive text... if theres over explanation of things instead
// of just showing the data with red for bad, and a basic layout for
// information, then we need to remove it." So the tab is tables of name,
// value and limit, a figure past its limit in deep red, and no sentences:
// no pills, no recommendations, no disclaimer.
//
// Everything here is pure: plain data in, HTML strings and chart specs
// out, no three.js and no DOM, so the whole tab is testable under node
// the way fields.js is. studio.js owns the wiring and the plotting
// library; this module owns the judgement.

// Indicative strength values, MPa, in the spirit of the Eurocodes'
// design values, NOT project design values. Each entry's comment says
// where its numbers lean on; since his ruling of 11 October 2026 that is
// no longer repeated on screen. Tension for the unreinforced materials
// is the number that matters most in a funicular shell: the whole game
// is keeping it near zero. slender is the band of span over thickness
// the material's shells commonly live in, stocky to proven thin work: a
// shell outside it goes red.
export const MATERIAL_LIMITS = {
  // EC2-style: fcd = fck/1.5 with fck 30 MPa; tension as fctk,0.05/1.5
  // for unreinforced work.
  concrete: {
    label: "Concrete C30/37",
    compression: 20.0, tension: 1.3,
    slender: [8, 300],
  },
  // EC2-style: fcd = 50/1.5; tension as fctk,0.05/1.5, unreinforced.
  "concrete-c50": {
    label: "Concrete C50/60",
    compression: 33.3, tension: 1.9,
    slender: [8, 300],
  },
  // EC2-style: fcd = 25/1.5; sprayed placement, no reinforcement assumed.
  "concrete-sprayed": {
    label: "Sprayed concrete C25/30",
    compression: 16.7, tension: 1.2,
    slender: [8, 250],
  },
  // EC5-style: fc,0,k 24 and ft,0,k 19.2 with kmod 0.8 over gammaM 1.25.
  timber: {
    label: "Timber GL24h",
    compression: 15.4, tension: 12.3,
    slender: [10, 120],
  },
  // EC6-style: fk about 5 MPa over gammaM 2.2; joint tension taken as
  // next to nothing.
  brick: {
    label: "Brick masonry",
    compression: 2.4, tension: 0.1,
    slender: [10, 60],
  },
  // Thin-tile (timbrel) masonry, indicative; the mortar bed governs.
  tile: {
    label: "Fired clay tile",
    compression: 3.5, tension: 0.2,
    slender: [15, 80],
  },
  // Limestone masonry, indicative; the joints govern tension.
  stone: {
    label: "Limestone",
    compression: 8.0, tension: 0.2,
    slender: [8, 50],
  },
};

// Densities, kg/m3, duplicating staging.py's table (which itself mirrors
// ananke_fea) so the tab can weigh the shell without a server call.
export const DENSITIES = {
  concrete: 2400, "concrete-c50": 2400, "concrete-sprayed": 2300,
  timber: 385, brick: 1900, tile: 1800, stone: 2500,
};

// Where something is, in an architect's words rather than coordinates,
// a word or two each (his ruling of 11 October 2026): height band first,
// then compass bearing from the plan centre, "crown, north-east". North
// is +y, matching the sun widget's compass.
export function describeLocation(centroid, bounds) {
  const height = bounds.max[2] - bounds.min[2] || 1;
  const zf = (centroid[2] - bounds.min[2]) / height;
  const band = zf > 0.7 ? "crown" : zf < 0.3 ? "springing" : "flank";
  const cx = (bounds.min[0] + bounds.max[0]) / 2;
  const cy = (bounds.min[1] + bounds.max[1]) / 2;
  const dx = centroid[0] - cx, dy = centroid[1] - cy;
  const reach = Math.max(bounds.max[0] - bounds.min[0],
    bounds.max[1] - bounds.min[1]) / 2 || 1;
  if (Math.hypot(dx, dy) < 0.15 * reach) return band + ", centre";
  const octants = ["east", "north-east", "north", "north-west",
    "west", "south-west", "south", "south-east"];
  const angle = Math.atan2(dy, dx);
  const index = ((Math.round(angle / (Math.PI / 4)) % 8) + 8) % 8;
  return band + ", " + octants[index];
}

function faceCentroid(face, vertices) {
  const sum = [0, 0, 0];
  for (const v of face) {
    sum[0] += vertices[v][0];
    sum[1] += vertices[v][1];
    sum[2] += vertices[v][2];
  }
  return sum.map((total) => total / face.length);
}

// Everything the tables and the graphs need, computed once from the
// bundle and the (possibly null) converged final stage.
export function computeAnalysisInput(bundle, stage) {
  const vertices = bundle.analysis_mesh.vertices;
  const bounds = { min: [...vertices[0]], max: [...vertices[0]] };
  for (const v of vertices) {
    for (let axis = 0; axis < 3; axis++) {
      bounds.min[axis] = Math.min(bounds.min[axis], v[axis]);
      bounds.max[axis] = Math.max(bounds.max[axis], v[axis]);
    }
  }
  const span = Math.max(bounds.max[0] - bounds.min[0],
    bounds.max[1] - bounds.min[1]);
  const thickness = bundle.provenance.thickness;
  const staging = bundle.staging;
  const stages = (staging && staging.stages) || [];
  const unconverged = [];
  stages.forEach((row, index) => {
    const struck = row.struck_now;
    if (struck && struck.status !== "unavailable" && !struck.converged) {
      unconverged.push(index + 1);
    }
  });

  const input = {
    material: bundle.material,
    limits: MATERIAL_LIMITS[bundle.material] || null,
    thickness, span, bounds,
    slenderness: thickness > 0 ? span / thickness : null,
    stagesTotal: stages.length,
    unconverged,
    formworkKN: stages.length
      ? (stages[stages.length - 1].formwork_carries_newtons || 0) / 1000
      : null,
    hasStage: !!stage,
    verification: bundle.verification || null,
    memberForces: bundle.member_forces || null,
    stageSeries: stages.map((row, index) => ({
      stage: index + 1,
      tension: row.struck_now && row.struck_now.peak_tension != null
        ? row.struck_now.peak_tension / 1e6 : null,
      compression: row.struck_now && row.struck_now.peak_compression != null
        ? Math.abs(row.struck_now.peak_compression) / 1e6 : null,
      formworkKN: (row.formwork_carries_newtons || 0) / 1000,
      displacementMM: row.struck_now && row.struck_now.peak_displacement != null
        ? row.struck_now.peak_displacement * 1000 : null,
      weightKN: (row.placed_weight_newtons || 0) / 1000,
    })),
  };

  // The member-force census: the funicular measure. In the exporter's
  // convention compression is negative, so the share of members at or
  // below zero says how honestly the form keeps its compression promise.
  const forces = bundle.member_forces || [];
  if (forces.length) {
    let compressionCount = 0, worstC = 0, worstT = 0;
    for (const force of forces) {
      if (force <= 0) {
        compressionCount += 1;
        worstC = Math.min(worstC, force);
      } else {
        worstT = Math.max(worstT, force);
      }
    }
    input.forceCensus = {
      members: forces.length,
      compressionCount,
      tensionCount: forces.length - compressionCount,
      compressionShare: compressionCount / forces.length,
      worstCompressionKN: -worstC / 1e3,
      worstTensionKN: worstT / 1e3,
    };
  }

  // The supports, read as thrust: how much the vault pushes outward and
  // how steeply the resultant leaves the springing. The angle is judged
  // only on supports doing real work, so a near-idle node's noise never
  // names the "steepest" thrust.
  const reactionRows = Object.entries(bundle.reactions || {});
  if (reactionRows.length) {
    let maxMagnitude = 0;
    for (const [, vector] of reactionRows) {
      maxMagnitude = Math.max(maxMagnitude,
        Math.hypot(vector[0], vector[1], vector[2]));
    }
    let totalVertical = 0, worst = null, steepest = null;
    for (const [node, vector] of reactionRows) {
      const magnitude = Math.hypot(vector[0], vector[1], vector[2]);
      totalVertical += vector[2];
      if (!worst || magnitude > worst.magnitude) worst = { node, magnitude };
      if (magnitude >= 0.05 * maxMagnitude) {
        const outward = Math.hypot(vector[0], vector[1]);
        const degrees =
          Math.atan2(outward, Math.abs(vector[2])) * 180 / Math.PI;
        if (!steepest || degrees > steepest.degrees) {
          steepest = { node, degrees, outwardKN: outward / 1e3 };
        }
      }
    }
    input.reactionStory = {
      count: reactionRows.length,
      totalVerticalKN: totalVertical / 1e3,
      worstKN: worst.magnitude / 1e3,
      worstWhere: vertices[+worst.node]
        ? describeLocation(vertices[+worst.node], bounds) : null,
      steepestDeg: steepest ? steepest.degrees : null,
      steepestOutwardKN: steepest ? steepest.outwardKN : null,
      steepestWhere: steepest && vertices[+steepest.node]
        ? describeLocation(vertices[+steepest.node], bounds) : null,
    };
  }

  // What the shell carries and what it is: total applied load, surface
  // area (polygon fan, so quads count too), and a weight for the load to
  // stand against -- the solver's own figure when a stage carries one,
  // else area x thickness x density.
  const loadRows = Object.values(bundle.loads || {});
  if (loadRows.length) {
    let total = 0;
    for (const vector of loadRows) {
      total += Math.hypot(vector[0], vector[1], vector[2]);
    }
    input.totalLoadKN = total / 1e3;
  }
  let area = 0;
  for (const face of bundle.analysis_mesh.faces) {
    for (let i = 2; i < face.length; i++) {
      const a = vertices[face[0]], b = vertices[face[i - 1]],
        c = vertices[face[i]];
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      area += Math.hypot(u[1] * w[2] - u[2] * w[1],
        u[2] * w[0] - u[0] * w[2],
        u[0] * w[1] - u[1] * w[0]) / 2;
    }
  }
  input.shellArea = area;
  if (input.totalLoadKN != null && area > 0) {
    input.loadPerM2 = input.totalLoadKN / area;
  }
  // What the vault was WEIGHED as. When a skin overrides the structural
  // class's own density the tab has to say so (the row is named Skin
  // density), or the reader will assume concrete and misread every
  // number under it.
  input.density = bundle.provenance.density
    || DENSITIES[bundle.material] || null;
  input.densityFromSkin = !!bundle.provenance.density_from_skin;
  // The estimate weighs the vault with the SAME density the solve was
  // given, not the structural table's: a copper shell whose Skin density
  // row reads 8,940 kg/m3 must not then be weighed as concrete here.
  input.selfWeightKN = stage && stage.self_weight_newtons != null
    ? stage.self_weight_newtons / 1e3
    : input.density && thickness > 0 && area > 0
      ? area * thickness * input.density * 9.81 / 1e3
      : null;

  // The build's tender moment and its handover: the stage that would
  // suffer most if struck early, where the formwork works hardest, and
  // the stage from which the carry stays below a tenth of that peak --
  // the vault carrying itself from there on.
  if (input.stageSeries.length) {
    let critical = null, peakCarry = null;
    for (const row of input.stageSeries) {
      if (row.tension != null
          && (!critical || row.tension > critical.tension)) critical = row;
      if (!peakCarry || row.formworkKN > peakCarry.formworkKN) peakCarry = row;
    }
    input.criticalStage = critical;
    if (peakCarry.formworkKN > 0) {
      input.formworkPeak = { stage: peakCarry.stage, kN: peakCarry.formworkKN };
      // Some staging models let the formwork hold everything placed until
      // striking: the carry then GROWS to the end, the last stage is never
      // under a tenth of the peak, and no stage is named self-supporting.
      let selfFrom = null;
      for (const row of input.stageSeries) {
        if (row.formworkKN <= 0.1 * peakCarry.formworkKN) {
          if (selfFrom == null) selfFrom = row.stage;
        } else {
          selfFrom = null;
        }
      }
      input.selfSupportingFrom = selfFrom;
    }
  }

  if (stage) {
    input.peakTension = stage.peak_tension / 1e6;
    input.peakCompression = Math.abs(stage.peak_compression) / 1e6;
    // The worst faces, for the "where" of each peak, and while walking
    // them the extent: how many faces run beyond half of each limit and
    // beyond the limit itself.
    let worstT = -Infinity, worstC = -Infinity, faceT = null, faceC = null;
    let hotT = 0, overT = 0, hotC = 0, overC = 0, faceCount = 0;
    const faces = bundle.analysis_mesh.faces;
    for (const [key, pair] of Object.entries(stage.stresses || {})) {
      const tension = Math.max(pair.top[0], pair.bottom[0]);
      const compression = Math.max(-pair.top[1], -pair.bottom[1]);
      if (tension > worstT) { worstT = tension; faceT = faces[+key]; }
      if (compression > worstC) { worstC = compression; faceC = faces[+key]; }
      faceCount += 1;
      if (input.limits) {
        if (tension / 1e6 >= 0.5 * input.limits.tension) hotT += 1;
        if (tension / 1e6 >= input.limits.tension) overT += 1;
        if (compression / 1e6 >= 0.5 * input.limits.compression) hotC += 1;
        if (compression / 1e6 >= input.limits.compression) overC += 1;
      }
    }
    input.tensionWhere = faceT
      ? describeLocation(faceCentroid(faceT, vertices), bounds) : null;
    input.compressionWhere = faceC
      ? describeLocation(faceCentroid(faceC, vertices), bounds) : null;
    if (input.limits && faceCount) {
      input.stressExtent = {
        faces: faceCount,
        hotTension: hotT, overTension: overT,
        hotCompression: hotC, overCompression: overC,
      };
    }
    // displacements is a dict keyed by node id, not an array (measured on
    // the real bundle), and the solver ships its own peak besides. The
    // dict is still walked for the ARGMAX so the movement gets a place.
    let deflection = stage.peak_displacement != null
      ? stage.peak_displacement : 0;
    let moved = 0, movedNode = null;
    for (const [node, d] of Object.entries(stage.displacements || {})) {
      const magnitude = Math.hypot(d[0], d[1], d[2]);
      if (magnitude > moved) { moved = magnitude; movedNode = node; }
    }
    if (!deflection) deflection = moved;
    input.deflection = deflection;
    input.deflectionWhere = movedNode != null && vertices[+movedNode]
      ? describeLocation(vertices[+movedNode], bounds) : null;
  } else if (input.verification && input.verification.stress) {
    input.peakTension = (input.verification.stress.peak_tension || 0) / 1e6;
    input.peakCompression =
      Math.abs(input.verification.stress.peak_compression || 0) / 1e6;
    input.deflection = input.verification.displacement
      ? input.verification.displacement.peak_magnitude : null;
    input.peaksOnly = true;
  }

  if (input.limits && input.peakTension != null) {
    input.tensionUtilisation = input.peakTension / input.limits.tension;
    input.compressionUtilisation =
      input.peakCompression / input.limits.compression;
    const governing = Math.max(input.tensionUtilisation,
      input.compressionUtilisation);
    input.headroom = governing > 0 ? 1 / governing : null;
  }
  if (input.deflection && span > 0) {
    input.deflectionRatio = span / input.deflection;   // the N of L/N
  }
  return input;
}

// The Graphs tab's utilisation bars wear these bands' colours. The words
// that went with them were pills on the Analysis tab, gone with his
// ruling of 11 October 2026.
export function utilisationBand(ratio) {
  if (ratio == null) return { cls: "warn" };
  if (ratio >= 1) return { cls: "bad" };
  if (ratio >= 0.6) return { cls: "warn" };
  return { cls: "good" };
}

function mpa(value) {
  return value.toFixed(2) + " MPa";
}

// A member force in readable units: a 14 N pull must not print as
// "0.0 kN" (a real bundle's worst tension did exactly that).
function forceLabel(kN) {
  return kN >= 0.1 ? kN.toFixed(1) + " kN" : Math.round(kN * 1000) + " N";
}

// A whole number grouped in thousands, as the Cable net answer writes
// its newtons.
function whole(n) {
  return Math.round(n).toLocaleString("en-GB");
}

function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// The lines the old narrative judged by, kept as the red lines now the
// sentences are gone: the customary L/250 serviceability ratio, a thrust
// 35 degrees off vertical (the Support thrust lens buckets at the same
// line), and 85% of members in compression, under which the form had
// drifted from the funicular.
const SPAN_RATIO_LIMIT = 250;
const THRUST_LIMIT_DEG = 35;
const COMPRESSION_SHARE_MIN = 0.85;

// A figure past its limit in deep red, as the Cable net answer shows a
// shortfall (his ruling of 11 October 2026: "red for bad"); nothing marks
// a good one.
function over(text, bad) {
  return bad ? '<span class="over">' + text + "</span>" : text;
}

// One row: name, value, limit, the limit cell left empty where there is
// none.
function row(name, value, limit) {
  return "<tr><th>" + name + "</th><td>" + value + "</td><td>"
    + (limit || "") + "</td></tr>";
}

// One group: a bare heading over its table, or nothing when it has no
// rows.
function group(heading, rows) {
  return rows.length
    ? "<h3>" + heading + "</h3><table>" + rows.join("") + "</table>"
    : "";
}

// The Analysis tab: Stresses, Deflection, Load path, Material and Build,
// each a table of name, value and limit (his ruling of 11 October 2026:
// "just showing the data with red for bad, and a basic layout for
// information"). Every figure the old narrative put in a sentence is a
// row here; where it judged a figure (over the limit, slacker than L/250,
// thinner than common practice), that judgement is the red on the value,
// and "approaching" is not red.
export function buildAnalysisHtml(input) {
  const limits = input.limits;
  const parts = [];
  if (!input.hasStage && !input.peaksOnly) {
    parts.push("<h3>No staged run</h3>");
  } else {
    const stresses = [row("Peak tension",
      over(mpa(input.peakTension), input.tensionUtilisation >= 1),
      limits ? mpa(limits.tension) : "")];
    if (input.tensionWhere) stresses.push(row("Tension at", input.tensionWhere));
    stresses.push(row("Peak compression",
      over(mpa(input.peakCompression), input.compressionUtilisation >= 1),
      limits ? mpa(limits.compression) : ""));
    if (input.compressionWhere) {
      stresses.push(row("Compression at", input.compressionWhere));
    }
    if (input.stressExtent) {
      const extent = input.stressExtent;
      stresses.push(
        row("Faces", whole(extent.faces)),
        row("Faces over half the limit (tension)", whole(extent.hotTension)),
        row("Faces over the limit (tension)",
          over(whole(extent.overTension), extent.overTension > 0)),
        row("Faces over half the limit (compression)",
          whole(extent.hotCompression)),
        row("Faces over the limit (compression)",
          over(whole(extent.overCompression), extent.overCompression > 0)));
    }
    parts.push(group("Stresses", stresses));
    if (input.deflection != null) {
      const deflection = [row("Deflection",
        (input.deflection * 1000).toFixed(2) + " mm")];
      if (input.deflectionWhere) {
        deflection.push(row("Deflection at", input.deflectionWhere));
      }
      if (input.deflectionRatio) {
        deflection.push(row("Span ratio",
          over("L/" + whole(input.deflectionRatio),
            input.deflectionRatio < SPAN_RATIO_LIMIT),
          "L/" + SPAN_RATIO_LIMIT));
      }
      parts.push(group("Deflection", deflection));
    }
  }

  // The load path reads bundle-level data (member forces, reactions,
  // loads), so it shows even before any staged run exists.
  const path = [];
  if (input.forceCensus) {
    const census = input.forceCensus;
    path.push(row("Members", whole(census.members)),
      row("In compression",
        over(Math.round(census.compressionShare * 100) + "%",
          census.compressionShare < COMPRESSION_SHARE_MIN),
        "min " + Math.round(COMPRESSION_SHARE_MIN * 100) + "%"),
      row("Members in tension", whole(census.tensionCount)));
    if (census.tensionCount) {
      path.push(row("Worst tension", forceLabel(census.worstTensionKN)));
    }
    if (census.compressionCount) {
      path.push(row("Worst compression",
        forceLabel(census.worstCompressionKN)));
    }
  }
  if (input.reactionStory) {
    const story = input.reactionStory;
    path.push(row("Supports", whole(story.count)),
      row("Vertical load", story.totalVerticalKN.toFixed(1) + " kN"),
      row("Worst support", story.worstKN.toFixed(1) + " kN"));
    if (story.worstWhere) path.push(row("Worst support at", story.worstWhere));
    if (story.steepestDeg != null) {
      path.push(row("Steepest thrust",
        over(Math.round(story.steepestDeg) + "&deg;",
          story.steepestDeg >= THRUST_LIMIT_DEG),
        THRUST_LIMIT_DEG + "&deg;"));
      if (story.steepestWhere) {
        path.push(row("Steepest thrust at", story.steepestWhere));
      }
      path.push(row("Outward push", story.steepestOutwardKN.toFixed(1) + " kN"));
    }
  }
  if (input.totalLoadKN != null || input.selfWeightKN != null) {
    if (input.totalLoadKN != null) {
      path.push(row("Load", input.totalLoadKN.toFixed(1) + " kN"));
    }
    path.push(row("Area", input.shellArea.toFixed(1) + " m<sup>2</sup>"));
    if (input.loadPerM2 != null) {
      path.push(row("Load per m<sup>2</sup>",
        input.loadPerM2.toFixed(1) + " kN/m<sup>2</sup>"));
    }
    if (input.selfWeightKN != null) {
      path.push(row("Shell weight",
        (input.selfWeightKN / 9.81).toFixed(1) + " t"));
    }
  }
  parts.push(group("Load path", path));

  // With no limits on file for the material key the rows are the raw
  // figures alone, their limit cells empty and nothing red.
  const material = [];
  if (limits) {
    material.push(row("Material", limits.label),
      row("Compression limit", mpa(limits.compression)),
      row("Tension limit", mpa(limits.tension)));
  } else if (input.material) {
    material.push(row("Material", escapeHtml(input.material)));
  }
  if (input.density) {
    material.push(row(input.densityFromSkin ? "Skin density" : "Density",
      whole(input.density) + " kg/m<sup>3</sup>"));
  }
  if (input.thickness > 0) {
    material.push(row("Thickness", whole(input.thickness * 1000) + " mm"));
  }
  material.push(row("Span", input.span.toFixed(1) + " m"));
  if (input.slenderness != null) {
    const band = limits ? limits.slender : null;
    material.push(row("Slenderness",
      over("1:" + whole(input.slenderness), !!band
        && (input.slenderness > band[1] || input.slenderness < band[0])),
      band ? "1:" + band[0] + " to 1:" + band[1] : ""));
  }
  if (input.headroom != null) {
    // Under 1x the load already passes a limit, as the red peak says.
    material.push(row("Headroom",
      over(input.headroom.toFixed(1) + "x", input.headroom <= 1)));
  }
  parts.push(group("Material", material));

  if (input.stagesTotal) {
    const build = [row("Stages", whole(input.stagesTotal))];
    if (input.unconverged.length) {
      build.push(row("Not in equilibrium",
        over((input.unconverged.length > 1 ? "stages " : "stage ")
          + input.unconverged.join(", "), true)));
    }
    if (input.formworkKN != null) {
      build.push(row("Formwork at final stage",
        input.formworkKN.toFixed(1) + " kN"));
    }
    const critical = input.criticalStage;
    if (critical && critical.tension != null) {
      build.push(row("Critical stage", String(critical.stage)),
        row("Tension there",
          over(mpa(critical.tension), !!limits && critical.tension >= limits.tension),
          limits ? mpa(limits.tension) : ""));
      if (input.peakTension > 0) {
        const ratio = critical.tension / input.peakTension;
        build.push(row("Against finished",
          (ratio >= 10 ? Math.round(ratio) : ratio.toFixed(1)) + "x"));
      }
    }
    if (input.formworkPeak) {
      build.push(row("Formwork peak", input.formworkPeak.kN.toFixed(1)
        + " kN (stage " + input.formworkPeak.stage + ")"));
    }
    if (input.selfSupportingFrom != null) {
      build.push(row("Self-supporting from",
        "stage " + input.selfSupportingFrom));
    }
    parts.push(group("Build", build));
  }
  return parts.join("");
}

// Chart specs the plotting library can draw directly. Pure data: colours
// arrive from the caller so the charts follow the theme.
export function buildGraphSpecs(input, theme) {
  const specs = [];
  const axis = {
    color: theme.ink2, gridcolor: theme.line, zerolinecolor: theme.line,
  };
  const layout = (title, extra) => Object.assign({
    title: { text: title, font: { color: theme.ink, size: 13 } },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: theme.ink2, size: 11 },
    margin: { l: 44, r: 12, t: 34, b: 34 },
    height: 230,
    xaxis: Object.assign({}, axis), yaxis: Object.assign({}, axis),
    showlegend: true,
    legend: { orientation: "h", y: -0.2, font: { color: theme.ink2 } },
  }, extra || {});

  if (input.stageSeries.some((row) => row.tension != null)) {
    const stagesAxis = input.stageSeries.map((row) => row.stage);
    const data = [
      { x: stagesAxis, y: input.stageSeries.map((row) => row.tension),
        type: "scatter", mode: "lines+markers", name: "peak tension",
        line: { color: "#cc2211" } },
      { x: stagesAxis, y: input.stageSeries.map((row) => row.compression),
        type: "scatter", mode: "lines+markers", name: "peak compression",
        line: { color: "#2255cc" } },
    ];
    if (input.limits) {
      data.push({ x: stagesAxis,
        y: stagesAxis.map(() => input.limits.tension),
        type: "scatter", mode: "lines", name: "tension limit",
        line: { color: "#cc2211", dash: "dot", width: 1 } });
    }
    specs.push({ id: "graph-stage-stress", data,
      layout: layout("Peak stress, MPa") });
  }
  if (input.stageSeries.some((row) => row.displacementMM != null)) {
    specs.push({ id: "graph-stage-deflection",
      data: [{ x: input.stageSeries.map((row) => row.stage),
        y: input.stageSeries.map((row) => row.displacementMM),
        type: "scatter", mode: "lines+markers", name: "peak deflection",
        line: { color: theme.accent } }],
      layout: layout("Peak deflection, mm",
        { showlegend: false }) });
  }
  if (input.stageSeries.length) {
    const handover = [{ x: input.stageSeries.map((row) => row.stage),
      y: input.stageSeries.map((row) => row.formworkKN),
      type: "bar", name: "formwork carries",
      marker: { color: theme.accent } }];
    const weighed = input.stageSeries.some((row) => row.weightKN > 0);
    if (weighed) {
      handover.push({ x: input.stageSeries.map((row) => row.stage),
        y: input.stageSeries.map((row) => row.weightKN),
        type: "scatter", mode: "lines+markers", name: "placed weight",
        line: { color: theme.ink2 } });
    }
    specs.push({ id: "graph-formwork", data: handover,
      layout: layout("Formwork carry, kN", { showlegend: weighed }) });
  }
  if (input.tensionUtilisation != null) {
    const bands = [utilisationBand(input.tensionUtilisation),
      utilisationBand(input.compressionUtilisation)];
    const bandColours = { good: "#3f9e57", warn: "#c99a2e", bad: "#c24936" };
    specs.push({ id: "graph-utilisation",
      data: [
        { x: ["tension", "compression"],
          y: [input.tensionUtilisation * 100,
            input.compressionUtilisation * 100],
          type: "bar", name: "utilisation",
          marker: { color: bands.map((band) => bandColours[band.cls]) } },
        { x: ["tension", "compression"], y: [100, 100],
          type: "scatter", mode: "lines", name: "limit",
          line: { color: "#cc2211", dash: "dot", width: 1 } },
      ],
      layout: layout("Utilisation, %") });
  }
  if (input.memberForces && input.memberForces.length) {
    // Binned here, not by the plotting library, so the histogram is
    // testable arithmetic rather than a library behaviour.
    const kn = input.memberForces.map((force) => force / 1e3);
    const low = Math.min(...kn), high = Math.max(...kn);
    const bins = 24;
    const width = (high - low) / bins || 1;
    const counts = new Array(bins).fill(0);
    for (const value of kn) {
      counts[Math.min(bins - 1, Math.floor((value - low) / width))] += 1;
    }
    specs.push({ id: "graph-forces",
      data: [{ x: counts.map((_, i) => low + (i + 0.5) * width),
        y: counts, type: "bar", name: "members",
        marker: { color: theme.accent } }],
      layout: layout("Member force, kN",
        { showlegend: false, bargap: 0.05 }) });
  }
  return specs;
}
