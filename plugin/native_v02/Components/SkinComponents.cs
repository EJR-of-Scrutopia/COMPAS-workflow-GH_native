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
                "extrados of the skin and never its middle. Extrude slides " +
                "between an offset surface, where every outline point " +
                "moves along the normal AT THAT POINT, and a per-cell " +
                "extrusion along the cell's own normal. BOTH ENDS ARE ON " +
                "THE SURFACE NORMAL.",
            GH_ParamAccess.item,
            0.0);
        // Spec 2026-09-04 (skin-offset-extrude-slider), section 2. The port
        // KEEPS ITS INDEX so no archived wire moves; the name, nickname,
        // type, default and description all change. It was "Along Normal"
        // and then "Offset", and both named a CHOICE where what Param asked
        // for is a slider: "I want to take this a step further and do a
        // slider 0-1.00 where I can slide between if the outer surface goes
        // from offset ... to extruded ... That means we can remove the
        // button and put in this slider."
        //
        // A BOOLEAN WIRED HERE STILL READS. Grasshopper casts a GH_Boolean
        // to a GH_Number, False to 0 and True to 1, so his archived toggle
        // sitting at False lands on the new default without his touching
        // it. Measured through this very port in the smoke harness rather
        // than assumed.
        parameters.AddNumberParameter(
            "Extrude",
            "EX",
            "Slide the outer skin from OFFSET to EXTRUDE, both of them on " +
                "the surface normal. At 0, the default, the skin is a true " +
                "OFFSET SURFACE: every outline point moves along the " +
                "surface normal AT THAT POINT, so cells that share a " +
                "corner move it to the same place, stay welded, and the " +
                "assembly is one continuous thickened shell. At 1 each " +
                "cell is EXTRUDED along its OWN normal, a rigid " +
                "translation whose outer face is congruent to its inner " +
                "one, and GAPS OPEN at the joints in proportion to " +
                "curvature times thickness, because neighbouring cells' " +
                "normals disagree. In between, the joint bevel slides from " +
                "radial and shared to parallel and open. Outside 0 to 1 " +
                "the value is clamped. Ignored while Th is 0.",
            GH_ParamAccess.item,
            0.0);
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
                out double extrude))
        {
            return;
        }
        SolveNative(
            data, result!, pattern, size, courseHeight, minPiece,
            thickness, extrude);
    }

    private void SolveNative(
        IGH_DataAccess data,
        ResultDto result,
        int pattern,
        double size,
        double courseHeight,
        double minPiece,
        double thickness,
        double extrude)
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
                            face, cell.Outline, cell.Sections, net,
                            thickness, extrude)
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
                extrude);
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
    /// THE REMEDY IS A SMALLER THICKNESS, AND THAT IS THE WHOLE OF IT.
    /// Rewritten 2026-09-04 for the slider (spec section 7 item 3). Every
    /// earlier draft of this sentence was written against a TOGGLE and
    /// advised moving it: the first said "or Along Normal off", on a
    /// toggle that defaulted off, so on a default canvas it told the
    /// author to switch off a switch already off; the second said "Offset
    /// ON, which costs nothing", an argument about the cost of a branch
    /// that no longer exists. Both directions went with the toggle.
    ///
    /// WHAT MAY NOT BE SAID HERE, and it is the point of the rewrite. THE
    /// SLIDER IS NOT A REMEDY FOR A REFUSAL. Extrude near 1 opens the
    /// joints BY DESIGN, in proportion to curvature times thickness, and
    /// nothing measured anywhere says it rescues a cell that will not
    /// close. The loft-route failures remain UNATTRIBUTED: only
    /// scripts/rhino_skin_surface.py can count a cell's refusal at all,
    /// and it has not been run. Advising an author to slide towards the
    /// extrusion would trade a solid he can build for gaps he did not ask
    /// for, on a hunch this engine has never measured.
    ///
    /// <paramref name="extrude"/> is a parameter because the sentence
    /// NAMES the slider's position, so the author reads which end of the
    /// range the count was taken at. It does not change the advice.
    /// </summary>
    internal static string? ThickenFailureLine(
        int failed, int firstCourse, double thickness, double extrude)
    {
        if (failed <= 0)
            return null;
        string remedy =
            " A smaller Thickness is the remedy, and it is the only one " +
            "this component has to offer. Extrude was " +
            extrude.ToString("F2", CultureInfo.InvariantCulture) +
            "; sliding it towards 1 OPENS THE JOINTS by design, in " +
            "proportion to curvature times thickness, and is not known to " +
            "rescue a cell that will not close. Where these cells go " +
            "instead is a question only a run inside Rhino can settle.";
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
        if (TopTakesLoft(cell.Sections))
            return LoftSections(cell.Sections!);
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
    /// THE CELL'S OWN NORMAL, N (spec 2026-09-04, section 3, rule 3.2): the
    /// renormalised MEAN of the cell's own corners' FIELD normals.
    ///
    /// It derives from the same oriented field the corners themselves read,
    /// which is the whole reason it is a mean of field normals rather than
    /// the Newell normal of the outline. A Newell sum follows the outline's
    /// WINDING, and a winding is not consistent from cell to cell on a
    /// vault whose contours are open strips: the deleted CellNormalUnit
    /// thickened half a shell outward and the other half inward at one
    /// positive Th for exactly that reason. A mean of field normals cannot,
    /// because the field is one-sided over the whole net (rule 4). So
    /// Extrude 1 cannot disagree with Extrude 0 about which side is out.
    ///
    /// DEGENERATE, and the ladder is the spec's own. Where the mean is
    /// shorter than 1e-12, the corners' normals have cancelled and the cell
    /// has no mean direction: the Newell normal of the outline is taken
    /// instead, turned to agree with the field's global up (which rule 4
    /// makes non-negative Z), and where that is degenerate too the answer
    /// is (0, 0, 1), an arbitrary but FINITE direction.
    /// </summary>
    internal static double[] CellNormal(
        SkinNet net, IReadOnlyList<double[]> outline)
    {
        double x = 0.0, y = 0.0, z = 0.0;
        foreach (double[] corner in outline)
        {
            double[] normal = SkinPatterns.NormalAt(net, corner);
            x += normal[0];
            y += normal[1];
            z += normal[2];
        }
        double length = Math.Sqrt((x * x) + (y * y) + (z * z));
        if (length > 1.0e-12)
            return new[] { x / length, y / length, z / length };

        double nx = 0.0, ny = 0.0, nz = 0.0;
        for (int at = 0; at < outline.Count; at++)
        {
            double[] a = outline[at];
            double[] b = outline[(at + 1) % outline.Count];
            nx += (a[1] - b[1]) * (a[2] + b[2]);
            ny += (a[2] - b[2]) * (a[0] + b[0]);
            nz += (a[0] - b[0]) * (a[1] + b[1]);
        }
        double newell = Math.Sqrt((nx * nx) + (ny * ny) + (nz * nz));
        if (!(newell > 1.0e-12))
            return new[] { 0.0, 0.0, 1.0 };
        double sign = nz < 0.0 ? -1.0 : 1.0;
        return new[]
        {
            sign * nx / newell, sign * ny / newell, sign * nz / newell
        };
    }

    /// <summary>
    /// THE OFFSET AT ONE POINT (spec 2026-09-03 rules 2 and 4, amended by
    /// spec 2026-09-04 rule 3.1), pulled out of
    /// <see cref="ThickenCellSurface"/> so it is testable without a Brep:
    /// the translation ONE outline point is copied by, in the SAME units
    /// and SAME sign convention Th itself carries.
    ///
    /// THE SLIDER BLENDS TWO DIRECTIONS, BOTH OF THEM ON THE SURFACE
    /// NORMAL. At Extrude 0 the direction is n(p), the field normal AT THE
    /// POINT, read through <see cref="SkinPatterns.NormalAt"/> and off
    /// nothing else, which is the offset surface. At Extrude 1 it is N, the
    /// CELL'S own normal, one vector for the whole cell, which makes the
    /// block a rigid translation of its cell and opens the joints. In
    /// between:
    ///
    ///     direction(p, t) = unit( (1 - t) n(p) + t N )
    ///     top(p, t)       = p + Th direction(p, t)
    ///
    /// THE BLEND IS RENORMALISED, so the thickness is exactly |Th| at every
    /// t and not only at the two ends. A straight interpolation of the two
    /// TRANSLATIONS would thin the stone in the middle of the slider by up
    /// to the half-angle's cosine, which is a silent structural change
    /// dressed as a display setting.
    ///
    /// WHERE THE BLEND DEGENERATES, n(p) and N opposed and the sum shorter
    /// than 1e-12, the answer falls back to n(p): the point's own normal is
    /// the one of the two that is defined without reference to the cell,
    /// and it is the end of the slider the default sits at.
    ///
    /// THE WELD LIVES AT t = 0 AND ONLY THERE, and that is the design. At
    /// t = 0 the direction is a function of the POINT alone, so two cells
    /// that share a corner hand this method the same three doubles and get
    /// the same three back. At any t above 0 the cell's own normal enters
    /// and neighbours may split; the gaps ARE the extrusion the slider is
    /// sliding towards.
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
        SkinNet net,
        double[] point,
        double[] cellNormal,
        double thickness,
        double extrude)
    {
        double[] normal = SkinPatterns.NormalAt(net, point);
        double x = ((1.0 - extrude) * normal[0]) + (extrude * cellNormal[0]);
        double y = ((1.0 - extrude) * normal[1]) + (extrude * cellNormal[1]);
        double z = ((1.0 - extrude) * normal[2]) + (extrude * cellNormal[2]);
        double length = Math.Sqrt((x * x) + (y * y) + (z * z));
        if (!(length > 1.0e-12))
        {
            return new[]
            {
                normal[0] * thickness,
                normal[1] * thickness,
                normal[2] * thickness
            };
        }
        return new[]
        {
            x / length * thickness,
            y / length * thickness,
            z / length * thickness
        };
    }

    /// <summary>
    /// One outline moved: corner by corner, each along its OWN blended
    /// direction (<see cref="ThicknessOffset"/>), under the ONE cell normal
    /// <see cref="CellNormal"/> reads off the whole outline. A static of
    /// plain double[] so the harness can weigh two neighbouring cells'
    /// answers against one another without a Brep anywhere.
    /// </summary>
    internal static IReadOnlyList<double[]> OffsetOutline(
        SkinNet net,
        IReadOnlyList<double[]> outline,
        double thickness,
        double extrude) =>
        OffsetPoints(
            net, outline, CellNormal(net, outline), thickness, extrude);

    /// <summary>
    /// A LIST OF POINTS MOVED UNDER ONE CELL'S NORMAL. The cell normal is
    /// handed in rather than read off the points, because a cell's SECTION
    /// RAILS must move under the same N its own outline moved under (spec
    /// 2026-09-04 section 5): a rail that computed its own would be a
    /// different cell as far as the arithmetic is concerned, and the top
    /// face would stand off the walls that meet it.
    /// </summary>
    internal static IReadOnlyList<double[]> OffsetPoints(
        SkinNet net,
        IReadOnlyList<double[]> points,
        double[] cellNormal,
        double thickness,
        double extrude)
    {
        var moved = new List<double[]>(points.Count);
        foreach (double[] point in points)
        {
            double[] offset = ThicknessOffset(
                net, point, cellNormal, thickness, extrude);
            moved.Add(new[]
            {
                point[0] + offset[0],
                point[1] + offset[1],
                point[2] + offset[2]
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
    ///
    /// A Th THAT IS NOT FINITE asks for nothing either. NaN compares equal
    /// to nothing, itself included, so "thickness != 0.0" is TRUE of it and
    /// the bare comparison sent a NaN into the thickener, where every
    /// offset corner becomes NaN, every wall quad is refused, and the cell
    /// is lost with no reason given. An infinity is the same story with
    /// coordinates the tolerance cannot reach. Neither can be built, so
    /// neither is attempted and the face survives untouched.
    /// </summary>
    internal static bool Thickening(double thickness) =>
        double.IsFinite(thickness) && thickness != 0.0;

    /// <summary>
    /// WHAT THICKENS: one cell's Surface face becomes a CLOSED SOLID
    /// between the face and a copy of it moved by
    /// <see cref="ThicknessOffset"/>, bottom, top and one side wall per
    /// outline edge, run off the cell's own Outline, exactly the boundary
    /// CellSurface itself already treats as the cell's ring regardless of
    /// which route built the face (loft, fan or cap), so this one method
    /// serves every cell shape without a case on Sections.
    ///
    /// THE TOP FACE TAKES THE SAME ROUTE ITS OWN BOTTOM TOOK (spec
    /// 2026-09-04, section 5). This is the correction the slider wave
    /// carries. Under the offset the top used to be built as a FAN even
    /// where the bottom is a LOFT, so a lofted cell was capped by a
    /// triangulated crust that does not share the bottom's boundary: that
    /// is the crust in Param's screenshot and the leading suspect for the
    /// 148 refusals, since a fan's chords and a loft's rails cannot join at
    /// the 1e-6 the join is asked for. Now a loft-route cell lofts its top
    /// from its own SECTION RAILS moved corner by corner, and only a
    /// fan-route cell fans. The route is read off Sections by the one
    /// predicate <see cref="CellSurface"/> reads it off
    /// (<see cref="TopTakesLoft"/>), so no new case is invented and the two
    /// cannot drift apart.
    ///
    /// EVERY POINT MOVES BY ITS OWN BLENDED DIRECTION (rule 3.1), under the
    /// ONE cell normal <see cref="CellNormal"/> reads off this cell's
    /// outline. The rails are moved under that same N and not under one of
    /// their own, or the top would stand off the walls that meet it.
    ///
    /// Where the fan's apex cannot be found (a cell whose plan has no
    /// interior point, or one lying off the net) the cell is refused
    /// rather than thickened wrongly.
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
        IReadOnlyList<IReadOnlyList<double[]>>? sections,
        SkinNet net,
        double thickness,
        double extrude)
    {
        if (outline.Count < 3)
            return null;
        double[] cellNormal = CellNormal(net, outline);
        IReadOnlyList<double[]> moved =
            OffsetPoints(net, outline, cellNormal, thickness, extrude);

        IReadOnlyList<IReadOnlyList<double[]>>? movedSections =
            MovedSections(net, sections, cellNormal, thickness, extrude);
        Brep? top = movedSections is not null
            ? LoftSections(movedSections)
            : OffsetTopFace(net, outline, moved, cellNormal, thickness, extrude);
        if (top is null)
            return null;
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
    /// IS THIS CELL A LOFT? The ONE predicate the bottom face and the top
    /// face both read the route off (spec 2026-09-04, section 5). It is
    /// exactly <see cref="CellSurface"/>'s own gate lifted out rather than
    /// a second reading of Sections: a cell with two or more sections, each
    /// of two or more points, lofts, and everything else fans. Two readings
    /// of one route is how the top came to be a fan over a lofted bottom in
    /// the first place.
    ///
    /// A section under two points is refused rather than fanned, which is
    /// what CellSurface does with it too: the cell has a route it cannot
    /// take and is left to the caller's null.
    /// </summary>
    internal static bool TopTakesLoft(
        IReadOnlyList<IReadOnlyList<double[]>>? sections) =>
        sections is not null && sections.Count >= 2;

    /// <summary>
    /// A CELL'S SECTION RAILS, MOVED, or null where the cell is not a loft
    /// at all. Every point of every rail moves by its own blended direction
    /// under the ONE cell normal handed in, so the moved rails are the top
    /// face's own boundary and meet the moved outline the walls stand on.
    ///
    /// Internal and returning plain double[] so the harness can count the
    /// rails and their points without a Brep: check 8 of the spec asserts
    /// the top of a loft cell carries the LOFT STRUCTURE and not a fan, and
    /// Brep face counts need Rhino.
    /// </summary>
    internal static IReadOnlyList<IReadOnlyList<double[]>>? MovedSections(
        SkinNet net,
        IReadOnlyList<IReadOnlyList<double[]>>? sections,
        double[] cellNormal,
        double thickness,
        double extrude)
    {
        if (!TopTakesLoft(sections))
            return null;
        var moved = new List<IReadOnlyList<double[]>>(sections!.Count);
        foreach (IReadOnlyList<double[]> section in sections)
        {
            if (section.Count < 2)
                return null;
            moved.Add(
                OffsetPoints(net, section, cellNormal, thickness, extrude));
        }
        return moved;
    }

    /// <summary>
    /// A STRAIGHT UNCLOSED LOFT OF SECTIONS, which is route 5.2.3(a) to
    /// (c). Shared by the bottom face and by the top face so that the two
    /// are built by one arithmetic and cannot differ in structure.
    /// </summary>
    private static Brep? LoftSections(
        IReadOnlyList<IReadOnlyList<double[]>> sections)
    {
        var curves = new List<Curve>(sections.Count);
        foreach (IReadOnlyList<double[]> section in sections)
        {
            if (section.Count < 2)
                return null;
            curves.Add(OpenOutlineCurve(section));
        }
        Brep[] lofted = Brep.CreateFromLoft(
            curves,
            Point3d.Unset,
            Point3d.Unset,
            LoftType.Straight,
            false);
        return lofted is { Length: 1 } && lofted[0].IsValid
            ? lofted[0]
            : null;
    }

    /// <summary>
    /// The fan-route cell's TOP FACE: the deterministic fan of rule
    /// 5.2.3(d) and (e) over the moved outline, from the cell's own plan
    /// interior point lifted onto the net and then moved by that point's
    /// own blended direction. Null where the cell has no plan interior
    /// point, where that point lies off the net, or where the fan will not
    /// join.
    ///
    /// IT IS NO LONGER THE ONLY TOP. Under spec 2026-09-04 section 5 this
    /// route serves a cell whose BOTTOM is a fan, and a loft-route cell
    /// lofts its top from its own moved rails instead. The fan over a
    /// lofted bottom was the triangulated crust in Param's screenshot.
    ///
    /// The MOVED outline is handed in rather than recomputed. Its caller
    /// has already built it, for the side walls, and rebuilding it here
    /// asked SkinPatterns.NormalAt for every corner of every cell a second
    /// time, which is a linear scan of the net's faces apiece; worse, a
    /// later edit could have moved one of the two and left the top face
    /// standing on different corners from the walls that meet it.
    /// </summary>
    private static Brep? OffsetTopFace(
        SkinNet net,
        IReadOnlyList<double[]> outline,
        IReadOnlyList<double[]> moved,
        double[] cellNormal,
        double thickness,
        double extrude)
    {
        double[]? inside = SkinPatterns.PlanInteriorPoint(outline);
        if (inside is null)
            return null;
        double[]? apex = SkinPatterns.LiftPlanPoint(net, inside[0], inside[1]);
        if (apex is null)
            return null;
        double[] apexOffset =
            ThicknessOffset(net, apex, cellNormal, thickness, extrude);
        var top = new Point3d(
            apex[0] + apexOffset[0],
            apex[1] + apexOffset[1],
            apex[2] + apexOffset[2]);
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
    /// <summary>
    /// THE SLIDER'S OWN BOUNDS (spec 2026-09-04 section 2), as a static so
    /// the harness can drive them without a canvas. Anything above 1
    /// clamps to 1, anything below 0 clamps to 0, and a value that is not
    /// finite falls back to the port default of 0.
    ///
    /// The message is returned rather than raised, so one arithmetic
    /// serves both the component's message and the harness's check. It is
    /// a REMARK and not a Warning, unlike Min Piece's: a slider driven
    /// past its own end is an author reaching for the end of the range and
    /// getting it, where a Min Piece outside 0 to 0.5 is a number he has
    /// probably mistyped.
    /// </summary>
    internal static double ClampExtrude(
        double asked, out bool clamped, out string remark)
    {
        double answer =
            !double.IsFinite(asked)
                ? 0.0
                : Math.Min(Math.Max(asked, 0.0), 1.0);
        clamped = !double.IsFinite(asked) || asked < 0.0 || asked > 1.0;
        remark = clamped
            ? "Extrude runs 0 (offset surface) to 1 (per-cell extrusion); " +
              "using " +
              answer.ToString("F3", CultureInfo.InvariantCulture) +
              ". Both ends are on the surface normal, so there is nothing " +
              "beyond either of them to reach for."
            : string.Empty;
        return answer;
    }

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
        out double extrude,
        bool report = true)
    {
        result = null;
        pattern = 0;
        size = DefaultSize;
        courseHeight = DefaultCourseHeight;
        minPiece = 1.0 / 3.0;
        thickness = 0.0;
        extrude = 0.0;
        ResultGoo? resultGoo = null;
        int patternInput = 0;
        double sizeInput = DefaultSize;
        double courseHeightInput = DefaultCourseHeight;
        double minPieceInput = 1.0 / 3.0;
        double thicknessInput = 0.0;
        double extrudeInput = 0.0;
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
        data.GetData(6, ref extrudeInput);
        minPieceInput = ClampMinPiece(
            minPieceInput, out bool minPieceClamped, out string minPieceWarning);
        if (minPieceClamped && report)
            AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, minPieceWarning);
        // Spec 2026-09-04 section 2: EX runs 0 to 1 and a value outside is
        // clamped with a REMARK naming the clamp, so an author who drove a
        // slider past its own end reads what the component actually used.
        extrudeInput = ClampExtrude(
            extrudeInput, out bool extrudeClamped, out string extrudeRemark);
        if (extrudeClamped && report)
            AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, extrudeRemark);
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
        extrude = extrudeInput;
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
