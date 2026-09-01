# Readers merge: Deconstruct and Frame become one reader, and Diagnose reads the document

Date: 2026-09-01. Status: design, awaiting Param's spec review.

Design input: docs/superpowers/specs/2026-09-01-readers-round-design-input.md, whose rulings govern.
Predecessor: docs/superpowers/specs/2026-08-31-readers-design.md, the shipped design that produced the
current split, whose surface rules this spec inherits: RES at input 0; trees aligned so branch {i} of
one output pairs with branch {i} of its partner; the load-protection warning that compares archived
port names as well as counts; readers' geometry outputs hidden by default.

Every statement below about how the code behaves today names the file and the line it was read from.
Where a claim could not be checked against the code it is marked as unchecked in the sentence that
makes it.

## 0. The open question that must be answered before this is built

The merged reader carries FIFTEEN outputs. That is Monitor-sized, and being tall is part of what Param
disliked about Monitor, which is why the previous round split it into Forces, Fit and Supports.

HE HAS NOT APPROVED THE MERGE, and an earlier draft of this section said he had. What the record holds
is a musing: "last thing, part of me thinks these two components can conjoin" (design input :6-13). That
is a proposal and not a ruling. The design input then reserves the decision to him in terms, at :108-114:
"THAT COUNT NEEDS HIS EYE before it is built. Fifteen ports is a tall component on a canvas, and being
tall is part of what he disliked about Monitor. The principle in section 1 says merge, and the port count
says a merged component is large; those pull opposite ways and only he can say which matters more in the
way he actually works." I searched the design input and the predecessor spec for approval language and
found none beyond "part of me thinks". The whole shape of this spec rests on an answer he has not given,
so it is put to him as question 12(a) and none of section 1 should be built before he answers it.

The arithmetic is not in doubt: ten registered on Deconstruct at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\VisualiseComponents.cs:343-427
and ten on Frame at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\FrameComponents.cs:76-169,
less Member IDs (VisualiseComponents.cs:363), Node IDs (:369), Reaction Points (:396) and Phase
(FrameComponents.cs:148) gives sixteen, and deduping Anchor Nodes against Support Points gives fifteen.

If fifteen proves too tall on the canvas the fallback is the one the design input already names at
docs/superpowers/specs/2026-09-01-readers-round-design-input.md:110-114: keep two components, apply the
four deletions and the Anchor Lines fix to them, and let one hold the geometry and the other the
statics. Nothing in sections 2 to 5 below depends on the merge; only sections 1, 9 and part of 10 do.

## 1. The merge

1.1 ONE COMPONENT replaces both. It takes one Result and hands back fifteen geometry outputs. It
configures nothing, targets nothing and has no second input, which is the property that made it a
candidate for merging in the first place (design input section 1).

1.2 NAME. "Deconstruct", nickname "DE", panel 04 Read, icon key result_breakdown, badge DE. The name
should say what the component does, which is take one Result apart into everything it holds; the
frame-relative rule of section 3 is a property of the outputs and belongs in their descriptions, not in
the component's title. The alternative is "Frame", nickname "FR", on the argument that after section 3
the whole reading is frame-relative; it is recorded here because Param named neither and either is
defensible. Whichever is chosen, the other's icon entry is deleted (section 10).

1.3 DESCRIPTION. "Take one solved FD or TNA Result apart: the formwork surface and its cables, the
notched bars, the anchors and the boundary, the columns, and the statics streams. On a Result from
Animate the FRAME GEOMETRY, Mesh down to Columns, is read at that frame; the STATICS STREAMS below it,
Member Lines down to Reaction Vectors, are read at the solved shape, because there is no frame-time force
answer to draw them at. A Result from a solver or from Columns is read at the solved shape throughout.
Forces, Fit and Supports carry the numbers and Skin the cells. Reciprocal-only streams (Form Lines,
Force Lines) come out empty for FD."

The second sentence is not decoration. An earlier draft said flatly that a Result from Animate "is read
AT THAT FRAME", which is false of nine of the fifteen slots as this spec builds them; rule 3.0 states the
split and this description now carries it.

1.4 GUID POLICY. A NEW GUID. Both existing classes are deleted and neither of their GUIDs is reused:
Deconstruct's 68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961 (VisualiseComponents.cs:326-327) and Frame's
5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58 (FrameComponents.cs:57-58) are retired. This follows the Monitor
precedent set at docs/superpowers/specs/2026-08-31-readers-design.md:68-75, and the reason is the same
one: wires cannot be redistributed mechanically across a shape this different. Section 9 sets out what
reusing a GUID would do instead, and why it is worse rather than kinder.

1.5 THE INPUT. Result, RES, ResultParam, GH_ParamAccess.item, at slot 0, NOT optional. A reader with no
Result has nothing to read. This is the registration Deconstruct has at VisualiseComponents.cs:332-337
and Frame at FrameComponents.cs:63-70, unchanged.

1.6 THE UNWIRED RULE. Frame's behaviour wins. With nothing wired the component sets Message = "No
Result" and returns, as Frame does at FrameComponents.cs:174-184. Deconstruct returns silently at
VisualiseComponents.cs:431-436, which leaves the previous solve's chin standing over empty ports, and
Frame's own comment at :178-181 gives the reason that behaviour was corrected.

1.6A FAILURE IS PARTITIONED, and this must be ruled rather than left to whoever writes the catch. Each
component today wraps its whole solve in ONE try/catch that sets Message = "Invalid" and reports the
exception: FrameComponents.cs:186-210 and VisualiseComponents.cs:438-679. Merged naively that becomes one
catch over both halves, and the halves fail independently in practice. Deconstruct's TNA path indexes
stateById[row.Id] with no guard at VisualiseComponents.cs:523, which throws on a Result whose edge-state
ids and member rows disagree; FrameGeometry.Read throws on a Result carrying no equilibrium or no
vertices at MouldComponents.cs:2453-2461. An author whose TNA mappings are malformed gets Frame's mesh,
cables and columns today, and would get fifteen empty ports after a naive merge.

THE RULE. The frame half and the statics half are computed under SEPARATE try/catch blocks. A Result that
FrameGeometry can read but ResultTables cannot still hands back slots 0 to 8, and the mirror case still
hands back slots 9 to 14. A half that failed emits empty ports and raises ONE Error naming which half
failed and why. The chin reads "Invalid" only when both halves failed; when one failed the chin carries
the surviving half's reading with the failure named after it, "TNA · 412 members · raise (statics
failed)" or "TNA · raise (frame failed)". Validate() runs ONCE, before either half, and its failure is
still the single Error that empties everything, because a Result that fails the contract is not a Result
either half should be reading.

1.7 THE CHIN. On a good solve the Message reads solver, member count, phase: "TNA · 412 members ·
raise". Deconstruct sets the first two clauses today at VisualiseComponents.cs:671-673 and Frame sets
the third at FrameComponents.cs:204. Joining them is what keeps Phase's content on the canvas after its
port is deleted (section 2.3). A Result carrying no frame reports "final", which is
FrameGeometry.FinalPhase at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\MouldComponents.cs:2398,
so the third clause is always present.

1.8 PREVIEWS. The constructor walks Params.Output and sets IGH_PreviewObject.Hidden on every output, as
both components already do identically at VisualiseComponents.cs:319-323 and FrameComponents.cs:50-54.
The loop transfers unchanged.

1.9 THE FIFTEEN OUTPUTS, in this order, with Anchor Lines immediately after Anchor Nodes as the design
input requires at :94-98:

| Slot | Name | Nick | Type | Access | Came from |
| --- | --- | --- | --- | --- | --- |
| 0 | Mesh | M | Mesh | item | Frame 0 |
| 1 | Cables | C | Line | tree | Frame 1 |
| 2 | Principal Lines | PL | Curve | tree | Frame 2 |
| 3 | Principal Nodes | PN | Point | tree | Frame 3 |
| 4 | Anchor Nodes | AN | Point | tree | Frame 4, absorbing Deconstruct's Support Points |
| 5 | Anchor Lines | AL | Curve or Line | tree | Frame 9, MOVED, and RETYPED only under 5.2(b) |
| 6 | Perimeter Nodes | PRN | Point | tree | Frame 5 |
| 7 | Perimeter Lines | PRL | Curve | tree | Frame 6 |
| 8 | Columns | CO | Line | tree | Frame 7 |
| 9 | Member Lines | ML | Line | tree | Deconstruct 0, RENAMED nickname (rule 1.10) |
| 10 | Form Lines | FL | Line | tree | Deconstruct 1 |
| 11 | Force Lines | FCL | Line | tree | Deconstruct 9 |
| 12 | Load Points | LP | Point | LIST | Deconstruct 5 |
| 13 | Load Vectors | LV | Vector | LIST | Deconstruct 6 |
| 14 | Reaction Vectors | RV | Vector | tree | Deconstruct 8, REBRANCHED (section 3.5) |

1.10 THE NICKNAME COLLISION, and the rule that settles it. Frame's Mesh is "M"
(FrameComponents.cs:76-82) and Deconstruct's Member Lines is "M" (VisualiseComponents.cs:343-356).
Merged, they collide. Grasshopper does not refuse two ports with one nickname, so the collision passes
the build in silence and shows up only as two ports labelled M on the canvas. The rule: MESH KEEPS M
and MEMBER LINES BECOMES ML. Mesh is slot 0 and M for a mesh is the convention across the whole
Grasshopper ecosystem; ML also reads better beside FL and FCL than M does, and Member Lines' own
description ties it to Forces' member-force tree, whose nickname is F rather than M
(docs/superpowers/specs/2026-08-31-readers-design.md:40-42). Section 10 adds the harness check that
would have caught this and will catch the next one.

1.11 LOAD POINTS AND LOAD VECTORS STAY LISTS. They are registered GH_ParamAccess.list at
VisualiseComponents.cs:388 and :394 while every other output on both components is a tree. That is not
tidied here. Changing an access mode changes what a downstream component receives, and this round has
enough moving underneath it already. It is recorded as a loose end rather than fixed.

1.12 CABLES AND MEMBER LINES ARE NOT ITEM-ALIGNED, and both descriptions must say so. The merged
component ships the net twice and the two shipments do not agree. Cables is built by iterating
MouldGeometry.ValidEdges, which hands back equilibrium.Edges in index order with out-of-range and
degenerate edges DROPPED (MouldComponents.cs:938-957, consumed at :2498 and :2511-2519). Member Lines is
built from ResultTables.Members, which for TNA sorts by EdgeState.Id and carries one row per edge STATE
(VisualiseComponents.cs:151-163), and for FD builds one line per equilibrium.Edges entry with no
valid-edge filter at all (:944-951). So the two can differ in item count, and will differ in item order
for any TNA Result whose state ids do not run parallel to its edge ids. Both descriptions promise
"branch {i} is bar {i}" today, and Member Lines' shipped text goes further with "Every member-aligned
output BELOW is branched and ordered identically" (VisualiseComponents.cs:346-356), which becomes a lie
the moment Cables sits above it on the same component.

THE RULE. Cables is kept and the pair is DENIED IN THE TEXT rather than made to hold. Deleting Cables
was considered and rejected: rule 3.0 makes Cables the net AT THE FRAME and Member Lines the net at the
SOLVED shape, so the two differ in more than ordering source and Member Lines cannot stand in for
Cables on an Animate Result. Three text changes follow, and they are written here rather than left to
the implementer.

  (a) CABLES gains: "Branch {i} is bar {i}, the same bar as branch {i} of Principal Lines and Principal
      Nodes. This is the net AT THIS FRAME, in the Result's own edge order with degenerate and
      out-of-range members dropped. It is NOT item-aligned with Member Lines, which is the solved net in
      the member-table's order; pair with Principal Lines and Principal Nodes, not with the statics
      streams."
  (b) MEMBER LINES' phrase "Every member-aligned output below is branched and ordered identically" is
      replaced by the two ports named: "Form Lines and Force Lines are branched and ordered identically,
      and so are FORCES' number trees for the same Result." Naming them by position stops being safe
      the moment the port list changes, which is what this round does.
  (c) MEMBER LINES gains: "Cables, above, is a different reading of the same net: the frame's edge order
      rather than this table's. Branch {i} is bar {i} in both, but item [k] within a branch is not the
      same member."

## 2. The deletions

Four ports go. For each: what is lost, and what was checked.

2.1 MEMBER IDS (Integer, tree, VisualiseComponents.cs:363-368). His reason is general: "if i have the
tree structure I dont need the structure given again, that goes for all components" (design input :6-13,
:31-33). What is lost is the one exact non-coordinate bridge from a member line back to the Result's own
member index. Nothing shipped needs it: the design input records at :34-37 that nothing in the plugin
consumes the port, that Export builds its payloads from the ResultDto contract rather than from a
reader's outputs, and that Forces names Member IDs only to disclaim alignment with it. That verification
was made in the previous round and is carried forward here rather than repeated.

2.2 NODE IDS (Integer, tree, VisualiseComponents.cs:369-376). Same reasoning, same verification (design
input :31-37). Loads' own Node IDs INPUT is a different port on a different component and is unaffected.

2.3 PHASE (Text, item, FrameComponents.cs:148-155). "I again dont need that information" (design input
:38-40). The deletion is safe, but the reason the design input gives for it is not the one the code
supports, and this spec repeated it before checking. The checked version: Phase is a read-out of
Mould.Frame.Phase (MouldComponents.cs:2490-2496). Fit reads the frame BLOCK off its own Result input,
`MouldFrameDto? frame = mould?.Frame` at FitComponent.cs:243, and the only member of it Fit tests for an
intermediate frame is frame.Time at :451; it never reads the phase word at all. The one component that
reads frame.Phase off a Result is FORCES, at ForcesComponent.cs:577, where it goes into the forces.counts
diagnostic sentence, and it takes it off the Result rather than off this port. A repository-wide search
finds Mould.Frame read in exactly two places, FitComponent.cs:243 and MouldComponents.cs:2463, and .Phase
read only at ForcesComponent.cs:577, MouldComponents.cs:2492, :2496 and :2671, and FrameComponents.cs:201
and :204. NOTHING CONSUMES THE PORT. Nothing is lost from the canvas either, because rule 1.7 puts the
phase word on the chin, which is where Frame already shows it at FrameComponents.cs:204.

2.4 REACTION POINTS (Point, tree, VisualiseComponents.cs:395-405). "Reaction points and support points
are also the same" (design input :41-49). This is true by CONSTRUCTION rather than by coincidence, and
the construction is worth naming because it is what makes the deletion safe: where a support node
carries no reaction the code reads the support's own point out of the supportPoints array
(VisualiseComponents.cs:634-640), so for every real support the two ports hold the same Point3d. The
port's own description already concedes it is "branched and ordered EXACTLY as Support Points"
(:398-405). Reaction VECTORS stay; they are what an author actually sums. The one case where the two
ports differ is section 4.

2.5 SUPPORT POINTS (Point, tree, VisualiseComponents.cs:377-382) is not in the list of four but is
removed all the same, absorbed into Anchor Nodes by the dedupe. Section 3 is entirely about what that
absorption commits us to, because the two ports are not interchangeable.

2.6 THE SWEEP HIS GENERAL CLAUSE REQUIRES. His ruling is explicitly general, "if i have the tree
structure I dont need the structure given again, that foes [goes] for all components" (design input
:6-13), and the design input underlines the reach at :31-33, "His reason is general and worth applying
beyond these two". An earlier draft quoted the general clause and then applied it to two ports on one
component, which narrows his scope without saying so. The sweep is reported here instead.

THE METHOD, and its limit. A port that restates a tree structure carries an index, an id or a key, so it
is registered through AddIntegerParameter or AddTextParameter. Every such registration in
plugin/native_v02/Components was read and the OUTPUT ones sorted from the input ones. Geometry ports
cannot restate a structure and were not read. That is the whole of the reach of this sweep and a port
that restated its structure as a number would be missed by it.

  (a) DECONSTRUCT'S MEMBER IDS and NODE IDS (VisualiseComponents.cs:363-376). RETIRED by rules 2.1 and
      2.2. These are the two he named.
  (b) SKIN'S COURSES (SkinComponents.cs:155-161), "The course per cell, branched and ordered exactly as
      Cells, the index repeated per item", sitting beside a Cells port branched by course, path = course,
      at :141-154. That is the branch path handed back as data, and it is the clearest live target
      outside the merged reader. ALREADY RULED, and not by this spec: rule 9.2.3 of
      docs/superpowers/specs/2026-09-01-skin-buildability-design.md removes it, on the same reasoning,
      and rule 10 of that spec makes Export read the branch path instead. Its stated consumer, "so the
      pairing survives Export's flatten. Wire into Export's Courses.", is the port that spec's rule
      12.10(b) also reshapes. So his general clause IS applied beyond the merged reader in this wave, in
      the spec that owns Skin. Nothing is asked of this round for it.
  (c) THE PLUGIN HAS ALREADY APPLIED THE RULE ONCE, to Skin's sibling: PiecesComponents.cs:119-121
      records "the flat Courses (C) output is REMOVED -- the branch path IS the course". That is the
      precedent, and it is worth naming because it shows the rule is house practice rather than a new
      preference.
  (d) IMPORT PIECES' KEYS (Text, tree, PiecesComponents.cs:135-140), "The piece key (for example c0p3)
      of each piece, branched and ordered exactly as Meshes." KEPT. Half of the key restates the branch
      path, the c0, and half does not: p3 is the studio document's own name for the piece, and it is
      what Meshes' own description at :127-134 tells an author to cross-reference when a piece comes
      back as a null placeholder. A key that names a thing in another system is not the tree structure
      given again.
  (e) FIT'S UNREACHABLE (Integer, tree, FitComponent.cs:149-154), "The node ids whose absolute deviation
      is outside Tolerance, ascending. One branch". KEPT. It is a SELECTION, not an alignment: nothing
      pairs with it branch for branch, and the ids are the answer rather than a restatement of it.
  (f) DIAGNOSE'S SOURCE (Text, tree, DiagnoseComponents.cs:63-67). KEPT. The branch path is a number and
      the source is the component's name; the path cannot say which component raised the entry, so this
      names what the structure does not. Section 6.8 depends on it.

No other output port in the plugin restates its own tree structure. The general rule is therefore
applied, twice in this wave, and rules 2.1 and 2.2 are not the whole of it.

## 3. The Anchor Nodes rule

3.0 THE FRAME RULE APPLIES TO SLOTS 0 TO 8 ONLY, and this comes first because without it the section
reads as exhaustive when it is not. Rules 3.1 to 3.4 settle Anchor Nodes and say nothing about the six
ports inherited from Deconstruct, and every one of those six is built on the SOLVED vertices: Member
Lines through ThrustLine and MemberLines at VisualiseComponents.cs:795-805 and :944-951, Load Points and
Load Vectors at :526-531 and :538-540, the reaction points and vectors at :486-495 and :617-644, all
reading equilibrium.Vertices. FrameGeometry.Read reads Mould.Frame's vertices instead when the count
matches (MouldComponents.cs:2463-2470) and builds every one of its outputs over those (:2595-2609).

THE RULE. Member Lines, Form Lines, Force Lines, Load Points, Load Vectors and Reaction Vectors are read
at the SOLVED vertices and do NOT follow the frame. They are the statics of the solved state, and there
is no frame-time force answer to draw them at: a member force computed for the finished vault drawn on
the line the half-reeled frame stands at would be a number attached to geometry it was not solved on.
Slots 0 to 8, Mesh through Columns, follow the frame by rules 3.1 to 3.4.

So on an Animate Result the component emits Cables at the frame and Member Lines at the solved shape,
from one Result input. That is deliberate, and because it is not obvious, EACH OF THE SIX statics ports'
descriptions carries the sentence in its own words, exactly as rule 3.4 makes Anchor Nodes carry its
own: "AT THE SOLVED STATE: this is read at the Result's solved vertices even on a Result from Animate,
because it is the statics of the finished vault. The frame's own geometry is Mesh through Columns,
above." Rule 1.12 then says what that means for the one pair an author will read across, Cables against
Member Lines.

Without rule 3.0 two competent implementers split here: one reads rule 1.3's old sentence as governing
and rebuilds the statics streams over set.Positions, the other reads section 3 as exhaustive and
transfers Deconstruct's code unchanged. The two components differ visibly at every intermediate frame.

3.1 THE RULE FOR THE FRAME HALF. The merged Anchor Nodes follows the ANIMATION FRAME'S positions, not
the solved positions. A reader fed an animation should show the animation.

3.2 WHY IT IS A RULE AND NOT A DETAIL. Frame reads Mould.Frame's vertices when the Result carries one
and the count matches, falling back to the solved vertices otherwise (MouldComponents.cs:2463-2470), and
every geometry output including the anchor strips is built over those positions (:2599-2601).
Deconstruct always reads the solved vertices. Animate blends every node between the drawn pattern and
the solved form, anchors included, so the two agree at rest and at finish and differ at every
intermediate frame (design input :50-59). Anchor Lines drawn through solved positions while the mesh
sits half reeled would be worse than useless.

3.3 WHERE THE SOLVED POSITIONS REMAIN. On the Result itself: equilibrium.Vertices is the solved vertex
list, and Fit's Deviation is the measured distance between the frame and the solved state. Nothing in
the plugin loses access to a solved anchor position by this rule; only this component's ports stop
offering one directly.

3.4 THE PORT DESCRIPTION MUST SAY IT. Anchor Nodes' text becomes:

"The Result's supports: the side anchors that stay on the ground and take the perimeter cables'
prestress. A TREE with one branch per CONNECTED STRIP, walked end to end, so opposite sides of the vault
come back as separate branches instead of one merged list. AT THIS FRAME: on a Result from Animate these
are the anchors where the frame has them, not where the solved vault has them, and the two agree only at
rest and at finish. The solved positions are on the Result's own vertex list."

Anchor Lines' description carries the same sentence, because it is drawn through these points.

3.5 REACTION VECTORS FOLLOW THE ANCHOR STRIPS. This is the work the dedupe actually costs, and it is not
a deletion. Reaction Vectors is branched onto Deconstruct's support strips today
(VisualiseComponents.cs:602-644); Anchor Nodes is branched onto Frame's anchor strips
(MouldComponents.cs:2575-2576). Keeping Anchor Nodes and dropping Support Points means Reaction Vectors
must be rebranched onto the ANCHOR strips, item for item, so that branch {i} item [k] is the same support
in both. The alignment promise the ports make is otherwise false.

THE REBRANCHING IS AN INTERNAL STATIC, and this is a requirement rather than a preference. Today the
branching lives inline inside DeconstructComponent.SolveInstance at VisualiseComponents.cs:617-664,
including the zero-vector fallback at :634-640 that rule 4.5 keeps. The harness never calls SolveInstance
on anything (tests/native_smoke/Program.cs:12741-12748), so inline is unmeasurable. The rule: an internal
static taking (the anchor strips as NODE INDEX lists, the reactions table) and returning (the vector
branches, the stray node ids), in the shape of DeconstructComponent.ColumnTrees and ForceLines, which the
harness already drives by reflection at Program.cs:2897 and :3147. SolveInstance calls it and does
nothing else with the branching. Rule 3.8's node-index lists are necessary for this and not sufficient on
their own: without the static the mapping from reaction to strip stays inside the component and rule
10.3(d) has nothing to call.

3.6 WHICH SEED LIST. The two components seed their strips from DIFFERENT lists. FrameGeometry.Read uses
equilibrium.ResolvedSupportNodeIds for every solver (MouldComponents.cs:2526-2528); ResultTables.
SupportNodes uses result.Mappings.Supports for TNA and ResolvedSupportNodeIds only for FD
(VisualiseComponents.cs:196-206). For a TNA Result built by the shipped codec the two hold the same set,
because ResolvedSupportNodeIds is derived from Mappings.Supports at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\TnaWorkerResultCodec.cs:161-165.
Nothing in the contract enforces that for a TNA Result deserialised from JSON: ResultDto.Validate
requires resolvedSupportNodeIds to be non-empty only for FD, in range and duplicate-free, and
cross-checks it against the problem's explicit supports only when solver == "fd"
(C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Contracts\ContractDtos.cs:830-865,
the explicit cross-check at :850-864).

THE RULE: the merged component KEEPS FrameGeometry's seed, ResolvedSupportNodeIds, unchanged. Two
reasons. First, FrameGeometry.Read is also what Animate's viewport draws from (its own comment at
MouldComponents.cs:2481-2489 names the two callers), so changing the seed would change the drawing of
the machine as a side effect of a reader merge, which is not what this round is for. Second, the
divergence then surfaces rather than hides: a node named by Mappings.Supports but absent from
ResolvedSupportNodeIds gets no anchor branch, and its reaction becomes a stray, which section 4 reports
out loud.

THERE IS A THIRD READER ON THE OTHER SEED, and keeping FrameGeometry's seed silently breaks an alignment
this spec had not named. SUPPORTS builds its anchor strips from ResultTables.SupportNodes, that is
Mappings.Supports for TNA, at SupportsReaderComponent.cs:278-282, through the same GroupingAdjacency and
ConnectedGroups calls, under a comment at :272-277 saying it makes "Exactly Deconstruct's calls". The
merged reader's Anchor Nodes and its rebranched Reaction Vectors would use
equilibrium.ResolvedSupportNodeIds (MouldComponents.cs:2526-2528). Where the two lists diverge, which is
exactly the case rule 3.7 exists to warn about, Supports' Anchor Along, Anchor Across and Tip Reaction
trees stop pairing branch for branch with the merged reader's Anchor Nodes. The harness records that
promise in prose at tests/native_smoke/Program.cs:141-143: "Supports owns the ground half: anchors by
strip, columns by tree, aligned with Deconstruct's Reaction Points and Frame's Columns." Supports' own
Anchor Along description says it too, in the port text an author reads: "As a TREE branched EXACTLY as
DECONSTRUCT's Reaction Points" (SupportsReaderComponent.cs:112-115). Rule 2.4 deletes Reaction Points, so
that sentence must be repointed at the merged component's Anchor Nodes in the same commit, whatever is
decided below.

FIVE SENTENCES ELSEWHERE IN THE PLUGIN NAME A PORT THIS ROUND REMOVES, found by searching every .cs file
under plugin/native_v02 outside the two merged components for the four removed port names. All five must
be corrected in the same commit or they become false the day this ships. Three are Supports naming
Deconstruct's Reaction Points: its class comment at SupportsReaderComponent.cs:17, its component
description at :45 and the Anchor Along port text at :113. Two are the deliberate DISCLAIMERS that
Deconstruct's Node IDs is per support while their own tree is not, at FitComponent.cs:121 and
ForcesComponent.cs:198; with the port gone the disclaimer has nothing left to disclaim against and the
clause comes out rather than being repointed. Loads' own Node IDs INPUT at SpineComponents.cs:626 and
:634 is a different port on a different component and is untouched, as rule 2.2 already says.

THE RULING, and it is the narrow one. Supports is NOT re-seeded in this round. Re-seeding it from
ResolvedSupportNodeIds would change what Supports reports on a TNA Result without any complaint of his
asking for it, and Supports is a numbers component whose readings he has already walked. So the
branch-for-branch promise between Supports and the merged reader holds ONLY WHILE THE TWO LISTS AGREE,
which is every Result the shipped codec builds (TnaWorkerResultCodec.cs:161-165) and is not guaranteed
for one deserialised from JSON. Rule 3.7's warning is what announces the case where it stops holding, and
that warning's text must name Supports as well as this component, because an author reading two
misaligned trees needs to know which pair went wrong. Re-seeding Supports, or re-seeding the merged
reader from Mappings.Supports, is the alternative and is deferred to section 11 rather than taken here.

3.7 THE DIVERGENCE CHECK. Because rule 3.6 leaves two lists in play, the merged component compares them
as SETS on every solve and raises a runtime Warning when they differ, naming the count on each side, the
node ids in the difference, and Supports as the component whose trees stop pairing. Both lists are
already computed in the same solve, so this costs one set comparison. Without it, rule 3.6's second
reason is a hope rather than a mechanism.

THE COMPARISON IS AN INTERNAL STATIC taking the two id lists and returning the warning STRING, or null
when they agree, so the harness can measure it; SolveInstance does nothing but raise what it returns.
Without that seam rule 10.3(f) cannot be written, because the harness never calls SolveInstance
(Program.cs:12741-12748) and a Warning raised inside one is unreachable from it.

3.8 WHAT THE SET RECORD MUST CARRY. FrameGeometry.Set holds AnchorGroups as List<List<Point3d>>
(MouldComponents.cs:2435), positions only, no node ids. Rebranching Reaction Vectors needs the ids, so
the strips' NODE INDEX lists are added to Net and carried onto Set beside AnchorGroups. This is a
required change whichever seed list wins.

## 4. The stray reaction

4.1 WHAT EXISTS TODAY. A reaction reported at a node that is on no support strip is appended as one
extra branch at the end of Reaction Points and Reaction Vectors, so Reaction Points can carry one branch
more than Support Points (VisualiseComponents.cs:646-664). The code's own comment at :646-649 gives the
reason: "losing it silently would be worse than an extra branch nobody expected."

4.2 THE PROBLEM. With Reaction Points deleted and Reaction Vectors rebranched onto the anchor strips,
that branch has nowhere to go. Deleting it quietly is exactly the failure the original comment was
written against.

4.3 THE RULE. A stray reaction produces NO extra branch on Reaction Vectors, and DOES produce a runtime
WARNING on the component naming how many strays there are and which nodes they sit on. It must not
vanish silently.

THE DETECTION IS AN INTERNAL STATIC, and this is what makes the rule measurable rather than merely
stated. An earlier draft said "Both halves are asserted by the harness", which cannot be done as written:
the harness never calls SolveInstance on anything, only constructors and static contract methods, in its
own words at tests/native_smoke/Program.cs:12741-12748, so "the component wiring around it
(AddRuntimeMessage, ...) is not exercised here". The same limit is recorded again at Program.cs:11989-
11991 for Skin's dropped-cells warning. A Warning raised inside the merged reader's SolveInstance is
therefore unreachable, and the one thing this section calls the whole risk would go unmeasured.

So the stray detection is the SAME internal static rule 3.5 already requires: it takes the reactions
table and the anchor strips and RETURNS (the vector branches, the stray node ids). Both halves of this
rule are then measurable without a document, the branch count off the branches it returns and the stray
report off the ids it returns. SolveInstance does nothing but raise a Warning built from strayNodes.
Rule 10.3(e) asserts over the static rather than over the Warning, and the sentence in the Warning
itself is READ rather than run, as the harness's own convention has it.

4.4 A CORRECTION TO THE BRIEF, and it matters. The design input says at :46-48 that the stray "should
survive as a diagnostic entry". A diagnostics entry in this plugin is written INTO a Result and read
back by Diagnose through a RES input; that is what ResultDiagnostics exists for
(C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\ResultDiagnostics.cs:10-18
and :72-82). NEITHER Deconstruct NOR Frame emits a Result, and the fifteen-port list has no RES output
either, so the merged reader has nowhere to put a diagnostics entry. The runtime warning is therefore
the whole of the report, and it is enough, because section 6 makes Diagnose read exactly that. If Param
wants the stray to travel to the studio instead, the merged reader needs a RES passthrough at output 0
and the component becomes SIXTEEN ports. That is a decision for him and it is named here rather than
assumed away.

4.5 A REACTION AT A SUPPORT THAT CARRIES NONE still holds its slot as a zero vector, as it does today
(VisualiseComponents.cs:634-640). That is what keeps Reaction Vectors item-aligned with Anchor Nodes and
it is unchanged.

## 5. Anchor Lines

5.1 THE DEFECT. The shipped port emits one Line per adjacent pair, so a strip of twenty-one nodes gives
twenty lines: FrameGeometry.AnchorLines at MouldComponents.cs:2683-2695, loop body at :2690-2691. Param
is seeing "20 items and 2 trees" and wants "just be 2 lines" (design input :63-65).

5.2 ONE LINE PER STRIP, AND WHICH KIND IS HIS TO SAY. An earlier draft ruled here for the polyline as
though the point were settled. It is not, and the design input says so in terms at :71-75: "Two forms are
possible and his sentence does not settle it. A straight LINE from the strip's first node to its last is
simplest and is what the present Line-typed port can carry. A POLYLINE through the strip's nodes
preserves a springing that curves in plan, which his vault's anchor clusters appear to do, and needs the
port retyped as a curve. The second is more faithful; the first is what he literally asked for. Put it to
him with that trade named." That instruction was skipped while the sentences either side of it, :63-65
and :77-81, were cited. It is question 12(f) now.

WHAT IS SETTLED EITHER WAY. One line per strip, running the length of it. Two strips give two items, not
twenty. That is his complaint and it is not in doubt.

  (a) THE CHORD. A straight Line from the strip's first node to its last. It is what he literally asked
      for, "should just be 2 lines" (design input :6-13), and a Line is not a polyline. It keeps the port
      typed AddLineParameter as shipped (FrameComponents.cs:159-169), keeps the Rhino-free helper
      FrameGeometry.AnchorLines (MouldComponents.cs:2683-2695) with a two-line change to its body, and
      keeps the harness check that drives that helper, since Line is a managed struct and needs no native
      core. Rule 5.7 already establishes that the strip arrives ordered end to end, so a first-to-last
      chord is a real chord and not a random pair. What it loses is the shape of a springing that curves
      in plan: the chord cuts across it.
  (b) THE POLYLINE. One curve per strip through every node of it. It is the more faithful drawing, and
      the design input's evidence for it at :77-81 is good: Perimeter Lines is built from the same
      grouping machinery and is already a polyline through every node of its loop, precisely because a
      boundary walked around a doubly curved vault does not run straight. What it costs is named in rules
      5.4 to 5.6: the port retypes to AddCurveParameter, the Rhino-free helper is deleted, the work moves
      into FrameGeometry.Build where the harness cannot reach it, and the shipped smoke check
      ValidateFrameAnchorLines is rewritten into something that measures less than it does today.

MY RECOMMENDATION, as a recommendation. The polyline, because his own vault's anchor clusters curve in
plan and a chord across a curved springing is the same defect as a chord across a curved boundary, which
we already refused to draw for Perimeter Lines. But the cost is a real one and it is his canvas: if he
wants the Line he asked for, take (a) and nothing else in this spec has to change except the rules
named below, which are written for (b).

SECTIONS 5.4 TO 5.6 AND 10.2(f) ARE CONDITIONAL ON HIS ANSWER. They set out the polyline. If he takes the
chord, the whole of the change is: FrameGeometry.AnchorLines returns one Line per strip, first node to
last, and an empty branch for a strip of fewer than two nodes; the port stays a Line and stays branched
as Anchor Nodes; the port moves to slot 5 by rule 1.9; ValidateFrameAnchorLines at Program.cs:5116-5177
keeps its reflection over the helper and only its expected counts change; and rule 10.3(c)'s unmeasurable
half disappears, because nothing moves into Build.

5.3 THE PRECEDENT TO COPY, in the same file. Perimeter Lines turns each grouped walk into one polyline
per branch inside FrameGeometry.Build at MouldComponents.cs:2643-2658, guarded on the walk having at
least two points, converting with Polyline.ToNurbsCurve(), and keeping an EMPTY branch when the polyline
will not build so the branch count stays aligned with Perimeter Nodes. Principal Lines is the same shape
at :2633-2641. Anchor strips are walked around the same boundary by the same machinery, so the same
reasoning applies to them; the design input makes this argument at :77-81.

5.4 THE CHANGE, in four parts, IF he takes the polyline of 5.2(b).
  (a) The branch is built INSIDE FrameGeometry.Build beside PerimeterLines, over Net.AnchorGroups, in the
      Perimeter shape, with TWO differences. An earlier draft called it one difference and asserted the
      wrong one.

      FIRST, there is no estimated flag. The Perimeter guard is "!net.PerimeterEstimated && walk.Count >=
      2" (MouldComponents.cs:2648), and there is no anchor analogue of PerimeterEstimated: the anchors
      are NAMED by the Result and are never a heuristic, where a boundary sometimes is. So the anchor
      guard is walk.Count >= 2 alone, followed by the same polyline.IsValid && polyline.Count > 1 test.
      An implementer copying "exactly the Perimeter shape" would otherwise go looking for a flag that
      does not exist.

      SECOND, THE CLOSING POINT IS NOT RULED OUT, it follows the same test the perimeter uses. The
      earlier draft said an anchor strip is an open run along a springing and never a loop, so nothing
      corresponding to net.PerimeterCloses applies. That was assumed rather than checked, and the
      grouping code contradicts it. MouldGeometry.ConnectedGroups, the very call that builds the anchor
      strips at MouldComponents.cs:2575-2576, contemplates a group with no end explicitly: "An END is a
      node with one neighbour inside the group. A closed loop has none, and then any node will do; taking
      the lowest keeps it deterministic" (:1099-1105), and its doc comment says a closed loop "is walked
      from its lowest node and comes back round" (:1056-1059). PerimeterCloses exists precisely because
      groups from that routine can close (:2585-2593, consumed at :2651-2652). A vault anchored right
      around its springing gives exactly such a ring, and the earlier rule would have handed back a
      polyline one segment short of closing with nothing said.

      So: a strip whose last node is adjacent to its first IN THE GROUPING GRAPH closes, computed exactly
      as net.PerimeterCloses is at MouldComponents.cs:2589-2592 but without the estimated term and with
      walk.Count >= 3, and the closing point is appended as :2651-2652 appends it. The flag is carried on
      Net as AnchorCloses, a bool[] beside AnchorGroups, and on Set beside AnchorLines.
  (b) It is carried on the Set record as AnchorLines, List<List<Curve>>, beside PerimeterLines
      (MouldComponents.cs:2437).
  (c) The port is retyped from AddLineParameter (FrameComponents.cs:159) to AddCurveParameter, matching
      Principal Lines at :93 and Perimeter Lines at :126.
  (d) The emit becomes OutputTree.Curves instead of OutputTree.Lines. The Curve-typed helper already
      exists at MouldComponents.cs:45.
The standalone FrameGeometry.AnchorLines helper is DELETED. It has exactly one caller in the plugin,
FrameComponents.cs:202-203, and one in the harness, which section 10 replaces.

5.5 WHY A POLYLINE CANNOT BE FIXED IN PLACE, and why a chord can. FrameGeometry.AnchorLines is
deliberately Rhino-free, and its own doc comment says why at MouldComponents.cs:2679-2682: "the harness
can drive it without a Rhino: Line is a managed struct." The Read/Build split at :2384-2390 states the
same rule for the class. Polyline.ToNurbsCurve() needs the native core, so a polyline cannot be built
where that method lives, which is why part (a) moves the work rather than editing the helper. A CHORD
needs no native core at all: it is one Line from strip[0] to strip[strip.Count - 1], so option 5.2(a)
edits the helper in place, keeps it Rhino-free, and keeps everything the move costs. That asymmetry is
the substance of the trade in 5.2 and it is why the question is worth putting to him rather than
deciding here.

5.6 A ONE-NODE STRIP GIVES AN EMPTY BRANCH, and so does an empty one, under either form. The Perimeter
guard is walk.Count >= 2 followed by polyline.IsValid && polyline.Count > 1
(MouldComponents.cs:2648-2655), less the estimated term by rule 5.4(a); the same guard applies to the
polyline, and the chord's guard is the same count test with no polyline half to it. Branch {i} of Anchor
Lines stays branch {i} of Anchor Nodes, which is the property that makes the pair readable, and it is
preserved by adding the empty branch rather than skipping it. This is the same rule the shipped port
already keeps (FrameComponents.cs:162-169), only with one item per branch instead of n-1 lines.

5.7 NODE ORDER NEEDS NO SORTING. "needs to go left to right in order" (design input :63-65) is already
satisfied. MouldGeometry.ConnectedGroups collects each connected component, finds an END (a node with at
most one neighbour inside the group) at MouldComponents.cs:1102-1105, and walks from there at :1107-1127,
so an open anchor strip arrives ordered end to end. The grouping is also independent of the order of the
ids handed in: they are pooled into a HashSet and iterated with pool.OrderBy(i => i) at :1071-1076, and
the groups come back in order of lowest node index, which the doc comment at :1062-1065 names as the
stability property. No sort is needed and none should be added.

5.8 ONE HONEST CAVEAT, which the design input does not mention because it was not looked for. A FORKED
group cannot be walked in one pass, and whatever the walk could not reach is APPENDED in index order
rather than dropped (MouldComponents.cs:1129-1137). A forked anchor cluster therefore produces a
polyline that runs the main branch and then jumps to the stragglers. This is pre-existing, applies
equally to Perimeter Lines today, and is visible on the canvas rather than silent. It is recorded rather
than fixed, and the harness check in section 10 documents the behaviour instead of pretending it cannot
occur.

## 6. Diagnose, document-wide

6.1 THE RULE. Diagnose's Result input becomes OPTIONAL. Unwired it scans the whole document and reports
every Ananke component's complaints. Wired it reports that chain alone, which is what it does today. One
port, two behaviours (design input :141-146).

6.2 THE REGISTRATION CHANGE is one line: parameters[0].Optional = true after the AddParameter call at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\DiagnoseComponents.cs:46-52,
the same idiom Export uses at DeliveryComponents.cs:241. Nothing else about Diagnose's registration
moves: its six outputs (DiagnoseComponents.cs:57-78) keep their names, nicknames, types and order.

6.3 THE MODE TEST. Chain mode when data.GetData(0, ref goo) succeeds and goo.Value is a ResultDto, which
is the existing guard at DiagnoseComponents.cs:83-85. Document mode otherwise, which INCLUDES a wire that
is present but carries nothing. Nothing about chain mode changes: Collect, CrossChecks, Group and Render
(:107-259) run exactly as they do now. THE ANSWER IS RECORDED ON THE COMPONENT as it is decided, because
rule 7.3(b)'s handler must read the same answer this test gives and not a second test of its own.

6.4 WALKING THE DOCUMENT, exact API.
  (a) GH_Document? document = OnPingDocument(); if (document is null) emit empty and return. This is the
      pairing the plugin already uses at DeliveryComponents.cs:213-216 and NativeComponentBase.cs:675-677.
  (b) Iterate document.Objects. It is documented as "a list of all normal, top-level objects"
      (C:\Program Files\Rhino 8\Plug-ins\Grasshopper\Grasshopper.xml:24050-24054).
  (c) Skip the Diagnose instance doing the scanning. It must not report its own chin or its own messages.
  (d) CLUSTERS ARE PROPOSED AS OUT OF SCOPE, and this is a DEPARTURE FROM HIS WORDS rather than an
      obvious boundary. He asked for a component that reads "every component of our plugin" (design
      input :117-120). A component inside a cluster is one of our components, and this rule would not
      read it. The departure is proposed for a reason and the reason is not a settled fact:
      document.Objects is top-level only; a GH_Cluster keeps its own inner GH_Document reachable only
      through GH_Cluster.Document(System.String password) (Grasshopper.xml:10429), and
      GH_Document.ObjectCount at :24045 counts the same top-level set. So descending means calling a
      password-taking method, and what it should do with a cluster that has a password is a question
      nobody has answered. That is why it is proposed as deferred, and it is question 12(g) rather than
      a ruling. It is also the one exclusion an author discovers by wondering why a component he can see
      reports nothing, so rule 7.4's description sentence carries it either way: "Components inside a
      cluster are not read."

6.5 TELLING OUR COMPONENTS FROM FOREIGN ONES. The test is ASSEMBLY IDENTITY:
obj.GetType().Assembly == typeof(DiagnoseComponent).Assembly. It is exact, costs one reference
comparison, and needs no Grasshopper lookup.

The obvious test is wrong and must not be used. `obj is NativeComponentBase` catches only thirteen of
the twenty-one components: the eight task-capable ones derive from NativeTaskComponentBase<TResult>,
which derives from GH_TaskCapableComponent<TResult> and NOT from NativeComponentBase
(NativeComponentBase.cs:539 against :696-697). The eight are Export (DeliveryComponents.cs:81), Backend
Health (FormFindingComponents.cs:17-18), Import Pieces (PiecesComponents.cs:84-85), Skin
(SkinComponents.cs:45-46) and the four solvers (SolverComponents.cs:32, :536, :1033). Export and Import
Pieces are the two Param named by name, so the wrong test would miss precisely the components the ruling
was about.

Category is also rejected. ComponentCategories.Category is the string "Ananke COMPAS"
(NativeComponentBase.cs:31), passed to every base constructor at :551-557 and :711-717, but a string any
plugin could register is weaker than an assembly reference. GH_ComponentServer.FindAssemblyByObject
(Grasshopper.xml:16740) against the GH_AssemblyInfo Guid d4c49da9-26d9-4c0d-89c0-958fa3ec5834
(C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\AssemblyInfo.cs:50-51)
is equally sound and strictly more work. Assembly identity is the one to write.

The predicate is an internal static taking an IGH_DocumentObject and returning bool, so the harness can
measure it without a document (section 10).

6.6 READING WHAT EACH COMPONENT HAS TO SAY.
  (a) Runtime messages are PER OBJECT, not on the document. Cast to IGH_ActiveObject and call
      RuntimeMessages(GH_RuntimeMessageLevel level), documented at Grasshopper.xml:8917-8923 as "the
      list of cached runtime messages that were recorded during solver-time processes".
  (b) There is no all-levels overload: the method takes ONE level, and GH_RuntimeMessageLevel has exactly
      four members, Blank, Remark, Warning and Error (Grasshopper.xml:8814, :8819, :8824, :8829). A full
      scan is THREE calls per object: Remark, Warning, Error. Blank is the "nothing recorded" state, not
      a list, and is not called.
  (c) Remark MUST be read. The plugin deliberately places content there: Display raises "FD result: no
      reciprocal diagram." and "Metric H unavailable for FD result; used F magnitude." as Remarks at
      VisualiseComponents.cs:1285-1297, under a comment at :1277-1284 explaining that these are Display's
      own readings which no other component can say. Section 8 then moves several retired ports' content
      onto Remarks, so a Warning-and-Error-only scan would lose most of what this round is building.
  (d) GH_Document offers no per-object message enumeration at all. A search of
      C:\Program Files\Rhino 8\Plug-ins\Grasshopper\Grasshopper.xml for a GH_Document member matching
      *Message returns nothing; the nearest members are the events ObjectsAdded (:24479), ObjectsDeleted
      (:24486), ModifiedChanged (:24472), SolutionStart (:25165) and SolutionEnd (:25171).
  (e) The chin line is GH_Component.Message (Grasshopper.xml:13352), so reading it needs a cast to
      GH_Component, not to IGH_ActiveObject or IGH_DocumentObject. Both plugin base classes derive from
      GH_Component, directly at NativeComponentBase.cs:539 and through GH_TaskCapableComponent at :696-697.
  (f) ONE ITEM TO CONFIRM AT IMPLEMENTATION. The shipped documentation for AddRuntimeMessage says "Valid
      message type flags are Warning and Error" and "Only Warnings and Errors are recorded"
      (Grasshopper.xml:8909-8915 for the interface, :9021-9028 for GH_ActiveObject). The plugin
      nevertheless adds Remarks (VisualiseComponents.cs:1287-1296) and its comment assumes an author sees
      them. I could not resolve this from the code: it needs one manual check in Rhino that
      RuntimeMessages(Remark) returns what AddRuntimeMessage(Remark, ...) put there. If it does not, rule
      6.6(c) fails and section 8's retired content must move to Warnings instead, which changes what the
      balloon looks like. Check this before building section 8.

6.7 NAMING A COMPONENT IN THE REPORT. Name and NickName come off IGH_InstanceDescription, which every
document object implements; InstanceGuid off IGH_DocumentObject. Two of the same component on one canvas
must be DISTINGUISHABLE IN WHAT THE AUTHOR READS, and the nickname alone cannot do it: every instance of
one component type ships the same nickname, because it comes from the base constructor, so two Frames
give two branches both reading "FR". An earlier draft answered this by keeping the InstanceGuid "for the
digest of section 7", which does nothing for the reader, since that digest is internal to rule 7.3(c) and
is never emitted. Rule 6.8 carries the arithmetic instead. I have not read those three members' entries
in Grasshopper.xml and am naming them from the plugin's own use of Name and NickName throughout rather
than from the API documentation.

6.8 THE OUTPUT SHAPE IN DOCUMENT MODE. The same six ports, filled differently.
  - SOURCE: one branch per scanned component that has anything to say, the source string being its
    NickName. A component with no messages and no chin gets no branch.
  - CODE: runtime messages carry no code, so one is synthesised: runtime.error, runtime.warning,
    runtime.remark, and runtime.chin for the Message line. This keeps the port's documented promise that
    a code is "namespaced by its source" (DiagnoseComponents.cs:68-70) in spirit, and says plainly that
    the entry came from the balloon rather than from a Result.
  - SEVERITY: error, warning, info. Remark maps to "info" and the chin maps to "info", because Diagnose's
    own vocabulary is ok, info, warning, error (DiagnoseComponents.cs:71-72) and has no "remark".
  - MESSAGE: the message string verbatim; for the chin, the Message line verbatim.
  - VALUE: NaN throughout. Runtime messages carry no number, and the port already documents NaN as the
    placeholder that keeps the tree aligned (DiagnoseComponents.cs:75-78).
  - TEXT: one block per component, headed "<NickName> (<Name>):" where the nickname is unique on the
    canvas and "<NickName> (<Name>) <first eight characters of InstanceGuid>:" where it is not, holding
    "  [severity] message" lines in
    the error, warning, info order the existing Rank gives at DiagnoseComponents.cs:211-217, then
    "  chin: <Message>" where a chin is set. Then a closing line naming how many of our components were
    found and how many had nothing to say. When none of our components is on the canvas, the text says so
    in a sentence rather than coming back empty.
  - There is NO "solver report:" block and no "not yet run on this Result:" block in document mode. Both
    read a Result (DiagnoseComponents.cs:239-257) and there is none.
  - THE CHIN: the same rule as today, errors / "<n> warnings" / clean (DiagnoseComponents.cs:96-98),
    computed over the scan.

6.9 WHAT DOCUMENT MODE DOES NOT READ, stated in the description so nobody hunts for it. It does not read
the diagnostics carried INSIDE a Result.

AN EARLIER DRAFT SAID IT COULD NOT, and that was false. It said those diagnostics "live on a wire, not on
the document", which the rest of this spec contradicts twice: rule 1.8 has a constructor walk
Params.Output, and rule 7.3(b) reads Params.Input[0].SourceCount, citing NativeComponentBase.cs:99. A
wire's data is held in the PARAMETERS of document objects, and Grasshopper documents IGH_Param.
VolatileData as "the instance of the volatile data tree stored in this parameter"
(C:\Program Files\Rhino 8\Plug-ins\Grasshopper\Grasshopper.xml:29995, read today). So a scanned
component's output parameters holding ResultGoo are reachable from exactly the walk rule 6.4(b) already
performs, and harvesting the Results on them is possible.

IT IS A CHOICE, and it is mine rather than his, so it goes to him as question 12(h). Three reasons for
it. First, a scan reads volatile data left by the PREVIOUS solution, so the entries reported would be
one solution old in general and stale in particular, and section 7 exists precisely because Diagnose has
no data dependency to make them fresh. Second, a wired Diagnose already reads them EXACTLY, through the
chain-mode path this round does not touch, so the same author has a correct reading available for one
wire. Third, the same Result travels down several wires and appears on several parameters, so a
document-wide harvest reports one study's entries many times over unless it dedupes by identity, which
is more machinery than this round should carry.

WHAT THAT COSTS, named rather than hidden. It removes from his "reveal any problems" (design input
:117-120) the entire class of problem ResultDiagnostics exists to carry (ResultDiagnostics.cs:10-18),
which is most of what Forces, Fit, Supports and Skin have to say. That is the reason to keep wiring
Diagnose when a definition holds two studies and only one is misbehaving, and it is the second half of
why the input stays rather than being removed. If he wants the harvest, rule 6.8 gains a seventh source
of entries and rule 7.3(c)'s digest gains their content, and the staleness has to be said on the face of
the report.

## 7. The solution-order trap

This is the part most likely to be got wrong. It is stated as lettered rules.

7.1 THE PROBLEM, stated correctly. It is not "one solve behind". Grasshopper solves only EXPIRED
objects, so a component with no wired input is never expired by upstream data and holds its FIRST answer
for the rest of the session. The plugin already ships proof that this is real rather than theoretical:
Backend Health registers no inputs at all (FormFindingComponents.cs:33-36) and carries no expiry
mechanism of any kind.

7.2 THE REMEDY IS TWO-PART. Something must EXPIRE Diagnose when the document changes, AND the re-solve
must be SCHEDULED rather than forced. Either half alone fails: expiry without scheduling recomputes
inside a running solution, and scheduling without expiry schedules a solution in which Diagnose is not
expired and therefore does not run.

7.3 THE RULES.

(a) SUBSCRIBE IN AddedToDocument, UNSUBSCRIBE IN RemovedFromDocument. The event is GH_Document.
    SolutionEnd, documented at Grasshopper.xml:25171 as "raised whenever a new solution request has been
    handled. Even if the document is locked". It is the one event that fires after every solve, which is
    exactly when the messages Diagnose reads have just been rewritten. ObjectsAdded (:24479) and
    ObjectsDeleted (:24486) may be subscribed as well, but they are NOT sufficient on their own: a
    component's messages change without any object being added or removed.

(b) THE HANDLER RETURNS IMMEDIATELY IN CHAIN MODE, AND CHAIN MODE IS THE SAME TEST SOLVEINSTANCE USES AT
    RULE 6.3, not SourceCount. An earlier draft tested Params.Input[0].SourceCount > 0, the plugin's own
    idiom for "is this input wired" at NativeComponentBase.cs:99, and that disagrees with rule 6.3 on the
    case that matters: a Result wire is PRESENT BUT CARRIES NOTHING, because the upstream solver errored,
    or the upstream component is disabled, or the wire feeds null. SolveInstance would then take the
    document branch and run a full scan, while the handler refused to expire the component, so the scan
    would be computed once and frozen for the rest of the session. That is exactly the failure rule 7.1
    is written against, reintroduced by the one case nobody enumerated, and it fails the acceptance
    criterion of (d) in a way the harness cannot catch, because 10.3(j) makes settling a manual check.

    THE RULE. The component RECORDS WHICH MODE ITS LAST SOLVE RAN IN, on itself, at the point rule 6.3
    decides it, and the handler reads that field. A wire that carries no Result puts the component in
    document mode, and document mode must schedule, or a broken upstream freezes the panel. When the
    Result really is present Diagnose has a data dependency, Grasshopper orders it correctly, and none of
    this machinery runs at all.

(c) THE ANTI-LOOP CONDITION, named explicitly, because this is where such components fail. If the handler
    schedules unconditionally, the scheduled solution ends, raises SolutionEnd, schedules another, and
    the document never rests. THE LATCH IS ON THE CONTENT, not on a flag and not on a timer. The handler
    computes a DIGEST of the scan, and schedules ONLY when that digest differs from the digest Diagnose
    last EMITTED. The digest is an ordinal string built from each scanned component's InstanceGuid, its
    three message lists in the order Remark, Warning, Error, and its chin, with the components in a
    stable order (InstanceGuid ascending). Two things matter about it: it is compared against what was
    last EMITTED rather than what was last computed, and it is stored on the component.

(d) THE ACCEPTANCE CRITERION FOR (c) IS TWO SOLVES. Solve one produces the answer, solve two confirms the
    digest is unchanged and schedules nothing, and the document rests. Anything that settles in three or
    more, or does not settle, is a defect in the digest and not a tuning problem.

(e) SCHEDULE, NEVER RECOMPUTE. The pairing is document.ScheduleSolution(5, _ => ExpireSolution(false)),
    from a callback OUTSIDE SolveInstance, with a null-document guard first. This is exactly the plugin's
    existing precedent at DeliveryComponents.cs:209-217, whose comment at :200-208 gives the reasoning:
    "Scheduling asks the document for the re-solve on its own terms; a component with no document does
    nothing at all." ExpireSolution(true) recomputes on the spot and is the classic loop.

(f) DELAY 5, NEVER 0. A delay of 0ms is documented as running the next solution RECURSIVELY within the
    current one, with an explicit stack-space warning and GH_Document.SolutionDepth (Grasshopper.xml:25227)
    named as the way to see how deep it has gone; the text is at Grasshopper.xml:25320-25327 and repeats
    on both overloads. The in-repo precedent uses 5 (DeliveryComponents.cs:216). Use 5.

(g) EXPIRE ITSELF ONLY. Never the document, never a scanned object. Expiring a component CLEARS its
    runtime messages before SolveInstance runs; the base class records this as the reason a load-time
    warning must be re-added every solve, at NativeComponentBase.cs:631-637 and again at :790-808. If
    Diagnose expired the document it would wipe the very messages it went back to read. ExpireSolution
    (false) on `this` is the whole of it.

(h) CAP THE CONSECUTIVE RE-SOLVES AT THREE. A foreign component whose messages genuinely change on every
    solve would make the digest differ for ever, and rule (c) alone would schedule for ever. After three
    consecutive scheduled re-solves without the digest settling, Diagnose stops scheduling and adds a
    Remark on ITSELF saying the document did not settle and naming the component whose entry changed. The
    counter resets whenever the digest matches. A document that will not settle is a document where
    something else is oscillating, and Diagnose should say so rather than spin.

7.4 WHAT IS STILL TRUE AFTER ALL THIS, and belongs in the component's own description. On the very first
solve after a file opens, Diagnose may report before some components have run. The rules above make it
correct within two solves rather than correct immediately, and that limit is a property of the host
rather than of this design. The description says: "Unwired, this reads the whole document and settles one
solve behind: what you see is the state at the end of the previous solution. Wire a Result in when you
want a guaranteed reading of one chain. Components inside a cluster are not read."

## 8. Retiring the other diagnostics ports

8.1 THE RULING. "This goes for all other components with a diagnostics output even the importer and
exporter" (design input :118-120, :148-153). A component should raise its problems where the author
already looks rather than hand back a text output that must be wired to a panel to be read.

8.2 THE COMPLETE LIST, verified by searching the whole of plugin/native_v02 for text ports named
Diagnostics, Status, Report, Notes or Log. Four such ports exist; THIS ROUND RETIRES THREE:
  (a) EXPORT, "Status" (ST, text, item), DeliveryComponents.cs:343-353.
  (b) IMPORT PIECES, "Diagnostics" (D, text, item), PiecesComponents.cs:155-164.
  (c) BACKEND HEALTH, "Report" (Out, text, item), FormFindingComponents.cs:61-65, subject to 8.6(d).

SKIN IS NOT RETIRED HERE, although its Diagnostics port (D, text, item, SkinComponents.cs:168-180) is the
fourth. docs/superpowers/specs/2026-09-01-skin-buildability-design.md, dated the same day and running in
the same wave, owns that removal at its rule 9.2.2, gives Skin a RES output at index 0 at its rule 9.4.1,
and routes Skin's diagnostics into RESULT DIAGNOSTICS ENTRIES through ResultDiagnostics.Replace at its
rule 9.3.3, with a full code list. That is a different destination from the one rule 8.5 sets, and its
rule 12.10(a) rewrites the very harness pin rule 10.2(j) names. This round touches neither Skin's
registration nor its harness pin at tests/native_smoke/Program.cs:100-102. An implementer working from
this spec alone would otherwise remove the port a second time, send its content to the balloon instead of
into the Result, and write a pin the other spec overwrites.

8.3 A CORRECTION, now narrowed. Skin's Diagnostics has NOT already been removed, as the design input
implies in the past tense at :149-151; the port is live at SkinComponents.cs:168-180 and pinned by the
harness at tests/native_smoke/Program.cs:102. What has changed since that observation was written is that
the removal now has an owner: the skin-buildability spec's rule 9.2.2 rather than the skin round design
input's proposal at docs/superpowers/specs/2026-09-01-skin-round-design-input.md:207-215. The record is
corrected here and the work stays there.

8.4 THE SECOND HALF OF THE RULING IS NOT POSSIBLE AS WRITTEN FOR THESE THREE, and this is the most
important finding in this section. "Runtime messages and diagnostics entries" (design input :148-153)
requires somewhere to put a diagnostics entry, and a diagnostics entry in this plugin lives inside a
ResultDto (ResultDiagnostics.cs:10-18). NONE of the three components this round retires emits a Result:
  - Export's only outputs are JSON and Status (DeliveryComponents.cs:325-354).
  - Import Pieces' are Meshes, Keys, Supports, Base Mesh, Diagnostics (pinned at Program.cs:274-282), and
    its ONLY input is a Path (PiecesComponents.cs:105-114), so there is no Result anywhere in its chain
    to write into even in principle.
  - Backend Health has no inputs at all (FormFindingComponents.cs:33-36).

Skin is the counter-example and the reason the two rounds differ: the skin spec's rule 9.4.1 GIVES it a
Result to write into, so the second half of the ruling is possible there and is taken there. Where a
component has a Result, the entries are the better home; where it has none, the balloon is the whole of
what is available.

8.5 THE RULE THAT FOLLOWS, with the arithmetic. Every retired port's content becomes RUNTIME MESSAGES
ONLY, at the level its content deserves: a real fault is a Warning or an Error, everything else is a
Remark. ONE MESSAGE PER FACT, NOT ONE PER PORT, because Diagnose's document scan emits one tree item per
message (rule 6.8), so a single Remark holding a nine-line block and nine Remarks look completely
different on the canvas and the spec must not leave the choice open. Per component:
  - IMPORT PIECES raises one Remark per line of what its D output carried (schema, units, piece count,
    courses, thickness, the degenerate_dropped keys, the metres factor, whether base_mesh was present,
    the branch-path note: PiecesComponents.cs:155-164), and one WARNING per piece that failed to build.
  - EXPORT raises one Remark per written path, one Remark per live line, and keeps its existing Warnings
    unduplicated. See 8.6(c) for why the live lines cannot simply go.
  - BACKEND HEALTH, subject to 8.6(d), raises one Remark per roll-up line.
Diagnose's document scan is where they are read, which is the entire point of section 6 and the reason
rule 6.6(c) insists on reading Remark. The Result-diagnostics half is a separate decision, per component,
and of the three retired here only Export has a Result it could pass through; adding a RES output to
Export would also let Diagnose sit AFTER it in a chain, which it cannot today. That is put to Param
rather than decided here.

8.6 WHAT IS GENUINELY LOST, named honestly rather than minimised.
  (a) A Remark cannot be wired. It cannot reach a panel, a File Path component or a text join.
  (b) Export's LATCHED written-file paths are the one piece of retired content an author plausibly wires
      onward. They are latched on the component precisely so a one-shot Button write stays visible after
      the button releases (DeliveryComponents.cs:96-98, the emit at :617-632). If Status goes, the paths
      go to the balloon and stop being data. This is the real trade in this section and Param should see
      it stated before it is built.
  (c) EXPORT'S STATUS CARRIES THREE THINGS, NOT TWO, and an earlier draft counted two. Its WARNING BLOCK
      is already a verbatim copy of the runtime messages, by design (DeliveryComponents.cs:633-637, under
      the comment at :611-616 "the warnings are repeated here because a bubble is not a value and the
      chin holds one line"), so retiring that third is a pure deletion of a duplicate. Its WRITTEN PATHS
      are the latched half of (b). Its LIVE LINES are the third, one per kind, at
      DeliveryComponents.cs:627-632, and they are not duplicated anywhere: only the FIRST reaches the
      chin, through FirstLine(uploaded) at :641-643, and a live outcome becomes a Warning only when it
      both failed AND reached Done (:594-600). So a two-kind push whose second kind fails while the first
      succeeds loses the second outcome entirely when Status goes, unless the live lines move to Remarks
      as rule 8.5 requires.
  (d) BACKEND HEALTH IS A DIFFERENT CASE and needs Param's word. Its Report is not a diagnostics
      side-channel; it is the component's product. The other four outputs are Ready, Python, Packages and
      Capabilities (FormFindingComponents.cs:41-65), and Report is the readable roll-up of the same facts
      plus the launch error, which is already raised as an Error at :92 when the worker fails. Retiring
      Report leaves a component whose whole purpose is inspection with no readable summary. His sentence
      named "the importer and exporter" and not this one. Recommendation: retire the FAILURE half, which
      is already duplicated on the balloon, and keep the port for the success roll-up. Flagged, not
      decided.

8.7 WHAT IS NOT RETIRED, and must be said plainly.
  (a) THE DIAGNOSTICS CARRIED INSIDE THE RESULT STAY. They travel with the data, reach Export, and form
      part of the contract the studio receives (design input :155-157). The document scan is for the
      author at the canvas; the Result's entries are for the data. Two readers, two surfaces, both stay.
  (b) DIAGNOSE'S OWN TEXT OUTPUT STAYS. It is the panel itself, not a per-component diagnostics
      side-channel (DiagnoseComponents.cs:57-62).

## 9. Migration

9.1 WHAT A SAVED DEFINITION SEES. With a new GUID (rule 1.4), both Deconstruct and Frame load as
ORPHANED OBJECTS. Grasshopper shows its own placeholder for a component whose GUID no assembly claims,
the wires stay attached to the placeholder, and the author deletes both and places one merged reader.
This is the Monitor outcome and it was chosen for the same reason
(docs/superpowers/specs/2026-08-31-readers-design.md:68-75).

9.2 THE LOAD WARNING DOES NOT COVER THIS CASE, and the spec should not pretend it does.
ParameterIdentity.Mismatch compares an ARCHIVED port list against a REGISTERED one
(NativeComponentBase.cs:321-407). An orphan has no registration to compare against, because the class no
longer exists. So the author gets Grasshopper's missing-component placeholder and nothing from us. That
is the honest reading and it is worse for the author than a warning would be; it is accepted because the
alternative in 9.3 is worse still.

9.3 WHAT GUID REUSE WOULD DO, so the choice is visible. Suppose the merged component reused Deconstruct's
GUID. Grasshopper reattaches an archived wire to the live port at the same INDEX
(NativeComponentBase.cs:620-627). Old slot 0 was Member Lines (Line tree) and new slot 0 is Mesh (Mesh
item), so that wire lands on an incompatible port; old slot 8 was Reaction Vectors and new slot 8 is
Columns; and old slot 4, Support Points, lands on new slot 4, Anchor Nodes, which is the one pairing that
happens to be right and is right by accident. Mismatch would open with the counts, ten outputs archived
against fifteen registered, list 'Member IDs', 'Node IDs', 'Reaction Points' and 'Support Points' as
removed (:362-366), fail the pure-append test because removed.Length is not zero (:385-392), and close
"wires may now sit on the wrong port, check every one" (:400-406). One sentence for fifteen silently
relanded wires. Meanwhile Frame orphans anyway, because only one GUID can be reused. So reuse buys
nothing and costs clarity, and rule 1.4 stands.

9.4 THE ANCHOR LINES REORDER IS SAFE ONLY BECAUSE OF THE MERGE. Anchor Lines was appended at slot 9 to
avoid moving anyone's wires, and both components carry a comment saying the append has to stay
(VisualiseComponents.cs:413-415 and FrameComponents.cs:156-158). Moving it to slot 5 is exactly the
migration those comments exist to prevent. It is safe here because a new GUID means there are no saved
wires to move. A spec that reordered Frame's ports WITHOUT merging would break saved definitions with
nothing but a load-time warning to show for it, and this is the sentence that records why the two changes
travel together.

9.5 DIAGNOSE MIGRATES CLEANLY. Making input 0 optional changes no name, no count and no order, so
Mismatch says nothing (NativeComponentBase.cs:333-334, both sides agreeing is silent). A saved definition
with a Result wired into Diagnose keeps working identically, in chain mode.

9.6 THE THREE RETIRED TEXT PORTS DO MOVE WIRES. Each is the LAST output on its component (Export's Status
at slot 1 of 2, Import Pieces' Diagnostics at slot 4 of 5, Backend Health's Report at slot 4 of 5), so
removing it is a pure truncation: no surviving port changes index,
and Mismatch reports a count change naming the removed port and closing "wires may now sit on the wrong
port" (:400-406). That close is harsher than the truth here, because nothing above the removed port
moved, but the pure-append branch at :385-392 only softens the message for ADDITIONS. A pure-truncation
branch would be the honest counterpart. Recorded as an optional improvement, not required by this round.

## 10. Verification

The harness is
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke\Program.cs.

10.1 A WARNING ABOUT GREEN RUNS BEFORE ANY OF THIS. There is a OneDrive edit-conflict artefact in the
harness's own release folder, verified present today:
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke\bin\Release\net8.0-windows\Ananke.COMPAS.NativeSmoke (# Edit conflict 2026-08-31 5sa2jeC #).dll.
On this machine a clash file can hold the NEW content while the original path keeps the OLD, so a green
run taken over a stale binary proves less than it looks. Delete the artefact and rebuild clean before
trusting any result in this section.

10.2 EXISTING CHECKS THAT MUST CHANGE.
  (a) VisualiseContracts, the DeconstructComponent entry at Program.cs:76-94, is deleted, and the
      FrameComponent entry at :161-177 is replaced by ONE entry for the merged component pinning the
      fifteen output NAMES in the order of table 1.9.
  (b) SpineComponentContracts, the FrameComponent entry at Program.cs:264-273, is replaced by the merged
      component's Name, NickName, tab "04 Read", input nicknames { "RES" } and the fifteen output
      NICKNAMES in order. Its comment at :264-267 says Frame is pinned nickname by nickname "because it
      is the one component whose whole job is the ORDER of its ports"; that is now doubly true.
  (c) The component-count pin at Program.cs:503-514. Two components become one, so 21 becomes 20 for this
      sub-project alone. This number is shared with the columns and skin rounds running in the same wave
      and must be reconciled against whatever they do; it is named here as a dependency rather than
      asserted as final.
  (d) NativeIconEntries at Program.cs:292-319: the DeconstructComponent row at :306 and the FrameComponent
      row at :312 become ONE row. With the name of rule 1.2 that is ("result_breakdown", "DE") and the
      "frame" key is retired.
  (e) plugin/icons/icon-map.json. Its native_components array holds 21 entries today, verified by reading
      the file; it becomes 20, and the harness enforces one entry per component at Program.cs:13940-13966.
      Icons regenerate through plugin/icons/generate_icons.py and --check stays byte-green
      (docs/superpowers/specs/2026-08-31-readers-design.md:127-128).
  (f) ValidateFrameAnchorLines at Program.cs:5116-5177, IF he takes the polyline of 5.2(b). It is
      REWRITTEN, and it breaks before it fails: it reflects over the helper's PARAMETER TYPE at
      :5120-5124 to build its inputs, so deleting FrameGeometry.AnchorLines takes the test out at the
      reflection rather than at an assertion. Its replacement drives FrameGeometry.Read, which is
      Rhino-free by design (MouldComponents.cs:2384-2390), and asserts what rule 10.3(c) marks as
      measured. The Polyline-to-Curve conversion inside Build cannot be smoke-tested without Rhino,
      exactly as Perimeter Lines' conversion cannot be today; that gap is stated rather than papered
      over, and rule 10.3(c) names the one way to narrow it. If he takes the chord of 5.2(a) this check
      keeps its reflection and only its expected counts change, and the gap does not open at all.
  (g) ValidateDeconstructColumnTrees at Program.cs:2891-2896 and ValidateDeconstructForceLines at
      :3133-3145 both call RequireComponentType(plugin, "DeconstructComponent") and must be re-pointed at
      the merged type.
  (h) The ParameterIdentity.Mismatch PASS MESSAGE at Program.cs:1379-1399 narrates the last reshape by
      name: "Deconstruct's slim lists 'Thrust Mesh', 'Columns', 'Heads' and 'Feet' as removed... Frame's
      pure append names 'Anchor Lines'" (:1392-1396). Its fixtures are hand-built name arrays rather than
      live components (the Deconstruct-slim fixture is at :5617-5652), so the fixtures may stay and only
      the prose needs correcting; but the prose is a claim about components that will no longer exist and
      must not be left standing.
  (i) The ResultTables order pass message at Program.cs:1360 and the stray-branch sentence at :5441 both
      name Deconstruct; prose only, but they are claims and should be true.
  (j) Retiring the three text ports touches two pinned places: Export's outputs at Program.cs:183-189 and
      Import Pieces' output nicknames at :274-282. SKIN'S PIN AT Program.cs:100-102 IS NOT TOUCHED HERE:
      rule 8.2 leaves Skin to its own spec, whose rule 12.10(a) rewrites that same pin to inputs {Result,
      Pattern, Size, Course Height, Min Piece} and outputs {Result, Cells, Surface}. EXPORT'S PIN IS
      WRITTEN BY BOTH ROUNDS: this one drops Status from its outputs, and skin rule 12.10(b) reorders its
      inputs to the nine {Result, Cells, Courses, Column Radius, Path, Name, Studio, Live, Write}. The two
      edits do not conflict, one being the output half and the other the input half, but whichever lands
      second must be written against the first rather than against the shipped file, and this is the one
      place in the two specs where the same line is claimed twice. Backend Health appears in
      NativeIconEntries at :318 and in neither contract table, so retiring its Report breaks no port pin,
      which is itself worth noting as a gap.

10.3 NEW CHECKS NEEDED.
  (a) NO TWO OUTPUTS OF ANY ONE COMPONENT SHARE A NICKNAME, and no two inputs do. Run it over every
      component, not just the merged one. This is the check that would have caught Mesh M against Member
      Lines M, and Grasshopper will not catch it for us.
  (b) The merged reader's fifteen outputs by NAME and by NICKNAME in order, with Anchor Nodes at index 4
      and Anchor Lines at index 5, and its one input at index 0.
  (c) ANCHOR LINES, split into what is measured and what is not, because the driver named here cannot
      make every assertion an earlier draft asked of it. FrameGeometry.Read returns a Net record whose
      members are listed at MouldComponents.cs:2411-2421 and which carries no curve of any kind; the
      polyline and the empty-branch guard live in Build (:2643-2658), which needs the native core, as
      rules 5.5 and 10.2(f) both say.

      MEASURED, driven off FrameGeometry.Read where Rhino is not needed: the anchor strips' branch count
      equals Anchor Nodes' branch count; a strip of ONE node and a strip of NONE each keep their branch;
      each strip's node order is end to end; and, if he takes the polyline of 5.2(b), the AnchorCloses
      flag of rule 5.4(a) is true on a ring fixture and false on an open strip.

      NOT MEASURED, and stated rather than papered over: under 5.2(b) the Polyline construction and the
      empty-branch guard live in Build and need Rhino, exactly as Perimeter Lines' conversion does today,
      so "one branch holding one polyline of three points" cannot be asserted from this harness. If that
      guard is to be measured, the guard ITSELF is extracted as an internal static over
      List<List<Point3d>> returning which branches will build, and that static is what the harness drives.
      Under 5.2(a) the question does not arise: the chord is built in the Rhino-free helper and the
      shipped check keeps driving it.
  (d) REACTION VECTORS BRANCH FOR BRANCH AGAINST ANCHOR NODES: same branch count, same item count per
      branch, on a fixture where every support carries a reaction AND on one where a support carries none,
      so the zero-vector slot at VisualiseComponents.cs:634-640 is measured rather than assumed. THE CHECK
      DRIVES THE REBRANCHING STATIC of rule 3.5, by reflection, in the shape of the existing
      ValidateDeconstructColumnTrees and ValidateDeconstructForceLines (Program.cs:2897 and :3147).
      Without that static there is nothing to call: the branching lives inline in SolveInstance at
      VisualiseComponents.cs:617-664 today, and the harness never calls SolveInstance (Program.cs:12743).
  (e) THE STRAY REACTION, both halves, ASSERTED OVER THE STATIC of rules 3.5 and 4.3 rather than over a
      Warning. Given a reactions table with a reaction at a node on no anchor strip, the static returns
      branches whose count equals the strip count, with NO extra branch, AND returns that node in its
      stray list. The whole risk in section 4 is a deletion nobody notices, so a check that measured only
      the branch count would pass on the silent failure. The Warning sentence SolveInstance builds from
      the stray list is read rather than run, which is this harness's own convention for component wiring
      (Program.cs:11989-11991).
  (f) THE SEED DIVERGENCE of rule 3.7, likewise asserted over the comparison STATIC: given a
      Mappings.Supports list and a ResolvedSupportNodeIds list that disagree, it returns a non-null string
      naming both counts and the difference; given two that agree, it returns null. A hand-built TNA
      Result is buildable from the harness's existing fixtures (Program.cs:5424-5433 already constructs a
      TNA Result with a support naming a vertex the net does not have) and is the input to the two lists.
  (g) DIAGNOSE'S RESULT INPUT IS OPTIONAL. One assertion, and it is what stops a later edit quietly making
      it required again. Note that Diagnose is pinned nowhere else in the harness: it appears only in
      NativeIconEntries at :311 and in a behavioural test's type lookup at :3284, so it has no port
      contract to fall back on.
  (h) THE MEMBERSHIP PREDICATE of rule 6.5, measured directly. Every one of our twenty concrete
      components passes it, including the eight task-capable ones, and a type from another assembly fails
      it. This is the check that would have caught `obj is NativeComponentBase`. It requires the predicate
      to be an internal static taking IGH_DocumentObject, because the harness has no document.
  (i) THE DIGEST of rule 7.3(c), measured as a pure static over a list of (InstanceGuid, remarks,
      warnings, errors, chin) tuples: identical input gives an identical digest, one changed message gives
      a different one, and reordering the input list does not change it. THE ORDERING FUNCTION IS
      MEASURED HERE TOO, once for both its uses: the same InstanceGuid-ascending sort serves the digest
      and rule 6.8's branch order, so assert that a shuffled input comes back in the same order both
      times and that inserting a component does not move the ones around it.
  (j) THE SETTLING BEHAVIOUR of rule 7.3(d) cannot be measured without Grasshopper and is a MANUAL check
      in Rhino, recorded as such: place Diagnose unwired on a canvas holding a failing chain, confirm the
      report appears, confirm the document settles within two solves, and confirm Rhino's CPU does not sit
      busy afterwards. Then delete a component and confirm the report updates on the next solve. THEN THE
      BROKEN-UPSTREAM CASE of rule 7.3(b): wire a Result in, disable the upstream solver so the wire
      carries nothing, and confirm the report still updates rather than freezing on its first answer.
      Also manual, and also in Rhino: the divergence Warning of rule 3.7 and the stray Warning of rule
      4.3 are seen on the balloon here, since 10.3(e) and (f) measure the statics behind them and not the
      raising of them.
  (k) RULE 6.6(f), the Remark question, also a manual check in Rhino and a PREREQUISITE for section 8:
      confirm that RuntimeMessages(GH_RuntimeMessageLevel.Remark) returns what AddRuntimeMessage placed
      there, against the documentation's claim that only Warnings and Errors are recorded.
  (l) EACH RETIRED PORT'S CONTENT STILL EXISTS. For Export and Import Pieces, drive the message-building
      code and assert the strings now raised are non-empty, one per fact by rule 8.5, and at the intended
      level. Export's per-kind live lines are the case worth naming, because 8.6(c) shows they are the
      half that has no duplicate. Skin is not in this list: rule 8.2 leaves it to its own spec, whose
      rule 12.10(d) writes the equivalent check there. Without this, "it moves to the balloon" is a plan
      rather than a fact.
  (m) FAILURE PARTITIONING of rule 1.6A, as far as the harness reaches. The two halves are separate
      methods with separate catches, so assert that the frame half's entry point and the statics half's
      entry point are distinct statics and that each returns its own empty answer rather than throwing
      when handed a Result the other half would refuse. Which half's Error reaches the balloon, and what
      the chin then reads, needs a document and is a manual check beside 10.3(j).

## 11. Out of scope

The columns priority ladder (its own spec,
docs/superpowers/specs/2026-09-01-columns-priority-design.md); the skin round
(docs/superpowers/specs/2026-09-01-skin-round-design-input.md and the spec that now owns it,
docs/superpowers/specs/2026-09-01-skin-buildability-design.md), INCLUDING Skin's Diagnostics port, which
rules 8.2 and 8.3 hand back to that spec rather than retiring here; descending into clusters (rule
6.4(d), and question 12(g)); harvesting the diagnostics inside a Result during a document scan (rule 6.9,
and question 12(h)); RE-SEEDING SUPPORTS from ResolvedSupportNodeIds, or re-seeding the merged reader from
Mappings.Supports, so that the two agree by construction rather than by warning (rule 3.6); THE GENERAL
IDENTIFIER RULE APPLIED BEYOND THE MERGED READER, which rule 2.6 sweeps and finds one live target, Skin's
Courses, already owned by the skin spec's rule 9.2.3, so nothing is left open but the sweep's own reach;
changing Load Points and Load Vectors from lists to trees (rule 1.11); adding a pure-truncation branch to
the load warning (rule 9.6); any change to what a measure computes.

## 12. Questions for Param

  (a) WHETHER TO MERGE AT ALL, and this is the question the whole spec rests on. He wrote "part of me
      thinks these two components can conjoin" (design input :6-13), which is a proposal, and the design
      input reserves the decision to him at :108-114. Nothing here is approved. Two parts to it. First,
      merge or keep two components. Second, if merged, is FIFTEEN PORTS on one component worse in the way
      he works than two components holding ten each? Fifteen is Monitor-sized and being tall is part of
      what he disliked about Monitor. Section 0 names the fallback if it is: keep two components, apply
      the four deletions and the Anchor Lines fix to them, and let one hold the geometry and the other
      the statics. Sections 2 to 5 stand either way; only sections 1, 9 and part of 10 depend on this.
  (b) THE NAME. "Deconstruct" or "Frame" (rule 1.2). He named neither.
  (c) THE STRAY REACTION'S HOME. Runtime warning only, or a RES passthrough at output 0 taking the
      component to sixteen ports so the stray travels to the studio (rule 4.4).
  (d) EXPORT'S WRITTEN-FILE PATHS. They stop being wireable data when Status goes (rule 8.6(b)). Accepted?
  (e) BACKEND HEALTH'S REPORT. Not named in his sentence, and it is the component's product rather than a
      diagnostics side-channel (rule 8.6(d)). Retire, or keep the success roll-up?
  (f) ANCHOR LINES: A CHORD OR A POLYLINE (rule 5.2). One line per strip either way, which is what he
      asked for. A straight LINE from the strip's first node to its last is what he literally said,
      "should just be 2 lines", and it keeps the port typed as a Line, keeps the Rhino-free helper and
      keeps the smoke check that drives it. A POLYLINE through the strip's nodes follows a springing that
      curves in plan, as Perimeter Lines already follows a boundary that does, and it costs the port
      retype to Curve, the deletion of the helper, the move of the work into Build and the loss of the
      measurable path. My recommendation is the polyline; his vault is the reason and his canvas is the
      test.
  (g) CLUSTERS (rule 6.4(d)). He asked for "every component of our plugin"; the rule as written reads
      only the top level, because descending needs GH_Cluster.Document(password) and what to do with a
      password nobody has answered. Does he cluster parts of a definition, and must the scan descend?
  (h) THE DIAGNOSTICS INSIDE A RESULT, during a document scan (rule 6.9). They are reachable through each
      scanned component's output parameters' volatile data, and the rule chooses not to read them, for
      staleness, duplication and because a wired Diagnose already reads them exactly. That choice removes
      from "reveal any problems" the whole class of problem the Result's own entries carry. Accepted, or
      is the harvest wanted with its staleness stated on the face of the report?
