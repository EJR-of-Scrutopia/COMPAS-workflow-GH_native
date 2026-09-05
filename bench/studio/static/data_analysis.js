// The Data sheet's interpretive half: what the numbers MEAN.
//
// Param: "this new analysis tab actually helps us make sense of the data.
// It can remark on how much stress there is and where the location is to
// be an issue or not, suggesting fixing recommendations. It should also be
// aware of the material used to know its limits... We should narrative
// this information properly too, so its clean visually and also says what
// it can and cant do."
//
// Everything here is pure: plain data in, HTML strings and chart specs
// out, no three.js and no DOM, so the whole narrative is testable under
// node the way fields.js is. studio.js owns the wiring and the plotting
// library; this module owns the judgement and the words.

// Indicative strength values, MPa, in the spirit of the Eurocodes'
// design values -- NOT project design values. Each entry says where its
// numbers lean on so the narrative can repeat that honestly. Tension for
// the unreinforced materials is the number that matters most in a
// funicular shell: the whole game is keeping it near zero.
export const MATERIAL_LIMITS = {
  concrete: {
    label: "Concrete C30/37",
    compression: 20.0, tension: 1.3,
    basis: "EC2-style: fcd = fck/1.5 with fck 30 MPa; tension as "
      + "fctk,0.05/1.5 for unreinforced work",
    slender: [8, 300],
  },
  "concrete-c50": {
    label: "Concrete C50/60",
    compression: 33.3, tension: 1.9,
    basis: "EC2-style: fcd = 50/1.5; tension as fctk,0.05/1.5, unreinforced",
    slender: [8, 300],
  },
  "concrete-sprayed": {
    label: "Sprayed concrete C25/30",
    compression: 16.7, tension: 1.2,
    basis: "EC2-style: fcd = 25/1.5; sprayed placement, no reinforcement "
      + "assumed",
    slender: [8, 250],
  },
  timber: {
    label: "Timber GL24h",
    compression: 15.4, tension: 12.3,
    basis: "EC5-style: fc,0,k 24 and ft,0,k 19.2 with kmod 0.8 over "
      + "gammaM 1.25",
    slender: [10, 120],
  },
  brick: {
    label: "Brick masonry",
    compression: 2.4, tension: 0.1,
    basis: "EC6-style: fk about 5 MPa over gammaM 2.2; joint tension "
      + "taken as next to nothing",
    slender: [10, 60],
  },
  tile: {
    label: "Fired clay tile",
    compression: 3.5, tension: 0.2,
    basis: "thin-tile (timbrel) masonry, indicative; the mortar bed "
      + "governs",
    slender: [15, 80],
  },
  stone: {
    label: "Limestone",
    compression: 8.0, tension: 0.2,
    basis: "limestone masonry, indicative; the joints govern tension",
    slender: [8, 50],
  },
};

// Densities, kg/m3, duplicating staging.py's table (which itself mirrors
// ananke_fea) so the narrative can weigh the shell without a server call.
export const DENSITIES = {
  concrete: 2400, "concrete-c50": 2400, "concrete-sprayed": 2300,
  timber: 385, brick: 1900, tile: 1800, stone: 2500,
};

// Where something is, in an architect's words rather than coordinates:
// height band first, then compass bearing from the plan centre. North is
// +y, matching the sun widget's compass.
export function describeLocation(centroid, bounds) {
  const height = bounds.max[2] - bounds.min[2] || 1;
  const zf = (centroid[2] - bounds.min[2]) / height;
  const band = zf > 0.7 ? "near the crown"
    : zf < 0.3 ? "at the springing level" : "on the flank";
  const cx = (bounds.min[0] + bounds.max[0]) / 2;
  const cy = (bounds.min[1] + bounds.max[1]) / 2;
  const dx = centroid[0] - cx, dy = centroid[1] - cy;
  const reach = Math.max(bounds.max[0] - bounds.min[0],
    bounds.max[1] - bounds.min[1]) / 2 || 1;
  if (Math.hypot(dx, dy) < 0.15 * reach) return band + ", centrally";
  const octants = ["east", "north-east", "north", "north-west",
    "west", "south-west", "south", "south-east"];
  const angle = Math.atan2(dy, dx);
  const index = ((Math.round(angle / (Math.PI / 4)) % 8) + 8) % 8;
  return band + ", to the " + octants[index];
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

// Everything the narrative and the graphs need, computed once from the
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
  let unavailable = 0;
  stages.forEach((row, index) => {
    const struck = row.struck_now;
    if (!struck || struck.status === "unavailable") unavailable += 1;
    else if (!struck.converged) unconverged.push(index + 1);
  });

  const input = {
    material: bundle.material,
    limits: MATERIAL_LIMITS[bundle.material] || null,
    thickness, span, bounds,
    slenderness: thickness > 0 ? span / thickness : null,
    stagesTotal: stages.length,
    unconverged,
    allUnavailable: stages.length > 0 && unavailable === stages.length,
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
  input.selfWeightKN = stage && stage.self_weight_newtons != null
    ? stage.self_weight_newtons / 1e3
    : DENSITIES[bundle.material] && thickness > 0 && area > 0
      ? area * thickness * DENSITIES[bundle.material] * 9.81 / 1e3
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
      // striking: the carry then GROWS to the end instead of peaking and
      // falling away, and the handover story must not pretend otherwise.
      input.formworkGrowsToEnd = input.formworkKN != null
        && input.formworkKN >= 0.95 * peakCarry.formworkKN;
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
    // The worst faces, for the "where" of the story -- and while walking
    // them, the extent: how much of the surface runs beyond half of each
    // limit, so the narrative can say spike or field.
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

export function utilisationBand(ratio) {
  if (ratio == null) return { word: "unknown", cls: "warn" };
  if (ratio >= 1) return { word: "over the limit", cls: "bad" };
  if (ratio >= 0.6) return { word: "approaching the limit", cls: "warn" };
  return { word: "comfortable", cls: "good" };
}

function pill(band) {
  return '<span class="pill ' + band.cls + '">' + band.word + "</span>";
}

function mpa(value) {
  return value.toFixed(2) + " MPa";
}

// A member force in readable units: a 14 N pull must not print as
// "0.0 kN" (a real bundle's worst tension did exactly that).
function forceLabel(kN) {
  return kN >= 0.1 ? kN.toFixed(1) + " kN" : Math.round(kN * 1000) + " N";
}

export function buildRecommendations(input) {
  const out = [];
  if (input.tensionUtilisation >= 1) {
    out.push("Tension exceeds what " + input.limits.label.toLowerCase()
      + " can honestly carry"
      + (input.tensionWhere ? " " + input.tensionWhere : "")
      + ". Thicken the shell locally, soften the form toward the "
      + "funicular so the thrust stays inside the section, or add a tie "
      + "where the tension gathers.");
  } else if (input.tensionUtilisation >= 0.6) {
    out.push("Tension is approaching the material's limit"
      + (input.tensionWhere ? " " + input.tensionWhere : "")
      + "; watch it as loads are added, and consider a gentle local "
      + "thickening before it governs.");
  }
  if (input.compressionUtilisation >= 1) {
    out.push("Compression exceeds the design strength"
      + (input.compressionWhere ? " " + input.compressionWhere : "")
      + "; thicken the section there or choose a stronger grade.");
  }
  if (input.reactionStory && input.reactionStory.steepestDeg != null
      && input.reactionStory.steepestDeg >= 35) {
    out.push("The thrust leaves the worst springing at "
      + Math.round(input.reactionStory.steepestDeg)
      + " degrees from vertical ("
      + input.reactionStory.steepestOutwardKN.toFixed(1) + " kN outward"
      + (input.reactionStory.steepestWhere
        ? ", " + input.reactionStory.steepestWhere : "")
      + "): the abutment there must hold that push, or a tie between "
      + "springings must close it.");
  }
  if (input.forceCensus && input.forceCensus.compressionShare < 0.85) {
    out.push("Only " + Math.round(input.forceCensus.compressionShare * 100)
      + "% of members work in compression: the form has drifted from the "
      + "funicular. Revisit the form-finding before sizing anything, "
      + "because thickening cannot buy back a load path.");
  }
  if (input.deflectionRatio != null && input.deflectionRatio < 250) {
    out.push("Deflection is L/" + Math.round(input.deflectionRatio)
      + ", slacker than the customary L/250 serviceability line: "
      + "stiffen the shell or thicken it.");
  }
  if (input.unconverged.length) {
    out.push("Stage" + (input.unconverged.length > 1 ? "s " : " ")
      + input.unconverged.join(", ")
      + " found no equilibrium when struck early: keep the formwork "
      + "under those courses longer, or resequence the build.");
  }
  if (input.slenderness != null && input.limits
      && input.slenderness > input.limits.slender[1]) {
    out.push("At 1:" + Math.round(input.slenderness)
      + " the shell is thinner than " + input.limits.label.toLowerCase()
      + " has commonly been proven to (about 1:" + input.limits.slender[1]
      + "); treat buckling as the governing question, which this tool "
      + "does not check.");
  }
  if (!out.length) {
    out.push("Nothing calls for action at this load: stresses sit "
      + "comfortably inside the material's limits and the deflection is "
      + "small. The margins above say how far the loading could grow.");
  }
  return out;
}

export function buildAnalysisHtml(input) {
  const parts = [];
  if (!input.hasStage && !input.peaksOnly) {
    parts.push("<h3>No staged run yet</h3>");
    parts.push("<p>The narrative reads the staged analysis, and this "
      + "bundle has none. Press <b>Run staged analysis</b> and come back: "
      + "every stage of the build is then solved as if struck at that "
      + "moment, and the story below fills in.</p>");
    if (input.allUnavailable) {
      parts.push("<p>Note: this material carries no FEA preset, so a "
        + "staged run will report verdicts as unavailable rather than "
        + "solved.</p>");
    }
  } else {
    const tBand = utilisationBand(input.tensionUtilisation);
    const cBand = utilisationBand(input.compressionUtilisation);
    parts.push("<h3>The stresses</h3>");
    parts.push("<p>Peak tension is <b>" + mpa(input.peakTension) + "</b> "
      + pill(tBand)
      + (input.tensionWhere ? ", found " + input.tensionWhere : "")
      + ". Peak compression is <b>" + mpa(input.peakCompression) + "</b> "
      + pill(cBand)
      + (input.compressionWhere ? ", found " + input.compressionWhere : "")
      + "." + (input.peaksOnly
        ? " These are the verification file's peaks only; a staged run "
          + "would place them on the surface."
        : "") + "</p>");
    if (input.stressExtent) {
      const extent = input.stressExtent;
      parts.push("<p>Tension beyond half the limit touches <b>"
        + extent.hotTension + " of " + extent.faces + " faces</b>"
        + (extent.overTension
          ? ", and " + extent.overTension + " exceed"
            + (extent.overTension > 1 ? "" : "s") + " it outright"
          : "")
        + (extent.hotTension / extent.faces <= 0.1
          ? ": a local spike, not a field"
          : ": a spread condition, not one bad face")
        + (extent.hotCompression
          ? ". Compression runs past half its limit on "
            + extent.hotCompression + " face"
            + (extent.hotCompression > 1 ? "s" : "") + "."
          : ". Compression stays below half its limit everywhere.")
        + "</p>");
    }
    if (input.limits) {
      parts.push("<p>In a funicular shell the tension number is the one "
        + "to watch: the form exists so the load path stays in "
        + "compression, and tension appearing is the form drifting from "
        + "that promise.</p>");
    }
    if (input.deflection != null) {
      parts.push("<h3>The deflection</h3>");
      parts.push("<p>The worst movement is <b>"
        + (input.deflection * 1000).toFixed(2) + " mm</b>"
        + (input.deflectionWhere ? ", found " + input.deflectionWhere : "")
        + (input.deflectionRatio
          ? ", which over the " + input.span.toFixed(1) + " m span is L/"
            + Math.round(input.deflectionRatio)
            + (input.deflectionRatio >= 250
              ? " -- well inside the customary L/250"
              : " -- slacker than the customary L/250")
          : "") + ".</p>");
    }
  }

  // The load path reads bundle-level data (member forces, reactions,
  // loads), so it speaks even before any staged run exists.
  const path = [];
  if (input.forceCensus) {
    const census = input.forceCensus;
    path.push("Of <b>" + census.members + " members</b>, "
      + Math.round(census.compressionShare * 100)
      + "% work in compression"
      + (census.tensionCount
        ? "; " + census.tensionCount + " pick"
          + (census.tensionCount > 1 ? "" : "s") + " up tension, the "
          + "worst at " + forceLabel(census.worstTensionKN) + " against "
          + forceLabel(census.worstCompressionKN)
          + " in the hardest-pushing strut."
        : " -- every member, the funicular promise kept whole."));
  }
  if (input.reactionStory) {
    const story = input.reactionStory;
    path.push("The vault stands on <b>" + story.count + " supports</b> "
      + "carrying " + story.totalVerticalKN.toFixed(1)
      + " kN of vertical load between them; the hardest-working takes "
      + story.worstKN.toFixed(1) + " kN"
      + (story.worstWhere ? ", " + story.worstWhere : "") + "."
      + (story.steepestDeg != null
        ? " The steepest thrust leaves at <b>"
          + Math.round(story.steepestDeg)
          + " degrees from vertical</b>, an outward push of "
          + story.steepestOutwardKN.toFixed(1)
          + " kN the abutment there must hold."
        : ""));
  }
  if (input.totalLoadKN != null || input.selfWeightKN != null) {
    path.push((input.totalLoadKN != null
      ? "The applied load totals " + input.totalLoadKN.toFixed(1)
        + " kN over about " + input.shellArea.toFixed(1)
        + " m<sup>2</sup> of shell"
        + (input.loadPerM2 != null
          ? " (" + input.loadPerM2.toFixed(1) + " kN/m<sup>2</sup>)" : "")
      : "The shell surface is about " + input.shellArea.toFixed(1)
        + " m<sup>2</sup>")
      + (input.selfWeightKN != null
        ? "; the shell itself weighs about "
          + (input.selfWeightKN / 9.81).toFixed(1) + " tonnes."
        : "."));
  }
  if (path.length) {
    parts.push("<h3>The load path</h3>");
    parts.push(path.map((sentence) => "<p>" + sentence + "</p>").join(""));
  }

  if (input.limits) {
    parts.push("<h3>The material</h3>");
    parts.push("<p><b>" + input.limits.label + "</b>: takes about "
      + mpa(input.limits.compression) + " in compression and "
      + mpa(input.limits.tension) + " in tension before the limit "
      + "(" + input.limits.basis + ").</p>");
    parts.push("<p>The shell is <b>"
      + Math.round(input.thickness * 1000) + " mm</b> thick over a "
      + input.span.toFixed(1) + " m span: a slenderness of 1:"
      + Math.round(input.slenderness) + ". This material's shells "
      + "commonly live between about 1:" + input.limits.slender[0]
      + " (stocky) and 1:" + input.limits.slender[1]
      + " (proven thin work), so "
      + (input.slenderness > input.limits.slender[1]
        ? "this is thinner than common practice: buckling, not strength, "
          + "becomes the question."
        : input.slenderness < input.limits.slender[0]
          ? "this is on the stocky side: weight, not strength, is doing "
            + "the arguing."
          : "this sits inside the comfortable band.") + "</p>");
    if (input.headroom != null) {
      parts.push("<p>Linearly, the current load pattern could grow about "
        + "<b>" + input.headroom.toFixed(1) + "x</b> before the first "
        + "material limit is met. That is a straight-line estimate, not "
        + "a collapse load.</p>");
    }
  } else {
    parts.push("<h3>The material</h3>");
    parts.push("<p>No limits are on file for this material key, so the "
      + "narrative stops at the raw numbers.</p>");
  }

  if (input.stagesTotal) {
    parts.push("<h3>The build</h3>");
    parts.push("<p>" + input.stagesTotal + " staged course"
      + (input.stagesTotal > 1 ? "s" : "") + ", "
      + (input.unconverged.length
        ? "of which stage" + (input.unconverged.length > 1 ? "s " : " ")
          + input.unconverged.join(", ") + " found no equilibrium when "
          + "struck early"
        : "every one standing when struck at its own moment")
      + (input.formworkKN != null
        ? "; the formwork carries " + input.formworkKN.toFixed(1)
          + " kN at the final stage"
        : "") + ".</p>");
    if (input.criticalStage && input.criticalStage.tension != null
        && input.peakTension > 0) {
      const ratio = input.criticalStage.tension / input.peakTension;
      parts.push(ratio >= 1.2
        ? "<p>The tender moment is <b>stage " + input.criticalStage.stage
          + "</b>: struck then, tension would reach "
          + mpa(input.criticalStage.tension) + ", about "
          + (ratio >= 10 ? Math.round(ratio) : ratio.toFixed(1))
          + "x the finished vault's " + mpa(input.peakTension)
          + ". The formwork is not an accessory; it holds that promise "
          + "until the ring closes.</p>"
        : "<p>No stage is tenderer than the finished vault: struck-early "
          + "tension never rises meaningfully past the final "
          + mpa(input.peakTension) + ".</p>");
    }
    if (input.formworkPeak) {
      parts.push(input.formworkGrowsToEnd
        ? "<p>The formwork's carry grows with the build to "
          + input.formworkPeak.kN.toFixed(1) + " kN: in this staging "
          + "model it holds everything placed until striking, and the "
          + "shell takes the load only when it is struck.</p>"
        : "<p>Formwork carry peaks at stage "
          + input.formworkPeak.stage + " ("
          + input.formworkPeak.kN.toFixed(1) + " kN)"
          + (input.selfSupportingFrom != null
            ? "; from stage " + input.selfSupportingFrom
              + " the carry stays under a tenth of that peak -- the vault "
              + "essentially carrying itself from there on."
            : " and is still working at the final stage.") + "</p>");
    }
  }

  parts.push("<h3>Recommendations</h3><ul>"
    + buildRecommendations(input).map((line) => "<li>" + line + "</li>").join("")
    + "</ul>");

  parts.push('<div class="data-note"><b>What this can and cannot tell '
    + "you.</b> The numbers come from thrust-network form finding plus a "
    + "linear-elastic solve of each build stage as if struck at that "
    + "moment. It does not check buckling, creep, shrinkage, seismic or "
    + "wind action, and the material limits are indicative code-style "
    + "values, not project design values. It is a design companion, not "
    + "an engineer's sign-off.</div>");
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
      layout: layout("Peak stress per built stage, MPa") });
  }
  if (input.stageSeries.some((row) => row.displacementMM != null)) {
    specs.push({ id: "graph-stage-deflection",
      data: [{ x: input.stageSeries.map((row) => row.stage),
        y: input.stageSeries.map((row) => row.displacementMM),
        type: "scatter", mode: "lines+markers", name: "peak deflection",
        line: { color: theme.accent } }],
      layout: layout("Peak deflection per built stage, mm",
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
      layout: layout(weighed
        ? "Formwork carry against placed weight, kN"
        : "Formwork load per stage, kN",
        { showlegend: weighed }) });
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
          type: "scatter", mode: "lines", name: "the limit",
          line: { color: "#cc2211", dash: "dot", width: 1 } },
      ],
      layout: layout("Utilisation against material limits, %") });
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
      layout: layout("Member force distribution, kN",
        { showlegend: false, bargap: 0.05 }) });
  }
  return specs;
}
