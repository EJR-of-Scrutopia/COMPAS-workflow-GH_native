# The prestress the form needs, and the nodes that need holding

Date: 2026-10-10. Part 3 of the five the owner set out on 2026-10-09, written overnight on his instruction to go from the display pass straight on to the next spec, plan and build without stopping for approval ("if you finish before 9 then start the next spec, implementation and build"). Every decision below that he has not ruled on himself is marked as a ruling, so he can overturn it when he reads this.

## 1. What he ruled

- Prestress is not a manual input. It is computed from the load: the least pretension that keeps the net inside the tolerance. It is then checked against what the chosen mechanism supplies.
- Show the roof: the most skin the system holds within the tolerance, and how far that scales.
- Holds are column branches, props from below that push and never pull. When the mechanism is not enough, the studio highlights the nodes that need holding and says why: either the chosen mechanism cannot supply the prestress, or no mechanism can (the principal nodes are not enough for any). The studio writes those nodes out for Grasshopper, whose Columns component (part 5) grows the branches. The studio never adds geometry itself.
- The panel answers yes, no or a value. The pop-up's motors table shows what each motor produces and how a change of motor changes the accuracy.

## 2. What stays out

- Playing the raise from the physics engine is part 4. The Formwork run keeps its own prestress until then.
- The Columns component in the Grasshopper plugin is part 5. This part writes the file it will read.
- The timber demand keyed by a skin's density is unchanged.

## 3. What the run already knows

These facts come from the code as it stands (bench/studio/solve_cablenet.py, src/tree_forest_compas/placement.py, stiffness.py). They are why the design below is cheap.

- The prestress enters the analysis in one place only: `first_order_sag`, where each member's stiffness is floored at `prestress / length`. The equilibrium fit (`fit_tension_state`) does not see it.
- So the walk that chooses where to hold the net (`greedy_actuators`, the largest unbalanced force first, twenty nodes a batch) picks the same nodes in the same order whatever the prestress. Only where it stops depends on the prestress.
- The worst sag falls as the prestress rises: a stiffer floor under the same residual.
- One sag solve on the real net takes about 0.1 s, one refit about 0.1 s.

## 4. The run

The run no longer takes a prestress. It takes the ceiling it is designed for (`ceiling_newtons`): the chosen machine's worst wire ceiling from the scored row, or the strongest machine's (section 5) when none is scored, or none.

At the heaviest instant, as now:

1. **The walk.** The walk runs with no stopping line, to its 40 batches or until no unbalanced node is left. Step 0 holds the wire nodes and the column heads alone.
2. **The prestress each step needs.** For every step k, the least prestress that keeps the worst sag within the tolerance with that step's nodes held: found by bisection on the logarithm of the prestress between 1 N and 1 MN, to 1 percent. A step that cannot reach the tolerance even at 1 MN records none. Ruling: the bounds are 1 N and 1 MN, which bracket every wire in the catalogue many times over.
3. **The sag ladder.** With the column heads alone, the worst sag at each prestress of a ladder of 25 values from 100 N to 100 kN, evenly spaced in the logarithm. This is the accuracy column of section 6.
4. **The roof ladder.** For the same ladder, the largest factor on the whole load (skin, net and everything the instant carries) that keeps the worst sag within the tolerance with the column heads alone, by bisection to 1 percent between 0 and 100. Ruling: the whole load is scaled, not the skin alone; the net's own weight is under 1 percent of the skin on the real study.
5. **The design point.** With a ceiling C, the run holds the fewest steps k* whose prestress is at most C, and analyses every instant (as now) with those nodes held at that step's prestress. With no ceiling, k* is 0 and the prestress is step 0's. If no step reaches C, k* is the last step and the prestress is what that step needs (1 MN when even that is beyond the search), so the machine's verdict reads the shortfall. Amended after the final review: the first ruling, designing at C, made the verdict pass at exactly 1.0x for the machine that did not reach.

The document stays `bench.cablenet/2` and gains one block, `needs`:

```
"needs": {
  "stage": "S17",                 the heaviest instant
  "tolerance_mm": 20.0,
  "ceiling_newtons": 772.5,       what the run was designed for, or null
  "steps": [ {"count": 0, "added": [], "prestress_newtons": 41250.0}, ... ],
  "ladder": [ {"prestress_newtons": 100.0, "worst_sag_mm": 2027.7, "roof": 0.01}, ... ]
}
```

`added` is each step's batch as contract node ids, as the placement curve's already are. The demand's `prestress`, `sizing.prestress_newtons` and `held.actuators` are the design point's. A document without `needs` is an older run (section 5's warning).

Ruling: the run's added cost is about 40 refits and some 700 sag solves, of the order of a minute on the real net, on top of today's minute or two. The route's status line says so.

## 5. The menu

| Row | What |
|---|---|
| Needed | the prestress the form needs with its column heads alone: `needs.steps[0]`, N; `more than 1 MN` when step 0 records none |
| Gives | the chosen machine's worst wire ceiling, N a wire, with a mark and a margin: ✓ when it is at least Needed and the run's verdict holds; the margin is the worse of the ceiling over Needed and the verdict's own (amended after the final review, so the menu and the pop-up never mark one machine both ways) |
| Most | the strongest machine's ceiling, N a wire, with a mark against Needed and its name |
| Holds | the nodes the chosen machine needs held: `none`, or `340 nodes, this machine short` (Most is at least Needed), or `340 nodes, every machine short` (Most is below Needed) |
| Roof | the load factor the chosen machine's ceiling gives with the column heads alone, from the roof ladder: `0.4x the skin`, `2.6x the skin` |

The Prestress slider goes. The run sends the ceiling. Warnings stay one line each: `Run again: machine 772.5 N, run 6660.0 N` when the chosen ceiling differs from the run's by more than 1 percent, and `Run again: older analysis, no prestress table` for a document without `needs`. Every figure in the menu and the pop-up is worked out in the browser's model from `needs`, so a change of machine answers at once; only the lenses wait for a run.

Ruling: Holds for a machine is the fewest steps whose prestress it covers, counted in nodes. Interpolating between two steps would claim a precision the batch heuristic does not have.

## 6. The pop-up

- **Mechanism, every motor:** two columns join the table: Holds (the nodes that motor's ceiling needs held, by the rule above) and Sag alone, mm (the worst sag at that ceiling with the column heads alone, from the sag ladder, interpolated in the logarithm of the prestress). That is what a change of motor does to the accuracy.
- **Mechanism, the verdict:** headed Wires hold, with a Nodes held row: it judges the run as designed, with its holds, which the menu's Holds row counts.
- **Graphs:** a fifth graph, the prestress needed against nodes held (`needs.steps`), with the chosen ceiling as a line.

## 7. The Holds lens

A sixth lens, Holds, under the five:
- the nodes the chosen machine needs held, coloured red, every other node grey; the column heads blue;
- a label at each held batch's first node with its step (`+20`), at most the label cap;
- its legend: `holds: 340 nodes, this machine short`;
- the click card gains `Hold: yes` for a node in the set.

The lens reads the set from `needs.steps` for the chosen ceiling, so it follows the machine without a run.

## 8. The holds file for Grasshopper

Export writes `holds.json` beside the other documents, and the exports route offers it for download:

```
{ "schema": "bench.holds/1", "study": "5 sided form", "cut": {...},
  "tolerance_mm": 20.0, "ceiling_newtons": 772.5, "prestress_newtons": 772.5,
  "reason": "machine" | "every machine" | null,
  "nodes": [ {"node": 412, "x": 3.215, "y": -1.002, "z": 2.871, "step": 1}, ... ] }
```

Coordinates are the contract's, in metres, at the finished shape. The nodes are those of section 7 for the chosen machine. A study that needs no holds writes the file with an empty list and a null reason.

## 9. The exports judge the drum as the panel does

The exports' rig ladder still checks the drum with `catalogue.drum_and_travel`, which counts the rope on the drum without the reeving and so under-counts it by the reeve factor. The panel uses `machine.travel`. The ladder takes `machine.travel` with each wire's own take-up and reeving, so the two agree. This closes the item left open in part 2.

## 10. Tests and the check on screen

- The walk's prestress table, the two ladders and the design point on a small net, against brute force: the prestress found is within 1 percent of the least that a fine sweep finds, and the sag at it is within the tolerance.
- The route sends and keeps the ceiling; an older document reads as one.
- Every new model function under node: the answers, the holds set for a ceiling, the two pop-up columns, the graph.
- The lens and the card by their text, as the display pass's are.
- The holds file's schema and its nodes against the demand.
- The ladder's drum check against `machine.travel` on the Tiny study.
- On screen, before handover: the real 5 sided form run again, then the check of the display pass with the Holds lens added, every picture looked at.
