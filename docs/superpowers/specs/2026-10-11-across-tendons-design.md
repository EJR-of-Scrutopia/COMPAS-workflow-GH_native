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

Amended later on 2026-10-11, after the first run on the real study (section 10). Held at their design lengths the tendons carried 36 N and changed nothing: each across line had already fallen straight from its head to its free edge at its full length, with no slack to take in. He saw the section and wrote: "I am not convinced that you can't reel in from both sides keeping the symmetry of the shape while pulling in. I suspect this also won't work to recreate a perfect form, but will decrease the total force on the system maybe and offer slightly more shape even if it just produces straight lines instead of curvature", and "I think we still need to show it, just to get the data on the amount of newtons it will add to the system, whether it alleviates or decreases the amount so that a mechanism could feasibly work". His answers then:

- The pull is a force he dials, the same on every tendon, from both sides of each principal line, replacing the length hold; neighbouring rings stop against each other, so a line pulled in past its ropes gathers at its edge instead of passing through itself.
- It pulls from the raise on, each line once that line is off the ground ("Build, with lift-off start").

Out of scope: the tendons' mechanism, its strength and its cost; pneumatics; friction at the rings.

## 2. The lines

The across lines are found from the net as the old hold search found them: the quads sorted into two families from the principal lines out (an edge joining two head nodes runs along; across a quad the opposite edge keeps its family and a side edge takes the other), and each line followed across from its column head node to the free edge. On the 5 sided form that is 95 lines, each of 10 segments, through 950 nodes; the rim's 105 wire nodes lie on the other family.

A net whose quads do not sort into the two families, or that has no principal line, runs without tendons, and the tab says so in one line: "No tendons: this net's lines do not run across from a principal line".

## 3. The tendon

- One tendon a line. Its path is the line's nodes from the column head to the free edge, in order.
- It slides through a ring at each node of its path with no friction, so its tension is one figure along its whole length.
- Its reel sits on the column head and pulls it in with the dialled tension, the same on every tendon (amended: it no longer holds a length). The tendon's pull at the head goes into that head's tree, so the trees' forces and utilisation include it.
- Two neighbouring rings stop against each other 20 mm apart, pushing back 100,000 N a millimetre closer, so a line pulled in past its slack ropes gathers at its free edge.
- The net is laid out unpulled. From the raise on, each line pulls once none of its nodes rests on the ground; a line still lying there pulls nothing (found running the real study: a big pull dragged lines still on the ground along it).
- A pulled net is given 3,000 Newton steps rather than 300: where a pull slackens a line's ropes its rings are held along it only by the pull, and Newton settles there slowly.

A tendon's force on its nodes: at the free edge, its tension along the last segment toward the head; at each ring, its tension along both its segments, pressing the node toward the inside of the line; at the head, its tension along the first segment, taken by the head.

## 4. What the run keeps

- The document gains `tendons`: the pull, N, and for each line its column head (the tree head's index), its side (as `net.sides` numbers them) and its path of nodes. Null for a run without a pull; `tendons_reason` says why when the net could not take them.
- `net.families`: each edge's family, "along" or "across", null for a net that does not sort.
- Each capture gains `tendon_tension`, N a tendon: the pull, or nought for a line still on the ground. Packed as the other arrays are.
- The summary gains `tendon_pull_n`.
- The run's options gain `pull_in`, N.
- The saved state at the hold carries the run to there, so a rods-only rerun starts with the tendons as they were.

## 5. The answer

One row more under the five of the one tab:

```text
Pull in   3,000 N a tendon   95 tendons, 285,000 N in all
```

- Pull in: the dialled pull, the number of tendons, and what they put into the column heads in all.
- No Have and no Missing: the mechanism is not chosen.
- A run without a pull has no Pull in row.

## 6. What the tab shows

- Colour by: Wires, Along, Across, Both, Offset, Trees, Off.
  - Along: the family the rim wires pull, down the arms, each member by its rope tension; the across members drawn thin and grey.
  - Across: the family pulled in toward the principal lines, each member by its rope tension plus the tension of the tendon beside it, the whole force in that direction; the along members drawn thin and grey.
  - Both: every member by its whole force, as Across counts it for the across members and the rope tension for the along. It replaces Ropes.
  - Each scale runs from nought to the run's largest. Along and Both mark the rope's working load; Across marks no limit.
- Values on the model: the worst five and the worst a side, as now, in kN.
- Show gains a Tendons chip: each tendon drawn along its line a little proud of the net, with a small reel at its column head, in the Across or Both colours and white otherwise.
- The frame line gains "Pulling", the tendons pulling at that capture out of all, and "At the stop", the rings closed to the stop.
- A node's card gives its tendon's tension when it is on a line.
- The pop-up's Graphs tab gains a third graph: the tendons' pull in all at every capture, N, with no limit line.
- Weakest judges the ropes by their own tension against their working load, as now; a tendon has no limit to be over.
- The Cost tab is unchanged; the tendons are not priced.

## 7. Reruns and older runs

| Change | What happens |
|---|---|
| Pull in, a dial from 0 to 30,000 N a tendon in steps of 100, 0 (none) by default | A full run, started one second after the last change, as a mechanism change is. |
| Holds a side | A run from the saved state at the hold, with the tendons as they were there. |
| Mechanism, wires a motor | A full run, as now. |

A run made before the tendons reads as before: Across shows the across ropes alone and there is no Pull in row. A run whose pull is not the dial's is out of date: "Run again: pull changed".

## 8. Tests and checks

- Engine, on a small net with a principal line:
  - a tendon pulls its free edge in with its tension, checked by hand, and its head takes it;
  - a ring pulled past its slack ropes stops 20 mm from the next;
  - each ring is pressed toward the inside of its line;
  - Newton and relaxation agree with a tendon;
  - the net is laid out unpulled, and each line pulls once it is off the ground;
  - the tendon's pull reaches the tree at the head;
  - a run from the saved state at the hold matches a full run with tendons to the bit;
  - a net without a principal line runs without tendons and says why.
- Server: the run's request carries the tendons and the pull; the document carries them as section 4 says.
- Page: Along, Across and Both colour the right members with the right forces; the Pull in row; the Tendons chip draws its tendons; the frame line's Pulling and At the stop; the third graph; "Run again: pull changed".
- On screen, before he is told it is ready: the real 5 sided form at no pull, at 3,000 N and at 3,000 N with three rods a side; every view looked at (Along, Across, Both, the chip, the graphs); and a new video.

## 9. Rulings in this spec

- No friction at the rings. Cost if wrong: tensions that fall along a real tendon.
- The stop: 20 mm between neighbouring rings, 100,000 N a millimetre. Cost if wrong: where a line gathers.
- A line pulls once none of its nodes rests on the ground. Cost if wrong: a different start to the pull.
- 3,000 Newton steps for a pulled net. Cost if wrong: slower failures.
- The dial runs from 0 to 30,000 N a tendon in steps of 100, 0 by default: every pull to 30,000 N ran on the real study. Cost if wrong: one range.
- Lines are named by their column head and side. Cost if wrong: a name.
- Across marks no limit; Weakest judges ropes only; the Cost tab leaves the tendons out, all until their mechanism is chosen. Cost if wrong: three lines.
- A net without a principal line runs without tendons rather than being refused. Cost if wrong: a refusal instead.

## 10. What the runs found

The real 5 sided form, tiled, with the strongest mechanism, 2026-10-11.

Held at their design lengths, as first specified, the tendons carried 36 N at most and the form was unchanged: every across line had already fallen straight from its column head to its free edge at its full length, the edges about 900 mm below and 600 mm inside their design points.

Pulled with a dialled tension on all 95 tendons, each line pulling once off the ground:

| Pull a tendon | Rim's worst wire | Trees | Rings at the stop | At the hold: worst / mean offset, edge drop | End of tiling: worst / mean offset, edge drop |
|---|---|---|---|---|---|
| none | 171,305 N | 7.35 | 0 | 1,328 / 611 mm, 564 mm | 1,407 / 618 mm, 534 mm |
| 300 N | 171,305 N | 7.35 | 0 | 866 / 358 mm, 285 mm | 1,369 / 611 mm, 529 mm |
| 1,000 N | 171,305 N | 7.37 | 35 | 831 / 340 mm, 258 mm | 1,186 / 515 mm, 429 mm |
| 3,000 N | 171,305 N | 7.40 | 90 | 822 / 337 mm, 230 mm | 976 / 406 mm, 297 mm |
| 10,000 N | 171,305 N | 7.53 | 90 | 821 / 338 mm, 173 mm | 877 / 359 mm, 195 mm |
| 30,000 N | 171,305 N | 8.14 | 145 | 828 / 353 mm, 80 mm | 848 / 360 mm, 88 mm |

The pull buys shape, with diminishing returns past about 10,000 N; about 350 mm of mean offset stays, the arch's lost curvature, which a pull along the line does not restore. The rim's worst wire is untouched (it comes in the raise, before the edges leave the ground), and the trees take more as the pull grows.

With the rods as well (checked on screen on the built tab, three rods a side): the worst offset at the end of the tiling is 893 mm with no pull and 463 mm at 3,000 N a tendon, against 1,407 mm and 976 mm without the rods.

Corrected the same evening: the rim's worst wire is not untouched because it comes before the edges leave the ground. All 95 lines pull at its capture (t 60, the finish; the first lines pull from t 44). It is untouched because geometry sets it: wire 3-1-3's rim node (692) is joined by one rope (edge 1372) straight to a column head's node (691), and with the head tied to its tree and the rim node held on its anchor with whatever it takes, that rope is stretched from 879.7 mm to 994.8 mm by where the tree has put the head, and carries 235,371 N whatever the net does; the wire takes 171,305 N of it along its line. The same figure, to the newton, came from every run: tile or timber, no pull or 8,600 N, no rods or 3 or 10 a side. Needed is therefore a measure of the trees' path against that rope's length, not of any mechanism.
