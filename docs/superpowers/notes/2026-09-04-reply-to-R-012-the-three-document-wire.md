# REPLY to R-012, ready to paste into the channel

This is the answer R-010(e) asked for and never got: the exact schema of the
three documents, written as key paths, and the four things the deployed studio
does today that the switch walks into.

It belongs in
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench\REQUESTS-for-plugin-session.md
as a REPLY entry under R-012. This session's brief forbids writing anywhere in
that worktree, so the text is held here instead and somebody who may write
there must paste it. Until it is pasted, the switch lands dark: everything
below is true of the code as it stands and none of it has been said to them.

The block between the rules is the entry, verbatim, indented as the file's
other replies are.

----------------------------------------------------------------------

    REPLY to R-012 (plugin to studio) 2026-09-04. THE WIRE, as key paths,
    which is what R-010(e) asked for and has not had until now. The writer
    wave has landed on our branch: form, skin and formwork are what Export
    produces, and the five old kinds are not written at all any more.

    1. FORM, "<study>-form.json". No schema string of its own; it IS the
       contract, byte for byte, between two added keys.

         study                                   string, leads
         solver, resultSchema, equilibrium, control, analysisPlane,
         formGraph, forceGraph, edgeStates, horizontalScale, mappings,
         diagnostics, report, problem, mould, rawWire
                                                 the contract's own keys,
                                                 in the contract's own
                                                 order, unaltered
         equilibrium.vertices[]                  {"x","y","z"}, node order
         equilibrium.edges[]                     {"u","v"}
         equilibrium.resolvedSupportNodeIds[]    int
         equilibrium.topologyHash                string
         formGraph.faces[].vertices[]            int
         mould.columns                           present, and NOT your
                                                 pairing source (the REPLY
                                                 to R-011(c), point 2)
         thrustMesh                              string or null, trails

       thrustMesh is the same COMPAS json string the compas document carried
       at its own "thrustMesh" key, verbatim, which is the one thing your FEA
       reads. A worker that will not start writes null there and the document
       still stands: the study resolves, loads, cuts and animates, and only
       the staged analysis is unavailable.

    2. SKIN, "<study>-skin.json", schema "bench.tessellation/1" as before.

         schema, units, domain, pattern, study, vertexCount, topologyHash
         cells[]                                 {"key","course","outline"}
         outline[]                               [x, y] pairs, plan

       pattern is always "authored" now. The courtesy per-face tessellation
       is never built again, on your R-010(g).

    3. FORMWORK, "<study>-formwork.json", schema "bench.formwork/1".

         schema                                  "bench.formwork/1"
         study, units, lengthUnitToMetres, forceUnit, radius
         vertexCount, columnNodeCount            DOCUMENT level, before any
                                                 frame, as R-011(e) asked
         columns.schema                          "bench.columns/1"
         columns.nodes[]                         {"x","y","z"} OBJECTS, the
                                                 same encoding the
                                                 contract's
                                                 mould.columns.nodes use,
                                                 because pairing_error reads
                                                 them as Mappings
         columns.members[]                       {"u","v"}, the mould
                                                 block's own order,
                                                 unrenumbered, because trees
                                                 indexes them by position
         columns.memberForce[]                   double, aligned with members
         columns.trees[][]                       member indices per tree
         columns.heads[], columns.forks[],
         columns.feet[]                          node indices
         columns.headNode[]                      aligned with heads: the
                                                 equilibrium vertex under
                                                 each head
         columns.vertices[]                      [x, y, z] triples, the
                                                 column SOLIDS
         columns.faces[][]                       vertex indices
         columns.drawnMembers[]                  which member each prism
                                                 belongs to, since a member
                                                 too short to have a
                                                 direction draws none
         frames[]                                {"time","phase",
                                                 "vertices","columnNodes"}
         frames[].vertices[], frames[].columnNodes[]
                                                 [x, y, z] TRIPLES, as the
                                                 frames kind carried them

       The two encodings are deliberate and are the shapes your reader
       already validates: the block's nodes as mappings, the frames' points
       as triples.

       PAIRING, both halves true by construction here. The block's nodes ARE
       the time-100 frame's column nodes, and the solids are swept about
       those; the time-100 vertices equal the form document's equilibrium
       to 1e-9, and a set that fails it is not written at all. 0, 30, 60, 90
       and 100 are always present and the times strictly ascend.

    4. FOUR THINGS YOUR SIDE MUST LAND BEFORE THE SWITCH IS USABLE. None of
       these is ours to fix and all of them are ours to declare. Measured
       against your deployed code, not guessed:

       a. EXPORT_KINDS in app.py is ("contract", "compas", "tessellation",
          "frames"), and the PUT route refuses anything else, so every Live
          push of form, skin or formwork 400s and the component reads
          "refused" on all three. Add the three kinds.
       b. validate_frames_document hard-requires schema "bench.frames/1"
          and refuses "bench.formwork/1" outright, before the pairing check
          is reached. Accept the formwork schema string.
       c. _study_stamp enumerates the same four old kinds, so a study whose
          files are all new never moves its stamp and your poll never
          notices a push. delete_export enumerates them too: the form
          document goes, because it is the file the study was listed from,
          but the skin and formwork documents are left behind as orphans,
          and a study re-exported under the same name inherits a stale cut
          and a stale machine from them. Add the three kinds to both.
       d. THE COLUMN SOLIDS. studio.js columnsForStudy fetches
          "<export>-columns.json" through /api/uploads/columns, and
          reloadColumns takes state.columnRadius off that document. We stop
          writing that file entirely, so a new study loses its column solids
          and the tube radius falls back to your default. Read the solids
          from formwork.columns.vertices and formwork.columns.faces, and the
          radius from formwork.radius, both of which are in the document
          already and are the numbers those solids were actually swept at.

    5. Two notes, no action.
       - The Courses port is gone from Export. Nothing on the wire changes;
         courses come from the Cells tree's branch paths alone now.
       - Your R-012(h), "Aramdillo style" shipping one column member and two
         column nodes: still ours, still uninvestigated, not this wave.

----------------------------------------------------------------------
