# The machine in Vaulted: the studio's side of bench.mechanism/1

Settled overnight 2026-09-07 to 08 between the plugin session (the
Grasshopper writer) and this studio session, in five rounds under P-003
in `REQUESTS-for-plugin-session.md`. That file is the negotiation; this
is the conclusion, so the build works from one page rather than eight
messages. The plugin's binding spec is their commit c90bf64.

Nothing here is built yet. The first real document arrives when Param
installs the rebuilt plugin, which is his call.

> **NO LONGER PROVISIONAL: BUILT AND MEASURED 2026-09-08.** The reader
> exists, and it was built against Param's real
> `2 Sided Vault-mechanism.json` (10.1 MB, six instances, 42 wires),
> not against this page. Where the two disagreed the FILE won, and the
> disagreements are recorded under "What the real document actually
> looks like" at the foot of this page. Read that section before this
> one: the key layout below is the negotiated shape, and the writer
> moved three parts of it.

## What the document is

`<study>-mechanism.json`, schema `bench.mechanism/1`, a fourth sibling
beside form, skin and formwork. **Shape only, never per-frame data**:
the motion already lives in the formwork document's frames the studio
replays today. Absence means "no machine view for this study", quietly,
exactly as a missing formwork document is treated.

Parts arrive on **named ports** -- Param rejected a tree of type and
part and asked for one port per kind -- so **the part's kind is the
array it sits in**, not a tag field on it. That is the tag vocabulary
answered structurally: a kind authored by construction cannot fall out
of step with the thing it names. It also serves the material mapping
and the permanence view from the same property.

### The literal top-level keys

Read from the writer (`ExportPayloads.cs`, plugin commits 9225647 and
363fdea), not from a description of it:

    numbering, rotation, principalRows, mechanism, instances,
    anchors, tensionTies, wires

- `mechanism` -- ONE authored body plus its spinners. Not a map of unit
  types: Param authors a single mesh and places six instances of it.
- `instances` -- its own top-level array, each entry carrying `side`,
  `mechanism` and `placement`.
- `anchors` and `tensionTies` -- two separate arrays, because they
  arrive on two separate ports and are two distinct kinds in his own
  list. These are the permanent works; everything else is machine.
- `wires` -- `id`, `net_vertex`, `path` (a list of `{side, mechanism}`
  steps) and `route` (the routing frames).
- `numbering`, `rotation`, `principalRows` -- as described elsewhere on
  this page.

Geometry travels **once**, in the `bench.columns/1` convention (a
vertices array, a faces array, mixed triangles and quads,
`lengthUnitToMetres` on the document). Instances carry a placement
frame and nothing else: origin plus x and y axes, right handed, z
derived. The anchors and tension ties are the exception and arrive
pre-placed in world coordinates behind an explicit flag, rather than
relying on the reader to know their kind is special.

Param authors the placements himself. The plugin relays; the studio
stamps.

> This shape superseded an earlier one mid-negotiation, after five
> rounds of settling the old keys. The lesson is cheap to state and
> was expensive to nearly learn: a contract page describes a writer,
> so it is only as current as the last time somebody read the writer.
> Diff this section against the emitted keys before building, not
> against memory of an agreement.

## The shape of his machine, for sizing

Seven wires per mechanism, three mechanisms a side, two sides: 42
wires, and **six instances from one authored mesh**. Routing frames
arrive as a tree of side, then mechanism, then wire, each holding an
ordered list of planes in threading order, up to about a hundred planes
where the wire wraps tightly.

## The invariants the studio leans on

1. **Net vertex numbering is shared.** Net vertex *i* is the same point
   in the formwork document and in the form bundle. Measured on two
   studies by two sessions: Column diagnosis 661 vertices, last frame
   against equilibrium max and mean 0.000000000 m, edge lists identical
   element for element. Numbering, not positions -- frame 0 is the flat
   start and sits far away (5.651 m max on Column diagnosis).
2. **Every wire carries its own explicit `net_vertex`**, whatever else
   groups it. Non-negotiable, written into the plugin's requirements in
   those words, and it survived the port rewrite. Grouping alone says
   which mechanism a wire belongs to and nothing about which vertex it
   pulls; inferring the net end from ordinal position would land the
   wire on a real vertex that is simply the wrong one, with nothing on
   screen to show it.

   **But explicit is not the same as authored.** The plugin DERIVES
   `net_vertex` by matching wire order to anchor order along the row;
   Param does not declare it. The reader is unaffected -- the value is
   in the document either way, so the studio cannot be silently wrong
   about what it was told -- but the writer can be, and a bad match is
   the C1 failure relocated from the reader to the writer rather than
   eliminated. Their defence is that the component prints every match
   distance so a wrong one shows on his canvas. **Ours costs nothing
   and belongs here too:** after placement, compare each wire's
   declared `net_vertex` against the vertices nearest its first routing
   plane, and if a different vertex is dramatically closer, say so in
   the log. Same principle as refusing to snap the wire -- detect and
   report, never quietly draw the plausible thing.
3. **Two index spaces, named in the field itself**: `net_vertex` into
   `frames[].vertices`, `column_node` into `frames[].columnNodes`.
   Node reels live in the first, the tie and rail in the second.
4. **`planes[0]` is the net end**, so the list reads in the direction
   the wire is drawn. The plugin validates it after placement rather
   than trusting it: the first plane must sit nearer its net vertex
   than the last, and a reversed list is named on the component.
5. **The routed portion is PARTLY constant.** Superseded 2026-09-08
   after being stated twice: Param has modelled the wire wrapping the
   drums, so part of every wire's routed path sits on a body that
   rotates. Every `wires[].route[]` frame now carries `owner`
   (`"body"` or `"reel"`) and `ownerReel` (that reel's 0-based index,
   or -1), shipped at plugin `be30f38`. Body-owned frames behave as
   originally agreed and are built once per instance. Reel-owned
   frames belong to a spinning part.

   The owner is DERIVED, not authored: for each frame the writer takes
   the perpendicular distance from the frame's origin to each reel's
   axis, divides by that reel's radial extent, and the smallest ratio
   at or under 1.0 wins. Frames near a boundary or near two reels are
   named on the component as ambiguous rather than picked silently.
   Positions are never altered -- classification only, with a check
   proving a frame's origin and axes are byte-identical whichever
   owner it gets. So this is another derived value to read explicitly
   and sanity-check, the same posture as `net_vertex`.

   **What to DO with a reel-owned frame is open, and rigidly rotating
   it is probably wrong.** See the open items: a wrap cannot rotate
   rigidly while the free span feeding it stays put, because one end
   of the wire has to stay where the wire arrives.

## What the studio builds

**The wire, from a declared rule rather than sent geometry.** Param's
construction: a circle on each routing frame, lofted in order, giving a
tube that follows each frame's Z around every turn rather than a
polyline cutting corners. The plugin uses the identical construction
for its own Rhino preview so his canvas and the app cannot drift apart.

Radius is the studio's own: `state.wireRadius`, 0.02 m, a 40 mm
diameter wire. It has **no writer left in studio.js** -- set once at
boot, never assigned; the Wire size slider the old comments mention was
removed in an earlier wave. So the mechanism wires match the net wires
by construction, which is what his ruling was reaching for.

Build the **body-owned** routed tube once per instance in local space
and stamp it with the placement; rebuild the **free span** from the net
vertex to the first routing plane per time step. That is still 42 short
tubes a frame rather than 4200 circles. The **reel-owned** portion is
the open question below. Guard coincident or duplicated consecutive
planes by skipping zero-length spans, or a tight wrap folds the loft.

**No snapping.** The wire is drawn from its declared net vertex to
wherever the placement puts the first plane. A mechanism placed off its
node shows as a wire that stretches or floats. The drawing is a check
on the placement, not a flattering picture of it. Param has been told
to expect this.

**The spin**, per spinner, about its own authored axis. The `rotation`
object now declares its own terms rather than promising them in a
message:

    unit      = "turns"
    reference = "frame0"
    sign      = positive turns take up wire (the spool winds in and the
                wire's routed length shortens); negative pays out
    formula   = turns = (length_at(t) - length_at(frame0))
                        * reeveFactor / (2 * pi * spoolRadius)

So the studio multiplies by 2 pi for radians, as expected.

**The formula's sign was inverted, and is fixed** (plugin `29da394`).
It briefly read `length_at(t) - length_at(frame0)` while the sign
sentence called take-up positive, which are opposite claims: reeling in
SHORTENS the free span, so that subtraction went negative exactly when
the sentence said positive. The sentence was right and the arithmetic
was wrong, so the subtraction was inverted rather than the wording
rewritten:

    turns = (length_at(frame0) - length_at(t))
            * reeveFactor / (2 * pi * spoolRadius)

with `length_at(t)` defined explicitly as the wire's **free span** at
frame t -- from its net vertex to where it first meets the machine,
the wrapped portion excluded because it is constant. That is also the
quantity the studio already computes in order to draw the free span,
so nothing has to be derived that the scene does not give directly.

The **frame 0 reference** is the load-bearing part: the studio's timeline is
a pure function of t by construction, so an incremental per-frame delta
would drift on scrub and be wrong on every recorded frame not played in
order. Nothing is keyframed; the loosen-then-tighten falls out of the
frames.

**`reeveFactor` is per wire, and the reader never inherits it.** It is
authored once per mechanism as a default and overridden per wire where
a wire genuinely differs, but **the document carries the RESOLVED value
on every wire**, so the studio never has to inherit anything or know a
default exists. Same principle as `net_vertex` being explicit even
though it is derived: the reader reads a value, never a rule for
finding one.

Per wire rather than per document because the routing frames are
already per wire -- Param's tree is side, mechanism, wire, with a plane
list inside -- so a single number governing 42 individually specified
paths would be the wrong shape twice over. Per-mechanism defaulting
exists only so he does not type the same number seven times, which is
how transcription errors get in; it is an authoring convenience,
invisible here.

**Its current value is 1.0 and provisional.** The author port lands
before the first real document, but until it does the writer is fixed
at 1.0 while Param's unit has four wheels, so the reels would turn too
slowly by a whole multiple. Treat the field as real and its value as
unverified; a reader that hard-codes around 1.0 would have to be
unpicked. The reeving is partly visible in `route`, since the wraps are
geometry -- not fully derivable, because whether a wheel gives
mechanical advantage or merely guides depends on whether it moves with
the load, but enough that a factor wildly at odds with the wrap count
is detectable. The plugin is adding that check on its side alongside
its match distances and reversed-list naming; by agreement it warns
loudly and refuses nothing, since geometry cannot settle the question
on its own.

Known refinement, immaterial at this representation: as wire layers
build on a spool the effective winding radius grows, so a very long
take-up is not perfectly constant at the drum. If it ever matters it is
a correction to the spin arithmetic, not to the routing.

## The sequence

One clock, pure in t, the three acts running straight into the voussoir
drop at the frames' hold phase. The frames already carry a `phase`
field that studio.js reads nowhere today. Measured mapping, confirmed
on two studies:

| frames phase | frame time | what moves | Param's act |
|---|---|---|---|
| `reel` | 0 to 28 | columns motionless, net nearly flat, edges shortening | none: pre-lift slack take-up |
| `raise` | 30 to 58 | columns climb, net carried up, edges lengthening | act one, the columns lift |
| `finish` | 60 to 88 | columns frozen, net rises alone, edges shortening | acts two and three |
| `hold` | 90 to 100 | nothing moves at all | the settle before the drop |

Beware the names: the frames' `reel` is a pre-lift event and is **not**
Param's "ribs reel in", which lands in `finish`. Both sessions misread
this at first, in opposite directions.

**The names and their order are structurally guaranteed, not
data-dependent.** The writer is a single pure function of normalised
time against hard-coded thresholds (`Phases(time, preSag)` in the
plugin's `MouldComponents.cs`): under 0.3 `reel`, under 0.6 `raise`,
under 0.9 `finish`, otherwise `hold`. Neither geometry, topology,
anchor count nor solve is an input to that decision, so no study can
reorder, rename or omit a phase. The measurement above agrees with the
code exactly: at the frames' 2-unit spacing, 28, 58 and 88 are simply
the last frames below 30, 60 and 90. Two independent readings, one from
their source and one from my instruments, landing on the same
boundaries.

Two consequences worth carrying into the build. First, the phase
BOUNDARIES are fixed but the WORK inside them is not. `Pre-Sag` is an
authored input on the plugin's Mould component (default 40, Param's
canvas currently 30), documented there as "0 to 100, as a percentage of
the FINAL sag: how much is reeled in before the columns lift. The
remainder is reeled after, which is the part that tightens the form
against the bars." It moves no boundary, so the clock is identical
across studies while the felt pacing is not, and **the sequence must
never assume a fixed amount of movement per act**. Both ends are
reachable and legitimate: at 0 the `reel` third opens on an essentially
static flat net, at 100 all the sag is out before the lift and `finish`
only tensions against the bars.

**The studio derives the realised split by measurement, not from the
declared value**, and that is deliberate. Frame 0 against the phase
boundaries against the last frame gives the fraction of shaping
actually done in each act, which is what pacing needs; the authored
number states an intent that the geometry may not realise, since a form
with little total sag barely moves at any setting. Measuring also works
on every document already on disk, including all of them written before
`preSag` is exported at all. Keying the sequence to the field would
make every existing study need a re-export to animate correctly. The
declared value is therefore welcome as PROVENANCE -- it lets the studio
name the cause when it reports a near-static opening, rather than
inferring it -- and its home is the formwork document, since it governs
the frames rather than the machine and the frames exist for studies
that have no mechanism document at all. Second, the
vocabulary is guaranteed by CODE and not by a version field: no
document says which phase vocabulary it was written with. So **treat an
unrecognised phase name as the signal that a vintage moved**, and say
so, rather than slotting it somewhere sensible. Any future change to
these names or thresholds is meant to bump the formwork document's
schema identifier, which is the only defence available.

Acts two and three are not separable in the frames, which are
piecewise-linear morphs rather than a simulation: per-frame
displacement is identical within each phase and the vertices furthest
from the anchors move most. **Param ruled this needs no fixing**: "the
rib tightening will also make the mechanism reel", so both reel
families turning together through `finish` is what the machine does,
not a compromise. No phase split, no per-wire act membership.

## The materials

Tags are semantic and the studio owns the mapping, so Param re-skins
from the panel without a re-export.

| part | material |
|---|---|
| tension tie / column slider rail | one dark anodised family, see below |
| foundation anchor | the same, deliberately |
| columns | `metal/steel-mill-grey` |
| pulley bodies | `timber/birch-pale-fine` |
| cable net and mechanism wires | plain bright metal, no library texture |
| principal bars (already shipped) | `metal/steel-polished-dark` |

His ruling: "the two things that remain when all is taken away is the
tension tie / column slide, and the anchor. Both are a dark anodised
steel / aluminium." One family across both, because those two are the
**permanent works** and everything else is temporary machine that comes
away. The library has no anodised entry, so the opening take is
`metal/aluminium-mill-grey` carried dark by tint, which gives the satin
non-directional face anodising has;
`metal/steel-polished-dark` is the sheenier alternative and
`metal/steel-powder-coated-black` the flatter one. Settle it on screen
against the real parts, not from a swatch list.

No texture on the wires: at 40 mm diameter a texture is invisible and
costs a texture unit per draw.

Permanence needs no field. With named ports, anchor and tension tie
**are** the works that remain, so the "what remains when the machine is
taken away" view reads off the port name.

## Open, and whose

- **The drop's rhythm, Param's, and the case is stronger than it first
  looked.** `FORMWORK_SECONDS` is 12 and the studio starts the build
  clock when the frames reach time 100, but the machine stops moving at
  time 90, so every take spends its last **1.2 seconds** on a motionless
  machine before the first voussoir falls. The plugin has since supplied
  the intent behind that tail: `hold` exists **to keep the shape while
  load arrives**. So the drop is meant to happen DURING hold, and the
  studio currently waits for the phase to finish before starting the
  thing the phase was written for. That reframes this from a matter of
  taste to a misreading of the frames' own design.

  The fix is small and geometrically safe: begin the build clock at the
  start of `hold` (frame time 90) rather than at the end of the frames.
  Nothing moves during hold, so the net is already at its equilibrium
  pose throughout, and pieces landing on it during the phase meet the
  same geometry they meet today. Not changed while he slept, because it
  alters the visible rhythm and the take length of a presentation
  animation and he has twice been told it would be left alone -- but it
  is one word of approval away, and worth pairing with the Pre-Sag
  question below since both ask what the studio should do with clock
  time in which nothing happens.

- **What a reel-owned route frame should DO, unsettled, and the
  proposed answer looks wrong.** The plugin's intent is that reel-owned
  frames rotate with their drum, so a stationary wire on a spinning
  drum does not read as slipping. The geometric objection: **a wrap
  cannot rotate rigidly while the free span feeding it stays still.**
  One end of the wire has to remain where the wire arrives. Rotate the
  wrapped frames rigidly and the junction with the last body-owned
  frame opens by the full spin angle; let the free span chase the
  rotated wrap instead and the wire visibly orbits the drum. Neither is
  what a winch does.

  How bad depends on total turns, and a rough estimate says badly. With
  `turns = delta * reeve / (2 * pi * spoolRadius)`, a per-wire take-up
  of about a metre (plausible when the columns rise 2.64 m) on a drum
  of 50 to 100 mm radius gives roughly 1.6 to 3 turns at reeve 1, and
  6 to 13 turns at reeve 4. Rigid rotation through several turns does
  not produce a wire; it produces a wrap pointing somewhere unrelated
  to where the wire comes in. For rigid rotation to be sound the drum
  would need a radius near 0.6 m, which is not this machine.

  The likely resolution, pending the two numbers below: a wrap of a
  full turn or more is nearly invariant under rotation about its own
  axis, so leaving those frames where they are is NOT the slipping
  failure the plugin fears -- the drum reads as turning because the
  spinner MESH turns, which already happens. Slip only shows if the
  wrap is a short arc with visible ends. So: leave reel-owned frames in
  place if the wrap is roughly symmetric, and treat a short-arc wrap as
  the case that needs a tangent-point construction rather than a rigid
  spin. **Two numbers settle it, both Param's: how far the authored
  wrap subtends, and the drum radius.**

  **CLOSED, in Param's own words:** "yes the wires are already fully
  wound in the image and my model, you can use the frames to tighten
  and losen along the frames as long as it stays spooled enough for
  now." So it is a multi-turn wrap, **reel-owned frames stay static**,
  and no tangent-point construction is needed. Read his second clause
  as licence rather than instruction: the visible wire may slacken and
  pull taut along its authored path, and the wrap itself need not grow
  or shrink. The `owner` fields stay regardless: they are what lets the
  wrap be drawn once and the free span per frame without re-deriving
  which is which, and if the geometry ever does need the tangent-point
  construction the classification is already in the document rather
  than being a schema change under pressure.

  Note also what "stacked on top of itself" implies for the spin: with
  layers, the effective winding radius grows as the drum fills, so the
  constant `spoolRadius` in the formula is a mild simplification of his
  own stated intent rather than an idealisation nobody meant. It stays
  immaterial here, and with a static wrap nothing visual depends on it.

- **The static opening, same family, also Param's.** At `Pre-Sag` 0 the
  `reel` third opens on an essentially static flat net. Compounded with
  the tail above, a take could run with roughly a third of it
  motionless. His canvas is at 30, nowhere near it. Both ends are
  legitimate machine settings rather than faults, so the sequence must
  survive them gracefully whatever he decides about rhythm.
- **The anodised material, Param's**, to be confirmed on screen once
  the parts exist.
- ~~Phase vocabulary and order guaranteed or incidental~~ **CLOSED**
  2026-09-08: structurally guaranteed by a pure function of normalised
  time, confirmed from the plugin's own source and cross-checked
  against my measurement. See the sequence section.

## Two facts from the writer, 2026-09-08, to hold until the file arrives

Both were reported by the plugin session against Param's real geometry
and will be visible in the document itself. Neither is the reader's fault
to fix.

1. The seven anchors per mechanism are COLLINEAR. The placement transform
   is therefore fitted in two parts: the anchor line from the seven
   origins, which is exact, and the roll about that line from the
   authored axes of all seven placement planes against all seven routing
   frames. On the current data those axes disagree by about 45 degrees on
   average after the best spin, so every anchor lands exactly while the
   machine may be ROLLED about the anchor line. If a mechanism renders
   lying on its side, that is the cause, it is an authoring convention
   for Param to settle, and the figure is reported per branch in the
   document's own chin. The reader should surface it, not correct it.

2. Side 1 is a genuine REFLECTION: determinant -1, which is expected for
   the mirrored side. Instancing must carry a left-handed transform
   rather than assume a rotation, or the mirrored half will come back
   inside out.

Still open and NOT to be decided without Param: placement derived from
the first wire frame moves the key layout. That is a design decision, it
is his, and it gets raised with him directly when the reader reaches it.


## What the real document actually looks like, measured 2026-09-08

Read off `2 Sided Vault-mechanism.json` as written at 22:57, with the
reader that now ships. Where this section and the negotiated shape above
disagree, THIS is what the writer emits.

Top level: `schema, study, units, lengthUnitToMetres, vertexCount,
columnNodeCount, numbering, rotation, principalRows, mechanism,
instances, anchors, tensionTies, wires`.

Three differences from the shape agreed above, each of which the reader
had to be changed for:

1. **The parts live INSIDE `mechanism`, under named keys**, not on
   top-level ports. `mechanism.frame1` is one part; `mechanism.frame2`
   is a LIST of three; `mechanism.motors` is one; `mechanism.tensionTie`
   is one; `mechanism.reels` is a list of ten, each carrying `reel` (its
   own number, which `ownerReel` points at), `mesh`, `axis` and
   `driven`. So a key holds either one part or a list, and both are read.
2. **Permanence is DECLARED**, as a `permanence` string on each part,
   rather than being inferred from which port a part arrived on. The
   reader reads it. The port-based inference in the negotiated shape was
   a good idea that the writer improved on.
3. **An instance carries `frame` for its frame and `placement` for a
   LABEL.** Reading `placement` first finds a string and reports six
   unreadable placements on a document whose placements are all present.
   An instance also carries `wireIds`, which names the wires it carries
   exactly and is better than matching a wire's `path` back to a side
   and a mechanism number.

Also measured, and agreeing with the writer's own numbers: 6 instances
of which 3 are reflections; 42 wires each carrying its own `net_vertex`,
42 distinct values; 201 route frames per wire; owners 4530 reel and 3912
body; `reeveFactor` 1 and `spoolRadius` 0.03, BOTH ON THE BODY rather
than per wire, so the body's values stand in.

`zAxis` is present on every frame -- instance frames, reel axes and all
8,442 routing frames -- written from the fitted transform and never
derived. That is load bearing: a determinant -1 reflection CANNOT
survive a frame of origin plus x and y with z derived, because x cross y
is right-handed by construction for any pair of axes. Do not re-derive z
anywhere.

**Param has since ruled that placement will become DERIVED, and that the
far side is then always a rotation and never a mirror.** Keep the
explicit-z handling regardless, because it costs nothing and this file
needs it, but build nothing that assumes or requires a mirrored far
side.

### The check that cried wolf

The contract asks the reader to re-check the writer's derived
`net_vertex` against the vertices nearest each wire's first routing
plane. Built as asked, it fired on 35 of 42 wires, each apparently
naming a vertex 1.05 m away while another sat at 0.00 m.

Every one was false. The routing frames are in the authored body's LOCAL
space, so comparing them with the net compares across a placement --
16.1 m of it here. With the instance frame applied the worst gap is
0.0000 m on all 42 and the declared vertex is the nearest in every case,
reproducing the writer's own measurement independently.

The lesson is about checks, not about this bug: **a check that cries
wolf is worse than no check, because the one time it is right nobody
looks.** Verify a complaint in the frame the data lives in before
reporting it to anybody.

## Departures from the contract, made on the real file, 2026-09-09

Recorded because the page above still states the negotiated rule and a
reader who trusts it will build the wrong thing twice.

1. **length_at(t) is the RIB, not the free span.** The contract defines
   take-up from the free span between the net vertex and the wire's
   first routing frame. On the real file that span is zero at every
   frame: route[0] IS the anchor (gap 0.0000 m, reproduced on both
   sides) and the anchors are the net's fixed supports. Read that way
   the reels turned 0.008 of a turn. The studio now measures take-up
   along the rib of net cable leaving the anchor and climbing over the
   vault -- from the anchor to its highest neighbour in the final pose,
   then the straightest continuation -- halved between the two machines
   that pull one rib. Measured: -1.9 turns mid-build, -1.1 at the end.
   `ribChain` and `chainLength` in static/mechanism.js.

2. **Routing frame origins are the CONTACT LINE, not the centreline.**
   Spools 0.049988 m from their axis against a 0.0500 barrel; pulleys at
   exactly the groove-bottom radii 0.170 / 0.200 / 0.300. The studio
   pushes the centreline out by one wire radius, radially from the drum
   axis, at every reel-owned frame, and blends that offset along the
   straight runs. If the exporter moves to centreline frames, remove the
   offset (`wireCentreline`, the `k = wireRadius / about.radius` line).

3. **The reel radius is measured, not read.** `spoolRadius` 0.030
   matches no reel in the file. Each reel's contact radius is the
   median distance of the frames it owns from its own axis.

4. **The permanent parts are stamped ONCE, untransformed.** The tie is
   authored at row scale in the body frame, centred on x 0, y 0.

5. **The motors are replicated by the studio.** One authored body,
   stamped at every spool of its bank. To be removed when the exporter
   authors them.

6. **The machine is lifted to the floor.** z = 0 in the file is the wire
   plane; the machine's lowest point (the tie's feet, -0.117) is placed
   on the studio floor, and the log names the lift.

## Agreed with the writer, 2026-09-09, and what the next file will change

- **The rib take-up is adopted on both sides.** The plugin will rewrite
  the rotation block's formula text to describe the rib measure rather
  than the free span, which on this machine yields zero by construction.
  The studio does not parse that text, so the change needs nothing here.
- **spoolRadius will be emitted per reel** from the median of that
  reel's own route frames, replacing the bounding-box default (0.030,
  which matched nothing). The studio already measures the same number
  itself and prefers it; when the document's value agrees, either wins.
- **Contact line or centreline is Param's ruling.** The frames sit at
  the drum radius; the contract says centreline. The studio's
  one-wire-radius offset stays until he says which he meant. Evidence
  for the contact-line reading: the pulleys' frames sit exactly at the
  groove-bottom mesh radius.
- **Derived placement has landed in the plugin** (committed, not yet
  installed). With nothing wired to PL the instances come off the net's
  own anchor rows: rotation always, rows filled at seven wires a
  machine, leftovers reported. On the real study it reproduces the
  hand-authored side 0 exactly and lands all six instances' anchors to
  0.000000 m. THE ONE VISIBLE CHANGE in the next file: side 1's
  instances become a half turn rather than a reflection. The reader
  needs no change for that -- it reads the explicit z verbatim either
  way and flags DoubleSide only when a placement is mirrored -- and the
  tie, stamped once and untransformed in body space, is unaffected.
- His authoring, told to him by the plugin session: frame1 arriving as
  a 55 mm block; one motor body; the 26.7 mm spool pitch against a
  40 mm wire; the tie's lugs serving one machine.
