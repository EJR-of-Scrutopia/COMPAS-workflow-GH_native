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
  across (radius 0.03 m), which is the 60.3 mm standard tube; the wall is not
  in the export, so 3.2 mm is assumed and marked as assumed everywhere it is
  used, until the plugin exports the section (part 5).
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

EA and the mass per metre are the net rope's. The unstretched lengths L0 are
cut from the designed shape at a prestress P, the rule the Cable net run uses
today, so that the net would carry P in every member if it sat exactly on the
designed shape:

```
L0 = L_design / (1 + P / EA)
```

How the net is cut, and which P, are inputs. Part 3 searches P; whether the
cut should instead follow the designed form's own member forces is an open
item for part 3 (section 11).

### 3.2 The machine wires

All 105 wires run from their spool (the frame point of their machine instance
in the mechanism export, 15 instances of seven spools) to their rim node.
Each wire is split into segments of at most 250 mm, and each segment is a
rope element like the net's, with the wire rope's EA. The rope's own weight
is lumped at the segment nodes, so a slack wire droops as the real one would.
A wire's total unstretched length is what its drum has paid out.

### 3.3 Motors, drums, pulleys and pairing

- A motor drives one drum. Every spool on a drum reels the same length change
  (equal spool diameters are assumed).
- Which spools share a motor is chosen per machine. With N wires per motor,
  every way of splitting the machine's seven spools into groups of at most N
  is tried (877 ways at most), and the split kept is the one whose shared
  reels stray least from what each wire needs over the whole raise:

  ```
  cost(split) = sum over frames, over motors, over the motor's wires of
                (required change of the wire - common change of the motor)^2
  common change of a motor = the mean of its wires' required changes
  ```

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
A  = pi/4 * (D^2 - (D - 2t)^2)    D = 60.3 mm, t = 3.2 mm (assumed)
EA = 210000 N/mm2 * A
```

What a tree carries is worked out from the forces its heads receive, down
each branch to the foot, by statics at every fork: a member carries the part
of the load along its own axis. Whatever a fork cannot pass on along its
members is a load the joint would have to resist in bending; it is reported
at that fork, never hidden. Each member's axial force is set against its
flexural buckling resistance to EN 1993-1-1 (buckling curve a, the member's
own length as its effective length), which gives the utilisation the strain
colour will show in part 4.

### 3.5 Heads and holds

Where a tree's head meets its net node, the net rests on the head: the head
pushes up and never pulls, and if the net lifts away the two part.

```
gap  g = (net node - head node) . n        n: the head member's direction
push F = k_c * max(0, -g)
```

k_c is stiff enough that a node sinks less than 0.01 mm into its head at the
head's working load. An extra hold at a highlighted node (part 3) behaves the
same way; in this part it stands on the ground under its node, vertically,
and is marked as provisional until the plugin grows the real branch (part 5).

### 3.6 Loads

The net rope's weight, the wire ropes' weight, and the skin, course by course,
from the cut plan, as the Cable net run builds them today. The trees' own
weight goes into their member forces, not into the net.

### 3.7 Not modelled in this part

Listed so that none of it is mistaken for having been considered: the
mechanism's permanent tension tie; wind; temperature; creep; a rope's bending
stiffness; winding layers on a drum; friction in pulleys; inertia (swing and
bounce).

## 4. The sequence: computed once, captured, replayed

### 4.1 The raise

The formwork export's 51 frames run from machine time 0 to 100 in four
phases: reel (15 frames), raise (15), finish (15) and hold (6). At every
frame:

1. the trees stand at that frame's node positions;
2. each wire's required paid-out length is the straight distance from its
   spool to its rim node's designed position at that frame;
3. each motor reels its common change (section 3.3);
4. the engine solves for the shape the net takes, and the state is captured.

The difference between where the net settles and where the frame designed it
to be is the deviation, frame by frame.

### 4.2 The tiling

From the hold frame on, the reels hold where they are: closed-loop steppers
hold position. Each course's weight goes on in four equal steps, each solved
and captured, so a course is seen landing and the net settling under it.
Whether the machine should re-reel between courses to win back the shape is
part 3's question.

### 4.3 The captures

Every solved state is one capture. It holds:

- the position of every net node, wire segment node and tree node;
- every net member's and wire segment's tension, or that it is slack;
- every head's and hold's push;
- every tree member's axial force, utilisation and any fork's bending load;
- every motor's common reel and its drum tension;
- every net node's deviation from the frame's designed position;
- how it was solved: Newton or relaxation, iterations, the largest leftover
  force.

### 4.4 The build clock and the replay

Each capture carries a time on the real build's clock. Between raise frames
that is the largest reel change of any motor divided by the rope speed (the
Rope speed dial). No placement rate is recorded for the tiles yet (section
11), so until one is, each tiling step is given one second.

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

Unknowns: the positions of every node not held. Held: the spools (the wires'
fixed ends) and the tree nodes (prescribed). Net nodes on heads or holds are
free and pushed by contact, not fixed.

Each step is solved by Newton's method from the previous capture's state:

```
R(x)  = f_ext - f_int(x)                residual force at every free node
K(x) dx = R(x)                          K: tangent stiffness, material plus
                                        geometric; slack ropes add nothing;
                                        contacts add k_c while pushing
x     <- x + a dx                       a in (0, 1], line search on |R|
done  when max |R_i| < 0.01 N and max |dx_i| < 0.001 mm
```

It reuses the sparse assembly and the sparse factorisation, with its
condition check, that the stiffness module already has. When Newton fails to
reduce the residual, finds the stiffness singular, or reaches 30 iterations,
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

## 9. Performance

About 51 raise solves and 80 tiling solves on the real study. The target is
five minutes or less on the owner's machine, measured before the plan is
final; if it is exceeded, fewer tiling steps per course before anything else.

## 10. Out of scope here

The five mechanism choices and the derived electronics (part 2); the
prestress search, the roof, the next mechanism up and the holds needed (part
3); the tab, focus mode, strain colours, newton labels and the player (part
4); the plugin's Columns (part 5). This part's own visible output is the
script's findings and images.

## 11. Open items

1. The mechanism's permanent tension tie is not modelled; whether it bears on
   the net during the raise is the owner's to say.
2. No tile placement rate is recorded, so tiling steps play at one second
   each until one is given.
3. The cut: a uniform prestress in every member (today's rule) or the
   designed form's own member forces plus a prestress. Part 3 decides it with
   the prestress search.
4. The tree tube's wall thickness is assumed at 3.2 mm until the plugin
   exports the section (part 5).
5. Whether the machine re-reels between courses to win back the shape is
   part 3's.
6. Bending at the forks is reported, not modelled.
