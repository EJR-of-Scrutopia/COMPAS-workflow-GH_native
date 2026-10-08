# Vaulted: the cable net as a view, and where to grab the net

Design specification, 8 October 2026. Branch `feature/studio-finish`.
Revised the same day after the owner read the first draft, and again on 8 October
after the formulation was measured against the real export (section 13).

This replaces the cable net panel shipped on 7 October rather than extending it.
That panel was a tab inside the Data popup and reported in prose. The owner's
verdict, with a screenshot: it belongs on the rail beside the other sections, it
must draw on the model rather than describe it, and it must be legible.

It answers two questions the machine exists for and the shipped panel did not:
**can this system hold the weight**, and **how many nodes must we grab, and
where**.

## 1. The intent, written back

A person opening a study presses one button on the rail and SEES the cable net:
the formwork read through a ghosted skin, the net coloured by tension, the force
at each node drawn where that node is, the prestress tagged at the terminations,
and the sag shown where the net is not held well enough to keep its shape.
Numbers on the model, not a paragraph beside it.

They choose a system, with the parts that must go together already paired, or
press Recommend and get one. The panel tells them what load it can carry, where
it sags, how much reeling it does, and whether it holds.

Then one button exports the configuration with its data.

**Price is not the subject.** It stays in the exported documents, where a
supplier or a supervisor needs it, and comes out of the panel, which is about
whether the thing works.

## 2. Build with the panel, not beside it

The studio already has every mechanism this needs. The 7 October work ignored
them, which is the mistake this spec exists to correct.

| what is needed | what already does it |
| --- | --- |
| a rail button and its section | `#tab-rail` buttons carry `data-section`, each opening a `<details>` in `#panel` |
| lens buttons with a note under the active one | `LAYERS` plus `buildLayerToggles`, which already writes the Support thrust note |
| a lens saying why it is greyed out | `layerAvailability(name)` returning `{on, why}` |
| one painting lens at a time | `EXCLUSIVE_LAYERS` and `setLayer` |
| the net coloured by force | `applyWireForces` |
| vectors drawn per node | `updateVectorLayers` and `arrowField(entries, colour, anchor, scale)` |
| view switching and restoring | `SHOW_BUTTONS`, `setShowMode`, `state.showModeBeforeForces` |
| how much load a mechanism can carry | `capacity_from_curve` and its checks, already built and tested, moved whole into the standard-library `mechanism.py` so the server can call them; the curve they read is built from the fit of section 8, because the forward solve behind `tension_curve` refuses the real study (section 13) |
| refusing a mismatched motor and drive | `catalogue.mechanism_for`, which already raises naming both families |

Nothing in this spec may reimplement any of those.

## 3. The rail section

An eighth rail button, **Cable net**, with `data-section="cablenet-section"`, and
a matching `<details id="cablenet-section">` in `#panel`, between Analysis and
Animation because that is the order of the work.

Its contents, in this order, which is the order the questions are asked:

1. **Run**: the section's one primary action, `Run cable net analysis`, with
   the prestress floor and the rope speed as dials beside it. Nothing in the
   studio today sends the cable net phase, so no study has a demand document
   until this exists. It runs the cut and the analysis of section 8 only, not
   the staged FEA, and reports progress through the same run registry.
2. **What the build demands** (section 7)
3. **The lenses** (section 4)
4. **The system** (section 5)
5. **Can it hold it** (section 6)
6. **Where to grab** (section 8)
7. **Export** (section 9)

The Data popup's Cable net tab and its markup are **removed**. One place, not
two.

## 4. The lenses

Five, in a sibling table of `LAYERS` read by the same builder, each drawing on
the model. Every figure they draw comes from the demand document of section 8;
nothing is computed in the browser beyond colour and scale.

**Wire tension.** The net coloured by the tension each member carries in the
best tension-only state at the selected instant (`member_tensions`). A painting
lens, so it joins `EXCLUSIVE_LAYERS`.

**Node force.** The force left unbalanced at each node by that state, drawn as
an arrow at the node (`node_residual`). It is what an actuator there must
supply, and it is the field that chose the grabbed nodes.

**Sag.** The net coloured by how far each node would move under that unbalanced
force, with the direction drawn where the move is large (`node_sag_mm`). It is a
first-order figure: the unbalanced force divided by the net's tangent stiffness
at the fitted tensions, with the entered prestress as a floor on every member.
It is not a re-solve of the net, and where the net is slack and flat the figure
is large and says so. Red past the acceptance line, falling to neutral well
inside it, so the eye goes to the problem. A painting lens, so it joins
`EXCLUSIVE_LAYERS`.

**Prestress.** Tagged at the terminations: at each mechanism wire's net end an
arrow along the wire, its length the tension and its colour the margin against
the chosen system's ceiling, so the margin reads where the part is. With no
system chosen the tags show tension alone and the note says so.

**Reel.** How much each mechanism wire pays out or takes in between the previous
computed instant and this one, drawn along the wire: the change in its length
from the exported frames, plus the elastic take-up when its tension changes. On
this export the rim never moves, so those figures are the take-up alone, which
is a result and is shown as one. At a grabbed node, where no drum point is
known, the node's own travel between instants is drawn instead and the note
names it as travel, not rope.

The lenses draw on the finished net at its exported shape whichever instant is
selected; the stage line under the buttons names the instant the figures belong
to (a frame of the raise, or a course of the skin) and says they are drawn on
the finished net. Scrubbing the timeline moves the instant.

Each gets one note under it when active, in the voice of the Support thrust
note. Each gets a `layerAvailability` answer naming what is missing when it
cannot draw, which for all five is "this study has no cable net demand yet; run
the cable net analysis from this section".

## 5. The system: pick a configuration, not nine parts

**The catalogue stays rich and grows.** The point is not fewer parts; it is
fewer decisions at the moment of use. Assembling a machine from nine independent
selects is the wrong unit of choice, because most combinations are not machines
anybody would build and the person is left to work out which are.

So the catalogue gains a **configurations** block: named, complete, buildable
mechanisms, each naming its parts and carrying a line saying what it is for and
what it is good at. The panel's primary control is a single select over those.

A configuration is a part set plus a description, for example a seven-spool
stepper rig with the planetary gearbox and the rope path as currently drawn; the
same with the moving block fitted; a three-phase inverter rig on a worm reducer
for higher sustained torque; the same rig with the rope path upgraded to eye and
eye terminations and heavier rope. The list is the designed options, not the
cross product.

**Three ways in, in increasing effort:**

1. **Recommend** picks a configuration outright, by the rule in this section.
2. **The configuration select** offers the designed set, each with its one-line
   description, and switching between them is the normal way to explore.
3. **Vary parts** is a collapsed block, opened only when wanted, exposing the
   individual selects. Changing anything marks the state "modified from
   that configuration", so it is always clear whether you are looking at a designed
   machine or one you have altered, and a reset returns to it.

**The drive follows the motor, and is shown rather than chosen**, at every level
including the varied one. The catalogue already carries a `family` on every
motor and drive, and `mechanism_for` already refuses a mismatch by raising. A
refusal is the wrong way to learn this at a panel, so the pairing is applied and
named, and the refusal stays as the backstop for anything posted to the route
directly. The gearbox list filters the same way, planetary for a stepper and
worm for a three-phase motor.

**What is settled is said, not offered.** The wiring and the electronics are
decided, so they appear as a short stated block rather than as controls: the
drive that follows the motor, the bespoke drum, the rail, and the note that the
controller, single board computer, power supply, amplifiers and terminals carry
no mechanical load and therefore change no number on this panel. A reader
should not have to wonder whether they were forgotten.

**Recommend.** One button filling the whole configuration in. The rule, stated
on the panel and not merely implemented: the configuration that carries the load
with the largest margin, and among those that tie, the one with the fewest
parts. If none carries the load, it recommends the one with the highest ceiling
and says plainly that nothing in the catalogue is sufficient, which is a result
and not a failure. The search is arithmetic against the stored tension curve, so
it is instant and never re-solves.

Where something is decided for the person, the panel says so in a line rather
than silently changing a control, because one that moves on its own and stays
quiet is how somebody comes to believe they chose it.

**Recommend.** One button that fills the whole system in. The rule, stated on
the panel and not merely implemented: the configuration that carries the load
with the largest margin, and among those that tie, the one with the fewest
parts. If none carries the load, it recommends the one with the highest ceiling
and says plainly that nothing in the catalogue is sufficient, which is a result
and not a failure. The sweep this searches is arithmetic against the stored
tension curve, so it is instant; it never re-solves.

## 6. Can it hold the weight

The question the shipped panel never answered.

The forward solve cannot answer it on the real study: with the column heads and
the rim held, `solve_prescribed_lengths` refuses at every prestress from 100 N
to 5000 N because the net goes slack (section 13). So the curve
`capacity_from_curve` reads is built from the fit of section 8 instead, on one
stated assumption: **the tensions scale with the load**. That is the owner's own
hypothesis for the machine, that the actuators re-tension the net to hold its
shape as the skin arrives, and it is exact for the fit, whose feasible set is a
cone. The net's own weight is scaled with the skin, which overstates the demand
slightly and is conservative.

So at the sizing stage the document records the worst wire tension and the
worst sag under the full load. The wires are judged at the larger of the
entered prestress and the greatest tension the fit finds in any wire, and that
larger figure is the worst wire tension the sizing block records, with the two
kept beside it. The shape half gives every member the prestress as a floor on
its stiffness and judges the sag at it, so a wire judged at the fit's own
tension (14.6 N on the real study, at 300 N) would let a rig pass for a net the
analysis holds at the prestress. The curve has `worst_tension = f * t1` and
`deviation = sag` at every factor `f`, and `capacity_from_curve` applies the
chosen mechanism's checks to it unchanged. It answers:

- **the load factor**: how many times the real skin weight this system can carry
  before something binds, where 1.0 means it carries the skin exactly and no
  more
- **what binds**, named as the part, not the constraint: the turnbuckle, the
  sheave, the motor; or the shape, when the sag is past the acceptance line at
  any load, which no part can cure
- **the margin** against the skin as specified

`capacity_from_curve` and its checks move whole into `mechanism.py`, which is
standard library only, so the server can call them without numpy; `capacity.py`
keeps exporting the same names, the result is identical and the existing curve
tests prove it.

The panel states the skin it is judging: the thickness, the density and the
total weight in kilonewtons, because a load factor against an unnamed load means
nothing. Those numbers already exist in the demand document.

A load factor below 1.0 is reported as plainly as one above it. The documents
and the panel lead with the failure, as they already do for the two halves of
the verdict.

## 7. What the build demands

Unchanged from the shipped panel in substance, first in order because it does
not move when parts change: the prestress floor and the stage that sets it, the
acceptance line and its source, the worst miss and where it occurs, and the
total skin weight. The section says these are properties of the vault and the
skin, not of the chosen parts.

## 8. Where to grab the net, and how many

The computation the owner asked for, and the reason every lens has something to
draw.

**What is held.** The drum end of each of the 105 mechanism wires, which
`build_problem` already fixes, with the wires as tension members so each can
pull only along its own line; and the 46 column heads, read from the formwork
document's `columns.headNode`, which are the net nodes the columns prop. A
column is not a member: it is a node whose position is prescribed, and the
force it carries is the reaction there.

**What it computes.** At the shape the export gives for the instant, fit the
best tension-only state the net can carry under the instant's load: a
non-negative least squares over every member's force density
(`hold.fit_tension_state`, measured at 1.4 s on the real net). The force left
unbalanced at each free node is what an actuator there would have to supply:
that field is the Node force lens. The reaction at each column head is the
column force, reported with its vertical part. The movement each unbalanced
force would cause, to first order through the net's tangent stiffness with the
entered prestress as a floor on every member (`stiffness.first_order_sag`,
measured at 0.1 s), is the Sag lens.

**Then place actuators greedily**, at the heaviest instant: take the nodes with
the largest unbalanced force, in batches of twenty, add them to the held set,
refit, repeat, until the worst sag is inside the acceptance line or forty
batches have been tried. Report the curve of **number of actuated nodes against
worst sag and worst unbalanced force**, with the chosen nodes lit on the vault,
and whether the line was reached. Every stage's figures and every lens are then
given with the actuators at the chosen count; the curve tells the story of
fewer.

**The instants.** Five frames of the raise, at machine times 45, 60, 75, 90 and
100, under the net's own weight; and every course of the skin at the finished
shape. The lenses snap to the nearest computed instant and the stage line names
it.

**Honesty about the method.** Greedy placement by residual is a heuristic, not
an optimum, and the panel says so. It answers "a good place to put the next
twenty", not "the best possible twenty". A test pins that the residual norm
never rises as actuators are added, which is provable: holding a node removes
its equations and leaves every member free to do what it did. A curve that rose
would mean the fit is at fault rather than the placement.

**Cost.** One fit is 1.4 s and a refit after holding a batch is 0.1 s, so the
whole analysis of a 1101-node study is a minute or two in a subprocess, run once
per study and cached in the demand document. The panel never re-solves.

**Where it runs.** In `solve_cablenet.py`, under the solver interpreter, like
every other solve. `bench/studio/**` stays free of numpy and the solver stack,
and `tests/studio/test_studio_guard.py` still enforces it. `walk_stages`, the
forward walk, stays in the module with its tests and is no longer what the
route runs; the demand document it wrote is replaced by this analysis under
schema `bench.cablenet/2`, keeping the name and meaning of every field the
exports read.

## 9. Export

**One button.** It writes the configuration together with its data: the parts
chosen, the load factor and what binds, the prestress demanded against the
ceiling, the reeling per wire per stage, the sag and where it is worst, the
column forces, and the actuator count with the chosen nodes.

The three documents from the 7 October spec remain and are what that button
produces, unchanged in behaviour, because they already agree with each other and
a test proves it. What changes is the panel: one button rather than a folder
row, a choose-folder control beside it, and the files listed after a write.

**Price leaves the panel.** It stays in the spreadsheet and the data sheet,
where a supplier or a supervisor needs it, and no longer appears beside the
verdict. The totals keep saying they are a floor where a line is unpriced; that
honesty belongs with the figure, wherever it is shown.

## 10. The ghosted skin

The owner asked for the formwork to show through a partly transparent skin,
automatically. The three show modes are opaque, and the renderer already sets
`transparent` on several materials, so the mechanism exists and is not wired to
a view.

While any cable net lens is up, the shell draws semi-transparent over the
framework rather than replacing it, so the net reads through the vault. Leaving
the lenses returns the view to whatever it interrupted, exactly as Wire forces
already does through `state.showModeBeforeForces`.

A behaviour of the existing modes, not a fourth button: it was asked for as
automatic, so there is nothing new to press.

## 11. What must not regress

The catalogue's existing functions, the three exports' existing content and
their agreement tests are unchanged in behaviour; `capacity_from_curve` keeps
its name and its result; `walk_stages` stays with its tests. The demand document
grows and every field the exports already read keeps its name and meaning.
`studio.js` gains only what the rail and the lenses require. The rope speed
slider still cannot change a verdict. The three documents still agree byte for
byte and the test that proves it still runs. The interface language's dial
census is updated for the two new dials rather than worked around.

## 12. Open items

1. **The greedy placement is a heuristic.** A better one is a research question
   in its own right; the panel must not imply optimality.
2. **The actuator count assumes a wire can reach any node.** Nothing in the
   export records reachability, so the answer is optimistic and says so.
3. **The cross-axis wires are in no export.** This computation is how to decide
   where they go rather than a description of a machine that exists.
4. **Recommend ranks by margin, then by part count.** That is a defensible rule
   and not the only one; cost, resolution and speed could each lead instead, and
   the sweep already reports three fronts for exactly that reason.
5. **The load factor assumes the tensions scale with the load.** It is the
   owner's hypothesis for an actuated net and exact for the fit; a net with
   fixed rest lengths behaves differently, and that is what the forward solve
   would have measured had it run.
6. **Sag is first order.** The real net stiffens as it sags, but a member that
   would go slack keeps its stiffness in the linearisation, so a large figure
   is a guide and not a bound on the movement; small ones are close.
7. **The lenses draw on the finished net.** At a frame of the raise the figures
   belong to a different shape than the one they are drawn on; drawing them on
   the formwork net is a later refinement.

## 13. What the real export settled, 8 October

Measured before this revision, on `5 sided form` (1101 vertices, 2000 members,
105 wires, 46 column heads), with scripts in the session scratchpad:

- With the column heads and the rim held, the forward prescribed-length solve
  refuses at every prestress from 100 N to 5000 N: the net goes slack. The
  uniform cut rule is not an equilibrium state on this shape, so
  `tension_curve` cannot be pointed at it.
- The best tension-only self-stress state at the exported shape balances to
  7.6e-07 but is degenerate: the median member carries nothing, and forcing
  every member to carry a floor leaves a residual that grows in proportion to
  the floor. The shape cannot be held taut throughout by the net alone.
- Under the 66.9 kN tile skin, with only the columns and the rim holding, the
  fit leaves every one of the 950 free nodes unbalanced by 47 to 83 N: the net
  at this shape carries almost none of the skin, and the first-order sag is of
  the order of a metre at 300 N prestress and 200 mm at 3000 N.
- The 105 rim wires reel nothing across the 51 frames: the rim never moves. The
  raise is the columns; the finish phase moves 985 of 1101 nodes by more than
  100 mm, which is the cross-axis tightening the machine does not yet have.
- The dense non-negative solve converges in 1.4 s; the sparse bounded solver
  stops at its iteration cap unconverged and is not used.

So the deliverable of this spec is exactly the finding the owner feared: the
actuators are necessary, and the computation says how many and where.
