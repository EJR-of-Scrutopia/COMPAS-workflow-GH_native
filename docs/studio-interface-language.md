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

**Declare `data-unit` when the dial can rest at zero AND its reading is
not its raw value.** Two conditions, not one, and the second is the part
that is easy to get wrong.

At zero the derivation gives up -- 0 mm and 0 m read the same -- so a
dial whose reading is millimetres of a value held in metres declares
`data-unit="1000"`. But where the reading IS the raw value the
derivation returns 1, which is already right, and declaring a factor
there is actively wrong: `data-unit="100"` on a dial reading 100 makes a
typed 50 set the slider to 0.5, which its own `step` then rounds away.
That was a real bug in `sky-brightness`, written and caught on the same
day by the test that enforces this section.

A dial whose `min` is not zero must NOT declare one at all, or a later
change to its handler silently stops being honoured.

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

in that order. The grid is the only part that scrolls, so the dials and
the readout stay in view while browsing. `Scatter` and `Lights` are the
worked examples.

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

Measured across `index.html`, 48 labels and 37 sliders.

**Three slider shapes coexisted:** 13 in the old `name slider
<span>value</span> unit` form, 11 in the new four-part form, and 9 with
no readout markup at all.

**Eighteen sliders carried no reading**, so they could be neither read
nor typed into:

    hdri-scale, hdri-height, hdri-rotation, scatter-size-min,
    scatter-size-max, glow-strength, outline-width, size-slider,
    thickness-input, exaggeration, timeline-scrubber, orbit-speed,
    brightness, contrast, day-cycle-seconds, sun-azimuth, sun-elevation,
    background-tone

Some of those are deliberate -- `timeline-scrubber` is a transport, not a
dial, and reads its position elsewhere. The rest are the backlog.

**Eight sliders can rest at zero and do not declare `data-unit`**, so
typing into them lands the raw number:

    hdri-rotation, sky-brightness, scatter-clump, scatter-clearance,
    timeline-scrubber, orbit-speed, sun-azimuth, background-tone

Where a dial is a plain count or a percentage of itself the factor is 1
and nothing is wrong; where it is not, typing is broken today.

The Scatter and Lights drawers are the reference implementation. Bring
the rest to them a section at a time rather than in one sweep, because
each one needs its handler checked against its new reading cell.
