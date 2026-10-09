# The formwork engine: the cable net as it really moves

Part 1 of 5 of the Formwork tab. Design agreed with the owner in conversation
on 9 October 2026; this document is that design written down for his review.
Nothing in it is built yet.

## 1. Where this sits

The owner asked for the Cable net section to become a Formwork tab that tells
him, for a chosen mechanism, what prestress the skin needs, whether the system
holds it within the tolerance, where the net must be held, and what every
element of the formwork carries, with an animation that is "the closest to
reality digital twin as we can get". That is five pieces of work, each with
its own spec, plan and build, in this order:

1. **The engine** (this spec): a real cable-net simulation of the raise and
   the tiling, computed once and captured frame by frame.
2. **The mechanism**: five choices (motor, planetary gear ratio, pulley yes or
   no, wire, wires per motor), with the electronics derived from them by the
   rules in the T1 brief's note 14.
3. **The answers**: the prestress required, whether the mechanism supplies
   it, the roof (the most skin held within the tolerance), the next mechanism
   up, and the nodes that need holding, written to a holds file.
4. **The Formwork tab**: the mechanism at the top, the answers below, an
   Elements browser with focus mode, strain colours, newtons on the nodes,
   and the player for this engine's captures.
5. **The plugin's Columns**: growing branches to the nodes the studio says
   need holding, so the owner adds them in Grasshopper.

What the engine replaces. The Cable net view today holds the net at its
designed shape, fits the forces that would keep it there (a tension-only
least-squares fit), and estimates how far the net would move from that shape
by a first-order (linear) sag. That is not a simulation. A first-order
estimate is valid for small movements only, which is why it could report
2027.7 mm of sag on the real study with nothing grabbed: a real net would have
found another shape long before. The engine below finds the shape the net
actually takes, at every frame, from the forces in it.

## 2. The owner's rulings this spec carries

All from 9 October 2026, in conversation:

- The animation is the closest-to-reality digital twin that can be built. No
  deflection exaggeration: everything at true scale, deviation shown only as
  colour and numbers.
- The physics is a real engineering solver, not a game engine. Ragdoll and
  VFX solvers (PhysX, Bullet, Houdini's Vellum, Nuke's particles) run a fixed
  number of correction passes per frame and stop, so a stiff steel rope comes
  out stretchier than it is and the forces are not trustworthy to the newton.
  The engine uses the same physics but iterates until the forces balance:
  Newton's method, falling back to dynamic relaxation where ropes go slack.
- The engine computes the full loading sequence once, in the background, and
  captures every frame. Play then replays the captures in real time; nothing
  is recomputed to play.
- Holds are column branches: props from below that push and never pull.
- The column trees are steel tube, S355. The formwork export draws them 60 mm
  across (radius 0.03 m), which is the 60.3 mm standard tube. The wall starts
  at 3.2 mm, which the owner judges strong; it is an input, and a run says
  whether a thinner or a thicker wall is needed (section 3.4).
- The anchors are foundations built on site: immovable. The wires run through
  them on their way from the machines to the net, and the permanent tension
  ties connect the anchors and hold them in place, so the foundations resist
  part of the strain and help the system keep its form. How the wires move
  through an anchor needs more thought; section 3.2 states what this part
  assumes.
- The skin goes on one row of tiles at a time, from the bottom, each row
  placed going around, as the studio's animation does now.
- The net is judged on whatever force really goes through each member.
- The reel phase of the formwork animation (machine time 0 to 28) is people
  laying the net out by hand. The physics starts when the trees begin to
  rise, at machine time 30, from the net where the animation has it then.
- Several wires may share one motor, and the studio chooses which spools of
  each machine share it, so that sharing costs the least deviation.
- Prestress is computed, not dialled (part 3 searches it). The engine takes it
  as an input.

## 3. What the engine simulates

Units throughout: millimetres, newtons, kilograms. The contract's metres are
scaled by 1000 on the way in, as the Cable net run does today.

### 3.1 The net

Every one of the net's members (2000 on the real study) is a rope element
that pulls and never pushes:

```
strain   e = (L - L0) / L0
force    T = EA * e     when L > L0
         T = 0          when L <= L0        (slack: a rope cannot push)
```

EA and the mass per metre are the net rope's. The net is cut once, to fixed
lengths, before it is raised. Each member is cut to the tension it really
carries when the net is held exactly at the designed shape with no skin on:
the tension-only equilibrium of the net at that shape under its own weight,
held by the anchors' wires and the column heads (the fit the Cable net view
already makes), never less than the prestress P:

```
F_i  = max(fitted tension of member i, P)
L0_i = L_design_i / (1 + F_i / EA)
```

The form export's own member forces cannot be used for this: all 2000 are
the finished vault's compression (-0.12 to -2.12 kN), which a net that only
pulls cannot carry. P is an input here; part 3 searches it. Once the net is
cut, nothing about it is assumed again: every frame is judged on whatever
force the engine finds in each member.

### 3.2 The machine wires and the anchors

All 105 wires run from a rim node, into its side's anchor, through the
anchor's body and the machine's reeving, to a drum on one of the 15
seven-spool machine instances: each of the five anchors lists the 21 rim
nodes its wires hold. Each wire's route is in the mechanism export, a
polyline of about a thousand points per wire, alternating between the body
and the reels, about 12.6 m of rope inside, reeved 4 to 1.

On the real study every rim node sits on the point where its wire enters the
anchor at all 51 frames (0.000 m away at every frame). So the wires never
hang free; they hold the rim at the anchors from inside them, and what sags,
tightens and lifts is the net. The engine models each rim node's hold as:

- **The wire**, a link that only pulls: if the net draws the rim node away
  from its anchor, the wire's rope inside stretches and resists, with the
  stiffness of the whole reeved route,

  ```
  k = MA^2 * EA / L_route        MA: the reeve factor (4), L_route: the rope
                                 inside the anchor and machine (about 12.6 m)
  ```

  and with the length the drum has paid out as its unstretched length.
- **The foundation**, which pushes and never pulls: the rim node cannot go
  into the anchor. An anchor is a foundation, immovable.
- **The anchor's force**, the wire's pull and the foundation's push together,
  reported frame by frame as the load that foundation must resist.

The machine reels to hold the rim on its anchor: as the tension in a wire
changes, its drum takes up or pays out the rope's stretch so the node stays
where it was designed to be. That take-up is each wire's required reel
(section 3.3). The permanent tension ties connect the five anchors; because
the anchors do not move, the ties change nothing in the net's motion. The
anchor forces are what the ties and the foundations must resist together, and
how that is shared between them is an open item (section 11).

Should a mechanism ever leave a free span of wire between an anchor and its
rim node, that span is split into segments of at most 250 mm, each a rope
element with its own weight, so it droops as a real wire would. The real
study has none.

### 3.3 Motors, drums, pulleys and pairing

- A motor drives one drum. Every spool on a drum reels the same length change
  (equal spool diameters are assumed).
- Which spools share a motor is chosen per machine. With N wires per motor,
  every way of splitting the machine's seven spools into groups of at most N
  is tried (877 ways at most), and the split kept is the one whose shared
  reels stray least from what each wire needs over the whole sequence, a
  wire's need being the take-up that holds its rim node on its anchor:

  ```
  cost(split) = sum over frames, over motors, over the motor's wires of
                (required change of the wire - common change of the motor)^2
  common change of a motor = the mean of its wires' required changes
  ```

- A motor's shared reel leaves each of its wires a little long or a little
  short of its own need, and the engine lets the rim nodes move by exactly
  that, through each wire's stiffness: the cost of fewer motors, measured in
  millimetres at the rim.
- With a pulley, the drum reels MA times the line's length change and feels
  the line tension divided by MA, MA being the pulley's mechanical advantage.
  Part 2 owns the choice; until it lands the engine takes MA, N, the drum
  radius and the gear ratio as inputs, with today's catalogue values.

### 3.4 The column trees

The 16 trees of the formwork export (82 nodes, 66 members, 16 feet, 20
forks, 46 heads under net nodes) are part of the moving mould: every one of
the export's 51 frames gives all 82 tree node positions. The engine follows
that prescribed motion and treats the trees as rigid in position. Their
elastic shortening is negligible against the tolerance: a 3 m member of 60.3
by 3.2 mm tube carrying 1.5 kN shortens about 0.04 mm.

```
A  = pi/4 * (D^2 - (D - 2t)^2)    D = 60.3 mm, t = 3.2 mm (the starting wall)
EA = 210000 N/mm2 * A
```

What a tree carries is worked out from the forces its heads receive, down
each branch to the foot, by statics at every fork: a member carries the part
of the load along its own axis. Whatever a fork cannot pass on along its
members is a load the joint would have to resist in bending; it is reported
at that fork, never hidden. Each member's axial force is set against its
flexural buckling resistance to EN 1993-1-1 (buckling curve a, the member's
own length as its effective length), which gives the utilisation the strain
colour will show in part 4. The run reports the utilisation at the wall in
use and the thinnest standard wall of 60.3 mm tube that keeps every member
within its resistance, so a run says whether a thinner or a thicker wall is
needed.

### 3.5 Heads, holds and the ground

Where a tree's head meets its net node, the net rests on the head: the head
pushes and never pulls. While it pushes, it holds its node in its notch, in
every direction, as the columns' "every notch held" means; the moment
holding the node would mean pulling it, the head lets it go and the two part.
An extra hold at a highlighted node (part 3) behaves the same way; in this
part it stands on the ground under its node, vertically, and is marked as
provisional until the plugin grows the real branch (part 5).

The ground behaves the same way. The net is laid out on it, so no node may go
below the ground plane, z = 0. A node resting on the ground is held where it
rests while the ground pushes it (the friction of a net lying on the ground),
and let go when it lifts.

These are exact constraints, not stiff springs. A node in contact sits exactly
on its head, its hold or the ground, and the contact's force is whatever
holding it there takes; the solver keeps the set of nodes in contact up to
date, releasing any whose contact would pull and taking on any that would
pass through. A throwaway prototype on the real net (section 12) showed why:
modelled as stiff springs, the heads answered a frame's 0.33 m lift with
millions of newtons and the solve diverged.

### 3.6 Loads

The net rope's weight, the wire ropes' weight, and the skin, course by course,
from the cut plan, as the Cable net run builds them today. The trees' own
weight goes into their member forces, not into the net.

### 3.7 Not modelled in this part

Listed so that none of it is mistaken for having been considered: friction
where the wires pass through the anchors; wind; temperature; creep; a rope's
bending stiffness; winding layers on a drum; friction in pulleys; inertia
(swing and bounce).

## 4. The sequence: computed once, captured, replayed

### 4.1 The raise

The formwork export's 51 frames run from machine time 0 to 100 in four
phases: reel (15 frames), raise (15), finish (15) and hold (6). The reel
phase is the net being laid out by people (section 2), so the engine places
the net where the frame at machine time 30 has it, and simulates the 36
frames from 30 to 100. At every one of them:

1. the trees stand at that frame's node positions;
2. each wire's required reel is the take-up that keeps its rim node on its
   anchor at that frame's tension (section 3.2);
3. each motor reels its common change, from its wires' needs (section 3.3);
4. the engine solves for the shape the net takes, and the state is captured.

The difference between where the net settles and where the frame designed it
to be is the deviation, frame by frame.

### 4.2 The tiling

From the hold frame on, the reels hold where they are: closed-loop steppers
hold position. The skin goes on one row of tiles at a time, from the bottom,
each row placed going around, in the order the studio's animation places
them. Each row goes on in four steps, a quarter of the way round at a time,
so the load lands unevenly as it really does; every step is solved and
captured. Whether the machine should re-reel between rows to win back the
shape is part 3's question.

### 4.3 The captures

Every solved state is one capture. It holds:

- the position of every net node, wire segment node and tree node;
- every net member's and wire segment's tension, or that it is slack;
- every head's and hold's push, and every anchor's force;
- every tree member's axial force, utilisation and any fork's bending load;
- every motor's common reel and its drum tension;
- every net node's deviation from the frame's designed position;
- how it was solved: Newton or relaxation, iterations, the largest leftover
  force.

### 4.4 The build clock and the replay

Each capture carries a time on the real build's clock. Between raise frames
that is the largest reel change of any motor divided by the rope speed (the
Rope speed dial). The rows take the studio animation's own timing, one row
at a time as it plays them now, so the replay and the studio's animation stay
in step.

Play replays the captures at that clock, so the raise is seen at the speed
the machine would really run it; scrubbing jumps to any capture. Nothing is
recomputed to play. A new run recomputes everything and replaces the
captures. The captures are kept per study and options, beside the cable net
demand documents, and an upload of the study clears them, as it does those.

### 4.5 Storage

One capture document per study and options, schema `bench.formwork-sim/1`: a
JSON index (frames, phases, clock, element lists, units, the assumptions) with
the positions and forces as base64 float32 arrays, which the browser decodes
directly and the studio's server never parses with numpy. On the real study
that is about 130 captures of about 60 kB each, roughly 8 MB.

## 5. The solver

Unknowns: the positions of every net node not in contact. The rim nodes are
held to their anchors by their wires and the foundations; nodes in contact
with a head, a hold or the ground are held there exactly while the contact
pushes (section 3.5). Held: the tree nodes, which follow their prescribed
motion. A frame that moves a head by more than 25 mm is solved in sub-steps
of at most 25 mm, so contacts are gained and lost one small move at a time.

Each step finds the shape that minimises the net's stored energy less the
work of its loads, from the previous capture's state, by damped Newton steps:

```
Pi(x) = sum over taut ropes of EA / (2 L0) * (L - L0)^2  -  loads . x
R(x)  = - grad Pi(x)                    the force left over at every free node
(K + mu I) dx = R                       K: tangent stiffness, material plus
                                        geometric; slack ropes add nothing;
                                        mu damps the step where K is soft
                                        (Levenberg-Marquardt)
x     <- x + a dx                       a halved until Pi falls (Armijo)
done  when max |R_i| < 0.01 N
```

Nodes in contact are held, and their contact forces are the reactions. A
step judged by the energy always makes progress, whether ropes go slack or
taut; judged by the leftover force, as the first prototype did, it stalled
(section 12).

It reuses the sparse assembly and the sparse factorisation, with its
condition check, that the stiffness module already has. When the damped
steps stall (the damping grows past its limit) or reach 60 iterations,
dynamic relaxation with kinetic damping takes over from the last good state
and runs to the same test. The capture records which finished it.

Every capture is checked before it is kept: the loads and the reactions must
sum to zero within 0.1 N. A capture that fails the check fails the run with
the reason; it is never kept with a note.

## 6. What it hands the studio

The capture document of section 4.5, read by part 4's player. The Cable net
view's demand document stays as it is until part 3 moves the answers onto
this engine.

## 7. Where it lives

- `src/tree_forest_compas/net_engine.py`: the model, the solver and the
  sequence, numpy and scipy only, tested headless.
- `bench/studio/solve_formwork.py`: the subprocess entry, request in and
  capture document out, as `solve_cablenet.py` is for the Cable net run.
- A run route of its own (kind "formwork"), sharing the cut-and-plan and the
  options assembly with the other two runs, as they share them with each
  other.
- `bench/scripts/formwork_real.py`: runs the real study through the route and
  writes the findings, with images of the net at the end of the raise and at
  the last course, coloured by tension and by deviation, rendered so the
  result is seen and not only read.

## 8. How we know it is right

Each of these is a test the engine must pass before it is run on the
owner's vault:

1. One rope hanging between two supports under its own weight: the segmented
   rope's mid-span sag matches the catenary within 0.5 per cent.
2. A taut rope with a point load at mid-span: the deflection matches the
   exact two-segment geometry.
3. A flat pretensioned square net with a central load: the deflection matches
   the hand calculation from the prestress within 1 per cent at small loads.
4. Two ropes holding a node from either side, loaded sideways until one goes
   slack: the slack rope carries nothing and the node goes where the other
   rope alone puts it.
5. A node resting on a prop, then lifted: the prop's push falls to zero and
   the node leaves it.
6. A tree with one fork under head loads along its branches: every member's
   force matches statics, and a load off the branch axis is reported as
   bending at the fork.
7. Two wires on one drum: both reel the same change, and the pairing search
   on a toy machine picks the split with the least cost, checked against
   every split listed by hand.
8. Newton and dynamic relaxation on the same problem agree within 0.01 mm.
9. Every capture's loads and reactions sum to zero within 0.1 N.
10. On the real study, before the skin, the end of the raise sits close to the
    designed shape; how close is reported, not judged.
11. A rim node on its anchor: pulled away, its wire stretches by the pull
    over MA^2 EA / L; pushed in, the foundation stops it; the anchor's force
    is the two together. Two wires sharing one reel: their nodes move by
    exactly the mismatch the stiffness predicts.
12. The cut: with the net held exactly at the designed shape and no skin, each
    member carries the larger of its fitted tension and P, within 0.1 N.
13. The tiling order: a row's four steps add its tiles in the animation's
    order around the ring, and together they add exactly the row's weight.

## 9. Performance

About 36 raise frames, in sub-steps, and 80 tiling steps on the real study.
The prototype measured one Newton iteration on the real net at about 15 ms;
with exact contacts a step should take well under a second, so the whole
sequence a minute or two. The target is five minutes or less on the owner's
machine; if it is exceeded, fewer tiling steps per row before anything else.

## 10. Out of scope here

The five mechanism choices and the derived electronics (part 2); the
prestress search, the roof, the next mechanism up and the holds needed (part
3); the tab, focus mode, strain colours, newton labels and the player (part
4); the plugin's Columns (part 5). This part's own visible output is the
script's findings and images.

## 11. Open items

1. How the anchor forces are shared between the tension ties and the
   foundations, and how the wires move through an anchor (here a link with
   the stiffness of the reeved rope inside, and no friction in the reeving),
   need more thought, in the owner's words.
2. Whether the machine re-reels between rows to win back the shape is part
   3's.
3. Bending at the forks is reported, not modelled.

## 12. What a throwaway prototype on the real net showed

Before the plan, a prototype of the solver (written to be thrown away, not
product code) was run on the real study, held at its 105 rim nodes and its
46 heads, at the hold frame and then through the raise:

- The tension the net needs to sit exactly on the designed shape under its
  own weight is at most 0.3 N in any member. A dome-shaped net in tension
  pulls every node down, so tension can only hold the dome where nearly every
  node is propped. Section 3.1's cut therefore puts every member at the
  prestress P.
- At 300 N and with only the 46 heads, the net drapes 1.0 to 1.5 m between
  them under the full skin, against the 2.0 m the first-order estimate gave.
  The heads push up 92.0 kN while the rim pulls down 24.5 kN against 67.5 kN
  of load: the forces close.
- One Newton iteration on the real net takes about 15 ms. Jumped straight from
  the designed shape to the draped one, Newton did not converge in 60
  iterations; followed frame by frame it does, once contacts are exact.
- Modelled as stiff springs, the heads diverged the solve as the trees rose,
  which is why section 3.5 makes contacts exact.
- Judged by the leftover force, the Newton steps stalled at their cap on 13
  of the 20 courses, with up to 5.7 kN of the load unaccounted. Judged by the
  energy, with damped steps (section 5), every course converged in 5 to 38
  iterations, 0.03 to 0.26 s each, and the vertical forces closed to 0.000 N.
- The whole sequence from machine time 30, with exact contacts and 25 mm
  sub-steps: about 120 s for the raise, nearly all of it where the net peels
  off the ground between machine time 40 and 50, and about 1 s for the 20
  courses taken whole. At 300 N on the 46 heads the net drapes about 0.9 m at
  the start of the tiling and 1.5 m under the full skin.

