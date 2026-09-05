DRAFT, NOT YET PASTED. This is the channel entry for the Vaulted session, to be appended to
REQUESTS-for-plugin-session.md as P-003 ONLY after Param approves it and the companion spec at
docs/superpowers/specs/2026-09-05-mechanism-into-vaulted-design.md. The indentation matches the
channel's house style.

----------------------------------------------------------------------

P-003 (plugin to studio) 2026-09-05. Status: OPEN. THE MACHINE COMES TO
VAULTED, and this entry asks for your half: a rig player.

PARAM'S INTENT, his words: the studio should show the reeling mechanism
"working correctly ... we export the frames so we see it moving the
mechanism as intended", realistic from the start, one continuous scene
where the machine reels the net and the voussoirs then drop onto it.

THE WRITER'S HALF, specced and awaiting his approval before building
(docs/superpowers/specs/2026-09-05-mechanism-into-vaulted-design.md in
the plugin repo): a new sibling document, "<study>-mechanism.json",
schema "bench.mechanism/1". SHAPE ONLY, no per-frame data ever:

  a. PARTS: designed meshes wired in on the canvas and embedded ONCE
     (vertices, faces, material tag): the pulley unit, the sliding
     ground bar, the fused anchor-plus-tension-tie. Heavy but rare; it
     re-sends only when its own change key moves, per the standing
     per-document keys.
  b. SOCKETS: the pulley unit carries an ordered list of planes in its
     own local space, the routing frames a wire runs through around its
     four wheels. Placed instances carry their sockets with them.
  c. PLACEMENTS: plugin-computed frames per instance (pulley units
     tangential to the anchor rows, the bar attached to the anchors,
     one tie frame per position along the anchored edge), each pulley
     instance carrying the WIRE IDS it serves, a wire id being the
     (net vertex index, anchor node index) pair the frames already
     animate.
  d. DECLARED FACTS: spool radius and reeve factor (rope crossing the
     spool per unit of net-side length change; his unit has four
     wheels).

YOUR HALF, requested, in your order of preference:

  1. READ the mechanism document beside form, skin and formwork; treat
     absence as "no machine view for this study", quietly.
  2. INSTANCE each part's mesh at its placement frames; apply material
     tags through your existing material system (tags in the document;
     the mapping tag-to-render is yours, Param supplies the vocabulary).
  3. DRAW EACH WIRE per frame as: net endpoint (from the frames you
     already replay) then through its instance's transformed sockets in
     order. The routed portion is constant per instance.
  4. SPIN each reel by the derived arithmetic: rotation = delta(net-side
     wire length) x reeve factor / (2 pi x spool radius), signed, so the
     reels pay out as the net rises and reel in as it tightens. Nothing
     is authored; the frames already encode the loosen-then-tighten.
  5. THE CONTINUOUS SCENE: one clock, the reel (frames 0..100) running
     straight into your voussoir drop, the handoff at the frames' hold
     phase. The timeline design is yours; the writer guarantees only
     the standing frames invariants (boundaries present, time-100
     equals the form document's equilibrium).
  6. The net itself as a deforming mesh from the frames' vertex stream,
     if you do not already draw it so in the formwork act.

NOT ASKED: per-frame meshes (never written), the wheels' cosmetic
individual spin (later, same arithmetic, if ever), any placement logic
on your side (the plugin owns placement so it is always safe, his
ruling).

SEQUENCING: the writer side builds after Param approves the spec; your
half can start from this entry's schema sketch whenever suits, and the
first mechanism document lands beside a study for you to read the
moment the collector exists. Corrections to the schema welcome under
this entry before either side builds; the writer owns the shape, you
own the reading, as ever.

----------------------------------------------------------------------
