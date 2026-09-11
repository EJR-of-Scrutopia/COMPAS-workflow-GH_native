# bench.frames/1: how the exporter will write the animation, so the reader can build from the same logic

Written 2026-09-03 by the plugin session, which will implement the writer in Export after its skin
phase. This document is the contract between the two sessions. The reader side builds against it
tonight; if anything here proves wrong against the studio's needs, file the objection in
REQUESTS-for-plugin-session.md rather than diverging. Where this document and section 7 of
HANDOFF-studio-animation-2026-09-03.md disagree, THIS document governs; it is the fuller statement.

## 1. What the frames ARE

One frame is the whole machine at one instant of the build: every net vertex's position, and every
node of the built columns (feet, forks, heads), on the machine's own 0..100 timeline. The sequence
is the formwork build: the net reeled out flat on the ground, sagged to Pre-Sag, lifted, reeled the
rest of the way, held.

The writer does NOT invent this motion. It calls the same engine functions the Animate component
uses on every slider tick (the phase arithmetic, the per-node blend, the live column nodes), so a
frame in the file is bit-comparable to what Grasshopper shows at that time. The reader therefore
NEVER reimplements the motion; it interpolates positions between the frames it is given, linearly,
and that is all.

## 2. The timeline semantics, so the numbers mean something when displayed

- time runs 0 to 100. Phases: reel 0-30 (the net, laid out on the ground, takes up sag until
  Pre-Sag), raise 30-60 (it lifts), finish 60-90 (the remaining sag reels in), hold 90-100
  (nothing moves).
- Two internal scalars drive the blend, sag and lift; both are continuous across every phase
  boundary and never decrease. The reader does not see them, only their effect.
- Frame at time 0: the net's start state, flat on the ground in its laid-out plan position (the
  drawn pattern where one exists, else the ground-flattened solved plan). Its plan position is NOT
  the solved plan position; anchors included, everything moves during the build.
- Frame at time 100: the solved state exactly. vertices[i] at time 100 equals the contract's
  equilibrium.vertices[i] to full precision.
- Column FEET never move (they are fixed on the ground). Forks and heads move with the net: a
  fork keeps its built fraction along its rail throughout, so trunk, fork and main head stay
  collinear in every frame.

## 3. Sampling: which times get a frame

- Base sweep: every 2.0 time units, 0 to 100 inclusive (51 samples).
- The phase boundaries 0, 30, 60, 90, 100 are always present exactly (the base sweep already
  contains them; if the step ever changes they are inserted and the list deduplicated).
- Strictly ascending, no duplicates. Expect roughly 50; NEVER assume the count or the step, read
  the array.

## 4. The file, exactly

Name: "<Study>-frames.json", beside "<Study>-contract.json" in the same set, written after the
columns kind in the set's order. Same escaping of the study name as every other kind. UTF-8, plain
JSON, full double precision (no rounding beyond what JSON serialisation of doubles does; the
contract's own vertices are written the same way, which is what makes the time-100 equality above
checkable).

    {
      "schema": "bench.frames/1",
      "units": "m",
      "study": "Column diagnosis",
      "vertexCount": 441,
      "columnNodeCount": 57,
      "frames": [
        {
          "time": 0.0,
          "phase": "reel",
          "vertices":    [[x, y, z], ...],   // exactly vertexCount triples
          "columnNodes": [[x, y, z], ...]    // exactly columnNodeCount triples
        }
      ]
    }

- "schema": consumers prefix-check "bench.frames/" and then require the version they support,
  mirroring the tessellation sidecar's convention.
- "units": always "m" today; read it anyway.
- vertices[i] is THE SAME NODE as equilibrium.vertices[i] in the contract, in the same order, in
  every frame. This is the join key to everything else in the study; there is no separate id list.
- columnNodes[j] is the j-th node of the mould's columns block (the same node list the contract's
  mould block carries: feet, forks, notch heads), same order in every frame. Members of the
  columns block index into that list, so the reader can draw moving members by joining the same
  indices it joins for the static columns, frame by frame.
- "phase" is the label at that instant: "reel", "raise", "finish" or "hold". At a boundary the
  incoming phase's label is used; cosmetic, for display only, the motion is in the numbers.

## 5. When the file is written, and Live

- Export writes the frames kind whenever the Result carries a Mould block with columns, i.e.
  whenever there is a machine to animate. No Mould block, no frames file, and that is not an
  error. The sequence derives from the solved state and the columns, so it is written even when
  the author never touched Animate.
- The LIVE connection PUTs the frames file as one more kind of the set, retried on 409 like the
  others, and it JOINS THE SET KEY, so a change that alters the animation re-uploads the set.
- The file is deterministic for a given Result: same study, same solve, byte-identical frames.

## 6. Guarantees the reader may enforce as validation (and should)

1. schema prefix "bench.frames/", version 1.
2. frames non-empty; times strictly ascending; 0 and 100 present; 30, 60, 90 present.
3. every frame: vertices.length == vertexCount, columnNodes.length == columnNodeCount, every
   coordinate finite.
4. vertexCount equals the study contract's equilibrium.vertices length (reject the pairing if
   not; it means the set is mixed from two solves).
5. the time-100 frame's vertices equal the contract's equilibrium.vertices (tolerance 1e-9): a
   cheap, decisive integrity check of the whole pairing.
6. phase labels drawn from the four words above.

## 7. A hand fixture the reader can build against tonight

Three vertices, two column nodes, three frames. Not physically meaningful, structurally exact:

    {
      "schema": "bench.frames/1",
      "units": "m",
      "study": "fixture",
      "vertexCount": 3,
      "columnNodeCount": 2,
      "frames": [
        { "time": 0.0,  "phase": "reel",
          "vertices": [[0,0,0],[1,0,0],[2,0,0]],
          "columnNodes": [[0.5,0,0],[0.5,0,0]] },
        { "time": 30.0, "phase": "raise",
          "vertices": [[0,0,0],[1,0,0.4],[2,0,0]],
          "columnNodes": [[0.5,0,0],[0.5,0,0.2]] },
        { "time": 100.0, "phase": "hold",
          "vertices": [[0,0,0],[1,0,1],[2,0,0]],
          "columnNodes": [[0.5,0,0],[0.5,0,0.5]] }
      ]
    }

(Boundaries 60 and 90 are omitted here ONLY because this is a toy; the reader's validator should
flag their absence, and the test for the validator can use exactly this file to prove it.)

## 8. What the writer will NOT do, so the reader does not wait for it

- No per-frame tessellation, forces, or voussoir states: the frames are the MACHINE and the NET.
  The voussoir drop animation remains the studio's own, driven by courses as today.
- No compression, no binary format, no separate index file.
- No frames for studies without a mould block, and no partial files: the write is atomic, and this
  line now describes the code rather than a habit it did not have. When this was written the
  exporter used File.WriteAllText for every kind, which truncates the destination and then fills
  it; the studio's importer audit found that and filed it as R-005. It is fixed. EVERY kind,
  frames included, is now written to a temporary in the destination's own directory and then moved
  over the destination with overwrite (AtomicFile in DeliveryComponents.cs), so the destination is
  never opened for writing and a reader sees the whole old document or the whole new one.
  One consequence, stated rather than hidden: the move has to displace the destination, so a
  reader holding a kind open without granting delete sharing makes the WRITE fail rather than the
  read tear. The old file stands whole, Export reports the failure by name, and the next solve
  writes again.

## 9. Open points, answered by default unless tonight's reading objects

- Frame count 51 at step 2.0: chosen for smoothness against file size (roughly 51 x 441 x 3
  doubles, about 1.5 MB for the diagnosis-sized net). If the studio wants fewer or more, file it
  in REQUESTS; the reader must not care either way.
- Interpolation between frames is the reader's, linear per coordinate. The motion is smooth and
  monotone, so linear between 2.0-unit samples is visually clean; if the frontend wants easing,
  ease the PLAYBACK CLOCK, never the positions.

## 10. Optional per-frame forces (2026-09-11)

Added by the studio session. This section amends the first bullet of section 8 on ONE point:
the writer MAY now add forces to a frame. It still writes no per-frame tessellation and no
voussoir states, and the voussoir drop stays the studio's own animation. Everything here is
optional; a writer that adds nothing produces a document the reader treats exactly as before.

What the studio does WITHOUT these keys, so the writer knows what the addition buys: three
graphs stand beside the viewport during the build animation (cable force per cable, the load on
the formwork, column force). With positions alone the studio has no force at any instant except
the last, so it draws a linear force-density model: the final TNA forces from the contract's
equilibrium.memberForces and equilibrium.forceDensities, scaled through the build with the placed
weight. That is a model of the cables, not a reading of them; the reel phase in particular has
no weight on the net at all, and the model reads as zero there whether or not the net is taut.
Forces written by the machine's own solver replace that model with the number the machine saw.

Two keys, each optional, each written on EVERY frame or on none:

- "forces": one number per equilibrium edge, in equilibrium.edges order (the same index space
  as equilibrium.memberForces and equilibrium.forceDensities in the contract, and the same order
  the studio serves as "edges"). kN. The cable's axial force at that instant as the machine's own
  solver (Kangaroo or Karamba) sees it. Sign convention: positive_tension, the contract's own
  equilibrium.signConvention; a cable in tension is positive, and a value at or below zero means
  the cable is slack at that instant. The studio graphs the MAGNITUDE, so the sign is carried for
  the reader who wants it and never decides what is drawn.
- "columnForces": one number per column member, in the document's own columns.members order (or
  the contract's mould.columns.members order for a document that carries no columns block of
  its own, since that list is then the one the reader draws). kN. The axial force in the member
  at that instant. Sign convention: positive_compression, so a column standing on its foot and
  carrying the net reads positive, the opposite sense to the cables above because that is the
  sense the contract's mould.columns.memberForce already uses. The studio graphs the magnitude
  here too.

Rules the reader enforces, and what it does when they are broken:

- All-or-nothing across frames, per key: a series carried by some frames and not others is
  dropped whole, with one disclosed sentence. A graph drawn from half the frames would read as
  the forces falling to nothing at the instant the writer stopped writing them.
- Every value a finite number; one and the same length across frames. A frame whose list is
  shorter, or carries a null or NaN, drops the series whole, with the frame named.
- The length is checked against the contract at the point of use (the formwork route), never at
  upload: the document alone cannot know the edge count. A series of the wrong length is dropped
  from every frame and the route's top-level "notes" list says so ("per-frame forces dropped:
  800 values for 2253 edges").
- A dropped series never costs the act. The positions are validated exactly as before, and the
  studio falls back to the force-density model for the graph the series would have fed.
- Units are kN as they are in the contract; the reader converts nothing.

The formwork route serves, beside the frames: "forceDensities", the contract's
equilibrium.forceDensities filtered to the served edges in the same order (kN/m, null when the
contract has none or the length does not match), and "columns": {"members", "forces",
"forceUnit": "kN"}, where "forces" is the contract's mould.columns.memberForce aligned to the
served members, null with a note when the members list is the document's own and differs from
the contract's. Both feed the fallback model; neither needs anything from the writer.
