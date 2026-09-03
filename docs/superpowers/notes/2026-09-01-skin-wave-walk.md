# Skin buildability wave: the walk

This note is written for Param to read before he opens Rhino. It carries the four open questions
that are genuinely his, the numbers this wave measured rather than asserted, and the two mechanical
things that catch everyone who reopens a saved definition after a wave like this one.

1. Three outputs or two. The design left this to him and it is still open. The choice is between
   Result, Cells and Surface, with the skin diagnostics written into the Result alongside every
   other component's numbers so Diagnose can read them with the rest; or Cells and Surface alone,
   with the numbers living only on the component's own message chin and its Remark, which is closer
   to his own words asking for the info bubble to be left as enough. Declining the third output
   loses him nothing he can read, only the ability to wire the numbers into a panel. Nothing in this
   wave depends on which way this goes, so it stays open until he says.

2. The setout distortion's first cause is deferred, not closed. His ruling asked for both causes to
   be addressed: the arc-length ratio mapping, and separately the seam quantised to a trace vertex.
   This wave answers the second, by projecting a propagated seam exactly onto the row below rather
   than snapping it to the nearest vertex. It defers the first, because replacing the ratio mapping
   properly means marching every joint along the level field's own gradient, which is a second
   advection engine stacked on the one this wave already carries, and it adds corners to every
   courses cell, which is exactly what pushes cells onto the Surface output's fan route and makes
   the plan filter dearer. Task 32 measured what the deferral costs rather than leaving it a guess:
   on the fine dome the proportional image and the gradient-marched image differ by up to 0.1057 m
   in plan, and on the serpentine by up to 0.1278 m. Both are under a third of a course height at
   the shipped 0.35 m CH, which is the size of the residual he is being asked to accept for now. If
   he wants this cause closed in the same round as everything else, something else in this wave, the
   force-aligned pattern or the band-splitting work, has to come out to pay for it, and that is his
   call to make.

3. A bounded residual hole at a topology transition, or an exact solve. His ruling asked for the
   full band-splitting answer to replace the present refusal outright, and this wave keeps the
   refusal as the base case at a search depth of six rather than replacing it. That leaves a hole of
   up to CH / 64 along a transition, which is 5.5 mm at the shipped 0.35 m course height and 7.8 mm
   at 0.5 m. The alternative is an explicit critical-point solve, which would be exact but needs a
   saddle classifier the engine does not have, and this wave could not carry that alongside
   everything else in it. A bounded 5.5 mm hole now, or a later wave for the exact answer: his call.

4. The cap that cannot be split. This is the honest residue of his own crown-cap ruling rather than
   a reopening of it. Splitting an oversized cap into a rosette needs an inner level curve smaller
   than the maximum girth, and on a dome whose plan is not a circle there may be none: where the cut
   locus is a segment rather than a point, the level curves near the top shrink onto that segment
   and the girth at the top cut never falls below roughly twice the segment's own length, however
   fine the course height is made. The engine emits such a cap whole and oversized, with a Warning
   naming its girth against the maximum, on the reasoning that a stone he can see and measure beats
   a hole he cannot fill. Measured on the elliptical dome fixture this wave built for exactly this
   case, the emitted cap's girth comes out at 3.855 m against a maximum of 1.8 m, more than double.
   The alternative is to refuse the cap outright, leaving the crown uncovered, which is at least
   consistent with what the band-splitting base case already does at a transition (item 3 above).
   His call.

5. The numbers this wave printed, gathered here in one place because they sit scattered across the
   harness output otherwise.

   The honeycomb, before and after the row-normalised lattice landed: on the two-oculus fixture, 74
   cells withheld out of 153 built, unchanged before and after, because that fixture's withholding is
   driven by its oculi rather than by lattice placement; on the serpentine, 99 withheld out of 199
   built before the change (the serpentine was not re-measured after, since the fixture the AFTER
   check re-runs is the two-oculus one against Task 13's own BEFORE).

   The bed-spacing ratio: on a rimmed hemisphere, world Z course spacing stretches towards the crown
   in a ratio of 47.62 to one between the widest and narrowest interior band, against the rim
   distance field's own courses, which hold every interior course to 0.35 m along the surface to
   within 5 per cent regardless of where on the dome it falls.

   The force-aligned pattern's uniformity ratio: piece sizes ranging from 0.600 m to 1.200 m, a
   ratio of 2.00 to one, on the fixture check 12.3(d) measures against.

   The band-splitting cost: on the two-hump barrel, 12 extra levels in 7 TraceAll passes, 2 ms; on
   the split-and-death fixture, 12 extra levels in 7 passes, 3 ms. Both sit far inside rule 8.2.3b's
   cap of 128 extra levels for a whole solve.

   The deferred cause, cause 1 of item 2 above: 0.1057 m on the fine dome and 0.1278 m on the
   serpentine, as already given in item 2.

   The oversized cap's girth, item 4 above: 3.855 m against a maximum of 1.8 m on the elliptical
   dome fixture.

   Task 32 also re-measured, rather than relaxed, the plan filter's own cost bound on the annular
   vault at 96 a ring: it now takes about 0.79 s, against a bound of 4 s, roughly five times headroom
   and still fifty times under the 206 seconds the unoptimised filter took before the fix that check
   guards. The field computation this wave adds is a separate, smaller cost: on the same scale of
   fixture it runs at 11 to 15 per cent of the whole pattern build's own time, comfortably under the
   fifth of that time the field is now held to.

6. Every saved definition needs its Skin and Export wires checked once after this wave lands, because
   both components' ports moved during it. Skin's own ports have shifted as inputs were added across
   the wave's tasks, and Export's input order was reordered by Task 32's own step. A definition saved
   against the old ports will have wires sitting on the wrong inputs after the update, silently,
   unless each wire is checked against its new port name. Export's Live toggle is HELD across a
   definition load whose ports moved, exactly the guard rule 9.4's port-identity check exists for, so
   after checking the wires Live needs to be toggled off and back on again before Export will run.

7. Rhino must be restarted after the plugin is installed. An open Rhino session keeps the old .gha
   loaded together with its worker process, and installing over it does not reach either: the new
   component code only takes effect once Rhino itself is closed and reopened.
