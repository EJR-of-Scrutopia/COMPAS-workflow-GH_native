# Where to grab the net: what the real export says

This is the cable net analysis run on the owner's study `5 sided form`, through the studio's own routes and in process, by `bench/scripts/cablenet_real.py`, on 8 October 2026. Each block below is that script's own output, copied as it printed it, and the prose between the blocks only says how to read them. The progress lines it prints every five seconds while the engine works are left out. The short answer is in the last section, which says nothing the lines do not.

To run it again, from the repository root: `.venv/Scripts/python.exe bench/scripts/cablenet_real.py`. It reads the export folder that `bench/studio/settings.json` names and writes only under `bench/studies/`. The demand document it writes is runtime output and is not committed.

## The options the run used

The script asked for tile in the bonded-courses pattern, a piece size of 1.0 m, a skin 0.02 m thick and a prestress of 300 N, and left the rest to the route's defaults: the 4 mm rope, batches of 20 nodes, at most 40 steps, and the falsework plywood-rib-2000. The pattern only names the file the demand is kept under, because this study's cut is its authored skin, and the line `cut source: authored` says so.

The server did not run with the falsework it was given. The engine takes its acceptance line from the deflection of a timber rib under the same skin, and refuses a rib that spans less than half the vault's reach as describing a different building. The vault's reach is 16.1 m and a rib of 2000 mm spans less than half of it, so the server used the shortest rib in the catalogue that does, glulam-rib-9000, and the note line says so. That rib gives the line of 3.25 mm.

```
export folder: C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports
run: 202 {'run': 'c3c807c15332'}
run done after 120 s
cut source: authored  demand document: C:\dev\VS code\COMPAS-Workflow-bench\bench\studies\5-sided-form\studio\cablenet-tile-authored-s1000-t20.json
schema bench.cablenet/2  prestress 300.0 N  EA 450000.0 N  acceptance 3.25 mm (falsework glulam-rib-9000: {"depth": 400.0, "description": "glulam GL24h rib 9000 x 600, 400 x 90 deep", "e_modulus": 11600.0, "spacing": 600.0, "span": 9000.0, "width": 90.0})
note: falsework glulam-rib-9000 was used in place of plywood-rib-2000, which spans 2000 mm, less than half the vault's 16.1 m reach
```

## What is held

Three things hold the net. The 105 wire nodes are the supports, each pulled along its own wire by a drum, so a wire pulls and does not push. The 46 column heads are props whose positions are prescribed, so a column is a reaction and not a member. The 800 actuators are the nodes the walk chose to grab, and the next section says how it chose them. Of the net's 1101 nodes, 1055 are not column heads, and 800 of those were grabbed.

```
held: 105 wire nodes, 46 column heads, 800 actuators
net: 1101 nodes, 2000 members; 1055 are not column heads, of which 800 were grabbed and 255 were not
```

## The placement curve

The walk starts from the wires and the column heads alone, grabs the 20 nodes left most unbalanced, fits the net again and repeats, up to 40 times. It is a heuristic and makes no claim to be the fewest nodes. Here it ran all 40 steps and stopped there, and the line was not reached: `reached False`. The worst sag fell at every step, from 2027.7 mm with nothing grabbed to 12.3 mm with 800, against the line of 3.25 mm. The worst unbalanced force fell from 433.1 N to 15.7 N, and the norm of the unbalanced forces from 2506.3 N to 125.6 N. The placement is made at S17, the heaviest instant.

```
placement at S17: batch 20 steps 40 reached False
      0 grabbed  worst sag     2027.7 mm  worst unbalanced    433.1 N  norm     2506.3 N
     20 grabbed  worst sag     1676.2 mm  worst unbalanced    194.6 N  norm     1957.2 N
     40 grabbed  worst sag     1489.0 mm  worst unbalanced    151.8 N  norm     1726.1 N
     60 grabbed  worst sag     1229.4 mm  worst unbalanced    140.3 N  norm     1583.4 N
     80 grabbed  worst sag     1091.7 mm  worst unbalanced    120.5 N  norm     1456.5 N
    100 grabbed  worst sag      985.1 mm  worst unbalanced    106.5 N  norm     1353.6 N
    120 grabbed  worst sag      812.9 mm  worst unbalanced     98.9 N  norm     1270.3 N
    140 grabbed  worst sag      723.1 mm  worst unbalanced     90.1 N  norm     1188.5 N
    160 grabbed  worst sag      657.4 mm  worst unbalanced     81.9 N  norm     1120.2 N
    180 grabbed  worst sag      587.0 mm  worst unbalanced     76.5 N  norm     1058.5 N
    200 grabbed  worst sag      506.2 mm  worst unbalanced     72.6 N  norm     1001.9 N
    220 grabbed  worst sag      455.3 mm  worst unbalanced     67.7 N  norm      951.7 N
    240 grabbed  worst sag      376.5 mm  worst unbalanced     65.6 N  norm      901.5 N
    260 grabbed  worst sag      343.6 mm  worst unbalanced     61.7 N  norm      855.8 N
    280 grabbed  worst sag      329.5 mm  worst unbalanced     55.7 N  norm      814.3 N
    300 grabbed  worst sag      263.6 mm  worst unbalanced     52.7 N  norm      776.4 N
    320 grabbed  worst sag      245.9 mm  worst unbalanced     50.1 N  norm      738.9 N
    340 grabbed  worst sag      228.4 mm  worst unbalanced     48.7 N  norm      703.5 N
    360 grabbed  worst sag      197.9 mm  worst unbalanced     46.2 N  norm      669.3 N
    380 grabbed  worst sag      180.0 mm  worst unbalanced     42.5 N  norm      636.1 N
    400 grabbed  worst sag      165.1 mm  worst unbalanced     41.3 N  norm      607.0 N
    420 grabbed  worst sag      151.8 mm  worst unbalanced     40.7 N  norm      577.8 N
    440 grabbed  worst sag      139.4 mm  worst unbalanced     38.2 N  norm      549.9 N
    460 grabbed  worst sag      122.6 mm  worst unbalanced     37.6 N  norm      523.0 N
    480 grabbed  worst sag      111.5 mm  worst unbalanced     36.1 N  norm      496.5 N
    500 grabbed  worst sag      105.6 mm  worst unbalanced     34.2 N  norm      470.8 N
    520 grabbed  worst sag       92.7 mm  worst unbalanced     33.9 N  norm      445.3 N
    540 grabbed  worst sag       88.8 mm  worst unbalanced     31.8 N  norm      420.1 N
    560 grabbed  worst sag       84.1 mm  worst unbalanced     31.5 N  norm      395.4 N
    580 grabbed  worst sag       70.0 mm  worst unbalanced     29.9 N  norm      370.6 N
    600 grabbed  worst sag       62.8 mm  worst unbalanced     28.1 N  norm      347.0 N
    620 grabbed  worst sag       60.7 mm  worst unbalanced     27.0 N  norm      323.9 N
    640 grabbed  worst sag       48.2 mm  worst unbalanced     25.9 N  norm      301.7 N
    660 grabbed  worst sag       42.2 mm  worst unbalanced     25.2 N  norm      279.0 N
    680 grabbed  worst sag       37.4 mm  worst unbalanced     24.0 N  norm      256.1 N
    700 grabbed  worst sag       33.3 mm  worst unbalanced     22.6 N  norm      232.8 N
    720 grabbed  worst sag       27.1 mm  worst unbalanced     21.2 N  norm      210.9 N
    740 grabbed  worst sag       19.6 mm  worst unbalanced     19.4 N  norm      187.9 N
    760 grabbed  worst sag       19.0 mm  worst unbalanced     18.2 N  norm      166.7 N
    780 grabbed  worst sag       15.0 mm  worst unbalanced     16.8 N  norm      145.3 N
    800 grabbed  worst sag       12.3 mm  worst unbalanced     15.7 N  norm      125.6 N
```

## The first twenty actuators chosen

The numbers are contract node numbers, in the order the walk took them: the first batch of 20, most unbalanced first.

```
first actuators chosen: [670, 450, 890, 119, 230, 220, 108, 779, 880, 660, 559, 339, 440, 1100, 999, 229, 118, 449, 669, 889]
```

## The stage table

There is one row for each instant the engine computed: the five sampled frames of the raise, F45 to F100, then the 20 courses of the skin, S1 to S20, which are cumulative from the rim to the crown. `wire N` is the largest wire tension at that instant, `actuator N` the largest force at a grabbed node, `dev mm` the worst sag with only the wires and the column heads holding, `after mm` the worst sag once the 800 grabbed nodes hold too, `reach` whether that is inside the line, and `column N` the largest force at a column head. The frames of the raise carry only the net's own weight and are not judged. The courses are judged, and none of them is inside the line. The worst column over all the rows is named under the table.

```
 stage    kind     wire N actuator N     dev mm   after mm     reach   column N
   F45   raise        0.3        1.5       22.8        0.3      True        6.1
   F60  finish        0.2        1.5       17.7        0.3      True        6.1
   F75  finish        0.2        1.5       19.1        0.3      True        6.1
   F90    hold        0.2        1.5       19.2        0.3      True        6.1
  F100    hold        0.2        1.5       19.2        0.3      True        6.1
    S1    tile       14.6       43.5       84.0        4.3     False       44.0
    S2    tile       14.6       43.5      104.0        4.3     False       44.0
    S3    tile       14.6       70.1      168.9        7.0     False       70.9
    S4    tile       14.6       70.1      238.7        7.6     False       70.9
    S5    tile       14.6       70.1      317.8        9.1     False       70.9
    S6    tile       14.6       70.1      423.1       10.1     False       70.9
    S7    tile       14.6       70.1      539.8       11.0     False       70.9
    S8    tile       14.6       72.7      731.1       12.1     False       74.0
    S9    tile       14.6       84.8      940.6       12.2     False       86.8
   S10    tile       14.6       84.8     1301.0       12.3     False       86.8
   S11    tile       14.6      103.1     1547.7       12.3     False      106.7
   S12    tile       14.6      115.5     1685.4       12.3     False      106.7
   S13    tile       14.6      133.5     1809.2       12.3     False      141.6
   S14    tile       14.6      147.6     1914.3       12.3     False      141.6
   S15    tile       14.6      218.0     1989.3       12.3     False      215.7
   S16    tile       14.6      218.0     1989.3       12.3     False      215.7
   S17    tile       14.6      435.1     2027.7       12.3     False     1499.8
   S18    tile       14.6      435.1     2027.7       12.3     False     1499.8
   S19    tile       14.6      435.1     2027.7       12.3     False     1499.8
   S20    tile       14.6      435.1     2027.7       12.3     False     1499.8
worst column: 1499.8 N at S17, node 120 (vertical part 1499.8 N)
```

## The sizing block

The engine sizes the system on the course that works the parts hardest, here S17, which is the first of four courses, S17 to S20, with the same figures. The worst wire tension is about 14.6 N, the worst force at a grabbed node about 435.1 N, and the worst sag about 12.3 mm, under a load of about 67459 N. The wires, which are what the load factor is judged on, carry little beside the grabbed nodes.

```
sizing: {'stage': 'S17', 'worst_wire_tension_newtons': 14.580109355377992, 'worst_actuator_newtons': 435.1058005569256, 'worst_sag_mm': 12.251784374877603, 'load_newtons': 67458.98645081984}
```

## The six load factors and the recommendation

Judged as the catalogue judges them, all six rigs have a load factor of 0.0: the shape is already past the line of 3.25 mm at the sizing stage, and no part changes that. With the shape set aside, all six reach 20.0, the largest factor the walk tries, and nothing binds. The six therefore tie on what their parts carry, and the recommendation falls to the rule's remaining tests, the fewest parts and then the first listed.

```
  stepper-seven-spool          load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
  stepper-seven-spool-block    load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
  stepper-eye-eye              load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
  stepper-heavy                load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
  inverter-worm                load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
  inverter-worm-heavy          load factor 0.0 binds on shape  |  parts alone 20.0 binds on nothing
recommend: stepper-seven-spool | the shape is past the acceptance line at the sizing stage and no part can change it; ranked by what the parts alone carry: the largest load factor, then the fewest parts, then the first listed
```

## What this says

The walk grabbed 800 nodes, which is all that its 40 batches of 20 allow, and it did not reach the line: the worst sag is 12.3 mm against 3.25 mm, and the worst unbalanced force is still 15.7 N. That is consistent with the measured expectation in section 13 that nearly every node the columns do not hold is unbalanced: the walk found 20 to take at every one of its 40 steps, took 800 of the 1055 nodes that are not column heads and left 255, so it needs more than 800 nodes to reach the line and no more than 1055. The worst column carries 1499.8 N, at node 120 from S17 on, against 215.7 N at S16, but the split of the skin between the columns and the grabbed nodes follows a convention of the fit, that a member between two held nodes carries nothing, so these forces are one tension-only state among many and not a measurement. The catalogue would build stepper-seven-spool, though only on the tie-break: judged against the shape every one of the six has a load factor of 0.0, and judged on the parts alone every one reaches 20.0. The load factor weighs the wires, whose worst tension is 14.6 N, and not the 435.1 N that a grabbed node needs, which a wire there would have to carry, so it does not yet show that any rig in the catalogue holds the 800. So the finding of section 13 stands: the actuators are necessary, 800 is not enough, and the walk's cap, not the net, set the count.

The load factors in the table above were judged at the fit's own 14.6 N in the worst wire, while the shape half gave every member the entered 300 N as a floor on its stiffness. They are superseded by the rule the final review settled: a wire is judged at the larger of the entered prestress and the greatest tension the fit finds in any wire, worked out once in the engine's sizing block. Fitting the net with that floor, so that the imbalance the prestress leaves is charged to the grabbed nodes, is an open item for the owner, and it would change the grab count.


## Addendum, 9 October 2026: judged against a 20 mm tolerance

The owner ruled, on reading this document, that the acceptance line is a
tolerance from the designed form, not the deflection of a falsework rib: the
falsework the machine does away with is a mould cut to the vault's exact
surface and propped from below, which barely moves. The 3.25 mm line above was
the sag of a straight 9 m glulam beam that the server had swapped in for the
catalogue's 2 m plywood rib, a beam nobody designed for this vault. The run was
repeated with the same options and a tolerance of 20 mm, the placement
tolerance the T1 brief sets at full scale; it took 80 s. The quoted lines
are the run's own, copied by a program.

```
schema bench.cablenet/2  prestress 300.0 N  EA 450000.0 N  acceptance 20.00 mm (a tolerance of 20.00 mm from the designed form, set for this run)
held: 105 wire nodes, 46 column heads, 740 actuators
net: 1101 nodes, 2000 members; 1055 are not column heads, of which 740 were grabbed and 315 were not
placement at S17: batch 20 steps 40 reached True
```

The walk picks the same nodes whatever the line, and this time it stopped at
the first point within 20.00 mm, so its curve is the one above, point for
point, ending at 740:

```
    680 grabbed  worst sag       37.4 mm  worst unbalanced     24.0 N  norm      256.1 N
    700 grabbed  worst sag       33.3 mm  worst unbalanced     22.6 N  norm      232.8 N
    720 grabbed  worst sag       27.1 mm  worst unbalanced     21.2 N  norm      210.9 N
    740 grabbed  worst sag       19.6 mm  worst unbalanced     19.4 N  norm      187.9 N
```

```
 stage    kind     wire N actuator N     dev mm   after mm     reach   column N
   F45   raise        0.3        1.5       22.8        0.7      True        6.1
   F60  finish        0.2        1.5       17.7        0.6      True        6.1
   F75  finish        0.2        1.5       19.1        0.6      True        6.1
   F90    hold        0.2        1.5       19.2        0.5      True        6.1
  F100    hold        0.2        1.5       19.2        0.5      True        6.1
    S1    tile       14.6       43.5       84.0        4.3      True       44.0
    S2    tile       14.6       43.8      104.0        9.0      True       44.0
    S3    tile       14.6       70.1      168.9       14.7      True       70.9
    S4    tile       14.6       70.1      238.7       16.9      True       70.9
    S5    tile       14.6       70.1      317.8       18.6      True       70.9
    S6    tile       14.6       71.5      423.1       19.1      True       70.9
    S7    tile       14.6       71.5      539.8       19.4      True       70.9
    S8    tile       14.6       72.7      731.1       19.6      True       74.0
    S9    tile       14.6       84.8      940.6       19.6      True       86.8
   S10    tile       14.6       84.8     1301.0       19.6      True       86.8
   S11    tile       14.6      103.1     1547.7       19.6      True      106.7
   S12    tile       14.6      115.5     1685.4       19.6      True      106.7
   S13    tile       14.6      133.5     1809.2       19.6      True      141.6
   S14    tile       14.6      147.6     1914.3       19.6      True      141.6
   S15    tile       14.6      218.0     1989.3       19.6      True      215.7
   S16    tile       14.6      218.0     1989.3       19.6      True      215.7
   S17    tile       14.6      435.1     2027.7       19.6      True     1499.8
   S18    tile       14.6      435.1     2027.7       19.6      True     1499.8
   S19    tile       14.6      435.1     2027.7       19.6      True     1499.8
   S20    tile       14.6      435.1     2027.7       19.6      True     1499.8
worst column: 1499.8 N at S17, node 120 (vertical part 1499.8 N)
```

```
sizing: {'stage': 'S17', 'worst_wire_tension_newtons': 300.0, 'fitted_wire_tension_newtons': 14.580109307758057, 'prestress_newtons': 300.0, 'worst_actuator_newtons': 435.1058005569256, 'worst_sag_mm': 19.626526644687637, 'load_newtons': 67458.98645081984}
```

```
  stepper-seven-spool          load factor 4.9 binds on turnbuckle-hook-hook-M10
  stepper-seven-spool-block    load factor 4.0 binds on WZ-11-K
  stepper-eye-eye              load factor 7.8 binds on 34HS46
  stepper-heavy                load factor 12.5 binds on rope-6mm
  inverter-worm                load factor 4.9 binds on turnbuckle-hook-hook-M10
  inverter-worm-heavy          load factor 12.5 binds on rope-6mm
recommend: stepper-heavy | the configuration that carries the skin with the largest margin, the ceiling over the tension the wires are judged at; among ties the fewest parts, then the first listed
```

At 20 mm and 300 N of prestress the walk reaches the line with 740 grabbed
nodes of the 1055 the columns do not hold, and every instant, frames and
courses, is within it: the worst sag after grabbing is 19.6 mm, from S8 on. The
answer of 8 October, that 800 were not enough, was an answer to the invented
3.25 mm line. The walk is the 8 October walk, node for node, up to 740: the
same nodes in the same order, with the same sags and residuals, checked
against the earlier document. With the shape inside the line the rigs are
judged on their parts: the two heavy rigs have a load factor of 12.5, the
eye-eye stepper 7.8 and the other three 4.0 to 4.9, and stepper-heavy is
recommended on the margin, tied with inverter-worm-heavy and first listed.
Two items stay open for the owner. The wires are judged at
the 300 N prestress floor, not at the 14.6 N the skin drives through them, so
each factor measures the prestress against the parts. And the 435.1 N a
grabbed node needs is judged against no rig.
