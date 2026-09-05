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

## The overnight Unreal harvest (2026-09-05, Param asleep)

State of the pipeline, kept honest as it runs:

- WORKS: headless UnrealEditor-Cmd + Python + the engine glTF exporter,
  driven per project (UE 5.4 at A:\unreal engine\UE_5.4 for
  Trees_Downloaded, 5.7 for tree_assets; GLTFExporter plugin enabled in
  both .uprojects). tools/props/ingest.mjs is the finishing line into
  props-hd (skin strip, slot-aware texture re-encode, budgets,
  manifest).
- LANDED: all 17 European Beech (Megascans, Fab Standard License) --
  seedlings 2.3 MB, saplings 3.7-7 MB, three forest canopies at
  118k-164k triangles ~9-10 MB, verified live beside the vault. The six
  BIGGEST beeches (Field_01, Forest_01-05) export at LOD0 only
  (default_level_of_detail is ignored on direct asset export; min_lod
  does not exist in 5.4 Python); the in-flight fix rebuilds LOD0 from
  the authored LOD1 in memory via
  EditorStaticMeshLibrary.set_lod_from_static_mesh, never saving.
- WALL, named: the 5.7 Megaplant species (Black Alder, Hornbeam, Norway
  Maple, Silver Birch, Hazel, Goat Willow...) are Nanite-ASSEMBLY
  skeletal meshes -- geometry exists only as Nanite assembly of branch
  parts, classic sections are empty ("-1 indices"), and BOTH glTF
  export paths (asset and spawned-actor selection) crash the engine
  natively on the first tree even with r.Nanite.AllowAssemblies=1.
  Not extractable tonight.
- THE UNLOCK for the morning: Fab serves engine-appropriate formats.
  The same species packs added to the UE 5.4 project (Trees_Downloaded)
  arrive as classic static meshes exactly like the beech pack did.
  Param: launcher > Fab library > Add to project (5.4) for Black Alder,
  Hornbeam, Norway Maple (and any others); then one export+ingest run.
- MetaHumans (MHC_Hannah, Mason, Skotukeda x2 in tree_assets): parked;
  characters are assembled skeletal + groom stacks, licence terms since
  the 2025 MetaHuman change permit use outside Unreal, but a posed
  static export needs an interactive session or a much longer harness.
  The posed-people ask ("standing, pointing, chatting") is registered.

## Overnight close (2026-09-05 ~02:30): where it ended

- LIBRARY: 110 props. 89 Poly Haven CC0 + 15 European Beech + 6
  Megascans statics (5 rock/terrain clusters, 1 broadleaf study tree),
  Fab Standard License, credited in NOTICE.txt. Verified in a composed
  live scene: beech canopy green behind the vault, rocks at the
  springing.
- BAKE HYGIENE learned the hard way (in ingest.mjs now): drop impostor
  billboards (textureless magenta, drew a black mass over the canopy);
  zero metallicFactor when no metallic texture came through.
- RIDERS still open: (1) beech Field_01 and Forest_02 export only at
  LOD0 (2-3.4M tris; all three LOD-selection APIs tried and defeated:
  default_level_of_detail ignored, min_lod absent in 5.4 Python,
  set_lod_from_static_mesh returns success without effect) -- next idea
  is duplicate-asset + remove-LOD0 or an FBX round trip; (2) posed
  MetaHuman people ("standing, pointing, chatting"); (3) eager prop
  template loading at boot now parses ~230 MB -- consider lazy
  templates.
- MORNING ERRAND for Param (2 minutes): Epic launcher > Fab library >
  add Black Alder, Hornbeam, Norway Maple (and any other species) to
  the UE 5.4 project Trees_Downloaded -- 5.4 delivery is classic static
  meshes, and the whole export+ingest pipeline is proven on them.

## The daytime wave (2026-09-05, after the trees)

- BLACK TREES, root-caused: the atlas was healthy; the RGB UNDER its
  transparent texels was black and mipmaps averaged it into every leaf.
  ingest.mjs inpaints hidden RGB (pull-push) before the palette encode.
  forest_03 dropped (canopy lost to forced full-res decimation);
  library 109.
- STALE PANEL FACES: restores write selects without change events by
  design; repaintSettingControls() (render-only) now runs after every
  silent writer, and choosing a sky in the drawer switches the
  environment to HDRI.
- HALF-TURN CLOSE: admireSeconds spans pi, on his word.
- CAMERA MENU: rail tab; FOV 15-100 with full-frame lens equivalent
  (f = 12/tan(v/2)); brightness/contrast moved in; frame presets Fill,
  16:9, 4:3, 1:1, 4:5, 9:16 letterboxed via canvas CSS (resize()
  derives everything from the canvas box); the recording renders at the
  chosen frame, longest side 1920. FOV+frame persist in scenes.
- LAYERS DRAWER: rows of prop groups; active layer receives new props;
  eye hides a set (and blocks picking); Duplicate stamps the group a
  step away on a fresh layer; rename on double-click; layered layout
  and scene persistence (old bare-array layouts still restore).
- Verified live over CDP: FOV 24 -> 56 mm, 1:1 letterbox 849x849,
  layer hide/pick-block/duplicate/persist all measured. 692 tests
  green; five new pin tests, each proved by mutation.

- LAYERS v2 (same day, on his walk): the drawer lists the placed
  OBJECTS under their layer rows -- click a name to select it in the
  viewport, tick boxes to gather, and the action button picks the set
  up as one rubber stamp: every click plants the whole group, Escape
  releases the copy in hand. Verified live: 3 plants of a 2-prop stamp
  = exactly 9 props, camera controls returned.

- LAYERS v3 (his walk again): the drawer is now a THUMBNAIL GRID of the
  open layer's placed objects (same preview tiles as the prop library),
  multi-select by clicking, Place copies stamps, Group to new layer
  moves the selection where it stands. Layers are TABS on the drawer's
  bottom edge: open tab receives new placements, eye hides, + adds,
  double-click renames. All rules verified live.

## 2026-09-05 -- THE REMOTE DOOR (tailnet access from any device)

His brief: "accessible from anywhere ... through any of my tailscale
devices"; then "A stop server button on the ui is needed too"; then
"install it as an app [on the laptop] ... it starts the server here and
then it opens up browser".

- FRONT DOOR: Tailscale Serve on this desktop, tailnet-only HTTPS:
  https://edwards-desktop.tailb66524.ts.net:8443/ -> 127.0.0.1:8600
  https://edwards-desktop.tailb66524.ts.net:8443/start -> 127.0.0.1:8611
  The app still binds loopback; nothing listens on LAN or internet. The
  old root entry on 443 (dead 18789 proxy) was left untouched. Config
  persists across reboots; disable with: tailscale serve --https=8443 off
- THE WAKER (launcher/waker.py): loopback-only stdlib server on 8611,
  run windowless by pythonw from the Startup folder ("Vaulted Waker.lnk").
  GET /start (or /, Serve may strip the mount) with the studio down
  spawns launch.ps1 -Quiet -NoBrowser (new switch) and returns a page
  that polls /api/health and location.replace("/")s when a real studio
  answers -- reply.ok AND health.studio, because the proxy answers 502
  for a dead server. 30 s spawn cooldown so a burst of knocks is one
  launch. Under pythonw one stderr write is fatal (serve.py's lesson):
  log_message is overridden to silence.
- STOP FROM THE PAGE: /api/stop mirrors /api/restart (reply first,
  schedule_stop exits a beat later via os._exit -- uvicorn's graceful
  path is unreachable and every write is atomic). The button sits beside
  Restart; success is health going QUIET, where "not ok" counts as quiet
  because through the proxy the connection never drops.
- CACHE TIERS: the flat no-store split three ways. App files: no-store
  (the stale-stylesheet fault stays closed). /static/vendor/: no-cache
  (kept, 304 to confirm). Heavy assets (props/hdri/materials/
  ground-materials prefixes, non-JSON answers only): public,
  max-age=3600, stale-while-revalidate=604800 -- props ARE replaced in
  place by ingests, so an hour of patience, not immutable.
- DESKTOP: Stop Vaulted.lnk beside Vaulted.lnk (shortcut.ps1 makes
  both now, and prints real paths instead of an undefined variable).
- LAPTOP: launcher/remote-shortcut.ps1 + vaulted.ico shipped over SSH
  to C:\Users\Param\Vaulted on edwards-laptop-1; desktop Vaulted.lnk
  opens Brave --app= on /start (Edge absent there; installer probes
  Edge/Brave/Chrome). Laptop fetch of /api/health over the tailnet:
  200 with a valid ts.net certificate.
- Verified live end to end through the proxy: restart onto the new
  build, cache headers as designed, POST /api/stop -> quiet, GET /start
  -> 200 waiting page -> studio back on a fresh pid; then the REAL
  button in a CDP page: status settled on "stopped", knock revived it.
  704 tests green; 11 new pins, all mutation-proved (one false-clean
  caught and closed: the spawn pin now demands QUOTED tokens because
  the docstring names the same switches).
- Riders: scenes are per-browser localStorage, so devices see their own
  scene lists (server-side sync is a future wave); touch was not
  exercised -- the UI is pointer-events based and should mostly work on
  iPad, but it was built for a mouse; a weak GPU may want a quality cap
  for 16k backdrops and 200k canopies.

## 2026-09-05 -- THE iPAD BOOT DEATH (lazy prop library)

His screenshot: tailnet page on the iPad, banner "The studio stopped
setting itself up. Script error..", toast stuck at "cutting Concrete
C30/37...", panel half-built.

- DIAGNOSIS TRAIL: tip WebKit (Playwright webkit-2359) boots the studio
  with ZERO errors; a 3-agent sweep found NO Safari-gated constructs in
  the app's own scripts; the diagnostics log had no row from the iPad
  (its report died with the tab); the bundle is only 17.8 MB. What
  remained: the EAGER PROP BOOT -- all 109 GLBs, 241 MB, parsed while
  the vault was still cutting. An iOS tab gets a fraction of a desktop's
  memory; allocations start failing anywhere, module errors surface as
  WebKit's muted "Script error.", and in-flight fetch bodies (the
  report) are dropped.
- LAZY LIBRARY: boot = manifest + .thumb.png snapshots (~3 MB total).
  ensurePropTemplate(key) loads a model the first time something needs
  its geometry (tile click, layout restore, scene apply -- each path
  wired), deduped by a promise map whose failures STAY failed (a cleared
  promise would be re-asked-for on every restoreProps re-run, forever).
  Scene apply Promise.alls its cast before placing any.
- SNAPSHOTS: tools/props/snap_thumbs.py (with tools/props/cdp.py)
  renders 256px previews against the running desktop studio; files land
  beside the GLBs, gitignored like them, served through /api/props/ with
  the heavy cache tier and a proper image/png (the route called
  everything glTF; sniffing hid it). Rerun after adding/re-ingesting
  props; a prop without a snapshot falls back to a live geometry load
  for its tile.
- FOUND ON THE WAY: preview rig far plane is 20 (material ball); big
  props (cliffs, 20 m beeches -- 16 of 109) framed from beyond it came
  out empty squares; the frustum now follows the framing and goes back.
- REPORTER: sendBeacon first (built for dying pages), fetch fallback;
  context built in its own try (module-eval errors reach the reporter
  before `state` exists); index.html banner also hears
  unhandledrejection until window.__studioReady.
- Verified live: fresh boot fetches 0 GLBs; opening the drawer fetches
  109 thumbs; one tile click fetches exactly one GLB; __studioReady
  true; thumbs over the tailnet are image/png with the heavy tier.
  711 tests green; 8 new pins mutation-proved (two false-cleans caught:
  a comment satisfying the .thumb.png pin, a docstring satisfying the
  spawn-switch pin).
- QUEUED (his word, 2026-09-05): plotly is installed and wanted for the
  ANALYSIS side of the web app -- charts for the analysis panel.

## 2026-09-05 -- START FROM THE PAGE, FOOTER ON THE FLOOR, DEVICE FIT

His asks: "if i stop the server we need a ztart server too"; footer
"always... on the bottom of the banner not on the bottom of the menus";
"make the ui fit these different devices better".

- START SERVER: hidden button beside Stop, revealed exactly when
  "stopped" lands (Stop hides itself). Click knocks the waker TWICE --
  same-origin /start (tailnet pages) and http://127.0.0.1:8611/start
  no-cors (the desktop page, whose own origin is dead) -- reads neither
  answer, then polls its own /api/health for a real studio (health.ok
  AND health.studio; a proxy 502 or the waker page must not trigger it)
  and location.reload()s onto the fresh build. Waker cooldown folds the
  double knock into one launch. The offline pin now exempts
  http://127.0.0.1 -- loopback is not the network.
- FOOTER: #panel is a flex column (children flex-shrink 0), #mode-row
  margin-top auto -- short sections drop the mode row + panel foot to
  the banner's true bottom; overflow keeps the old sticky behaviour.
- DEVICE FIT (first pass): @media (pointer: coarse) raises the footer
  buttons to 32px and pads shelf/layer tabs; @media (max-width: 1000px)
  centres the drawer in the space LEFT of the panel
  (calc((100vw - var(--panel-w)) / 2)); every backdrop-filter carries
  -webkit- for iOS. The fuller adaptive pass (portrait phones,
  collapsible panel) is QUEUED on his direction.
- HIS 14:18 iPad screenshot decoded: the vault RENDERED (lazy library
  works there); the banner + broken material tiles came from my own
  server restarts colliding with his attempt -- the page's log showed
  "request refused 502: /api/studies", the proxy speaking for a server
  that was mid-bounce. Not a client fault.
- Verified live through the tailnet: stop -> "stopped", Stop hidden,
  Start shown, server measured down; Start click -> waker spawned ->
  studio back on a fresh pid -> the page reloaded ITSELF onto the new
  build. Footer screenshot shows the rows pinned to the panel's floor.
  714 tests green, 4 new pins mutation-proved (4/4 kills).

## 2026-09-05 -- TOUCH-DEVICE PERFORMANCE (his report: slow materials,
## silver props on the iPad; "not a huge priority... would be nice")

- CAUSE CHAIN: VIEWPORT_PX 0 = MASTER tier, five maps per material
  change; iPad decodes+uploads seconds' worth and iOS sheds texture
  uploads under GPU memory pressure -- silver/untextured props are that
  shedding, "mesh being wrong" likely the same pressure or a context
  loss. DPR 2 = 3200x2400 canvas doubled the shading cost besides.
- SHIPPED (e2a1a85): pbr.js CONSTRAINED_DEVICE (maxTouchPoints > 1;
  iPadOS masquerades as a Mac) -> VIEWPORT_PX 1024 on touch, master on
  desktop; renderer DPR capped at 1.5 on touch; webglcontextlost files
  a diagnostics report; every report carries device numbers (touch,
  dpr, maxTextureSize, UA). Desktop path byte-identical in behaviour.
- QUEUED (needs his on-device evidence, now instrumented): if silver
  props persist on the iPad, read bench/studio/diagnostics.log for
  context-loss rows and the device block; candidate next steps are a
  constrained-device prop texture tier (ingest already bakes 1024) and
  capping the environment/backdrop sizes on touch.

## 2026-09-05 -- FOLD HANDLE, SHELF PLAY, NO-JUMP TAKES

His asks: "a little tile arrow attached to the mid left side of the
banner... collapse... pressed again to open"; "add a play button next
to the scene tile"; "when i start the animation the viewport jumps
slightly and changes its camera lens size".

- FOLD: #panel-collapse, a fixed sibling at right: var(--panel-w),
  top 50% (the panel's overflow scroll would clip a child outside its
  box). body.panel-collapsed moves everything on CSS alone: panel
  translateX(100%), tab rail opacity 0 + pointer-events none, handle
  rides to right: 0, event log frees the band. Arrow reverses
  (open shows a right-pointing chevron, collapsed a left-pointing one); choice persists in
  localStorage "panel-collapsed". Live: panel left edge measured AT the
  viewport edge folded, back at 1224 reopened, survives reload.
- SHELF PLAY: #shelf-play beside the Scenes tab, delegating to
  #play-button's click; paintPlayButtons() is the ONE label painter
  (every direct textContent write replaced; pin forbids new ones); tab
  wiring scoped to #shelf-tabs button[data-shelf] in all three query
  sites or the newcomer would openShelf(undefined).
- NO-JUMP: captureOrbitBase centres on controls.target.clone() (stored
  as base.centre; applyTimeline uses base.centre || state.centre).
  lookAt(state.centre) on the first played frame was the jump AND the
  perceived lens change. Measured with a deliberately panned camera:
  quaternion delta 0.0, fov 45 -> 45, labels flip together both ways.
- 718 tests green; pins mutation-proved (5 kills; one mutation misfired
  on indent and was re-proved properly). The old take-orbit pin updated
  to the deeper version of the same ruling: the framing IS the shot,
  including its aim.

## 2026-09-05 -- THE JUMP'S SECOND CAUSE, TRANSPORT ICONS, SHELL ALONE

His reports: "it still did it though, where it jumped slightly";
"change the tiles for play to the play icon, a restart icon and a
record icon all lines up there"; "when i press the shell button... it
shows the columns too".

- THE GLIDE: OrbitControls damping keeps applying leftover drag inertia
  through the render loop's unconditional controls.update(), on top of
  the turntable's pinned orbit -- the jump that survived the re-aim
  fix. settleControls() (damping off, one update, damping back) flushes
  the leftovers before EVERY capture (startPlaying, recordAnimation,
  drag-end mid-take), and frame() skips controls.update() while
  turntableOwns (playing && orbitBase && autoSpin && !userDragging).
  Measured with a real synthetic drag then play: pos and aim drift 0.0
  over 0.9 s.
- TRANSPORT ICONS: #shelf-play (triangle at rest / pause bars playing, painted by
  paintPlayButtons), #shelf-restart (clockwise arrow), #shelf-record (dot, tinted) --
  square .shelf-act tiles beside the drawer tabs, each delegating to
  the real control (play-button/restart-button/record-button clicks).
  NOTE the glyphs in studio.js are literal characters, not escapes.
- SHELL ALONE: formworkVisibility's rest branch returns columnMesh
  false for showMode "shell" -- the columns are the machine's, and
  Shell shows no machine. Node test extended (shell hides, framework
  keeps); verified live on Column diagnosis: Shell False, Both True.
- 719 tests green; 4 fresh mutation kills; three stale pins updated to
  the new truths (restart slice needed .addEventListener anchoring now
  that a delegate mentions the same id earlier in the file).
