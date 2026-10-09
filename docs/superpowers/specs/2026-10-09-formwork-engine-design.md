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
  from its anchor, the node moves out along the wire's line (the anchor holds
  it sideways where the wire enters), and the wire's rope inside stretches and
  resists, with the stiffness of the whole reeved route,

  ```
  k = MA^2 * EA / L_route        MA: the reeve factor (4), L_route: the rope
                                 inside the anchor and machine (about 12.6 m)
  T = k * max(0, u + r)          u: how far the node is let out of its
                                 anchor; r: what the drum has reeled past
                                 the wire being just taut with its node on
                                 the anchor
  ```

  and with the length the drum has paid out as its unstretched length.
- **The foundation**, which pushes and never pulls: the rim node cannot go
  into the anchor. An anchor is a foundation, immovable.
- **The anchor's force**, the wire's pull and the foundation's push together,
  reported frame by frame as the load that foundation must resist.

The machine reels to hold the rim on its anchor: as the tension in a wire
changes, its drum takes up or pays out the rope's stretch so the node stays
where it was designed to be. That take-up is each wire's required reel
(section 3.3). That is the raise. From the hold frame on, the drums hold
where they are (section 4.2), so the skin's weight stretches the wires and
lets the rim out of its anchors by the added tension over k.

The permanent tension ties connect the five anchors; because the anchors do
not move, the ties change nothing in the net's motion. The anchor forces are
what the ties and the foundations must resist together, and how that is
shared between them is an open item (section 11).

Should a mechanism ever leave a free span of wire between an anchor and its
rim node, this part refuses the run, naming the wire and the gap: a span
modelled as if it were not there would hide its sag. Splitting it into
segments of at most 250 mm, each a rope element with its own weight, so it
droops as a real wire would, waits for a study that has one. The real study
has none: every rim node is within 0.01 mm of where its wire enters the
anchor.

### 3.3 Motors, drums, pulleys and pairing

- A motor drives one drum. Every spool on a drum reels the same length change
  (equal spool diameters are assumed).
- Which spools share a motor is chosen per machine. With N wires per motor,
  the machine has the fewest motors that carry its seven spools at N each,
  ceil(7 / N), and every way of splitting the spools onto them is tried (at
  most 877 splits of seven spools in all); the split kept is the one whose
  shared reels stray least from what each wire needs over the whole
  sequence, a wire's need being the take-up that holds its rim node on its
  anchor (one motor a wire would cost nothing, so the motor count is the
  choice and only the pairing is searched):

  ```
  cost(split) = sum over frames, over motors, over the motor's wires of
                (required change of the wire - common change of the motor)^2
  common change of a motor = the mean of its wires' required changes
  ```

- A motor's shared reel leaves each of its wires a little long or a little
  short of its own need. A wire left long lets its rim node out of the anchor
  until the wire and the net agree; a wire left short pulls its node onto the
  anchor, and the foundation pushes back the difference. That is the cost of
  fewer motors, measured in millimetres at the rim. The needs come from a
  first pass of the whole sequence with every wire on its own motor; the
  spools are paired on them, and a second pass reels each motor's mean of
  its wires' needs, step by step.
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
A node its head has let go of left the notch sideways, so that head takes it
back only once it has been above the head again and comes down onto it. On
the real net a head that took back a node from beside it, below its top, let
it go and took it back round after round (section 12).
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
phase is the net being laid out by people (section 2), so the engine lays the
net out where the frame at machine time 30 has it, as near as the net allows,
and simulates the 36 frames from 30 to 100.

On the real study that frame is not a layout a real net can take. Its 950
inner nodes hover up to 421 mm above the ground, and against the cut lengths
its members run from 44 per cent short to 130 per cent stretched, because the
animation draws the net in with the heads, which start up to a metre inside
their final places (section 12). Held there, the net would carry over a
meganewton. So the people's layout is taken literally: every node but the
rim's and the heads' is put on the ground under where that frame has it, the
rim on its anchors and each head node in its head's notch, and the nodes
slide on the ground, without friction, until no member is stretched. Then the
ground's friction takes hold and the raise begins. How far each node moved
from the frame is the first capture's deviation. At every frame after that:

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

Each capture carries its place on the studio's own timeline: the machine
time of its frame during the raise, and its row and quarter during the
tiling. Play replays the captures in step with the studio's animation, one
row at a time as it plays them now; scrubbing jumps to any capture. Nothing
is recomputed to play.

A duration in seconds cannot be read from this mechanism for the raise: the
reels only take up stretch while the trees lift the net, and how fast the
trees extend is not in the export. Real seconds wait for that figure (section
11). A new run recomputes everything and replaces the
captures. The captures are kept per study and options, beside the cable net
demand documents, and an upload of the study clears them, as it does those.

### 4.5 Storage

One capture document per study and options, schema `bench.formwork-sim/1`: a
JSON index (frames, phases, clock, element lists, units, the assumptions) with
the positions and forces as base64 float32 arrays, which the browser decodes
directly and the studio's server never parses with numpy. On the real study
that is about 130 captures of about 60 kB each, roughly 8 MB.

## 5. The solver

Unknowns: the positions of every net node not in contact; for each rim node
off its anchor, how far it is let out along its wire, its one unknown, since
the anchor holds it sideways; and while the net is laid out (section 4.1),
the x and y of each node sliding on the ground. A rim node is held on its
anchor while its drum reels exactly what holds it there, and while its
foundation pushes; nodes in contact with a head, a hold or the ground are
held there exactly while the contact pushes (section 3.5). Held: the tree
nodes, which follow their prescribed motion. A frame that moves a head by
more than 25 mm is solved in sub-steps of at most 25 mm, so contacts are
gained and lost one small move at a time.

Each step finds the shape that minimises the net's stored energy less the
work of its loads, from the previous capture's state, by damped Newton steps:

```
Pi(x) = sum over taut ropes of EA / (2 L0) * (L - L0)^2
        + sum over rim nodes off their anchors of k / 2 * max(0, u + r)^2
        - loads . x
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

The engine assembles its own tangent stiffness, with a rope's material
stiffness only while it is taut (the stiffness module's is built for force
densities), and factorises it with scipy's sparse LU. When the damped
steps stall (the damping grows past its limit) or reach 300 iterations,
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

- In `src/tree_forest_compas`, numpy and scipy only, tested headless:
  `net_engine.py` (the ropes, the wires, the solver and the contacts),
  `trees.py` (the column trees and the steel tube), `pairing.py` (which
  spools share a motor) and `formwork_sequence.py` (the cut, the sequence
  and the captures).
- `bench/studio/solve_formwork.py`: the subprocess entry, request in and
  capture document out, as `solve_cablenet.py` is for the Cable net run.
- A run route of its own (kind "formwork"), cut by the same
  staging.cut_and_plan as the other two runs, so all three run on the same
  cut, and reading the study's documents before the cut, as the cable net
  run does.
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
    is the two together. Two wires sharing one reel: the long wire's node is
    let out until its wire and the net agree, the short wire's node stays on
    its anchor with the foundation pushing back. Through the tiling the
    reels hold, and the skin lets the rim out by the added tension over k.
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
3. How fast the trees extend during the raise, so the replay can also say how
   long the raise takes in seconds (section 4.4).
4. Bending at the forks is reported, not modelled.

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

While the plan was written, the engine it specifies was run on the real study
through the whole sequence, and what it found changed the design:

- The frame at machine time 30 is not a layout a net can take: its 950 inner
  nodes hover up to 421 mm above the ground, and against the cut lengths its
  members run from 44 per cent short to 130 per cent stretched. Held where it
  is drawn, the net carried 1.1 MN and put the trees at 21 times their
  resistance. Hence the laying out of section 4.1: laid out, no member is
  taut at machine time 30, and the worst node is 445 mm from where the frame
  drew it.
- In the finish phase, machine time 60 to 90, 45 of the 46 heads slide
  outward, level, by up to 994 mm, to their final places. At machine time 62,
  at full height but up to a metre inside them, they pull a rope to about
  67 kN and a wire to about 34 kN, and put the trees at 1.9 times the
  resistance of a 3.2 mm wall; all of it falls away as the heads slide out,
  to 30 N in a wire by the hold. A 4 mm rope breaks at about 10 kN. No
  standard wall holds every capture, because of machine time 62.
- Each wire on the real mechanism drops straight down 30 mm into its anchor,
  so it feels only the net's uplift at its rim node, and the anchor body takes
  the sideways pull. Every route is drawn in its machine instance's own frame,
  and only that frame puts it on its rim node.
- The net slides off the lower heads as the higher ones lift it into a tent:
  all 46 touch until machine time 46, 21 from 50 and 11 at the hold, the rest
  48 to 725 mm to one side and below. At the hold the worst node is 1.6 m from
  the designed form, and 1.75 m under the last course. A head that took back
  a node from beside it, below its top, let it go and took it back round after
  round, hence section 3.5's rule.
- The whole sequence ran in 114 s at one wire a motor and 243 s at two, once
  Newton was allowed 300 damped steps. At 60, relaxation took over a dozen
  times in the first ten frames, at about 12,000 steps each, and doubled the
  time. At two wires a motor the shared reels let the rim out by at most
  0.72 mm.
