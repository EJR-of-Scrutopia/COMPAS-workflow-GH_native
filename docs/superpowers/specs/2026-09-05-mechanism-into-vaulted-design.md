# The machine goes to Vaulted: the mechanism document and the rig player

## THE INPUT MODEL, settled with him 2026-09-08 night. THIS SUPERSEDES SECTION 3 AND 3a's PORTS

Settled in conversation while he modelled the machine, and it replaces the tree-of-type-and-part
port scheme entirely. He rejected that shape in favour of NAMED PORTS: "i think though we should
turn it into another exporter, where it has the inputs, anchor, tension tie, mechanism, mechanism
normal, mechanism reel, reel plane". Named ports are better here and carry a free benefit: the
port a part arrives on IS its semantic tag, which is exactly what the studio asked for, so the
material-tag port disappears.

HIS MACHINE, from his renders and his description: each mechanism serves a fixed number of wires
(7 in his current design), with 3 mechanisms a side and 2 sides, so 21 wires a side and 42 in
all. The wires leave the net, pass through a guide plate, and wrap the drums of a framed reel.

THE DATA SHAPE, his own words, "frames, wires per mechanism, mechanisms per side, sides":

  1. MECHANISM MESH, once, in its OWN LOCAL SPACE, with the spinning parts separated out, each
     carrying its ROTATION AXIS as a plane in that same local space. One asset, instanced six
     times, never six copies (the studio's iPad constraint makes this binding, not preference).
  2. PLACEMENT FRAMES, a tree of side then mechanism, ONE PLANE PER INSTANCE. HIS RULING, and it
     resolves the two-sources-of-truth question in the plugin's favour of doing less: HE places
     the mechanisms, the plugin no longer computes tangential placements. One authority.
  3. WIRE ROUTING FRAMES, a tree of side then mechanism then wire, holding a LIST of planes per
     wire in threading order, as many as he sees fit ("could be 100 to be safe"). LOCAL SPACE,
     his ruling: "frames will absolutely be local space so you follow the z and you fill know
     exactly where to place the wire". The plane's Z gives the wire's direction through that
     point, so routing is unambiguous rather than inferred from neighbouring positions.
  4. ANCHOR and TENSION TIE, authored in place in WORLD coordinates, since they are singular
     pieces rather than instanced assets. The tie remains the fused sliding bar, anchor clamps
     and column tension tie of his 2026-09-05 ruling.

THE WIRE IS BUILT, NEVER EXPORTED. His construction: "create a circe on each frame and loft to
make the wire". A circle on each routing frame, lofted in order, gives a tube that follows his Z
around every turn instead of a line that cuts corners. Since the wire's shape changes on every
frame of the animation, THE RULE TRAVELS AND THE RESULT DOES NOT: the document declares the
construction, and the studio builds the tube at each time step from the net vertex, then through
the transformed routing frames in order. The plugin uses the identical rule for its own Rhino
preview so the canvas and the app cannot drift apart.

THE WIRE RADIUS IS NOT OURS TO SEND. His ruling: "wire radius will be the same as the one
predefined in the vaulted app". The studio already draws the cable net at a known radius and uses
that same value here, so the mechanism wires match the net wires by construction rather than by
two numbers that agree until one is edited. Do NOT add a radius field.

STILL OPEN, with a default in place so nothing blocks: which net vertex each wire pulls on. Until
he says otherwise, wire branch order is taken as anchor order along the row, and the component
chin PRINTS THE MATCHED DISTANCES so a wire latched to the wrong anchor is visible rather than
silent.

### HIS FIVE-PART MECHANISM, described 2026-09-08 late. TO BE BUILT AFTER HE TESTS THE CURRENT ONE

His own description, and it supersedes the port shape above once built. THE MECHANISM IS FIVE
PARTS: (1) the frame, one joined mesh; (2) a second part of the frame in a DIFFERENT MATERIAL,
several objects; (3) the REELS, of which there are TEN per mechanism, but seven move identically
so he groups them as one, giving FOUR reel entries, which lands on the four-reel structure
already built; (4) the WIRE FRAMES; (5) the MOTORS, one joined mesh. He joins what can be joined
so each input takes one mesh, except the seven grouped reels, the wires, and the second frame
part. He proposes a component taking all five and feeding the exporter, plus an input for the
reels' rotation planes matching the reels' own data structure.

THE PLACEMENT CHANGE, which is the substantive part: ONE mechanism authored exactly right, placed
from THE FIRST FRAME OF EACH WIRE-FRAME GROUP. His words: "just give you one mechanism, exactly
how it should be, you take the starting planes and place the mechanism off each starting plane
set (remember 7 wires per mechanism and the strucutre will follow that goruped in 7, then number
of 7 per side, then sides)". And the constraint that will bite if ignored: "if the mechanism goes
on the opposite side it needs to be flipped and not be upside down" -- a MIRROR, not a rotation,
so handedness must come from his own frame axes rather than be inferred.

THE COST OF THAT CHANGE, flagged by the studio session and worth more than the change is worth
losing: deriving placement from the wire frame guarantees the mechanism and its wire can never
disagree, which is better than two independently authored values. BUT IT INVERTS THE DIAGNOSTIC
WE DELIBERATELY KEPT. Today the studio refuses to snap a wire, so a mis-placed mechanism shows as
a wire that stretches or floats and the drawing checks the placement. If placement comes FROM the
wire, a bad first frame moves the whole unit to a wrong but perfectly SELF-CONSISTENT position
and nothing on screen looks wrong at all. The error stops being visible precisely because the two
can no longer contradict each other. THEREFORE, binding on that build: the first wire frame
becomes a single point of failure, and the component must carry a proximity or sanity print
against it the way the tension tie's door guard already does, so his eye on the canvas has
something to catch it with.

ALSO SETTLED: the anchor and tension tie now arrive as ONE object by his choice, so the document
must keep them distinguishable even though they enter together, since the permanence view rests
on that distinction. And the wrap: "yes the wires are already fully wound in the image and my
model, you can use the frames to tighten and losen along the frames as long as it stays spooled
enough for now" -- a multi-turn wrap, so reel-owned routing frames stay STATIC (rotating a
multi-turn helix about its own axis is a visual no-op away from its ends), and the visible motion
comes from the spinner mesh turning.

### The reeve factor, settled 2026-09-08 late. NOT YET BUILT, and 1.0 is currently WRONG

THE GAP, found by the rebuild's own review: reeveFactor ships as a FIXED 1.0 with no author port.
Param's unit has FOUR WHEELS, so 1.0 is very probably wrong for his machine, and the symptom is
subtle rather than loud: every reel spins at the wrong RATE while the geometry, the wire paths and
the timing all remain correct, so nothing looks broken, it just does not match the machine.

THE SHAPE, ruled on the data rather than on convenience: PER WIRE, WITH A PER-MECHANISM DEFAULT.
The factor is a property of how one wire is reeved through its block, not of the block, and his
routing frames are ALREADY authored per wire (his tree is side, mechanism, wire, with a plane list
inside), so a per-wire factor matches what he authors while a document-level number would govern
42 individually specified wires with one value. The default is per mechanism because his seven
wires through a unit are almost certainly reeved alike, and making him type one number seven times
is how a transcription error arrives. THE DOCUMENT CARRIES THE RESOLVED VALUE ON EVERY WIRE, so
the studio never inherits or infers: the same principle already applied to net_vertex.

THE SANITY CHECK, the studio's idea and worth taking: a wire's wraps are visible in its route, so
counting direction reversals gives a rough expected advantage to compare against the declared
factor. THEIR CAVEAT IS THE IMPORTANT HALF and must be encoded as such: a wheel that merely guides
gives no advantage while a wheel that moves with the load does, and geometry cannot tell them
apart, so this can only ever flag a factor WILDLY at odds with the wrap count. It refuses nothing
and warns by name, like the tension tie's proximity guard.

### Four rulings from the studio's REPLY 4, binding on the collector rebuild

R1. EVERY WIRE CARRIES ITS OWN EXPLICIT net_vertex, whatever the tree groups it by. NON
NEGOTIABLE, and the studio is right to insist: a tree grouped side, mechanism, wire says which
mechanism a wire belongs to and NOTHING about which net vertex it pulls. If the net end were
implied by ordinal position we would have rebuilt the exact silent-wrong-answer failure their C1
was written to prevent, a wire landing on a real vertex that is simply the wrong one with nothing
on screen to show it. The document's top-level wires array already carries net_vertex; the
REBUILD MUST NOT let the named-port shape quietly replace it with position-in-tree.

R2. planes[0] IS THE NET END. Threading order fixes the sequence but not its direction, and the
studio builds the tube outward from the net vertex, so the list must read in the direction the
wire is drawn. TELL PARAM, since he authors them. The plugin also VALIDATES it, the door-guard
pattern: after placement, the first plane must sit nearer its net vertex than the last, and a
reversed list is named in the chin rather than silently drawn backwards.

R3. THE ROUTED PORTION IS CONSTANT, confirmed and reasoned rather than asserted. The routing
frames describe FIXED HARDWARE, the guide plate holes and the wheel wraps; the wire passes
through the same route whatever length has spooled. What changes is the FREE SPAN and the drum's
rotation. This is worth its weight to the studio: constant means the routed tube is built once
per instance and stamped with the placement, with only the free span rebuilt per time step, 42
short tubes a frame instead of 4200 circles. ONE HONEST CAVEAT to carry: as wire layers build up
on a spool the effective winding radius grows slightly, so a long take-up is not perfectly
constant at the drum itself. At this level of representation it is immaterial, and if his machine
ever needs the layer effect it is a refinement to the spin arithmetic, not to the routing.

R4. PERMANENCE COMES FROM THE PORT NAME, so no boolean is needed after all. With ports named
anchor, tension tie, mechanism, reel and routing, the anchor and the tension tie ARE the works
that remain, and the studio derives his "what remains when the machine is taken away" view from
the part kind. THE REQUIREMENT THIS PLACES ON THE REBUILD: the port name must REACH THE DOCUMENT
as the part's kind, not be flattened away into an anonymous parts list. That single property
serves the material tags, the permanence view, and their C9, and it is the reason the named-port
shape is better than the tree it replaces.

MEASURED FACT FROM THEIR SIDE, for his information: the studio's wire radius is 0.02 m, a 40 mm
diameter wire, set once at boot with no writer left in the code (the old Wire size slider was
removed in a later wave). So "the one predefined in the vaulted app" is 40 mm and cannot drift.
He should confirm 40 mm suits the design, since it is now the number his mechanism wires render
at as well as his net.

CONSEQUENCE HE SHOULD HEAR BEFORE HE SEES IT: the studio will NOT snap a wire to close a gap. It
draws from the declared net vertex to wherever his placement puts the first plane, so a mechanism
placed off its node shows as a wire that stretches or floats. That is right, and arguably a
feature, since the drawing becomes a check on the placement.

## BUILD RULING, 2026-09-08: this is now being built, and his inputs are firmer

His words: "can we work on the exporter that will then go to the vaulted app we have, so the
animation will be more consistent ... I need a foundation anchor, tension tie / column slider
rail, mechanism, wire routing for the mechanism. the rotating parts on the mechanism and the
wire movement as it happens. we already decided i can provide you frame and i can seperate the
moving parts from the mechanism even give you to rotational axis etc. we just need the sequence
and materials right on the other app after that." Coordination with the Vaulted session is
authorised by the same message, so P-003 goes to the channel.

THE PART LIST IS NOW HIS, and supersedes section 3's working names where they differ. Five
kinds travel:
  1. FOUNDATION ANCHOR. The ground fixing the tie pulls against.
  2. TENSION TIE / COLUMN SLIDER RAIL. His 2026-09-05 ruling stands: the sliding bar and the
     anchor are ONE authored mesh, because the column piece is the tension tie. Authored in
     place, exported in world coordinates, validated against the anchor rows, never placed by
     the plugin.
  3. THE MECHANISM. The pulley unit, in its two types: the EDGE REEL on the anchor lines and
     the NODE REEL under each principal node.
  4. WIRE ROUTING. His "series of frames" through the unit: an ordered list of planes in the
     unit's own local space, the path a wire takes around its wheels.
  5. THE ROTATING PARTS. NEW AND FIRMER: he now separates the moving parts from the body of the
     mechanism and supplies each part's ROTATION AXIS himself, rather than the plugin inferring
     one from a bounding box. So a mechanism arrives as a static body plus a list of spinners,
     each spinner carrying its own mesh, its own axis (a line or a plane in unit-local space)
     and its own kind.

WHAT STAYS DERIVED, because it must follow the physics rather than be animated by hand: the
ROTATION ANGLE of each spinner per frame, from the wire-length arithmetic of section 5. He
gives the axis; the frames give the motion. Nothing about the reeling is keyframed.

WHAT THE STUDIO OWES, his closing sentence "we just need the sequence and materials right on the
other app after that": the SEQUENCE is his three-act lifting order of section 5a (columns lift,
then pulleys tighten, then ribs reel in), and the MATERIALS are the tag vocabulary of section 7.
Both are asked of the Vaulted session in the channel note, since the writer side only supplies
tags and frames.

Written 2026-09-05 from the brainstorm with Param, his mechanism explanation and his two
refinements. FOR HIS READ: nothing here is built until he approves this document and the
companion channel note at docs/superpowers/notes/2026-09-05-note-to-vaulted-P-003.md. His
rulings from the brainstorm, verbatim where they are rulings:
- Realistic machine from the start; one continuous scene (reel into drop).
- "i can provide one asset that you can following the same logic always place" (the pulley unit).
- "This mechanism need to be placed always tangential to the anchors and perhaps the vector and
  placement is decided in the plugin to make it safe."
- "a mesh is take from an asset mesh, yes changing the logic to your other suggestion here."
- "maybe i will provide a series fo frames with the mechanism to direct where the wires shoould
  run and then thats quite an easy calculation?"
- "The anchor and the column piece actually will likely be fixed together because i will use the
  column piece as a tension tie, so maybe its better I just create that."

## 1. Shape and motion are two documents

The machine's MOTION is already exported: the formwork document's frames carry the net vertices
and the column nodes per time step, light, rebuilt on rest, re-sent when changed. The machine's
SHAPE becomes a sibling document, "<study>-mechanism.json", schema "bench.mechanism/1": heavy
(it embeds meshes), changing only when the design changes, and therefore re-sent only when its
bytes change under the standing per-document change keys. The studio loads the mechanism once
and replays the frames against it. Nothing per-frame is ever embedded.

## 2. The part model

Every object in the machine is one of three kinds, all driven by the frames' node streams:

- DEFORMING: the net. Faces fixed, vertices read per frame from the frames document. Exactly one
  such part, built studio-side from the topology the form document already carries.
- RIGID: a mesh bound to nodes. Column segments and cables remain data-driven primitives (node
  pairs drawn as tubes and lines at declared radii). Designed hardware is a rest-pose mesh plus a
  placement, static or node-following.
- SPINNING: a rigid part with a local rotation about a declared axis, driven by derived wire
  length (section 5).

## 3. How geometry travels: wired in, embedded once

All designed meshes enter THROUGH THE CANVAS, not through files: a new collector component
(working name MECHANISM, "ME") whose output feeds Export beside RES and Cells. Ports, all
optional, item or tree access as noted:

    PU  Pulley unit meshes (TREE, one branch per pulley TYPE): branch {0} is the EDGE REEL, the
        anchor-line unit; branch {1} is the NODE REEL, the unit that sits by each principal node
        and reels the sag and relax of the net (added by Param 2026-09-05: "another pulley
        mechanism that goes by each principle node ... on the ground or just below each node").
        A missing branch means the machine has no reels of that type. The ports stay four; the
        family lives in the tree.
    PS  Pulley sockets (tree of planes, branches matching PU): the routing frames embedded in
        each unit's own local space, IN WIRE ORDER, directing where a wire runs through the
        wheels. His "series of frames". Stored with the asset, transformed with every instance.
    PR  Reeve factors (tree of numbers matching PU, default 1.0 per type): rope crossing the
        spool per unit of net-side length change, the four-wheel advantage as one number.
    SR  Spool radii (tree of numbers matching PU; default per type from the unit's bounding box
        smallest dimension over 4, said in the chin so the default is never silent).
    AT  Anchor tie mesh (item or tree, one per anchored row): the sliding ground bar, the anchor
        clamps and the column tension tie AS ONE AUTHORED PIECE, his ruling of 2026-09-05: "i
        will turn the sliding bar and the anchor as one mesh, the sliding bar is the tension tie
        in my mind." Authored IN PLACE on the form and exported in world coordinates: the plugin
        computes no placement for it, it VALIDATES it (a proximity check against the anchor rows,
        warning by name when the piece strays), the door-guard pattern. The generated-default
        clamp stays PARKED: this piece is structural and the quick fix stays in his hands.
    MT  Materials (tree of text): tags per part, matched by position to the ports above; a
        missing tag falls back to the part's name.

The collector serialises each mesh once (vertices, faces, its sockets, its material tag) and
hands Export one mechanism payload. Export embeds it in the mechanism document with its own
change key. Wire weight: the meshes travel once and then only on change, per the standing
build-on-rest rules.

## 3a. Port set settled 2026-09-08, against the BUILD RULING's item 5

DESIGN-CHECK AMENDMENT. Section 3 above predates the BUILD RULING at the top of this document and
did not move with it: the ruling has Param separating each mechanism's static body from its
spinning parts and authoring each spinner's OWN rotation axis himself, but the port table above
carries no axis at all, PU is one mesh per pulley type with nothing under it for a spinner to be,
and SR's default reads off "the unit's bounding box" as though body and spinner were still one
thing. That is section 3 contradicting the ruling it sits under, not the ruling contradicting the
code; checked against the engine (MouldGeometry, MouldColumnsDto, the writer) everything else in
this document stood up unchanged. Settled here, port set unchanged in count but two ports change
shape and one is added:

    PU  Pulley unit meshes (TREE, TWO-LEVEL PATH {type}{part}): {type} unchanged, 0 EDGE REEL,
        1 NODE REEL. WITHIN a type branch, {part} 0 is ALWAYS THE STATIC BODY; {part} 1..N are the
        SPINNERS, in order. A branch with only {part} 0 is a fully static unit, legal. A missing
        {type} branch still means no reels of that kind.
    AX  Spinner axes (NEW, tree, matches PU for {part} >= 1 ONLY): one plane per spinner, unit-local
        space, plane origin a point on the axis and plane Z the axis direction. {part} 0 (the body)
        has no entry and none is read. A spinner mesh in PU with no matching plane in AX is refused:
        the axis is authored, never inferred, and this pairing is how that is enforced rather than
        by convention alone.
    PS  Unchanged, still matches PU's {type} only, not {part}: a unit's wire route is a property of
        the whole unit, not of one spinner.
    PR  Unchanged.
    SR  Unchanged in shape (one number per {type}); DEFAULT NOW NAMES ITS SOURCE EXPLICITLY: the
        {part} 1 spinner's (the spool's) bounding box smallest dimension over 4 when one is wired,
        falling back to the body's own bounding box when a type has no spinner at all.
    AT  Unchanged.
    MT  Unchanged rule (tags per part, matched by position, missing tag falls back to the part's
        name); shape widens to match PU's full two-level path plus one entry per AT row.

WHICH SPINNER IS DRIVEN, flagged rather than assumed. SR and PR are one number per TYPE, not per
spinner, which already presumes exactly one driven spool per unit: this settles that {part} 1 is
that spool and the only spinner section 5's derived rotation ever turns; any {part} 2, 3, ... are
cosmetic wheels, carried with mesh and axis but not rotated, squarely section 9's "cosmetic,
later" scope. No eighth port for a spinner "kind" tag is added on this reading. If Param means more
than one driven spinner per unit, this convention is wrong and needs a real port; put it to him
before the collector is built rather than after.

Full field-by-field detail (the bench.mechanism/1 document shape, the change key, and the wire-id
confirmation against the frames document) is the implementer's brief, not repeated here.

## 4. Placements: the plugin's half, computed every solve

The plugin computes, from the Result it already owns:

- EDGE REEL INSTANCES: one placement frame per reeling group, origin on the anchor line, X
  tangent to the anchor row, Z up, exactly his "always tangential to the anchors ... decided in
  the plugin to make it safe". Count scales with the wires. Each instance carries the LIST OF
  WIRE IDS it serves (the wire-to-unit mapping), where a wire id is the pair (net vertex index,
  anchor node index) the frames already animate.
- NODE REEL INSTANCES: one per principal node, plan position under the node, oriented to the
  bar's tangent there. THE VERTICAL RULE IS DELIBERATELY OPEN, his words "on the ground or just
  below each node ... i am deciding on still": the plugin's placement function carries a mode
  (ground z, or a fixed drop below the node) settled when his design lands, and NOTHING
  DOWNSTREAM DEPENDS ON THE CHOICE, because the document carries only the resulting frames. The
  default until he rules is ground. Wire ids for these reels pair a net vertex index with the
  principal node's index in the frames' column-node stream, so the sag and relax wires derive
  their spin by the same section 5 arithmetic, in whichever direction the physics runs them.
- THE ANCHOR TIE takes NO computed placement: authored in place, world coordinates, validated
  against the anchor rows with a named warning when it strays (rule above). One piece per row
  where rows are separate.
- All placements are data in the mechanism document: {part, frame, wires?}. The studio stamps
  instances; it never re-derives placement logic.

## 5. The reeling, derived, never authored

The studio derives each wire's drawn path per frame: net endpoint (moving, from the frames), then
through its instance's sockets in order (static per instance). The spooled length change per
frame is delta(net-side length) times the reeve factor; reel rotation is that over two pi times
the spool radius. The loosen-then-tighten behaviour Param described is not animated by anyone: it
falls out of the frames, because the wire lengthens as the net rises and shortens as it draws
into curvature. The plugin exports two facts only (mapping, radius-and-reeve); the studio owns
the arithmetic.

## 5a. The lifting order, his ruling of 2026-09-05 evening

Verbatim: "the mechanism is the columns lifting the net, the pulleys tighten when net is
raised correctly and ribs are also reeled in to form the final shape." Three phases, binding
on the scene and on the diagnostics:

1. THE COLUMNS LIFT. The push-up comes from the columns rising on their sliding ground
   mechanism, carrying the net at the bars. The reels do not raise anything.
2. THE PULLEYS TIGHTEN once the net is raised correctly: the edge reels take up the
   anchor-line wires.
3. THE RIBS ARE REELED IN to form the final shape: the node reels draw the ribs down into
   curvature.

CONSEQUENCE FOR DIAGNOSE: the Animate warning "N nodes sit ABOVE the bare surface ... a reel
only pulls down ... it needs a mechanism this machine does not have" models a reels-only
machine and is WRONG about this one: the column lift IS the push-up provider, and the frames
already animate it (bars risen measured in the same chin). The warning must be re-modelled:
push-up demand is served by column lift where a node's demand is reachable through the bars
from a rising column, and the warning only names the nodes NO column can serve. Until that
lands, the current warning over-reports and should be read against this section.

One clock: the reel (the formwork frames, 0 to 100 on the machine's own timeline) runs first;
the voussoir drop (the studio's own staging, from the skin document) follows on the same clock,
beginning when the net holds its final form. The handoff instant is the frames' hold phase.
Timeline details are the Vaulted session's half and are put to them in the channel note; the
writer-side commitment is only that the frames keep their standing guarantees (boundaries
present, time-100 equals the form document's equilibrium).

## 7. Materials

Tags travel with parts (section 3). The studio maps tag to rendered material and owns the look.
Param's opening vocabulary, from his own render, to correct at will: cable net bright steel
wire; columns grey painted steel; sliding bar near-black steel; pulley units pale timber-tone
blocks; anchor ties dark cast steel.

## 8. What must be checked, each proved able to fail

1. The mechanism document embeds each wired mesh ONCE, byte-stable across identical solves, and
   its change key moves when a mesh, socket, tag or placement changes and not otherwise.
2. Placement frames: tangential rule pinned on the crown-arch fixture (known anchor rows), tie
   frames on the free-edge fixture; a rotated model rotates its placements with it.
3. Wire mapping: every wire id references a net vertex and an anchor node that exist in the
   frames; the harness cross-checks counts.
4. Sockets: transformed sockets equal hand-computed placement times local plane on a fixture.
5. Codec round trip: mechanism payload through the collector, Export, and back through the
   reader-side json, lossless.
6. The collector with NOTHING wired produces no mechanism document and no warning noise: the
   machine view is optional per study.

## 9. Out of scope, said so nobody reinvents it

The studio-side rig player (instancing, spin, the continuous timeline, materials rendering): the
Vaulted session's half, requested in the channel note, built against fixtures they define. The
generated-default anchor clamp: parked. Per-frame mesh baking: never. The wheels' individual
spin within a unit beyond the spool: cosmetic, later, driven by the same derived lengths if ever
wanted.

## 10. Two amendments to the settled maths, 2026-09-08, from his first real solve

Both come from the chin his own ten-reel mechanism printed, not from review. They amend sections
above; where they disagree with anything earlier, these win.

### 10a. Ownership is radial AND axial

Section 3's ownership rule tested a routing frame's perpendicular distance to a reel's AXIS, which
is an infinite line. A reel therefore claimed anything inside its radius however far past its own
end faces that frame sat, so a wire running parallel to a drum read as riding on it and the studio
would have spun it. A reel now owns only what lies inside its radius AND between its own end faces,
with a margin of a quarter of its own radius past each face.

The ambiguity report changes with it. A wire wrapped on a drum sits at that drum's surface on every
frame of the wrap, and the radius it is measured against is the mesh's outermost extent -- the
flanges -- so a CORRECT wrap lands at ratio about 0.92, inside the +/-0.15 band, on every frame,
for ever. Warning per frame there says nothing and buries everything else: his read fifteen rows
deep and then "Further warnings not shown". Warnings are now kept for the two cases where the
answer could flip to different BEHAVIOUR -- a frame just OUTSIDE a reel that the body therefore
holds still, and a frame two reels both reach -- gathered and said once per wire and reel. A frame
just inside the reel that owns it is tallied in a note.

### 10b. A placement falls back to a fit from all seven origins

The placement maths derive the whole instance transform from ONE correspondence, so the instance
inherits placement plane [0]'s own X and Y. A routing frame's own X and Y spin freely about the
wire's tangent (a perp-frame on a curve picks them arbitrarily) and an anchor plane's axes are
whatever they were authored as. There is no reason for the two to agree, and when they do not,
every one of the other six wires lands rotated about plane [0] while all seven origins sit exactly
where they belong. His first solve read 1.364922 m of residual on all three mechanisms of side 0
and 1.173451 m on all three of side 1 -- identical within a side, so the three copies agree with
each other and the disagreement is between the AUTHORED MECHANISM and the PLACEMENT PLANES.

Edge lengths decide which fault it is, because they survive any placement. Matched pair for pair
they separate orientation from everything else; sorted they separate a reordering from a genuine
shape difference. So, when the residual exceeds the 0.001 m guard:

1. Seven origins congruent PAIR FOR PAIR: the fault is orientation alone. The transform is REFITTED
   from all seven origins -- basis founded on the base point, the furthest correspondence and the
   most off-axis one, both handednesses tried and the better kept, so a genuinely mirrored side
   still yields a genuine reflection derived from where its anchors sit rather than from a
   hand-authored left-handed plane. The chin says the refit happened and gives both residuals.
   Refused, with the reason named, when the origins are collinear or fewer than three wires carry
   frames; plane [0]'s axes still place the instance then.
2. Congruent only as a SET: the branches are in different orders. Named, NOT refitted -- a fit onto
   the wrong pairing places a plausible, wrong machine.
3. The wires' LAST frames congruent instead: the routes are threaded the other way round, against
   his own R2 ruling that Route[0] is the net end. Named, not refitted.
4. Nothing congruent: the placement planes and the wire ends are different geometry. Named.

The one-correspondence derivation stays primary. The fit is a fallback that engages only where the
primary demonstrably fails and the data demonstrably supports it, and it is never silent.
