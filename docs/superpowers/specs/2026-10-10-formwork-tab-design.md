# The Formwork tab: the raise played from the physics engine (DRAFT)

Date: 2026-10-10. Part 4 of the five the owner set out on 2026-10-09. A draft written overnight for his review: it is not planned and not built. It rests on the outline he agreed on 2026-10-09 and on what the code holds today; every choice he has not made himself is marked as a ruling for him to take or overturn, and the questions at the end are his.

## 1. What he ruled

- The Formwork tab is its own tab. The Cable net tab keeps its own run.
- In the tab: Run formwork analysis; the five-choice mechanism block, the same component as the Cable net tab's, the choices kept per study; a player over the captures (step, play, speed, a label such as `t 60 finish` or `S7 q2`).
- SHOW ticks, one a part: net, trees, heads and their push, wires and machine, anchors, ground contacts, skin placed, designed form.
- COLOUR BY, one at a time: rope tension N, deviation mm, tree utilisation, wire tension N, off; with a keyed scale.
- LABELS on the model for what is in view: rope kN, deviation mm, contact N.
- A frame line: rope max, wire max, trees, deviation max, heads touching n/46.
- A click on a node: its numbers and its members' tensions.
- WORST tables (ropes, wires, trees, nodes, machines) that sort, and fly to the row.
- No prose. The engine as real as possible, computed once in the background, the captures replayed in real time; no exaggeration slider.

## 2. What is there today

From the code at 694aae6 and later (a survey of bench/studio/solve_formwork.py, app.py and studio.js):

- The engine writes `bench.formwork-sim/1`: `net` (1101 nodes, 2000 edges, the design shape, rest lengths, the cut force), `rim` (105 wires on 15 machines of 7, anchors), `trees` (66 members, 16 feet, 46 heads), and `captures`. The real 5 sided form file is 4.3 MB: 100 captures (15 raise, 15 finish, 6 hold, then 64 tiling quarters), 112 s of engine time.
- A capture carries `phase`, `time` (machine time, none while tiling), `row` and `quarter`, the node positions `x` [1101, 3] mm, member `tension` [2000] N, `deviation` [1101] mm, `head_push` [46, 3] N, `anchor_force`, `wire_tension`, `reel`, `let_out` [105], the tree's `tree_x`, `tree_axial` and `tree_utilisation` [66].
- Arrays are packed as base64 little-endian float32 (`{shape, f32}`). Nothing in the browser decodes them yet.
- Not stored: ground contacts (the findings take a node within 1 mm of the ground), the skin placed (implied by row and quarter), a head's contact (a non-zero push), the labels (built from phase and time, or row and quarter).
- `POST /api/studies/{export}/formwork/run` runs it (110 s at one wire a motor, 210 s at two); `GET .../formwork/sim` serves the file.
- The studio draws nothing from the captures. Its Formwork, Shell and Both buttons and its 12 s formwork act play the bundle's `bench.frames/1` frames, not the engine.
- The node and edge numbering of the captures is the cable net demand's and the analysis mesh's, so the display pass's labels, legends and card can be reused with capture-shaped readers.

## 3. The tab

A ninth button in the rail, Formwork, after Cable net, and a `formwork-section` in the panel:

| Row | What |
|---|---|
| Run formwork analysis | the button, its one-line status and progress (capture n of 100) |
| Machine | the five choices, shared with the Cable net tab: one machine a study (ruling: the tabs never disagree on the machine) |
| Wall | the tree tube's wall, mm, a dial (3.2 to start, as ruled) |
| Player | step back, play or pause, step on, speed (0.25x to 4x), the capture label, a scrub over the 100 captures |
| Frame line | rope max kN, wire max N, trees max utilisation, deviation max mm, heads touching n/46 |
| Show | the eight ticks |
| Colour by | the five choices, one at a time |
| Labels | rope, deviation, contact: ticks |
| Worst | the button that opens the worst tables (ruling: in a left pop-up like the Cable net tab's, one tab a table) |

Ruling: while the Formwork tab is open, the studio's own timeline stands still and the scene shows the capture the player is at; leaving the tab gives the scene back.

## 4. The player

- The captures are decoded once when read, each array a Float32Array, positions taken from millimetres to metres.
- Real time: the raise, finish and hold are played at machine time (30 to 100), the tiling at one quarter a fixed beat (ruling: 0.5 s a quarter at 1x).
- Between two captures the positions are blended linearly for the drawing only; every number shown is the nearer capture's, never a blend.
- The label: `t 60 finish`, `t 98 hold`, `S7 q2`.

## 5. The model on screen

- Net: the members drawn between the capture's node positions, coloured by Colour by; the nodes as now.
- Trees: each member a tube of the ruled diameter at `tree_x`, coloured by utilisation when chosen (a line at 1.0 in its key).
- Heads and push: a head touching is marked, its push an arrow scaled by force.
- Wires and machine: each machine wire from its anchor to its rim node, coloured by wire tension when chosen.
- Anchors: a mark at each.
- Ground contacts: a mark at each node within 1 mm of the ground.
- Skin placed: the bundle's pieces of every row and quarter laid by the capture.
- Designed form: the design shape as a light line net, to read the deviation against.

## 6. Colour, labels, the frame line, the card

- Colour by: one ramp at a time, keyed as the Cable net lenses are (the display pass's legends); deviation keyed against the tolerance as the Sag lens is.
- Labels: the 20 largest of what is chosen, thinned where they crowd, at most 125, as the Cable net tab's.
- The card: a click on a node gives its position, deviation, and for a head its push, then each member at the node with its tension.

## 7. The worst tables

One table a part, each row a part's worst over the whole sequence with the capture it happens at: ropes (member, kN, capture), wires (wire, N, capture), trees (member, utilisation, capture), nodes (node, deviation mm, capture), machines (machine, worst wire N, capture). A header click sorts; a row click moves the player to the capture and the camera to the part.

## 8. Tests and the check on screen

Every new model function under node (the decoding, the frame line, the worst tables, the labels, the keys, the card); the page by its text; the routes are unchanged. On screen before handover, on the real study: the tab at a raise capture, a finish capture, the hold and a tiling quarter, each Colour by, the labels, the card, each worst table.

## 9. His questions

1. One machine a study shared by both tabs (as ruled above), or a Formwork machine of its own?
2. The worst tables in a left pop-up like the Cable net tab's, or in the panel?
3. While the tab is open, should the studio's own animation (the 12 s formwork act from the bundle's frames) give way to the engine's captures everywhere, or only in this tab?
4. The tiling beat: 0.5 s a quarter at 1x, or something else?
5. The formwork run takes its own prestress today (300 N). Should it take the cable net run's computed prestress (part 3) instead, so the two runs share one?
