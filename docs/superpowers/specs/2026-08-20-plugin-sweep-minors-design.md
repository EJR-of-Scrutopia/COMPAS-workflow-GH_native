# Plugin sweep minors: the parked C# findings, closed

Date: 2026-08-20. The 2026-08-18 review sweep parked six plugin
findings (recorded in the UI repo's
.superpowers/sdd/2026-08-18-review-sweep/parked.md, Plugin section);
Param's standing word "keep going on the next fixes" reaches them now
that the studio register is closed. Branch fix/plugin-sweep-minors off
plugin main 30a5a78 (pushed). One batch task: every item is a small,
same-shape change in plugin/native_v02.

## The six findings, with dispositions

1. Courses bounds validation (the one correctness item): negative
   course values pass through Export's Tessellation format into
   "c-1p0"-style keys -- which the STUDIO then refuses on import
   (from_document pins course >= 0), so the failure is late, remote,
   and confusing. FIX: ExportComponent validates the Courses list
   before writing -- any negative value is a component ERROR
   (AddRuntimeMessage Error, no file written) naming the offending
   indices and values; non-integer handling follows however the input
   is typed today (read the code). A matching guard in the Armadillo
   Dual component is NOT needed (its CO output is a band index built
   non-negative by construction) -- verify that claim by reading
   armadillo_dual.py's course construction and STATE it in the report.
2. BuildTessellationJson uses default JsonSerializer options instead
   of the shared ContractJson.Options: FIX to the shared options (no
   functional difference today; consistency prevents a future
   divergence). Confirm output bytes unchanged on the existing
   fixtures (the native_smoke harness or a unit test).
3. ExportComponent.SolveInstance lacks the local try/catch its
   siblings have (GH catches at framework level with an uglier
   message): FIX to sibling parity -- read how FdSolve/Deconstruct
   wrap SolveInstance and mirror it exactly.
4. The closing-duplicate check can leave a near-duplicate final vertex
   when IsClosed is true but the 1e-9 approximation misses: FIX the
   check to tolerance-compare first-vs-last (the same 1e-9 the dedupe
   uses) rather than exact equality -- read the current code first;
   if it already tolerance-compares and the finding is about a
   different path, fix THAT path and say so.
5. FacePolylines/FaceCourses duplicate the centroid/corner loop
   inline: FIX by extracting the shared helper (pure refactor, no
   behaviour change -- the native_smoke Deconstruct contract must
   pass unchanged).
6. No dedicated tests for the new plugin code paths: FIX proportionally
   -- unit tests where the existing C#-side test pattern reaches
   (find what tests/ carries for component-level code; if C# unit
   tests do not exist as a pattern in this repo, the native_smoke
   harness IS the test seam: extend it to cover the Courses error
   path and the tessellation JSON options if it can, and SAY exactly
   what coverage the repo's own patterns allow).

## Acceptance

- `dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c
  Release` with 0 warnings (the repo's standing bar).
- The python worker suite untouched and green: `.venv/Scripts/python.exe
  -m pytest tests -q` from the repo root (236 passed 1 skipped
  baseline).
- The native_smoke harness passes: `dotnet run --project
  tests/native_smoke -- plugin/native_v02/bin/Release/net8.0-windows/
  Ananke.COMPAS.gha` (read its README/usage in the repo first).
- .gha REBUILT at the end; INSTALL PENDING (Rhino state unknown --
  do NOT run Build-And-Install.ps1; the controller handles the
  install cycle with Param).
- No em dashes (U+2014); no AI attribution; explicit-path commits;
  NEVER push.

## Out of scope

Any new component behaviour; the worker algorithm; the 6c deferrals
(component-side plan-degenerate filtering, bench.tessellation/2).
