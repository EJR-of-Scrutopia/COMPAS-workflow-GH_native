# The horizontal equilibrium station: the pattern learns to carry itself

DRAFT FOR PARAM'S REVIEW, written overnight 2026-09-04. NOTHING HERE IS BUILT until he has read
this and said yes, because the station MOVES HIS DRAWING, and how far a drawing may move is a
design decision, not an engineering one. Register section 1 is the ruling this implements; the
2026-09-03 holed-form diagnosis is the measured ground.

## 1. The problem, measured on his six-lobe form

TNA needs the plan pattern to be in horizontal equilibrium before heights mean anything: at every
free node the horizontal edge forces must close a polygon in pure compression. There are two
families of unknowns, the FORCE DENSITIES and the PLAN GEOMETRY. Our solver adjusts only the
first: the algebraic path projects onto the exact self-stress space of the plan AS DRAWN
(tna.py:1873-2108), and on his form the only exact self-stress needs 55 edges in tension, because
a fan corner's edges all leave into a wedge narrower than a half-plane and no positive
combination of them can vanish. The reciprocal stalls at 85 degrees against a 5 degree gate, no
slider can fix it (heights enter after the failed stage), and reducing mesh density cannot fix it
(a fan is a fan at any density). RhinoVAULT passes the same forms because its preparation MOVES
PLAN VERTICES. That second unknown is this station.

## 2. What it is

A new opt-in component between TNA Relax and TNA Solve: RLX in, RLX out, so the existing
Relaxed-to-Solve wire is unchanged and a canvas without the station behaves exactly as today.

    TNA Equilibrate (EQ)
      RLX   the prepared problem from Relax
      A     Alpha, 0.0 to 1.0: how far toward equilibrium the drawing may move.
            0 returns the drawing untouched; 1 is the fully equilibrated plan.
      I     iteration cap (default from the worker's own convention)
      RLX   the problem with its plan moved, ready for Solve

Worker side: one new command, tna.equilibrate, beside tna.prepare and tna.solve in
src/ananke_equilibrium/worker.py, so the arithmetic lives where the solves live and the harness
measures it through the same protocol.

## 3. What it does, and what it holds

Moves FREE vertices IN PLAN toward horizontal equilibrium of a compression-only force state,
holding fixed: supports, floating anchors (hole rims ride through untouched), and z (nothing
vertical happens here). The blend is positional: moved = drawn + Alpha * (equilibrated - drawn),
the same per-vertex reading as the thickness slider's, so Alpha 0.3 means "give me a plan seventy
per cent mine and thirty per cent physics".

The equilibrated target comes from the machinery the codebase already trusts: the uniform-q FDM
relaxation the apron already runs (fd_numpy, zero loads, plan only), extended from the apron to
every free vertex, followed by the existing algebraic projection to measure what remains. No new
solver is invented.

## 4. What it reports, because moving a drawing must be visible

- INTENT DEVIATION, the number the pipeline already computes (algebraic_intent_deviation): the
  max and mean plan movement, in model units and as a fraction of mean edge length, on the chin.
- The negative-q count and the reciprocity angle BEFORE and AFTER, so the author sees what the
  movement bought: "55 tension edges and 85.0 degrees became 0 and 2.1 at Alpha 0.4" is the whole
  story in one line.
- A Remark when Alpha was not enough: "the gate still fails at this Alpha; raise it, or redraw
  the corners it names", with the worst three node locations.

## 5. Riders in the same wave, all small, all solver-side

1. REGISTER 2 AS SETTLED WITH PARAM 2026-09-04: measured sag (rise over support chord) reported
   per opening on the Relax chin with indices; AUTO sag as the default, per-opening
   max(drawn sag, floor), never flattening a deeper arc (today's single global target does, and
   flattens; tna.py:1395); the input renamed "Minimum sag %"; an optional per-opening sag LIST as
   the finer tuner, indices matching the chin.
2. S2 OF THE QUEUE: the algebraic path's force gate reads q times FORM length where the iterative
   path reads the DUAL length, so the 1 per cent gate stops filtering collapsed duals exactly
   where it is needed (tna.py:2067, 2081 against 1838). Gate on the dual length.
3. S3: algebraic_residual_max_relative and its siblings surfaced on the Solve chin, so
   converged-solve versus failed-dual is readable off the canvas (they decided the whole six-lobe
   diagnosis and are currently invisible).
4. S1: zero-support interior loops auto-held with a warning naming Floating Anchors, so the
   FA rule stops being folklore.

## 6. Questions for Param, each with a default so silence is not a blocker

1. DEFAULT ALPHA: 0.0 (strictly opt-in, the drawing never moves unless you say so) is the
   proposed default. The alternative is a small nonzero default that quietly fixes most patterns
   and quietly moves most drawings. Recommendation: 0.0.
2. AUTO MODE: should the SOLVE suggest the station when its gate fails ("the held pattern cannot
   close; wire TNA Equilibrate or accept the residual"), which is advice, or should anything ever
   run automatically? Recommendation: advice only, nothing automatic.
3. NAME: "TNA Equilibrate" (EQ) proposed; "Horizontal" collides with the solve's own horizontal
   phase in every doc sentence.
4. Should the station's moved pattern be exportable as a drawing he can inspect against his
   original (a one-toggle overlay through the existing Display machinery), now or later?
   Recommendation: later, unless he wants it for the thesis figures.
