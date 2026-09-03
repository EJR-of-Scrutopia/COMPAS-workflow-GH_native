# Columns: the centre is still annexed on Param's real forms. A second mechanism.

Design input, 2026-09-02, after the leftover-central-node fix (fdd0172) was installed and verified
on a 510-configuration sweep. Param's words, on new screenshots of a single-span arch elevation and
the three-way vault:

> "Back to the columns you can see we have the same issue with the central column attaching to a
> branching side, when it should be a straight column coming down."

## What this means against what was already fixed

The installed fix extracts a contested node ONLY where the node is SHARED between two or more spans
(the owner map, holderMap count >= 2). His screenshots show the same visible symptom surviving on:

1. A SINGLE-SPAN arch, where nothing is shared by construction, so the owner-map extraction cannot
   fire. The elevation shows the centre as a V of two leaning columns, or a centre notch carried as
   a BRANCH of a side group's fan, where he wants one plumb column.
2. The THREE-WAY vault, where the same look persists near the crown, which suggests his principal
   lines may NEARLY touch at the crown without topologically sharing a net node, in which case each
   line holds its OWN near-centre notch and again nothing is contested and nothing extracted.

So there is a SECOND mechanism with the same symptom: the central notch of a span's own row ends up
inside a flank group, reached by a branch from that group's foot, instead of standing under its own
column. The fixed mechanism was BETWEEN spans; this one is WITHIN a span, or between spans that do
not share a node.

## His ruling on the mechanism, given after the diagnosis was dispatched. GOVERNS the fix.

> "the central column shouldnt land in the branching that is the point. I want the branching to
> ignore it in those instances and just have a central column thats verticle"

Read precisely, this settles two things the diagnosis was asked to leave open:

1. THE BRANCHING IGNORES THE CENTRAL NOTCH. The centre is removed from the row BEFORE the group
   layout runs, so the groups are laid out over the remaining notches as if the centre were not
   there. This is stronger than the shared-node fix, which extracted after the fact and left the
   layout untouched: here the layout itself is computed without the centre, so no group is ever
   sized or placed as though it owned it.
2. THE CENTRAL COLUMN IS VERTICAL. Plumb, foot directly beneath the notch on the ground. Not aimed
   by the resultant, not leaned, not peeled. The word is his: "a central column thats verticle".

"In those instances" bounds it: this applies where the layout would otherwise put the central notch
inside a side group. Where the ladder already gives the centre its own standing column (the odd
count centre, the merged central pair), nothing changes.

## The standing principle, which already covers this

His 2026-09-02 ruling generalises: THE CENTRE IS NEVER ANNEXED BY A SIDE. The mechanism he chose for
the shared-node case, extract the node into its own column and change nothing else, is presumably
the mechanism here too, but the trigger condition needs diagnosis before anything is built:
when, exactly, does a span's own central notch land in a side group as a non-main member, and when
do two nearly-touching lines each carry a near-centre notch that should be one column.

## Not to be moved

The three settled rulings stand as before: fewest strays with the two-stray ends-only case intact;
the plumb central column at an even Type; Branching 3 moving at m = 3, 7, 9, 13 only. And the new
sweep property from fdd0172 stands: equal branch counts either side of the mirror plane, 510
configurations, zero unequal. Whatever fixes his real forms must keep all of it.

## Status

Read-only diagnosis dispatched 2026-09-02 while the skin phase runs (diagnosis works on a detached
copy and touches nothing). The FIX waits for the tree: pause the skin workflow at a task boundary,
apply, verify, resume skin from cache.
