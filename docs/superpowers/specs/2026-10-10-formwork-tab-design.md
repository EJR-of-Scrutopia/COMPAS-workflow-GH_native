# The Formwork tab: the raise played from the physics engine

Date: 2026-10-10. Part 4 of the five the owner set out on 2026-10-09. Drafted overnight, finished on his word of 2026-10-10 ("let's continue and finish this new spec, give me the questions and build it, then we go from there"). Every choice he has not made himself is marked as a ruling. He answered the five questions of section 13 the same day, each with the recommended choice, and the answers are folded in where they fall.

## 1. What he ruled

- The Formwork tab is its own tab. The Cable net tab keeps its own run.
- In the tab: Run formwork analysis; the mechanism the Cable net tab chose; a player over the captures (step, play, speed, a label such as `t 60 finish` or `S7 q2`).
- SHOW ticks, one a part: net, trees, heads and their push, wires and machine, anchors, ground contacts, skin placed, designed form.
- COLOUR BY, one at a time: rope tension N, deviation mm, tree utilisation, wire tension N, off; with a keyed scale.
- LABELS on the model for what is in view: rope kN, deviation mm, contact N.
- A frame line: rope max, wire max, trees, deviation max, heads touching n/46.
- A click on a node: its numbers and its members' tensions.
- WORST tables (ropes, wires, trees, nodes, machines) that sort, and fly to the row.
- No prose. The engine as real as possible, computed once in the background, the captures replayed; no exaggeration slider.
- His answers of 2026-10-10: the formwork run takes the cable net run's design prestress; one machine a study, shared by both tabs; the captures replace the studio's formwork act only in this tab; the raise at the studio's own rate and 0.5 s a tiling quarter; the worst tables in a left pop-up.

## 2. What stays out

- The mechanism itself. On 2026-10-10 the owner judged that the method needs perimeter holding as well as the machines and the trees, and that the mechanism goes back to the drawing board so that any design can be built, anticlastic or not. This part plays the engine as it is; it does not change how the net is held.
- Part 3's holds are not props in the engine. The engine holds the net by its rim wires and the tree heads only, so the Formwork tab shows the net without the holds the Cable net tab asks for.
- The Columns component in Grasshopper is part 5.

## 3. What is there today

From the code at 889a3e3 (bench/studio/solve_formwork.py, formwork_sim.py, src/tree_forest_compas/formwork_sequence.py, app.py, studio.js):

- The engine writes `bench.formwork-sim/1`: `net` (nodes, edges, the design shape, rest lengths, the cut force), `rim` (wires with anchors, the way each runs in, stiffness, reeving, route, machines), `trees` (members, feet, heads, the tube), `captures` and a `summary`.
- A capture carries `phase`, `time` (machine time; none while tiling), `row` and `quarter`, the node positions `x` [n, 3] mm, member `tension` [m] N, `deviation` [n] mm (from where the frame puts each node during the raise, from the design while tiling), `head_push` [heads, 3] N, `anchor_force`, `wire_tension`, `reel`, `let_out` [rim], `tree_x`, `tree_axial`, `tree_utilisation` [members].
- Arrays are packed as base64 little-endian float32 (`{shape, f32}`). Nothing in the browser decodes them yet.
- The real 5 sided form (tile cut, 300 N, one wire a motor) has 1101 nodes, 2000 members, 105 wires on 15 machines, 66 tree members on 16 feet and 46 heads. Its file is 4.3 MB: 100 captures (15 raise, 15 finish, 6 hold, then 64 tiling quarters over rows S1 to S17), 112 s of engine time. Its summary: deviation at the end of the raise 1,640 mm, at the end of the tiling 1,746 mm, worst wire 36,459 N, trees 2.30 of capacity.
- Machine time is the build's own 0 to 100 (reel 0 to 30, raise 30 to 60, finish 60 to 90, hold 90 to 100), not seconds. The studio plays 0 to 100 in its 12 s formwork act from the bundle's `bench.frames/1` frames.
- `POST /api/studies/{export}/formwork/run` runs it (about 110 s at one wire a motor); `GET .../formwork/sim` serves the file; `GET /api/runs/{id}` reports progress as capture n of 100.
- The studio draws nothing from the captures.
- Not stored: the skin placed, the ground contacts. The engine knows both (each quarter's faces in formwork_sim.rows_from; the nodes resting on the ground in its contacts).

## 4. The document gains three fields

Ruling: so the tab can draw the skin and the ground contacts from the run rather than guess them:
- `net.faces`: the cut mesh's faces, each a list of node ids;
- each tiling capture's `added_faces`: the faces its quarter placed;
- each capture's `ground`: the nodes the ground holds at that instant.

The schema stays `bench.formwork-sim/1`. A document without these is an older run: the skin and ground ticks draw nothing and the warning line says `Run again: older formwork run`.

## 5. The tab

A ninth button in the rail, Formwork, after Cable net, and a `formwork-section` in the panel:

| Row | What |
|---|---|
| Run formwork analysis | the button, its status line and progress (capture n of 100) |
| Machine | the mechanism the Cable net tab chose, one line (his answer: one machine a study), and the prestress the run takes (section 6) |
| Wall | the tree tube's wall, mm, a dial (3.2 to start, as ruled) |
| Player | step back, play or pause, step on, speed (0.25x to 4x), the capture label, a scrub over the captures |
| Frame line | rope max kN, wire max N, trees max utilisation, deviation max mm, heads touching n/46 |
| Show | the eight ticks |
| Colour by | the five choices, one at a time |
| Labels | rope, deviation, contact: ticks |
| Worst | the button that opens the worst tables |
| Warnings | one line each: no run yet, the run failed, an older run, the run's machine or prestress not the chosen one |

## 6. The run

The tab's button posts the study's cut options (as the Cable net run does), the chosen wire, wires a motor and pulleys, and the wall. Progress polls `/api/runs/{id}`; when it is done the tab fetches the file and goes to the first capture. The run takes about two minutes on the real study, and the status line says so.

The prestress (his answer to question 5): the route reads the design prestress from the cable net run of the same cut (the demand's `prestress`, part 3's design point), so the net is cut for what the chosen machine holds. With no cable net run, the route refuses: `Run the cable net analysis first`. The run's options record the prestress and that it came from the cable net run. Ruling: a body that names a prestress is still taken, for scripts and tests; the tab never sends one.

## 7. The player

- The captures are decoded once when read, each array a Float32Array, positions taken from millimetres to metres.
- Timing at 1x (his answer to question 4): the raise, finish and hold at the studio's own rate, 12 s for machine time 0 to 100, so 8.4 s from 30 to 100; the tiling at 0.5 s a quarter. About 40 s in all on the real study.
- Between two captures the positions are blended linearly for the drawing only; every number shown is the nearer capture's, never a blend.
- The label: `t 60 finish`, `t 98 hold`, `S7 q2`.
- His answer to question 3, with a ruling on how: while the Formwork tab is open, the studio's timeline stands still, its own net, shell, trees and lenses are hidden, and the scene shows the capture the player is at; leaving the tab gives them back as they were.

## 8. The model on screen

Ruling: the tab draws its own objects in one group, built from the document, moved from the captures, removed when the tab closes. The studio's objects are not reused.

- Net: the members as lines between the capture's node positions, coloured by Colour by; the nodes as small points.
- Trees: each member a cylinder of the tube's diameter (60.3 mm) between its two tree nodes, coloured by utilisation when chosen.
- Heads and push: a head touching its node marked, its push an arrow scaled by force.
- Wires and machine: each rim wire from its node along the way it runs into its anchor, 300 mm, coloured by wire tension when chosen; the machine as the studio already draws it.
- Anchors: a mark at each.
- Ground contacts: a mark at each node the ground holds.
- Skin placed: the faces placed by the capture, drawn on the net where the capture has it, so the skin rides the net.
- Designed form: the design shape as a light line net, to read the deviation against.

## 9. Colour, labels, the frame line, the card

- Colour by: one ramp at a time, keyed as the Cable net lenses are (the display pass's legend). Ruling: each scale runs from nought to the largest value over the whole run, not the capture's, so a colour is the same newtons in every capture. Deviation is banded against the Cable net tab's tolerance (within, near, over) as the Sag lens is. Tree utilisation is banded at 1.0.
- Labels: for each ticked kind, the 20 largest at the capture, thinned where they crowd, at most 125 on screen, as the Cable net tab's are. Rope kN at a member's midpoint, deviation mm at a node, contact N at a touching head.
- The frame line: rope max kN, wire max N, trees max utilisation, deviation max mm, heads touching n of the heads, all at the nearer capture.
- The card: a click on a node gives its position, deviation, on the ground or not, for a head its push, for a rim node its wire's tension, then each member at the node with its tension. It follows the node as the player moves.

## 10. The worst tables

In a left pop-up like the Cable net tab's (his answer to question 2), opened by the Worst button, one tab a part. Each row is a part's worst over the whole sequence with the capture it happens at:
- ropes: member, kN, capture;
- wires: wire, N, capture;
- trees: member, utilisation, capture;
- nodes: node, deviation mm, capture;
- machines: machine, worst wire N, capture.

The 50 worst rows of each. A header click sorts; a row click moves the player to the capture and turns the camera onto the part.

## 11. Refusals

One line each, no prose: `No formwork run: Run formwork analysis`; the run's own failure reason as the server gives it; `Run again: older formwork run`; `Run again: machine X, run Y` when the chosen wire, wires a motor or pulleys differ from the run's options; `Run again: prestress X N, run Y N` when the prestress of question 5 differs from the run's by more than 1 percent.

## 12. Tests and the check on screen

- The engine: the document carries `net.faces`, each tiling capture's `added_faces` (together the faces the plan places), and each capture's `ground` (the laid-out net on the ground at the first capture, fewer once raised).
- Every new model function under node: the decoding, the timing and the label, the frame line, the worst tables and their sort, the label targets, the keys, the card, the warnings.
- The page by its text: the rail button, the section, the ticks, the pop-up.
- On screen before handover, on the real study after a fresh formwork run: the tab at a raise capture, a finish capture, the hold and a tiling quarter; each Colour by; each show tick; the labels; the card; each worst table and a row's fly-to. Every picture looked at.

## 13. His questions, answered 2026-10-10

Each answered with the recommended choice.

1. Machine: one machine a study shared by both tabs (recommended: the tabs never disagree), or a Formwork machine of its own?
2. The worst tables in a left pop-up like the Cable net tab's (recommended), or in the panel?
3. While the tab is open, the engine's captures replace the studio's 12 s formwork act only in this tab (recommended), or everywhere once a run exists?
4. The beat: the raise at the studio's own rate and 0.5 s a tiling quarter (recommended, about 40 s), every capture the same 0.4 s, or something else?
5. The formwork run takes 300 N today. Should it take the cable net run's design prestress (part 3, recommended), the prestress Needed with the column heads alone, or stay at 300 N?
