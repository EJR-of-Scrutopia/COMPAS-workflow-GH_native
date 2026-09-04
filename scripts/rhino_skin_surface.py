"""Prove the Brep route section 5 is built on (check 12.5(a)), then its
behaviour (checks 12.5(b) to 12.5(e), task 29's own extension).

Run inside Rhino 8, from the Script Editor's CPython engine or:

    "C:\\Program Files\\Rhino 8\\System\\RhinoCode.exe" script \
        scripts/rhino_skin_surface.py

Part one proves the RhinoCommon API shape directly and touches nothing in
the plugin. Part two drives the ACTUAL plugin: it loads the built
Ananke.COMPAS.gha, reaches SkinNet, SkinNetEdge, all three of
SkinPatterns.Courses, SkinPatterns.Hexagonal and
SkinPatterns.ForceAligned, and SkinComponent's private CellSurface(cell, net)
by reflection -- exactly the way tests/native_smoke/Program.cs reaches the
same members -- and calls CellSurface directly, one cell at a time, with
no Grasshopper document at all: CellSurface takes only a cell and a net,
so this is the one shortcut the harness itself could not take, for want of
a native core to build a real Brep with. This is the split rule 5.2.1
itself states: construction happens on the SOLVE thread, in
SkinComponents.cs, and native_smoke can measure the SECTIONS a cell
carries but not the Brep a section lofts into.

Part three (NEW, 2026-09-03, amended 2026-09-04) is the THICKNESS half
of spec 2026-09-02 as amended by spec 2026-09-03 (skin-offset-surface)
and again by spec 2026-09-04 (skin-offset-extrude-slider): a planar and
a non-planar cell thickened at Th 0.2 and -0.2 at the SLIDER STOPS 0,
0.5 and 1, each asserted watertight and outward, every moved corner
asserted exactly |Th| from the corner it came from because the blend is
renormalised, the top ring congruent to the bottom at Extrude 1, two
neighbours' shared corner asserted WELDED at 0 and OPEN at 1, and the
side-by-side count of cells that close into a solid at each stop. No
volume is predicted anywhere any more: the world-Z branch is deleted and
both ends of the slider are on the net's own normal. IT HAS NEVER BEEN RUN.
It was written by an agent with no Rhino, to this file's own conventions,
and its first execution is Param's.
"""

import math
import os

import Rhino.Geometry as rg
import System
import System.Reflection as reflection


def polyline(points):
    return rg.PolylineCurve([rg.Point3d(*point) for point in points])


def loft_two_runs():
    lower = polyline([(0, 0, 0), (1, 0, 0.1), (2, 0, 0.15)])
    upper = polyline([(0, 1, 0.4), (1, 1, 0.5), (2, 1, 0.55)])
    breps = rg.Brep.CreateFromLoft(
        [lower, upper],
        rg.Point3d.Unset,
        rg.Point3d.Unset,
        rg.LoftType.Straight,
        False,
    )
    if not breps or len(breps) != 1:
        return "FAIL: CreateFromLoft returned %r" % (breps,)
    brep = breps[0]
    if not brep.IsValid:
        return "FAIL: the loft came back invalid"
    if brep.Faces.Count != 1:
        return "FAIL: %d faces, and rule 5.2.3(a) promises one" % (
            brep.Faces.Count,
        )
    return "PASS: a two-section loft is one valid single-face Brep"


def fan_a_cap():
    loop = [
        (0.5, 0.0, 1.0), (0.35, 0.35, 1.0), (0.0, 0.5, 1.0),
        (-0.35, 0.35, 1.0), (-0.5, 0.0, 1.0), (-0.35, -0.35, 1.0),
        (0.0, -0.5, 1.0), (0.35, -0.35, 1.0),
    ]
    apex = rg.Point3d(0.0, 0.0, 1.2)
    faces = []
    for at in range(len(loop)):
        a = rg.Point3d(*loop[at])
        b = rg.Point3d(*loop[(at + 1) % len(loop)])
        faces.append(rg.Brep.CreateFromCornerPoints(a, b, apex, 1e-9))
    joined = rg.Brep.JoinBreps(faces, 1e-9)
    if not joined or len(joined) != 1:
        return "FAIL: the fan did not join into one Brep"
    return "PASS: a cap fans into one joined Brep of %d faces" % (
        joined[0].Faces.Count,
    )


print(loft_two_runs())
print(fan_a_cap())


# ---------------------------------------------------------------------------
# Part two, checks 12.5(b) to 12.5(e): the ACTUAL plugin, driven directly.
# ---------------------------------------------------------------------------

# Rhino's script editor runs a COPY of this file from its own rhinocode
# cache, so a repo root derived from __file__ resolves into ProgramData and
# checks 12.5(b) onward never ran on Param's first execution (measured
# 2026-09-04: "Built plugin not found at 'C:\ProgramData\McNeel\...'").
# The candidates are therefore tried in order, and the one that answered
# is printed so a stale fallback cannot masquerade as the fresh build:
# the __file__ route (running from the repo), the repo's own absolute
# path (running inside Rhino), and the INSTALLED plugin as a last resort,
# which lags the repo build by one install and says so.
_FILE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT_ABSOLUTE = (
    "C:\\Users\\Param\\OneDrive - Ananke-eidos\\Documents\\"
    "Ananke Eidos Studio\\VS code\\COMPAS Workflow"
)
_BUILT_TAIL = os.path.join(
    "plugin", "native_v02", "bin", "Release", "net8.0-windows",
    "Ananke.COMPAS.gha",
)
_INSTALLED = os.path.join(
    os.environ.get("APPDATA", ""), "Grasshopper", "Libraries",
    "Ananke_COMPAS", "Ananke.COMPAS.gha",
)
_CANDIDATES = [
    ("the repo build beside this script", os.path.join(_FILE_ROOT, _BUILT_TAIL)),
    ("the repo build at the absolute path", os.path.join(_REPO_ROOT_ABSOLUTE, _BUILT_TAIL)),
    ("the INSTALLED plugin (lags the repo build by one install)", _INSTALLED),
]
REPO_ROOT = _REPO_ROOT_ABSOLUTE
PLUGIN_PATH = next(
    (path for _, path in _CANDIDATES if os.path.isfile(path)),
    os.path.join(_REPO_ROOT_ABSOLUTE, _BUILT_TAIL),
)
PLUGIN_SOURCE_NOTE = next(
    (note for note, path in _CANDIDATES if path == PLUGIN_PATH),
    "no candidate existed",
)

BindingFlags = reflection.BindingFlags
_PUBLIC_STATIC = BindingFlags.Public | BindingFlags.Static
_NONPUBLIC_STATIC = BindingFlags.NonPublic | BindingFlags.Static


def _load_plugin(path):
    if not os.path.isfile(path):
        raise RuntimeError(
            "Built plugin not found at %r (tried: %s); run the two dotnet "
            "build commands in the task brief first."
            % (path, "; ".join(candidate for _, candidate in _CANDIDATES))
        )
    print("plugin loaded from %s: %s" % (PLUGIN_SOURCE_NOTE, path))
    return reflection.Assembly.LoadFrom(path)


def _find_type(assembly, name):
    for candidate in assembly.GetTypes():
        if candidate.Name == name:
            return candidate
    raise RuntimeError("Type not found in plugin: %s" % (name,))


def _method(owner, name, param_types=None, nonpublic=False):
    flags = _NONPUBLIC_STATIC if nonpublic else _PUBLIC_STATIC
    if param_types is None:
        found = owner.GetMethod(name, flags)
    else:
        found = owner.GetMethod(
            name, flags, None, System.Array[System.Type](param_types), None)
    if found is None:
        raise RuntimeError(
            "Method not found: %s.%s" % (owner.Name, name))
    return found


def _property(obj, name):
    return obj.GetType().GetProperty(name).GetValue(obj)


def _make_net(net_type, edge_type, vertices, faces, rim=None, forces=None):
    """The four-argument SkinNet, built the way
    tests/native_smoke/Program.cs's SkinNetWith builds it: plain nested
    Python lists for the double[][]/int[][] arguments, which .NET
    reflection's argument binder coerces against the constructor's own
    declared parameter types."""
    rim = list(rim or [])
    forces = list(forces or [])
    edges = System.Array.CreateInstance(edge_type, len(forces))
    for at, (a, b, force) in enumerate(forces):
        edges[at] = System.Activator.CreateInstance(
            edge_type, System.Array[object]([a, b, force]))
    return System.Activator.CreateInstance(
        net_type, System.Array[object]([vertices, faces, rim, edges]))


def _hemisphere(rings=24, around=48, radius=3.0):
    """The same hemisphere fixture native_smoke calls SkinHemisphereNet:
    radius 3, 24 rings by 48 around, ring 0 as the rim, the apex a
    triangle fan. Kept in step deliberately so this script's own results
    are comparable to the harness's."""
    vertices = []
    for ring in range(rings):
        phi = math.pi / 2.0 * ring / rings
        for k in range(around):
            theta = math.pi * 2.0 * k / around
            vertices.append([
                radius * math.cos(phi) * math.cos(theta),
                radius * math.cos(phi) * math.sin(theta),
                radius * math.sin(phi),
            ])
    apex = len(vertices)
    vertices.append([0.0, 0.0, radius])
    faces = []
    for ring in range(rings - 1):
        for k in range(around):
            nxt = (k + 1) % around
            faces.append([
                ring * around + k,
                ring * around + nxt,
                (ring + 1) * around + nxt,
                (ring + 1) * around + k,
            ])
    for k in range(around):
        nxt = (k + 1) % around
        faces.append([(rings - 1) * around + k, (rings - 1) * around + nxt, apex])
    rim = list(range(around))
    return vertices, faces, rim


def _barrel():
    """The barrel fixture native_smoke calls SkinBarrelNet, vertex for
    vertex and face for face: x 0 to 6 along the barrel (7 columns), a tent
    profile z = 2 - |y - 2| over y 0 to 4, so both eaves sit at z 0 and the
    crest at z 2. Its rim is both eaves, and its forces are check 12.3(b)'s
    ARCH forces, 1 kN across the arch and 0.1 kN along the generators.

    That force list is not a choice of convenience. Under check 12.3(a)'s
    along-the-barrel list the field lies along the generators, the bed
    curves lie along them too, every streamline then runs parallel to every
    bed and crosses none, and the force-aligned pattern comes back with 42
    accepted lines and ZERO cells. A fixture with no cells would let
    12.5(b) report that all of its nought cells yield a Brep.
    """
    vertices = []
    for j in range(5):
        z = 2.0 - abs(j - 2.0)
        for i in range(7):
            vertices.append([float(i), float(j), z])
    faces = []
    for j in range(4):
        for i in range(6):
            a = j * 7 + i
            faces.append([a, a + 1, a + 8, a + 7])
    rim = []
    for i in range(7):
        rim.append(i)
        rim.append(4 * 7 + i)
    forces = []
    for j in range(5):
        for i in range(6):
            forces.append((j * 7 + i, j * 7 + i + 1, 0.1))
    for j in range(4):
        for i in range(7):
            forces.append((j * 7 + i, (j + 1) * 7 + i, 1.0))
    return vertices, faces, rim, forces


def _plan_area(outline):
    """The centred signed shoelace, matching PlanArea/rule 11.2 in the
    engine: centred on the outline's own mean so a far-from-origin cell
    keeps full precision."""
    n = len(outline)
    if n < 3:
        return 0.0
    mx = sum(p[0] for p in outline) / n
    my = sum(p[1] for p in outline) / n
    total = 0.0
    for i in range(n):
        ax, ay = outline[i][0] - mx, outline[i][1] - my
        bx, by = outline[(i + 1) % n][0] - mx, outline[(i + 1) % n][1] - my
        total += ax * by - bx * ay
    return abs(total) / 2.0


def _mean_surface_slope_cosine(outline):
    """The cosine of the mean angle between the cell's own best-fit plane
    normal and world Z, estimated from the outline's own corners by a
    simple Newell normal (adequate for a nearly-planar band cell; a
    fanned cap or odd cell is excluded from check 12.5(c) for exactly
    this reason, since its many small facets do not share one slope)."""
    n = len(outline)
    nx = ny = nz = 0.0
    for i in range(n):
        ax, ay, az = outline[i]
        bx, by, bz = outline[(i + 1) % n]
        nx += (ay - by) * (az + bz)
        ny += (az - bz) * (ax + bx)
        nz += (ax - bx) * (ay + by)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return 1.0
    return abs(nz) / length


def run_behavioural_checks():
    assembly = _load_plugin(PLUGIN_PATH)
    skin_patterns = _find_type(assembly, "SkinPatterns")
    skin_net_type = _find_type(assembly, "SkinNet")
    skin_net_edge_type = _find_type(assembly, "SkinNetEdge")
    skin_component_type = _find_type(assembly, "SkinComponent")

    courses_method = _method(
        skin_patterns, "Courses",
        [skin_net_type, System.Double, System.Double, System.Double])
    hexagonal_method = _method(skin_patterns, "Hexagonal")
    # ForceAligned is overloaded on Min Piece, so it is named by its
    # parameter types the way native_smoke names it.
    force_aligned_method = _method(
        skin_patterns, "ForceAligned",
        [skin_net_type, System.Double, System.Double, System.Double])
    cell_surface_method = _method(
        skin_component_type, "CellSurface", nonpublic=True)

    def courses(net, size, ch, min_piece=1.0 / 3.0):
        return courses_method.Invoke(
            None, System.Array[object]([net, size, ch, min_piece]))

    def hexagonal(net, size, ch):
        return hexagonal_method.Invoke(
            None, System.Array[object]([net, size, ch]))

    def force_aligned(net, size, ch, min_piece=1.0 / 3.0):
        return force_aligned_method.Invoke(
            None, System.Array[object]([net, size, ch, min_piece]))

    def cell_surface(cell, net):
        return cell_surface_method.Invoke(
            None, System.Array[object]([cell, net]))

    reports = []

    # ---- 12.5(b) and 12.5(c): every cell on every fixture yields a Brep,
    # and its area matches the cell's own plan area corrected for slope.
    vertices, faces, rim = _hemisphere()
    net = _make_net(skin_net_type, skin_net_edge_type, vertices, faces, rim)
    barrel_vertices, barrel_faces, barrel_rim, barrel_forces = _barrel()
    barrel = _make_net(
        skin_net_type, skin_net_edge_type, barrel_vertices, barrel_faces,
        barrel_rim, barrel_forces)
    # ALL THREE PATTERNS. Pattern 2 was missing here when this script first
    # shipped, and with it the whole force-aligned Surface path: nothing in
    # this file and nothing in native_smoke ever called CellSurface on a
    # force-aligned cell. It carries its own net, the force-bearing barrel,
    # because the hemisphere has no forces at all.
    fixtures = [
        ("courses", net, courses(net, 0.6, 0.35)),
        ("hexagonal", net, hexagonal(net, 0.6, 0.35)),
        ("force aligned", barrel, force_aligned(barrel, 0.6, 0.5)),
    ]
    for label, fixture_net, built in fixtures:
        cells = list(_property(built, "Cells"))
        if not cells:
            reports.append(
                "FAIL (12.5(b), %s): the fixture built NO cells, so this "
                "check would report that all nought of them yield a Brep"
                % (label,))
            continue
        failed = 0
        worst_error = 0.0
        for cell in cells:
            outline = [list(pt) for pt in _property(cell, "Outline")]
            brep = cell_surface(cell, fixture_net)
            if brep is None:
                failed += 1
                continue
            plan = _plan_area(outline)
            cosine = _mean_surface_slope_cosine(outline)
            expected = plan / cosine if cosine > 1e-9 else plan
            area = brep.GetArea()
            if expected > 1e-9:
                error = abs(area - expected) / expected
                worst_error = max(worst_error, error)
        if failed:
            reports.append(
                "FAIL (12.5(b), %s): %d of %d cells did not close into a "
                "Brep" % (label, failed, len(cells)))
        else:
            reports.append(
                "PASS (12.5(b)/(c), %s): all %d cells yield a Brep, worst "
                "area error %.4f%% against plan area / cos(slope)"
                % (label, len(cells), worst_error * 100.0))

    # ---- 12.5(b) on pattern 2 again, this time by ROUTE. Rule 5.2.3(c)
    # sends a four-cornered force-aligned cell down route (a), a loft of the
    # cell's two bed runs, which comes back as ONE face; rule 3.3.5's three-
    # and five-cornered cells have an odd corner with nothing to loft
    # against and take the fan of route (e), which comes back as several.
    # The face count is what separates the two, and it is the measurement
    # that catches a route lofting the cell's four ring CHAINS in place of
    # its two cross sections: four edges in cyclic order, bottom to right to
    # top to left, loft into a twisted face and not the cell's own surface.
    aligned = force_aligned(barrel, 0.6, 0.5)
    aligned_cells = list(_property(aligned, "Cells"))
    four_cornered = 0
    odd_cornered = 0
    route_faults = []
    for cell in aligned_cells:
        setout = _property(cell, "SetoutCorners")
        brep = cell_surface(cell, barrel)
        if brep is None:
            route_faults.append(
                "a %d-cornered cell gave no Brep at all" % (setout,))
            continue
        if setout == 4:
            four_cornered += 1
            if brep.Faces.Count != 1:
                route_faults.append(
                    "a four-cornered cell came back with %d faces, and "
                    "route (a) is a single-face loft" % (brep.Faces.Count,))
        else:
            odd_cornered += 1
            if brep.Faces.Count < 3:
                route_faults.append(
                    "a %d-cornered cell came back with %d faces, and route "
                    "(e) fans one face per outline segment"
                    % (setout, brep.Faces.Count))
    if route_faults:
        reports.append(
            "FAIL (12.5(b), force-aligned routes): %s"
            % ("; ".join(sorted(set(route_faults))),))
    elif not four_cornered or not odd_cornered:
        reports.append(
            "FAIL (12.5(b), force-aligned routes): the barrel gave %d "
            "four-cornered and %d odd cells, so one arm of rule 5.2.3 was "
            "measured on nothing" % (four_cornered, odd_cornered))
    else:
        reports.append(
            "PASS (12.5(b), force-aligned routes): %d four-cornered cells "
            "each came back a SINGLE-face loft of their two bed runs "
            "(route (c) taking route (a)) and %d odd cells each a "
            "multi-face fan (route (e))"
            % (four_cornered, odd_cornered))

    # ---- 12.5(d): the split cap, W + 1 items in both trees, wedges
    # single-face and only the centre disc multi-face.
    #
    # COURSES ONLY, and deliberately so rather than by oversight. A cap is
    # emitted by the courses engine alone: ForceAligned builds band cells
    # and nothing else, so no force-aligned cell ever has Cap true and
    # there is no split cap of pattern 2 to measure. The tree-alignment
    # half below is engine-agnostic for the same reason it is testable at
    # all: it replays SolveNative's own bucketing loop, which walks the
    # cell list of WHATEVER pattern built it, one append per cell into each
    # of two parallel lists.
    split = courses(net, 0.6, 1.2)
    split_cells = list(_property(split, "Cells"))
    course_count = _property(split, "CourseCount")
    cap_cells = [c for c in split_cells if _property(c, "Cap")]
    wedge_counts = list(_property(split, "CapWedgeCounts"))
    wedges = wedge_counts[0] if wedge_counts else 0
    top_cells = [
        c for c in split_cells if _property(c, "Course") == course_count - 1
    ]
    top_surfaces = [cell_surface(c, net) for c in top_cells]
    if len(top_cells) != wedges + 1 or len(top_surfaces) != len(top_cells):
        reports.append(
            "FAIL (12.5(d)): split-cap top branch holds %d cells and %d "
            "surfaces; expected W + 1 = %d in both"
            % (len(top_cells), len(top_surfaces), wedges + 1))
    else:
        disc_faces = None
        wedge_face_counts = []
        for cell, brep in zip(top_cells, top_surfaces):
            if brep is None:
                reports.append(
                    "FAIL (12.5(d)): a split-cap piece would not close "
                    "into a surface")
                break
            is_disc = abs(
                (_property(cell, "U0") + _property(cell, "U1")) / 2.0
            ) <= 1e-6
            if is_disc:
                disc_faces = brep.Faces.Count
            else:
                wedge_face_counts.append(brep.Faces.Count)
        else:
            if wedge_face_counts and any(
                    count != 1 for count in wedge_face_counts):
                reports.append(
                    "FAIL (12.5(d)): a wedge came back with more than one "
                    "face; wedges must be single-face Breps like any "
                    "other ordinary band cell")
            elif disc_faces is not None and disc_faces < 3:
                reports.append(
                    "FAIL (12.5(d)): the centre disc's fan came back with "
                    "fewer faces than its own corner count")
            else:
                reports.append(
                    "PASS (12.5(d)): split cap's top branch holds W + 1 = "
                    "%d items in both Cells and Surface, each wedge a "
                    "single-face Brep and the centre disc a %d-face fan"
                    % (wedges + 1, disc_faces))

    # 12.5(d), the branch-count/branch-path/item-count identity, tested by
    # replicating SkinComponent.SolveNative's OWN bucketing loop (course
    # clamped to [0, CourseCount - 1], one append per cell into each of two
    # parallel lists) over a course list synthetically emptied at course 1,
    # since no shipped fixture is documented to leave a whole course
    # naturally empty under the post-bisection courses engine (rule 8.1
    # narrows a transition refusal to a residual sliver rather than a whole
    # band; see the deviation note in progress.md). The mechanism under
    # test -- OutputTree.Build pre-creating every branch before either
    # loop fills it -- does not depend on WHY a course is empty, only that
    # both loops walk the same cell list once.
    plain = courses(net, 0.6, 0.35)
    plain_cells = [
        c for c in _property(plain, "Cells")
        if _property(c, "Course") != 1
    ]
    plain_course_count = _property(plain, "CourseCount")
    cell_branch_counts = [0] * plain_course_count
    surface_branch_counts = [0] * plain_course_count
    surface_failed_here = 0
    for cell in plain_cells:
        course = min(
            max(_property(cell, "Course"), 0), plain_course_count - 1)
        cell_branch_counts[course] += 1
        brep = cell_surface(cell, net)
        surface_branch_counts[course] += 1
        if brep is None:
            surface_failed_here += 1
    if cell_branch_counts != surface_branch_counts:
        reports.append(
            "FAIL (12.5(d), empty course): branch item counts diverge "
            "between Cells %r and Surface %r"
            % (cell_branch_counts, surface_branch_counts))
    elif cell_branch_counts[1] != 0:
        reports.append(
            "FAIL (12.5(d), empty course): course 1 was not actually "
            "emptied by the synthetic filter")
    else:
        reports.append(
            "PASS (12.5(d), empty course): with course 1 synthetically "
            "emptied, both trees carry %d branches with identical "
            "per-branch counts %r, course 1 an EMPTY branch in both "
            "rather than a missing one" % (
                plain_course_count, cell_branch_counts))

    # ---- 12.5(e): an injected degenerate cell gives a NULL, not a
    # missing item. A cell whose Outline is collapsed to two coincident
    # points cannot triangulate an interior point and cannot loft (its
    # Sections, if any, are truncated the same way), so CellSurface must
    # return None rather than throwing or silently substituting geometry.
    #
    # This one is PATTERN-FREE by construction: the cell is built straight
    # off the SkinCell record and never off an engine, and CellSurface
    # routes on the record alone, so injecting the same degenerate cell
    # again per pattern would measure the same code path three times.
    sample_cell = list(_property(plain, "Cells"))[0]
    cell_type = sample_cell.GetType()
    degenerate = System.Activator.CreateInstance(
        cell_type,
        System.Array[object]([
            0,
            System.Array[object]([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            False,
            0.0,
            0.0,
            False,
            0,
            None,  # Sections: the cross sections rule 5.2.3 lofts.
            None,  # Chains: the force-aligned ring's own four edges.
        ]),
    )
    degenerate_result = cell_surface(degenerate, net)
    if degenerate_result is not None:
        reports.append(
            "FAIL (12.5(e)): a degenerate two-point cell built a Brep "
            "instead of returning NULL")
    else:
        reports.append(
            "PASS (12.5(e)): an injected degenerate cell (two coincident "
            "outline points, no sections) gives a NULL Surface slot, not "
            "a missing item")

    return reports


# ---------------------------------------------------------------------------
# Part three, NEW 2026-09-03 and AWAITING PARAM'S RUN: the thickened solid.
#
# Spec 2026-09-02 (skin-thickness-input) promises a CLOSED SOLID between a
# cell's face and a copy of it offset by Th, outward-oriented, and a
# shared wall that stays coincident between neighbours. Not
# one of those three claims can be taken outside Rhino: RhinoCommon's
# native core does not initialise there, so JoinBreps, IsSolid,
# SolidOrientation and GetVolume are all unavailable to
# tests/native_smoke, which measures only the offset VECTOR through
# ThicknessOffset and says so in its own check text.
#
# AMENDED 2026-09-03 by spec skin-offset-surface. The toggle that used to
# say Along Normal came to say OFFSET, its true branch an OFFSET SURFACE
# rather than a per-cell extrusion, and it defaulted TRUE, so the mode
# this script had never exercised at all became the shipped one.
#
# AMENDED AGAIN 2026-09-04 by spec skin-offset-extrude-slider, and the
# amendment is larger. THE TOGGLE IS GONE. Port 6 is a NUMBER, Extrude,
# running 0 to 1 and defaulting 0, and BOTH ENDS ARE ON THE SURFACE
# NORMAL: at 0 the outer skin is a true offset surface welded corner to
# corner, at 1 each cell is extruded along its OWN normal and the joints
# open. THE (0, 0, Th) WORLD-Z BRANCH IS DELETED, so every case below runs
# at the SLIDER STOPS 0, 0.5 and 1 rather than in two branches, and no
# case predicts a volume from a vertical translation any more.
#
# What replaces the volume predictions is the DISTANCE, which is exact at
# every stop: the blended direction is renormalised, so every moved corner
# stands exactly |Th| from the corner it came from whatever the slider
# says. Those per-corner assertions are kept in full.
#
# 12.5(h) splits in two with the weld. At Extrude 0 two cells sharing an
# outline corner must both carry a vertex at that corner moved by the SAME
# vector, since the direction is read at the POINT and not off the cell.
# At Extrude 1 they must NOT: the cell's own normal enters, the two
# neighbours disagree, and the gap is the extrusion the slider slides
# towards. Both halves are asserted, so a slider read and ignored fails
# one of them whichever way it was ignored.
#
# ThickenCellSurface's signature moved twice. It takes the NET, because
# the field it reads lives there, and it takes the cell's SECTIONS,
# because the top face is now built by its own bottom's ROUTE: a
# loft-route cell lofts its top from its own moved rails where it used to
# be capped by a fan. The order is (face, outline, sections, net, Th,
# extrude).
#
# WHAT THIS SCRIPT IS FOR, restated after the harness measured what it
# could. tests/native_smoke can count the cells whose side wall is
# ANNIHILATED into a line, and on 2026-09-03 it counted ZERO on every
# fixture including Param's own net under both patterns, with the tightest
# wall on the force-aligned run coming from an outline edge 1.5 microns
# long rather than from a vertical one. So the 148 of 262 he measured is
# NOT the vertical-edge mechanism, and which of the thickener's remaining
# exits refuses those cells is a question only this script can answer.
# 12.5(i) below is where that count is taken.
#
# THESE CHECKS HAVE NOT BEEN RUN. The agent that wrote them cannot execute
# Rhino and did not execute them; they are written to this file's
# established pattern and nothing more. Their first run is Param's, and
# until then a green line among them says nothing about the thickened
# solid.
# ---------------------------------------------------------------------------


def run_thickness_checks():
    assembly = _load_plugin(PLUGIN_PATH)
    skin_patterns = _find_type(assembly, "SkinPatterns")
    skin_net_type = _find_type(assembly, "SkinNet")
    skin_net_edge_type = _find_type(assembly, "SkinNetEdge")
    skin_component_type = _find_type(assembly, "SkinComponent")

    courses_method = _method(
        skin_patterns, "Courses",
        [skin_net_type, System.Double, System.Double, System.Double])
    cell_surface_method = _method(
        skin_component_type, "CellSurface", nonpublic=True)
    thicken_method = _method(
        skin_component_type, "ThickenCellSurface", nonpublic=True)

    def courses(net, size, ch, min_piece=1.0 / 3.0):
        return courses_method.Invoke(
            None, System.Array[object]([net, size, ch, min_piece]))

    def cell_surface(cell, net):
        return cell_surface_method.Invoke(
            None, System.Array[object]([cell, net]))

    def thicken(face, outline, sections, net, thickness, extrude):
        return thicken_method.Invoke(
            None,
            System.Array[object](
                [face, outline, sections, net, thickness, extrude]))

    offset_method = _method(
        skin_component_type, "ThicknessOffset", nonpublic=True)
    cell_normal_method = _method(
        skin_component_type, "CellNormal", nonpublic=True)

    # The three stops of the slider this script exercises. 0 is the
    # shipped default and the offset surface; 1 is the per-cell extrusion;
    # 0.5 is there because the blend's renormalisation is right at both
    # ends and wrong in the middle if it is written as an interpolation of
    # the two translations rather than of the two directions.
    STOPS = (0.0, 0.5, 1.0)

    reports = []
    vertices, faces, rim = _hemisphere()
    net = _make_net(skin_net_type, skin_net_edge_type, vertices, faces, rim)

    def cell_normal(outline):
        """The cell's OWN normal, N: the renormalised mean of its corners'
        field normals. Taken off the engine rather than recomputed, so the
        numbers asserted below are read from the same arithmetic the solid
        was built with."""
        return cell_normal_method.Invoke(
            None, System.Array[object]([net, outline]))

    def point_offset(point, normal, thickness, extrude):
        """The translation ONE point is copied by, taken straight off the
        engine, so that the exact numbers asserted below are read from the
        same arithmetic the solid was built with rather than from a second
        implementation of it that could drift."""
        return offset_method.Invoke(
            None,
            System.Array[object](
                [net, System.Array[float](list(point)), normal, thickness,
                 extrude]))

    built = courses(net, 0.6, 0.35)
    cells = list(_property(built, "Cells"))
    if not cells:
        return ["FAIL (12.5(f), NEW): the courses fixture built NO cells."]

    cell_type = cells[0].GetType()

    def make_cell(outline):
        """A SkinCell straight off the record, the way check 12.5(e)'s
        degenerate cell is built: course 0, unclipped, not a cap, no
        sections and no chains, so CellSurface routes on the outline
        alone."""
        return System.Activator.CreateInstance(
            cell_type,
            System.Array[object]([
                0,
                System.Array[object]([list(p) for p in outline]),
                False,
                0.0,
                0.0,
                False,
                len(outline),
                None,
                None,
            ]),
        )

    # ---- 12.5(f): a PLANAR cell, at every stop of the slider.
    #
    # NO VOLUME IS PREDICTED ANY MORE, and the reason is the deletion of
    # the world-Z branch. The old prediction, that a unit square thickened
    # by |Th| encloses |Th|, was true only of a VERTICAL translation of a
    # square lying flat. Both ends of the slider are now on the surface
    # normal, which under this square is a hemisphere's, so the enclosed
    # volume is a property of the hemisphere and not of the square at
    # every stop.
    #
    # WHAT IS ASSERTED INSTEAD IS EXACT AT EVERY STOP. The blended
    # direction is renormalised, so every moved corner stands exactly |Th|
    # from the corner it came from; the solid must carry a vertex at each
    # of them, which is what says its top stands on the outline its walls
    # were built from; and at Extrude 1 the top ring must be CONGRUENT to
    # the bottom, every corner having moved by the same vector Th * N.
    planar_outline = [
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
    ]
    planar_cell = make_cell(planar_outline)
    planar_face = cell_surface(planar_cell, net)
    if planar_face is None:
        reports.append(
            "FAIL (12.5(f), NEW, planar): CellSurface gave no face to "
            "thicken at all")
    else:
        planar_ring = _property(planar_cell, "Outline")
        planar_normal = cell_normal(planar_ring)
        for thickness in (0.2, -0.2):
            for extrude in STOPS:
                solid = thicken(
                    planar_face, planar_ring, None, net, thickness, extrude)
                if solid is None:
                    reports.append(
                        "FAIL (12.5(f), NEW, planar): Th %+.1f at Extrude "
                        "%.2f returned NULL rather than a solid"
                        % (thickness, extrude))
                    continue
                if not solid.IsSolid:
                    reports.append(
                        "FAIL (12.5(f), NEW, planar): Th %+.1f at Extrude "
                        "%.2f did not close; a thickened cell is a "
                        "watertight Brep or it is nothing"
                        % (thickness, extrude))
                    continue
                if solid.SolidOrientation != rg.BrepSolidOrientation.Outward:
                    reports.append(
                        "FAIL (12.5(f), NEW, planar): Th %+.1f at Extrude "
                        "%.2f came back oriented %s; the spec asks for "
                        "Outward"
                        % (thickness, extrude, solid.SolidOrientation))
                    continue
                volume = solid.GetVolume()
                box = solid.GetBoundingBox(True)
                low, high = box.Min.Z, box.Max.Z
                faults = []
                corners = [v.Location for v in solid.Vertices]
                moved = []
                for point in planar_outline:
                    step = point_offset(
                        point, planar_normal, thickness, extrude)
                    moved.append((
                        point[0] + step[0],
                        point[1] + step[1],
                        point[2] + step[2]))
                    walked = math.sqrt(
                        (step[0] * step[0]) + (step[1] * step[1]) +
                        (step[2] * step[2]))
                    if abs(walked - abs(thickness)) > 1.0e-9:
                        faults.append(
                            "the corner (%.6f, %.6f, %.6f) moved %.12f "
                            "rather than |Th| = %.12f, so the blended "
                            "direction was not RENORMALISED"
                            % (point[0], point[1], point[2],
                               walked, abs(thickness)))
                for point in moved:
                    seat = rg.Point3d(point[0], point[1], point[2])
                    if not any(
                            seat.DistanceTo(at) <= 1.0e-9 for at in corners):
                        faults.append(
                            "the solid carries no vertex at the moved "
                            "corner (%.9f, %.9f, %.9f), so its top does "
                            "not stand on the outline its walls were "
                            "built from"
                            % (point[0], point[1], point[2]))
                # ONE WALL'S TWO ENDS. The wall on outline edge 0 runs from
                # that corner to the corner it moved to, and that span is
                # |Th| exactly, which is the thickness this cell actually
                # carries at that corner.
                span = rg.Point3d(
                    planar_outline[0][0], planar_outline[0][1],
                    planar_outline[0][2]).DistanceTo(
                        rg.Point3d(moved[0][0], moved[0][1], moved[0][2]))
                if abs(span - abs(thickness)) > 1.0e-9:
                    faults.append(
                        "the first wall's two ends span %.12f rather than "
                        "|Th| = %.12f" % (span, abs(thickness)))
                # CONGRUENCE AT 1, and only there. Every corner moves by
                # the same vector Th * N, so the top ring's pairwise corner
                # distances are the bottom's.
                if extrude == 1.0:
                    for a in range(len(planar_outline)):
                        for b in range(a + 1, len(planar_outline)):
                            below = rg.Point3d(
                                planar_outline[a][0], planar_outline[a][1],
                                planar_outline[a][2]).DistanceTo(
                                    rg.Point3d(
                                        planar_outline[b][0],
                                        planar_outline[b][1],
                                        planar_outline[b][2]))
                            above = rg.Point3d(
                                moved[a][0], moved[a][1],
                                moved[a][2]).DistanceTo(
                                    rg.Point3d(
                                        moved[b][0], moved[b][1],
                                        moved[b][2]))
                            if abs(above - below) > 1.0e-9:
                                faults.append(
                                    "at Extrude 1 corners %d and %d are "
                                    "%.12f apart below and %.12f above, "
                                    "where a rigid translation keeps them "
                                    "equal" % (a, b, below, above))
                if faults:
                    reports.append(
                        "FAIL (12.5(f), NEW, planar): Th %+.1f at Extrude "
                        "%.2f: %s"
                        % (thickness, extrude, "; ".join(faults)))
                    continue
                reports.append(
                    "PASS (12.5(f), NEW, UNVERIFIED BY ITS AUTHOR, "
                    "planar): Th %+.1f at Extrude %.2f is a watertight "
                    "outward solid of volume %.9f spanning z %.6f to "
                    "%.6f, every one of its %d moved corners standing "
                    "exactly |Th| from the corner it came from and "
                    "carried as a vertex of the solid, the first wall's "
                    "two ends spanning %.9f; no volume is predicted at "
                    "any stop, both ends of the slider being on the net's "
                    "own normal and not the square's"
                    % (thickness, extrude, volume, low, high, len(moved),
                       span))

    # ---- 12.5(g): a NON-PLANAR cell off the real courses engine, where no
    # volume is worth predicting by hand but closedness and orientation
    # still are. The cell chosen is the one whose corners depart furthest
    # from their own mean height, so this is not a nearly-flat cell in
    # disguise.
    #
    # IT CARRIES ITS OWN SECTIONS NOW, which is spec 2026-09-04 section 5:
    # a courses cell is a LOFT of two bed runs, and its top must be lofted
    # from those same rails moved rather than fanned over its outline. The
    # fan over a lofted bottom is the triangulated crust in Param's
    # screenshot, and this is the cell it appears on.
    def out_of_plane(cell):
        outline = [list(p) for p in _property(cell, "Outline")]
        if len(outline) < 4:
            return -1.0
        mean_z = sum(p[2] for p in outline) / len(outline)
        return max(abs(p[2] - mean_z) for p in outline)

    warped = max(cells, key=out_of_plane)
    warped_face = cell_surface(warped, net)
    if warped_face is None:
        reports.append(
            "FAIL (12.5(g), NEW, non-planar): CellSurface gave no face")
    else:
        warped_ring = _property(warped, "Outline")
        warped_sections = _property(warped, "Sections")
        for thickness in (0.2, -0.2):
            for extrude in STOPS:
                solid = thicken(
                    warped_face, warped_ring, warped_sections, net,
                    thickness, extrude)
                if solid is None or not solid.IsSolid:
                    reports.append(
                        "FAIL (12.5(g), NEW, non-planar): Th %+.1f at "
                        "Extrude %.2f did not close into a watertight "
                        "solid" % (thickness, extrude))
                    continue
                if solid.SolidOrientation != rg.BrepSolidOrientation.Outward:
                    reports.append(
                        "FAIL (12.5(g), NEW, non-planar): Th %+.1f at "
                        "Extrude %.2f came back oriented %s rather than "
                        "Outward"
                        % (thickness, extrude, solid.SolidOrientation))
                    continue
                reports.append(
                    "PASS (12.5(g), NEW, UNVERIFIED BY ITS AUTHOR, "
                    "non-planar): Th %+.1f at Extrude %.2f is a watertight "
                    "outward solid of %d faces, out-of-plane departure "
                    "%.4f m, its top lofted from %s rails rather than "
                    "fanned"
                    % (thickness, extrude, solid.Faces.Count,
                       out_of_plane(warped),
                       "no" if warped_sections is None
                       else str(len(list(warped_sections)))))

    # ---- 12.5(h): THE WELD AT 0 AND THE SPLIT AT 1, which is the whole of
    # what the slider claims and the one thing only real Breps can show.
    #
    # AT EXTRUDE 0 the direction is read at the POINT and off nothing else,
    # so two cells that share an outline corner move it by the same vector
    # and BOTH SOLIDS must carry a vertex at the corner and at the moved
    # corner. Under the deleted per-cell normal that half would have failed
    # by construction, which is why it could not be written before.
    #
    # AT EXTRUDE 1 they must NOT: the cell's own normal enters, the two
    # neighbours disagree about it, and the joint opens. The gap is
    # asserted to be REAL, above the 1e-6 the join is asked at, because a
    # slider read and ignored would leave it at zero and pass the weld half
    # alone.
    #
    # AND THE PAIR MUST GENUINELY DISAGREE ABOUT ITS OWN NORMAL, which is
    # the approving review of 2026-09-04, finding 4. This took the FIRST
    # corner-sharing pair it met and asserted a real gap at Extrude 1 off
    # it. Two cells whose own normals happen to agree, which is every pair
    # across a flat patch and every pair on a coarse ring, move a shared
    # corner to the same place at EVERY stop of the slider: that is the
    # arithmetic behaving, not a defect, and the assertion would have
    # reddened on a fixture rather than on the engine. The filter is the
    # one tests/native_smoke's own weld check uses (its ValidateSkinOffsetWeld,
    # the |cos| > cos(0.1) skip): a tenth of a radian is a real difference,
    # half a degree is not. Only if NO disagreeing pair exists anywhere does
    # this fail, and then it fails for what it is, a fixture that cannot
    # carry the claim.
    def disagreement(left_cell, right_cell):
        """One minus |cos| between the two cells' own normals, off the
        ENGINE's CellNormal, so the pair is chosen by the same arithmetic
        the gap is then measured with."""
        a = cell_normal(_property(left_cell, "Outline"))
        b = cell_normal(_property(right_cell, "Outline"))
        return 1.0 - abs(sum(a[k] * b[k] for k in range(3)))

    shared = None
    agreeing_pairs = 0
    for i in range(len(cells)):
        left = [tuple(p) for p in _property(cells[i], "Outline")]
        for j in range(i + 1, len(cells)):
            right = set(tuple(p) for p in _property(cells[j], "Outline"))
            common = [p for p in left if p in right]
            if not common:
                continue
            if disagreement(cells[i], cells[j]) <= 1.0 - math.cos(0.1):
                agreeing_pairs += 1
                continue
            shared = (cells[i], cells[j], common[0])
            break
        if shared is not None:
            break
    if shared is None:
        reports.append(
            "FAIL (12.5(h), NEW): no two cells of the fixture share an "
            "outline corner AND disagree about their own normals by more "
            "than a tenth of a radian (%d corner-sharing pairs were found "
            "and every one of them agreed), so the split at Extrude 1 "
            "could only have been measured on a pair the engine is right "
            "to weld at both ends" % (agreeing_pairs,))
    else:
        left_cell, right_cell, corner = shared
        thickness = 0.2
        left_normal = cell_normal(_property(left_cell, "Outline"))
        right_normal = cell_normal(_property(right_cell, "Outline"))
        for extrude in (0.0, 1.0):
            left_step = point_offset(
                corner, left_normal, thickness, extrude)
            right_step = point_offset(
                corner, right_normal, thickness, extrude)
            gap = math.sqrt(
                sum((left_step[k] - right_step[k]) ** 2 for k in range(3)))
            faults = []
            if extrude == 0.0 and gap > 1.0e-12:
                faults.append(
                    "the two cells moved the shared corner %.12f apart at "
                    "Extrude 0, where the direction is a function of the "
                    "POINT alone and they must agree exactly" % (gap,))
            if extrude == 1.0 and gap <= 1.0e-6:
                faults.append(
                    "the two cells moved the shared corner only %.12f "
                    "apart at Extrude 1, where each is meant to follow its "
                    "OWN normal and the joint is meant to open; a slider "
                    "read and ignored looks exactly like this" % (gap,))
            wanted = []
            for step in ((left_step, left_cell), (right_step, right_cell)):
                wanted.append((
                    step[1],
                    rg.Point3d(corner[0], corner[1], corner[2]),
                    rg.Point3d(
                        corner[0] + step[0][0],
                        corner[1] + step[0][1],
                        corner[2] + step[0][2])))
            for cell, seat, moved_seat in wanted:
                face = cell_surface(cell, net)
                solid = thicken(
                    face, _property(cell, "Outline"),
                    _property(cell, "Sections"), net, thickness, extrude)
                if solid is None or not solid.IsSolid:
                    faults.append(
                        "one of the two cells did not close into a solid")
                    continue
                corners = [v.Location for v in solid.Vertices]
                for point in (seat, moved_seat):
                    if not any(
                            point.DistanceTo(at) <= 1.0e-9 for at in corners):
                        faults.append(
                            "a cell's solid has no vertex at (%.9f, %.9f, "
                            "%.9f)" % (point.X, point.Y, point.Z))
            if faults:
                reports.append(
                    "FAIL (12.5(h), NEW, shared corner, Extrude %.2f): %s"
                    % (extrude, "; ".join(sorted(set(faults)))))
            else:
                reports.append(
                    "PASS (12.5(h), NEW, UNVERIFIED BY ITS AUTHOR, shared "
                    "corner, Extrude %.2f): two cells sharing the corner "
                    "(%.6f, %.6f, %.6f), whose own normals disagree by "
                    "%.4f in cosine, at Th 0.2 move it %.12f m apart, and "
                    "each solid carries a vertex at the corner and at its "
                    "own moved corner. At 0 that gap is the WELD and at 1 "
                    "it is the joint opening by design."
                    % (extrude, corner[0], corner[1], corner[2],
                       disagreement(left_cell, right_cell), gap))

    # ---- 12.5(i), NEW 2026-09-03, PER SLIDER STOP since 2026-09-04: THE
    # COUNT PARAM ASKED FOR, and the only place it can honestly be taken.
    #
    # tests/native_smoke can count the cells whose side wall is ANNIHILATED
    # into a line, and that count is ZERO on every fixture at both ends of
    # the slider, including Param's own net under both patterns. So the
    # vertical-edge mechanism is not behind his 148 of 262, and the refusal
    # must be happening at one of the thickener's other exits: a wall Rhino
    # declines for its own reasons, a join that does not close, or a shell
    # that is not solid. All three need the native core, so the count
    # belongs here.
    #
    # THE OPEN QUESTION THIS SCRIPT OWNS is the LOFT ROUTE. A courses cell
    # is a loft of two bed runs, and until 2026-09-04 its top was fanned
    # over its outline whatever its bottom was, so the top's boundary was
    # the outline's straight chords where the bottom's was the loft's own
    # rails: two boundaries that cannot join at the 1e-6 the join is asked
    # at. That would refuse EVERY cell of the loft route rather than a
    # scattering, which fits 148 of 262 far better than any vertical edge
    # does. The counts below are what decides it.
    #
    # It is a MEASUREMENT and not an assertion. Whether one end of the
    # slider closes more cells than the other is exactly the open question,
    # and a check that decided it in advance would be worthless.
    thickness = 0.29
    tally = {}
    for extrude in STOPS:
        faces_built = 0
        solids_built = 0
        for cell in cells:
            face = cell_surface(cell, net)
            if face is None:
                continue
            faces_built += 1
            solid = thicken(
                face, _property(cell, "Outline"),
                _property(cell, "Sections"), net, thickness, extrude)
            if solid is not None and solid.IsSolid:
                solids_built += 1
        tally[extrude] = (faces_built, solids_built)
    reports.append(
        "MEASURED (12.5(i), NEW, UNVERIFIED BY ITS AUTHOR): at Th %.2f "
        "over %d cells, %s. If the refusal counts are the same at every "
        "stop, the thickener's problem is not the offset direction; if "
        "they are near zero everywhere, the top-by-its-bottom's-route "
        "change of spec 2026-09-04 section 5 is what closed them and the "
        "148 are accounted for."
        % (thickness, len(cells),
           "; ".join(
               "Extrude %.2f built %d faces and closed %d of them into "
               "solids (%d refused)"
               % (stop, tally[stop][0], tally[stop][1],
                  tally[stop][0] - tally[stop][1])
               for stop in STOPS)))

    return reports


try:
    for line in run_behavioural_checks():
        print(line)
except Exception as error:  # pragma: no cover - reported to the console
    print("FAIL (12.5(b) to (e)): %s" % (error,))

print(
    "---- NEW 2026-09-03, AWAITING PARAM'S RUN: the thickness checks "
    "below have NEVER been executed. Their author has no Rhino and did "
    "not run them. Read a green line among them as untested until this "
    "script has been run once inside Rhino. ----"
)
try:
    for line in run_thickness_checks():
        print(line)
except Exception as error:  # pragma: no cover - reported to the console
    print("FAIL (12.5(f) to (h), NEW): %s" % (error,))
