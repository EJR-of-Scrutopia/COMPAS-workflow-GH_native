# Vaulted: the cable net as a view, and where to grab the net

Design specification, 8 October 2026. Branch `feature/studio-finish`.
Revised the same day after the owner read the first draft.

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
| how much load a mechanism can carry | `capacity.tension_curve` and `capacity_from_curve`, already built and tested |
| refusing a mismatched motor and drive | `catalogue.mechanism_for`, which already raises naming both families |

Nothing in this spec may reimplement any of those.

## 3. The rail section

An eighth rail button, **Cable net**, with `data-section="cablenet-section"`, and
a matching `<details id="cablenet-section">` in `#panel`, between Analysis and
Animation because that is the order of the work.

Its contents, in this order, which is the order the questions are asked:

1. **What the build demands** (section 7)
2. **The lenses** (section 4)
3. **The system** (section 5)
4. **Can it hold it** (section 6)
5. **Where to grab** (section 8)
6. **Export** (section 9)

The Data popup's Cable net tab and its markup are **removed**. One place, not
two.

## 4. The lenses

Five, added to `LAYERS` or a sibling table read by the same builder, each
drawing on the model:

**Wire tension.** The net coloured by the tension each member carries at the
selected stage, through `applyWireForces`. Raising it shows the net, so it joins
`EXCLUSIVE_LAYERS`.

**Node force.** The force at each node drawn as an arrow at that node, through
`arrowField`. This is the live force per node, and it is what section 8
computes.

**Sag.** The net coloured by how far each node is from where it should be, with
the direction of the miss drawn where the miss is large. This is the lens the
owner asked for by name: it shows where too few grabbed nodes are letting the
form go, and equally where the support is ample. Red where the deviation exceeds
the acceptance line, falling to neutral where it is comfortably inside, so the
eye goes to the problem. It is a painting lens, so it joins `EXCLUSIVE_LAYERS`.

**Prestress.** Tagged at the terminations: each wire's tension at its net end,
and at the anchor rows the chain's working limit, so the margin reads where the
part is.

**Reel.** How much each wire pays out or takes in between the previous stage and
this one, drawn along the wire.

Each gets one note under it when active, in the voice of the Support thrust
note. Each gets a `layerAvailability` answer naming what is missing when it
cannot draw, which for all five is "this study has no cable net demand yet; run
it with the cable net phase enabled".

## 5. The system, with the parts that go together paired

The selects are in the panel's own `label.named` style, not the wrapping,
overlapping block in the owner's screenshot.

**Choosing a motor narrows everything that must match it.** The catalogue
already carries a `family` on every motor and drive, and `mechanism_for` already
refuses a mismatch by raising. A refusal is the wrong way to learn this, so the
panel prevents it instead: picking a motor filters the drive list to that
motor's family and selects that family's sensible default, and filters the
gearbox list to the kind that suits it, planetary for a stepper and worm for an
alternating current motor. The refusal stays as the backstop for anything posted
directly to the route.

Where a choice is made for the person, the panel says so in one line rather than
silently changing a box, because a select that moves on its own and says nothing
is how somebody ends up believing they chose it.

**Recommend.** One button that fills the whole system in. The rule, stated on
the panel and not merely implemented: the configuration that carries the load
with the largest margin, and among those that tie, the one with the fewest
parts. If none carries the load, it recommends the one with the highest ceiling
and says plainly that nothing in the catalogue is sufficient, which is a result
and not a failure. The sweep this searches is arithmetic against the stored
tension curve, so it is instant; it never re-solves.

## 6. Can it hold the weight

The question the shipped panel never answered.

`capacity.tension_curve` walks the load upward and records what the net does;
`capacity_from_curve` applies one mechanism's checks to that walk. Both exist,
are tested, and are already used by the chooser. Pointed at the staged skin load
rather than an abstract pattern, they answer directly:

- **the load factor**: how many times the real skin weight this system can carry
  before something binds, where 1.0 means it carries the skin exactly and no
  more
- **what binds**, named as the part, not the constraint: the turnbuckle, the
  sheave, the motor
- **the margin** against the skin as specified

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

The computation the owner asked for, and the reason the Sag and Node force
lenses have anything to draw.

**What it computes.** At the target shape, with the columns holding their nodes
and the rim held, fit the best tension-only state the net can carry under the
stage's load. The force left unbalanced at each free node is what an actuator
there would have to supply. That residual field is the Node force lens, and the
deviation it produces is the Sag lens.

Then place actuators greedily: take the nodes with the largest residual, add
them to the held set, refit, repeat. Report the curve of **number of actuated
nodes against worst deviation**, with the chosen nodes lit on the vault, and the
count needed to bring the whole net inside the acceptance line.

**Honesty about the method.** Greedy placement by residual is a heuristic, not
an optimum, and the panel says so. It answers "a good place to put the next
twenty", not "the best possible twenty". A test pins that more actuators never
make the reported deviation worse, because a curve that wandered would mean the
fit is at fault rather than the placement.

**Cost.** A forward solve on the real 1101-node study takes about a second, so
re-solving per candidate is not affordable. The loop uses the cheap linear
non-negative fit; a true forward solve runs only at the handful of counts the
curve reports, and the panel says which figures came from which.

**Where it runs.** In `solve_cablenet.py`, under the solver interpreter, like
every other solve. `bench/studio/**` stays free of numpy and the solver stack,
and `tests/studio/test_studio_guard.py` still enforces it.

## 9. Export

**One button.** It writes the configuration together with its data: the parts
chosen, the load factor and what binds, the prestress demanded against the
ceiling, the reeling per wire per stage, the sag and where it is worst, and the
actuator count with the chosen nodes.

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

The engine, the catalogue, the three exports and their agreement tests are
untouched in behaviour. `studio.js` gains only what the rail and the lenses
require. The rope speed slider still cannot change a verdict. The three
documents still agree byte for byte and the test that proves it still runs.

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
