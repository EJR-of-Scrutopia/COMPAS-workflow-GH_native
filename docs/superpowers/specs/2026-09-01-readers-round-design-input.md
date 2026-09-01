# Readers round: Param's rulings on merging Deconstruct and Frame

Design input for a third round, after the columns and the skin. His words are quoted exactly; anything
outside a quote is the reading taken from them and is subordinate to the quote.

> "last thing, part of me thinks these two components can conjoin. They actually have many similar
> values given. There are a couple which also can go like MID and NID, if i have the tree structure I
> dont need the structure given again, that foes for all components. also on frame component we will
> remove phase I again dont need that information. Reaction points and support points are also the
> same, Also I am getting 20 items and 2 trees for the anchor lines, that is wrong should just be 2
> lines, needs to go left to right in order for it to create the line properly, but I can make it
> myself if its hard to be perfect each time. we also need to group AL with AN so it fits in sequence.
> In reference to the columns we will make all of the fixes to columns todays problem"

## 1. The principle underneath this, which is worth stating because it is a good one

He asked earlier for Monitor to be broken up because it was "very intense" and he wanted to "target
analysis for different things", and he is now asking for two components to be joined. That is not a
contradiction, and the rule that reconciles them is worth writing into the taxonomy:

SPLIT what needs different INPUTS. Monitor took EI, EA, Tolerance and two capacities, and an author
wiring for one kind of analysis had to look at ports belonging to another; splitting it into Forces,
Fit and Supports gave each its own small input set.

MERGE what is a pure READER of one input. Deconstruct and Frame both take a Result and nothing else,
and hand geometry straight back. Nothing is targeted, nothing is configured, and having the answer
split across two components only makes the author remember which one holds which output.

## 2. The deletions, and what each rests on

- MEMBER IDS and NODE IDS go. His reason is general and worth applying beyond these two: "if i have
  the tree structure I dont need the structure given again, that goes for all components". The trees
  are already aligned branch for branch across every reader, so pairing needs no identifiers.
  VERIFIED: nothing in the plugin consumes either port. Loads' own Node IDs INPUT is unrelated, Forces
  names Node IDs only to disclaim alignment with it, and Export builds its payloads from the ResultDto
  contract and never from a reader's outputs. What is lost is the one exact non-coordinate bridge from
  a point or a member line back to the Result's own index, which nothing shipped needs today.
- PHASE goes. "I again dont need that information." VERIFIED unconsumed: it is a read-out of
  Mould.Frame.Phase, and Fit, the only component that cares about an intermediate frame, reads that
  field off its own Result input rather than off this port.
- REACTION POINTS go. "Reaction points and support points are also the same", which the port's own
  description already concedes, since Reaction Points is documented as a tree "branched and ordered
  EXACTLY as Support Points". VERIFIED, and more strongly than the description claims: where a node has
  no reaction the code falls back to reading the Support Points array itself, so for every real support
  they are the same Point3d by construction. ONE EXCEPTION, which the merged component must keep
  somewhere: a reaction reported at a node that is not a support gets a branch of its own at the end,
  so Reaction Points can carry one branch more than Support Points. That branch is a fault report and
  should survive as a diagnostic entry rather than as a silently vanished branch. Reaction VECTORS stay;
  they pair with Support Points.
- ANCHOR NODES and SUPPORT POINTS carry the same NODES but not always the same POSITIONS, and this is
  now measured rather than suspected. The node identity agrees in the shipped path. The positions do
  not: Frame reads Mould.Frame's vertices when an Animate result is upstream, and Animate blends EVERY
  node between the drawn pattern and the solved form, anchors included, so an anchor's plan position
  only reaches its solved place when sag reaches 1. Deconstruct always reads the solved vertices. They
  agree at rest and at "finish", and differ at every intermediate frame. So the merge cannot dedupe
  these two silently. The rule to state: the merged ANCHOR NODES follows the frame, because a reader
  fed an animation should show the animation, and Anchor Lines drawn through solved positions while the
  mesh sits half-reeled would be worse than useless. Anyone wanting the solved positions has the
  Result's own vertex list.

## 3. The Anchor Lines defect

> "I am getting 20 items and 2 trees for the anchor lines, that is wrong should just be 2 lines, needs
> to go left to right in order for it to create the line properly, but I can make it myself if its
> hard to be perfect each time"

The spec written for Anchor Lines said one line per adjacent pair of nodes, so a strip of 21 nodes
gives 20 lines, which is what he is seeing and it is not what he wants. He wants ONE line per anchor
strip, running the length of it, so two strips give two lines.

Two forms are possible and his sentence does not settle it. A straight LINE from the strip's first
node to its last is simplest and is what the present Line-typed port can carry. A POLYLINE through
the strip's nodes preserves a springing that curves in plan, which his vault's anchor clusters appear
to do, and needs the port retyped as a curve. The second is more faithful; the first is what he
literally asked for. Put it to him with that trade named.

ONE PIECE OF EVIDENCE FOR THE POLYLINE, from inside our own code. PERIMETER LINES is built from the
same grouping machinery and is already a polyline through every node of its loop, precisely because a
boundary walked around a doubly curved vault does not run straight. Anchor Lines was left as discrete
segments. The two are siblings and only one of them was thought about; the anchor strips are walked
around the same boundary, so the same reasoning applies to them.

His "needs to go left to right in order" is a second requirement and a real one either way: the nodes
within a strip must be ordered sequentially ALONG the strip, not by node id or by discovery order, or
a line drawn end to end is meaningless. VERIFIED ALREADY SATISFIED: the grouping walks each connected
component from one of its graph ends, so a strip's nodes already arrive in order along it. That is one
less thing to build, and it means a first-to-last chord is a real chord and not a random pair.

His "I can make it myself if its hard to be perfect each time" is an offer, not a preference; if one
line per strip is straightforward, which it is, he should not have to.

## 4. Port order

> "we also need to group AL with AN so it fits in sequence"

Anchor Lines sits immediately after Anchor Nodes rather than at the end of the list. It was appended
last only to avoid moving anyone's wires when it was added, which is a migration concern that expires
the moment the components merge and every wire moves anyway.

## 5. The merged component

With the deletions above the merged reader carries, in a sensible order: Mesh, Cables, Principal
Lines, Principal Nodes, Anchor Nodes, Anchor Lines, Perimeter Nodes, Perimeter Lines, Columns, Member
Lines, Form Lines, Force Lines, Load Points, Load Vectors, Reaction Vectors. Fifteen outputs on one
Result input. VERIFIED from the two components' registrations: ten and ten today, four named deletions
take it to sixteen, and deduping Anchor Nodes with Support Points takes it to fifteen.

THAT COUNT NEEDS HIS EYE before it is built. Fifteen ports is a tall component on a canvas, and being
tall is part of what he disliked about Monitor. The principle in section 1 says merge, and the port
count says a merged component is large; those pull opposite ways and only he can say which matters
more in the way he actually works. The alternative, if fifteen is too many, is to keep two components
but fix the real complaint, which is the DUPLICATION rather than the count: dedupe the shared outputs,
delete the four he has named, and let one hold the geometry his work needs while the other holds the
statics and diagram streams.

## 5a. Diagnose reads the whole document, with no input

> "also last thing the diagnostics component, I want it to have no input needed, to read every
> component of our plugin read and will then reveal any problems. This goes for all other components
> with a diagnostics output even the importer and exporter"

He wants Diagnose to stop being a reader of one Result chain and become the plugin's problems panel:
drop it on the canvas, wire nothing, and see every Ananke component's complaints in one place,
Export's and Import Pieces' included.

IT IS FEASIBLE. A component can reach its own document through OnPingDocument and walk its objects,
select the ones belonging to this plugin, and read each one's runtime messages, which is where every
error, warning and remark already lives, along with the Message line each component sets. Nothing new
has to be recorded for this to work; the information is already there and merely unreachable from one
place.

ONE REAL TRAP, and it must be designed around rather than discovered. Grasshopper decides solution
order from data dependencies, and a component with NO INPUTS has no dependency on anything, so it may
compute BEFORE the components it is reporting on. Wired the usual way, Diagnose is guaranteed to run
after the chain feeding it; unwired, it can quite legitimately show the previous solve's problems, or
none at all on the first run. That is not a bug we would be introducing but a property of the host,
and every document-scanning component in every plugin meets it. It has to be handled deliberately: by
expiring on document change, or by scheduling a fresh solution once the current one finishes, which is
the usual remedy and needs care not to loop.

THE SUGGESTION, which gives him what he asked for and keeps what he had. Make the Result input
OPTIONAL rather than removing it. Unwired, Diagnose scans the whole document, which is the behaviour
he wants. Wired, it reports that chain alone, which is what it does today and is what an author wants
when a definition holds two studies and only one is misbehaving. One port, two useful behaviours, and
the staleness trap only applies to the unwired case, where it can be stated plainly in the component's
own description.

WHAT THIS MEANS FOR THE OTHER COMPONENTS. "This goes for all other components with a diagnostics
output" is the same instinct that removed Skin's Diagnostics output: a component should raise its
problems where the author already looks, not hand back a text output that must be wired to a panel to
be read. So Export's Status, Import Pieces' equivalent, and any other component's diagnostics text
become runtime messages and diagnostics entries, and Diagnose is where they are read. That is a
consistent surface rather than a per-component habit, and it removes several ports.

Note it does NOT retire the diagnostics carried in the Result. Those travel with the data, reach
Export, and form part of the contract the studio receives; the document scan is for the author at the
canvas. The two serve different readers and both should stay.

## 6. Sequence

> "In reference to the columns we will make all of the fixes to columns todays problem"

The columns are today. This round follows the columns and the skin.
