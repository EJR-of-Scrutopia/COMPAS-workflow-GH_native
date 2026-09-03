# Overnight recovery brief: the studio session

If you are reading this you are the woken turn. Assume you remember NOTHING of what
follows; this file is your memory. Param is asleep and expects finished work and morning
notes. Act without waiting for him.

Written 2026-09-03 by the studio session, in response to R-004 in
REQUESTS-for-plugin-session.md, against the possibility that the API session dies
mid-task overnight.

## 1. Who you are and the one hard prohibition

You are the STUDIO session. Your worktree, and the only one you may write to:

    C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench

on branch feature/studio-finish.

NEVER write to the main worktree at

    C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow

A second session is building there all night on feature/mould-round-three. You share one
.git store through the worktree mechanism. You may READ its files. You may NEVER check
out, rebase, or touch that branch, and you may NEVER run git worktree commands. Do not
edit anything under plugin\ in any worktree. If you need an exporter-side change, write
the request into REQUESTS-for-plugin-session.md instead and build everything that does
not depend on it.

## 2. Verify what survived, before doing anything else

Run these, in this worktree, and believe the output over anything this file claims:

    git log --oneline -12
    git status --short
    "C:/Python313/python.exe" -m pytest tests/studio -q

Commits that should exist on feature/studio-finish, oldest first:

    0cb31b0  docs(bench): the request channel between the two live sessions
    9fefce2  docs(bench): R-004 locks the frames upload segment and the reader's read-time gate
    e99bd49  feat(studio): the bench.frames/1 reader, validation and pairing gates
    684a275  feat(studio): formwork frame interpolation, the playback's whole algorithm
    527cf00  feat(studio): the formwork act, the timeline's new first act
    99fd0ba  fix(importer): the stability wave, and the two kinds the exporter sends

The studio suite was 393 passed when 99fd0ba landed (baseline before this session's work
was 363). If the suite is red, fix that FIRST and before starting anything new.

NOTE: `pytest tests` (the whole tree) fails collection with 12 errors that predate this
session, in the ananke_equilibrium tier, unrelated to the studio. Use `pytest tests/studio`.
Say so in the morning notes rather than "the suite fails".

## 3. What the work is

Param's ask, his words, from HANDOFF-studio-animation-2026-09-03.md section 1:

> "I would like it to now just take our result as it does from animation, key the frames
> in and that exports as the formwork building. the dropping down of the voussoirs as it
> currently does in animation and the different materials etc it has is great. but it
> should now use the skin we give it from grasshopper also as an option, just a toggle
> will do."

Three deliverables, and his three decisions (asked and answered 2026-09-03):

- A. FORMWORK BUILD PLAYBACK. Done except for end-to-end proof. Built against
  FRAMES-WRITER-SPEC-2026-09-03.md, the contract with the plugin session, NOT against the
  handoff's original route-1 plan (live per-solve accumulation). That plan is abandoned;
  he approved building to the spec.
- B. THE SKIN TOGGLE. NOT DONE. This is your main remaining build. See section 4.
- C. DO NOT DEGRADE the existing voussoir drop and materials.

His decisions, which are settled and not to be revisited:

1. Build on the bench studio line AS IS. Do not port the engine line's divergent work
   from the COMPAS-UI-integration-tool tree, and do not attempt to unify the two lines.
2. ONE TIMELINE, TWO ACTS: the formwork act plays first, then the voussoirs drop onto it.
   Not a separate player.
3. The Skin toggle DEFAULTS TO SKIN when a study has an authored tessellation, so no
   existing study changes appearance when opened. The toggle exists to force the
   studio-generated cut instead.

## 4. Exactly where you are, and what to do next

DONE and committed:

- bench\studio\frames.py: the bench.frames/1 reader. validate_frames_document enforces
  the writer spec's guarantees 1, 2, 3, 6 and raises ValueError naming the fault;
  pairing_error is guarantees 4 and 5 and RETURNS A REASON rather than raising, because
  an unpaired frames file is a leftover to disclose and skip, never an error that blocks
  a study (this is R-004 point 2, agreed with the plugin session).
- bench\studio\static\fields.js: interpolateFormworkFrame, linear per coordinate between
  bracketing samples, clamped both ends. Pure, no DOM, so tests/studio/test_fields.py
  drives it through node.
- bench\studio\static\studio.js: the formwork act. openingSeconds() is now the single
  source of the build clock (three sites used to re-derive it); the act replaces the
  inflation reveal only for studies that have frames; wires hide during the act and take
  over at its end; members strike on the wires' clock; everything stays pure in t so the
  1080p recorder stays deterministic.
- bench\studio\app.py, bundle.py, geometry.py, tessellation.py: the importer stability
  wave. Atomic writes everywhere, torn-file healing, the generation-guarded bundle
  persist, the ':' and containment guards, a 64 MB body bound, NaN/Infinity refusal,
  slug-collision refusal, the post-body interlock recheck, and the tessellation and
  frames kinds now accepted. GET /api/studies/{export}/formwork serves the act's data.

REMAINING, in priority order:

1. DELIVERABLE B, the Skin toggle. The survey found the real shape of this, and it is
   NOT what the handoff assumed. There is no pattern value "authored" in the bundle: the
   discriminator is tessellation.source == "imported" plus target_size == None. Today
   build_tessellation_for makes authored ALWAYS win when a sidecar exists
   (bench\studio\bundle.py, in build_tessellation_for: read_tessellation then
   from_document, and the requested pattern and size are ignored entirely).
   The work: make the source a per-request CHOICE, defaulting to authored-when-present.
   The traps the survey named, all of which will bite if ignored:
   - the choice MUST enter both cache keys or you serve the wrong source's cut: the
     _cut_for memo key (export_name, pattern, size) AND the bundle-/staging-*.json
     filenames (bundle_path / staging_path).
   - app.py's _validate requires the requested pattern to be a real generator even when
     authored wins; a source=authored request must not be coupled to a generator name.
   - memoised cut tuples are SHARED BY REFERENCE; never mutate one in place.
   - _staging_matches is a subset test on cell keys, and generated keys look like
     "c{course}p{k}", so an authored cut reusing that scheme could pass a stale stage
     plan. Consider keying staging by source too.
   - the frontend infers the source today at studio.js around lines 1008 and 1755-1772
     from target_size === null; a real toggle should make it explicit in the bundle.
2. END TO END. Start the server and drive the real routes; the handoff makes this the
   floor, not optional:
       cd "<this worktree>"
       "C:/Python313/python.exe" bench\studio\serve.py     (http://127.0.0.1:8600)
   Uploads on disk live in TWO folders, demo\ and bench\demo\; bundle.UPLOAD_DIR decides
   which the server reads, so check it rather than assuming. A real mould-bearing
   contract to test with:
       demo\upload from grasshopper\Column diagnosis-contract.json
   It has 441 vertices, 400 quad faces, and a mould block with ground, columns (33 nodes,
   27 members) and ONE frame at time 100. There is no frames document on disk yet; the
   plugin session writes that kind. You can hand-build one from the contract to prove the
   act end to end: take equilibrium.vertices as the time-100 frame, flatten z for time 0,
   and interpolate the boundary instants 30, 60, 90.
3. MORNING-NOTES.md at this worktree's root: what works, what to click, what is
   unfinished. Param reads this first.
4. Answer anything OPEN in REQUESTS-for-plugin-session.md, and reply to entries the
   plugin session has left for you.

## 5. Working rules that bind you

- No em dashes anywhere, in any file or commit message. ASCII "--" instead.
- No Co-Authored-By and no AI attribution of any kind, anywhere.
- Commit locally after every working fix. git add BY EXPLICIT PATH only, never -A and
  never ".". NEVER push.
- Before every test run and every commit, scan for OneDrive corruption:
      find . \( -name "*Name clash*" -o -name "*Edit conflict*" \) -not -path "./.git/*"
  A clash file can hold your NEWEST edit or a stale copy; resolve by CONTENT, and note
  that this machine has split ONE edit across BOTH copies before, leaving neither
  compiling. Never resolve the other session's clash: back it up, restore it
  byte-identically, and file the evidence in REQUESTS-for-plugin-session.md.
- A NEW TEST MUST BE PROVED ABLE TO FAIL: break the code it covers, watch it go red,
  restore, and say so in the commit message. Three suite-green-while-broken incidents
  happened here this week.
- Evidence over verdicts. Quote file:line and real command output. Never "should be fine".

## 6. Where the reasoning is written down

- HANDOFF-studio-animation-2026-09-03.md: the original brief. Its section 4 route 1 is
  SUPERSEDED, see section 3 above.
- FRAMES-WRITER-SPEC-2026-09-03.md: the frames contract. Section 6 is the reader's
  validation duty, section 7 is a toy fixture whose missing 60 and 90 boundaries the
  validator is required to flag, section 9 says easing belongs on the playback clock and
  never on positions.
- REQUESTS-for-plugin-session.md: the live channel between the two sessions. Append only,
  never edit the other side's text, replies go beneath their entry, statuses are OPEN,
  ANSWERED or DONE.
