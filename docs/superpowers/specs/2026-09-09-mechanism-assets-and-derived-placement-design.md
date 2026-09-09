# Mechanism assets and derived placement

**Status:** design, awaiting Param's review. Written overnight on his
instruction: "right im going to bed you take over the fixes and the new
placement mechanism."

## 1 The problem

1.1 A study's mechanism document places its own machines. That placement
is authored in Grasshopper, and it does not survive a changing form.
Param: "the anchors dont play fair in my script with many chnaging
forms."

1.2 On his export of 2026-09-09 at 01:50 the placement stage produced
nothing at all: `instances: 0`, `wires: 0`, `anchors: 0`, with every body
present. The studio drew the machine once where its body was authored,
which is the only honest reading of a document with no placements, and he
asked why he was seeing one machine.

1.3 He also wants a mechanism to stop being a property of one study and
become a thing he can choose: "the mechanism itself wants to become an
asset, so add to import the mechanism as a drop down selection, so if i
export any other types of mechanisms, we can pick and chose or you can
auto chose the best one. this will likely be ones with different wire
configs to deal with un even numbers of wires."

1.4 These are one feature, not two. Borrowing a mechanism from another
study necessarily means placing it on this one, because a borrowed
document's placements belong to the study it came from.

## 2 What is already true

2.1 Measured on `2 Sided Vault-form.json`, and the whole design rests on
these numbers rather than on inference:

| Fact | Value |
| --- | --- |
| Net vertices | 441 |
| Net edges | 800 |
| Supports (`equilibrium.resolvedSupportNodeIds`) | 42 |
| Edges joining two supports | **0** |
| Nearest-neighbour spacing among supports | 0.1500 m, min = median = max |
| Groups at a 0.45 m join limit | **2, of 21 each** |
| Straightness of each group | 0.0000 m off its own line |
| Length of each group | 3.000 m along (0, 1) |
| Distance between group centres | 16.000 m |
| Separation margin | 36x the join limit |

2.2 Twenty-one supports a row divided by seven spools a machine is three
machines a side and six in total, each pulling seven cables. That is
exactly what his authored export carried before the placement stage
broke, so the derivation reproduces his own answer rather than inventing
a new one.

2.3 The supports cannot be grouped by walking the net's edges. Zero edges
join two supports, so every anchor connects only to interior vertices and
an edge walk returns 42 groups of one. This is recorded because it is the
approach a reader would reach for first, and it looks reasonable until
measured.

2.4 `principalRows` must not be used. It resolves from principal curves
Param draws by hand; it is empty on any study where he drew none, its
count is however many he drew, and on this study its two runs are RIBS
over the crown, crossing the springings at right angles. Deriving machine
rows from it would stand every machine on the wrong axis and look almost
plausible.

## 3 Ownership

3.1 Agreed with the exporter session: **the document is authoritative
when it carries instances; the studio derives only when it carries
none.** One source of truth per study. The exporter holds the full result
including topology, its derivation is verified against the real study,
and Param can see a wrong placement in the Rhino viewport before
exporting, which no importer can offer.

3.2 The studio owns two cases the exporter cannot reach: a study whose
document carries bodies but no placements, and a study with no mechanism
document at all, which is what his ask is about.

## 4 The mechanism library

4.1 A mechanism document becomes a selectable asset. The server scans the
upload folder for `*-mechanism.json` and lists each with the facts needed
to choose between them: its name, its spool count, the part kinds it
carries, and whether it brings its own placements.

4.2 The client gains a Mechanism dropdown beside the vault selector, with
entries: **Auto**, **None**, and one per mechanism found. Auto is the
default and is what a user who never opens the control gets.

4.3 **Auto picks by fit, not by name.** A study needs one cable per
support. Auto chooses the mechanism whose spool count divides the row
length with the smallest remainder, breaking ties toward the larger bank
so a row is served by fewer machines. This is the answer to "different
wire configs to deal with un even numbers of wires": a row of 21 is
served exactly by a bank of seven, and a row of 20 by a bank of five
rather than seven with one machine short-handed.

4.4 A study's OWN mechanism document, when it has one, is preferred over
any other at equal fit, so borrowing never silently overrides authoring.

## 5 Derived placement

5.1 Runs only when the chosen mechanism carries no instances. Each step
below is a pure function, tested on its own, in `mechanism.js` beside the
reader.

5.2 **Rows.** Take the supports, compute their nearest-neighbour
distances, and join any two within three times the median into a group.
Groups of fewer than two supports are discarded as strays rather than
served by a machine of their own.

5.3 **The row's line.** Fit a line in plan by the spread of the two axes.
Its direction is the row's axis; the outward normal is the horizontal
direction from the net's centroid to the row's centre, which mirrors the
two sides without anything having to declare which side it is on.

5.4 **Machines.** Divide the row into consecutive runs of `spoolCount`
supports. A final short run is served by one more machine rather than
being dropped. Each machine is placed so its own spool line sits parallel
to the row, centred behind the supports it serves, set back along the
outward normal, standing on the ground.

5.5 **The machine's own datum is its spool line**, not its body origin.
Measured: the body origin sits nowhere meaningful in the mesh, while the
seven spool axis origins lie on a straight line 0.82 m long. That line is
what the machine is actually pinned to.

5.6 **Wires.** One wire per support, from the machine's k-th spool to the
k-th support it serves, so the fan is ordered and no two wires cross.

5.7 **Anchors are READ before they are derived**, the same ownership rule
as instances. The exporter gained an anchor port on 2026-09-09 (plugin
commit 95a31af) and now emits them whenever a result is wired, whether or
not Param has authored a body.

5.8 The contract, declared by the writer rather than inferred here:

- `mechanism.anchor` carries the body ONCE, as vertices and faces with
  `permanence: "permanent"`, or null when none is authored. Every stamp
  references it, so a hundred anchors cost one mesh.
- the top-level `anchors` array carries the stamps. Each has `side` and
  `mechanism` pairing with `instances[]`, the seven `net_vertices` its
  bank holds, an explicit `frame` of origin and three axes, `placement:
  "instance"`, `ref: "mechanism.anchor"` or null, and `permanence`.
- the frame is authored with **+Z up, X along the bank of seven, and its
  origin at the CENTRE of those seven where they attach**. A body modelled
  with its bearing face on z = 0 therefore sits on the ground.
- each anchor carries **the frame its own machine was placed by**, so an
  anchor and the machine behind it cannot disagree about which way is
  out, and the anchor lands in front by construction rather than by an
  offset.

5.9 The frames are emitted even when no body is authored, and they are
worth having on their own: they are a rail a reader can stamp its OWN
anchor asset onto without deriving anything. So a study with `ref: null`
still places anchors if the library supplies a body.

5.10 Only when the document carries no anchors at all does the studio
derive them: one per machine, in front of it, using the same frame the
machine was placed by, which is the writer's own rule reproduced.

## 6 What can go wrong, and what is said

6.1 Every derivation says it derived, in the log and once in the banner.
A derived placement is a studio opinion and must never be mistaken for
his authoring.

6.2 No supports, one support, or a study with no form document: no
machines, said plainly, no fallback that invents a position.

6.3 A mechanism with no reel axes has no spool line, so it cannot be
placed by this route. It is drawn once at its authored position, as now,
with the reason given.

6.4 Rows that are not straight are still served: the fit gives the best
line, and the straightness residual is logged so a curved springing is
visible as a number rather than as a machine that looks slightly wrong.

## 7 Testing

7.1 The pure functions are node-tested in `tests/studio/test_mechanism.py`
beside the reader's own tests, on synthetic rows with known answers.

7.2 One test pins the whole chain against **his real study**: 42 supports
must yield two rows of 21, six machines, 42 wires, and six anchors. It
skips when the export is not mounted, in the shape the material-library
test already uses.

7.3 Every new behaviour is proved able to fail by mutation before it is
committed.

## 8 Out of scope

8.1 Reeving, take-up and the spin are unchanged. A derived machine uses
the same act as an authored one.

8.2 The exporter's own derivation is not touched. If a document arrives
with instances, none of this runs.
