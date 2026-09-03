# Morning notes, 2026-09-04

Overnight session on the studio, branch feature/studio-finish. Everything below was
driven against the real server with your own exports, not fixtures.

## Start here

    cd "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench"
    "C:/Python313/python.exe" bench\studio\serve.py

Then open http://127.0.0.1:8600 and pick a study. A server may still be running from
overnight; if the port is busy, that is it, and it already has all of this in it.

Two studies are uploaded and working: "Aramdillo style" and "Column diagnosis".

## What to click

1. Pick "Column diagnosis". It opens on your Grasshopper Skin: 1074 pieces in 28
   courses.
2. The timeline now opens with the FORMWORK BUILD. The net starts flat on the ground,
   reels down, lifts and finishes on the columns, and only then do the voussoirs drop
   onto it. One slider, two acts, in the order the thing is actually built.
3. Under the pattern control there is a new row, "Cut from", with two options: the
   Grasshopper Skin, or the studio pattern. It starts on the Skin wherever a Skin
   exists, so nothing you already had looks different this morning.
4. "Aramdillo style" is the same, 1501 pieces in 11 courses.

## The one thing to know about the toggle

Both of your studies can only be cut from their Skin. The studio's own polar generator
refuses them, and it is right to: Column diagnosis has a plan that is not star shaped
(the rim turns back on itself at vertex 21, 5.44 degrees of backward turn), and the
Armadillo has an oculus, so its rim is more than one loop. If you flip the toggle to
"the studio pattern" on either, you get the engine's own message in the banner saying
so, and the control goes back to the Skin rather than sitting on a cut that never
loaded. That is the toggle working, not failing. Flip it on a simple single-loop vault
and you will see the studio's own cut.

## The formwork frames are MINE, not the exporter's yet

The plugin session is writing the real frames exporter. Until it lands, the animation
you will see is built from each contract's own solved state: flat on the ground at time
0, the solved net at time 100, interpolated between. The shape of the motion is
therefore a placeholder; everything that CARRIES it (upload route, validation, pairing,
the act itself, the interpolation) is real and will take the exporter's frames the
moment they arrive, with no further work. The two sessions agreed the format in
FRAMES-WRITER-SPEC-2026-09-03.md and my reader implements its section 6 exactly.

## What I fixed, and why some of it matters more than it sounds

I ran a five-dimension audit of the importer under live-upload conditions. It found 35
defects, 25 after dedup, six of them critical, and an adversarial pass confirmed 47 of
48 verdicts, several by running probes that reproduced the bug. The live context is what
makes them real: your exporter PUTs a whole set of files on EVERY solve while you scrub
a slider, so races that would be exotic elsewhere are routine here.

The three worth understanding:

1. YOUR SKIN COULD NEVER ARRIVE LIVE. The upload route accepted only "contract" and
   "compas", and 400'd the tessellation your exporter sends on every TNA solve. The
   studio silently used its own generated cut instead. That is why deliverable B needed
   the route work before the toggle meant anything.
2. A RE-UPLOAD COULD LEAVE THE OLD GEOMETRY ON SCREEN FOREVER. If a bundle was being
   built while you re-uploaded, the build finished afterwards and wrote its result over
   the cache the re-upload had just cleared. Every later view served the old vault,
   silently, because the stale file passes every shape check. The audit reproduced this
   with a probe. It now cannot persist a bundle whose export changed underneath it.
3. A HALF-WRITTEN FILE WEDGED A STUDY. A cache torn by a killed process or a OneDrive
   sync raised a parse error that reached you as a 400 blaming your authored
   tessellation, naming no file, fixable only by re-uploading. Derived files are now
   read as absent when unparseable and rebuilt over, and every store is atomic.

Plus: NaN and Infinity refused at the door (python accepts both, then the browser
refuses what python wrote, which is a blank 500 nobody can explain); a 64 MB body bound;
the ':' guard the exports route alone was missing; two names that share one slug refused
rather than silently sharing a cache; the run interlock re-checked after the body read.

Two more, found only by using your real files:

- A TRIANGULATED EXPORT COULD NOT BE OPENED AT ALL. The Armadillo is 1481 triangles and
  the render subdivision refuses non-quads, so every view of it 400'd. It now falls back
  to the unsubdivided mesh and says so in the bundle.
- YOUR COLUMN DIAGNOSIS SKIN WAS REFUSED WHOLE. 28 of its 1074 cells carry corner pairs
  about 0.5 micrometres apart, which made "does this ring cross itself" unanswerable.
  Those doubled corners are now welded before the question is asked, which is what the
  pipeline does to them a few lines later anyway. A genuine self-crossing is still
  refused by name.

## Not done

- DELIVERABLE A's real frames, waiting on the plugin session's writer. My side is ready.
- The exporter writes its files in place rather than write-then-move, which contradicts
  its own spec. Filed as R-005 in REQUESTS-for-plugin-session.md. My side is hardened
  against it, so it degrades to a rebuild rather than a broken study, but it is theirs
  to close.
- The 28 doubled corners in the Column diagnosis Skin are an exporter artefact. Filed as
  R-006. The studio tolerates them now; better not to emit them.
- Nine minor audit findings are recorded and unfixed: unbounded RUNS growth, key-presence
  validation on the columns and HDRI uploads, trailing-dot name aliasing, and similar.
  None can corrupt geometry; all are listed in the audit and can be picked up any time.

## Housekeeping

Suite: `"C:/Python313/python.exe" -m pytest tests/studio -q` gives 401 passed. Note that
`pytest tests` (the whole tree) fails collection with 12 errors in the ananke_equilibrium
tier that predate this session and have nothing to do with the studio.

Every new test was proved able to fail by breaking the code it covers and watching it go
red. Nothing is pushed. The main worktree was never touched; the plugin session's branch
is untouched and I read its files read-only only.

Tonight's commits, oldest first: 0cb31b0 the request channel, 9fefce2 R-004, e99bd49 the
frames reader, 684a275 the interpolation, 527cf00 the formwork act, 99fd0ba the importer
stability wave, 3732e8b the recovery brief and R-005, 2a835d1 the cut source and toggle,
5eaebb6 both real studies opening.
