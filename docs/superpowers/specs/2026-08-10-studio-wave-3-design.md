# Studio Wave 3: Honest Visuals

Bench Studio renders the thrust network and its staged build faithfully in
the numbers but not yet in the picture. Param's first full browser pass
surfaced six visual defects and three missing controls. This wave makes the
picture as honest as the solve: the shell gets its real thickness, the
strike takes everything the strike should take, textures read per cast
piece, the heatmaps become continuous fields with a legend, and the load
arrows point the way gravity does.

All work is client-side in `bench/studio/static/` except the sprayed
concrete preset, which threads through the solver presets and staging
densities like the existing materials.

## Global constraints (unchanged from waves 1 and 2)

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- The server never imports compas, numpy, scipy, compas_fea2 or ananke_fea
  outside `solve_stage.py` (guard test).
- Metres everywhere server-side; the UI labels millimetres.
- kN to N exactly once, at the geometry reader.
- `applyTimeline` stays a pure function of t (purity pin).
- Python is canonical for anything mirrored in JS.

## Fix 1: the strike takes the wires and nodes

`applyTimeline` animates segments and falsework; the wires and nodes are
untouched, so they hang in the air after the falsework drops. During the
strike window (the same `u` the falsework uses) the wires and nodes fade
from full opacity to zero, translate downward by the same 1.5 m, and become
invisible at u = 1. Scrubbing back restores them exactly, because
visibility, opacity and position are all computed from t on every call.

Composition with the layer toggle: visible = `state.layers.wires` AND the
timeline says they still stand. The steel materials on wires and nodes are
created with `transparent: true` once at build so mid-strike opacity works.

## Fix 2: real thickness extrusion

The shell segments are zero-thickness surfaces; the thickness slider drives
the solve but not the geometry. `buildSegmentMeshes` extrudes each segment
to the bundle's actual thickness:

- Compute area-weighted vertex normals once on the whole render mesh, so
  adjacent segments agree along shared edges.
- Top skin: each render vertex offset by +n * t/2, original winding.
- Bottom skin: offset by -n * t/2, reversed winding.
- Walls: for every boundary edge of the segment's face set (an edge used by
  exactly one face inside the segment), one quad joining the top pair to
  the bottom pair. Walls make the joints between cast pieces visible.
- t = `state.bundle.provenance.thickness`, never the live slider value, so
  the picture always matches the solve on screen.

Each segment mesh carries corner metadata in `userData`, parallel to its
position attribute: the render vertex id, the surface ("top", "bottom",
"wall") and the render face index (walls record their adjacent face).
`recolourSegments` consumes that metadata instead of re-deriving the
six-corners-per-face layout, which no longer holds.

Deflection displacement moves both skins by the same vertex displacement
(base offset position plus d * exaggeration). The falsework stays a
surface: it is formwork, not the cast.

## Fix 3: per-segment box UV

UVs are a single planar XY projection over the whole pavilion, so steep
faces smear and all segments share one continuous texture. Replace with box
mapping per segment:

- Per face (skins and walls alike), the dominant axis of the face normal
  picks the projection plane; UV = the remaining two coordinates * 0.15.
- Coordinates are taken relative to the segment centroid, plus a
  deterministic offset derived from a hash of the segment key, so no two
  segments share texture alignment and each reads as its own cast piece.

## Fix 4: continuous heatmaps with a legend

Stress is one flat colour per analysis face. Replace with a per-vertex
field:

- For each analysis vertex and each surface (top, bottom), average the
  signed `stressValue` over the parent faces adjacent to that vertex
  (adjacency from `analysis_mesh.faces`).
- Interpolate those per-vertex values onto the render mesh through
  `vertex_sources`, the same rule `interpolate_vertex_field` uses for
  displacements.
- Colour each corner from the field of its own surface. Walls colour by
  the worst of both surfaces.

The stress surface picker gains a "Per surface" option and it becomes the
default: the top skin shows the top field, the bottom skin the bottom
field, which is the honest picture for a shell in bending. The existing
worst / top / bottom options keep their meaning and colour both skins by
that single choice.

A legend appears whenever the stress or deflection layer is on: a DOM
element (not canvas) showing the diverging ramp with numeric min, zero and
max labels, MPa for stress and mm for deflection, and naming the field it
shows. In the verification-peaks-only fallback (no staged run) the legend
says "peaks only" and the flat tint stays as it is today.

The smoothing lives in a small exported pure function so a node test can
check it against a hand-computed toy mesh, the same style as the binning.js
parity tests.

## Fix 5: falsework becomes a ghost with its own toggle

The "skin under the wires" is the falsework surface: dark grey, fully
opaque, 20 mm below the shell from t = 0. It becomes translucent (opacity
0.3) from the start, so the pre-build state reads as wires and nodes over a
faint formwork surface. The strike fades 0.3 to 0. A new "Falsework" layer
toggle joins LAYERS, always available, letting Param switch the ghost off
entirely.

## Fix 6: load arrows point along the load

The contract ships loads already pointing down (negative z). `arrowField`
takes a direction argument of -1 for loads and multiplies the shipped
vector by it twice over (line endpoint and head orientation), so loads
render upward. The direction parameter is removed; arrows draw from the
node along the shipped vector exactly, for loads and reactions both. What
the contract says is what the screen shows.

## Addition 1: sprayed concrete preset

New preset "Sprayed concrete C25/30", key `concrete-sprayed`, wet-mix
shotcrete with the same EN derivation as the existing presets:

- E = 31 GPa
- design compression = 0.8 * 25 / 1.5 = 13.333 MPa
- design tension = 0.8 * 1.8 / 1.5 = 0.96 MPa (fctk,0.05 = 1.8 MPa for
  C25/30)
- density 2300 kg/m3

Threads through `src/ananke_fea/materials.py` (constant + PRESETS),
`staging.DENSITIES`, the mirror test, and the materials reconstruction
test. UI: fourth option in the material dropdown; JS material is a warmer,
rougher grey than cast concrete (higher noise variation, roughness near
1.0) so sprayed reads differently from C30/37 at a glance.

## Addition 2: node and wire size sliders

Two sliders in the panel:

- Node radius: range 0.01 to 0.10 m, default 0.03 (smaller than today's
  0.045, per Param's request).
- Wire radius: range 0.005 to 0.06 m, default 0.02 (today's value).

Changing either disposes and rebuilds the wires and nodes instanced meshes
at the new radii, then reapplies the wire-forces layer and the current
timeline state, so force thickening and mid-strike fade keep working on top
of whatever base size is set.

## Addition 3: Stop and Restart

Two new buttons beside Play in the Placement section:

- Stop: pause, reset to t = 0, scrubber to 0, Play button label back to
  "Play".
- Restart: jump to t = 0 and play immediately.

Play/Pause keeps its current toggle behaviour.

## Testing

- Static source pins (existing pattern in `tests/studio/test_static.py`):
  strike handling touches wires opacity; `arrowField` has no direction
  parameter; legend element exists; "Per surface" option exists and is the
  default; `concrete-sprayed` appears in index.html and studio.js; the four
  new control ids exist (node radius, wire radius, stop, restart);
  `transparent: true` on the steel materials.
- Node tests: stress smoothing checked against a hand-computed toy mesh;
  extrusion corner metadata checked for a two-quad segment (vertex counts,
  boundary edge count, top/bottom/wall labelling).
- Python: sprayed preset reconstruction in `tests/fea/test_materials.py`;
  `DENSITIES` mirror extended in `tests/fea/test_studio_mirror.py`; no
  other server-side behaviour changes.
- The `applyTimeline` purity pin and the existing 75 studio tests must stay
  green.

## Out of scope, queued as wave 4

Param picked the next tools wave: CRA feasibility (per-study badge plus
per-stage rigid-block verdicts via `.venv-cra`), mould clustering, concrete
vs timber A/B, and robot choreography. Each gets its own spec. Adaptable
prestress stays on the Grasshopper side, as ruled in wave 2.
