# Dual quality: the Armadillo Dual cuts voussoirs, not slats

Date: 2026-08-20. Param's live run on his own TNA Armadillo pavilion
at S = 0.2 produced ribbon/slat cells, contour bands, a funnel knot,
staircase edges, and output the studio would refuse to import. The
measured diagnosis (.superpowers/sdd/2026-08-20-dual-quality-diagnosis/
findings.md, binding companion to this spec) ranked seven mechanisms
with numbers on HIS vault; this wave fixes them. Branch
feature/dual-quality off plugin main ea1e851 (independent of
feature/import-pieces; armadillo_dual.py is untouched there).

## The seven fixes (designs binding, from the diagnosis)

M1+M2 (dominant): REPLACE band-only seeding with evenly spaced
streamlines (Jobard-Lefebvre 1997) mapped to S. A queue of accepted
lines; when a line is accepted, candidate seeds are offered at
distance S to the LEFT and RIGHT of every one of its points -- a true
geometric offset in the local cross-flow direction, landing in
whatever face it lands in, NEVER snapped to a mesh vertex (that snap
is the M1a defect that pinned his line count at 34 for every S). A
candidate is accepted only if farther than S from every accepted
line; an accepted line advects BOTH ways along the field; a line
terminates when it comes within 0.5*S of an accepted line, measured
point-to-SEGMENT against a spatial index (reuse/adapt the module's
existing bucket-grid style; stdlib only). The queue is seeded from
the support band (springing still governs where the cut starts; band
candidates also unsnapped). ONE threshold pair -- accept S, terminate
0.5*S -- replaces the 0.6*S/no-reseed asymmetry (the 2.4x funnel/mid
size ratio). Seeds along each line and courses stay as today
(S-spaced, staggered, band index = course).

M6: dual-graph refinement target becomes 0.15*S with the cap at 5
levels (constants; the diagnosis measured coverage 93.0 -> 98.7% and
disconnected 15 -> 2 on his vault). Re-time and disclose: the dual
already owns most of the wall time.

M4: an OPEN extracted chain whose two ends both lie on (within the
weld tolerance of) the mesh boundary closes by WALKING the mesh
boundary polyline between the ends (build each loop's polyline once
per run; splice its points), not by a straight chord. Interior chain
breaks (both-ends-not-on-boundary, ~2.4%) keep the chord. This turns
the 19-21% chamfered boundary cells into cells that reach the rim
and the oculi.

M3: after extraction (and M4 closure), every chain is RESAMPLED at
~0.5*S spacing (endpoints kept; both neighbours resample the SAME
midpoint chain so shared joints stay shared bit-for-bit -- resample
the chain ONCE and hand both cells the same points, mirroring how
bonded_courses shares arcs). The Laplacian smoothing pass count does
NOT increase (measured: a bad trade). No extra refinement for shape
(measured: none).

M5: generate() itself DROPS plan-degenerate cells AND
plan-overlapping cells (the pairwise plan overlap check ported from
the acceptance script's method) before returning, counted in
diagnostics as plan_degenerate_dropped and plan_overlap_dropped with
the keys; D's guidance line updates. The raw output of a run must be
importable by the studio -- 0.6% of cells may not cost 100% of the
import.

M7: _smooth_pass weights each neighbour's doubled vector by that
neighbour's own RAW coherence (|weighted sum| / sum of |weights| on
the unsmoothed field) instead of unit-normalising, so the ~8% of
numerically arbitrary faces stop voting at full strength. One
mechanism, no new knobs.

## Test data: Param's own vault, with recovered forces

A tests-local adapter (tests/patterns/, following the 6c BRG adapter
pattern) loads his compas export ("bench/demo/upload from
grasshopper/Aramdillo style-compas.json" in the UI repo, skip-guarded
when absent) and recovers per-edge q from his reciprocal force
diagram exactly as the diagnosis did (form face <-> force node by
angle signature with the force diagram rotated 90 degrees; q =
|force edge| / |plan form edge|; member_forces = q*L; supports = the
z=0 vertices). The diagnosis validated this recovery at machine
precision (signature distance 0.003 deg, equilibrium residual median
9.4e-07); the adapter asserts those two properties as its own sanity
check. The diagnosis probe scripts in the session scratchpad
(dualdiag/) are reference material, not dependencies.

## Acceptance bars (his vault, S = 0.2, forces path; the diagnosis's
baseline numbers in parentheses)

- streamline_count scales with S: >= 70 at S = 0.2 (was 34, fixed).
- cell_count >= 2000 (was 1055 against ~3135 implied).
- mean_cell_size / S in [0.8, 1.3] (was 1.55).
- Ribbons: elongation > 3 in <= 2% of cells and <= 6% of covered
  area (was 11.8% / 28.1%).
- Starvation: <= 5% of mesh area farther than 2*S from a streamline
  (was 26.8%).
- Coverage >= 97% (was 93.0%); disconnected <= 3 (was 15).
- Funnel/mid median cell size ratio <= 1.5 (was 2.4).
- Boundary chamfers: cells with an outline segment > 3x their own
  median AND both ends on the boundary <= 3% (was 19.4% incl.
  chamfers).
- IMPORTABILITY: the S = 0.2 output, written as a bench.tessellation/1
  sidecar, is ACCEPTED by the studio's real from_document (the 6c
  cross-repo acceptance pattern) -- zero rejections.
- Wall time at S = 0.2 on his mesh <= 90 s, measured and disclosed
  in the report (re-timed after M6; the seed count roughly triples
  and the dual graph grows a level).
- No regression at S = 0.4 on his vault: mean/S stays in [0.8, 1.3],
  ribbons <= 4% of cells.
- The BRG primal (6c's reference): the geometric FLOORS hold or
  improve (coverage >= 75%, outline/territory median >= 0.6); the
  count and mean-size pins are RE-MEASURED and re-pinned with the
  changes disclosed in the spec-retrospective style (evenly spaced
  seeding legitimately changes both); the dome meridian tests update
  where the two-sided seeding legitimately changes semantics
  (disclosed per test).
- DEFAULT_SIZE stays 0.6 this wave (re-evaluate after; Param drives
  S explicitly anyway). Worker command and GH component signatures
  unchanged; D gains the two new dropped counts.

## Out of scope

bench.tessellation/2 (3D outlines); Fast-Marching true-geodesic
bisectors (M3's honest version -- recorded as the next step if
resampling is not enough); anisotropy controls; the import-pieces
branch (separate, unmerged, untouched).

## Constraints

numpy + stdlib ONLY in the module (live Rhino env: numpy 2.0.2, no
scipy); suite `.venv\Scripts\python.exe -m pytest tests -q` from the
plugin repo root; dotnet build 0 warnings (component untouched but
the build bar holds); no em dashes (U+2014); no AI attribution;
explicit-path commits; NEVER push; TDD red-first per mechanism.
