#nullable enable

using System;
using System.Collections.Generic;
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
                + "dual. Cells and Courses wire straight into Export, "
                + "which projects to plan and writes the sidecar.",
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
            "Which pattern to propose: 0 courses (running bond), 1 "
                + "hexagonal (stretched honeycomb), 2 force aligned (the "
                + "worker's Armadillo dual). A value list is offered on "
                + "the component menu.",
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
        parameters[1].Optional = true;
        parameters[2].Optional = true;
        parameters[3].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed polyline per cell, on the thrust surface, as a "
                + "TREE branched by COURSE (path = course, 0 up from the "
                + "bottom). A NATIVE pattern's branch lists one traced "
                + "component's run after another, each run ordered SEAM "
                + "OUTWARD, alternating either side of it with the "
                + "negative side first; this serves the Grasshopper "
                + "author's reading and the overlap filter, which keeps "
                + "the first cell it is handed, and is NOT the studio's "
                + "own build sequence. Which component comes first still "
                + "follows the mesh's face order. The force-aligned "
                + "pattern keeps the worker's own order. Wire into "
                + "Export's Cells; Export flattens and projects itself.",
            GH_ParamAccess.tree);
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "The course per cell, branched and ordered exactly as Cells, "
                + "the index repeated per item, so the pairing survives "
                + "Export's flatten. Wire into Export's Courses.",
            GH_ParamAccess.tree);
        parameters.AddCurveParameter(
            "Flowlines",
            "FL",
            "The advected flow lines, force-aligned pattern only; empty "
                + "for the native patterns.",
            GH_ParamAccess.tree);
        parameters.AddTextParameter(
            "Diagnostics",
            "D",
            "Readable text. Native patterns: the pattern name, cell and "
                + "course counts, mean/min/max piece length, the stagger, "
                + "the count of boundary-clipped cells, how many cells "
                + "were DROPPED to keep the pattern valid in plan (self-"
                + "crossing, and overlapping a cell already kept) and, "
                + "where bands were REFUSED because the level curves "
                + "across them do not correspond, how many and the "
                + "heights each refusal sits between. Force aligned: the "
                + "worker's diagnostics verbatim.",
            GH_ParamAccess.item);
        parameters.AddBrepParameter(
            "Surface",
            "SF",
            "One Brep per cell (spec section 5), branched and ordered "
                + "EXACTLY as Cells, item for item: a two-section cell "
                + "(courses, force aligned) lofts its lower and upper "
                + "runs, a three-section hexagon lofts its bottom run, "
                + "its side pair and its top run, and a cap or an odd-"
                + "cornered cell is fanned from its own interior point "
                + "lifted onto the surface. A cell that will not close "
                + "into a Brep carries a NULL here rather than a missing "
                + "item, so this tree stays aligned with Cells even where "
                + "a cell failed.",
            GH_ParamAccess.tree);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (!TryReadInputs(
                data,
                out ResultDto? result,
                out int pattern,
                out double size,
                out double courseHeight))
        {
            return;
        }
        // TryReadInputs' extra minPiece out parameter is Task 30's; until
        // then, call the four-parameter form and pass the engine's own
        // default here.
        SolveNative(
            data, result!, pattern, size, courseHeight, 1.0 / 3.0);
    }

    private void SolveNative(
        IGH_DataAccess data,
        ResultDto result,
        int pattern,
        double size,
        double courseHeight,
        double minPiece)
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
                    1, OutputTree.Integers(Array.Empty<List<int>>()));
                data.SetDataTree(
                    2, OutputTree.Curves(Array.Empty<List<Curve>>()));
                data.SetData(3, string.Empty);
                data.SetDataTree(
                    4, OutputTree.Breps(Array.Empty<List<Brep?>>()));
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
            // self-crossed, or overlapped a cell already kept. Spec
            // section 4 claims the native patterns cannot produce
            // either, and the claim is now enforced rather than argued,
            // because ONE bad cell makes Bench Studio reject the whole
            // tessellation. The drop is never silent: the author is told
            // how many and of which kind, exactly as the force-aligned
            // pattern already tells him.
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
                generated.PlanOverlapDropped;
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
                    " DROPPED to keep it valid in plan: " +
                    $"{generated.PlanDegenerateDropped} self-crossing " +
                    $"and {generated.PlanOverlapDropped} overlapping a " +
                    $"cell already kept. {scale} Diagnostics counts them.");
            }

            var cellBranches = new List<List<Curve>>();
            var courseBranches = new List<List<int>>();
            for (int course = 0; course < generated.CourseCount; course++)
            {
                cellBranches.Add(new List<Curve>());
                courseBranches.Add(new List<int>());
            }
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
                courseBranches[course].Add(course);
                Brep? surface = CellSurface(cell, net);
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
            data.SetDataTree(1, OutputTree.Integers(courseBranches));
            data.SetDataTree(
                2, OutputTree.Curves(Array.Empty<List<Curve>>()));
            data.SetData(3, generated.Diagnostics);
            data.SetDataTree(4, OutputTree.Breps(surfaceBranches));
            Message =
                $"{generated.Cells.Count} cells · " +
                $"{generated.CourseCount} courses · " +
                PatternName(pattern);
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
    /// Read RES, Pattern, S and CH, validating up front so the background
    /// task never has to report a runtime message itself. S keeps the
    /// Armadillo Dual guard: a NaN or sub-millimetre S is REFUSED with
    /// the negated comparison (NaN fails every comparison, so a guard
    /// written the other way round would let it through, and the worker
    /// would return a silent empty result). CH keeps the old Skin's rule:
    /// floored to the default with a warning. A Pattern outside 0..2 is
    /// refused naming the three patterns.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ResultDto? result,
        out int pattern,
        out double size,
        out double courseHeight,
        bool report = true)
    {
        result = null;
        pattern = 0;
        size = DefaultSize;
        courseHeight = DefaultCourseHeight;
        ResultGoo? resultGoo = null;
        int patternInput = 0;
        double sizeInput = DefaultSize;
        double courseHeightInput = DefaultCourseHeight;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref patternInput);
        data.GetData(2, ref sizeInput);
        data.GetData(3, ref courseHeightInput);

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
