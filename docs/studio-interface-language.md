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
and Projection, Scale and Height only in HDRI mode, with Scale and
Height only for the grounded dome. Brightness and Rotation act in every
mode and always show. The HDRI tiles stay in every mode, because
choosing one switches to HDRI.

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
    Lights     Output, Warmth, Glow, Size, Length

Three are HIDDEN inputs -- `sun-azimuth`, `sun-elevation` and
`day-cycle-seconds` -- which are the model behind the sun dial widget
rather than dials anyone reads. Three are exempt for stated reasons:
`timeline-scrubber` is a transport whose position IS the time, and
`scatter-size-min` and `-max` are one dial with two grips sharing the
reading "0.80 to 1.30".

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

The inventory of section 10 is now 41 sliders. Since then: `site-
latitude`, `site-longitude`, `site-north` (Scene, Site), `section-offset`
(Scene, Section), `camera-width` (Camera, shown in orthographic in place
of Field of view), and the Output section's `still-size` segments.

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
a rectangle by accident. Each fill is its own undo entry, and a session's
fills share one layer. Arming a tool folds the
shelf away and ONE Escape brings it back (the tool's handler is in the
capture phase and stops the event immediately, or the window's general
Escape would close the drawer again); a CLOSED shelf is not "another
drawer" and must not disarm the tool. The click-to-place version lasted
one morning: "i want to drag the brush around".

**The live graphs are the model's own readings, with the model written
on them.** `#graphs-panel` is a column of mostly translucent cards down
the left edge (z 11: under the stilling cover and the data sheet), one
per quantity a physical model would instrument: cable force, the load on
the formwork, column force with its strain, thrust at the supports. They
come up when Play starts (the `#shelf-graphs` tile and the close button
move the remembered switch), follow the clock from the render loop
(never from applyTimeline, which stays pure in t), scrub with the
scrubber, and a click on a graph seeks the take to that instant. Each
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
what lets a fixture read when the day is turned down. Night is not a
preset's angle but a time on the site's own clock (dusk plus ninety
minutes), so the day track, the day cycle and every environment mode
agree about what hour it is; below the horizon the sun goes out and the
moon takes the shadow.

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
