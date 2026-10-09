# The mechanism, chosen from five parts (part 2 of the Formwork tab)

Status: design, for the owner's review. Written 9 October 2026, after part 1
(the formwork engine, spec 2026-10-09-formwork-engine-design.md) merged into
main locally at 0bea6a6.

## 1. What this part is for

The studio sizes the machine that raises the net. Today it does so from six
named presets ("Seven-spool stepper rig", "Heavy inverter rig" and so on),
which the owner rejected on 9 October 2026: "you just name it weirdly and pre
set up everything. this is a no." This part replaces them with the five
choices he named, and derives everything else from those choices and from the
machine he exports.

His rulings, each in his own terms:

- The mechanism is chosen by five things: the motor, the planetary gear ratio,
  pulleys included or not, the wire type and thickness, and how many wires
  share a motor (9 October 2026).
- No preset rigs with made-up names (9 October 2026).
- Everything else (the power supply, the Pi, the drivers, the boards) is
  derived from the five choices, by the rules in T1 note 14 (9 October 2026).
- The studio uses the mechanism he exports and never offers a mechanism
  chooser (15 September 2026). The five choices are the drive parts fitted to
  his exported machine, not a choice of machine.
- Pulleys "yes" keeps the reeving his export draws (a factor of 4 on every
  wire of the real study); "no" runs each wire straight off its drum, a factor
  of 1, to compare (9 October 2026).
- Recommend stays, and searches every combination of the five choices
  (9 October 2026).
- The choices are kept in the studio page, remembered per study in that
  browser, and sent with every run and export (9 October 2026).
- Closed-loop motors only: an open-loop motor that slips loses its reel count
  without knowing it (9 October 2026).
- Pulleys come in a range of sizes and materials, chosen to suit the scale of
  the vault (9 October 2026).
- One cabinet per seven-spool machine; a second Octopus board above eight
  motors (9 October 2026).
- Load cells are chosen by the force each wire carries, from the Zemic H3
  range (9 October 2026).

Success: for any five choices, the studio says what each wire can pull against
what the net needs, names the part that limits it, and lists every part of
every machine and cabinet with its count, the rule that counted it and its
price where one is known. No named rig appears anywhere.

## 2. The five choices

### 2.1 Motor

Closed-loop motors only. Each carries its frame, its torque and the basis of
that torque (holding torque for a stepper, rated continuous torque for a
servo), its rated current and, for a stepper, its phase resistance, because
note 14's power budget needs both.

| Motor | Kind | Frame | Torque | Current, resistance | Driver | Price seen 2026-10-09 |
| --- | --- | --- | --- | --- | --- | --- |
| 23HS45-4204D-E1000 | closed-loop stepper | NEMA 23 | 3.0 N m holding | 4.2 A, 0.82 ohm | CL57T-V41, 24 to 48 V DC | 28.46 GBP; driver 28.75 |
| 34HS31-6004D-E1000 | closed-loop stepper | NEMA 34 | 4.3 N m holding | 6.0 A, 0.30 ohm | CL86T-V41, 24 to 110 V DC | 32.60; driver 36.58 |
| 34HS39-6004D-E1000 | closed-loop stepper | NEMA 34 | 6.5 N m holding | 6.0 A, 0.36 ohm | CL86T-V41 | 40.57 |
| 34HS46-6004D-E1000 | closed-loop stepper | NEMA 34 | 9.0 N m holding | 6.0 A, 0.40 ohm | CL86T-V41 | 40.45 |
| 34HS59-6004D-E1000 | closed-loop stepper | NEMA 34 | 12.0 N m holding | 6.0 A, 0.53 ohm | CL86T-V41 | 49.44 |
| ES-MH342200 (Leadshine) | closed-loop stepper | NEMA 42 | 20 N m holding | 5.2 A, 1.88 ohm | ES-DH2306, 150 to 230 V AC | 309 EUR (Rocketronics) or 199 USD (Leadshine) |
| A6-RS400H2A1-M17 kit | AC servo | 60 mm flange | 1.27 N m rated, 4.45 peak | 2.51 A | kit driver, 220 V AC | 77.76 GBP, kit |
| A6-RS750H2A1-M17 kit | AC servo | 80 mm flange | 2.39 N m rated, 8.36 peak | 4.6 A | kit driver, 220 V AC | 91.94, kit |
| A6-RS1000H2A1-M17 kit | AC servo | 80 mm flange | 3.18 N m rated, 11.13 peak | 6.3 A | kit driver, 220 V AC | 116.25, kit |

Every driver here takes step and direction pulses, so every motor fits the
same Octopus board. Left out, with the reason recorded beside the catalogue:
the open-loop NEMA 42 and 52 motors (the owner's ruling); the NEMA 56C AC
motors (no UK seller with a price, and no planetary gearbox is made for that
frame); the A6 1.5 kW kit (network control only); the Lunyee 50 N m NEMA 52
kit (its stated motor current, 8.5 A, is above its driver's 6 A peak, and
nothing found resolves it); and every AC motor on a worm gearbox and the
boat-lift motors, which went with the presets. No closed-loop motor exists in
a NEMA 56 size.

### 2.2 Planetary ratio

The ratios the gearboxes for the chosen motor's frame offer, plus "none",
direct drive. A ratio is offered only when its gearbox publishes a maximum
(or rated) output torque, because that torque is one of the limits in
section 4; a gearbox listed with a price and no torque waits until one is
found.

| Frame | Gearbox | Ratio | Efficiency | Output torque | Price seen 2026-10-09 |
| --- | --- | --- | --- | --- | --- |
| NEMA 23 | EG23-G5-D8 | 5:1 | 94% | 28 N m max | 26.93 GBP |
| NEMA 23 | EG23-G20-D8 | 20:1 | 94% | 30 N m max | 37.03 |
| NEMA 23 | EG23-G50-D8 | 50:1 | 94% | 25 N m max | 37.03 |
| NEMA 34 | EG34-G5 | 5:1 | 96% | 90 N m max | 47.12 |
| NEMA 34 | EG34-G10 | 10:1 | 96% | 39 N m max (to re-read) | 47.12 |
| NEMA 34 | EG34-G20 | 20:1 | 94% | 90 N m max | 67.32 |
| NEMA 34 | EG34-G50 | 50:1 | 94% | 100 N m continuous, 200 momentary | 67.32 |
| NEMA 42 | EG42-G100 | 100:1 | 90% | 260 N m max | 140.36 |
| NEMA 42 | PLG120 (Oyostepper) | 3, 4, 5, 7, 10:1 | 95% | 165, 230, 230, 220, 175 N m rated | 499 USD |
| NEMA 42 | PLG120, two stage | 9 to 30, 35 to 50, 70 to 100:1 | 90% | 165, 230, 175 N m rated | 658.32 USD |
| Servo 60 mm | AEP60-G20-D14 | 20:1 | 92% | 27 N m max | 94.28 |
| Servo 60 mm | AD60-G10-D14 | 10:1 | 97% | 18 N m max | not priced |
| Servo 80 mm | AB90-G5-D19 | 5:1 | 97% | 130 N m max | 100.98 |
| Servo 80 mm | AD90-G10-D19 | 10:1 | 97% | 50 N m rated | not priced |

The PLG120's maximum is twice its rated torque by its maker's table; the
studio uses the rated figure. The EG23 at 10:1 and the 60 and 90 mm servo
gearboxes in the HTG, MG and TG ranges (about 35 more ratios) are on price
lists with no torque, and wait. No planetary gearbox was found for a 130 mm
servo flange.

### 2.3 Pulleys

"None", or a pulley model. Pulleys "yes" keeps the reeving the export draws
for each wire; the chosen model is the pulley used in that reeving. A pulley
is offered only when its maker publishes both a working load and the wire
sizes its groove takes; where a maker states a single wire size, the pulley
takes that size only. The studio uses the working load for the angle the rope
wraps the pulley (section 4).

| Pulley | Sheave | Wire | Material, bearing | Working load | Price seen 2026-10-09 |
| --- | --- | --- | --- | --- | --- |
| GPS Lifting rope pulley with bracket | 55 mm | 2 to 4 mm | polyamide, steel bracket | 125 kg | 41.50 GBP exc VAT |
| GPS Lifting WZ type 3 | 60 mm | 2 to 3 mm | cast iron, bronze bush | 50 kg at 180 degrees, 75 at 90 | 87.00 exc |
| GPS Lifting WZ type 3 | 90 mm | 3 to 4 mm | cast iron, bronze bush | 75 kg at 180, 100 at 90 | not priced |
| GPS Lifting WZ type 3 (the catalogue's WZ 11 K) | 120 mm | 4 to 5 mm | cast iron, bronze bush | 125 kg at 180, 180 at 90 | 118.00 exc |
| GPS Lifting WZ type 3 | 190 mm | 6 to 8 mm | cast iron, bronze bush | 250 kg at 180, 320 at 90 | not priced |
| GPS Lifting stainless pulley with bracket | 100 mm | 5 to 6.5 mm | stainless steel | 500 kg | 236.00 exc |
| Pfaff DSRB 90 | 90 mm | 3 to 4 mm | steel, sealed ball bearing | 500 kg at 180, 700 at 90 | 159.18 inc |
| Pfaff DSRB 90 | 90 mm | 5 to 6 mm | steel, sealed ball bearing | 500 kg at 180, 700 at 90 | 162.63 inc |
| Pfaff DSRB 145 | 145 mm | 5 to 7 mm | steel, sealed ball bearing | 800 kg at 180, 1,100 at 90 | 275.10 inc |
| Pfaff DSRB 185/8 | 185 mm | 8 mm | steel, sealed ball bearing | 1,630 kg at 180, 2,300 at 90 | 404.86 inc |
| Wire Rope Shop galvanised snatch block, 3 in | 76 mm | 6 mm | galvanised steel | 1,500 kg | 18.72 exc |

Waiting on a figure: the Wire Rope Shop 48 mm stainless sheave (400 kg, no
stated wire size), the GPS polyamide pulleys of 50 to 100 mm (60 to 150 kg,
the load of each size not stated on the page), the Lifting Gear Direct snatch
blocks (size of the priced one not confirmed), and the GPS WZ 12.5 K (its
90-degree load reads below its 180-degree load, to re-read). The 25 to 38 mm
stainless sheaves publish no load and are not offered.

Where a maker publishes no efficiency, the studio assumes 0.98 for a ball
bearing and 0.95 for a plain bush, and says it is assumed.

### 2.4 Wire

| Wire | Breaking load | Mass | Price seen |
| --- | --- | --- | --- |
| 2 mm 7x19 stainless 316 (GS Products) | 2.28 kN (232 kg) | 0.0152 kg/m | 0.32 GBP/m exc, 2026-10-09 |
| 2 mm 7x7 galvanised (GS Products), the stiffer construction | 2.75 kN (280 kg) | 0.0154 kg/m | 0.15 GBP/m exc, 2026-10-09 |
| 3 mm 7x19 galvanised (GS Products) | 5.77 kN (588 kg) | 0.0345 kg/m | 0.29 GBP/m exc, 2026-10-09 |
| 4, 5, 6 and 8 mm 7x19 galvanised | as catalogued | as catalogued | as catalogued |

No supplier sells 2 mm 7x19 galvanised. The axial stiffness EA of the new
ropes follows the rule the catalogue's 4 to 8 mm entries already follow, EA
in proportion to the square of the diameter from the 4 mm rope's 450 kN, and
is marked assumed, as theirs is.

### 2.5 Wires per motor

1 to 7. The studio puts each machine's seven spools on the fewest motors that
carry them, ceil(7 / N), paired by part 1's search (pairing.best_split).

## 3. The machine that follows

One function takes the five choices and the exported machine and returns the
whole machine:

- Driver: the one the motor names (the CL57T for the NEMA 23, the CL86T for
  the NEMA 34s, the ES-DH2306 for the NEMA 42, a servo's own kit driver).
- Gearbox: the catalogued gearbox for the motor's frame and the chosen ratio,
  or none.
- Reeving per wire: the export's reeve factor for that wire with pulleys, 1
  without.
- Pulleys per wire: as many as the wire's reeve factor, as the catalogue's
  price already counts them. The machine document records the reeve factor
  (authored on the Machine component, 4 on the real study), not the pulleys;
  its three idlers are guides shared by the whole bank, give no advantage, and
  belong to the machine as drawn.
- Drum: the winding radius the machine document gives (machine.spoolRadius,
  33.9 mm on the real study), not the catalogue's 36 mm drum, which stays for
  its width and its price. The rail is the catalogue's MGN15H, as now.
- Anchor chain: derived, not chosen. The lightest catalogued eye bolt and
  turnbuckle whose working load, at the angle the wire pulls, covers the
  rope's working load (its breaking load over 5), so the chain never gives way
  before the rope. When no catalogued chain covers it, the chain is the
  strongest one, and the limit says so by name.
- Load cell per wire: the smallest Zemic H3 whose rated capacity covers that
  wire's peak tension (section 5.4).
- Motor count per machine: ceil(7 / wires per motor), and which spools share
  each motor (section 4.3).

## 4. Each wire's limit, and the verdict

### 4.1 The named limits

Each wire's limit is the smallest of these tensions in the wire, each named,
so the reader sees which part sets it. All but the last two exist in the
catalogue today (tree_forest_compas.mechanism.ceiling_terms).

- Rope: its breaking load over 5.
- Rope on the drum: the same, times the pulleys' mechanical advantage.
- Each pulley: its working load at the wrap angle, shared across the falls.
  The wrap angle comes from the machine document's routing; a pulley rated
  only at 180 degrees is used at that rating.
- Anchor chain: its weakest part at the wire's angle.
- Motor: the torque the motor may be asked for (half the holding torque for a
  stepper, as the catalogue already derates it; 0.8 of the rated torque for a
  servo, as it derates continuous-rated motors), times ratio, gearbox
  efficiency and mechanical advantage, over the drum radius.
- Gearbox (new): its maximum or rated output torque, as section 2.2 records
  it, times the mechanical advantage, over the drum radius.
- Shared motor (new): wires that share a motor share its motor and gearbox
  limits: the sum of their tensions, each over its mechanical advantage, times
  the drum radius, must fit the motor's and the gearbox's torque.

### 4.2 The verdict

For each wire: holds or not, by how much, and the part that limits it; for
each machine, the worst wire; for the study, the worst machine. The demand
comes from the run the section shows: in the Cable net section, the net's
demand as the cable net run writes it today; in the Formwork tab (part 4), the
engine's peak wire tension over the whole sequence, with the capture it
happens at.

### 4.3 Which wires share a motor, for the verdict

In the Formwork tab the engine's own pairing is used: the capture document
records each machine's motors (rim.motors). In the Cable net section there is
no engine run, so the shared-motor limit is checked against the worst any
pairing could do: each motor carries the N largest demands on its machine.
The verdict says which of the two it used.

### 4.4 Speed

The rope speed (from the motor's speed, the ratio, the drum and the reeving)
is reported, not judged: how fast the trees extend is not in the export, so
the raise's duration cannot be checked yet.

### 4.5 What reaches part 1's engine

Three choices change how the net moves and go into the formwork run: the wire
(its stiffness and weight), the pulleys (the reeving sets each wire's
stiffness, k = MA^2 EA / L, as part 1 computes it) and wires per motor (the
shared reels). The motor and the ratio change only the verdict. The capture
document's rim block gains each wire's reeve factor and route length, so the
Formwork tab can turn a wire's tension into its drum's tension (part 1's
deferred minor 3).

## 5. The cabinet

### 5.1 One cabinet per machine

One cabinet per seven-spool machine, as note 14 sizes it, times the machine
instances in the export (15 on the real study). The choices it depends on are
the motor's kind, the motor count and each motor's current.

### 5.2 Every cabinet

| Part | Count | Rule |
| --- | --- | --- |
| Driver | one per motor | note 14 section 2 |
| External driver adapter | one per motor | note 14 section 2 |
| BIGTREETECH Octopus Pro H723 | one per 8 motors, ceil(m / 8) | note 14 section 2; the owner's ruling |
| Raspberry Pi 5 4 GB, 27 W supply, active cooler, storage | one each | note 14 section 2 |
| Zemic H3 load cell | one per wire, plus one spare of the largest capacity used | note 14 section 2; section 5.4 |
| SparkFun HX711 amplifier | one per load cell | note 14 section 2 |
| Raspberry Pi Pico | one per 13 load cells | note 14 section 2 (8 cells use 16 of its 26 pins) |
| Ratchet pawl solenoid | one per motor (spools on one motor turn together) | note 14 section 3 |
| Sequent Microsystems 8-MOSFET board | one per 8 solenoids | note 14 section 3 |
| Europa IP65 steel enclosure 600 x 400 x 200 mm | one | note 14 section 4 |
| Phoenix Contact PTFIX distribution blocks, WAGO TOPJOB S terminals | as the buses need | note 14 section 4 |
| IEC C14 switched and fused inlet, latching mushroom E-stop | one each | note 14 sections 4 and 5 |
| Cable glands | one pack | note 14 section 4 |
| CY4x1 screened motor cable, screened encoder cable | 2 m each per motor | note 14 section 4 |

The formal safety upgrade (the Phoenix Contact PSR-SPP relay and a DC
contactor) is listed and kept out of the total, as note 14 keeps it.

### 5.3 By the motor's kind

Steppers on 48 V (the NEMA 23 and 34):

- The 48 V supply is sized by note 14's current budget. Each motor draws its
  resistive loss, I^2 R, plus its full holding torque at 60 rpm, through an
  85 per cent efficient driver:

  ```text
  I_motor = (I^2 R + T 2 pi) / (0.85 x 48)
  ```

  The 24 V rail is bucked from the 48 V rail: the board's logic at 0.5 A and
  each pawl solenoid at 0.8 A, through an 85 per cent buck. The worst case is
  every motor and every solenoid at once; the supply must carry twice it. The
  studio picks the smallest catalogued 48 V supply that does (the Mean Well
  LRS-600-48 at 12.5 A or the UHP-1000-48 at 21 A). When none does alone, the
  drivers are split across two or more supplies of the largest model, each
  with its own fused ways. Note 14's own case, seven 23HS45s, comes to about
  9 A and takes the UHP-1000-48.
- One Fulree F60J24V10A5L buck converter, 48 V to 24 V at 10 A, checked
  against the 24 V load.
- Fuses: one 7.5 A blade fuse per driver and one 5 A fuse for the buck, in
  JOREST inline holders, as note 14 and PenX size them.

Mains-fed drivers (the servos and the NEMA 42):

- The drivers run on 230 V directly, so there is no 48 V supply; the
  mains-side E-stop still cuts them, upstream of everything.
- A 24 V DIN-rail supply for the board's logic and the pawls, sized from that
  load with the same doubling. Its part is to be sourced.
- Fuses or breakers for each driver as its maker's manual sizes them. That
  figure is to be sourced; until it is, the line says so and carries no
  price.

### 5.4 Load cells, chosen by force

The Zemic H3 S-type range: class C3 (OIML R60), combined error at most 0.020
per cent of full scale, creep at most 0.016 per cent over 30 minutes, safe
overload 150 per cent and ultimate overload 300 per cent of capacity, IP67,
nickel-plated alloy steel, tension and compression, 2.0 mV/V, from 25 kg to
30 t (Zemic datasheet H3 Rev10, 2026.02). Seen at 195 GBP exc VAT for each
capacity from 50 kg to 5 t; the price of each capacity, and each capacity's
thread, are confirmed before the catalogue takes them, because the thread
sets how the cell joins the anchor chain.

Each wire takes the smallest H3 whose rated capacity covers its peak tension.
The cell is taken to sit in the wire's line at the anchor, carrying the wire's
full tension (an assumption, section 10). The generic cells (ATO, Phidgets)
are listed where their figures are published, as cheaper alternatives; the
RS PRO 2042773 (class C3, IP66, stainless) stays as the stainless option, its
price marked unconfirmed.

### 5.5 What the reader sees

Every line: the part, the count, the rule that counted it (citing note 14's
section), the unit price with its currency and VAT basis, and the source.
Lines with no price are listed, never dropped. The total is the priced part
plus a count of what is unpriced, per cabinet and for the study.

## 6. Recommend

Recommend judges every combination of the five choices: each motor, each ratio
its frame offers and none, each pulley that takes the wire and none, each
wire, and 1 to 7 wires per motor: some tens of thousands of combinations,
each judged directly from section 4's formulas, not by running the engine.

It fills the five selects with the cheapest combination that holds, and names
the part that limits it. The price is the study's whole: every machine's
motors, drivers, gearboxes, drums, pulleys, rope, anchor chains and load
cells, and every cabinet, so sharing a motor is credited for the drivers and
supplies it saves. A combination with an unpriced part ranks after every
priced one and says which price is missing.

Prices are compared exclusive of VAT: a price published inclusive is divided
by 1.2, and one whose basis is unclear is taken as published and flagged.
Prices in other currencies are converted at one dated rate kept in the
catalogue and marked converted.

The demand Recommend judges against is the one on screen. The wire, the
pulleys and wires per motor change how the net moves, and with it the demand,
so a combination that changes any of them is marked "to confirm by a run with
these choices", and choosing it offers that run.

## 7. Where it shows and how it flows

### 7.1 The catalogue

bench/studio/parts.json loses its six configurations, the AC motors, the
boat-lift motors, the worm gearboxes, the inverter and the "none" drive. It
gains the motors, gearboxes, pulleys, ropes, load cells and cabinet parts of
sections 2 and 5, each with its supplier, part number, price, currency, VAT
basis, the date seen, the source and a confidence, as the catalogue's entries
already carry; and the currency rates with the date they were taken.

Every figure the researchers recorded is re-read against its page before the
catalogue takes it: their quotes are summaries made by the fetching tool, not
the pages' text. bench/studio/catalogue.py's load_parts already refuses a
designed preset that cannot be built; it now refuses, by name and when the
studio starts, any part that lacks a figure the rules need.

### 7.2 The modules

- bench/studio/catalogue.py keeps the limits, price and speed machinery and
  takes a derived machine where it took a configuration: mechanism_for,
  ceiling_for, price_of, rope_speed and load_factor move from preset keys to
  the machine section 3 derives.
- A new bench/studio/machine.py derives the machine from the five choices and
  the export (section 3) and searches the combinations (section 6).
- A new bench/studio/cabinet.py applies note 14's rules (section 5).
- Like the rest of bench/studio, none of them imports numpy.

### 7.3 The Cable net section

The preset dropdown, "Vary parts" and the block tick box give way to five
selects: the motor; the ratios its frame offers; the pulleys, none or the
models that take the chosen wire; the wire; wires per motor. The choices are
remembered per study in the browser. Below them: the derived machine, each
wire's limit with the part that sets it, the verdict against the net's
demand, and the cabinet list with its total. Recommend fills the five selects.
The Formwork tab (part 4) reuses the same block.

### 7.4 The routes

- GET /api/catalogue serves the catalogue with the pairings the page needs
  (which ratios each motor's frame offers, which pulleys take each wire).
- POST /api/studies/{export}/cablenet/configurations takes choices instead of
  configurations and returns, for each, the derived machine, the limits, the
  verdict and the cabinet.
- POST /api/studies/{export}/cablenet/recommend searches the choices.
- POST /api/studies/{export}/cablenet/exports and its GET name the machine by
  its parts ("34HS46 on EG34 20:1, Pfaff DSRB 90 pulleys, 4 mm 7x19, two wires
  a motor"), never as a rig, and gain the cabinet list.
- POST /api/studies/{export}/formwork/run takes the pulley choice: with a
  pulley, each wire's reeve factor is the export's; with none, it is 1.

## 8. Refusals

Every refusal is a sentence that names both sides, never a bare exception:

- a ratio the motor's frame does not offer ("EG23 offers no 30:1");
- a wire outside the chosen pulley's range ("the Pfaff DSRB 185/8 takes 8 mm
  wire, not 4");
- a machine document with no winding radius;
- a part missing a figure a rule needs, at start-up;
- a cabinet whose 24 V load exceeds its buck converter, or whose motors exceed
  what any number of catalogued supplies can carry.

## 9. Tests

Each rule gets a test worked by hand:

- note 14's seven 23HS45s take the UHP-1000-48 (about 9 A, doubled, under
  21 A);
- seven 12 N m NEMA 34s need two supplies;
- two wires on one motor share its torque, and the shared-motor limit bites
  where the single-wire one does not;
- the gearbox limit bites before a 12 N m motor on EG34 20:1;
- a wire outside a pulley's range is refused, by name;
- a 230 V driver's cabinet has no 48 V supply and a 24 V DIN supply instead;
- each wire's load cell is the smallest H3 that covers its peak;
- the anchor chain is the lightest that holds the rope's working load;
- Recommend finds the known cheapest on a small hand-made catalogue, and ranks
  an unpriced combination last;
- load_parts refuses a part missing a needed figure, by name;
- the routes, the page's state per study, and the exports' wording (no rig
  name appears).

Then the real study is judged. Part 1 found its peak wire tension at 36.5 kN
and a rope at 74 kN at machine time 60, so the verdict is expected to say that
no combination in the catalogue holds that moment, and which part fails first.
That is the finding part 3 acts on.

## 10. Open items

- The load cell's place: taken here to sit in the wire's line at the anchor,
  carrying the wire's full tension. If it sits on the drum side, it carries
  the tension over the mechanical advantage and a smaller cell will do.
- Figures to confirm before the catalogue takes them: the EG34-G10's 39 N m
  against its siblings' 90; the 34HS39's resistance (0.36 ohm on the UK page,
  0.43 in a search snippet); the GPS WZ 12.5 K's two ratings; the GPS
  polyamide pulleys' load per size; the 48 mm sheave's wire size; each Zemic
  H3 capacity's price and thread; the ES-DH2306 driver's price; the AD60-G10
  and AD90-G10 prices; and the HTG, MG and TG gearboxes' torques.
- Parts to source: a 24 V DIN-rail supply; each mains-fed driver's fuse or
  breaker size; a continuous-duty rating for the pawl solenoid, which note 14
  flagged.
- The currency rates: the source and the date, chosen when the catalogue is
  written.

## 11. Not in this part

The prestress the load requires, the roof, the next mechanism up and the nodes
that need holds are part 3. The Formwork tab and its player are part 4; it
reuses section 7.3's block. The plugin's Columns component is part 5.
