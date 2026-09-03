#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Skin: ONE proposer for the buildable skin layout on the thrust surface
/// (spec 2026-08-31), under the old Skin's GUID so saved placements load
/// as this component behind the ports-moved warning. Three patterns behind
/// one flag: 0 running-bond courses, 1 stretched honeycomb and 2 the
/// force-aligned dual, all three computed natively and synchronously on
/// the Result's own vertex and face arrays through SkinPatterns (rule
/// 3.2.4): there is no worker dispatch left on this component. Outputs
/// are VISIBLE: seeing the pattern the moment it computes is the point.
/// Export still owns projecting to plan and writing the sidecar, and still
/// calls <see cref="FacePolylines"/> for its unwired default tessellation.
/// </summary>
public sealed class SkinComponent : NativeComponentBase
{
    /// <summary>
    /// The shipped S default, in metres. Kept in step with the generator's
    /// own <c>armadillo_dual.DEFAULT_SIZE</c> (the worker reads that same
    /// constant when a request omits size). 0.6 is measured, not chosen:
    /// it is the smallest value on a 0.1 m grid at which the reference BRG
    /// armadillo primal clears every geometric acceptance bar.
    /// </summary>
    private const double DefaultSize = 0.6;

    /// <summary>The old Skin's CH default: one course rise, metres.</summary>
    private const double DefaultCourseHeight = 0.35;

    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Pattern",
            new (string Label, string Value)[]
            {
                ("0 · courses", "0"),
                ("1 · hexagonal", "1"),
                ("2 · force aligned", "2")
            },
            "0")
    };

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    public SkinComponent()
        : base(
            "Skin",
            "Skin",
            "Propose the buildable skin layout on the thrust surface: "
                + "running-bond courses or a stretched honeycomb, set out "
                + "natively from a seam with Size along the course and "
                + "Course Height up it, or the worker's force-aligned "
                + "dual. Cells wires straight into Export, which reads "
                + "the branch path as the course, projects to plan and "
                + "writes the sidecar.",
            ComponentCategories.Deliver,
            "skin")
    {
        // A PROPOSER previews: no output is hidden, the Armadillo Dual
        // convention, because seeing the pattern the moment it computes
        // is the point of the component.
    }

    public override Guid ComponentGuid =>
        new("7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "A solved Result. The native patterns need a TNA Result with "
                + "faces; an FD Result gives empty outputs and a Remark. "
                + "The force-aligned pattern hands the Result to the "
                + "worker unchanged and inherits its refusal rules.",
            GH_ParamAccess.item);
        parameters.AddIntegerParameter(
            "Pattern",
            "P",
            "Which tessellation to lay: 0 courses, 1 honeycomb, 2 "
                + "force-aligned. The force-aligned pattern's flow lines are "
                + "the MESH'S OWN EDGE DIRECTIONS weighted by member force and "
                + "averaged in doubled-angle space. They are NOT principal "
                + "stress directions, and the pattern does not claim to be "
                + "one. Because the directions are read off the form "
                + "diagram's own layout, a REMESH OF THE FORM DIAGRAM MOVES "
                + "THE JOINTS even where the surface and the forces are "
                + "unchanged. And where a face's edges carry no force at all "
                + "the direction is a DEFAULT rather than a measurement: the "
                + "face takes its own first basis vector, so the joints there "
                + "are arbitrary and not wrong. Wire a Result that carries "
                + "member forces, or pattern 2 defaults everywhere and says so "
                + "in its own diagnostics.",
            GH_ParamAccess.item,
            0);
        parameters.AddNumberParameter(
            "Size",
            "S",
            "Target piece length along the course, metres. Minimum 1 mm. "
                + "Pattern 2 reads S alone as its voussoir size.",
            GH_ParamAccess.item,
            DefaultSize);
        parameters.AddNumberParameter(
            "Course Height",
            "CH",
            "Course rise, metres. Minimum 1 mm; below it the default is "
                + "used with a warning, the old Skin's rule. Ignored by "
                + "pattern 2.",
            GH_ParamAccess.item,
            DefaultCourseHeight);
        parameters.AddNumberParameter(
            "Min Piece",
            "MP",
            "The smallest piece worth laying, as a FRACTION of Size and not "
                + "a length of its own: 1/3 by default, so the minimum piece "
                + "is S / 3 and the maximum is S / MP = 3 S. A cell whose "
                + "along-course span is at or under the minimum is merged "
                + "into the shorter neighbour along its course, and a crown "
                + "cap above the maximum becomes a ring of wedges about a "
                + "smaller centre disc. Zero turns BOTH ends off, which is "
                + "the value for seeing the engine's raw output; a negative "
                + "clamps to zero and anything above 0.5 clamps to 0.5, each "
                + "with a warning naming the clamped value.",
            GH_ParamAccess.item,
            1.0 / 3.0);
        parameters[1].Optional = true;
        parameters[2].Optional = true;
        parameters[3].Optional = true;
        parameters[4].Optional = true;

        // Spec 2026-09-02 (skin-thickness-input), PURE APPEND after Min
        // Piece: ParameterIdentity's archived-name comparison walks the
        // saved ports in order, so a definition saved before this task
        // keeps every wire on the port it left and simply has no data on
        // these two, which read as their defaults (Th = 0, no thickening
        // at all; Along Normal = false). Th = 0 changes nothing about the
        // Surface output: this is the ONE port pair on this component
        // whose absence must be provably invisible.
        //
        // CORRECTION, measured 2026-09-03. The task that added these two
        // claimed the append is SILENT on load. It is not, and the claim
        // is withdrawn: Mismatch compares counts as well as names, so
        // five archived inputs against seven registered is reported. What
        // the append buys is the WORDING. The author is told the two new
        // ports were appended and that existing wires kept their ports,
        // rather than being sent to check every wire. Pinned in
        // ValidateParameterMismatch.
        parameters.AddNumberParameter(
            "Thickness",
            "Th",
            "Thicken the Surface output. Zero, the default, leaves every " +
                "output exactly as pattern 0 and 1 shipped it: no cell is " +
                "touched. Nonzero, each cell's face becomes a CLOSED SOLID " +
                "between the face and a copy of it offset by this amount, " +
                "the sign choosing the direction. The default offset is " +
                "VERTICAL, (0, 0, Th): every cell moves by the SAME " +
                "vector, so a wall shared by two cells stays coincident " +
                "and the thickened skin is watertight cell to cell. That " +
                "connectedness costs true thickness on a steep slope, " +
                "where a vertical offset reads thinner along the surface's " +
                "own normal by a factor of the local slope's cosine; " +
                "Along Normal trades the connectedness for the true " +
                "thickness instead.",
            GH_ParamAccess.item,
            0.0);
        parameters.AddBooleanParameter(
            "Along Normal",
            "N",
            "False, the default, offsets every cell VERTICALLY by the " +
                "same (0, 0, Th) so neighbouring cells stay watertight " +
                "(Param's own wording: \"the same level of " +
                "connectivness\"). True offsets each cell along ITS OWN " +
                "normal instead, giving true normal thickness at the cost " +
                "of gaps between cells wherever they meet at an angle. " +
                "Ignored while Th is 0.",
            GH_ParamAccess.item,
            false);
        parameters[5].Optional = true;
        parameters[6].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed polyline per cell, on the thrust surface, as a "
                + "TREE branched by COURSE (path = course, 0 up from the "
                + "bottom), which is now the ONLY carrier of the course: "
                + "Export reads the branch path. Within a branch cells run "
                + "FROM THE SEAM OUTWARD, alternating either side of it. "
                + "That order is for sequencing work on this canvas, and for "
                + "one thing more: where two cells overlap in plan the FIRST "
                + "one emitted is the one kept, so the cells nearest the "
                + "seam survive and the losses fall out at the edges of the "
                + "course. It is NOT the studio's build sequence. The studio "
                + "re-sorts every tessellation by course and then by each "
                + "cell's angle about the cut's own centre and reassigns its "
                + "own index, so the order in the file is discarded on "
                + "import. Courses are a RUNNING BOND, so cell 0 of one "
                + "course does not sit above cell 0 of the course below it "
                + "and the two courses may not even hold the same number of "
                + "cells; do not map item k of one branch against item k of "
                + "the next. Wire into Export's Cells. Do NOT graft, flatten "
                + "or regraft the wire: the branch path is the course, and a "
                + "flatten sends every cell to course 0 and every build "
                + "stage with it.",
            GH_ParamAccess.tree);
        parameters.AddBrepParameter(
            "Surface",
            "SRF",
            "One surface per cell, aligned with Cells BRANCH FOR BRANCH and "
                + "ITEM FOR ITEM: item k of branch r IS the surface of cell k "
                + "of course r. Skin's cells are non-planar many-sided rings, "
                + "and turning one of those into a face by hand is the "
                + "awkward job this output exists to spare. A cell that will "
                + "not close leaves a NULL in its slot rather than being "
                + "dropped, so the alignment holds. A crown cap comes back as "
                + "a Brep of MANY triangular faces rather than one, and so "
                + "does any cell whose corner count its pattern's own route "
                + "does not fit. Courses are a running bond, so item k of one "
                + "branch is NOT the surface sitting above item k of the "
                + "branch below; find the piece above a given piece "
                + "geometrically, by overlapping signed arc, and not by "
                + "index.",
            GH_ParamAccess.tree);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (!TryReadInputs(
                data,
                out ResultDto? result,
                out int pattern,
                out double size,
                out double courseHeight,
                out double minPiece,
                out double thickness,
                out bool alongNormal))
        {
            return;
        }
        SolveNative(
            data, result!, pattern, size, courseHeight, minPiece,
            thickness, alongNormal);
    }

    private void SolveNative(
        IGH_DataAccess data,
        ResultDto result,
        int pattern,
        double size,
        double courseHeight,
        double minPiece,
        double thickness,
        bool alongNormal)
    {
        try
        {
            SkinNet? net = SkinPatterns.ReadNet(result);
            if (net is null || net.Faces.Count == 0)
            {
                // The parenthesis is only true of the FD path. A TNA
                // Result whose form graph carries no faces reaches this
                // branch too, and telling its author it is an FD Result
                // would send them looking for the wrong fault.
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark,
                    ResultTables.IsTna(result)
                        ? "No faces on this Result, so there are no cells."
                        : "No faces on this Result (FD carries none), so "
                            + "there are no cells.");
                data.SetDataTree(
                    0, OutputTree.Curves(Array.Empty<List<Curve>>()));
                data.SetDataTree(
                    1, OutputTree.Breps(Array.Empty<List<Brep?>>()));
                Message = $"0 cells · 0 courses · {PatternName(pattern)}";
                return;
            }
            SkinPatternResult generated = pattern switch
            {
                0 => SkinPatterns.Courses(
                    net, size, courseHeight, minPiece),
                1 => SkinPatterns.Hexagonal(net, size, courseHeight),
                _ => SkinPatterns.ForceAligned(
                    net, size, courseHeight, minPiece)
            };

            // Rule 1.7.4: the field fallback, in its own words, because a
            // world-Z fallback changes what Course Height MEANS (a rise,
            // not a bed-to-bed spacing) and that is easy to miss on a
            // Result that simply carries no supports.
            if (generated.FieldKind == "world Z" && net.Rim.Count == 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "world Z: this Result names no supports, so courses " +
                    "are cut horizontally. Course Height is then a RISE " +
                    "and not a bed-to-bed spacing along the surface, so " +
                    "the courses stretch wherever the surface flattens.");
            }
            // Rule 1.7.3: a vertex the tracer could not reach across the
            // triangulation from the rim leaves a hole the cells never
            // cover, and the only place that hole is visible is here.
            if (generated.UnreachableVertices > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.UnreachableVertices} vertices are " +
                    "UNREACHABLE from the rim across the triangulation, so " +
                    "no cells are laid there and the skin has a hole over " +
                    "that region.");
            }
            // Rule 2.6.6: a crown cap over the maximum piece size that
            // could not be split into a ring of wedges is emitted whole,
            // and the girth against the maximum is named rather than
            // left for the author to measure by eye.
            if (generated.CapsOversized > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.CapsOversized} crown cap" +
                    (generated.CapsOversized == 1 ? " is" : "s are") +
                    " above the maximum piece size and could not be split " +
                    "into a ring of wedges, so " +
                    (generated.CapsOversized == 1 ? "it is" : "they are") +
                    " emitted WHOLE: a stone you can see and measure beats " +
                    "a hole you cannot fill. A smaller Course Height, or a " +
                    "larger Min Piece for bigger stones, is the remedy.");
            }

            // A band the engine REFUSED because the level curves changed
            // component count across it (a low loop splitting into
            // separate strips higher up, a two-hump barrel). The engine
            // records the heights in D; the canvas has to be told there
            // is a HOLE, because an author who only sees the cells would
            // read the gap as a pattern he chose.
            if (generated.TransitionBands > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.TransitionBands} band" +
                    (generated.TransitionBands == 1 ? " was" : "s were") +
                    " skipped where the level curves split, so the skin " +
                    "has a HOLE at those heights and this pattern does " +
                    "not cover the surface. Diagnostics names the " +
                    "heights.");
            }

            // A cell the engine DROPPED because its plan projection
            // self-crossed, overlapped a cell already kept, or (studio
            // request R-006) welded below three distinct corners once
            // consecutive corners within 1e-6 m were collapsed at
            // emission. Spec section 4 claims the native patterns cannot
            // produce a self-crossing or overlapping cell, and the claim
            // is now enforced rather than argued, because ONE bad cell
            // makes Bench Studio reject the whole tessellation. The drop
            // is never silent: the author is told how many and of which
            // kind, exactly as the force-aligned pattern already tells
            // him.
            // The sentence is SCALED TO THE FRACTION DROPPED, because a
            // warning that promises a small hole while handing back an
            // empty tree is worse than no warning at all. A HELICOIDAL
            // shell is the case: its level curves are radial segments at
            // an angle that keeps turning, so a course two turns up lies
            // over a course two turns down and every cell overlaps
            // something already kept. Measured on a three-turn ramp of
            // inner radius 1 and outer radius 2 climbing 2 m, at S 0.6:
            // the honeycomb drops 11 of 11 at CH 0.35 and 8 of 8 at CH
            // 0.5, so the pattern is EMPTY, and the courses engine drops
            // 10 of 15 and 3 of 10. Dropping everything there is the
            // right answer, since a level curve that wraps is not a
            // height field's and the surface is outside the spec's
            // domain; only the sentence was wrong. So the count is
            // always given against the TOTAL the pattern built; "a small
            // hole where each one was" is reserved for at most a TENTH
            // of that total; and where nothing survives the author is
            // told the pattern is EMPTY rather than holed.
            int dropped =
                generated.PlanDegenerateDropped +
                generated.PlanOverlapDropped +
                generated.WeldCollapsedDropped;
            if (dropped > 0)
            {
                int built = dropped + generated.Cells.Count;
                int percent = (int)Math.Round(100.0 * dropped / built);
                string scale =
                    generated.Cells.Count == 0
                        ? "NOTHING survived, so this pattern is EMPTY " +
                          "and covers none of the surface."
                        : dropped * 10 <= built
                            ? "The skin has a small hole where each one " +
                              "was, and the tessellation Export writes " +
                              "still imports."
                            : $"That is {percent} per cent of this " +
                              "pattern, so the skin has a LARGE hole and " +
                              "it covers only part of the surface; the " +
                              "tessellation Export writes still imports.";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{dropped} of the {built} cell" +
                    (built == 1 ? "" : "s") + " this pattern built " +
                    (dropped == 1 ? "was" : "were") +
                    " DROPPED to keep it valid: " +
                    $"{generated.PlanDegenerateDropped} self-crossing, " +
                    $"{generated.PlanOverlapDropped} overlapping a cell " +
                    "already kept and " +
                    $"{generated.WeldCollapsedDropped} welded below " +
                    $"three distinct corners. {scale} Diagnostics counts " +
                    "them.");
            }

            var cellBranches = new List<List<Curve>>();
            for (int course = 0; course < generated.CourseCount; course++)
                cellBranches.Add(new List<Curve>());
            var surfaceBranches = new List<List<Brep?>>();
            for (int course = 0; course < generated.CourseCount; course++)
                surfaceBranches.Add(new List<Brep?>());
            int surfaceFailed = 0;
            int firstFailedCourse = -1;
            foreach (SkinCell cell in generated.Cells)
            {
                int course = Math.Min(
                    Math.Max(cell.Course, 0),
                    Math.Max(generated.CourseCount - 1, 0));
                cellBranches[course].Add(ClosedOutlineCurve(cell.Outline));
                Brep? surface = CellSurface(cell, net);
                if (surface is not null && thickness != 0.0)
                {
                    surface = ThickenCellSurface(
                        surface, cell.Outline, thickness, alongNormal);
                }
                surfaceBranches[course].Add(surface);
                if (surface is null)
                {
                    surfaceFailed++;
                    if (firstFailedCourse < 0)
                        firstFailedCourse = course;
                }
            }
            if (surfaceFailed > 0)
            {
                // A failure is a defect in this engine, not a fact about the
                // geometry, so it is counted, reported and raised.
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{surfaceFailed} cell" +
                    (surfaceFailed == 1 ? "" : "s") +
                    " would not close into a surface, the first at course " +
                    $"{firstFailedCourse}; those slots carry a NULL so the " +
                    "Surface tree stays aligned with Cells item for item.");
            }
            data.SetDataTree(0, OutputTree.Curves(cellBranches));
            data.SetDataTree(1, OutputTree.Breps(surfaceBranches));

            // Rule 9.3.1's chin: min and max piece length are on the FACE
            // of the component because they are what showed him the
            // force-aligned pattern was not uniform, 0.377 m against
            // 3.889 m, and losing them would remove the measurement this
            // round exists to restore. Cap cells are excluded (rule
            // 2.3.2a): a cap's own span is not a piece length.
            double[] spans = generated.Cells
                .Where(cell => !cell.Cap)
                .Select(cell => cell.U1 - cell.U0)
                .ToArray();
            Message =
                $"{generated.Cells.Count} cells · " +
                $"{generated.CourseCount} courses · " +
                PatternName(pattern) +
                (spans.Length > 0
                    ? $" · piece {spans.Min():F2} to {spans.Max():F2} m"
                    : string.Empty);

            // Rule 9.3.5's single Remark: the residual diagnostics content
            // that is not a hole and does not fit the chin reaches him
            // nowhere at all unless it is stated here, now that the D port
            // is gone.
            var residual = new List<string>
            {
                $"Field: {generated.FieldKind} ({generated.RimVerticesUsed} " +
                $"rim vertices, {generated.RimVerticesDropped} named " +
                $"supports and {generated.ForceEdgesDropped} force edges " +
                "dropped as unmappable)",
                "Mean piece length: " +
                $"{(spans.Length > 0 ? spans.Average() : 0.0):F3} m",
                $"Boundary-clipped cells: {generated.ClippedCells}",
                $"Crown caps: {generated.CapGirths.Count}" +
                (generated.CapGirths.Count > 0
                    ? " (girth " + string.Join(
                        ", ",
                        generated.CapGirths.Select(
                            girth => $"{girth:F3} m")) + "; wedges " +
                      string.Join(", ", generated.CapWedgeCounts) + ")"
                    : string.Empty),
                $"Odd cells: {generated.FiveSidedCells} five-sided, " +
                $"{generated.SevenSidedCells} seven-sided" +
                (generated.CountChangeRows.Count > 0
                    ? " (row counts change at rows " +
                      string.Join(", ", generated.CountChangeRows) + ")"
                    : string.Empty),
                $"Merged pieces: {generated.MergedPieces}"
            };
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Remark,
                string.Join("; ", residual));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Skin failed", error);
        }
    }

    private static string PatternName(int pattern) =>
        pattern switch
        {
            0 => "courses",
            1 => "hexagonal",
            _ => "force aligned"
        };

    /// <summary>
    /// Each outline is CLOSED by appending its first point again; both
    /// the native engines' cells and the worker's decoded cells arrive
    /// as open rings and leave through this one method. Moved verbatim.
    /// </summary>
    private static PolylineCurve ClosedOutlineCurve(
        IReadOnlyList<double[]> outline)
    {
        var points = new List<Point3d>(outline.Count + 1);
        foreach (double[] coordinate in outline)
        {
            points.Add(new Point3d(
                coordinate[0],
                coordinate[1],
                coordinate[2]));
        }
        if (points.Count > 0)
            points.Add(points[0]);
        return new PolylineCurve(points);
    }

    /// <summary>A flowline is open: it is not a cell boundary. Moved
    /// verbatim.</summary>
    private static PolylineCurve OpenOutlineCurve(
        IReadOnlyList<double[]> line)
    {
        var points = new List<Point3d>(line.Count);
        foreach (double[] coordinate in line)
        {
            points.Add(new Point3d(
                coordinate[0],
                coordinate[1],
                coordinate[2]));
        }
        return new PolylineCurve(points);
    }

    /// <summary>
    /// One cell's surface (spec section 5). On the SOLVE thread and only
    /// here, the split the component already keeps: nothing in
    /// SkinPatterns.cs may reference RhinoCommon.
    ///
    /// A cell carrying two sections is a straight, unclosed loft of them,
    /// which is route 5.2.3(a) and (c); three sections is route (b); no
    /// sections is the deterministic fan of routes (d) and (e), from the
    /// cell's own interior point lifted onto the surface, to each segment of
    /// the outline, joined. Brep.CreatePatch is NOT used: it is a fitting
    /// solver, its output is not the surface the cell describes, and a
    /// deterministic fan is worth more here than a smooth guess.
    ///
    /// The route is read off SECTIONS alone and there is no per-pattern case
    /// here: Sections carries the cell's own CROSS SECTIONS in one direction,
    /// whichever engine built it, and a force-aligned cell's four ring CHAINS
    /// live on their own field, which this method never reads. They are its
    /// four EDGES in cyclic order, bottom to right to top to left, so lofting
    /// them would loft a cell against its own sides.
    /// </summary>
    private static Brep? CellSurface(SkinCell cell, SkinNet net)
    {
        if (cell.Sections is not null && cell.Sections.Count >= 2)
        {
            var sections = new List<Curve>(cell.Sections.Count);
            foreach (IReadOnlyList<double[]> section in cell.Sections)
            {
                if (section.Count < 2)
                    return null;
                sections.Add(OpenOutlineCurve(section));
            }
            Brep[] lofted = Brep.CreateFromLoft(
                sections,
                Point3d.Unset,
                Point3d.Unset,
                LoftType.Straight,
                false);
            return lofted is { Length: 1 } && lofted[0].IsValid
                ? lofted[0]
                : null;
        }
        double[]? inside = SkinPatterns.PlanInteriorPoint(cell.Outline);
        if (inside is null)
            return null;
        double[]? apex = SkinPatterns.LiftPlanPoint(net, inside[0], inside[1]);
        if (apex is null)
            return null;
        var pieces = new List<Brep>(cell.Outline.Count);
        for (int at = 0; at < cell.Outline.Count; at++)
        {
            double[] a = cell.Outline[at];
            double[] b = cell.Outline[(at + 1) % cell.Outline.Count];
            Brep? piece = Brep.CreateFromCornerPoints(
                new Point3d(a[0], a[1], a[2]),
                new Point3d(b[0], b[1], b[2]),
                new Point3d(apex[0], apex[1], apex[2]),
                1.0e-9);
            if (piece is null)
                return null;
            pieces.Add(piece);
        }
        Brep[] joined = Brep.JoinBreps(pieces, 1.0e-9);
        return joined is { Length: 1 } && joined[0].IsValid
            ? joined[0]
            : null;
    }

    /// <summary>
    /// The Newell normal of a cell's own OUTLINE, unit length, never the
    /// mesh face's normal: a cell's outline is what Along Normal offsets,
    /// and a fanned cap or many-sided cell has no single mesh face to read
    /// a normal off in the first place. Pure arithmetic, no RhinoCommon
    /// type anywhere in the signature, so the harness can drive it with
    /// plain double[] fixtures the same way it drives Dedupe. An outline
    /// under three corners, or one whose Newell sum is too small to
    /// normalise (collinear or coincident corners), falls back to world Z
    /// rather than dividing by zero: an ARBITRARY direction is the honest
    /// answer for a shape too degenerate to have one.
    /// </summary>
    internal static double[] CellNormalUnit(IReadOnlyList<double[]> outline)
    {
        int count = outline.Count;
        if (count < 3)
            return new[] { 0.0, 0.0, 1.0 };
        double nx = 0.0, ny = 0.0, nz = 0.0;
        for (int at = 0; at < count; at++)
        {
            double[] a = outline[at];
            double[] b = outline[(at + 1) % count];
            nx += (a[1] - b[1]) * (a[2] + b[2]);
            ny += (a[2] - b[2]) * (a[0] + b[0]);
            nz += (a[0] - b[0]) * (a[1] + b[1]);
        }
        double length = Math.Sqrt((nx * nx) + (ny * ny) + (nz * nz));
        return length > 1.0e-12
            ? new[] { nx / length, ny / length, nz / length }
            : new[] { 0.0, 0.0, 1.0 };
    }

    /// <summary>
    /// The skin-thickness-input ruling's own arithmetic (2026-09-02),
    /// pulled out of <see cref="ThickenCellSurface"/> so it is testable
    /// without a Brep: the translation a cell's face is copied by, in the
    /// SAME units and SAME sign convention Th itself carries. Along
    /// Normal false, the default, is (0, 0, Th) for every cell without
    /// exception, which is the whole of Param's "same level of
    /// connectivness": two cells built from literally the same traced
    /// corner point add the literally same three doubles to it, so the
    /// shared wall stays coincident by construction and not by
    /// tolerance. Along Normal true reads the direction off THIS cell's
    /// own outline alone, so neighbouring cells generally diverge, which
    /// is exactly the trade the toggle exists to offer.
    /// </summary>
    internal static double[] ThicknessOffset(
        IReadOnlyList<double[]> outline, double thickness, bool alongNormal)
    {
        if (!alongNormal)
            return new[] { 0.0, 0.0, thickness };
        double[] normal = CellNormalUnit(outline);
        return new[]
        {
            normal[0] * thickness,
            normal[1] * thickness,
            normal[2] * thickness
        };
    }

    /// <summary>
    /// Spec 2026-09-02 (skin-thickness-input), section on WHAT THICKENS:
    /// one cell's Surface face becomes a CLOSED SOLID between the face and
    /// a copy of it translated by <see cref="ThicknessOffset"/>, bottom,
    /// top and the side walls run off the cell's own Outline, exactly the
    /// boundary CellSurface itself already treats as the cell's ring
    /// regardless of which route built the face (loft, fan or cap), so
    /// this one method serves every cell shape without a case on Sections.
    ///
    /// Th = 0 is refused entry here at all: <c>SolveNative</c> calls this
    /// method only when thickness is nonzero, which is the fast path the
    /// ruling's "byte-identical at Th = 0" requirement rests on -- the
    /// Surface tree carries the SAME Brep reference CellSurface built,
    /// untouched, rather than a copy built and then found equal.
    ///
    /// The closedness of the result needs RhinoCommon's native core to
    /// prove, which this plugin's own harness deliberately does not
    /// launch (rule 5.2.4's split): that proof is
    /// scripts/rhino_skin_surface.py, run inside Rhino, the same split
    /// CellSurface itself is already measured under.
    /// </summary>
    private static Brep? ThickenCellSurface(
        Brep face,
        IReadOnlyList<double[]> outline,
        double thickness,
        bool alongNormal)
    {
        if (outline.Count < 3)
            return null;
        double[] offset = ThicknessOffset(outline, thickness, alongNormal);
        var translation = new Vector3d(offset[0], offset[1], offset[2]);

        Brep top = face.DuplicateBrep();
        top.Transform(Transform.Translation(translation));
        // The top is the SAME face turned to face the opposite way, so a
        // solid join sees a consistent shell rather than two faces both
        // facing up; SolidOrientation below is the belt to this braces.
        top.Flip();

        var pieces = new List<Brep>(outline.Count + 2) { face, top };
        for (int at = 0; at < outline.Count; at++)
        {
            double[] a = outline[at];
            double[] b = outline[(at + 1) % outline.Count];
            var a0 = new Point3d(a[0], a[1], a[2]);
            var b0 = new Point3d(b[0], b[1], b[2]);
            Brep? wall = Brep.CreateFromCornerPoints(
                a0, b0, b0 + translation, a0 + translation, 1.0e-9);
            if (wall is null)
                return null;
            pieces.Add(wall);
        }

        Brep[] joined = Brep.JoinBreps(pieces, 1.0e-6);
        if (joined is not { Length: 1 } || !joined[0].IsValid)
            return null;
        Brep solid = joined[0];
        if (solid.SolidOrientation == BrepSolidOrientation.Inward)
            solid.Flip();
        return solid.IsSolid ? solid : null;
    }

    /// <summary>
    /// Rule 6.4's bounds, as a static so the harness can drive them without a
    /// canvas. Anything above 0.5 clamps to 0.5, anything below 0 clamps to
    /// 0, and a value that is not finite falls back to the port default. The
    /// message is returned rather than raised, so the one arithmetic serves
    /// both the component's Warning and check 12.6(e).
    /// </summary>
    internal static double ClampMinPiece(
        double asked, out bool clamped, out string warning)
    {
        double answer =
            !double.IsFinite(asked)
                ? 1.0 / 3.0
                : Math.Min(Math.Max(asked, 0.0), 0.5);
        clamped = !double.IsFinite(asked) || asked < 0.0 || asked > 0.5;
        warning = clamped
            ? "Min Piece is a fraction of Size between 0 and 0.5; using " +
              answer.ToString("F3", CultureInfo.InvariantCulture) +
              ". Zero turns both the merge and the crown-cap split off " +
              "together, which is the only coherent reading of a single " +
              "threshold turned off."
            : string.Empty;
        return answer;
    }

    /// <summary>
    /// Read RES, Pattern, S, CH and MP, validating up front so the
    /// background task never has to report a runtime message itself. S
    /// keeps the Armadillo Dual guard: a NaN or sub-millimetre S is
    /// REFUSED with the negated comparison (NaN fails every comparison, so
    /// a guard written the other way round would let it through, and the
    /// worker would return a silent empty result). CH keeps the old Skin's
    /// rule: floored to the default with a warning. A Pattern outside 0..2
    /// is refused naming the three patterns. MP is clamped rather than
    /// refused, by rule 6.4's <see cref="ClampMinPiece"/>: a negative
    /// therefore means "off" rather than meaning a failed solve, because
    /// refusing the whole output over a number he can see and fix on the
    /// canvas would cost him more than the mistake did.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ResultDto? result,
        out int pattern,
        out double size,
        out double courseHeight,
        out double minPiece,
        out double thickness,
        out bool alongNormal,
        bool report = true)
    {
        result = null;
        pattern = 0;
        size = DefaultSize;
        courseHeight = DefaultCourseHeight;
        minPiece = 1.0 / 3.0;
        thickness = 0.0;
        alongNormal = false;
        ResultGoo? resultGoo = null;
        int patternInput = 0;
        double sizeInput = DefaultSize;
        double courseHeightInput = DefaultCourseHeight;
        double minPieceInput = 1.0 / 3.0;
        double thicknessInput = 0.0;
        bool alongNormalInput = false;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref patternInput);
        data.GetData(2, ref sizeInput);
        data.GetData(3, ref courseHeightInput);
        data.GetData(4, ref minPieceInput);
        data.GetData(5, ref thicknessInput);
        data.GetData(6, ref alongNormalInput);
        minPieceInput = ClampMinPiece(
            minPieceInput, out bool minPieceClamped, out string minPieceWarning);
        if (minPieceClamped && report)
            AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, minPieceWarning);
        // Th keeps its own sign always (it is a direction, not a
        // magnitude), so only non-finite is refused, floored to 0 -- no
        // thickening -- rather than to the port default, which IS 0.
        if (!double.IsFinite(thicknessInput))
        {
            if (report)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Th must be finite; using 0 (no thickening).");
            }
            thicknessInput = 0.0;
        }

        var errors = new List<string>(resultValue.Validate());
        if (patternInput < 0 || patternInput > 2)
        {
            errors.Add(
                "Pattern must be 0 (courses), 1 (hexagonal) or 2 " +
                $"(force aligned); received {patternInput}.");
        }
        if (!(sizeInput > 0.001))
        {
            errors.Add(
                "S must be greater than 1 mm (0.001 m); received " +
                $"{sizeInput}.");
        }
        if (!(courseHeightInput > 0.001))
        {
            if (report)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Course Height must be at least 1 mm; using 0.35 m.");
            }
            courseHeightInput = DefaultCourseHeight;
        }
        if (errors.Count > 0)
        {
            if (report)
            {
                Message = "Invalid";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    string.Join(" ", errors));
            }
            return false;
        }

        result = resultValue;
        pattern = patternInput;
        size = sizeInput;
        courseHeight = courseHeightInput;
        minPiece = minPieceInput;
        thickness = thicknessInput;
        alongNormal = alongNormalInput;
        return true;
    }

    /// <summary>
    /// One mesh face's corner points, in winding order: three for a
    /// triangle, four for a quad. Kept from the old Skin because
    /// <see cref="FacePolylines"/> reads corners this way.
    /// </summary>
    private static IReadOnlyList<Point3d> FaceCorners(
        Mesh mesh,
        MeshFace face)
    {
        var points = new List<Point3d>(4)
        {
            mesh.Vertices[face.A],
            mesh.Vertices[face.B],
            mesh.Vertices[face.C]
        };
        if (face.IsQuad)
            points.Add(mesh.Vertices[face.D]);
        return points;
    }

    /// <summary>
    /// One closed polyline per mesh face, in face order. Internal because
    /// EXPORT calls it, for the tessellation it builds when nobody wired
    /// one (one cell per face, course 0): the signature is a compile-time
    /// contract with DeliveryComponents.cs and does not move.
    /// </summary>
    internal static IReadOnlyList<PolylineCurve> FacePolylines(Mesh mesh)
    {
        var polylines = new List<PolylineCurve>(mesh.Faces.Count);
        for (int i = 0; i < mesh.Faces.Count; i++)
        {
            IReadOnlyList<Point3d> corners =
                FaceCorners(mesh, mesh.Faces[i]);
            var points = new List<Point3d>(corners.Count + 1);
            points.AddRange(corners);
            points.Add(points[0]);
            polylines.Add(new PolylineCurve(points));
        }
        return polylines;
    }
}
