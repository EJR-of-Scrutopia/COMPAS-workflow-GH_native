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
        // at all; Offset = true, which Th = 0 ignores). Th = 0 changes
        // nothing about the Surface output: this is the ONE port pair on
        // this component whose absence must be provably invisible.
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
                "between the face and a copy of it offset by this amount. " +
                "The offset is SIGNED and ONE-SIDED: a positive Th builds " +
                "outward along the surface normal and a negative one " +
                "inward, so the solved surface is the intrados or the " +
                "extrados of the skin and never its middle. Offset chooses " +
                "between an offset surface, where every outline point " +
                "moves along the normal AT THAT POINT, and a plain " +
                "vertical extrusion.",
            GH_ParamAccess.item,
            0.0);
        // Spec 2026-09-03 (skin-offset-surface), rule 5. The port KEEPS ITS
        // INDEX so no archived wire moves; only the name, nickname, default
        // and description change. It used to be "Along Normal" and it named
        // the direction of an EXTRUSION, whole cell translated either by
        // (0, 0, Th) or along that one cell's own Newell normal. Both are
        // extrusions, and the second gapped and clashed where the surface
        // turned. What was asked for was the choice between an OFFSET
        // SURFACE and an extrusion, which is what this port now offers.
        parameters.AddBooleanParameter(
            "Offset",
            "OF",
            "True, the default, builds an OFFSET SURFACE: every outline " +
                "point moves along the surface normal AT THAT POINT, so " +
                "cells that share a corner move it to the same place and " +
                "stay welded, and the skin keeps its connectivity. The " +
                "normal is a property of the POINT and not of the cell, " +
                "which is why neighbours cannot gap and cannot clash. " +
                "False EXTRUDES instead: the whole cell is translated by " +
                "(0, 0, Th), which leaves gaps where cells meet and copies " +
                "a vertical outline edge onto itself, but is a simpler " +
                "solid. Ignored while Th is 0.",
            GH_ParamAccess.item,
            true);
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
                out bool offsetSurface))
        {
            return;
        }
        SolveNative(
            data, result!, pattern, size, courseHeight, minPiece,
            thickness, offsetSurface);
    }

    private void SolveNative(
        IGH_DataAccess data,
        ResultDto result,
        int pattern,
        double size,
        double courseHeight,
        double minPiece,
        double thickness,
        bool offsetSurface)
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
            // read the gap as a pattern he chose. The heights themselves
            // are named by TransitionWarningLine below.
            string? transitionLine = TransitionWarningLine(
                generated.TransitionBands,
                generated.TransitionIntervals,
                generated.FieldKind);
            if (transitionLine is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning, transitionLine);
            }

            // Every cell the pattern proposed and did not deliver, of all
            // four kinds, in one sentence sized by the fraction lost.
            // LostCellsWarningLine carries the reasoning.
            string? lostLine = LostCellsWarningLine(
                generated.PlanDegenerateDropped,
                generated.PlanOverlapDropped,
                generated.WeldCollapsedDropped,
                generated.BandEscapedRefused,
                generated.Cells.Count);
            if (lostLine is not null)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, lostLine);

            var cellBranches = new List<List<Curve>>();
            for (int course = 0; course < generated.CourseCount; course++)
                cellBranches.Add(new List<Curve>());
            var surfaceBranches = new List<List<Brep?>>();
            for (int course = 0; course < generated.CourseCount; course++)
                surfaceBranches.Add(new List<Brep?>());
            int faceFailed = 0;
            int firstFaceFailedCourse = -1;
            int thickenFailed = 0;
            int firstThickenFailedCourse = -1;
            bool thickening = Thickening(thickness);
            foreach (SkinCell cell in generated.Cells)
            {
                int course = Math.Min(
                    Math.Max(cell.Course, 0),
                    Math.Max(generated.CourseCount - 1, 0));
                cellBranches[course].Add(ClosedOutlineCurve(cell.Outline));
                Brep? face = CellSurface(cell, net);
                Brep? solid =
                    face is not null && thickening
                        ? ThickenCellSurface(
                            face, cell.Outline, net, thickness, offsetSurface)
                        : null;
                CellSurfaceSlot slot = ClassifyCellSurface(
                    face is not null, thickening, solid is not null);
                surfaceBranches[course].Add(slot switch
                {
                    CellSurfaceSlot.Solid => solid,
                    CellSurfaceSlot.Face => face,
                    _ => null
                });
                if (slot == CellSurfaceSlot.Nothing)
                {
                    faceFailed++;
                    if (firstFaceFailedCourse < 0)
                        firstFaceFailedCourse = course;
                }
                else if (slot == CellSurfaceSlot.Face && thickening)
                {
                    thickenFailed++;
                    if (firstThickenFailedCourse < 0)
                        firstThickenFailedCourse = course;
                }
            }
            // Two failures, two sentences. One message counting both sent
            // the reader to the wrong function: spec 5.3.1 and the
            // thickness spec both say a NULL slot means the FACE failed,
            // so a thickening failure reported under that wording is a
            // false statement about which half of the engine broke.
            string? faceLine = FaceFailureLine(
                faceFailed, firstFaceFailedCourse);
            if (faceLine is not null)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, faceLine);
            string? thickenLine = ThickenFailureLine(
                thickenFailed, firstThickenFailedCourse, thickness,
                offsetSurface);
            if (thickenLine is not null)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, thickenLine);
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
                OddCellsLine(
                    generated.FiveSidedCells,
                    generated.ThreeSidedCells,
                    generated.SevenSidedCells,
                    generated.CountChangeRows),
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
    /// What goes into one cell's slot on the Surface tree: the thickened
    /// SOLID, the un-thickened FACE, or NOTHING at all.
    /// </summary>
    internal enum CellSurfaceSlot
    {
        /// <summary>The face itself would not close. Only here is the slot
        /// a null, and only here does spec 5.3.1's reading hold.</summary>
        Nothing = 0,

        /// <summary>The face is what the author gets: either Th is zero
        /// and nothing was asked for, or the thickening failed and the
        /// face the engine had already built is kept.</summary>
        Face = 1,

        /// <summary>The closed solid between the face and its offset
        /// copy.</summary>
        Solid = 2
    }

    /// <summary>
    /// A FACE THE ENGINE BUILT IS NEVER THROWN AWAY.
    ///
    /// Until 2026-09-03 the thickened solid simply REPLACED the face in
    /// the slot, so a cell whose face closed and whose thickening did not
    /// came back as a null, indistinguishable from a cell that had no
    /// surface at all. Param measured 148 of 262 nulls on his
    /// force-aligned run at Th 0.29 and 12 of 282 on his courses run, and
    /// the thickener is the suspect: it joins the face, its flipped copy
    /// and one wall per outline corner into a single watertight shell and
    /// refuses anything that is not solid, which is a far narrower gate
    /// than building the face was. Half a stone is worth more than none,
    /// so where the solid fails the face stands and the failure is
    /// counted under its own name.
    ///
    /// It is a static of three booleans because the two Brep routes need
    /// RhinoCommon's native core, which does not initialise outside
    /// Rhino, so this rule is the only part of the decision the harness
    /// can reach. Measured 2026-09-03 in a scratch console app on this
    /// machine: Brep.CreateFromCornerPoints outside Rhino throws
    /// "System.DllNotFoundException: Unable to load DLL 'rhcommon_c'".
    /// </summary>
    internal static CellSurfaceSlot ClassifyCellSurface(
        bool faceBuilt, bool thickeningAsked, bool solidBuilt)
    {
        if (!faceBuilt)
            return CellSurfaceSlot.Nothing;
        if (thickeningAsked && solidBuilt)
            return CellSurfaceSlot.Solid;
        return CellSurfaceSlot.Face;
    }

    /// <summary>
    /// The warning for cells whose FACE would not close, or null where
    /// none did. This is the message spec 5.3.1 is about: these slots and
    /// only these slots carry a null.
    /// </summary>
    internal static string? FaceFailureLine(int failed, int firstCourse)
    {
        if (failed <= 0)
            return null;
        return
            $"{failed} cell" + (failed == 1 ? "" : "s") +
            " would not close into a FACE, the first at course " +
            $"{firstCourse}; those slots carry a NULL so the Surface tree " +
            "stays aligned with Cells item for item.";
    }

    /// <summary>
    /// The warning for faces that would not close into a SOLID at the
    /// thickness in force, or null where none failed. It is a SEPARATE
    /// sentence from <see cref="FaceFailureLine"/> and it says plainly
    /// that nothing was lost: those cells are still exported and are
    /// drawn as the un-thickened face. One count for both failures was
    /// the defect: it told the author his cells had no surface when the
    /// engine had built every one of them.
    ///
    /// THE REMEDY IS WORDED AGAINST THE MODE ACTUALLY IN FORCE, which is
    /// why <paramref name="offsetSurface"/> is a parameter of a sentence
    /// that otherwise needs only counts. The first draft advised "a
    /// smaller Thickness, or Along Normal off" unconditionally, on a
    /// toggle that defaulted to off, so on a default canvas it told the
    /// author to switch off a toggle already off.
    ///
    /// The second draft, written against that same toggle, advised turning
    /// Along Normal ON, and a reviewer's objection to it was that it never
    /// named the COST: under the old semantics ON meant each cell moved
    /// along its OWN normal, so neighbours gapped, and a remedy that trades
    /// a hole for a solid ought to say so. Under the port renamed by spec
    /// 2026-09-03 (skin-offset-surface) THAT COST IS GONE. Offset ON is an
    /// offset surface, not a per-cell extrusion: every outline point moves
    /// along the normal at that point, so cells that share a corner keep
    /// sharing it and the skin stays welded. Recommending it costs the
    /// author nothing, which is why the cost is not named here: there is
    /// none to name.
    ///
    /// Why Offset OFF is the likelier cause of a refusal. A side wall is
    /// built from the quad (a, b, b + offset, a + offset) per outline edge
    /// (<see cref="ThickenCellSurface"/>), and OFF offsets vertically at
    /// (0, 0, Th): where the edge a to b itself runs vertical, all four
    /// corners lie on one vertical line, Brep.CreateFromCornerPoints has no
    /// quad to make, and the cell is refused. A steep springing with
    /// near-vertical head joints refuses cells for that reason alone and
    /// not for any fault of their thickness.
    /// </summary>
    internal static string? ThickenFailureLine(
        int failed, int firstCourse, double thickness, bool offsetSurface)
    {
        if (failed <= 0)
            return null;
        string remedy = offsetSurface
            ? " A smaller Thickness is the remedy. Offset is already on, " +
              "so every outline point already moves along the surface " +
              "normal at that point and the cells are already welded."
            : " A smaller Thickness is the remedy, and so is Offset ON, " +
              "which costs nothing: an offset surface moves every outline " +
              "point along the normal AT THAT POINT, so neighbouring " +
              "cells stay welded rather than gapping. With Offset off the " +
              "whole cell is extruded by (0, 0, Th) instead, so an " +
              "outline edge that runs vertical is copied onto itself and " +
              "leaves no side wall to build.";
        return
            $"{failed} face" + (failed == 1 ? "" : "s") +
            " would not close into a SOLID at Thickness " +
            thickness.ToString("F3", CultureInfo.InvariantCulture) +
            $", the first at course {firstCourse}. Those cells are STILL " +
            "EXPORTED and are drawn as the un-thickened face, so the " +
            "slot holds a surface and not a null." + remedy;
    }

    /// <summary>
    /// The transition warning, or null where no band was skipped. THE
    /// HEIGHTS ARE NAMED HERE rather than promised: the old wording ended
    /// "Diagnostics names the heights" and nothing named them, because the
    /// intervals live on TransitionIntervals and inside the engine's own
    /// Diagnostics string and no component has read either since the D
    /// port went. The fragment comes from
    /// <see cref="SkinPatterns.TransitionWhere"/>, which is the same
    /// arithmetic and the same wording the diagnostics line uses, so the
    /// two readings of one refusal cannot drift apart.
    /// </summary>
    internal static string? TransitionWarningLine(
        int bands,
        IReadOnlyList<(double Low, double High)> intervals,
        string fieldKind)
    {
        if (bands <= 0)
            return null;
        string where = intervals.Count > 0
            ? " The level curves stop corresponding " +
              SkinPatterns.TransitionWhere(intervals, fieldKind) + "."
            : string.Empty;
        return
            $"{bands} band" + (bands == 1 ? " was" : "s were") +
            " skipped where the level curves split, so the skin has a " +
            "HOLE at those heights and this pattern does not cover the " +
            "surface." + where;
    }

    /// <summary>
    /// EVERY CELL THE PATTERN PROPOSED AND DID NOT DELIVER, in one
    /// sentence, or null where it delivered them all.
    ///
    /// Three of the four are DROPS taken after emission: a cell whose plan
    /// projection self-crossed, one that overlapped a cell already kept,
    /// or (studio request R-006) one that welded below three distinct
    /// corners once consecutive corners within 1e-6 m were collapsed at
    /// emission. Spec section 4 claims the native patterns cannot produce
    /// a self-crossing or overlapping cell, and the claim is enforced
    /// rather than argued, because ONE bad cell makes Bench Studio reject
    /// the whole tessellation. The loss is never silent: the author is
    /// told how many and of which kind.
    ///
    /// The fourth is a REFUSAL taken at emission, and it is here rather
    /// than in the engine's diagnostics alone because of what the sentence
    /// below does with it. The force-aligned pattern refuses a cell whose
    /// head joint stands outside its own band (plan 2026-09-03 task 2,
    /// step 2). Before this, a refused cell reached the canvas nowhere:
    /// on Param's own crown arch at S 0.17 and CH 0.375 the pattern
    /// proposed 142 cells and delivered 71, and a warning built from the
    /// drops alone read 6 of 77, an 8 per cent hole, for a skin that had
    /// lost half of itself. Counting the refusals restores 71 of 142, and
    /// the same net read 64 of 142 before the refusal existed at all, so
    /// the number an author sees no longer FALLS when the pattern starts
    /// covering less.
    ///
    /// The sentence is SCALED TO THE FRACTION LOST, because a warning
    /// that promises a small hole while handing back an empty tree is
    /// worse than no warning at all. A HELICOIDAL shell is the case: its
    /// level curves are radial segments at an angle that keeps turning, so
    /// a course two turns up lies over a course two turns down and every
    /// cell overlaps something already kept. Measured on a three-turn ramp
    /// of inner radius 1 and outer radius 2 climbing 2 m, at S 0.6: the
    /// honeycomb drops 11 of 11 at CH 0.35 and 8 of 8 at CH 0.5, so the
    /// pattern is EMPTY, and the courses engine drops 10 of 15 and 3 of
    /// 10. Dropping everything there is the right answer, since a level
    /// curve that wraps is not a height field's and the surface is outside
    /// the spec's domain; only the sentence was wrong. So the count is
    /// always given against the TOTAL the pattern proposed; "a small hole
    /// where each one was" is reserved for at most a TENTH of that total;
    /// and where nothing survives the author is told the pattern is EMPTY
    /// rather than holed.
    /// </summary>
    internal static string? LostCellsWarningLine(
        int degenerateDropped,
        int overlapDropped,
        int weldCollapsedDropped,
        int bandEscapedRefused,
        int kept)
    {
        int lost =
            degenerateDropped + overlapDropped + weldCollapsedDropped +
            bandEscapedRefused;
        if (lost <= 0)
            return null;
        int proposed = lost + kept;
        int percent = (int)Math.Round(100.0 * lost / proposed);
        string scale =
            kept == 0
                ? "NOTHING survived, so this pattern is EMPTY and covers " +
                  "none of the surface."
                : lost * 10 <= proposed
                    ? "The skin has a small hole where each one was, and " +
                      "the tessellation Export writes still imports."
                    : $"That is {percent} per cent of this pattern, so " +
                      "the skin has a LARGE hole and it covers only part " +
                      "of the surface; the tessellation Export writes " +
                      "still imports.";
        return
            $"{lost} of the {proposed} cell" +
            (proposed == 1 ? "" : "s") + " this pattern proposed " +
            (lost == 1 ? "was" : "were") +
            " REFUSED or DROPPED to keep it valid: " +
            $"{degenerateDropped} self-crossing, " +
            $"{overlapDropped} overlapping a cell already kept, " +
            $"{weldCollapsedDropped} welded below three distinct corners " +
            $"and {bandEscapedRefused} refused at emission for leaving " +
            $"their band. {scale} Diagnostics counts them.";
    }

    /// <summary>
    /// The Remark's odd-cell line, all THREE counts each under its own
    /// name. The force-aligned closer of rule 3.3.5 has THREE corners,
    /// and until 2026-09-03 it was carried in SevenSidedCells and printed
    /// here as "seven-sided", while the engine's own diagnostics line
    /// called the same number three-sided. The honeycomb's seven-sided
    /// rim cell of rule 4.3 is the only genuine seven, and it keeps the
    /// seven-sided field.
    /// </summary>
    internal static string OddCellsLine(
        int fiveSided,
        int threeSided,
        int sevenSided,
        IReadOnlyList<int> countChangeRows) =>
        $"Odd cells: {fiveSided} five-sided, {threeSided} three-sided, " +
        $"{sevenSided} seven-sided" +
        (countChangeRows.Count > 0
            ? " (row counts change at rows " +
              string.Join(", ", countChangeRows) + ")"
            : string.Empty);

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
    ///
    /// ROUTES (d) AND (e) SHARE ONE APEX, and there is no Cap branch here.
    /// That is deliberate and it is now what the spec says. Rule 5.2.3(d)
    /// used to name a DIFFERENT apex, the net vertex of greatest field
    /// value inside the cap's loop; the whole-branch review's finding 6
    /// caught that this engine has never built it, and the spec carries an
    /// erratum of 2026-09-03 amending the rule to this apex rather than
    /// amending the engine to the rule. The reason is that the old apex
    /// can simply fail to exist: rule 2.6.3's crown disc is a small ring
    /// found by bisection and holds no net vertex at all on any net whose
    /// crown is coarser than the disc, so the cap would have no surface,
    /// and even where one exists it is a MESH vertex rather than a point
    /// on the loop's own patch. The lifted plan interior point always
    /// exists and always lies on the cell's own surface, and on a crown
    /// loop it lands at the summit the old wording was reaching for.
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

    // CellNormalUnit WAS HERE, and its deletion is recorded rather than
    // left silent. It read the Newell normal of a cell's own OUTLINE and it
    // existed for one caller, Along Normal's true branch, which translated
    // the WHOLE cell along that one direction. Spec 2026-09-03
    // (skin-offset-surface) deletes that branch: it gapped like an
    // extrusion and ignored the point normals like an extrusion, so it was
    // strictly worse than both survivors. Nothing else ever called
    // CellNormalUnit, so it went with its caller rather than being left to
    // rot. The normal that matters now belongs to the POINT, is computed
    // over the whole net, and lives in SkinPatterns.VertexNormals and
    // SkinPatterns.NormalAt.
    //
    // The old comment's warning is kept because it names the trap the
    // deletion walks past: a Newell sum follows the outline's WINDING, and
    // a winding is not consistent from cell to cell on a vault whose
    // contours are open strips, so one positive Th thickened half a shell
    // outward and the other half inward. The old code answered that by
    // forcing the normal into the upward hemisphere. The net's own vertex
    // normals need no such correction: the net carries ONE winding, so its
    // normal field is already one-sided, and the sign of Th is left to
    // decide the side by itself.

    /// <summary>
    /// THE OFFSET AT ONE POINT (spec 2026-09-03, skin-offset-surface, rules
    /// 2 and 4), pulled out of <see cref="ThickenCellSurface"/> so it is
    /// testable without a Brep: the translation ONE outline point is copied
    /// by, in the SAME units and SAME sign convention Th itself carries.
    ///
    /// Offset FALSE is (0, 0, Th) for every point without exception, which
    /// is the extrusion the port's false branch names: every cell moves by
    /// the same vector, so a wall shared by two cells stays coincident, and
    /// an outline edge that runs vertical is copied onto itself.
    ///
    /// Offset TRUE reads the direction off the NET at that point, through
    /// <see cref="SkinPatterns.NormalAt"/>, and off nothing else. It takes
    /// the point and not the cell, and that is the load-bearing part of the
    /// design rather than a convenience: two cells that share a corner hand
    /// this method the same three doubles and get the same three back, so
    /// the corner moves to one place and the skin stays welded. A signature
    /// that could see the calling cell would let a future edit weight the
    /// answer by it and break the weld silently.
    ///
    /// SIGNED AND ONE-SIDED, which is Param's ruling of 2026-09-03: the
    /// full Th goes one way, never half each side, so the solved surface is
    /// the intrados or the extrados of the skin and never its middle. The
    /// studio centres its blocks instead (bench/studio/voussoirs.py
    /// _solid_from_corners, half each side); that reading is the
    /// structurally truer one and it is NOT taken here, because he wants
    /// the solved surface to be a face he can build to.
    /// </summary>
    internal static double[] ThicknessOffset(
        SkinNet net, double[] point, double thickness, bool offsetSurface)
    {
        if (!offsetSurface)
            return new[] { 0.0, 0.0, thickness };
        double[] normal = SkinPatterns.NormalAt(net, point);
        return new[]
        {
            normal[0] * thickness,
            normal[1] * thickness,
            normal[2] * thickness
        };
    }

    /// <summary>
    /// One outline moved: corner by corner, each along its OWN offset
    /// (<see cref="ThicknessOffset"/>). This is the whole of the change the
    /// spec asks for, and it is a static of plain double[] so the harness
    /// can weigh two neighbouring cells' answers against one another
    /// without a Brep anywhere.
    /// </summary>
    internal static IReadOnlyList<double[]> OffsetOutline(
        SkinNet net,
        IReadOnlyList<double[]> outline,
        double thickness,
        bool offsetSurface)
    {
        var moved = new List<double[]>(outline.Count);
        foreach (double[] corner in outline)
        {
            double[] offset =
                ThicknessOffset(net, corner, thickness, offsetSurface);
            moved.Add(new[]
            {
                corner[0] + offset[0],
                corner[1] + offset[1],
                corner[2] + offset[2]
            });
        }
        return moved;
    }

    /// <summary>
    /// IS THIS SIDE WALL ANNIHILATED? A wall is the quad (a, b, bTop,
    /// aTop), and Brep.CreateFromCornerPoints has nothing to make of it
    /// when the four corners are COLLINEAR: it refuses, and
    /// <see cref="ThickenCellSurface"/> refuses the whole cell with it.
    /// That is spec 2026-09-03 section 1 point 3, the mechanism by which a
    /// VERTICAL outline edge under a VERTICAL offset kills a cell that has
    /// nothing else wrong with it.
    ///
    /// Pure arithmetic and no Brep, deliberately: RhinoCommon's native core
    /// does not initialise outside Rhino, so this predicate is the only way
    /// the harness can count the refusals of that class at all, and it is
    /// the measurement Param asked for, extrude against offset on one
    /// fixture.
    ///
    /// The measure is <see cref="WallQuadArea"/>, the largest triangle area
    /// among the quad's four corner triples, and the test is that it is
    /// EXACTLY nothing to within 1e-18. Annihilation is an exact
    /// collinearity and not a near one: a merely STEEP edge leaves a sliver
    /// quad with real area, which Rhino builds without complaint. Measured
    /// 2026-09-03 on the harness's fixtures, that distinction is the whole
    /// answer: a 45 degree tent barrel and Param's own crown arch produce
    /// no annihilated wall at all, and only a surface standing exactly
    /// vertical does.
    /// </summary>
    internal static bool WallQuadDegenerate(
        double[] a, double[] b, double[] bTop, double[] aTop) =>
        WallQuadArea(a, b, bTop, aTop) <= 1.0e-18;

    /// <summary>
    /// How much of a quad a side wall actually is: the largest triangle
    /// area among its four corner triples. Zero on every triple means the
    /// four corners lie on one line and there is nothing to build; a small
    /// positive value means a sliver, which is a wall and not a refusal.
    ///
    /// It is separate from <see cref="WallQuadDegenerate"/> so the harness
    /// can report HOW CLOSE a fixture's walls come to annihilation rather
    /// than only whether any of them crossed the line. A count of zero
    /// tells an author nothing about whether he was nearly caught.
    /// </summary>
    internal static double WallQuadArea(
        double[] a, double[] b, double[] bTop, double[] aTop)
    {
        double[][] quad = { a, b, bTop, aTop };
        double worst = 0.0;
        for (int i = 0; i < 4; i++)
        {
            double[] p = quad[i];
            double[] q = quad[(i + 1) % 4];
            double[] r = quad[(i + 2) % 4];
            double ux = q[0] - p[0], uy = q[1] - p[1], uz = q[2] - p[2];
            double vx = r[0] - p[0], vy = r[1] - p[1], vz = r[2] - p[2];
            double cx = (uy * vz) - (uz * vy);
            double cy = (uz * vx) - (ux * vz);
            double cz = (ux * vy) - (uy * vx);
            double twice = Math.Sqrt((cx * cx) + (cy * cy) + (cz * cz));
            worst = Math.Max(worst, twice / 2.0);
        }
        return worst;
    }

    /// <summary>
    /// IS ANY THICKENING ASKED FOR AT ALL? Named rather than written inline
    /// because it is the gate the "byte-identical at Th = 0" ruling rests
    /// on: at Th exactly zero the Surface tree carries the SAME Brep
    /// reference CellSurface built, untouched, and never a copy built and
    /// then found equal. A comparison that let zero through would replace
    /// every face on a default canvas with a rebuilt one.
    /// </summary>
    internal static bool Thickening(double thickness) => thickness != 0.0;

    /// <summary>
    /// WHAT THICKENS: one cell's Surface face becomes a CLOSED SOLID
    /// between the face and a copy of it moved by
    /// <see cref="ThicknessOffset"/>, bottom, top and one side wall per
    /// outline edge, run off the cell's own Outline, exactly the boundary
    /// CellSurface itself already treats as the cell's ring regardless of
    /// which route built the face (loft, fan or cap), so this one method
    /// serves every cell shape without a case on Sections.
    ///
    /// TWO ROUTES, and the port decides which (spec 2026-09-03,
    /// skin-offset-surface, rule 5).
    ///
    /// EXTRUDE, Offset false, is unchanged from what shipped: one
    /// translation vector (0, 0, Th) for the whole cell, so the face is
    /// duplicated and transformed, which is the cheapest and simplest
    /// solid and is reproduced here bit for bit for anyone who wants it.
    ///
    /// OFFSET SURFACE, Offset true and the default, moves every outline
    /// point along the normal AT THAT POINT, so there is no single
    /// translation and the top cannot be a transformed copy of the bottom.
    /// It is built instead as the deterministic fan of routes (d) and (e)
    /// of rule 5.2.3 over the MOVED outline, from the cell's own lifted
    /// plan interior point moved by ITS own offset. The fan is what
    /// CellSurface already builds for a cell with no sections, its edges
    /// are the straight chords the side walls are built on, and its apex
    /// is a function of the cell's own plan alone, so two runs of the same
    /// cell give the same solid. Where the apex cannot be found (a cell
    /// whose plan has no interior point, or one lying off the net) the
    /// cell is refused rather than thickened wrongly.
    ///
    /// Th = 0 is refused entry here at all: <c>SolveNative</c> calls this
    /// method only when <see cref="Thickening"/> is true, which is the fast
    /// path the ruling's "byte-identical at Th = 0" requirement rests on --
    /// the Surface tree carries the SAME Brep reference CellSurface built,
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
        SkinNet net,
        double thickness,
        bool offsetSurface)
    {
        if (outline.Count < 3)
            return null;
        IReadOnlyList<double[]> moved =
            OffsetOutline(net, outline, thickness, offsetSurface);

        Brep? top;
        if (!offsetSurface)
        {
            double[] offset =
                ThicknessOffset(net, outline[0], thickness, false);
            top = face.DuplicateBrep();
            top.Transform(Transform.Translation(
                new Vector3d(offset[0], offset[1], offset[2])));
        }
        else
        {
            top = OffsetTopFace(net, outline, thickness);
            if (top is null)
                return null;
        }
        // The top is the same ring seen from the other side, so a solid
        // join sees a consistent shell rather than two faces both facing
        // the same way; SolidOrientation below is the belt to this braces.
        top.Flip();

        var pieces = new List<Brep>(outline.Count + 2) { face, top };
        for (int at = 0; at < outline.Count; at++)
        {
            double[] a = outline[at];
            double[] b = outline[(at + 1) % outline.Count];
            double[] aTop = moved[at];
            double[] bTop = moved[(at + 1) % outline.Count];
            Brep? wall = Brep.CreateFromCornerPoints(
                new Point3d(a[0], a[1], a[2]),
                new Point3d(b[0], b[1], b[2]),
                new Point3d(bTop[0], bTop[1], bTop[2]),
                new Point3d(aTop[0], aTop[1], aTop[2]),
                1.0e-9);
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
    /// The offset route's TOP FACE: the deterministic fan of rule 5.2.3(d)
    /// and (e) over the moved outline, from the cell's own plan interior
    /// point lifted onto the net and then moved by that point's own offset.
    /// Null where the cell has no plan interior point, where that point
    /// lies off the net, or where the fan will not join.
    /// </summary>
    private static Brep? OffsetTopFace(
        SkinNet net, IReadOnlyList<double[]> outline, double thickness)
    {
        double[]? inside = SkinPatterns.PlanInteriorPoint(outline);
        if (inside is null)
            return null;
        double[]? apex = SkinPatterns.LiftPlanPoint(net, inside[0], inside[1]);
        if (apex is null)
            return null;
        double[] apexOffset = ThicknessOffset(net, apex, thickness, true);
        var top = new Point3d(
            apex[0] + apexOffset[0],
            apex[1] + apexOffset[1],
            apex[2] + apexOffset[2]);
        IReadOnlyList<double[]> moved =
            OffsetOutline(net, outline, thickness, true);
        var pieces = new List<Brep>(moved.Count);
        for (int at = 0; at < moved.Count; at++)
        {
            double[] a = moved[at];
            double[] b = moved[(at + 1) % moved.Count];
            Brep? piece = Brep.CreateFromCornerPoints(
                new Point3d(a[0], a[1], a[2]),
                new Point3d(b[0], b[1], b[2]),
                top,
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
        out bool offsetSurface,
        bool report = true)
    {
        result = null;
        pattern = 0;
        size = DefaultSize;
        courseHeight = DefaultCourseHeight;
        minPiece = 1.0 / 3.0;
        thickness = 0.0;
        offsetSurface = true;
        ResultGoo? resultGoo = null;
        int patternInput = 0;
        double sizeInput = DefaultSize;
        double courseHeightInput = DefaultCourseHeight;
        double minPieceInput = 1.0 / 3.0;
        double thicknessInput = 0.0;
        bool offsetSurfaceInput = true;
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
        data.GetData(6, ref offsetSurfaceInput);
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
        offsetSurface = offsetSurfaceInput;
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
