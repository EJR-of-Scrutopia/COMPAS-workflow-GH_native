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
  are already aligned branch for branch across every reader, so pairing needs no identifiers. Being
  verified: whether anything else consumes them, above all the export payloads.
- PHASE goes. "I again dont need that information."
- REACTION POINTS go. "Reaction points and support points are also the same", which the port's own
  description already concedes, since Reaction Points is documented as a tree "branched and ordered
  EXACTLY as Support Points". Reaction VECTORS stay; they pair with Support Points.
- ANCHOR NODES and SUPPORT POINTS are very probably the same points under two names, one on each
  component, and if so only one survives the merge. Being verified, with one real risk named: Frame
  follows the ANIMATION FRAME's positions when an Animate result is upstream while Deconstruct reads
  the solved positions, so the two would differ mid-animation even though they agree at rest. If that
  is confirmed, the merged component needs one output with a stated rule, not a silent choice.

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

His "needs to go left to right in order" is a second requirement and a real one either way: the nodes
within a strip must be ordered sequentially ALONG the strip, not by node id or by discovery order, or
a line drawn end to end is meaningless. Being verified.

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
Result input.

THAT COUNT NEEDS HIS EYE before it is built. Fifteen ports is a tall component on a canvas, and being
tall is part of what he disliked about Monitor. The principle in section 1 says merge, and the port
count says a merged component is large; those pull opposite ways and only he can say which matters
more in the way he actually works. The alternative, if fifteen is too many, is to keep two components
but fix the real complaint, which is the DUPLICATION rather than the count: dedupe the shared outputs,
delete the four he has named, and let one hold the geometry his work needs while the other holds the
statics and diagram streams.

## 6. Sequence

> "In reference to the columns we will make all of the fixes to columns todays problem"

The columns are today. This round follows the columns and the skin.
