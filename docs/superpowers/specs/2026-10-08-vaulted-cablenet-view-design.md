# Vaulted: the cable net as a view, and where to grab the net

Design specification, 8 October 2026. Branch `feature/studio-finish`.

This replaces the cable net panel shipped on 7 October rather than extending it.
That panel was a tab inside the Data popup and reported in prose. The owner's
verdict, with a screenshot: it belongs on the rail beside the other sections, it
must draw on the model rather than describe it, and it must be legible.

It also answers the question he asked in the same breath: **how many nodes do we
need to grab, and where**, which is the research question underneath the whole
machine and a better one than sizing a single configuration.

## 1. The intent, written back

Two things, which are really one.

A person opening a study should be able to press one button on the rail and SEE
the cable net: the formwork read through a ghosted skin, the net coloured by
tension, the force at each node drawn where that node is, the prestress tagged
at the terminations. Numbers on the model, not a paragraph beside it.

And they should be able to ask what it would take to hold THIS surface: how many
actuated nodes, placed where, to bring the whole net inside the acceptance line.
The answer is a curve of actuators against deviation with the chosen nodes lit
on the vault, and it generalises to any surface, symmetric or not, which is what
reconfigurable formwork means.

The second is what makes the first worth looking at: the per-node force the
lenses draw IS what the placement computation produces.

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
| view switching | `SHOW_BUTTONS`, `setShowMode`, modes `framework`, `shell`, `both` |

Nothing in this spec may reimplement any of those. Where a cable net lens needs
behaviour one of them already has, it calls it.

## 3. The rail section

An eighth rail button, **Cable net**, with `data-section="cablenet-section"`, and
a matching `<details id="cablenet-section">` in `#panel`, between Analysis and
Animation because that is the order of the work.

Its contents, in this order:

1. **What the build demands.** The prestress floor, the stage that sets it, the
   acceptance line and its source, the worst miss. These do not move when parts
   change and the section says so, as the panel does today.
2. **The lenses**, as section 4.
3. **The parts**, as section 6: named selects in the panel's own `label.named`
   style, the pulley as a labelled checkbox, the rope speed slider with its
   readout. Not the wrapping, overlapping block in the screenshot.
4. **The verdict**, as section 7.
5. **Where to grab**, as section 5.
6. **Export**, the three documents and the chosen folder, moved across
   unchanged in behaviour.

The Data popup's Cable net tab and its markup are **removed**. One place, not
two.

## 4. The lenses

Four, added to `LAYERS` or to a sibling table read by the same builder, each
drawing on the model:

**Wire tension.** The net coloured by the tension each member carries at the
selected stage. `applyWireForces` already colours wires by force for the
analysis lens; this is the same treatment driven by the demand document's
per-stage tensions. Like Wire forces, raising it shows the net, so it belongs in
`EXCLUSIVE_LAYERS`.

**Node force.** The force at each node drawn as an arrow at that node, through
`arrowField` with the anchor and scale the vector lenses already take. This is
the live force per node the owner asked for, and it is what section 5 computes.

**Prestress.** Tagged at the terminations: a label at each wire's net end
carrying that wire's tension, and at the anchor rows the chain's working limit,
so the margin reads where the part is rather than in a table.

**Reel.** How much each wire pays out or takes in between the previous stage and
this one, drawn along the wire, so the raising and the tightening can be watched
rather than totalled.

Each gets one note under it when active, in the voice of the Support thrust
note, saying what it shows and what it does not. Each gets a `layerAvailability`
answer naming what is missing when it cannot draw, which for all four is "this
study has no cable net demand yet; run it with the cable net phase enabled".

## 5. Where to grab the net, and how many

The computation the owner asked for, and the reason the lenses have anything to
draw.

**What it computes.** At the target shape, with the columns holding their nodes
and the rim held, fit the best tension-only state the net can carry under the
stage's load. The force left unbalanced at each free node is what an actuator
there would have to supply. That residual field is the Node force lens.

Then place actuators greedily: take the nodes with the largest residual, add
them to the held set, refit, and repeat. Report the curve of **number of
actuated nodes against worst deviation**, and the chosen nodes.

**Honesty about the method.** Greedy placement by residual is a heuristic, not
an optimum, and the spec says so on the panel as well as here. It answers "a
good place to put the next twenty" and not "the best possible twenty". A test
pins that the curve is monotonic in the sense that more actuators never make the
reported deviation worse, because a result that wandered would mean the fit, not
the placement, is at fault.

**Cost, which decides the shape of the loop.** A forward solve on the real
1101-node study takes about a second, so re-solving for every candidate
placement is not affordable. The fit used inside the loop is the linear
non-negative least squares, which is cheap, and a true forward solve is run only
at the handful of actuator counts the curve reports. The panel says which
numbers came from which.

**Where it runs.** In `solve_cablenet.py`, under the solver interpreter, like
every other solve. `bench/studio/**` stays free of numpy and the solver stack and
`tests/studio/test_studio_guard.py` still enforces it.

**What it answers that the first two specs did not.** Those sized one machine
against one export. This takes any surface and says what holding it costs in
actuators. That is the reconfigurable formwork question, and it is the one worth
putting in front of a supervisor.

## 6. The ghosted skin

The owner asked for the formwork to show through a partly transparent skin,
automatically. The three show modes are opaque, and the renderer already sets
`transparent` on several materials, so the mechanism exists and is simply not
wired to a view.

While any cable net lens is up, the shell is drawn semi-transparent over the
framework rather than replacing it, so the net reads through the vault. Leaving
the lenses returns the view to whatever it interrupted, exactly as Wire forces
already does through `state.showModeBeforeForces`.

This is a fourth behaviour of the existing modes and not a fourth button: the
owner asked for it to happen automatically, so nothing new to press.

## 7. The verdict, shown rather than described

The section reports, in short lines rather than paragraphs:

- whether it holds, as the two halves that can disagree: the parts carrying the
  tension, and the net keeping its shape within the acceptance line
- the ceiling, and the part that sets it, named
- the prestress required against that ceiling
- how much wire goes through each drum, against the drum's single-layer capacity
- the rope speed the configuration gives, and the motor speed it demands

Every figure already exists; this is a presentation change. The one new figure
is the actuator count from section 5.

## 8. What must not regress

The engine, the catalogue, the three exports and their agreement tests are
untouched. `studio.js` gains only what the rail and the lenses require. The
rope speed slider still cannot change a verdict. The three documents still agree
byte for byte, and the test that proves it still runs.

## 9. Open items

1. **The greedy placement is a heuristic.** A better one exists and is a
   research question in its own right; the panel must not imply optimality.
2. **The actuator count assumes a wire can be put at any node.** Where the
   machine physically cannot reach, the answer is optimistic. Nothing in the
   export records reachability, so this is stated rather than modelled.
3. **The cross-axis wires are still not in any export.** The placement
   computation is how to decide where they go, so this spec is the tool for
   that decision rather than a description of a machine that exists.
