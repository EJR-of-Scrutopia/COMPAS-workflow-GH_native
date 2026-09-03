# The night's work: interface, sun, props, WebGPU

Written for Param, 2026-09-04, after the overnight run. Everything below is
on `feature/studio-finish`, committed, tested, and running. The server has
been restarted, so a plain reload is enough; hard refreshes are no longer
part of the workflow, for a reason given under "the cache" below.

---

## 1. What changed while you slept

### The material browser is a material browser

Materials and render skins are rendered spheres in a two-column grid, the
name centred underneath, nothing beside the picture. The sphere carries the
same registry material the vault is cut in, under a fixed three-point rig
with its own environment, so the preview cannot drift from the thing it
previews: it is the thing.

The ground surfaces are previewed too, on a tilted plane rather than a ball,
because the reason to choose paving over concrete is the size of the pieces
and a sphere cannot show that. The preview borrows the scene's own material
and puts its texture repeat back afterwards, so looking at a floor cannot
change the floor.

One small hidden renderer serves every tile. It is built inside a guard: a
browser may refuse a second WebGL context and a driver may fail one, and a
panel that falls back to flat colour is a disappointment while a panel that
throws before the first frame is a dead studio.

### The sun is one instrument

Three sliders and a colour picker are gone. In their place: a compass with
the sun's bearing, an arc with its height and the horizon drawn as a line,
a day track painted with the sky the model actually produces at each hour,
and six chips that solve their own moments.

The maths is the NOAA solar calculator's formulation, which is Meeus's
low-precision solar coordinates with his equation of time and NOAA's
refraction. It is pinned in the test suite against three independent facts:

- London's midsummer noon elevation, 61.94 degrees, against the analytic
  90 - 51.507 + 23.438 = 61.93;
- the published sunrise and sunset for that day, 04:43 and 21:21 BST, to
  the minute;
- the equinox sun standing overhead at the equator, and the midday sun
  standing due north from Sydney.

Dragging the compass sets the TIME, not the angle: the day is searched for
the instant that puts the sun on that bearing, so you cannot drag the sun
somewhere the sky would never put it in September. Sunrise and sunset solve
on the almanac's own definition, the upper limb on the horizon. Noon is
SOLAR noon, where the shadow is shortest. A moment the sun never reaches
today greys out rather than lying: there is no 20 degree morning sun over
London in December, and the chip says so.

The colour picker is gone because sun colour is not an independent
variable. What reddens a low sun is optical path length: one air mass at
the zenith, about thirty-eight at the horizon, with Rayleigh scattering
stripping blue as the fourth power of frequency. Dimming and reddening are
therefore the same variable, and elevation drives both. The ramp was
derived by attenuating a 5778 K source through Rayleigh, aerosol and ozone
terms and integrating against the CIE 1931 observer; it gives the accepted
5.6 magnitudes of extinction from zenith to horizon, so it is calibrated
rather than tasted. It fades across the last degree and a half rather than
switching off, because at sunset the sky is doing the lighting.

The day cycle is now the clock running: dawn to dusk on the real day at the
real site, through exactly the same code path a chosen time takes.

### Props are a library of real models

Fifteen CC0 models from poly.pizza, which is where the Google Poly archive
survives alongside the Kenney and Quaternius packs: two figures, a pine and
a broadleaf tree, a bush, a hedge, a bench, a table, a planter, a lamp
column, a car, a cone, a barrier, a fence, a pallet. The whole library is
10,673 triangles, less than one course of the vault.

They are chosen from the same tile grid the materials use, each tile a
render of the model from a fixed three-quarter view.

The manifest carries what the file cannot: a real-world height in metres
for every model, because a GLB holds whatever units its author worked in
and a figure is only a scale figure if the studio scales it to a stated
height. It also carries the credit and the licence, shown on the tile and
written into a NOTICE beside the files. Everything is CC0 and asks for
nothing; it is credited anyway.

The hand-modelled props remain as the fallback for an empty library folder,
which is what made this safe to ship overnight.

### The panel

- Every slider is one row: name left, value right, the row itself the
  track. The native input is kept, stretched over the row and invisible, so
  every handler, id and keyboard behaviour survives; only the appearance is
  new. Twenty parameters now cost twenty lines instead of forty.
- The setting is a segmented row, Studio | Sky | HDRI, rather than a
  dropdown that shows one and hides two.
- Every group heading folds its group, and a folded group carries a summary
  on the right: which surface and how big, which setting, what time the sun
  is at, how many props are placed, how many scenes are saved. Five lines
  instead of a column you have to read to the bottom of.
- One face, one size, throughout.

### The cache

Twice this week a fix shipped and looked as though it had not, because the
browser kept yesterday's stylesheet. Static files are served `no-store`
now. A plain reload always gets the current studio.

---

## 2. What I could not do, and what I need from you

**WebGPU.** The build is vendored and there is a probe at
<http://127.0.0.1:8600/static/webgpu.html>. Open it on your machine: it
reports the adapter, renders the seven registry materials under a six
degree sun, and prints the frame rate. I did not switch the studio's
renderer, deliberately. This sandbox has no GPU at all, so nothing here
could tell me how WebGPU behaves on a 4090, and switching the renderer
unattended on a night when nobody can look at it is a decision made without
the one piece of evidence that matters.

What the switch would cost: the EffectComposer, RenderPass, ShaderPass and
BrightnessContrast grade are WebGL-only and would be rewritten as TSL
nodes; the preview renderer behind the tiles needs the same treatment or
stays WebGL. PMREM, shadows and MeshPhysicalMaterial carry over.

What it would not buy, and this is worth being blunt about: **three.js has
no Lumen**. There is no real-time global illumination in the library. The
honest options are ambient occlusion and screen-space GI as post nodes,
which are an improvement but not the thing, or a path-traced still for a
final image, which is the thing but not real-time. If what you want is the
D5 look, the path is: better IBL (you have it), contact shadows, AO, and a
"final render" mode that path-traces a still over a few seconds. Say the
word and I will spec it.

**More props.** The sandbox refuses network access to the shell, so tonight
I pulled the models through the Playwright Chromium you pointed at, a page
that fetches a file and base64s it into the DOM. It works and the script is
ready to pull more. If you want a bigger library (interiors, people in more
poses, vehicles, planting variety), say which categories and I will add
them; each is about a minute.

**Three older one-line notes** still sit in the panel: under the pattern
select, under the appearance controls, and the joint-gap note. They carry
honesty statements rather than decoration, so I left them for your word.
Say "log them" and they go to the event log with the rest.

---

## 3. Ideas worth considering next

Ordered by what I think they would be worth to you.

1. **A final-render mode.** A button that path-traces the current view over
   ten or twenty seconds and hands you a 4K still. This is what would
   actually close the gap to D5 for presentation images, and it does not
   require moving the whole studio to WebGPU.

2. **HDRI thumbnails.** The HDRI list is filenames. Each could be a
   tone-mapped strip of the equirect with the sun's direction marked as a
   pip, generated once and cached. It is the last list in the panel that
   still asks you to remember what a name looks like.

3. **A north offset and a site.** The sun model already takes latitude,
   longitude and a north offset; the panel currently assumes London and
   north at +Y. A small popover with those three fields would make the
   shadow study defensible for a real site, which matters for the PhD work.

4. **Weather as sky renders.** The five weather presets could be previewed
   as small sky renders using the same Sky shader, which would make
   "Golden hour" and "Overcast" a look rather than a word.

5. **Scene compare.** Two saved scenes side by side, or a wipe between
   them, for showing a client the same vault under two skins or two skies.

6. **Prop scattering.** Place ten figures along a line or around the rim in
   one gesture, with a little jitter, rather than one at a time. Populating
   a scene properly is what makes an image read as architecture.

7. **A measure tool.** Click two points, get a dimension, drawn in the
   scene. For a vault study this is the one instrument the studio does not
   have and every reviewer asks for.

8. **Shadow study.** Since the sun is a real position now, a strip of six
   thumbnails across the day would be a genuine analysis rather than a
   picture, and it comes almost free from the machinery already here.

---

## 4. State of the work

- Suite: 424 passing, 1 skipped, on `tests/studio`.
- Every new rule mutation-proved; two mutants survived at first attempt and
  were chased down, one of which found a real flaw in the colour ramp
  (it extrapolated below the horizon instead of clamping).
- Smoke tested in headless Chromium after each wave: the module evaluates,
  boot runs, all fifteen props load, nothing reports to the diagnostics log.
- Commits: dd60673, fad84e0, bf71156, 7077608, 9536db4, c45e6fb, and the
  earlier session work from ad23d1b back.
