# The mechanism rework: the machine leaves the study

Settled with Param on 2026-09-09, the day after the two sided vault deadline. This
document is binding on the rework and supersedes the parts of
`2026-09-05-mechanism-into-vaulted-design.md` named in section 0.

## 0. What this supersedes, and what it leaves standing

0.1 SECTION 82 OF THE EARLIER SPEC IS REVERSED. It records that "the anchor and tension
tie now arrive as ONE object by his choice". His ruling of 2026-09-09 is the opposite and
is permanent: "i will alsway give you the anchor, the tension tie seperately, and make new
mechanisms". Two ports, always, and the welded-body case that would have drawn the tie
twice is off the table.

0.2 THE PLACEMENT HALF OF "HIS FIVE-PART MECHANISM" IS ALREADY OBSOLETE. That section, of
2026-09-08 late, proposes authoring the wire frames per unit and taking the placement from
the first frame of each group of seven. Section 11 of the same document, written hours
later and titled "placement stops being authored", replaced it after he said the planes
flip randomly. The derived placement is built and measures 0.000000 m residual on all six
instances. The PARTS half of the five-part section stands and is built here. The PLACEMENT
half is not pending work, it is the problem the derived placement was written to replace,
and rebuilding it would undo a measured win.

0.3 RULINGS R1 TO R4 OF THE STUDIO'S REPLY 4 STAND UNCHANGED, and this document depends on
them: every wire carries its own explicit `net_vertex` (R1); `planes[0]` is the net end
(R2); the routed portion is constant hardware (R3); permanence comes from the port name,
so the port name must reach the document as the part's kind (R4).

0.4 ROUTING STAYS UNIT-LOCAL, seven wires, tree `{wire}`. R3's payoff depends on it: the
studio builds each tube once and stamps it with a placement, 42 short tubes a frame rather
than 4200 circles. Forty-two world-space wire frames were considered and rejected.

## 1. Rulings settled 2026-09-09

1.1 The machine belongs to the web app. Machine parts upload ONCE as their own document.
Only the anchor and the tension tie travel with each study. (His ruling of 2026-09-08,
completed here.)

1.2 A study cites exactly ONE machine, by id, and the export writes N placements of it.
Several machine designs may exist; a single study never mixes them.

1.3 A slim Mechanism component does the study-side work and outputs a block. Export just
writes it, and keeps its current ten ports. The reason is not tidiness: placement is now
derived rather than authored, so seeing the derived placements on the canvas before
exporting is the only moment he can catch a bad one.

1.4 Placement is derived by default from the solved net's own anchor rows. The world-space
`Placement` (PL) override survives, because it is built, tested, and the day a layout
appears that the anchors cannot express, a port that exists beats a spec amendment.

1.5 A reel ENTRY is one mesh at N axes, not N meshes. Grouping only earns its keep if the
mesh travels once.

1.6 His four wheels MOVE WITH THE LOAD. The reeve default is 4.0.

1.7 The motors mesh is intended at its authored density and is kept. The machine document
stays about 36 MiB and uploads once; the study document falls to a few hundred KB. That is
the trade the split exists to make.

1.8 A machine's id is a MINTED CODE. The name is a human label and may be renamed freely
without orphaning any study that cites the machine.

## 2. The two documents

2.1 `bench.machine/1` carries the machine alone: the five parts, the reel entries and
bodies, the unit-local routing, the reeve default, and a header. It carries NO STUDY. That
negative invariant already exists and is pinned; section 9 strengthens the pin, which today
is false-clean.

2.2 The study document carries the citation, the placements, the permanent works, and the
wires. It carries no machine bodies at all.

2.3 THE STUDY DOCUMENT'S OWN SIZE BUDGET, stated so a later change cannot quietly reverse
the split: the envelope, instances, anchors, ties and wires together stay under 10 KB, PLUS
exactly the part bodies that were wired, each sized by its own vertex count. It is stated
that way rather than as a percentage because ruling 1.1 keeps the anchor and the tie in the
study, and their meshes are real. His current file carries a 235 KB tension tie by
reference and a null anchor; once both are bodies in the study, a percentage bound would
fail on correct output and be relaxed, which is the pin defeating itself.

## 3. The Machine component

3.0 THE PORT RULE, BINDING ON BOTH COMPONENTS AND STATED ONCE. New ports APPEND at the end.
A port that is withdrawn does NOT vacate its slot; it stays as a REFUSING STUB that names
itself and refuses anything wired to it. Neither component ever reorders, inserts or deletes
a port. The reason is that Grasshopper archives a wire by INDEX, so an insertion or deletion
silently re-points every wire after it, and the ports it re-points onto are the permissive
ones: a text port casts from almost anything, and a list arriving at an item port makes the
whole component solve once per item and keep the last. That is how a 55 mm bracket once
exported in place of a whole frame. A slot shift must be loud or it must not happen, and the
cheapest way to guarantee that is never to shift.

3.1 FIFTEEN PORTS. Every port he has wired keeps its index. `RE` and `AX` change access from
list to tree, which is non-breaking in itself because a list lands in branch `{0}`, though
paragraph 4.7 records the one archived shape whose MEANING changes under it. `TT` and `AN`
become refusing stubs under 3.0 rather than being removed.

```text
0  N   Name           item text    the human label, renameable
1  F   Folder         item text    the machine library
2  W   Write          item bool
3  TT  Tension Tie    REFUSING STUB, see 3.3
4  AN  Anchor         REFUSING STUB, see 3.3
5  F1  Frame 1        list         joined, ONE part, kind "frame"
6  F2  Frame 2        list         joined, ONE part, kind "frame"
7  MO  Motors         list         joined, ONE part, kind "motor"
8  RE  Reel           tree {entry} one branch per reel KIND, branch joined
9  AX  Reel Axis      tree {entry} ONE PLANE PER BODY
10 RT  Routing        tree {wire}  unit-local, planes[0] the net end
11 FM  Frame Meaning  item text
12 WS  Wire Start     tree {wire}  the un-offset first plane per wire
13 ID  Machine Id     item text    the minted code a study cites
14 RV  Reeve          item number  the per-mechanism default
```

3.2 F1, F2 AND MO EACH JOIN THEIR LIST INTO ONE PART. F2 joining is a change from today,
where it is an array. The reason is that a part index must not move when he adds a bracket,
and the join is lossless by construction: the existing `JoinMeshes` keeps every vertex and
face as authored and welds nothing. Should per-object materials ever be wanted, F2 becomes
a tree `{material}` joined per branch, and his existing single-list wire still lands in
branch `{0}`.

3.3 TENSION TIE AND ANCHOR LEAVE THIS COMPONENT ENTIRELY. They are study-side permanent
works. Leaving both authoring points alive would give two independently wired copies of the
same body, and the studio's "what remains when the machine is removed" view would then
depend on which copy it read. The two would drift the first time he edited one. Under 3.0
their slots remain as refusing stubs: an archived definition with a tie still wired to the
machine gets a named refusal telling him to move it to the collector, rather than a machine
document that quietly carries a permanent study body inside `machine.tensionTie` as today's
does.

3.4 CONSEQUENCE THAT MUST BE HANDLED RATHER THAN DISCOVERED: today the footprint bounding
box is computed over the tie's and the anchor's vertices as well as the machine's. Removing
them changes `footprint.min`, `max`, `setback` and `cableSpan`, which is what a layout uses
to space units without collision. The change is correct, since a footprint should describe
the machine, but it is a measurable change in a published number and the harness must pin
the new values rather than inherit the old.

3.5 WS EXISTS ON THIS COMPONENT FOR THE SAME REASON IT EXISTS ON THE COLLECTOR. The
machine's datum IS `planes[0]`. He offsets his routing planes to stop the drawn cable
cutting the drums, and that offset moves the datum, which moves every study placed against
it. The reader must take its port index as a parameter: the collector hard-codes index 9
for WS, and index 9 on this component is `Reel Axis`, also a plane tree. A verbatim reuse
would compile, run, and prepend each reel's AXIS PLANE to the front of every wire's route,
moving the whole machine to a plausible wrong place with zero residual.

3.6 THE HEADER. `schema`, `id` (the minted code), `name` (the label), `wireCount`, `reeve`,
`bank`, `footprint` and `datum`. `id` must not be derived from `name`: today the id is the
file-name-safe name, and a name that is not one path segment is silently rewritten to
"machine".

## 4. Reels: entries and bodies

4.1 AN ENTRY IS A REEL KIND. It carries one authored mesh and N BODIES. A BODY is one
physical reel: one axis plane, one place, one spin. His machine is four entries and ten
bodies: the spool entry with seven bodies, and three pulley entries with one each.

4.2 THE ENTRY'S MESH IS AUTHORED AT BODY 0, in unit-local space, which is how he models
today. Body 0's transform is emitted as the identity, explicitly, rather than omitted.

4.3 EACH BODY CARRIES A TRANSFORM mapping the entry's mesh frame onto that body's own axis,
built by the same basis maths the placement already uses.

4.4 EVERY BODY TRANSFORM'S DETERMINANT IS EMITTED, AND A REFLECTION IS REFUSED BY NAME.
This is not defensive decoration. A mirrored Rhino plane keeps a genuinely left-handed
stored Z, and this codebase treats that as a signal rather than an error, deliberately. If
any authored spool plane is mirrored, its body transform has determinant -1 and is a
reflection. A rotationally symmetric drum reflected about a plane through its own axis is
PIXEL-IDENTICAL IN EVERY STILL FRAME and turns the opposite way for the same take-up. The
obvious test, that the transform reproduces the body's own axis to 1e-12, is satisfied
exactly by that reflection, so the test cannot be the guard. The determinant must be.

4.5 THE FOUR-ENTRY GROUPING REVERSES AN EXISTING NOTE. The current code records his
ten-reel statement as "a fact about the machine, not a grouping to build: every reel here is
driven by its own axis". Ruling 1.5 reverses it, and the note must go rather than sit
contradicting the build.

4.6 THE BANK CROSS-CHECK MUST BE RE-DERIVED FOR ENTRIES. It currently identifies driven
spools as the largest group of reels sharing one axis direction and one winding radius,
which only works when seven separate spool meshes are authored. With four entries it would
read one or two driven spools against seven wires and fire its disagreement warning on a
correctly authored machine. The bank is now the entry whose bodies terminate wire routes.

4.7 THE ONE ARCHIVED SHAPE WHOSE MEANING CHANGES, and it must be refused rather than
reinterpreted. Today `RE` and `AX` are two flat lists zipped one to one: ten meshes, ten
planes, ten reels. Under the tree reading, that same wiring lands entirely in branch `{0}`,
which is ONE entry whose mesh is all ten reels JOINED, repeated at ten axes. That is a
complete, plausible, catastrophically wrong machine, and it is what every definition he has
saved would produce on first open. The component detects the legacy shape, being a single
branch whose plane count exceeds one and whose branch held more than one disjoint mesh, and
REFUSES it by name, telling him to branch the reels by kind. It does not guess which reading
he meant.

## 5. The slim Mechanism component and the study document

5.1 ITS PORTS, under the same rule 3.0. The five machine parts move to the Machine
component and their slots stay as refusing stubs; `MA` and `RW` append. The anchor and the
tie are separate ports permanently (0.1), and each port's NAME reaches the document as its
part's kind (R4).

```text
0   RES  Result
1   TT   Tension Tie      kept, kind "tie"
2   F1   REFUSING STUB    moved to the Machine component
3   F2   REFUSING STUB    moved
4   MO   REFUSING STUB    moved
5   RE   REFUSING STUB    moved
6   AX   REFUSING STUB    moved
7   RT   Routing          kept, unit-local, tree {wire}
8   PL   Placement        kept, the optional override
9   WS   Wire Start       kept
10  FM   Frame Meaning    kept
11  AN   Anchor           kept, kind "anchor"
12  MA   Machine          NEW: the bench.machine/1 document it cites
13  RW   Reeve Per Wire   NEW: optional per-wire override, tree {wire}
```

The five stubs matter more here than on the Machine component, because the slots they hold
are the ones an archived definition already has meshes wired into. Withdrawing them outright
would shift `RT`, `PL`, `WS`, `FM` and `AN` down by five, landing a mesh on `Frame Meaning`,
an item text port, which does not refuse it: it warns, falls back to "centreline", and makes
the whole component solve once per mesh and keep the last.

5.2 IT RESOLVES THE REEVE FACTOR, not the Export payload layer. Export just writes what it
is handed (1.3), and the machine document arrives here on a port rather than being read off
disk by the exporter.

5.3 THE STUDY DOCUMENT CARRIES: the cited machine id, N placements, the anchor and tie
bodies with their own placements and kinds, and the wires. Every wire carries its own
explicit `net_vertex` (R1) and its own RESOLVED reeve factor.

5.4 A WIRE NAMES ITS MACHINE WIRE BY THE AUTHORED WIRE NUMBER, never by an offset into the
machine document's routing array. That array is filtered and compacted, so a machine
authored with one wire's frames missing shifts every index after it, and all seven cables
would land on real drums in a self-consistent arrangement, every one of them wrong. R1's
whole point is that the identity travels rather than the position.

5.5 THE WIRE COUNT CROSS-CHECK IS AN EQUALITY, not a range. `PlacementGroupSize` is a
compile-time seven that drives the derivation loop, the override's plane-count refusal and
the study's own wire emit loop. Ruling 1.2 allows a machine with a different wire count, so
a study citing a twelve-wire machine would today write twelve in the header and exactly
seven wires, and a range test of "every wire lies in [0, wireCount)" would pass. Wires
placed per instance must EQUAL the machine's declared wire count.

5.6 THE SCHEMA NAME. The study document is no longer mostly a mechanism, and a rename would
describe it better. It is NOT renamed. The precedent is close and recent: renaming
`bench.frames/1` to `bench.formwork/1` broke the studio's reader silently and cost days.
The name stays `bench.mechanism/1` and the change is in its contents, which the studio must
be told about through the channel note regardless.

## 6. The reeve factor

6.1 THE DEFAULT IS 4.0, on the Machine component, per mechanism (1.6). A per-wire override
lives on the collector, matching the tree he already authors.

6.2 THE RESOLVED VALUE IS WRITTEN ON EVERY WIRE, so the studio never inherits or infers.
The same principle already applies to `net_vertex`.

6.3 THE MACHINE STATES ITS DEFAULT ONCE. The existing scalar `mechanism.reeveFactor` is
written deep inside the shared collector path, which the Machine component's own input does
not reach. If a renamed `machine.reeveFactorDefault` were added beside it without threading
the input through, one document would state the machine default twice, in two keys, with
two different numbers, both plausible and neither null. There is ONE statement of the
default, in the header's `reeve` block.

6.4 THE SANITY CHECK counts direction reversals along a wire's route and compares the
implied advantage against the declared factor. It warns by name and REFUSES NOTHING,
because a wheel that merely guides gives no advantage while a wheel that moves with the load
does, and geometry cannot tell them apart.

6.5 THE CHORDS ARE NORMALISED BEFORE THE ANGLE TEST. An unnormalised dot product compared
against a cosine threshold is scale-dependent. His routing frames are centimetres apart at
drum scale, giving dot products two orders of magnitude below any sensible threshold, so the
count would be zero on every wire of every real machine and the check could never fire,
while a fixture authored at unit scale would pass by coincidence. The harness therefore
carries a SCALE-INVARIANCE check: the same fixture scaled by 0.01 must report the same
reversal count. Nothing else in the suite can see that class of defect.

6.6 THE FAILURE THIS PREVENTS, recorded so nobody relaxes it later: a wrong factor makes
every reel spin at the wrong RATE while the geometry, the wire paths and the timing all stay
correct. Nothing looks broken.

## 7. Placement, and the guards that must survive it

7.1 DERIVATION IS UNCHANGED and remains the default: X along the line of anchors, Z the
world's up across it, Y completing them, the machine turned to face away from the net.

7.2 THE THREE GUARDS MOVE OUT OF THE OVERRIDE-ONLY BRANCH AND RUN ON BOTH PATHS. They are
the per-wire match-distance print, the match-distance warning against the row's own
characteristic spacing, and the R2 reversed-list check. Today all three sit in the authored
branch only.

7.3 WHY THAT IS THE WHOLE POINT OF THIS SECTION. All three read `net_vertex` and `route`,
and the derivation synthesises both. On the default path, a routing tree authored BACKWARDS
therefore yields a placement, a 0.000000 m residual, a 0.000000 m datum check, an explicit
net vertex carried straight out of the derivation, and not one number that can differ from
its right value. The earlier spec predicted this inversion in advance and made a binding
requirement of a sanity print; this is that requirement, discharged.

7.4 THE WITNESS MUST BE INDEPENDENT OF THE MACHINE'S OWN DATUM. A guard fed from the datum
the placement was derived from measures the derivation's own fit residual and cannot fail.
The independent witness is the anchor row's own characteristic spacing against the
machine's `footprint.cableSpan`.

7.5 THE DOC COMMENT MUST SAY, in the code and not only here, that a DERIVED residual proves
nothing and the match distance is the number that can.

## 8. The winding radius, and what the document must admit

8.1 THE MEASUREMENT CODE IS NOT THE BUG. Measured on his exported `2 Sided Vault` machine
on 2026-09-09: the seven spools' owned routing frames sweep from 0.0200 m to 0.0600 m about
their own axes, a spread of 120 per cent of the median. Pulley 7, by contrast, holds 1314
frames within 4 mm of a single radius, which is what a cable on a barrel looks like. The
published 0.0330 m is therefore the MEDIAN OF A SWEEP and not a radius at all. His reported
move from 0.0500 to 0.0330 was not a radius shrinking; it was the frames leaving the barrel
surface.

8.2 THE LIKELY CAUSE, for him to confirm on his own canvas: the endpoints are 0.0200 and
0.0600 on all seven spools, which is what a barrel near 0.040 m offset by 0.020 m along a
direction that ROTATES WITH THE HELIX produces, inward on one side of the turn and outward
on the other. The offset is not radial. That is a fix in his Grasshopper offset step, not in
the plugin.

8.3 THE DOCUMENT MUST ADMIT WHAT IT MEASURED. Each reel emits its `windingRadiusSource` as
today, plus a SCATTER figure.

8.4 THE SCATTER GATE IS THE RATIO OF REJECTED FRAMES TO OWNED ONES, never the spread of the
survivors. Ownership is radial and axial, so frames far off the barrel are EXCLUDED before
any spread is taken; gating on the survivors' spread makes the detector weakest exactly
where the defect is worst, and a truncated population looks tight. Rejected-against-owned is
directly countable and the tallying already exists.

8.5 A REEL WHOSE SCATTER FAILS THE GATE IS NAMED AND ITS RADIUS MARKED UNFIT TO ANIMATE. It
is not silently replaced with a fallback, and it does not receive a confidence label. A wrong
number carrying a certificate of correctness is worse than a bare wrong number, because it
is trusted where a bare one is not.

## 9. What must be checked, each proved able to fail

9.1 THE EXISTING MACHINE FIXTURE CANNOT PROVE WHAT IT CLAIMS, and this must be fixed before
anything is built on it. Zero of its routing frames are reel-owned, because its spool axes
sit outside the ownership window of its routes, so every claim about driven reels holds
vacuously. Its negative "no study" check walks ROOT keys only, so a tie or an anchor leaking
into the nested machine block is invisible to it, and its fixture passes null for both, so
the document under test never had an anchor to leak. That check is false-clean for the leak
it is named after.

9.2 THE FIXTURE MUST BREAK THE IDENTITY BETWEEN WIRE NUMBER AND BODY NUMBER. In the current
fixture wire k starts where spool k is centred, so the wire-to-body mapping is the identity
permutation and a mutation writing `wire = bodyIndex` passes unchanged. Wire 3 must
terminate on body 5.

9.3 THE FIXTURE MUST CARRY A MIRRORED-PLANE BODY, or 4.4 is unmeasured.

9.4 ANCHOR FIXTURES MUST USE NON-CONTIGUOUS NODE IDS. A row walked from its lowest-indexed
end returns ascending ids, so reversing a row is a no-op against the walker and a
`net_vertex` written as a loop counter passes. Anchors at nodes 10 to 16, so wire 0 must
read 10.

9.5 THE MACHINE-LEAK CHECK MUST BE A WRONG ANSWER, NOT A COUNT. A count of parts is
satisfied by the wrong parts. The check compares the study document's total body vertex
count against the sum of exactly the bodies that were wired to the study ports, so a machine
part that crept back in is a number that differs rather than a key that appears.

9.6 THE CITATION FINGERPRINT MUST PIN (WIRE INDEX, ORIGIN) PAIRS, not a positional list of
origins. The machine's datum is written over only the wires that carry frames, so a machine
whose wire 0 is empty produces a datum whose first entry is wire 1, and a study laid out on
that correspondence fingerprints clean while every cable is one wire out.

9.7 EVERY NEW CHECK IS RED-PROVED BY A PRODUCT MUTATION, never by deleting the assertion.
An assertion that no change to the product can turn red is coverage theatre, and this
document names three places where that trap was already set.

## 10. Migration and what breaks

10.1 His canvas rewires. `TT` and `AN` move off the Machine component; `ID` and `RV` are
new; `RE` and `AX` become trees.

10.2 THE STUDIO MUST BE TOLD, through the channel note, before this ships: the
`bench.machine/1` schema and where machine documents live; that `bench.mechanism/1` keeps
its name but loses the machine bodies; and that the scalar `reeveFactor` is replaced by a
resolved per-wire value.

10.3 `Seven spool winch-mechanism.json` should be removed from the machine library folder.
It is 36 MiB of `bench.mechanism/1`, a STUDY document whose `study` field still reads
"2 Sided Vault", sitting where the studio will scan for machines.

10.4 The Machine component's Folder and Export's Machine Folder must resolve to the same
place. They are independent strings today that have to agree by hand, and a machine written
to one folder while studies point at the other resolves to nothing.

## 11. Out of scope, said so nobody reinvents it

11.1 NO UPLOAD ROUTE. Nothing in this repo has one, and building a port for a route that
does not exist is speculative. The machine arrives through the library folder until the
studio says otherwise.

11.2 NO MESH DECIMATION. Ruling 1.7 keeps the motors mesh at its authored density.

11.3 NO LAYERED-SPOOL ARITHMETIC. As wire builds up on a drum the effective radius grows
slightly. At this level of representation it is immaterial, and if his machine ever needs
it, it is a refinement to the spin arithmetic and not to the routing.

11.4 THE FORTY-TWO WORLD-SPACE WIRE FRAMES, considered and rejected (0.2 and 0.4).

## 12. Open items and channel asks

12.1 FOR HIM: confirm the offset direction in his Grasshopper script (8.2). Everything else
in section 8 is the plugin reporting honestly on whatever he authors; this is the thing that
makes the number right.

12.2 FOR THE STUDIO: 10.2, and whether they want an upload route at all (11.1).

12.3 CARRIED, NOT CLOSED: five of his eight registered studies are unexported, and
`Complex geometry` is an irregular net (823 vertices, 1543 faces) that no fixture measures.
Neither blocks this rework.

## 13. Amendments found during implementation, 2026-09-09 to 2026-09-11

These six were found while building Tasks 3, 4, 6, 7 and 8, most of them by measurement
against his real files rather than by review of the prose. Four are corrections to what
this document got wrong. Each is recorded here as an amendment, with its evidence, rather
than edited silently into the paragraph it corrects, on the same principle sections 10 and
11 of the earlier spec were written on: the evidence is the valuable part, and a future
reader should be able to see what was first specified and what the build then found. Where
an amendment below disagrees with a numbered paragraph above, the amendment wins.

13.1 PARAGRAPH 4.7 IS DEFECTIVE, and it would have refused correct machines. As written it
refuses a branch "whose plane count exceeds one and whose branch held more than one disjoint
mesh". That contradicts 3.1 and 4.1, both of which bless several meshes in one branch: RE is
"tree {entry} one branch per reel KIND, branch joined" (3.1), and an entry's several authored
objects are joined into the one mesh it carries (4.1, 4.2). Taken literally, 4.7's rule would
refuse a drum authored as a hub plus two flanges at seven axes, a legitimate machine, which
is a warning firing on correct input. The rule as built is an EQUALITY instead: only when a
branch's item count equals its plane count does the old flat-zip reading exist at all to be
confused with the tree reading, so below equality there is nothing to guess between and
nothing to refuse. It is implemented over total ITEM counts, not resolved-mesh counts,
because `ReadMeshTree` adds a bare null to a branch, with no warning, for any wired item that
fails to resolve; counting only resolved meshes let a ten-object legacy branch with one
unresolved item read as nine against ten planes, fall through the equality untested, and be
built as one entry with every drum joined at ten axes, with nothing said at all. Confirmed by
measurement, not asserted: that case produced one entry and zero warnings before the item-count
form was adopted.

13.2 PARAGRAPH 2.3'S 10 KB ENVELOPE BOUND HOLDS ONLY AT FIXTURE SCALE. Measured on his own
`2 Sided Vault` study: 661,616 bytes total, of which about 330 KB is the tension tie and the
anchor bodies the paragraph already excludes from the bound, leaving an envelope of about
316 KB against the stated 10 KB, thirty times over. The excess is dominated by the wires' own
route frames, which paragraph 2.3 counts inside the bound. The split this section exists to
pin still holds: the 646 KiB total is the figure ruling 1.7 predicted ("a few hundred KB"),
and every machine body is genuinely gone. It is the 10 KB SUB-bound that describes a study
with a handful of frames per wire and not his forty-two wires' worth. Recorded here rather
than legislated in a fixture, because raising it to a number that means something at his
scale is a spec amendment and not a test change.

13.3 PARAGRAPH 7.2 IS FACTUALLY WRONG about the pre-change state. It says "Today all three sit
in the authored branch only." They did not: the per-wire match-distance print, the
match-distance warning and the R2 reversed-list check all already ran from one condition that
asks only for a solved net, a route and an instance frame, which every instance carries
whether Placement (PL) authored its frame or `DerivePlacements` built it. What was true, and
what the task actually fixed, is that on the DERIVED path none of the three could REPORT a
fault, because a derived transform is fitted TO the anchors its wires are then matched
against. Measured before the fix, on a routing tree authored backwards down the derived path:
residual exactly 0.000000 m on both instances, zero reversed-list warnings on either one, and
match distances and warning counts IDENTICAL to the correct tree's own (0.9, 0.6, 0.3, 0, 0.3,
0.6, 0.9 m; four warnings), only on the other side. A number that reads the same whether the
input is right or wrong is not a guard. The paragraph's substance, that the three guards must
be provably load-bearing on both paths and not only on the authored one, stands and is what
was built; only its claim about where they already ran was wrong.

13.4 PARAGRAPH 8.4 IS FALSIFIED ON HIS REAL FILE. Taken at its narrowest, "the ratio of
rejected frames to owned ones, counting ownership refusals only" runs BACKWARDS there: his
seven swept spools score 0.16 to 0.28 while the honest pulley (pulley 7) scores 0.40, so a
gate on that quantity either fires on a correct drum or passes the defect. Two structural
causes, confirmed independently by two agents' measurements: first, his spools' flange radius
and their sweep both end at exactly 0.0600 m, so nothing is refused radially at all and the
narrow reading has nothing to count; second, the just-outside window is a fraction of the
MESH radius, so a 0.200 m pulley trawls a 30 mm annulus against a 0.060 m spool's 9 mm, and
dividing by the drum's own owned count does not remove that size bias.

AMENDED TO: the figure is disagreement with the published radius, counted over the whole
neighbourhood a reel's ownership window reaches, where a REFUSED frame is classified by the
SAME band test as an owned one. So a refusal that still sits at the published radius counts
as agreeing, and only a frame that actually disagrees with the published radius counts against
the reel. Under this reading, measured on his file: spools 4.00 to 4.24, pulley 7 reads 0.0407,
pulley 9 reads 0.1747, a hundredfold gap between the defect and the two honest wraps.

AND ADD: the ownership margin bounds the population the figure is taken over, so a drum with
no flange at all sits outside the gate's reach in one direction. State that direction
plainly, with the measured numbers, rather than leaving it as a blind spot to be found later:
on a uniform sweep from 0.020 to 0.060 m varying only the flange, flange 0.060 scores 2.33 and
is named, flange 0.030 scores 0.93 and is named, and flange 0.0205 scores 0.09 and goes
SILENT while publishing a radius wrong by a factor of two for spin rate. That is a direction
this measure weakens in as the flange closes on the sweep, not an isolated blind spot off to
one side.

13.5 THE WITHIN-ROW MATCHING RULE CHANGED (Task 7a). It is no longer the open default this
document describes elsewhere as pending. It is now "the anchor the wire was actually placed
against": `MechanismDocument.Json` orders an instance's placed wire ends and its row's anchors
along the same axis `DerivePlacements` uses (`WidestPairDirection`, `OrderAlongAxis`) and pairs
k-th to k-th, rather than pairing wire order against the row's discovery order. The two
orderings were EXTRACTED, not reimplemented, so the placement rule and the document's matching
rule are one piece of code that cannot drift apart again the way the old pair of independent
rules did. On every two-sided vault the far side is a machine the derivation turns round, and
the two rules used to run end for end there; see section 5 of the channel note at
`docs/superpowers/notes/2026-09-09-machine-schema-channel-note.md` for the artefact
consequence.

13.6 THE MACHINE FILE IS STILL NAMED FROM THE MACHINE'S NAME, NOT ITS MINTED ID. The write
target is `<Name>-machine.json` in the machine library folder; the id (ID port, section 3.6)
plays no part in it. Two machines sharing a name therefore write ONE file, and a study citing
minted id A can open that file, find id B inside it, and render the wrong machine with no
complaint, because the schema is right and only the id inside says whose file it actually is.
A name that is not one path segment still collapses, through the same `StudyName` sanitisation
the id path itself was freed of. An INTERIM GUARD is built: `RefuseOverwritingAnotherMachine`
refuses to overwrite a machine file whose stored id differs from the one about to be written,
naming both ids. That is a guard against the write, not a fix to the naming. THE FULL FIX IS
OUTSTANDING and needs Param's ruling on two things: what characters a minted id may carry (so
it can become a filename), and a migration for a library that already holds files named the
old way. Tracked, not scheduled.
