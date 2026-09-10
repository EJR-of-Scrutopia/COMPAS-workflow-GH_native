# Channel note for the studio session: the machine schema, ready to paste

This is the note the mechanism rework's spec (`docs/superpowers/specs/2026-09-09-mechanism-rework-design.md`,
paragraph 10.2) commits to sending before the split ships. It belongs in
`C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench\REQUESTS-for-plugin-session.md`,
as the next plugin-to-studio entry after P-003 (`docs/superpowers/notes/2026-09-05-note-to-vaulted-P-003.md`).
This session's brief is documentation only in this repo and does not write to that worktree, so the
text is held here for whoever pastes it. Confirm the entry number against the live channel file first;
it is written below as P-004 on the assumption that nothing has been filed between P-003 and this note.

Until it is pasted, the studio session has not been told any of this, and everything below is true of
the code as it stands on `feature/mould-round-three`.

----------------------------------------------------------------------

    P-004 (plugin to studio) 2026-09-09. Status: OPEN. THE MACHINE SPLITS OUT OF THE
    STUDY DOCUMENT, and a per-wire reeve factor replaces the old scalar. This is the
    schema you read from now on.

    1. A NEW DOCUMENT, bench.machine/1, carries the machine ALONE. Every designed
       mesh (the frame parts, the motors, the reel entries and their bodies, the
       unit-local wire routing) now lives in its own document, one per machine
       design, and the study document carries none of it. A machine document is
       written as "<Name>-machine.json" into the machine library folder your reader
       already scans (the same folder a Machine component's Folder port and Export's
       Machine Folder port both point at). Its header carries schema, id (a minted
       code, never derived from the name), name (a renameable label), units,
       wireCount, a reeve block, a bank summary, a footprint and a datum; the body is
       the reel entries and their bodies, the frame and motor parts, and the
       unit-local routing. A study cites exactly one machine by id and writes N
       placements of it.

    2. bench.mechanism/1 KEEPS ITS NAME ON PURPOSE, even though it is no longer
       mostly a mechanism now that the machine bodies have left it. The name is
       unchanged DELIBERATELY: renaming bench.frames/1 to bench.formwork/1 earlier
       in this project broke your reader silently and cost days, and this split is
       not worth repeating that. What changes is the document's CONTENTS, not its
       schema string: it still carries the citation, the per-instance placements,
       the anchor and tension-tie bodies with their own placements and kinds
       (unchanged, still two separate ports and two separate kinds), and the wires.

    3. THE SCALAR mechanism.reeveFactor IS GONE from the study document. Every wire
       now carries its own RESOLVED reeveFactor plus a reeveFactorSource ("wire" when
       a per-wire override won, "machine" when the machine's own default did), so you
       never inherit or infer a factor the way net_vertex already worked. The machine
       states its own default exactly once, at reeve.default in its header, with a
       how string explaining that it is authored per mechanism rather than derived.
       There is a new key on the study payload, reeve.perWire, an object keyed by
       wire index as a JSON string: it is ALWAYS present, even when empty, so its
       absence is never a question you have to answer.

    4. mechanism.spoolRadius IS GONE from the study document as well. It is not
       replaced by anything on the study side: a radius derived from the tension
       tie's bounding box, with no reel reaching this build any more, would be a
       plausible number measured from the wrong object, and it is better withheld
       than invented. The real radii are the machine's: each reel entry's own
       windingRadius, and the median spoolRadius across the reels that carry wire,
       both in the machine document per reel entry, not the study.

    5. THE ARTEFACT CHANGE YOU MOST NEED TO KNOW ABOUT: on every TWO-SIDED vault, the
       TURNED side's seven net_vertex values change end for end against what an
       export written before this fix would have held. The study document used to
       pair a side's wires to its anchors by the row's DISCOVERY order; the
       placement itself pairs them SPATIALLY, along the same axis on both ends. On
       an untouched side those two orderings agree by construction, but the far side
       of a two-sided vault is a machine the derivation turns round to face its own
       springing, and there the two orderings ran end for end: real cables were
       being drawn to anchors up to 0.9 m from where the machine was actually
       placed against them, with correct-input warnings as the only visible symptom.
       The document now binds each wire to the anchor it was actually placed
       against. The UNTURNED side of a two-sided vault and every SINGLE-machine
       study are byte-identical to before; only the turned side's net_vertex values
       move, and the four match-distance warnings that used to accompany them are
       gone. Since your app draws each cable to net_vertex, this changes what gets
       drawn on those wires, from wrong to right, on any study exported before this
       change and re-exported after it.

    6. EACH REEL MAY NOW CARRY windingRadiusUnfitToAnimate (bool), windingRadiusScatter
       (a number, or null when nothing was measured near it) and windingRadiusNearby
       (the population the scatter figure was taken over, distinct from
       windingRadiusSamples, which is the population the radius itself was
       MEDIANED over). A reel marked unfit still publishes its measured radius
       exactly as measured, with no substituted fallback and no separate confidence
       or quality field anywhere in the document: an unfit mark is the only signal,
       stated plainly rather than hidden or dressed up. A reel is marked unfit when
       too many of the frames near it disagree with the radius it publishes, which
       is what a radius measured off frames that are not actually sitting on a
       cylinder looks like. His own seven spools are CURRENTLY MARKED UNFIT on his
       real machine (scatter 4.0 to 4.24 against a limit of 0.40), most likely from
       an authoring offset in his Grasshopper script rather than anything in the
       document; that is his own open item, not one for you.

    7. TWO QUESTIONS FOR YOU. First, whether you want a PUT upload route for
       machines at all: nothing in this repo has one today, and a machine currently
       arrives at your side only through the library folder, so building a port for
       a route that does not exist would be speculative on our part. Second,
       whether your reader tolerates the new keys above gracefully (an unrecognised
       key ignored rather than refused) or needs to be told about each one by name
       before this ships.

----------------------------------------------------------------------
