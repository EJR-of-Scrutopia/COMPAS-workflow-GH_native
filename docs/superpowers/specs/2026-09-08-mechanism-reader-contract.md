# The machine in Vaulted: the studio's side of bench.mechanism/1

Settled overnight 2026-09-07 to 08 between the plugin session (the
Grasshopper writer) and this studio session, in five rounds under P-003
in `REQUESTS-for-plugin-session.md`. That file is the negotiation; this
is the conclusion, so the build works from one page rather than eight
messages. The plugin's binding spec is their commit c90bf64.

Nothing here is built yet. The first real document arrives when Param
installs the rebuilt plugin, which is his call.

## What the document is

`<study>-mechanism.json`, schema `bench.mechanism/1`, a fourth sibling
beside form, skin and formwork. **Shape only, never per-frame data**:
the motion already lives in the formwork document's frames the studio
replays today. Absence means "no machine view for this study", quietly,
exactly as a missing formwork document is treated.

Parts arrive on **named ports** -- anchor, tension tie, mechanism,
placement, reel, reel axis, routing -- and the port a part came in on
IS its semantic tag. The plugin guarantees the port name reaches the
document as the part's kind rather than being flattened into an
anonymous list. That one property serves three things at once: the
material mapping, the permanence view, and the tag vocabulary.

Geometry travels **once per type** in the `bench.columns/1` convention
(a vertices array, a faces array, mixed triangles and quads,
`lengthUnitToMetres` on the document). Instances carry a placement
frame and nothing else: origin plus x and y axes, right handed, z
derived. The anchor and the tension tie are the exception and arrive
pre-placed in world coordinates behind an explicit flag, rather than
relying on the reader to know their kind is special.

Param authors the placements himself. The plugin relays; the studio
stamps.

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
2. **Every wire carries its own explicit `net_vertex`**, whatever the
   tree groups it by. Non-negotiable, and written into the plugin's
   rebuild requirements in those words. A tree grouped by mechanism
   says which mechanism a wire belongs to and nothing about which
   vertex it pulls; inferring the net end from ordinal position would
   land the wire on a real vertex that is simply the wrong one, with
   nothing on screen to show it.
3. **Two index spaces, named in the field itself**: `net_vertex` into
   `frames[].vertices`, `column_node` into `frames[].columnNodes`.
   Node reels live in the first, the tie and rail in the second.
4. **`planes[0]` is the net end**, so the list reads in the direction
   the wire is drawn. The plugin validates it after placement rather
   than trusting it: the first plane must sit nearer its net vertex
   than the last, and a reversed list is named on the component.
5. **The routed portion is constant.** The routing frames describe
   fixed hardware, the guide plate holes and the wheel wraps; the wire
   passes the same route however much length has spooled. What changes
   is the free span and the drum's rotation.

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

Because the routed portion is constant, build the routed tube **once
per instance** in local space, stamp it with the placement, and rebuild
only the **free span** from the net vertex to the first routing plane
per time step. That is 42 short tubes a frame rather than 4200 circles.
Guard coincident or duplicated consecutive planes by skipping
zero-length spans, or a tight wrap folds the loft.

**No snapping.** The wire is drawn from its declared net vertex to
wherever the placement puts the first plane. A mechanism placed off its
node shows as a wire that stretches or floats. The drawing is a check
on the placement, not a flattering picture of it. Param has been told
to expect this.

**The spin**, per spinner, about its own authored axis:

    angle = delta(net-side wire length) * reeve_factor / spool_radius

in radians. The document declares its unit, its sign convention in
words with take-up named, and measures the delta from **frame 0**, not
from the previous frame. That last one matters: the studio's timeline
is a pure function of t by construction, so an incremental delta would
drift on scrub and be wrong on every recorded frame not played in
order. Nothing is keyframed; the loosen-then-tighten falls out of the
frames.

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

- **The drop's rhythm, Param's.** `FORMWORK_SECONDS` is 12 and the drop
  begins when the frames reach time 100, but the machine stops moving
  at frame time 90. Every take therefore spends its last **1.2 seconds**
  on a motionless machine before the first voussoir falls. Not changed:
  the rhythm is his call. Worth knowing the quiet phases earn their time
  once the reels and wires are drawn.
- **The anodised material, Param's**, to be confirmed on screen once
  the parts exist.
- ~~Phase vocabulary and order guaranteed or incidental~~ **CLOSED**
  2026-09-08: structurally guaranteed by a pure function of normalised
  time, confirmed from the plugin's own source and cross-checked
  against my measurement. See the sequence section.
