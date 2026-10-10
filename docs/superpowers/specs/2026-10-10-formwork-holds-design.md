# Holds in the formwork engine: whole net lines, evenly spaced, to the tolerance

Date: 2026-10-10. Option 1 of the four the owner was offered after the tied-head run showed the net draping between the principal lines ("lets add in option 1 for now"). His answers of the same day are folded in; every other choice is marked as a ruling.

## 1. What he ruled

- The principal line nodes are an absolute must: the net is tied to the column heads (engine de8b584). The only question is whether additional nodes are needed, and the engine says they are: every one of the 901 inner nodes of the 5 sided form is dome-like, and a tension net cannot hold a panel that bulges up between its supports at any prestress (769 mm at 33 kN).
- The extra holds are uniform, not random: whole net lines parallel to the principal lines, evenly spaced, the same in all five arms, added until the tolerance (20 mm) is met.
- The search: the open edges alone, then every 5th line, then every 2nd, then every line, stopping at the first that meets the tolerance.
- The holds go in after the raise: once the net is up (the hold, machine time 100) each prop is put under its node and jacked to the design height, 25 mm at a step.
- A hold is a GRIPPED ROD (his ruling of the same evening, after the push-only finding in section 3): it grips its node like a column head, in every direction, from the jacking on, and never lets go. It is a straight member along its own force: a strut from the ground where it pushes, a tie down to the ground where it pulls. Getting the rods to the right angle is part of solving the form.
- Pressure (cushions under the panels, pressure lines, a shaped inflated surface) waits on his own research: "we will need to produce papers, studies and more on this".
- Option 4 (saddle-shaped panels) is the more sensible path for the method in the long run, and pressure and rods are to be explored; this part does option 1 only.

## 2. The lines

The net's quads are sorted into two families from the principal lines outwards: an edge joining two head nodes runs along; across a quad an opposite edge keeps its family and a side edge takes the other. A node's band is the number of steps across, along across edges only, to the nearest head node. On the 5 sided form there are no conflicts and the bands are exact: the principal lines are band 0 (46 heads), bands 1 to 10 hold 95 nodes each (19 in each arm, on both sides of its spine), and band 10 is the open edges, the perimeter arches between the arms. The rim's 105 wire nodes belong to no band.

Holds at spacing s are every node in a band that is a multiple of s. The spacings tried are the divisors of the widest band, here 10, 5, 2 and 1 (95, 190, 475 and 950 holds), so the held lines are evenly spaced from the principal line to the edge. Ruling: a net whose quads do not sort into the two families (a face that is not a quad, lines that cross themselves, or no two head nodes joined) is refused with one line: the holds need a quad net in which every line runs parallel to a principal line. Amended while building: the per-arm size check was dropped, since arms cannot be told apart from the quads alone; the 5 sided form's bands are checked equal (95 each) by the on-screen step.

The bands are worked out in plain Python in bench/studio (formwork_sim.py), from the cut mesh's faces and the formwork document's heads.

## 3. The engine

The model gains `holds`, a list of net nodes, empty by default. After the last frame of the raise the reels hold as now; then, if there are holds, every hold takes its node from where it hangs to its design point in steps of at most 25 mm (SUB_STEP_MM), gripping it in its cradle while it lifts it, and the net settles at every step; and the hold keeps its grip from then on, through the tiling, like a column head: its node is tied (Contacts.tied) and never let go. Ruling: the jack is guided straight from the node to its design point, plan position included.

Amended twice while building, each time by the real study (the 5 sided form, tile cut, 723.4 N):
- Jacked push-only from where the net hangs, 70 of the 95 edge props were pulled off their nodes at every step and the net never rose. So a jack grips its node while it lifts it.
- Gripped for the jacking and push-only after, the props did not hold the form at any spacing. Once the inside is lifted the net pulls the low edges up (up to 443 N a node) and pulls some inner props (40 of 380 at every 2nd line, to 182 N); the props also hold the net sideways (median 219 N, up to 508 N). When the pulled ones let go the sideways hold goes with them and the rest slide out of their cradles: 50 of 380 still pushed. Gripped for good, as he ruled, every 2nd line gives 295 mm worst and 10 mm mean (976 of 1101 nodes within 20 mm) and every line meets the tolerance; 135 of the 475 holds at every 2nd line pull, and the force leans 41 degrees from vertical at the median, 70 at most.

One capture is taken when the jacking is done: phase `holds`, machine time 100. The tiling follows with the holds in place. Every capture gains `hold_push` [holds, 3], the force each hold puts on its node (up where it pushes, down where it pulls), nought before the jacking. The document's net block gains `holds`, the list of held nodes.

## 4. The search

The formwork run (POST .../formwork/run) takes `holds`: `search` (the default) or `none`, and `tolerance_mm` (the Cable net tab's dial; 20 when left out). With `search`, the run tries each spacing in turn (the open edges, every 5th line, every 2nd, every line), one engine run each, and stops at the first whose worst deviation, over the `holds` capture and every tiling capture, is within the tolerance. Ruling: every node counts, the held ones included. If no spacing meets it, the every-line run is kept and the tolerance is said not to be met.

The document keeps the run that was chosen and gains a `holds` block:

```
"holds": { "spacing": 5, "bands": [5, 10], "count": 190, "tolerance_mm": 20.0, "met": true,
           "tried": [ {"spacing": 10, "count": 95, "deviation_max_mm": 412.3}, ... ] }
```

Progress says which try and which capture: `every 5th line: capture 37 of 101`. Ruling: four engine runs at about 70 s each make the search a few minutes on the real study; the status line says so.

## 5. The tab

- A Holds row under the machine: `Search to the tolerance` or `None`, sent with the run.
- The result, one table: the spacing kept, the holds, the worst deviation with its mark against the tolerance, then each try's spacing, holds and worst deviation.
- The table goes on from the capture after the jacking: `Struts` (holds that push), `Ties` (holds that pull), `Push max` and `Pull max` in N, `Lean max` in degrees from vertical.
- Show gains a tick, Holds: each hold drawn as a thin rod along its force at the capture after the jacking (the angle it is set at), its foot on the ground: a strut runs down from its node against its push, a tie runs down from its node along its pull. Ruling: a rod leaning more than 80 degrees is drawn at 80, so a force near level does not run off the picture; the table gives the true lean. Green while its hold pushes, blue while it pulls, grey while it carries nothing.
- The frame line gains `Struts n/N` and `Ties n/N` when the run has holds.
- The card says `Hold: strut n N` or `Hold: tie n N` for a held node.
- The capture after the jacking is labelled `t 100 holds`. It comes JACK_SECONDS (2 s at 1x) after the hold, which is also at machine time 100, so the player shows the jacking and reaches both (amended after the final review: the two shared one second and the hold could not be reached).
- While a search runs, the status line names the try beside the counter (`every 5th line: capture 37 of 101`), and starts with "a few minutes, one run a spacing tried".
- A hold's force under 0.01 N (the engine's own rest) counts as carrying nothing: grey, upright, neither strut nor tie.
- The recording's caption carries `Struts n/N` and `Ties n/N` like the frame line.

## 6. Tests

- The bands on a small quad net with one principal line: each node's band, the open edge as the widest band, the spacings and their holds; a net that does not sort is refused.
- The engine on the toy: the holds jacked to their design points and gripped there from then on, never let go; a strut and a tie side by side (up is push); the `holds` capture and `hold_push` in every capture.
- The document's `holds` and `hold_push`; an older document without them still reads.
- The search with a stand-in engine: stops at the first spacing that meets the tolerance; keeps the every-line run when none does; `none` runs once with no holds.
- The tab's model under node: the result table, the frame line, the card, the label, the recording's caption; the hold and the capture after the jacking each reachable in the player; the drawing of the rods under node with three.js; the page by its text.
- The run: a search through to the written document, its holds never a head or a wire node.
- On screen: the real study's search, the tab at the holds capture and the last tile, the props ticked, and a new recording.
