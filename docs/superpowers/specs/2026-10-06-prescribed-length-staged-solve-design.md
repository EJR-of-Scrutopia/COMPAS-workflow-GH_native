# Prescribed-length staged solve, and the mechanism trade study

Design, 6 October 2026. Status: agreed in brainstorm, not yet implemented.

## 1. Why this exists

The spooling machine commands the shape of a cable net by reeling length. Every
number the project needs downstream, which motor, which gear ratio, whether
there is a pulley at all, what size rail and extrusion, how much spooling takes
the net from flat to raised, follows from one capability the codebase does not
have: solving a cable net from prescribed unstrained lengths rather than from
prescribed forces.

The candidate has ruled that this solve is the authority. No component is
ordered until it runs.

The engine to extend is `src/tree_forest_compas/fd.py`, which holds a working
force density solver (Schek 1974, D = C^T Q C) with a clean API:
`register_fd_network`, `solve_fd_problem`, `solve_fd_network`. Nothing anywhere
in the repository handles rest lengths. Note for the record that
`T2_digital_twin/06_gap_list_and_build_order.md` names `tools/tree_forest/mould.py`
as the engine to extend; that file no longer exists and the gap list should be
corrected to point here.

## 2. Decisions taken

1. The solve comes before component choice, not after.
2. The build sequence is raise first, then tile ring by ring. The raise is a
   reeling phase with no skin load; the tiling is a loading phase in which the
   machine holds the form.
3. The core is headless Python with no Rhino and no web dependency. Grasshopper,
   the studio and the command line are thin adapters over it.
4. When several mechanism combinations pass, the output is all three trade
   fronts rather than a single ranking invented here.
5. The net carries physical location markers at its nodes, so node position is a
   measured quantity and the correction can be computed from measurement rather
   than from the model alone.
6. The acceptance line is the CNC-cut timber falsework the machine replaces,
   computed under the same load, not a tolerance chosen by hand.

## 3. Scope

In scope: statics of the cable net, the staged sequence, the capacity envelope,
the mechanism trade study, and the register that records all of it.

Out of scope for this piece, to be built when the component they depend on
exists: the reinforcement learning hold controller, parameter identification and
Kalman filtering against live sensors, time-domain dynamics and natural
frequency, wind, creep, thermal length change, and clamp slip.

## 4. The five solves

### 4.1 Forward: rest lengths in, geometry and tension out

Each member's force density depends on how far it has stretched, so the linear
solve is wrapped in an iteration:

```
q_i = EA_i * (L_i - L0_i) / (L0_i * L_i)

q_i   force density of member i, force per unit length
EA_i  axial stiffness of the cable, N
L_i   current strained length of member i
L0_i  prescribed unstrained length, which is what the machine reels
```

Guess q, solve the linear system for the geometry, measure the new lengths,
update q, repeat until node positions stop moving within tolerance. Report the
iteration count and the final residual; refuse on non-convergence.

### 4.2 Backward: target geometry in, rest lengths out

Direct, not iterative:

```
N_i  = q_i * L_i                  tension in member i
L0_i = L_i / (1 + N_i / EA_i)     rest length before stretching
```

Run on the target funicular and again on the flat starting net; the difference
per cable is the spooling travel from flat to raised.

### 4.3 Hold, which is the inverse kinematics: keep the form as load arrives

The target geometry is fixed and the skin load grows ring by ring. With the
geometry fixed, equilibrium is linear in the force densities, so this is a least
squares solve for q under the accumulated load, followed by 4.2 to turn those
tensions into rest lengths:

```
A(x) * q = p                 equilibrium at fixed geometry x under load p
q >= 0                       cables pull only, never push
N_i  = q_i * L_i
L0_i = L_i / (1 + N_i / EA_i)
```

The reel command for a ring is the change in L0 between consecutive stages.

Both halves of the loading phase are run and reported. Holding the rest lengths
fixed gives the sag if the machine does nothing, which is the honest test of
whether correction is needed at all. Running the hold solve gives the duty:
tension at every stage, correction per ring, torque at the worst instant.

### 4.4 Correction from measurement

The same solve against measured node positions rather than target ones:

```
dx  = x_measured - x_target        deviation at every node
J   = dx / dL0                     sensitivity of node position to rest length
dL0 = least squares solve of J * dL0 = -dx
```

J comes from the stiffness matrix the forward solve already assembles.

The system is under-actuated: one rest length per cable against three
coordinates per node. The solver must therefore report the residual deviation
after the best achievable correction, not only the command. If the residual at
the crown exceeds the acceptance line, that is the net asking for more cables,
and it is a prototype decision rather than a controller tuning problem.

### 4.5 Capacity: the mechanism asked what it can hold

Given a mechanism specification, raise the load until something binds:

```
for load in rising steps:
    run the hold solve at the target geometry
    check deviation    against the falsework acceptance line
    check tension      against rope MBL divided by the safety factor
    check tension      against anchor and eye bolt working load
    check drum torque  against motor torque x ratio x efficiency x margin
    check for any cable going slack
stop at the first breach; report which constraint bound and at what load
```

Two numbers are fixed here so they are not reinvented per run. The torque margin
is one half, that is a stage passes only if the required motor torque is at or
below half the motor's rated holding torque, following T1 05. The rope safety
factor is five against minimum breaking load, following T1 02. Both are
parameters with those defaults, and both are recorded in the register beside the
result so a reader can see what the pass was measured against.

Run at n = 1, 2 and 4 and the pulley question answers itself with a named
reason: if torque binds first the pulley earns its place, and if deviation or
rope tension binds first it does not.

## 5. The trade study

A sweep over the choices, with the physics as hard constraints.

| Variable | Range | Trade |
| --- | --- | --- |
| Drum winding radius | 25 to 75 mm | resolution and torque against fleet angle and single-layer capacity |
| Reeve factor n | 1, 2, 4 | lead tension and torque against rope travel, drum speed and carriage height |
| Pulley diameter | 60 to 120 mm | rope fatigue (D over d) against space in the frame |
| Gear ratio | 5, 10, 20, 50 | torque against speed and backlash |
| Motor | the T1 shortlist, NEMA 23 to 34 | torque and size against cost and driver choice |

Hard constraints, each refusing rather than scoring: rope tension within safety
factor, anchor and eye bolt within working load, drum torque within the motor
envelope with margin, D over d above the standard minimum, drum width holding
the required rope in a single layer, fleet angle within limit, carriage travel
within the frame, deviation within the falsework line.

Output is the feasible set, each member tagged with the constraint closest to
binding, each rejected combination tagged with what killed it, and three
fronts plotted rather than one winner: accuracy at the net, machine size and
simplicity, and margin for growth.

## 6. The staged run

```
S0        net flat or slack, anchors fixed, no skin
S1..Sk    raise increments, rest lengths stepping towards the target
T0        raised to target, unloaded, prestress set
T1..Tn    tile rings, springing towards crown, one solve per ring
X         strike: supports released, the vault stands alone
```

## 7. The register

One file per run, written by whichever adapter drove it, in the same schema
every time.

Per stage, per cable: required rest length, change from the previous stage (the
reel command), turns at the drum, cable tension, lead tension after the reeve,
drum torque, motor torque after ratio and efficiency, prestress floor and
ceiling for that stage, slack flag.

Per stage, per node: target position, modelled position, deviation, and a column
left for the measured position from the node markers.

Per stage, overall: skin load applied so far, worst tension, worst deviation,
the falsework deflection under the same load for comparison, and the constraint
closest to binding.

This is both the sizing evidence for the mechanism and the digital twin register
the Vaulted web app exports, so it is written once and read by both.

## 8. Where the code lives

Core, plain Python, beside `src/tree_forest_compas/fd.py`, no Rhino and no web
dependency, unit tested in isolation.

Adapters, thin, all producing the identical register:

1. A Grasshopper component in `src/ananke_equilibrium` for designing against the
   Rhino model of the workshop and the sited prototype.
2. A studio runner extending `bench/studio/solve_stage.py` so Vaulted can play a
   staged run and export the register.
3. A command line entry so the trade study can sweep thousands of combinations
   with no GUI involved.

## 9. Refusals

The solve refuses, with the number that broke it, rather than returning a
plausible value, when: a member would need to carry compression (reported as
gone slack, which is a topology or anchor finding); the iteration does not
converge; EA is missing or assumed; the system is singular from an
under-constrained net; the required tension exceeds rope, anchor or motor
envelope; the prestress window for a stage closes, meaning the floor needed to
hold tolerance exceeds the ceiling the hardware allows.

## 10. Acceptance tests

1. A single taut string recovers the analytic sag.
2. The prescribed-length solve, given the rest lengths implied by a known
   force-specified solution, recovers that solution's geometry and force
   densities.
3. Offsetting every node of a copy of the target by exactly 10 mm makes the
   deviation report read 10 mm.
4. A member forced into compression is refused as slack, not returned.
5. A deliberately under-constrained net is refused as singular.
6. Doubling skin density doubles every member force before any correction.
7. A capacity run on a deliberately under-powered mechanism reports torque as
   the binding constraint, at the right load.

## 11. Inputs still needed

1. Net geometry and anchor positions, once the prototype is sited at true size
   in the modelled office workshop.
2. The skin as an areal load in kN/m2 from the real tile. The studio currently
   carries 1800 kg/m3 at a 200 mm default, which is 3.5 kN/m2, while two layers
   of real thin clay tile are about 0.6 to 0.7 kN/m2 (T3). Every force in the
   project currently rests on the wrong one.
3. Cable E_eff and metallic area. Working values are 60 GPa and the area from
   the chosen rope's mass per metre, both marked ASSUMED until the rig pull test
   replaces them.

## 12. To verify before the numbers are quoted

1. The falsework and formwork deflection limits in ACI 347 and BS 5975. If they
   are of the order of span over 270 to span over 360, then 11 to 15 mm over a
   4 m span is what timber falsework is permitted, the 5 mm working tolerance is
   stricter than the thing being replaced, and relaxing it to the real line
   lowers prestress, tension, torque and possibly the need for a pulley.
2. The minimum D over d for the chosen sheave and rope, against ISO 4308-1.
3. The fleet angle limit for a grooved drum of the chosen geometry.

## 13. What comes after

With the register in hand: choose motor, ratio, pulley or no pulley, pulley
size, rail and extrusion, each from a line in the register rather than from
judgement. Then the adjustable rig set-ups for varying torque, microstep and
pulley height. Then stage B of the digital twin, with sensors streaming in.
