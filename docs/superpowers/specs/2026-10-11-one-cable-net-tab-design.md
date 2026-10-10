# One Cable net tab, driven by one physics run

Date: 2026-10-11. Written from the owner's critique of 10 October 2026 (evening), after he looked at the studio with the gripped-rod holds (main 3cdc029), and from his answers to six questions and five design sections the same night. Every choice he did not make is marked as a ruling.

## 1. What he asked for, and what he ruled

He reversed his ruling of 9 October ("Cable net want its own"): "one calculation wants to run both of them ... can we merge them please". His critique, in his terms:

1. One tab, one calculation. The Cable net analysis "barely does anything because it is not being measured off the true physics run outcome", so no deflection shows.
2. The wire key misleads: values drawn green sit under the red band.
3. Per spool, not "an equilibrium answer of them all": what one spool pulls against what the worst single wire needs.
4. The answer he still lacks: the force needed, the force we have, how much is missing or to spare.
5. No prestress arrows: numbers and wire colours.
6. Wire tension shown across the whole object, not only the hotspots; more information without crowding.
7. A skin transparency slider from invisible to 50% opacity.
8. The mechanism pop-up has far too much text. A preconfigured mechanism dropdown chosen by motor name and newton output, worked out per spool. No motor or cost breakdown there.
9. Cost as one spooling mechanism and the total; Export BOM instead of the detail.
10. Changing the mechanism shows where the formwork actually gets to.
11. Actual values on the model, not colour alone.
12. A hold on every node "won't work". He chooses how many extra holds a side and the studio places them; 0 is allowed, to show the design failing. He thinks the form "isn't that far off without the holds"; pressure may be the answer (it waits on his own research).
13. A compare mode: where the formwork should be against where it is, the offset and the tolerance; the design translucent and drawn as formwork, not skin; one click.
14. A better layout for the toggles.
15. A change that needs a rerun reruns; only the part that changed where possible (holds only rerun after the raise).
16. Worst goes ("bad name"); the weakest parts are shown on the model.
17. Play and pause as symbols in the studio's style.
18. Only what is genuinely useful, visualised well.
19. The mechanisms (the machine models) hidden for now: "they are the old ones".

His answers:
- The net's prestress comes from the mechanism's pull: the net is cut and reeled for what one spool of the chosen mechanism gives.
- "N extra holds a side": per side, at the worst sag, placed by the studio.
- The dropdown holds whole mechanisms; the four separate selects go; the wires-a-motor slider stays.
- Approach: the Formwork tab grows into the one tab, which is called Cable net; Formwork leaves the rail. Built in three stages from this spec.
- The two graphs from the run stay.
- The diagram, the data sheet and the holds file for Grasshopper are retired until they are rebuilt from the run.

## 2. Why the two tabs disagreed (the findings behind his questions)

The Cable net tab never simulated anything. Its wire tensions (8 to 31 N on the 5 sided form) were a tension-only fit on the fixed designed shape, with the column heads and drums held; on this dome the fit carries almost nothing (the timber cut's last course: 140 kN of load, 17 kN in the heads, 2.5 kN in all 105 wires, 122 kN unbalanced). The prestress did not enter that fit; it only stiffened a linear sag estimate. Needed was one prestress for the whole net from that estimate; Gives was the weakest single wire of the chosen machine; the Machines table printed Needed on every wire. The key spread three equal bands over 0 to the largest tension while each wire was coloured against the machine's limit. None of its lenses read the physics run. This spec removes all of it.

## 3. Scope and stages

One tab, called Cable net, grown from the Formwork tab. Three stages, each usable when it lands:

- Stage 1, one tab: the run with the mechanism's pull, the answer block, the drawing (section 5), the mechanism dropdown, the removals (section 9), the mechanisms hidden. Holds: none.
- Stage 2, holds: N a side (section 6) and the rerun from the hold (section 7).
- Stage 3, the pop-up's Cost tab, Export BOM and the two graphs (section 8).

Ruling (amended while writing): the mechanism dropdown moves from stage 3 into stage 1, because removing the fixed-shape solve takes away everything the old pop-up's tables read. Cost if wrong: stage 1 is a little larger.

Out of scope: pressure (waits on his research); part 5 (the plugin's Columns); the rebuilt diagram, data sheet and holds file.

## 4. The run and the answer

### 4.1 The mechanism and its pull

The mechanism is one entry of the dropdown (section 8.1): a motor, a gearbox ratio, a pulley (or none) and a rope, at the panel's wires a motor. One spool's pull ("Have") is the binding (lowest) term of the configuration's per-wire limits, as the studio already works them out (`machine.limit_terms`): the rope's working load, the anchor chain (eye bolt and turnbuckle), the spool's rope tension, the sheave, and the motor or gearbox torque shared across the wires on a motor. Have is per spool, never a total.

### 4.2 The run

One Run button. The server builds the engine's request as the Formwork run does now, with the prestress set to Have: every rope is cut so it carries Have at the designed shape (the engine's cut takes the larger of Have and its own fit, as now). The tab never sends a prestress; the server works out Have from the chosen mechanism and refuses one line ("Choose a mechanism") when there is none. The cut's material and the study are those open in the studio. The run takes about two minutes on the real study.

The capture document gains: the mechanism (its configuration and its description), `have_newtons` and its limiting part, `holds_per_side` (stage 2) and, per hold, its side.

Ruling: the default mechanism for a study that has none is the strongest entry of the dropdown. Cost if wrong: a first run with a machine he did not pick.

### 4.3 The answer block

At the top of the panel, from the run:

```text
Needed   57,476 N   worst wire, 2-1-4, at t 60
Have      3,411 N   one spool, ES-MH342200 50:1, 8 mm
Missing  54,065 N   ✗          (or: Spare 1,200 N ✓)
Form        12 mm   worst offset, tolerance 20 mm ✓
Holds    3 a side, 15 rods      (stage 2)
```

- Needed: the largest wire tension anywhere in the run, with the wire's name and the capture. A click takes the player to that capture and the camera to that wire.
- Have: section 4.1, with the mechanism's short name.
- Missing or Spare: Needed less Have; ✗ when Needed is over Have.
- Form: the worst distance from the design at the last capture (the end of the tiling), marked against the panel's tolerance.
- The run's own frame line stays under the player (rope max, wire max, trees, offset max, heads touching; struts and ties with holds).

### 4.4 Out of date

A change of mechanism or wires a motor makes the shown run out of date: the answer block is greyed and one line says "Run again: mechanism changed". Section 7 says what reruns on its own.

## 5. What the tab draws

### 5.1 Colour by

One at a time, as a segmented bar: Wires (the default), Ropes, Offset, Trees, Off.

- The whole net is coloured on a full ramp from the run's lowest to its largest (the scale is the run's, so a colour is the same value in every capture), starting from a clearly visible cool colour, so the spread shows everywhere and not only at the hotspots.
- The key is a real scale from 0 to the run's largest, with the limit drawn at its true place and its value: Have for wires, the rope's working load for ropes, the tolerance for offset, 1.0 for trees. The equal-thirds bands go.
- Whether a part is over its limit is shown by Weakest (5.3), not by recolouring.

### 5.2 Values on the model

For the colour shown: the worst five in view and the worst in each side, spread so they do not overlap. A click on any part opens its card (its figures, and for a node its members' tensions). Head pushes are in the card and the labels; there are no arrows anywhere (prestress arrows and the heads' push arrows both go).

### 5.3 Weakest

A button. At the capture shown, every part over its limit gets a red ring and its value: a wire over Have, a rope over its working load, a tree member over 1.0, a node outside the tolerance. When nothing is over, the five closest to their limits get an amber ring and their margin. It replaces the Worst pop-up and its tables.

### 5.4 Compare

A button. The design drawn as translucent formwork: its rope net and a pale blue see-through surface on the cut mesh's faces at their designed points, never the skin. From each node a short line from where it should be to where it is, green within the tolerance, amber near it (over half of it), red over; the largest offsets labelled in mm.

### 5.5 Skin, mechanisms, toggles, player

- Skin: a slider from 0 (hidden) to 50% opacity, default 30%.
- Mechanisms: the machine models are not drawn anywhere in the studio for now. The tab draws its own anchors and wire stubs as now. Ruling: hidden studio-wide rather than only in this tab, as "better just not to see them" reads. Cost if wrong: one switch.
- Toggles: Show as compact chips (Net, Trees, Heads, Wires, Anchors, Ground, Holds); Compare and Weakest as two larger buttons; Colour by as the segmented bar; Labels on or off.
- Player: back, play or pause, and step as symbols in the style of the studio's own toolbar; the capture label and the scrub stay.

## 6. Holds (stage 2)

- Holds a side: a slider from 0 to 20, default 0. With 0 the run is the design as it fails.
- Sides: a side is one wired run of the rim, found from the net itself: the rim's wire nodes chained along the net's boundary edges (edges on one face) split into separate runs, one per side (five runs of 21 on the 5 sided form, three machines each). Each net node belongs to the side it is fewest net steps from, ties to the lower-numbered side (on the 5 sided form: 231, 220, 220, 220 and 210 nodes, 9 or 10 column heads each). A net whose rim does not split into runs is refused in one line.
- Placement: at the hold capture (t 100) of the run without holds, each side's N rods go on that side's nodes furthest from the design, picked one at a time, never on a column head, a wire node, or a net neighbour of a rod already placed. Each side is placed on its own sag.
- Each hold is a gripped rod, as he ruled on 10 October: jacked to its design point after the raise, held in every direction from then on, a strut where it pushes and a tie where it pulls, drawn at its force's angle at the capture after the jacking, green or blue.
- The line search (every 10th, 5th, 2nd line, every line), its bands and its table go.

## 7. Reruns

| Change | What happens |
|---|---|
| Mechanism or wires a motor | A full run, started on its own after the change settles (one second without another change). The last run stays on screen, greyed and marked out of date, until the new one lands. |
| Holds a side | A run from the saved state at the hold: only the jacking and tiling are worked out again. |
| Tolerance | No run. The marks, the Offset colours and the Form line are judged again. |
| Tree wall | No run. The trees are judged again from the run's own member forces. |
| Skin, Colour by, Compare, Weakest, labels | Display only. |

The saved state: the engine returns, with its captures, its state at the hold (every node's position, the contacts: heads, engaged, resting, seated, left, tied; the reels; and, with shared motors, the motor pairing). The server keeps it beside the capture document, keyed as the capture document is. A holds-only run reads it, places the holds (section 6), jacks and tiles, and writes the whole capture document again with the saved captures up to the hold. A missing or mismatched state falls back to a full run. Run Again (the button) is always a full run.

The holds-only run must give the same captures as a full run with the same holds (test, section 10).

## 8. The pop-up

Two tabs open from the panel: Mechanism and Cost, plus Graphs (stage 3).

### 8.1 Mechanism (stage 1)

- One dropdown of whole spooling mechanisms, strongest first: for each motor the catalogue offers, the gearbox ratio, pulley and rope that give it the highest pull a spool at the panel's wires a motor, written with real names and its pull, for example `ES-MH342200, 50:1, 190 mm pulleys, 8 mm 7x19: 3,411 N a spool`. Motors the catalogue cannot build are left out.
- Under it, three lines: Have (its pull a spool), Limited by (the part that sets it, by name), Checks ("all pass ✓", or only the check that fails: rope on drum, carriage travel, drum or pulley D/d).
- Gone: the four selects, Recommend, the limits, motors, machine and machines tables, the eye bolt line, the travel table and the rope speed slider.

### 8.2 Cost (stage 3)

- One spooling mechanism as one priced line, its parts named.
- Spools (105 on the 5 sided form), cabinets (count times price), the total, VAT excluded; "Unpriced: n parts" when any.
- Export BOM: writes the bill of materials spreadsheet to the study's export folder, its demands (each wire's peak tension) read from the run. The per-machine and per-part tables go from the pop-up.

### 8.3 Graphs (stage 3)

Two, from the run, over its captures: the worst wire tension against Have (a dashed line), and the worst offset against the tolerance (a dashed line).

## 9. What goes

- From the rail: the Formwork button (its tab is now Cable net).
- The fixed-shape solve and everything built on it: the Cable net run and its route, its document (cablenet-*.json is no longer read), Needed / Gives / Most / Holds / Roof, the lenses (tension, node force, sag, prestress, reel, holds) and their arrows, labels and legends, the five graphs, the walk and the ladder.
- The Worst pop-up and its tables; the holds search and its table.
- Exports: the diagram, the data sheet and the holds file for Grasshopper leave the page and the export route until they are rebuilt from the run. Ruling: their writers' code stays in the repository, unreached, with its tests, so the rebuild starts from it. Cost if wrong: dead code until then.
- The plan audits every file that reads the removed document and lists each deletion.

## 10. Tests and checks

- Mechanism: Have equals the binding limit term for a known configuration; the dropdown lists one entry a buildable motor, strongest first, with its pull; shared motors lower Have.
- The run: the request's prestress is Have; the document carries the mechanism, Have and its part; no mechanism is refused in one line.
- The answer block: Needed is the run's largest wire tension with its wire and capture; Missing and Spare and their marks; Form against the tolerance; greyed and "Run again" when out of date.
- The drawing under node with three.js: the full ramp's low end is visible; the key's limit marker sits at its true place; Weakest rings exactly the parts over their limits, and the five closest when none is; Compare draws the design faces translucent and an offset line a node coloured by the tolerance; the skin slider's 0 hides it and 50 is half opaque; no arrows are built.
- Sides and placement on a toy net with two sides: each node's side; N rods a side on the furthest nodes, never a head, a wire node or a neighbour.
- The saved state: a holds-only run from it gives the same captures as a full run with the same holds.
- The page by its text: one Cable net tab, no Formwork button, no Worst, the toggles' layout, the player's symbols.
- On screen, before he is told it is ready: the real 5 sided form at 0 holds and at 3 a side, every view looked at (each Colour by, Compare, Weakest, the skin slider at 0 and 50, the pop-up), and a new video.

## 11. Rulings in this spec

- The dropdown moves into stage 1 (section 3).
- The default mechanism is the strongest entry (4.2).
- Mechanisms hidden studio-wide (5.5).
- The heads' push arrows go with the prestress arrows (5.2).
- Offset bands: green within the tolerance, amber over half of it, red over (5.4), as the studio's tolerance bands already are (deviationBand).
- Skin default 30% (5.5); holds a side capped at 20 (6).
- A rerun starts one second after the last change (7).
- The retired exports' code stays, unreached (9).
