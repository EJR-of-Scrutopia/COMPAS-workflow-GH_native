# The Cable net tab: a display an engineer can read

Date: 2026-10-09. Approved in conversation the same day, after the owner looked at the merged studio and found it "really bad". This is the first of three steps he ordered: this display pass, then part 3 (the prestress computed from the load, the nodes that need columns), then part 4 (the raise played from the physics engine).

## 1. What is wrong today, in his words and on screen

- The panel reads as paragraphs (the demand readout, the grab sentence, the notes). His rule: a tool, not a book. Yes, no, or a value.
- Mechanism, costs and graphs are stacked down the side menu.
- The lenses draw bare arrows: node force and prestress have no numbers, no colours and no legend; reel shows nothing; wire tension shows only a few rim members.
- The timber skin, made transparent over the net, hides what the lens shows.

## 2. What stays out of this pass

- The prestress slider stays until part 3 computes the prestress from the load; the panel's "Needed" line shows the run's floor until then.
- The nodes that need columns, and the accuracy a motor change gives (the sag at each prestress), are part 3.
- Playing the raise from the physics engine is part 4.
- The exports' documents keep their prose: they are documents for others, not the panel.

## 3. The Cable net menu (right)

In order, and nothing else:

| Row | What |
|---|---|
| Run cable net analysis | the button and its one-line status |
| Tolerance | the slider, mm |
| Prestress | the slider, N (until part 3) |
| Wires a motor | a slider, 1 to 7; it replaces the select of that name and keeps its remembered value |
| Needed | the run's prestress floor, N (part 3 replaces it with the prestress the form needs) |
| Gives | the chosen machine's worst wire ceiling, N a wire, with a mark and the margin (the ceiling the verdict reports since the final review: the shared motor's or gearbox's where that binds) |
| Most | the strongest wire ceiling any combination in the catalogue gives on this study's machine, N a wire, with that combination's name |
| Mechanism | the button that opens and closes the pop-up |
| Lenses | Wire tension, Node force, Sag, Prestress, Reel |
| Stage | the instant's caption alone ("F60 finish", "S7 tile") |

A warning is one line of data: `Run again: dial 2650 N, run 300 N`, `Run again: tolerance 15 mm, run 20 mm`, `Run again: wire EA 700000 N, run 450000 N`. No other text.

"Most" is computed on the server over every combination at one wire a motor (sharing only lowers a ceiling), on the study's own machine and angle, and returned with the scored row.

## 4. The pop-up (left)

A panel on the left, built like the data sheet (`#data-panel`: fixed left, scrim background, tabs), opened and closed by the Mechanism button and its own close button. Opening it closes the data sheet and tucks the live graphs column, which share that place. Whether it is open, and which tab, is remembered in this browser.

### 4.1 Mechanism

- The motor, ratio, pulleys and wire selects, and Recommend with its one-line answer.
- **Limits a wire, N:** each term of the chosen machine (wire, anchor chain, spool rope, pulleys, gearbox, motor) as a number with its part's name; the one that binds marked. The motor's row is what the motor produces at the wire.
- **Every motor:** one row a motor, each with the ratio its frame keeps or the first it offers, and your pulleys, wire and wires a motor: motor, ratio, N a wire, margin, mark, price. Clicking a row chooses it.
- The machine's parts table, the worst wire per machine, the drum and the carriage against their limits.
- The rope speed slider and its rpm at the motor.
- The eye bolt's angle as a row: `10°, assumed`.

### 4.2 Cost

The study total (with the floor mark where lines are unpriced), each cabinet's total, the cabinet lines with supplier, the basis quoted and the source, the wire to buy, and Export with its folder.

### 4.3 Graphs

Inline graphs, one line each, stage by stage along the run:

- worst wire tension, N, with the chosen machine's ceiling as a line;
- worst sag, mm, with the tolerance as a line;
- worst node force, N;
- the grab walk (sag against nodes grabbed), as today.

Below them, the net in numbers: floor N, tolerance mm, skin kN, net kN, wires, column heads, grabbed nodes, the largest grabbed node pull N, the worst sag mm, the sizing stage.

## 5. The lenses

### 5.1 The shell

While any Cable net lens is up, every piece of the skin shows light grey (#dcdcdc) at opacity 0.3, with no texture; each piece's own colour, texture and opacity come back when the last lens goes down. The skin's outline is unchanged.

### 5.2 Colour and a legend on every lens

| Lens | Coloured | Legend |
|---|---|---|
| Wire tension | the net's members by tension (as today) | `member tension, N` with its range |
| Node force | the nodes by force magnitude, pale to red | `node force, N` with its range |
| Sag | as today | as today |
| Prestress | each machine wire within, near, or over the chosen machine's ceiling (green, amber, red); grey with no machine scored | `wire tension, N: within / near / over <ceiling>` |
| Reel | each machine wire by the rope taken in so far: blue taken in, amber paid out | `reel, mm: in / out` |

The arrows stay, behind an "Arrows" tick under the lens; the tick is off by default for Node force and on for Prestress and Reel.

### 5.3 Numbers on the model

- Each of the 105 machine wires carries its figure at its rim node under Prestress (`1.2 kN`) and Reel (`-3.2 mm`, the rope taken in so far, which is never blank: a wire that has not moved reads `0.0 mm`).
- Node force and Wire tension label their 20 largest (`845 N`).
- Clicking a node or a wire's rim node shows a small card beside it: the node, its force N, its sag mm, held or grabbed; for a wire's rim node also the wire's name, tension N, ceiling N, margin and reel mm. Clicking elsewhere closes it.
- Labels are HTML placed by projecting each point every frame, as the hover badge is; one hidden behind the camera or off the view is not drawn. At most 125 labels show at once.

## 6. What the panel's model owns

The browser's model (`cablenet_model.js`) keeps every figure and table; the controller only fills ids. No model function returns a sentence: the functions that wrote the demand paragraphs and the grab sentence are removed with their tests, and the warnings become the one-line data templates of section 3. New model functions are tested under node as today: the three menu answers from a row and a demand, the stage series for the graphs and their SVG, which points get a label under each lens, and each lens's legend and colour for a value.

## 7. The server

- `POST /api/studies/{export}/cablenet/configurations` adds to its answer `strongest`: `{ceiling_newtons, described, limit, part}`, the "Most" of section 3, worked out once for a study's machine and angle and kept.
- Each row adds `terms`: the chosen machine's ceiling terms in N a wire, each with its part's name, for 4.1's limits table.
- Nothing else changes on the server.

## 8. Tests and the check on screen

- Every new model function under node; the panel's DOM ids and wiring by text, as the existing panel tests do; the two route additions by route tests on the Tiny study.
- A test that no readout the controller writes contains a sentence: no `<p>` holding prose, only tables, values and the one-line warnings.
- **On screen, before handover.** The plan's last task starts the studio on a spare port with the real 5 sided form study, opens the Cable net tab in a headless browser, and saves a screenshot of the menu, each pop-up tab, and each lens with its labels and legend. The executor looks at every screenshot against this spec and the owner's rulings, and fixes what is wrong, before telling him it is ready. Then the owner checks it himself.
