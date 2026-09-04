# The load, the sequence, and the crash: a briefing

Written 2026-09-04 for Param to read on his return. Everything below was measured or read in
source, then checked by an adversary instructed to refute it; where the adversary won, the
corrected version stands here. Nothing described in sections 8 to 10 has been built. The two
governing documents are docs/superpowers/specs/2026-09-04-selfweight-vertical-design.md (held)
and docs/superpowers/specs/2026-09-04-horizontal-equilibrium-station-design.md (awaiting your
answers), and both wait on this read.

1. What happened this morning. Your six-lobe forms crashed the vertical solve with "array must
not contain infs or NaNs" after about ninety seconds, in two different configurations, while a
three-lobe form solved. The crash arrived with two warnings: an invalid multiply in compas_tna's
self-weight line, and an overflow in a length computation.

2. The mechanism, reproduced rather than argued. Wiring a surface load makes our adapter do two
things at once: the load becomes a function of the geometry being solved (tributary area times
your vector), and every fixed nodal load is silently deleted, so nothing constant remains. The
library's target-height routine then multiplies its scale by a height ratio every iteration
while the load chases the heights. With a constant load that search lands in one step, which is
why it has worked all year. With the live load it orbits, the orbit tips into growth, the
coordinates overflow, and infinity times a zero mints the NaN. The loop monitors its progress
with a max that skips NaN, so it burns all hundred iterations blind; the error is finally raised
by a finiteness check two calls later. Both your runs dying at the same duration is that loop
running its full count.

3. Your own code knew. The worker's comment describes this exact runaway in its own words, and
freezes the self-weight against it, but only in natural-height mode. Give it a target Height and
it hands the live feedback to the library unguarded. Yesterday's "Natural selfweight frozen 0"
was the guard reporting itself off, not a safety measure engaged.

4. What was cleared. The hole rims, Floating Anchors, and your anchoring choices are innocent of
the crash: verified benign for finiteness. The load's magnitude is irrelevant: the iteration is
exactly invariant to scaling it, proved by a sweep. Degenerate faces give wrong areas, never
NaN. Your three-versus-six observation is the conditioning of the pattern deciding which side of
a stability boundary the iteration starts on, and the fan corners are the conditioning.

5. Why RhinoVAULT loads first, which was your question. Because in TNA the load is half the
definition of the shape. The vertical solve is a linear system whose right-hand side is the
load; solved with a different load it is a different vault. Their code names it self-weight in
as many words: the load updater is documented as handling "geometry and selfweight", computed as
tributary area times thickness times density, with thickness a per-vertex attribute. Your
suspicion was exactly right.

6. How RhinoVAULT survives the same physics, and this is the corrected finding after the
adversary's test. Their shipped tool has no target-height search at all: the scale is a design
dial the user drags, and each drag runs a fixed-scale relaxation for ten iterations. The
adversary then ran their own shipped loop at deep-vault scales and it diverged exactly as ours
does, reaching ten to the twenty-sixth at one setting. So nobody has solved live self-weight in
deep regimes; RhinoVAULT is protected by a human hand and a truncation, not by numerics. Their
2012 paper says the honest version themselves: the load is adapted "after a certain number of
steps during the solving process", never inside every step.

7. The physics will not let us simply freeze. A load evaluated on the flat plan under-weighs the
vault by measure: about six per cent at a rise-to-span of 0.3, fourteen and a half at 0.5. Fine
for sketching, wrong for the thesis.

8. The recommendation, held for your word. Frozen, then refined. Hold the weight still while
finding the height; reweigh the vault you actually got; find the height again; stop when the
total weight stops moving, with a fenced fallback and a named error instead of a ninety-second
silence. Measured: this converges in about ten rounds on the exact configuration where the live
loop overflows, and in two or three at architectural rises. It is stable by construction, it
converges to the true built-surface weight, and it is what the BRG paper describes. The full
rules are in the held spec.

9. The configuration you asked for mid-walk, also held. "The rhino vault sequence and config"
reads, in their code: self-weight as its own quantity from Thickness and Density inputs rather
than a vector's Z; nodal point loads kept BESIDE the self-weight, additive, never zeroed, which
retires our adapter's silent deletion; per-vertex thickness as the recorded future step; and the
two-step sequence, horizontal equilibrium first and load-bearing vertical second, written down
as the reference architecture. This is rule 2.4 of the held spec.

10. Where the station fits. The horizontal equilibrium station is the missing half of step one
of that sequence for hand-drawn patterns: it conditions the pattern the vertical solve then
stands on, and the fan corners it fixes are the same conditioning that decided your
three-versus-six outcome. Its spec carries four questions for you, each with a default.

11. What this briefing asks of you, in one place. First, lift or amend the hold on the
self-weight spec: the choice is frozen-then-refined as recommended, or something you would
rather have. Second, confirm rule 2.4's loads model: Thickness and Density inputs, additive
nodal loads, no silent zeroing. Third, answer the station's four questions when you are ready;
nothing else waits on them. Fourth, nothing in this briefing touches the skin or the export:
those continued on their own track while this was researched.

12. The sources, so you can check any of it. The diagnosis and research transcripts are in the
session's workflow outputs; the code citations are in the two specs; the paper is your own copy
at Kinetic AI\PHD robotics\papers\additional papers\Block Research Group\
2012_Rippmann_RhinoVAULT_Interactive_Vault_Design.pdf, pages 221 and 225 for the two passages
quoted. The measured divergence traces and the convergence of the refinement loop are in the
research workflow's journal, reproducible against the library in the project's own environment.
