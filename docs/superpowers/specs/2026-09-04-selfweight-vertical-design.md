# Self-weight under a target height: frozen, then refined

HOLD LIFTED BY PARAM 2026-09-04, after the briefing and the sequence discussion: "I like those
improvements you found i think we need to add all these improvement and the rhinovault sequence
in too as it should be." Everything below is APPROVED TO BUILD, rule 2.4's RhinoVAULT loads
model included. The build order: after the skin seams wave leaves the tree, this spec is the
solver wave; the TNA Horizontal component (its own spec, now ruled) follows as its own wave.

Written 2026-09-04, from the NaN diagnosis and the RhinoVAULT self-weight research, both
adversarially verified with measured reproductions. His question, "why does the rhinovault do load in its
calculation first? I suspect its to provide a self weight", is answered YES in their code's own
words (LoadUpdater: "updating loads when geometry and selfweight change"; sw = tributary_area x
thickness x density, thickness per vertex) and in the method paper on his own disk
(2012_Rippmann_RhinoVAULT_Interactive_Vault_Design.pdf, p.221 and p.225, under
Kinetic AI\PHD robotics\papers\additional papers\Block Research Group).

## 1. The measured facts this stands on

1. Our zmax branch hands compas_tna a LIVE density and lets vertical_from_zmax multiply its scale
   by a height ratio each iteration while the load chases the geometry. Reproduced against the
   real library: chaotic, overflow, NaN. The NaN is minted at loadupdater.py:81 by inf x 0.0.
2. The instability is INTRINSIC to live tributary self-weight in deep regimes, not to the ratio
   amplifier: the verifier ran RhinoVAULT's own shipped update_z at fixed deep scales and it
   diverged identically (scale 0.05 gave z = 1.9e26 on the same mesh). RV survives in practice
   because a human drags the scale interactively at kmax 10, never asking for depth and weight in
   one loop.
3. Pure plan-freezing under-weighs the vault by 0.7 per cent at rise/span 0.10, 6.0 at 0.30,
   14.5 at 0.50. Sound default, poor answer alone.
4. An OUTER refinement loop (solve at held load, re-evaluate on the solved surface, repeat)
   converged on the exact configuration where the live loop overflows: round 10 pathological,
   2 to 3 at architectural rises.
5. A negative density fed to vertical_from_zmax returns a NEGATIVE scale (measured -27.73 against
   +27.73). Under this design the library never sees a density again, so the hazard is retired on
   this path rather than patched.
6. solvers.py:670 silently ZEROES every nodal load when a surface load is wired. RETIRED by rule
   2.4(b): nodal loads ride beside the self-weight, additive, and the diagnostics say both totals.

## 2. The design

RULE 2.1. THE LIBRARY ALWAYS GETS A CONSTANT LOAD. In the zmax branch of
src/tree_forest_compas/tna.py (the 2538 gate and the 2544-2561 call), density 0.0 is always
passed to vertical_from_zmax. _persist_selfweight_loads (2504-2527) runs for zmax as it already
does for natural height: the tributary self-weight is evaluated by US, written into pz, held
constant through the solve. The comment at 2529-2537 already states this ruling; the gate that
confined it to natural mode is the defect.

RULE 2.2. THE REFINEMENT LOOP. Around the vertical call: evaluate the self-weight on the CURRENT
geometry, solve to zmax at that held load, re-evaluate on the SOLVED geometry, repeat. Stop when
the TOTAL load's relative change is under 1e-3, or at a cap of 10 rounds. Architectural rises
settle in 2 or 3; the cap is the pathology fence, not the expectation.

RULE 2.3. THE FENCE, WITH WORDS. If the cap is reached unconverged, fall back to the LAST
CONVERGED round's result (round 1, the plan-frozen solve, always exists) and raise a Warning that
names the drift: "the self-weight refinement did not settle in 10 rounds; the total load was
still moving N per cent; the result carries the round-K weight." Additionally, EVERY round
asserts finiteness of xyz, pz and the scale immediately after the library returns, and a
non-finite value raises a NAMED error carrying the first offending vertex key and the round
number, never scipy's bare ValueError after ninety blind seconds.

RULE 2.4. THE RHINOVAULT-SHAPED CONFIGURATION, ruled by Param mid-walk 2026-09-04: "ok we should
be doing the rhino vault sequence and config." Their model, adopted:
  a. SELF-WEIGHT IS A THING OF ITS OWN, computed as tributary area x THICKNESS x DENSITY. The
     Loads component's surface mode becomes SELF-WEIGHT and gains Thickness (T, default 1.0) and
     Density (D, default 1.0) in place of reading a bare vector's Z as a density. Per-vertex
     thickness (RV's "t" attribute and distribute_thickness) is the recorded future extension;
     one scalar now.
  b. NODAL POINT LOADS ARE NEVER ZEROED AGAIN. solvers.py:670's pz = 0.0 is retired: nodal loads
     ride BESIDE the self-weight, additive, exactly RV's pz + pzext split. A canvas with both
     wired gets both, and the diagnostics report the two totals separately.
  c. THE SEQUENCE IS THEIRS: horizontal equilibrium first (load-free by construction, since
     vertical loads vanish in plan), then the vertical solve where the load enters as the
     right-hand side. Our pipeline already has this order; this spec writes it down as the
     reference architecture, and the TNA Horizontal component (its own spec,
     now ruled) is step one's missing half for hand-drawn patterns.

RULE 2.5. DIAGNOSTICS. The worker ships per-solve: rounds run, total load per round, final
relative drift, converged or fenced. The chin carries one line: "self-weight settled in K rounds
(drift x.x per cent)". Yesterday's misreadable "Natural selfweight frozen 0" line is reworded to
say what mode the weight was evaluated in.

## 3. What must be checked, each proved able to fail

1. The zmax branch never passes a non-zero density to the library (grep-proof plus a harness
   assertion through the worker protocol test seam).
2. On a fixture where the live configuration diverged (the meshgrid of the reproduction), the
   refinement CONVERGES and the total load's round-to-round drift is monotone decreasing after
   round 2; red by re-enabling the live density.
3. The fence: force non-convergence (cap 1), assert the fallback result equals round 1 and the
   Warning names the drift.
4. Finiteness guard: inject a NaN through the test seam, assert the named error carries a vertex
   key and round number.
5. Rule 2.4(b): a canvas with BOTH self-weight and nodal loads wired gets both, additive; the
   diagnostics carry the two totals separately; proved red by restoring the pz = 0.0 zeroing.
6. Python-side: tests/test_tna_stages.py gains the refinement loop's unit coverage (rounds,
   tolerance, fence) against a hand-built fixture; the existing stage tests keep passing
   unchanged, since a zero-density solve with persisted loads is exactly what natural mode
   already exercised.

## 4. Out of scope, said so nobody reinvents it

The horizontal equilibrium station (its own spec, now RULED: TNA Horizontal, its own wave after this one). Any change to
RhinoVAULT sign conventions beyond retiring the density path. compas_tna itself is never edited:
everything lives in our worker layer. The envelope-normalised total-weight rescale
(meshenvelope.py's trick) is noted as a future refinement of rule 2.2's evaluation, not built.
