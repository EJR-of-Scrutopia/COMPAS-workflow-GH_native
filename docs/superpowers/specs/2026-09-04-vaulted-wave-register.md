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
