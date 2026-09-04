# The Vaulted wave: register of Param's 2026-09-04 requests

Param's words are the authority; this file is the queue and the ledger.
He is away for a few hours and has put the session in charge of all of
it: "Make sure you get them all noted down and on the implementation
list." Work autonomously, commit per fix, never push.

## Done this session (commits on feature/studio-finish)

- Launcher/silent-boot/restart chain stabilised for good: venv console
  python.exe launched directly inside a CreateNoWindow console, cmd-level
  log redirection, restart children get stamped log files. Restart
  survived twice consecutively under observation. (b9cdc90, ec3caec)
- Recording now moves like Play (show mode + orbit base armed) and the
  finished mp4 is delivered to
  C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\Animation
  as <study>-<stamp>.mp4 (recordings_folder setting overrides). (ec3caec)
- The camera holds still through the formwork growth act and only orbits
  after it (clamped clock in both writers of the angle). (ec3caec)
- Scene saving verified server-side end to end; his "Scene 1" was on
  disk all along -- the saves that seemed lost died against dead servers.
- Material/HDRI "would not load: undefined" and broken thumbnails: all
  dead-server casualties; every probed material serves 200s when a
  server is alive.

## Done in the autonomous run (evening 2026-09-04)

- 1 CLEAR RULING: scene-row Clear removed; props Clear is the one Clear
  (clearScene stays as the internal study-switching primitive). (d12d72d)
- 2 TAB PANEL: shipped and verified live -- rail on the viewport, one
  section at a time, permanent header/footer, remembered tab. (d12d72d)
- 3 MATERIALS SYSTEM: shipped. Two curated library folders (studio-skin
  130 / studio-ground 70, real copies beside the QS stack -- ruling:
  OneDrive+junctions are a known bad pair, and 5.5 GB of folder he can
  open beats a clever link; delete the folders to undo). Weight system
  live (skin drives structural class + density table + q readout);
  dropdown hidden; 'Sprayed monolithic' on the Pattern control;
  one-crop-per-voussoir stretch UVs + Randomise texture + Variation
  slider; secondary-map failures no longer veto a material; the silent
  restore-without-load hole closed. (8936a6b, 059bf43)
- 4 GROUND CONTROLS: Scale X/Y, Relief (decoupled), Randomise floor;
  persisted in scenes. (059bf43)
- 5a PROPS EDIT: select then R / Shift+R rotates, + / - scales from the
  ground up (feet-anchored by construction), Delete removes; scale in
  the record schema, layouts and scenes. Gizmo-style drag handles are a
  possible later upgrade (TransformControls is not vendored). (80a269f)
- 5b TREES: 28 new Poly Haven CC0 vegetation props fetched, decimated
  and manifested (verified against real .bin sizes; a 30 MB pre-flight
  guard now refuses the canopy-failure class before download). Poly
  Haven holds NO oak/maple/birch/palm -- what a CC0 catalogue has is
  what we got. Buildings batch (facades, fort kit, pier, fire escape)
  fetched after.
- 6 VAULTED: title, SVG favicon with the arch + wordmark, Vaulted.lnk
  with a proper .ico (Bench Studio.lnk removed). (80a269f)
- 7 CAMERA: never below floor; clamp in renderView, the one choke point
  every camera writer passes through. (80a269f)
- Plus, earlier the same evening: the restart/silent-boot server chain
  (b9cdc90, ec3caec), recording motion + orbit + the Animation output
  folder, and the orbit holding still through the formwork act.

## Done on Param's walk of the wave (2026-09-04 evening, b8c115d + 4e56a71)

His rulings, in his words: "not do stretch it was the wrong idea. we
should keep it always uniform. but we need it to cover each face without
repeating"; "the texture scale on the skin always needs to be the same
between objects"; "a match wood grain option... use the direction of the
voussoir for that, so that each leg has the right direction"; "the
randomise isnt working on the ground floor at all"; "the floor scale is
at its smallest, which is not even near enough".

- stretchUVs -> sheetUVs: ONE sheet for the whole vault, sized by the
  largest voussoir footprint, every piece at the same uniform scale
  sampling its own hashed window. Verified live: 1501 pieces, all UVs in
  the sheet, 1501 distinct windows.
- Match grain checkbox: v runs uphill per piece (world Z projected into
  the piece plane); per-piece turns collapse to 0/180, seed parity turns
  the whole deal 90 degrees for cross-grained pictures. Verified by eye
  on a leg close-up, on and off.
- Floor Randomise now deals a rotation about the disc centre as well as
  the slide (a slid periodic pattern is invisible by definition). Lay
  angle persists in scenes, stays out of the thumbnails. Live: one click
  took rotation 0 -> 4.078 rad.
- Floor Scale X/Y floor lowered 25% -> 5% (repeat 80 -> 4 on the default
  disc).
- Scene saves now carry prop scale (restore already read it) and the
  floor lay angle.
- 685 tests green; sheet contract proved by four mutations, the scene
  pin by two.

## The second walk (2026-09-05): scale truth, assets, quality

- SCALE, for real this time (891ee52 then 72131f5): the "same scale
  between objects" break had a beautiful root cause -- a voussoir is a
  CLOSED solid and Newell's signed normal cancels to zero over one, so
  every piece's projection plane was noise. Fixed with the area-weighted
  orientation tensor; then fixed AGAIN because a 200 mm piece's joint
  walls out-weigh its faces and tipped the tensor edge-on: the frame is
  now found on the TOP SURFACE alone (frameSource, from the surface
  flags), with a projection gain so curved pieces keep sheet density.
  Live: 1501 pieces at min 2.67 / median 2.67 / max 3.01 m per texture
  unit -- a 1.13 spread, residue = honest within-piece curvature.
- PROPS EDIT MODE (00e74aa): placed props are furniture until the Edit
  button says otherwise; in the mode, click picks up (drag or click to
  place), R/Shift+R rotate, +/- scale, Delete removes, Escape cancels.
- TREES AND ROCKS SWEPT (9a674e4): 34 new CC0 props (cliffs, coasts,
  boulders, roots, trunks, moon rocks). The five modular building KITS
  removed on his word -- they render as disassembled panels. 89 props.
- VEGETATION RE-PRICED (the floating-leaves complaint): its own budget
  table (canopy 200k / mid 150k / clutter 24k), sources at or under
  target pass unsimplified; all 44 planting props rebuilt, broadleaf
  tree 60k -> 200k triangles.
- 32 NEW SKINS from ambientCG (CC0, 4K): five marbles, three
  travertines, granite; corten, blackened/polished steels, zinc, brass,
  corrugated; oak/ash/birch/fir planks, herringbone parquet, plywood;
  seven cast concretes. studio-skin now 162 materials.
- SKY AT FULL QUALITY ("i would like them at maximum quality please"):
  the visible backdrop was derived at 2048 wide (~340 px per 60 degree
  view -- his blur); now derived at min(source, 16384) under the
  versioned .bg-full.png suffix. An 8k sky serves at native 8192x4096,
  verified live. First derivation of a big sky takes real time, once.
- LOADING TOAST: translucent card + turning ring top-centre for skin,
  floor, sky and prop loads; counted, so overlapping loads keep one
  card up until the last lands.

## The third walk (2026-09-05): gumball, selection truth, the shelf

- SELECTION: two real bugs. The selected prop's own outline (a
  BoxHelper in propsGroup, line raycasts carry a one-metre default
  threshold) was hijacking clicks near its edges and returning null;
  and triangle-exact picking missed through canopy gaps. The outline no
  longer raycasts, every hit is walked, and a miss falls back to the
  nearest bounding box. Delete while carrying now releases the carry,
  the camera and the outline.
- GUMBALL (Param: "like we might find in rhino"): blue ring about Z
  rotates, gold square off the ring scales about the feet, body drags
  to move. Slim visuals over fat invisible grab twins; keyboard R and
  +/- still work. Live: ring drag = exactly the quarter turn dragged.
- MATRIX TRAP for the findings file: Raycaster trusts matrixWorld as
  stored; an object created the same frame has not rendered, so its ray
  tests geometry at the origin. Picking now updates matrices first.
- THE SHELF: bottom asset drawer (Blender asset shelf / Quixel Bridge
  pattern). Props (chips by group, click carries, drawer STAYS open),
  Materials (both libraries merged by key, Assign to skin / Assign to
  ground per availability), Skies (click loads; projection, scale,
  height, rotation moved into the drawer). Panel pickers open it; the
  old inline grids stay hidden feeding the trigger swatches.
- Sourcing note relayed to Param: standalone Quixel Bridge was sunset
  in the Fab migration -- worth one try for direct FBX tree downloads,
  else the species packs need the UE round trip.

## TREES and PEOPLE: the sourcing answers (researched 2026-09-05)

- The free people site he half-remembered is almost certainly
  **xoio-air.de** (Berlin viz studio xoio): ~25 free photogrammetry
  3D people (2014/2015/2017 sets), OBJ + 3ds Max, 2K textures, free
  commercial use, no registration. Newer and sharper:
  **humanscanrepository.com/free-3d-human-models/** -- free full-body
  scans, retopo real-time versions, 8K/16K textures, commercial with
  credit. 3dscanstore.com free samples have contradictory terms -- ask
  before commercial use. Skalgubbar/MrCutout are 2D cutouts only.
- BRITISH TREES: no free source has oak, elm, birch or ash at renderer
  quality. Closest: **Quixel Megascans on Fab** -- the European Beech,
  Black Alder, Hornbeam and Norway Maple species packs are FREE with an
  Epic account under the Fab Standard Licence (any engine), BUT ship as
  Unreal packages only: a UE round-trip export to glTF is needed, and
  the wind/season shaders do not survive. Viz-People has 18 free
  high-detail birches (3ds Max oriented). Sketchfab still serves CC0
  glTF scans (free account, per-model licence check). Poly Haven's own
  broadleaf trees are all over the 30 MB source guard.

## PEOPLE: the licence wall, and Param's one-click list

Photoreal people exist under NO CC0 licence anywhere (verified across
Poly Haven, Sketchfab, BlenderKit, Renderpeople, Mixamo, Fab). The good
sources are account-gated manual downloads -- and any GLB dropped into
the props-hd folder is auto-offered by the studio with no manifest edit:

- Renderpeople free (photoreal, native GLB, free commercial use; their
  licence forbids serving raw GLBs where third parties could extract
  them -- fine for this local studio):
  https://renderpeople.com/free-3d-people/  (Dennis Posed 004, Mei
  Posed 001, Carla Rigged 001, Manuel Animated 001)
- Sketchfab CC0 statuary (museum scans, fully clean, read beautifully
  in an architectural vignette; needs a free Sketchfab login):
  Venus de Milo by smkmuseum (24k, web-ready), Lion Statue by
  nebulousflynn, the noe-3d.at Vienna series (need decimation).
  CC0 filter: https://sketchfab.com/search?type=models&features=downloadable&licenses=7c23a1ba438d4306920229c12afcb5f9
- Stylised CC0 scale figures, fetchable any time: Kenney character
  packs (kenney.nl, CC0 GLB) or poly.pizza with the CC0 filter.

An earth/grass GROUND MATERIAL family is still a gap in the QS stack
(good CC0 sources: ambientCG Ground###/Grass###; the fetch tooling for
materials is tools/fetch_tile_sizes.py territory, a future errand).

## The queue, in order

1. CLEAR RULING. The props Clear (props-only) is correct; the Scenes-row
   Clear (clearScene: nukes vault + ground) is what ate his vault. His
   ruling: "no just have it remove the props please." The viewport-nuke
   button goes; props Clear becomes the one Clear.

2. TAB PANEL. One translucent button per section at the top-right of the
   viewport beside the panel, section name on it; clicking shows ONLY
   that section in the panel. Permanently on the panel: theme toggle,
   version stamp (header) and Formwork/Shell/Both + Restart studio
   (footer), with a small visual distinction separating header and
   footer from the changing middle.

3. MATERIALS SYSTEM (the centrepiece).
   - Remove the OLD built-in materials for skin (white presentation,
     basalt dark, timber ply) and ground (dark studio, concrete slab,
     patio pavers, tiles).
   - Remove the first material dropdown (#material-select). Its two jobs
     move: (a) cutting-pattern distinction -> the Pattern option gains
     "Sprayed" (monolithic); (b) weight -> a real weight system.
   - WEIGHT SYSTEM: density per material (different metals, concretes
     etc.), areal load q = thickness x density x g, automated from the
     chosen skin material + thickness slider; surfaced in the panel and
     wired so future analysis runs true q loads.
   - TWO LIBRARY FOLDERS to keep it simple: one for skin materials, one
     for ground materials. Skin: no ground materials, no timber
     stacking/sheets. Ground: concrete, gravel, ground/earth, maybe
     timber flooring, patio tiling (add more patio/tiling materials).
   - PER-VOUSSOIR MAPPING: the material maps to each voussoir, not the
     world (world scale is "usually way out of proportion"). One unit
     crop stretched to fit each voussoir face, "each face should be a
     clean texture" -- the QS Intelligence one-unit rule.
   - Randomise-UV button so voussoirs don't look aligned.
   - Bump amount slider (scale of relief).
   - Keep the old per-voussoir slight discolouration; add a slider for
     the amount of colour differentiation.
   - Fix: some materials don't apply on click and fall back to the
     default look (re-verify live post-stability; if any remain, fix the
     loader path).
   - 4K quality focus throughout.

4. GROUND MATERIAL CONTROLS. Ground stays world-tiled (NOT stretched per
   piece). Add: texture scale X and scale Y sliders (separate), a bump
   amount, and the randomise-UV button, alongside the existing floor
   size slider.

5. PROPS.
   - In-viewport EDIT MODE: select a placed prop, rotate and scale it;
     scaling anchored to the ground (grows from the base, never the
     centre).
   - A ton more tree assets (Poly Haven CC0 list researched: see
     scratchpad recon research-trees).
   - Many high-quality people assets if licences allow (research done:
     see recon research-people-buildings); maybe buildings.
   - 4K only; he loves the current quality.

6. VAULTED BRANDING. Logo for the desktop shortcut and a browser
   favicon: a vault design with small text underneath. The app is
   called Vaulted (tab title too).

7. CAMERA. Never below floor level; stays above.

## Standing constraints (unchanged)

Never write to the main worktree (VS code\COMPAS Workflow) or plugin\;
exporter-side asks go to REQUESTS-for-plugin-session.md; no em dashes
(use --); no AI attribution; commit locally per fix, git add by explicit
path, NEVER push; clash scan before test runs and commits; every new
test proved able to fail by mutation; full Windows paths in replies.

## Deferred from the earlier asset spec (unchanged)

KTX2/Basis, Draco, Frankot-Chellappa in JS, WebGPU switch, re-cutting
the 58 small one-unit crops from 8K sources.
