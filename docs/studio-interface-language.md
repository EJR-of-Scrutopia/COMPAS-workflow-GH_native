# The studio's interface language

Param, 2026-09-09: "spend a while writing a md or specific document that
describes a language style for how all types of objects and interfaces
should be made for this application. it just sets a standard for every
additional build and can make things faster ... of course the style
should be like what we have, just now tidying up".

So this is a description before it is a prescription. Almost everything
here was already true of the studio; it was simply not written down, and
what is not written down drifts. The measurements in the sweep at the end
are what drift looks like.

Read this before adding any control. It is short on purpose.


## 1. The four planes, and no more

`studio.css` opens with them and the reason: it "stops thirty unrelated
greys accumulating again".

    --ground   the viewport, and the well behind a grid
    --panel    the panel itself
    --raised   a control, a popover, a tile
    --well     an inset, a track, a hover

Every surface is one of those four. Every border is `--line`, or
`--line-lit` under the pointer. Nothing introduces a fifth grey, and
nothing hard-codes a hex outside `:root`.

Ink is `--ink` for what you read, `--ink-2` for what you read second,
`--ink-3` for metadata and for a heading at rest. There is one accent
(`--accent`) and one red (`--danger`), and the red means destruction:
banners, the stale notice, deletes. It is never decoration.


## 2. Two heights and one spacing scale

    --h        32px   a control
    --h-small  24px   a chip, a list row

Those are the only two heights the panel is allowed. Spacing comes from
`--s1 --s2 --s3 --s4 --s6 --s8` and nothing else; a number that is not on
the scale is how a dense panel starts to look accidental.

Corners are `--radius` on a control and `--radius-s` on a thumbnail.


## 3. A dial is always the same four things

This is the rule that the sweep found most often broken, and the one that
matters most because Param reads these numbers all day.

    <label title="what it does, in a sentence"><span>Name</span>
      <input id="thing" type="range" min=".." max=".." step="..">
      <b id="thing-value">1.20</b><em>x</em></label>

inside a `<div class="dial-block">`. Four parts, in this order, always:

| part | is | why |
|---|---|---|
| `<span>` | the name | first column, so names align down the block |
| `<input type="range">` | the dial | second column, so tracks align |
| `<b id="...-value">` | the reading | tabular figures, right aligned |
| `<em>` | the unit | its own column, greyed |

`.dial-block` is a grid, so those four columns line up down the whole
block rather than each row finding its own edges. That is the whole
point: a column of ragged numbers is unreadable at a glance, and reading
at a glance is what a dial is for.

**Every dial has a reading.** A slider with no number cannot be read and
cannot be typed into, and `makeValueTypable` needs the reading cell to
exist. Eighteen sliders had none when this was written.

**The reading is typable, and that is free** as long as the reading cell
is there: `panel.js` derives the unit factor from `shown / raw`, so no
table of sliders has to be kept in step with any labels.

**The rule turns on where the dial RESTS, not on its `min`.**

- **Resting at zero: state the factor.** At zero the derivation gives up
  -- 0 mm and 0 m read the same -- and the markup cannot be inspected to
  find out either, because the reading and the raw value are both 0.
  `outline-width` rests at zero and is millimetres of a metre;
  `contrast` rests at zero and is a percentage of a multiplier. Neither
  is inferable, so both say so.
- **Resting away from zero, with the reading equal to the raw value:
  state nothing.** The derived factor is already 1, and declaring one is
  actively wrong.
- **Resting away from zero, with the reading unequal:** the derivation
  works. A declaration is optional and usually noise.

`data-unit="100"` on a dial already reading 100 makes a typed 50 set the
slider to 0.5, which its own `step` then rounds away. That was a real bug
in `sky-brightness`, written and caught on the same day by the test that
enforces this section.

Note that "can rest at zero" is about the RANGE, not the floor:
`contrast` runs from -0.5 to 0.5 straight through it.

**A paired range** -- a low and a high sharing one reading, as the size
ratio does -- is one dial with two grips. One reading between them is
the shape, not a missing one.

**A colour swatch is a dial's second cell like any other.** The Lights
drawer's Colour is `<span>Colour</span>`, an `input[type="color"]`, a
`<b id="lamp-tint-value">` holding the hex, and a `<em>` naming the
thing: four cells, the same four. The browser's own swatch is a white
rectangle in a chrome border belonging to no theme, so
`.dial-block label > input[type="color"]` gives it the studio's own
well, line and corner. The `#panel` rules that dressed the sun's colour
stop at the panel and reach no drawer.

**So is a toggle, and its unit cell stays empty.** Invisible is
`<span>Invisible</span>`, a checkbox, a `<b id="lamp-invisible-value">`
reading yes or no, and an empty `<em></em>`. A toggle has no unit, and
inventing one ("body", "state") is worse than a blank column: the four
cells are what the whole block is read down, and the blank is the
honest fourth. The box sits at its own width at the left of its cell
(`justify-self: start`) rather than stretching a track it does not
have.

A dial's `title` says what it changes in one sentence, in Param's own
terms. "The clear gap between items, as a multiple of each one's own
width" is right; "spacing factor" is not.


## 4. Naming

- Element ids are `kebab-case`, and a dial's reading is always
  `<slider-id>-value`. `syncLightControls` writes to exactly that, so
  breaking the pairing stops the reading updating with no error at all.
  The Glow dial had `glow-value` beside a slider called `glow-strength`
  and had therefore shown a static 60 since the day it was written;
  nothing pointed at it, and nothing complained.
- A drawer is `<name>-panel`, its tile grid `<name>-kinds` or
  `<name>-species`, its action row `<name>-actions`, its status line
  `<name>-readout`.
- JavaScript is `camelCase`. A function that draws is `paintX`, one that
  rebuilds from state is `renderX` or `syncX`, one that reads the model
  is `xOf` or `listX`.
- Say the thing, not the mechanism. The user-facing word is "fixture",
  not "lamp"; "Output", not "lumens slider"; "Keep clear", not
  "exclusion radius".


## 5. Buttons

Three kinds and no more.

- `.primary` -- the one action a drawer exists for. At most one per
  drawer.
- a plain `<button>` -- everything else.
- `.shelf-act` -- an icon tile on the shelf rail (undo, redo, play,
  record, full screen, stats).

A button that puts the app into a mode gets `.active` while that mode is
on, and the class is the only thing that says so. A destructive button
turns `--danger` on hover, never at rest.

Every button carries a `title`. A disabled button's title says **why**
it is disabled, not what it would do: "Nothing to redo", not "Redo".


## 6. Tiles

A tile is a `<button class="tile">` holding a canvas and a name, built by
`previewTile(value, label, paint)`. Its identity is `dataset.value`.

- Tiles live in a `.tile-grid`.
- Groups are separated by `<span class="tile-family">`, whose text is the
  manifest's own group word, lower case.
- A drawer whose items carry groups offers them as chips in the drawer
  head (`#shelf-cats`) through `shelfChips`, with "all" first.
- The `title` carries what the label cannot: real dimensions, triangle
  count, provenance. Labels lie about size -- "Pine roots" is a 15 cm
  root plate 1.9 m across -- so the numbers go in the tooltip.
- Selection is `.active`.
- A grid where selecting several means something supports **shift-click
  for the run** between the last plain click and this one, and a range
  ADDS rather than replaces.
- Preview pictures come from a `.thumb.png` beside the model, never from
  loading the geometry. Only a prop with no snapshot pays a live load.


## 7. Drawers

A shelf drawer is:

    tile grid (scrolls, takes the free height)
    chips or chosen items, if the drawer has a selection
    one .dial-block of every dial
    one row of actions
    one readout line

in that order. `Scatter` and `Lights` are the worked examples.

A drawer is bounded to the viewport. Its head, with the close button,
never leaves the screen, whatever the drawer holds: the head stays
pinned at the top of the drawer on an opaque ground. The tile grid
scrolls inside the drawer, and when the grids and the dials together
are taller than the viewport, the drawer's body scrolls under its head
as well. Nothing a drawer shows can push its own close button out of
reach. (The Skies drawer in Sky mode, with the weather grid open, did
exactly that: the close button sat 203 px above the top of a 720 px
screen, and the only way out was to press the tile again.)

Controls that do nothing in the current mode are hidden rather than
shown dead. The Skies drawer shows the weather picker only in Sky mode,
and Projection, Rotation, Scale and Height only in HDRI mode, with
Scale and Height only for the grounded dome. Rotation turns the
photograph and re-aims the sun from it, so outside HDRI there is
nothing for it to turn. Brightness acts in every mode and always shows.
The HDRI tiles stay in every mode, because choosing one switches to
HDRI. The atmosphere picker shows in every mode, because the fog works
in all three, and its nine dials show only while a preset other than
None is chosen.

The readout line is a full sentence in the second ink, and it says the
state, not an instruction, once there is state to report: "18 placed,
0.0 M triangles" rather than "Ready".


## 8. Messages

- Say what happened and what to do, in that order: "stopped at 271 -- 25
  M triangles. Loosen the spacing or pick a lighter tree."
- Never blame the user's file for a limit of our reader. The morning of
  2026-09-09 was lost to "Upload one from the Skin component", said of a
  study whose skin was already on disk.
- A guard rail with no explanation reads as a broken tool.
- No em dashes anywhere, in the interface or the source. Two hyphens.


## 9. What must never regress

- A new drawer never breaks the existing pointer handling. OrbitControls
  and the prop handling both bind `pointerdown` at boot, so anything that
  needs the press first listens in CAPTURE phase, and takes its listener
  off the moment the mode ends.
- Nothing pickable goes into `propsGroup` unless it is a prop.
  `propRecordAt` walks that group recursively and CONTINUES past a hit
  that maps to no record, so a stray child there causes a WRONG selection
  rather than a clean miss. Overlays go in `scene` with a no-op
  `raycast`.
- Anything drawn over the viewport hides itself during a take.
- **Hiding a thing must never stop it being clicked.** Param asked for
  a fixture whose body is not drawn but whose light still shines, and
  said in the same breath that he must still be able to click it where
  it stands. `Object3D.visible = false` would take it out of the
  raycast along with the picture, and an object that cannot be clicked
  again is an object he has lost. Hide the MATERIAL instead:
  three's Raycaster tests neither flag, so the renderer skips it and
  `propRecordAt` still finds it, and the shadow pass renders a mesh
  only `else if (material.visible)`, so the shadow goes with the body.
  The rule generalises: anything hidden stays selectable, by the
  viewport and by the Layers tile both.
- `renderer.info.autoReset` stays off, with a per-frame reset. Left on it
  clears the counters on every render call, and the composer ends a frame
  with a fullscreen copy pass, so a reading taken afterwards reports that
  pass alone.


## 10. The sweep, 2026-09-09

Measured across `index.html` before: 48 labels, 37 sliders, and THREE
slider shapes coexisting -- 13 in the old `name slider <span>value</span>
unit` form, 11 in the four-part form, and 9 with no readout markup at all.
Eighteen sliders carried no reading, so they could be neither read nor
typed into.

After: **31 of 37 sliders are in the language**, and the other six are
accounted for rather than outstanding.

    Skies      Projection, Brightness, Scale, Height, Rotation
    Skin       Shine, Relief, Occlusion, Variation, Outline,
               Piece size, Thickness
    Analysis   Deflection
    Animation  Timeline speed, Spin rate
    Camera     Field of view, Brightness, Contrast
    Scene      Background, Size, Scale, Relief
    Scatter    Brush, Spacing, Size, Clumping, Clump size, Keep clear
    Lights     Output, Warmth, Size, Length

Three are HIDDEN inputs -- `sun-azimuth`, `sun-elevation` and
`day-cycle-seconds` -- which are the model behind the sun dial widget
rather than dials anyone reads. Three are exempt for stated reasons:
`timeline-scrubber` is a transport whose position IS the time, and
`scatter-size-min` and `-max` are one dial with two grips sharing the
reading "0.80 to 1.30".

Glow was removed on 2026-09-11 (Param: "glow doesnt work well id
rather remove it"), and the Lights row above is four dials. A fixture
reads as a light by what it lights. The Skies drawer then took the
atmosphere's nine dials, and Light rays made them ten on 2026-09-13, so the count is now **56 of 62**: 45 visible
dials, every one of them in the language, out of 51 range inputs, the
other six being the three hidden models and the three exemptions named
above. The figure is measured rather than remembered, by
`test_the_dial_census_is_the_page_s_own_tally`, which counts the page
and fails when the page and this paragraph disagree.

Two tests are the ratchet. `test_the_sweep_is_finished_and_stays_finished`
fails on any new visible slider that is not in the language, and
`test_no_slider_keeps_the_old_reading_shape` fails on any return to the
old `<span id="..-value">` form. A fourth dialect cannot start.

**What the sweep found, beyond shape.** Four defects surfaced only
because the standard was written down, and two of them were live:

- `glow-strength` had its reading at `id="glow-value"`, and
  `syncLightControls` writes to `<slider-id>-value`. Nothing pointed at
  either id. The Glow number had shown a static 60 since the day it was
  written and had never once moved.
- `sky-brightness` was given `data-unit="100"` while its reading IS its
  raw value, so typing 50 set the slider to 0.5, which its own step
  rounded away. Written and caught the same day.
- `hdri-rotation` and `lamp-lumens` declared redundant factors of 1.

Three readings were also renamed to keep the pairing rule true rather
than carve an exception into it: `outline-value`, `size-value` and
`thickness-value` became `outline-width-value`, `size-slider-value` and
`thickness-input-value`, with their writers and tests moved with them.

Scatter and Lights remain the reference implementation.


## 11. The second sweep, 2026-09-11

A puppeteer probe now photographs every panel tab and every shelf
drawer and measures four things the language forbids: a row narrower
than its block, a control past its container's edge, a visible dial with
no reading, and a truncated segment label. Every tab and every drawer
came back clean, with only the three exemptions of section 10 flagged.

It did not start clean. Two rules were found by looking that no test
could see, because every test read source text and these were layout.

**A `.dial-block` takes labels only.** It is an eight-column grid and
`.dial-block label { display: contents }` dissolves each dial into
exactly four cells, so two dials fill a row. That holds only while EVERY
child is a label: a bare `<div>` takes one cell, shifts every dial after
it by a column, and overflows the panel. Three had accumulated in
`#camera-dials` and the Camera section measured 302 px of content in a
235 px box. Segmented controls and button rows sit ABOVE the block, as
Section does with `#section-axis-segments`. Now enforced by
`test_a_dial_block_holds_nothing_but_dials`, which reads structure.

**Inside `#panel`, an upgraded row spans the block.** `upgradeSliders`
scopes to `#panel` and REPLACES each label holding a range input with a
`div.scrub`, so inside the panel no label survives for
`display: contents` to dissolve, and every scrub lands as one item in
the eight-column grid. Gathering the panel's sliders into `.dial-block`
during the first sweep therefore forced them side by side: Skin read
"Shine  Re  Occlu  Varia" across one line for a day. The rule
`.dial-block > .scrub { grid-column: 1 / -1 }` makes each upgraded row
take the whole width. The four-column alignment section 3 describes is
true of the SHELF drawers, which sit outside `#panel` and keep their
labels; inside the panel a dial is one full-width scrub row. Both are
the language.

The inventory of section 10 is now 62 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
(Scene, Section), `camera-width` (Camera, shown in orthographic in place
of Field of view), the Skies drawer's nine atmosphere dials, and the
Output section's `still-size` segments.

**Two gestures, written down.** A scatter tool never disables
OrbitControls; it takes the LEFT button and leaves the camera the other
two (`giveButtonsToTool`: middle orbits, right pans, the wheel zooms; on
touch, one finger is the tool and two fingers zoom and pan). The brush is
a stroke: a press stamps, a drag stamps again every `BRUSH_STEP` of the
radius, a release ends it, and the whole stroke is ONE undo entry. The
area stays in hand until Escape: a drag draws a rectangle and fills it,
the rectangle stays on the floor, a click fills it again with a fresh
deal, and a new drag moves on. A press only becomes a drag past
`AREA_DRAG_PX` (12 px; 24 for a fingertip), so a firm click never draws
a rectangle by accident. Each fill is its own undo entry. Every
placement lands on the open layer: a scatter, a fixture, a prop or a
stamp goes onto the layer whose tab is open (shown again, and the log
says so, if it was hidden), the scatter and Lights readouts name that
layer, and nothing but the tab strip, + and Group changes which layer
is open. A layer is made only when there is none; an undo that empties
a layer its own action made takes it away, and the redo brings the
same layer back. Group is one undo entry. Arming a tool folds the
shelf away and ONE Escape brings it back (the tool's handler is in the
capture phase and stops the event immediately, or the window's general
Escape would close the drawer again); a CLOSED shelf is not "another
drawer" and must not disarm the tool. The click-to-place version lasted
one morning: "i want to drag the brush around".

**The live graphs are the model's own readings, with the model written
on them.** `#graphs-panel` is a column of cards down the left edge on
the drawers' own ground (`--scrim`, blur 10 px; z 11: under the stilling
cover and the data sheet), one
per quantity a physical model would instrument: cable force, the load on
the formwork, column force with its strain, thrust at the supports. They
come up when Play starts (the `#shelf-graphs` tile and the close button
move the remembered switch), follow the clock from the render loop
(never from applyTimeline, which stays pure in t), scrub with the
scrubber, and a click on a graph seeks the take to that instant, ahead
of the cursor as well as behind it. The traces grow with the clock:
each is drawn only up to the cursor, with its tip on it, so the curves
develop as the take plays, a scrub back truncates them and a paused take
shows them up to where it stands; the y axis is fixed from the whole
take, so it never rescales under a growing line. A handle on the
column's right edge (`#graphs-collapse`) tucks it off to the left and
brings it back, and the studio remembers which he left
(`vaulted-live-graphs-tucked`); tucked, the cards cost nothing. Each
card's header carries the name, the unit and the live reading in
monospace; the notes line states every assumption in full; `CSV` hands
over every series with those assumptions on top. The one number no
document states, the prestress the reels put into the net, is a dial in
the four-part form, and the graphs say what fraction it is set to: a
fraction of each cable's final thrust, its force once the whole shell is
placed. When the frames carry the machine's own forces the dial steps
aside, and after the act each cable holds the tension the frames end on.
The dial and the spin rate rebuild the graphs once the hand stops, never
per frame of a drag, and every card is in place before any plot measures
itself (Plotly sizes a plot once, from its box). The numbers come from
`live_graphs.js`, which is pure and tested under node to the figure.

**Brightness is the day, and Night is an hour.** The Skies drawer's
Brightness dial (`sky-brightness`) scales everything the day gives at
once: the sun, the sky light, the sky itself, the backdrop, the fog, a
photograph's dome and the environment. It never touches a lamp, which is
what lets a fixture read when the day is turned down. A fixture
emits from its shape: the sphere from its centre, which is exactly how a
sphere that glows evenly lights anything outside it, and the strip and
the cube from their faces, one area light per face sized to that face in
the world and given its share of the output by area. A longer strip
lights a longer stripe of floor, and the Size and Length dials, the
gumball and the + and - keys all re-lay the light as they reshape it. Night is not a
preset's angle but a time on the site's own clock (dusk plus ninety
minutes), so the day track, the day cycle and every environment mode
agree about what hour it is; below the horizon the sun goes out and the
moon takes the shadow.

**The atmosphere is a height fog, and it is off until chosen.** Param
asked for "a fog but super detailed nice fog we might find in the likes
of unreal engine". The Skies drawer's Atmosphere picker (`atmosphere-
picker`, tiles in `#atmosphere-tiles`, beside the weather) offers None,
Clear air, Morning mist, Haze and Valley fog, in every environment mode,
and None is the default, so no scene changes until he picks one; a
scene saved before it existed loads as None. It is Unreal's exponential
height fog, worked in closed form on every fogged fragment
(`atmosphere.js`, which replaces three's four fog chunks before anything
renders): two layers, a main one and a ground mist, each thinning
upward from a base above the floor, so a crown stands clearer than the
floor it rises from; a start distance, so what stands close stays
crisp; a cap on how much it may ever hide; and a glow toward the sun,
the moon's by night, with its own start. The dials are Density and
Ground mist in /km, Fog height, Mist height, Base and Start in metres,
Max opacity and Sun glow in per cent, and Sun lobe as an exponent. The
fog fades toward the scene's own horizon: the Sky's, measured from the
sky itself; a photograph's, averaged from its horizon band as the
backdrop shows it; the studio wall's. The Sky takes the same fog at a
fixed distance, so a fogged floor meets a fogged sky without a seam.
The Brightness dial and the night reach it as they reach the rest of
the day, with a faint blue floor so a moonlit fog still reads as air.
Plans and elevations (orthographic) stay clean. With the atmosphere at
None, Sky mode keeps the weather's own linear haze exactly as before;
once chosen, the atmosphere owns the fog. Anything drawn over
everything (the gumball, the outlines, the analysis arrows) is never
veiled. Each tile is drawn by the same integral, per pixel, so it shows
what the preset does.

**Detail is the viewport's, never the plate's.** The Props block's
Detail segments (Draft, Balanced, Full; `prop-detail`) decide how soon a
distant prop drops to its lighter tier while composing. A still and a
take always render every prop at Full whatever the segments say
(`state.recording` forces it), so a speed trade made at the desk can
never reach a figure. It is remembered per viewer, like the theme, and
belongs to no scene: the iPad wants Draft where the desktop wants
Balanced.

**A drawer shows a family once.** A species with variants
(`entry.family`) is one tile, labelled without its variant number, and
every placement draws a variant at random. The props drawer carries one;
the scatter solver draws one from its own seeded stream before measuring
a footprint, so a replay deals the same shapes.


## 12. The fixtures, 2026-09-12

Param: "can we add spot lights too where we can vary the aperture etc,
and a larger selection of lights too. we need to make all the lights
have individual controls and colours etc, more that any light we put in
needs its own controls."

There are five kinds now, and two of them are new.

A **Spot** is a conical housing with a lit mouth and a real spot light
down its own -Z. Its target is a CHILD of the fixture, so the gumball's
rotation rings aim the beam: turn the fixture and the pool turns with
it. At rest it points straight down, which is what a spot on a track
is, and the Z arrow lifts it to where it belongs. Its four controls are
the four a spot is specified by: **Aperture** is the WHOLE cone in
degrees (three.js wants the half angle in radians, and `layFixtureBeam`
is the one place that conversion happens), **Softness** is the
penumbra, **Reach** is how far it carries with nought meaning no limit,
and **Shadow** says whether it may be interrupted. It is the only
fixture that casts by default: a spot with nothing to stop it reads as
a glow rather than as a beam, and the sun is still what the shadow
study is for.

A **Panel** is the soft box a photograph wants: a flat slab, 1.2 by 0.8,
giving its light out of ONE face, which is the whole difference between
it and a cube of the same size. It goes through the face machinery the
strip and the cube already use, with a list of one face, so nothing new
had to be written to lay it.

Both point out of their own -Z at rest. Two fixtures that point the
same way are one thing to learn rather than two.

**A control that belongs to one kind is hidden for the others.** The
spot's four rows carry `.spot-dial` and are shown only while a spot is
what the dials are pointed at, by the drawer's own rule: the selected
fixture, or any spot in the scene when nothing is selected. A sphere
never offers an aperture, and the four never reach a sphere's record
either (`SPOT_FIELDS`), because a fixture carrying a setting it can
never use carries it through the layout and every saved scene for ever.

**A panel beside the thing it tunes.** Param: "I have an idea only in
edit mode we can move them around, but if we click them when not in
edit mode, then a translucent setting pops up next to it where we can
control the sliders and options for each type of light, then when we
click anywhere not on the light or the menu it disappears."

`#fixture-panel` is the first of these, and the rules it sets are the
rules the next one follows.

- **It belongs to ONE object.** Every control writes to the record the
  card is standing beside, never to the selection and never to all of
  them. That is the whole difference between it and the drawer, and
  the drawer is re-synced on every write so the two can never disagree
  about the fixture they are both showing.
- **It is the same language inside.** An id-carrying `.dial-block`,
  four parts to every control, readings named `<slider-id>-value`, a
  `title` on each one in Param's own terms, themed tokens only.
- **It shows only what applies.** The spot's four rows are hidden for
  every other kind, and Length is hidden where stretching the body
  would not move the light (`fixtureStretches`: a fixture whose light
  is laid on its faces). A control that cannot do anything here is not
  shown dead, it is not shown.
- **It opens and closes by his sentence.** Out of edit mode a left
  click on the fixture opens it; a click on anything that is not the
  fixture and not the card closes it, in the viewport and out of it;
  Escape closes it BEFORE the drawer's Escape, because it is the
  nearer thing on the screen. The outside-click listener is in the
  BUBBLE phase, so the scatter tools' capture-phase handler, which
  takes the press first and stops it, is untouched. In edit mode the
  click still picks the fixture up and the card never opens.
- **It follows its object and dies with it.** One projection a frame
  while it is open, kept whole inside the window, and closed the
  moment its object leaves `propsGroup` (a delete, a scene, a study
  reload). The test is the object's own parent, not a walk of
  `state.props`, which on a scattered field would be tens of thousands
  of comparisons a frame.
- **It is never in a picture.** Both captures read the canvas back, so
  no DOM overlay could reach the pixels anyway, but it is closed
  outright before a plate and before a take: an overlay left up over a
  take is a thing he then has to notice. It sits at the graphs' own
  height (z 11) and after them in the document, so it paints over them
  and under the stilling cover (12), the stats tile (15) and the data
  sheet (20).

One thing found while writing it, and left alone: `body.recording
#stats-overlay { display: none }` is inert, because nothing puts
`recording` on the body -- the class only ever goes on the two record
buttons. The readout stays out of takes only because a take is read
back off the canvas. Worth fixing on its own day, not on this one.


## 13. Selection, the corner, and the slider's node, 2026-09-12

A round about how the scene is TOUCHED, rather than about how it looks.
Five rules join the language, and one is a reversal.

**A slider has a node.** Until today every bare range input was the
browser's own control -- on Chromium an accent-blue pill on a two-tone
blue track, and the one loud thing in a page of greys. Param: "the
sliders as with all sliders, matching with the grey slider not
necessarily the blue. but we can take a nice feature from that with the
circle node on the slider to indicate where it is, but change it to
something more modern."

What that control got right is the node: a mark saying where the value
stands without reading the number, which section 3's underlined `.scrub`
rows never had. So the node stays and the rest goes.

| part | is |
|---|---|
| track | 3 px, `--well`, rounded |
| travelled | the same bar in `--ink-3`, stopped at the value |
| node | a 5 x 13 upright capsule in `--ink-2`, `--ink` under the pointer |

An upright capsule, not a ball: a ball wide enough to grab covers the
track it is marking. Nothing on a slider may use `--accent` -- the
accent means selection, and a slider is not a selection.

The travelled part needs the value in CSS, and a dozen handlers write a
slider without dispatching an event -- a restore, a preset, a scene, a
change of selection. Chasing them all is how the `.scrub` rows went
stale before `repaintScrubs` existed; this is settled from the frame at
6 Hz instead, and a memo makes it free (`settleRangeFills` writes only
what actually moved). Measured: zero coloured pixels across a slider's
whole box, the node at 0.737 of the travel for a value of 0.75.

**A hover names what it is over.** Param: "i would like a bounding box
with the object type and id so i can reference it in layers, that pops
up when i hover over items with the mouse." A box round the prop and a
small card reading its kind, its number and its layer -- "Beech #7 .
Layer 2" -- and the same words on that prop's tile in the Layers drawer,
which is what makes the number a reference rather than a label pointing
at nothing.

THE BOX IS AMBER (`0xd9a441`), never the selection's blue-grey
(`0x93a6bb`). The pointer being over a thing is not the thing being
selected, and one colour for both would say otherwise. Like every other
helper in `propsGroup` it must answer no raycast: a line has a one metre
default threshold, and the selection box hijacked clicks near its own
edges once already.

**A gathering is a selection.** Shift-clicking the layer tiles has
filled `gatheredProps` for a long time, but nothing except two buttons
ever read it, so four lit tiles behaved exactly like one selected prop.
There is now one answer to "what is selected" -- `actingProps()`, the
gathering when it holds more than one and the selected prop otherwise --
and the outlines, the gumball, Delete and the undo all read it. One
gumball stands at the middle of the members' feet and every reading
pivots on that centre.

**A mode you can leave without finding a button.** Two of the three Edit
faces are gone, which reverses two of Param's own earlier requests --
the tab-strip tile and the panel's button, both asked for by name. They
went because what they were needed for no longer needs a mode: a double
click gives any prop handles, and the hover badge answers Delete and the
arrow keys. One face remains, in the Layers drawer, where props are
chosen. Escape twice leaves the mode; once drops what is in hand.

A REVERSAL IS WORTH WRITING DOWN. A control removed because the work it
did moved elsewhere is a different thing from a control removed because
it was wrong, and the next person to read this should be able to tell
which happened.

**The corner is for looking.** The overlay, graphs and fullscreen tiles
moved out of the strip beside the drawers to the top left, because they
are about looking at the scene rather than about the take. The two
panels that shared that corner -- the data sheet and the graphs column
-- open below them: a sheet that buried the very buttons it was opened
from would be a worse fault than the one it fixes.

**Stop is not Pause and not Restart.** A Stop button existed once and
was removed for being those two together. This one undoes the whole
excursion instead: the mode he was looking at, the clock he was at and
where he was standing. Both faces stay disabled until a take has been
entered, because with nothing captured there is nowhere to go back to.

**What this round did not change.** No dial was added or removed, so
section 10's census stands. The `body.recording #stats-overlay` rule
noted at the end of section 12 is still inert, and still worth its own
day.

## 14. A scatter is a thing with a name, 2026-09-13

**A scatter is what he placed, so it is what the pointer names.** The
hover badge already put one box round a scattered field rather than one
round each blade (section 13), but which props made up "a field" was
guessed from what stood on a layer: every kind there sixty-four times or
more. Trees are scattered sparsely by nature, and his beeches came to
50, 36, 26 and 15 of four kinds, so every tree boxed alone. Param: "It
also should have been that these trees should be one scatter".

A count cannot tell a sparse scatter from props placed by hand; the
scatter that placed them can. Every prop a scatter places now carries
its scatter's number, the layout keeps it beside the rows (as runs of
number and count, so a field of a million is a short list), and the
badge reads "Scatter #2 of 446 props . Layer 1". The Layers drawer uses
the same words.

ONE SCATTER IS ONE MIX ON ONE LAYER, however many strokes painted it. A
stroke is how the brush was moved, not a thing he placed, so a stroke
joins the newest scatter on its layer whose every kind the chosen
species could have made, and starts a new one otherwise. More beeches
join the beeches; switching the mix to grass starts the grass.

A LAYOUT FROM BEFORE is read once and named on the way in, and the names
are written back with the next save. Its rows cannot be the guide -- his
beeches and his ground cover are interleaved from row 139 to row 1,969
-- so a kind counts as scattered when it is there in bulk or stands at
more than one size (the scatter draws every size from its range; a prop
placed by hand arrives at exactly 1), and what was scattered is split
into the cover and what stands above two metres. Measured on his own
field: 446 beeches as Scatter #2, 98,366 of ground cover as Scatter #1,
and Delete over any beech took the 446 and nothing else.

**Deleting a scatter is one gesture of well under a second.** Deleting
his 930,000 blades held the tab for 27.8 s, long enough for the browser
to offer to close it. The cost was a membership check that walked the
whole field once for every prop in it; it is a set now, and the same
Delete takes 0.64 s. Any code asking "is this prop still placed" of more
than a handful goes through `stillPlaced`, because a selection can now be
a whole scatter.

**The Layers drawer lists what is placed.** Above forty props it used to
refuse: "Layer 1 -- 53 props, 4 kinds. Too many to picture". Param:
"we also must find a way to display the objects in layers whether
thumbnail or not, perhaps when i select an object it highlights the prop
placed so we can confer that way. this means i can easily delete many
items that are placed."

A scatter is one tile, under the heading "scattered", pictured by the
kind most of it is and named as the badge names it. A prop placed by
hand is one tile each, under "placed by hand", as before. The pictures
are the `.thumb.png` files of section 6, so the refusal's reason is
gone; a cap of 300 still holds for props placed by hand, past which the
drawer says how many more there are. Its tiles are 96 px, like the
fixtures', because it is a list of things to find, and a label wraps to
a second line rather than cutting a prop's number off.

READ BOTH WAYS. Pointing at a tile puts the amber box and badge over what
it names in the viewport; pointing at a prop in the viewport lights its
tile in `--pointed`, the same amber, and scrolls it into view. A click
selects in both, and a prop selected in the viewport lights its tile
blue. A whole scatter in the selection is drawn as one box in the
selection's colour, not as two hundred outlines round part of it.

**Delete is a word beside Place copies and Group.** It takes what a
gesture acts on -- a scatter from its tile, a shift-clicked run, or the
one prop selected -- says how many ("Delete 446"), turns `--danger`
under the pointer and never at rest, and when there is nothing to take
its title says why. The Delete key does the same over a tile or a prop.
Measured on his layer of 98,815: the drawer opened in 25 ms, a click on
the beeches selected all 446, and the button took them in 68 ms.

**What this round did not change.** No dial was added or removed. One
button was added, with its title, and one colour token, `--pointed`.

**W A S D fly the camera, and 1 to 4 choose how fast.** Param: "can we
add movement with wsad and 1-4 for moevement speeds". Unreal's viewport
keys: W and S along the look, A and D across it, the orbit point moving
with the eye so that letting go leaves the orbit where he now stands.
1 walks at 1.5 m/s, 2 goes 5, 3 goes 15, 4 goes 45; a diagonal is no
faster than a straight, and the log says the speed when it changes. The
keys stand down while anything with a caret has focus, while Ctrl, Alt
or Cmd is held, and while a take or a plate owns the camera. Measured:
held for a second at 2 the eye travelled 5.08 m, and at 4, 24.2 m in
0.56 s; with a text box focused, nothing.

**Ground cover grows to the bark, and under the arch.** Param: "around
every tree with a circle radius no grass or plants can be placed near it
... it might be that only the grass can be placed anywhere under or much
closer to any collision geometry". A tree kept everything out to the
edge of its crown. Now what a thing keeps out depends on how big the
newcomer is: something of a size with it meets its crown, and something
much smaller (a third, the step-over ratio) meets only its base, measured
from the model's own vertices in its lowest 0.3 m. The works do the
same: their plan keeps out trees, and only where they meet the floor --
springings, column feet, the anchor and the tie -- keeps out the ground
cover. Measured with the real scatter round one beech: the nearest blade
stood 2.35 m from the trunk and now stands 1.02 m, against a measured
base of 1.01 m; over the vault 0 blades were placed and now 2,954.

**Light rays, a dial of their own.** Param, over a golden-hour beech wood
he had built for rendering: "I think we are just missing light rays from
this." A pass for them was withdrawn on 11 September because it only
added lit air over the fog's own glow, which made it a second Sun glow
dial, and because rays need the air lit harder than the analytic fog
lights it, which would have re-lit every saved scene. So it returns as a
dial, Light rays, in the atmosphere's block, resting at nought in every
preset and in every scene saved before it: nothing already made changes
until he turns it up. It splits the glow rather than adding to it -- the
air the sun reaches and the air it does not are summed in one march,
the shaded share is taken away and 48 times the lit share laid on -- so
shadowed air loses exactly the glow the fog gave it and no more. Measured
in his wood under Haze, looking toward a sun 2.5 degrees up: at a gain of
4 and of 16 the wood only glowed; at 48, beams stood between the trunks.
Desktop only, as before: the iPad has no pass and no dial.
