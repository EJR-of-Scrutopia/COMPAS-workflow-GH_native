# Studio Wave 5: Precast Pieces, Inflation and Honest Materials

The studio draws the vault as one continuous surface. Adjacent segments are
extruded from shared vertices, so they meet flush with no joint and the
shell reads as a single monolithic object rather than an assembly of cast
pieces. The three concrete presets sit within a few percent of each other
in colour and wash out to white under the environment and tone mapping, so
they are mutually indistinguishable. Sprayed concrete animates as though it
were precast. And the animation begins with the vault already found, so the
form-finding that is the point of the research is never shown.

This wave fixes all four. It is presentation work, and it is deliberately
separate from the CRA rescue, which gets its own spec.

## The piece: curved caps, planar joints

The load-bearing change. Today a drawn segment is the cell's mesh faces
offset by half the thickness each way, so its boundary follows the curved
mesh and its neighbour's boundary follows the same curve from the other
side. They interpenetrate exactly and no joint is visible.

A drawn piece becomes:

- Caps from the cell's own render-mesh faces, offset plus and minus half
  the thickness along area-weighted vertex normals, so the vault keeps its
  true curvature and the heatmaps keep their resolution.
- Boundary vertices projected onto a best-fit plane per joint run. The runs
  and their chains already exist in `voussoirs.py`, derived from the
  segmentation. Both cells sharing a run fit the plane to the same chain,
  so both project onto the same plane and the joint is a genuinely flat cut
  on both sides.
- Side faces spanning the projected chain through the thickness. Because
  the whole chain now lies in one plane, the side face is planar even
  though it is subdivided, and it still meets the curved cap watertight.
- A visible joint: each finished piece is scaled toward its own centroid by
  a gap of 20 mm by default, adjustable from 0 to 60 mm. Neighbours then
  stand apart by twice the inset and the assembly reads as castings.

This replaces the client-side extrusion. The piece geometry is computed in
Python and shipped in the bundle, which removes a mirrored implementation
rather than adding one: `fields.js` keeps only the UV helpers, and its
extrusion, vertex-normal and boundary-edge functions retire along with
their node parity tests, because Python becomes the only implementation.

Each piece carries, per vertex, the render-mesh vertex it came from, so the
stress and deflection fields and the displacement exaggeration keep working
exactly as they do now.

## Taper and per-piece variation

A taper slider thins pieces toward the crown: thickness at ring r is the
base thickness times `1 - taper * r / (rings - 1)`, taper adjustable from 0
to 0.5, default 0. This is structurally sensible, since the crown carries
least, and it makes the pieces visibly different sizes.

**Taper is a drawing parameter this wave.** Making it structural means
per-block thickness through the FEA, which is a separate piece of work. The
HUD states that the analysis used a uniform thickness whenever taper is not
zero, in the same style as the existing verified-thickness flag.

Per-piece variation comes from a deterministic hash of the segment key: a
lightness tint of plus or minus three percent and a UV rotation. Two
castings never look identical, and the same study always looks the same.

## Sprayed concrete builds, it does not land

Sprayed concrete is monolithic, so when the material is `concrete-sprayed`:

- The joint gap is forced to zero and the per-piece tint is suppressed. It
  is one continuous surface, correctly.
- The placement animation is replaced. Instead of pieces dropping from
  height, each piece grows in place from zero to full thickness, in a
  rim-to-crown sweep whose per-piece windows overlap by half their
  duration, so the shell reads as continuous build-up over the formwork
  rather than discrete arrivals.

Every other material keeps the existing drop.

## Net inflation

The timeline gains a phase before the build. The contract's `formGraph`
carries the flat form diagram: its xy matches the thrust surface exactly
and its z is zero throughout, verified on the Trial 2 export. So the
inflation is a straight interpolation of z from the flat plan to the
equilibrium surface, which is the project's own form-finding data rather
than an invented effect.

Wires and nodes start flat, rise into form over an adjustable inflation
time (default 3 seconds, range 0 to 10, zero skips the phase), and the
falsework fades in once the form is found. The build then proceeds as now.
`applyTimeline` stays a pure function of t, so recording and scrubbing
still work.

## Materials that read apart

Retune the four presets so they are distinguishable at a glance, and pull
back the environment intensity so light surfaces stop clipping to white:

- Concrete C30/37: warm mid grey, moderately rough.
- Concrete C50/60: cooler and distinctly darker, smoother, denser.
- Sprayed concrete: lighter, roughest, with a visibly coarser speckle.
- Timber GL24h: warm brown, so it stops reading as bare white with grain.

Only the appearance changes. The EN-sourced strengths, densities and
friction values are untouched, and the Data panel keeps quoting them.

## What does not change

- The FEA path, the staged solves and every verdict.
- The CRA machinery, its guards and its honest nulls.
- Every existing layer, the legend, the transport controls and record mode.

## Testing

- Python unit tests for the piece builder: planar joint faces (all a run's
  projected vertices lie in one plane to 1e-9), watertight closed
  orientable pieces, neighbours' joint planes identical, the gap producing
  a real separation, taper reducing thickness by ring, and per-vertex
  source ids preserved for field lookup.
- A test that sprayed concrete forces the gap to zero.
- Source pins for the new controls and for the sprayed and inflation
  timeline branches, in the existing `test_static.py` style.
- The `applyTimeline` purity pin must keep passing.
- Existing studio and fea suites stay green; the retired `fields.js`
  extrusion tests are removed with the code they pin, not weakened.

## Out of scope

- The CRA rescue: convergence above fourteen blocks and whether contact
  detection can afford these more accurate pieces. Its own spec, and it
  reuses this wave's geometry rather than duplicating it.
- Making taper structural.
- Mould clustering, the concrete versus timber A/B comparison, and robot
  choreography. Param ruled robot choreography not needed now.
