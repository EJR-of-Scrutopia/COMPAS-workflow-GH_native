# The machine goes to Vaulted: the mechanism document and the rig player

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
    BR  Bar mesh (item): the sliding ground bar the columns rise from.
    AT  Anchor tie mesh (item): the fused anchor clamp and column tension tie, authored by
        Param. (The generated-default clamp is PARKED, deliberately: he authors this piece
        because it is structural and he wants the quick fix in his own hands.)
    MT  Materials (tree of text): tags per part, matched by position to the ports above; a
        missing tag falls back to the part's name.

The collector serialises each mesh once (vertices, faces, its sockets, its material tag) and
hands Export one mechanism payload. Export embeds it in the mechanism document with its own
change key. Wire weight: the meshes travel once and then only on change, per the standing
build-on-rest rules.

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
- BAR PLACEMENT: the sliding bar attached to the anchors, one frame (or one per span where spans
  are separate), oriented along the anchor row.
- ANCHOR TIE INSTANCES: one frame per tie position along the anchored edge, oriented to the
  skin edge tangent, so his one authored piece lands correctly on every form.
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

## 6. The continuous scene

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
