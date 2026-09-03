# RhinoVAULT September 2026 update: what we take from it

A register of future development, written 2026-09-02 from Param's review of the RhinoVAULT update.
His words are quoted where they are rulings. Nothing here is scheduled; the standing sequence is
columns residual, then skin as it is, then these.

## 1. Horizontal thrust equilibrium in the form-finding chain

> "we should include horizontal thrust equilibrium as a major component in the form finding chain.
> it goes after the tna relax and before the z solve. unless the solve actually already discovers
> that equilibrium its not a problem."

FIRST STEP IS A CHECK, NOT A BUILD: establish whether our solve already discovers horizontal
equilibrium implicitly. In TNA terms the horizontal equilibrium IS the reciprocal force diagram; if
the worker's relax step closes the force diagram before heights are computed, the station exists
already and this item is documentation. If it does not, the station goes after the relax and before
the z solve, as he places it.

## 2. Optimum sag per form

RhinoVAULT reports the optimum sag for each form input. Nice to have; ties into Pre-Sag and the
counterweight-tension calibration.

## 3. The TNO analysis menu, for the studio web UI

The update exposes, over variables q (force densities), zb (support heights) and t (thickness),
with funicular + envelope constraints, SLSQP from a loadpath start, qmax ~ 0 so compression only:

- MinimumThrust / MaximumThrust: the bracket of horizontal reactions the vault can stand with.
  This bracket is the safe range the counterweight-tension calibration must live inside.
- MinimumThickness: thinnest envelope still containing a thrust network.
- Bestfit: network closest to a target surface.
- MaximumLoad: largest point load the envelope carries (vertex set selectable: All, Boundary,
  Degree, Manual).
- SupportDisplacement (Ecomp-linear, simplified): prescribed support movement (outward, inward,
  downward, manual), the network the structure actually settles into. This is the spreading-supports
  question of the PhD, directly.

> "This is real useable information, especially the minimum thickness when matched with a changing
> q load etc. super important data to utilise from."

So the flagship coupling to build eventually: MINIMUM THICKNESS AS A FUNCTION OF q, swept, as
calibration data for the live-weight rethickening feature.

## 4. DEM blocks and the pattern taxonomy

`_RV_dem_blocks` cuts blocks from the DUAL of a mesh pattern. Pattern families shipped: Brick,
DissectedHexQuad, DissectedHexTri, DissectedSquare, DissectedTriangle, Dodeca, Floret, Hex,
HexBigTri, HexTri, Octo, Pythagorean, Rhombus, Square, SquareTri, Tri, Weave, ZigZag.

What we take: the list is a ready taxonomy for future Skin variants; the dual-based generation
validates the armadillo approach; "DEM" says discrete-element assessment is coming their side, which
touches the parked CRA rescue item. A/B idea for later: run their DEM blocks and our Skin on the
same form and compare buildability.

## 5. Load vector display: match theirs

> "they calculate the load vectors differently or visualise it differently ... Ours is just uniform,
> we should understand what they are doing to get vectors like that and match it."

ANSWERED FROM THEIR CODE, read 2026-09-02 in the brg-csd site-env: their per-vertex load is
tributary, `pz = vertex_area * thickness * rho` (parametricenvelope.py, apply_selfweight), and the
displayed arrow scales with that magnitude, which is why crown vertices with large tributary quads
carry long arrows and edge vertices short ones. It is APPLIED load, not capacity. Our Result already
carries per-vertex Load Vectors with magnitudes; the work item is display-side: stop drawing them
uniform, scale by magnitude. Check whether our Display normalises them before drawing; if the worker
lumps loads uniformly rather than by tributary area, that is a second, worker-side item.

## 6. Style and Display consolidation, RULED

> "it would be nice to have a really simple force diagram scaler on the display component, which I
> see has 2 identical inputs on the style input and the display component, both weight and vector.
> These can stay on display, style gets removed and the value drop down moves to the display
> component under the style input still."

So: the STYLE COMPONENT IS REMOVED; its preset dropdown moves onto the Display component in the STY
slot's position; Weight and Vector stay on Display; and Display gains a simple FORCE DIAGRAM SCALER.
Queued behind the columns residual and the skin phase.

## 6a. The Armadillo Vault fabrication findings, from the published papers, 2026-09-02

Param supplied the tessellation figures and the fabrication text. Two rulings went straight into
the running phase (Task 26's brief): courses read as continuous contour families of the force flow,
and the size parameter dilates the CONTOUR SPACING rather than re-seeding the pattern.

The fabrication extract, registered for the voussoir-solids work to come (it is the professional
answer to what the new Thickness input approximates):

- INTRADOS: curved, continuous, matching the vault's soffit. Cut with parallel circular-blade
  passes leaving fins hammered off.
- LOAD-TRANSFERRING FACES (aligned with the course lines): RULED surfaces, cut by a cylindrical
  profiling tool that also forms the male and female NOTCHES. So the bed joints are ruled by
  construction, which is a constraint our course bands already respect by being traced curves.
- EXTRADOS: PLANARISED PER VOUSSOIR, deliberately DISCONNECTED, because anticlastic regions admit
  no connected convex flat-panel discretisation. Process: plane at the centroid normal first;
  then the plane rotates about the centroid normal and slides, corner normals allowed to rotate
  up to 5 DEGREES off the thrust-surface normal, intrados tessellation held fixed; finally the
  non-load faces planarised and notch lines added. Result: stepping of 2 to 5 cm everywhere, the
  lower bound kept for appearance; a scale-like exterior against a smooth interior.
- RELATION TO OUR THICKNESS INPUT: Param's Z-offset mode keeps BOTH skins connected (watertight,
  approximate normal thickness); the Armadillo answer keeps the INTRADOS connected and lets the
  extrados step. A per-voussoir planarised-extrados mode is therefore the natural third mode of
  the thickness feature when voussoir solids become fabrication-grade, with the 5-degree corner
  cap and the minimum-step bound as its two named tolerances.

## 7. Library of forms

> "this will be much later ... that is when everything is finished we work on that"

## 8. The envelope crash, diagnosed

Every TNO objective died identically in envelope setup, before any optimiser ran:
`crossvault_bounds` at crossvault.py:187 takes sqrt of a negative when a form vertex lies outside
the envelope's assumed plan. `CrossVaultEnvelope` DEFAULTS to x_span = y_span = (0, 10). Fix order:
match the envelope spans to the form's real footprint (or move the form); pick the right parametric
envelope for non-crossvault forms; only then, if boundary vertices still fail by rounding, clamp the
sqrt argument at zero locally. Worth reporting to BRG. Param sorts this himself later.
