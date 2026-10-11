# Across tendons: the pull toward the principal lines

Spec, 2026-10-11. Builds on the one Cable net tab (`2026-10-11-one-cable-net-tab-design.md`, merged to main f317a4e).

## 1. What he asked for, and what he ruled

Looking at the net's free edges on the 5 sided form, he wrote: "we pull on the mechanism down the length of one set of wires, like intended, but we have completely neglected the pull towards the principle line. so we actually are meant to have another set of mechanisms pulling the wires in ... this is another set of mechanisms that reel the mechanisms in on the other wires also." The mechanism is not decided: "it wont be pulley ... i already like the idea of pneumatic movement down the axial nodes which hold form, but it may not be strong enough i dont know, that will come after. but what is worth doing right now is adding in the pull towards principle lines along those axial wires." And: "we should also account for the force in that direction and show it as a visualisation. one for axial one way, one for the other and then for both."

His answers on 2026-10-11:

- The pull is reeled to hold the form: each line held at its length, the run reporting the pull it needs, so the mechanism can be sized later.
- It pulls on a tendon along the line: a cable from the free edge back along the across line through a ring at each node, reeled at the column head.
- It works through the raise, not only from the hold on.
- It goes into the engine as a tendon element, not as a pinned edge or a pre-tension.
- The design's three sections (the run, what the tab shows, reruns and checks): "Yes" to each.

Out of scope: the tendons' mechanism, its strength and its cost; pneumatics; friction at the rings.

## 2. The lines

The across lines are found from the net as the old hold search found them: the quads sorted into two families from the principal lines out (an edge joining two head nodes runs along; across a quad the opposite edge keeps its family and a side edge takes the other), and each line followed across from its column head node to the free edge. On the 5 sided form that is 95 lines, each of 10 segments, through 950 nodes; the rim's 105 wire nodes lie on the other family.

A net whose quads do not sort into the two families, or that has no principal line, runs without tendons, and the tab says so in one line: "No tendons: this net's lines do not run across from a principal line".

## 3. The tendon

- One tendon a line. Its path is the line's nodes from the column head to the free edge, in order.
- It slides through a ring at each node of its path with no friction, so its tension is one figure along its whole length. It takes tension only.
- Its axial stiffness is the chosen net rope's EA.
- Its reel sits on the column head; the tendon's pull at the head goes into that head's tree, so the trees' forces and utilisation include it.
- The reel holds the length of the tendon's path:
  - from the layout and through the raise, to the line's length in the animation's frame at that moment, interpolated between the frame before and the frame after as the heads are;
  - from the hold on, through the rods' jacking and the tiling, to the line's length at the design;
  - never shorter than the line's ropes unstretched (amended 2026-10-11, found running the real study: early in the raise the animation draws the across lines at as little as 0.82 of their design length, shorter than their ropes, and a reel holding that bunched a line's nodes until two met).
- It holds it to within 1 mm, as a stiff servo. The tension that takes is the run's result.

A tendon's force on its nodes: at the free edge, its tension along the last segment toward the head; at each ring, its tension along both its segments, pressing the node toward the inside of the line; at the head, its tension along the first segment, taken by the head.

## 4. What the run keeps

- The document gains `tendons`: for each line its column head (the tree head's index), its side (as `net.sides` numbers them), its path of nodes and its target length at the design, mm. Null for a run without tendons, with the reason when the net could not take them.
- Each capture gains `tendon_tension`, N a tendon, packed as the other arrays are.
- The summary gains `tendon_tension_max_n`.
- The run's options gain `tendons` (true or false, the switch).
- The saved state at the hold carries each tendon's reel, so a rods-only rerun starts there with the tendons as they were.

## 5. The answer

One row more under the five of the one tab:

```text
Pull in   12,345 N   worst tendon, head 12 side 3, at t 76 finish
```

- Pull in: the largest tendon tension anywhere in the run, its line named by its column head and side, and the capture. A click takes the player there and the camera to that line.
- No Have and no Missing: the mechanism is not chosen.
- A run without tendons has no Pull in row.

## 6. What the tab shows

- Colour by: Wires, Along, Across, Both, Offset, Trees, Off.
  - Along: the family the rim wires pull, down the arms, each member by its rope tension; the across members drawn thin and grey.
  - Across: the family pulled in toward the principal lines, each member by its rope tension plus the tension of the tendon beside it, the whole force in that direction; the along members drawn thin and grey.
  - Both: every member by its whole force, as Across counts it for the across members and the rope tension for the along. It replaces Ropes.
  - Each scale runs from nought to the run's largest. Along and Both mark the rope's working load; Across marks no limit.
- Values on the model: the worst five and the worst a side, as now, in kN.
- Show gains a Tendons chip: each tendon drawn along its line a little proud of the net, with a small reel at its column head, in the Across or Both colours and white otherwise.
- The frame line gains "Pull in max", the largest tendon tension at that capture.
- A node's card gives its tendon's tension when it is on a line.
- The pop-up's Graphs tab gains a third graph: the worst tendon tension at every capture, with no limit line.
- Weakest judges the ropes by their own tension against their working load, as now; a tendon has no limit to be over.
- The Cost tab is unchanged; the tendons are not priced.

## 7. Reruns and older runs

| Change | What happens |
|---|---|
| The Tendons switch (on by default) | A full run, started one second after the last change, as a mechanism change is. |
| Holds a side | A run from the saved state at the hold, with the tendons' reels in that state. |
| Mechanism, wires a motor | A full run, as now. |

A run made before the tendons reads as before: Across shows the across ropes alone and there is no Pull in row. With the switch on, such a run is out of date: "Run again: tendons changed".

## 8. Tests and checks

- Engine, on a small net with a principal line:
  - each tendon's path is held to its target length within 1 mm, through the raise and from the hold on;
  - each node of a line is in balance with its ring's push, and the free edge is pulled toward the head;
  - the tendon's pull reaches the tree at the head;
  - a run from the saved state at the hold matches a full run with tendons to the bit;
  - a net without a principal line runs without tendons and says why.
- Server: the run's request carries the tendons and the switch; the document carries them as section 4 says.
- Page: Along, Across and Both colour the right members with the right forces; the Pull in row and its click; the Tendons chip draws its tendons; the frame line's Pull in max; the third graph; "Run again: tendons changed".
- On screen, before he is told it is ready: the real 5 sided form with tendons at nought and at three rods a side, and without tendons; every view looked at (Along, Across, Both, the chip, the graphs); and a new video.

## 9. Rulings in this spec

- The tendon's EA is the chosen net rope's. Cost if wrong: one figure.
- No friction at the rings. Cost if wrong: tensions that fall along a real tendon.
- The reel holds its length to within 1 mm. Cost if wrong: a looser hold.
- Through the raise the target is the frame's line length, interpolated between frames as the heads are, and never shorter than the line's ropes unstretched (the amendment of section 3). Cost if wrong: a different reel schedule.
- Lines are named by their column head and side. Cost if wrong: a name.
- Across marks no limit; Weakest judges ropes only; the Cost tab leaves the tendons out, all until their mechanism is chosen. Cost if wrong: three lines.
- A net without a principal line runs without tendons rather than being refused. Cost if wrong: a refusal instead.
- The switch is on by default. Cost if wrong: one default.
