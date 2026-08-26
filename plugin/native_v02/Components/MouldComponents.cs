#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Mould Animate: replay the reconfigurable mould building itself, from one
    /// timeline slider.
    ///
    /// Everything the animation needs is already in the solved Result, so there
    /// is nothing to dial. The final geometry says how high the columns must
    /// lift the bars and how far the steppers must reel each infill cable; the
    /// component works both out and interpolates between the flat net on the
    /// ground and that final state.
    ///
    ///   bare    the surface the net takes between the principal bars with
    ///           nothing reeled in, found by relaxing every free node to the
    ///           average of its neighbours with the bars and anchors pinned.
    ///           That is the uniform force-density equilibrium, so by Schek's
    ///           Theorem 1 it is the minimum-way surface: flat or saddled,
    ///           never domed. This carries the HEIGHT.
    ///   relief  what the steppers must reel on top of it to reach the Result.
    ///           This carries the SAG.
    ///
    /// The net starts as the ORIGINAL PATTERN, read back up the chain from the
    /// Result through its Problem's topology, so frame zero is the flat plan
    /// the whole thing was drawn from rather than a level guessed from the
    /// solved geometry. A frame is
    ///
    ///     z = pattern + height * (bare - pattern) + sag * relief
    ///
    /// so at height zero everything stays down on the pattern while the first
    /// reeling happens, which is the order the machine actually builds in.
    ///
    /// This component animates. It runs no equilibrium check and it places no
    /// columns; Column Finder owns that.
    /// </summary>
    public sealed class MouldAnimateComponent : NativeComponentBase
    {
        public MouldAnimateComponent()
            : base(
                "Animate",
                "AN",
                "Replay the mould building itself from one timeline slider: the "
                    + "steppers reeling the net into shape on the ground, the "
                    + "columns lifting it, then the final tensioning. Sag and "
                    + "height are read from the solved Result, not dialled.",
                ComponentCategories.Visualise,
                "mould_animate")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        private string _bareKey = string.Empty;
        private double[]? _bareSurface;
        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Line> _previewPrincipal = new();
        private readonly List<Line> _previewColumns = new();
        private readonly List<Point3d> _previewSupports = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public override Guid ComponentGuid =>
            new("b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4");

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _previewMesh = null;
            _previewCables.Clear();
            _previewPrincipal.Clear();
            _previewColumns.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the frame in the viewport the way TNA Solve draws its solved
        /// network, with the same shaded material, wire colour and support
        /// points, so an animation reads as the same object at a different
        /// moment rather than as a different kind of drawing. The geometry
        /// outputs stay hidden, as on Deconstruct, so nothing double-draws.
        /// </summary>
        public override void DrawViewportMeshes(IGH_PreviewArgs args)
        {
            if (Hidden || _previewMesh is null || _previewMesh.Faces.Count == 0)
                return;
            args.Display.DrawMeshShaded(
                _previewMesh,
                new DisplayMaterial(Color.FromArgb(225, 222, 215), 0.35));
        }

        public override void DrawViewportWires(IGH_PreviewArgs args)
        {
            if (Hidden)
                return;
            base.DrawViewportWires(args);
            if (_previewMesh is not null && _previewMesh.Faces.Count > 0)
            {
                args.Display.DrawMeshWires(
                    _previewMesh, Color.FromArgb(95, 95, 100));
            }
            else
            {
                // No faces to shade, an FD result for instance, so the net
                // itself carries the drawing.
                foreach (Line cable in _previewCables)
                    args.Display.DrawLine(cable, Color.FromArgb(95, 95, 100));
            }
            foreach (Line bar in _previewPrincipal)
            {
                args.Display.DrawLine(
                    bar,
                    TnaWorkflowPreview.PrincipalColour,
                    TnaWorkflowPreview.PrincipalWeight);
            }
            // The same blue Column Finder draws its columns in, so a raising
            // column reads as the same member at a different moment.
            foreach (Line column in _previewColumns)
                args.Display.DrawLine(column, Color.FromArgb(40, 85, 175), 3);
            foreach (Point3d point in _previewSupports)
            {
                args.Display.DrawPoint(
                    point,
                    PointStyle.RoundControlPoint,
                    4,
                    Color.FromArgb(30, 165, 85));
            }
        }

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result. Its geometry IS the final state, so "
                    + "the sag and the lift are read from it rather than set.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Time",
                "T",
                "0 to 100, the whole build in one slider. Phase one reels the "
                    + "net part way down while it is flat, phase two lifts it "
                    + "on the columns, phase three reels the rest and tensions "
                    + "both axes against the bars.",
                GH_ParamAccess.item,
                100.0);
            parameters.AddNumberParameter(
                "Pre-Sag",
                "PS",
                "0 to 100, as a percentage of the FINAL sag: how much is reeled "
                    + "in before the columns lift. The remainder is reeled "
                    + "after, which is the part that tightens the form against "
                    + "the bars.",
                GH_ParamAccess.item,
                40.0);
            parameters.AddLineParameter(
                "Columns",
                "C",
                "Optional. The columns from Column Finder. Given them, the "
                    + "animation raises them WITH the net instead of leaving "
                    + "them at their finished positions: each foot slides "
                    + "linearly across the ground from under its own notch to "
                    + "where it finally stands, while the column extends to "
                    + "keep its head on that notch. Both at once, which is the "
                    + "two jobs the mechanism actually has to do.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Extension",
                "E",
                "How much of a column's final length its strut can extend, in "
                    + "percent. A column is not telescopic over its whole "
                    + "length: it has a fixed body and a ram. 40 means the "
                    + "strut is 60 percent of full when retracted and reaches "
                    + "100 when driven out, so early in the build it cannot be "
                    + "short and lies out along its rail instead.",
                GH_ParamAccess.item,
                40.0);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
            parameters[3].Optional = true;
            parameters[4].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at this frame, rebuilt from the Result's "
                    + "own faces. Empty for an FD result, which carries no "
                    + "faces to rebuild from.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Cables",
                "C",
                "Every net member at this frame, infill and bar alike.",
                GH_ParamAccess.list);
            parameters.AddCurveParameter(
                "Principal Lines",
                "PL",
                "The notched bars at this frame, bending as they rise.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Principal Nodes",
                "PN",
                "Every notch: one crossing cable, and a pair of stepper motors "
                    + "pulling it, one each side.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Anchor Nodes",
                "AN",
                "The Result's supports: the side anchors that stay on the "
                    + "ground and take the perimeter cables' prestress.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Perimeter Nodes",
                "PRN",
                "Nodes on the naked boundary of the net.",
                GH_ParamAccess.list);
            parameters.AddParameter(
                new MouldStateParam(),
                "State",
                "S",
                "This frame bundled for Stress Analysis: geometry, member "
                    + "forces, which members are bars and which are cables, and "
                    + "which nodes are notches, anchors and perimeter. Carries "
                    + "no columns; use Column Finder's State for those.",
                GH_ParamAccess.item);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "Which phase of the build this frame is in, the stepper count "
                    + "and how far the bars have risen, and a warning naming "
                    + "any node the net cannot reach.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Columns",
                "C",
                "The columns at THIS frame: foot part way along its slide, "
                    + "head on the notch wherever the net has got to. Empty "
                    + "unless columns are wired in. Their lengths are the "
                    + "extension the struts have to deliver.",
                GH_ParamAccess.list);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double timePct = 100.0;
            double preSag = 40.0;
            data.GetData(1, ref timePct);
            data.GetData(2, ref preSag);
            var columnLines = new List<Line>();
            data.GetDataList(3, columnLines);
            double extendPct = 40.0;
            data.GetData(4, ref extendPct);

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                Point3d[] target = equilibrium.Vertices
                    .Select(v => new Point3d(v.X, v.Y, v.Z))
                    .ToArray();
                int n = target.Length;
                if (n == 0)
                    throw new InvalidOperationException("Result carries no vertices.");

                // Keep the ORIGINAL edge index alongside each kept edge. The
                // filter drops invalid and self edges, so a filtered position
                // no longer matches the Result's own MemberForces array, and
                // indexing forces by it would silently attach every force
                // after the first dropped edge to the wrong member.
                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);
                if (edges.Length == 0)
                    throw new InvalidOperationException("Result carries no edges.");

                // Start from the ORIGINAL PATTERN: the plan as drawn, taken
                // off the SPINE PROBLEM that every solver attaches to its own
                // Result. Deliberately not the equilibrium's analysis topology,
                // which is the network the worker actually solved and so
                // already carries the answer; starting there put frame zero at
                // the finished vault and left the animation with nothing to do.
                var anchorIds = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds
                        .Where(i => i >= 0 && i < n));
                double ground = MouldGeometry.GroundLevel(target, anchorIds);
                IReadOnlyList<Point3Dto>? pattern =
                    result.Problem?.Anchored?.Pattern?.Topology?.Vertices;
                bool fromPattern = pattern is not null && pattern.Count == n;

                // A start that already matches the solved shape node for node
                // is not a plan, it is the answer. Lie the net flat and say so,
                // rather than replay a still image and call it an animation.
                double zSpan = Math.Max(target.Max(p => p.Z) - ground, 1.0e-9);
                double startDrift = 0.0;
                if (fromPattern)
                {
                    for (int i = 0; i < n; i++)
                    {
                        startDrift = Math.Max(
                            startDrift, Math.Abs(pattern![i].Z - target[i].Z));
                    }
                }
                bool startIsFinal = fromPattern && startDrift < 1.0e-4 * zSpan;
                if (startIsFinal)
                    fromPattern = false;

                // Frame zero is the pattern WHOLE: its plan as well as its
                // level. Reeling an infill cable in is one operation, and while
                // the net is still flat on the ground the only place it can
                // show is in PLAN, as the net draws in from the plan as drawn
                // toward the solved plan. Holding the plan at the solved one
                // and moving only Z is what lost the first phase: the net sat
                // flat and perfectly still until the columns began to lift.
                Point3d[] start = fromPattern
                    ? pattern!.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray()
                    : target.Select(p => new Point3d(p.X, p.Y, ground)).ToArray();
                double planTravel = 0.0;
                for (int i = 0; i < n; i++)
                {
                    planTravel = Math.Max(
                        planTravel,
                        Math.Sqrt(MouldGeometry.PlanDistanceSquared(
                            start[i], target[i])));
                }
                Mesh? mesh = MouldGeometry.ThrustMeshFromResult(
                    result, out int[] meshToNode);

                List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);

                // The runs travel in the contract, resolved once by Supports
                // from the anchors or by Pattern from drawn curves. Nothing is
                // snapped here, which is why there is no curve input: indices
                // survive a surface that rises and curves do not.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, target.Length);
                var principalIds = new HashSet<int>(bars.SelectMany(b => b));
                if (principalIds.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines, so nothing is "
                            + "held and there is nothing to lift. Set Ribs on "
                            + "Supports, or draw Principal Lines on Pattern.");
                }

                var pinned = new bool[n];
                foreach (int i in principalIds)
                    pinned[i] = true;
                foreach (int i in anchorIds)
                    pinned[i] = true;

                // BareSurface runs 2000 relaxation sweeps and reads only the
                // solved shape and what is pinned, neither of which Time or
                // Pre-Sag touch. Caching it is the difference between dragging
                // the timeline and re-solving a surface on every frame.
                string bareKey = MouldGeometry.SurfaceKey(target, pinned);
                if (_bareSurface is null ||
                    _bareSurface.Length != n ||
                    !string.Equals(_bareKey, bareKey, StringComparison.Ordinal))
                {
                    _bareSurface = MouldGeometry.BareSurface(
                        target, neighbours, pinned);
                    _bareKey = bareKey;
                }
                double[] bare = _bareSurface;
                var relief = new double[n];
                for (int i = 0; i < n; i++)
                    relief[i] = target[i].Z - bare[i];

                // Sag and height both come out of the Result, so Time is the
                // only thing left to drive.
                double time = Math.Min(Math.Max(timePct, 0.0), 100.0) / 100.0;
                double pre = Math.Min(Math.Max(preSag, 0.0), 100.0) / 100.0;
                double sag;
                double lift;
                string phase;
                if (time < 1.0 / 3.0)
                {
                    sag = pre * (time * 3.0);
                    lift = 0.0;
                    phase = $"1 of 3, reeling flat on the ground: {sag * 100:0}% "
                        + $"of the final sag, heading for {pre * 100:0}%";
                }
                else if (time < 2.0 / 3.0)
                {
                    sag = pre;
                    lift = (time - (1.0 / 3.0)) * 3.0;
                    phase = $"2 of 3, columns lifting: {lift * 100:0}% of the "
                        + $"height, holding {pre * 100:0}% sag";
                }
                else
                {
                    double u = (time - (2.0 / 3.0)) * 3.0;
                    sag = pre + ((1.0 - pre) * u);
                    lift = 1.0;
                    phase = "3 of 3, tensioning both axes against the columns: "
                        + $"{sag * 100:0}% sag";
                }

                // Re-aim on this frame's own geometry, so a column follows
                // the line of thrust the whole way up instead of only arriving
                // on it at the end. Same formula Column Finder places by, which
                // is the point of it living in MouldGeometry.
                var liveAim = new Dictionary<int, Vector3d>();
                var liveLoad = new Dictionary<int, double>();

                var live = new Point3d[n];
                for (int i = 0; i < n; i++)
                {
                    // SAG drives the plan as well as the depth, because they
                    // are the same operation seen twice: a cable reeled in
                    // pulls the net toward its bar and lets it drop between
                    // them at once. LIFT is the columns, and it moves only the
                    // height, so at lift zero the whole net stays down where it
                    // was drawn while the first reeling happens.
                    double z = start[i].Z
                        + (lift * (bare[i] - start[i].Z))
                        + (sag * relief[i]);
                    live[i] = new Point3d(
                        start[i].X + (sag * (target[i].X - start[i].X)),
                        start[i].Y + (sag * (target[i].Y - start[i].Y)),
                        z);
                }

                if (columnLines.Count > 0)
                {
                    var edgeForce = new double[edges.Length];
                    for (int e = 0; e < edges.Length; e++)
                    {
                        int src = e < edgeSource.Length ? edgeSource[e] : e;
                        edgeForce[e] = src < equilibrium.MemberForces.Count
                            ? equilibrium.MemberForces[src]
                            : 0.0;
                    }
                    var incident = new List<(int Other, double Force)>[n];
                    for (int i = 0; i < n; i++)
                        incident[i] = new List<(int, double)>();
                    for (int e = 0; e < edges.Length; e++)
                    {
                        incident[edges[e].Item1].Add(
                            (edges[e].Item2, edgeForce[e]));
                        incident[edges[e].Item2].Add(
                            (edges[e].Item1, edgeForce[e]));
                    }
                    foreach (List<int> run in bars)
                    {
                        Vector3d[] pull =
                            MouldGeometry.BarLoads(run, live, incident);
                        Vector3d[] across =
                            MouldGeometry.BarTransverse(run, live, pull);
                        for (int k = 0; k < run.Count; k++)
                        {
                            liveAim[run[k]] = MouldGeometry.AimFrom(across[k]);
                            liveLoad[run[k]] = across[k].Length;
                        }
                    }
                }

                int[] perimeterIds = MouldGeometry.PerimeterNodes(
                    mesh, meshToNode, neighbours, n);

                var barCurves = new List<Curve>();
                foreach (List<int> run in bars)
                {
                    var polyline = new Polyline(run.Select(i => live[i]));
                    if (polyline.IsValid && polyline.Count > 1)
                        barCurves.Add(polyline.ToNurbsCurve());
                }

                double barRise = principalIds.Count > 0
                    ? lift * (principalIds
                        .Select(i => bare[i] - start[i].Z).Average())
                    : 0.0;
                int wantsPush = relief.Count(r => r > 1e-9);

                var report = new List<string>
                {
                    phase,
                    string.Empty,
                    $"nodes {n}, cables {edges.Length}, bars {bars.Count} carrying "
                        + $"{principalIds.Count} notches",
                    $"anchors {anchorIds.Count}, perimeter nodes "
                        + $"{perimeterIds.Length}",
                    $"ground read as {ground:0.###}, the level the anchors sit "
                        + "at, which is what the columns stand on",
                    "principal lines read from the contract, resolved "
                        + "upstream by Supports or Pattern",
                    startIsFinal
                        ? "the pattern this Result carries IS its own solved "
                            + "shape, so there was nothing to rise from; the "
                            + $"net starts flat at {ground:0.###} instead"
                        : fromPattern
                            ? "starting from the ORIGINAL PATTERN, the plan as "
                                + "drawn, read off the Result's own Problem, so "
                                + "frame zero is what Pattern holds"
                            : "this Result carries no source pattern, so the "
                                + $"net starts flat at {ground:0.###}, the base "
                                + "of the solved geometry",
                    $"net travels from {start.Min(p => p.Z):0.###}/"
                        + $"{start.Max(p => p.Z):0.###} at frame zero to "
                        + $"{ground:0.###}/{target.Max(p => p.Z):0.###} at the "
                        + $"end, reeling {relief.Max(Math.Abs) * 1000.0:0.#} mm "
                        + "at the deepest node",
                    $"net draws in {planTravel * 1000.0:0.#} mm in plan as it "
                        + "reels, which is the whole of phase 1 and is only "
                        + "visible if the pattern plan and the solved plan "
                        + "differ",
                    $"steppers required {principalIds.Count * 2} "
                        + "(two per notch, one pulling each side)",
                    $"bars risen {barRise * 1000.0:0.#} mm at this frame",
                };
                if (mesh is null)
                {
                    report.Add(
                        "this Result carries no faces, so there is no shaded "
                            + "surface and the perimeter is read from the net's "
                            + "topology instead. That is expected for FD.");
                }
                if (wantsPush > 0)
                {
                    report.Add(string.Empty);
                    report.Add(
                        $"WARNING: {wantsPush} nodes sit ABOVE the bare surface, "
                            + "so they are asking to be pushed up. A reel only "
                            + "pulls down. That is curvature a net cannot make "
                            + "between the bars, and it needs a mechanism this "
                            + "machine does not have.");
                }

                // The columns, raised with the net, branches and all.
                //
                // A column is NOT telescopic over its whole length. It has a
                // fixed body and a ram, so it can never be shorter than its
                // retracted length, and driving it to nothing early on buried
                // it under the floor. What the machine does is SLIDE and then
                // EXTEND, and both fall out of one equation rather than a
                // schedule: a foot sits at whatever horizontal distance keeps
                // its member at the retracted length, until that distance falls
                // inside the finished one and the ram takes over.
                //
                // A FORKED column is solved, not interpolated. Its notches are
                // wherever the net has got to; its fork goes where the branches
                // come closest to standing on their own lines of thrust, which
                // is the same force-weighted solve Column Finder placed it by,
                // run on THIS FRAME's geometry and this frame's forces. So the
                // fork rises with its own branches and the whole assembly stays
                // in equilibrium the whole way up instead of only at the end.
                double extend = Math.Min(Math.Max(extendPct, 0.0), 95.0) / 100.0;
                var liveColumns = new List<Line>();
                double shortest = double.MaxValue;
                double longest = 0.0;
                double slid = 0.0;
                double overRun = 0.0;
                int belowGround = 0;

                if (columnLines.Count > 0)
                {
                    double weld = 1.0e-6 * Math.Max(
                        new BoundingBox(target).Diagonal.Length, 1.0);
                    MouldGeometry.ColumnTree tree =
                        MouldGeometry.BuildColumnTree(columnLines, weld);

                    int count = tree.Nodes.Count;
                    var at = new Point3d[count];
                    var flow = new Vector3d[count];
                    var known = new bool[count];

                    // The notches are wherever the net has got to.
                    foreach (int notch in tree.Notches)
                    {
                        int node = MouldGeometry.NearestNodeInPlan(
                            tree.Nodes[notch], target);
                        if (node < 0)
                            continue;
                        at[notch] = live[node];
                        flow[notch] = liveAim.TryGetValue(node, out Vector3d a)
                            ? a * Math.Max(liveLoad.TryGetValue(
                                node, out double w) ? w : 0.0, 1.0e-9)
                            : Vector3d.ZAxis;
                        known[notch] = true;
                    }

                    // Then downward: a node can be placed once everything above
                    // it is placed, which for this shape needs no ordering pass
                    // beyond repeating until nothing new resolves.
                    for (int pass = 0; pass < count + 2; pass++)
                    {
                        bool moved = false;
                        for (int v = 0; v < count; v++)
                        {
                            if (known[v] || tree.Above[v].Count == 0)
                                continue;
                            if (tree.Above[v].Any(u => !known[u]))
                                continue;

                            var reach = new List<Point3d>();
                            var pushes = new List<Vector3d>();
                            var total = Vector3d.Zero;
                            foreach (int u in tree.Above[v])
                            {
                                reach.Add(at[u]);
                                pushes.Add(flow[u]);
                                total += flow[u];
                            }
                            flow[v] = total;

                            bool onGround = tree.Feet.Contains(v);
                            if (!onGround)
                            {
                                at[v] = reach.Count > 1
                                    ? MouldGeometry.ForkPoint(
                                        reach, pushes, ground)
                                    : reach[0];
                            }
                            else
                            {
                                // A foot: slide along its rail, then let the ram
                                // finish. Several trunks on one foot are served
                                // by their force-weighted centre, because that
                                // is the point the foot actually carries.
                                double sw = 0.0;
                                double sx = 0.0;
                                double sy = 0.0;
                                double sz = 0.0;
                                double full = 0.0;
                                foreach (int u in tree.Above[v])
                                {
                                    double w = Math.Max(flow[u].Length, 1.0e-9);
                                    sx += at[u].X * w;
                                    sy += at[u].Y * w;
                                    sz += at[u].Z * w;
                                    sw += w;
                                    full = Math.Max(
                                        full,
                                        tree.Nodes[v].DistanceTo(tree.Nodes[u]));
                                }
                                var head = new Point3d(sx / sw, sy / sw, sz / sw);
                                at[v] = MouldGeometry.FootOnRail(
                                    head, tree.Nodes[v], flow[v], full, extend,
                                    ground, ref slid);
                            }
                            known[v] = true;
                            moved = true;
                        }
                        if (!moved)
                            break;
                    }

                    foreach ((int lower, int upper) in tree.Members)
                    {
                        if (!known[lower] || !known[upper])
                            continue;
                        if (at[upper].Z - ground <= 1.0e-9)
                        {
                            belowGround++;
                            continue;
                        }
                        var member = new Line(at[lower], at[upper]);
                        liveColumns.Add(member);
                        double length = member.Length;
                        shortest = Math.Min(shortest, length);
                        longest = Math.Max(longest, length);

                        // What the ram on this member has to deliver, against
                        // what it was built with.
                        double built = tree.Nodes[lower]
                            .DistanceTo(tree.Nodes[upper]);
                        overRun = Math.Max(overRun, length - built);
                    }
                }

                if (liveColumns.Count > 0)
                {
                    report.Add(string.Empty);
                    report.Add(
                        $"{liveColumns.Count} column members at this frame, "
                            + $"{shortest:0.###} to {longest:0.###} long, with "
                            + $"rams worth {extendPct:0}% of built length. "
                            + "Feet lie out on their rails while retracted, "
                            + "slide in as the notches rise, then stop and let "
                            + "the rams finish. Furthest a foot still has to "
                            + $"slide: {slid:0.###}.");
                    if (overRun > 1.0e-9)
                    {
                        report.Add(
                            $"longest member overshoots its built length by "
                                + $"{overRun:0.###} at this frame. A fork moves "
                                + "with its own branches, so a branch can be "
                                + "asked for more than it finishes at; that is "
                                + "the reach its own ram needs.");
                    }
                }
                if (belowGround > 0)
                {
                    report.Add(
                        $"{belowGround} column members are not drawn: their "
                            + "upper end has not cleared the floor yet, so "
                            + "there is nothing for them to stand under.");
                }

                Mesh? framed = mesh is null
                    ? null
                    : MouldGeometry.DeformMesh(mesh, meshToNode, live);
                var cables = edges
                    .Select(e => new Line(live[e.Item1], live[e.Item2]))
                    .ToList();

                _previewMesh = framed;
                _previewCables.Clear();
                _previewCables.AddRange(cables);
                _previewPrincipal.Clear();
                foreach (List<int> run in bars)
                {
                    for (int k = 0; k + 1 < run.Count; k++)
                        _previewPrincipal.Add(
                            new Line(live[run[k]], live[run[k + 1]]));
                }
                _previewColumns.Clear();
                _previewColumns.AddRange(liveColumns);
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    anchorIds.OrderBy(i => i).Select(i => live[i]));
                _clippingBox = new BoundingBox(
                    live.Concat(liveColumns.Select(c => c.From)));

                data.SetData(0, framed);
                data.SetDataList(1, cables);
                data.SetDataList(2, barCurves);
                data.SetDataList(3, principalIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(4, anchorIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(5, perimeterIds.Select(i => live[i]));
                data.SetData(6, new MouldStateGoo(MouldGeometry.BuildState(
                    phase, ground, live, edges, edgeSource, equilibrium,
                    principalIds, anchorIds, perimeterIds,
                    Array.Empty<Point3d>(), Array.Empty<Point3d>(),
                    Array.Empty<double>())));
                data.SetData(7, string.Join(Environment.NewLine, report));
                data.SetDataList(8, liveColumns);
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }
    }

    /// <summary>
    /// Geometry shared by Mould Animate and Column Finder: reading the net out
    /// of a Result, snapping the principal bars to it, and the bare surface.
    /// </summary>
    internal static class MouldGeometry
    {
        /// <summary>
        /// The Result's edges, minus any that are out of range or join a node
        /// to itself, with the original index of each survivor returned
        /// alongside. Callers need that index because the Result's per-edge
        /// arrays (member forces, force densities) are still in the unfiltered
        /// order.
        /// </summary>
        public static (int, int)[] ValidEdges(
            EquilibriumResultDto equilibrium,
            int nodeCount,
            out int[] source)
        {
            var kept = new List<(int, int)>();
            var origin = new List<int>();
            for (int i = 0; i < equilibrium.Edges.Count; i++)
            {
                EdgeDto e = equilibrium.Edges[i];
                if (e.U < 0 || e.U >= nodeCount || e.V < 0 || e.V >= nodeCount)
                    continue;
                if (e.U == e.V)
                    continue;
                kept.Add((e.U, e.V));
                origin.Add(i);
            }
            source = origin.ToArray();
            return kept.ToArray();
        }

        public static List<int>[] BuildAdjacency(int count, (int, int)[] edges)
        {
            var neighbours = new List<int>[count];
            for (int i = 0; i < count; i++)
                neighbours[i] = new List<int>();
            foreach ((int u, int v) in edges)
            {
                neighbours[u].Add(v);
                neighbours[v].Add(u);
            }
            return neighbours;
        }

        /// <summary>
        /// The surface the net takes between the pinned nodes with nothing
        /// reeled in: every free node at the average of its neighbours. That is
        /// the uniform force-density equilibrium, so by Schek's Theorem 1 it is
        /// the minimum-way surface, flat or saddled and never domed.
        /// </summary>
        public static double[] BareSurface(
            Point3d[] target,
            List<int>[] neighbours,
            bool[] pinned)
        {
            int n = target.Length;
            var z = new double[n];
            for (int i = 0; i < n; i++)
                z[i] = target[i].Z;

            for (int sweep = 0; sweep < 2000; sweep++)
            {
                double shift = 0.0;
                for (int i = 0; i < n; i++)
                {
                    if (pinned[i] || neighbours[i].Count == 0)
                        continue;
                    double sum = 0.0;
                    foreach (int j in neighbours[i])
                        sum += z[j];
                    double updated = sum / neighbours[i].Count;
                    shift = Math.Max(shift, Math.Abs(updated - z[i]));
                    z[i] = updated;
                }
                if (shift < 1e-9)
                    break;
            }
            return z;
        }

        /// <summary>
        /// The ordered run of net nodes lying along one principal bar, ordered
        /// by curve parameter so the bar reads end to end. The catch radius
        /// comes from the net's own edge lengths, so it scales with the model
        /// and needs no tolerance input.
        /// </summary>
        /// <summary>
        /// The ordered run of net nodes lying along one principal bar.
        ///
        /// Matching happens IN PLAN, ignoring height. The bars are drawn on the
        /// pattern, which is flat, while the nodes they have to find live on
        /// the solved surface, which is not: comparing in three dimensions puts
        /// the whole raised vault out of reach of its own bars and returns
        /// nothing at all. A principal line is a line in plan; which nodes it
        /// picks up is a plan question, and their heights come from the Result.
        /// </summary>
        /// <summary>
        /// The principal-line runs for a solved Result.
        ///
        /// They are resolved once upstream, by Supports from the anchors or by
        /// Pattern from drawn curves, and the contract carries them down as
        /// vertex indices. So the matching happens once for the whole
        /// definition rather than in every component on every frame, and it
        /// cannot go wrong on a raised surface, because by here there is no
        /// curve left to match.
        /// </summary>
        public static List<List<int>> PrincipalRuns(
            EquilibriumResultDto equilibrium,
            int nodeCount)
        {
            IReadOnlyList<IReadOnlyList<int>>? runs =
                equilibrium.Problem?.Topology?.PrincipalRuns;
            if (runs is null)
                return new List<List<int>>();
            return runs
                .Where(run => run is not null && run.Count >= 2)
                .Select(run => run
                    .Where(i => i >= 0 && i < nodeCount)
                    .ToList())
                .Where(run => run.Count >= 2)
                .ToList();
        }

        /// <summary>
        /// Match one drawn bar to the run of net nodes along it, as a WALK on
        /// the mesh rather than a sort along the curve.
        ///
        /// The sort is the obvious implementation and it is wrong. A line
        /// drawn down a bay catches the column of nodes either side of it, and
        /// their positions along the curve interleave, so ordering the caught
        /// nodes by how far along they lie hands back a run that crosses the
        /// bay on every step: a zigzag, not a bar. It looks like a drawing
        /// fault and is not one. Downstream that run is pinned by Animate and
        /// solved as a beam by Column Finder, so the zigzag is load-bearing
        /// nonsense: notches on both sides of a bay, and a bar reported twice
        /// its true length.
        ///
        /// A bar is a CONNECTED CHAIN OF NOTCHES, so only a neighbour may
        /// follow a node. From each node the walk takes the neighbour that
        /// advances furthest along the curve, closest to the line where two
        /// advance equally. A sideways step advances nothing, so it is never
        /// preferred to a real one, and the run cannot double back. On a line
        /// drawn at an angle to the mesh the two directions advance together
        /// and the walk staircases, which is the honest discrete answer.
        ///
        /// <paramref name="meanOffset"/> reports how far the matched run sits
        /// from the curve that asked for it, in plan. It is not zero when the
        /// author drew between two columns of nodes: no bar can be there, the
        /// nearest run of nodes was taken instead, and the caller can say so
        /// rather than let the offset pass unremarked.
        /// </summary>
        public static List<int> SnapCurveToNodes(
            Curve curve,
            Point3d[] nodes,
            (int, int)[] edges,
            out double meanOffset,
            int samples = 512)
        {
            // Sample the curve once and compare in plain arithmetic, rather
            // than asking Rhino for a closest point per node. ClosestPoint on a
            // NURBS curve is not cheap, and this runs for every node of every
            // bar on every solve, which an animation does on every frame.
            //
            // Sampling is the ONLY part of this that needs Rhino, so it is the
            // only part that lives here. Everything below the sampling is
            // arithmetic on arrays, and keeping it that way is what lets the
            // smoke harness measure it: that harness never launches Rhino's
            // native core, so a walk that asked a Curve anything could only
            // ever be read, not run.
            double[]? ts = curve.DivideByCount(samples, true);
            Point3d[] sampled;
            if (ts is null || ts.Length == 0)
            {
                sampled = new[] { curve.PointAtStart, curve.PointAtEnd };
            }
            else
            {
                sampled = new Point3d[ts.Length];
                for (int s = 0; s < ts.Length; s++)
                    sampled[s] = curve.PointAt(ts[s]);
            }
            return SnapSampledLineToNodes(
                sampled, nodes, edges, out meanOffset);
        }

        /// <summary>
        /// The walk itself, over a line already reduced to points. See
        /// <see cref="SnapCurveToNodes"/> for why it is a walk and not a sort.
        /// </summary>
        public static List<int> SnapSampledLineToNodes(
            Point3d[] sampled,
            Point3d[] nodes,
            (int, int)[] edges,
            out double meanOffset)
        {
            meanOffset = 0.0;
            var run = new List<int>();
            if (nodes.Length == 0 || edges.Length == 0 || sampled.Length == 0)
                return run;

            double catchRadius = 0.6 * MedianEdgeLength(nodes, edges);
            double catchSquared = catchRadius * catchRadius;

            // Project every node onto the sampled curve once: which station it
            // stands at, and how far off the line it sits. Neither changes
            // during the walk, so neither is recomputed inside it.
            var station = new int[nodes.Length];
            var offset = new double[nodes.Length];
            for (int i = 0; i < nodes.Length; i++)
            {
                int best = -1;
                double bestDistance = double.MaxValue;
                for (int s = 0; s < sampled.Length; s++)
                {
                    double d = PlanDistanceSquared(nodes[i], sampled[s]);
                    if (d < bestDistance)
                    {
                        bestDistance = d;
                        best = s;
                    }
                }
                station[i] = best;
                offset[i] = bestDistance;
            }

            // Start at the node standing at the curve's beginning: of every
            // node inside the catch radius, the earliest station, and of those
            // the one nearest the line.
            int at = -1;
            for (int i = 0; i < nodes.Length; i++)
            {
                if (offset[i] >= catchSquared)
                    continue;
                if (at < 0 ||
                    station[i] < station[at] ||
                    (station[i] == station[at] && offset[i] < offset[at]))
                {
                    at = i;
                }
            }
            if (at < 0)
                return run;

            List<int>[] neighbours = BuildAdjacency(nodes.Length, edges);
            var used = new HashSet<int> { at };
            run.Add(at);
            while (true)
            {
                int next = -1;
                int bestAdvance = 0;
                foreach (int candidate in neighbours[at])
                {
                    if (used.Contains(candidate))
                        continue;
                    if (offset[candidate] >= catchSquared)
                        continue;
                    int advance = station[candidate] - station[at];
                    if (advance <= 0)
                        continue;
                    if (next < 0 ||
                        advance > bestAdvance ||
                        (advance == bestAdvance &&
                            offset[candidate] < offset[next]))
                    {
                        next = candidate;
                        bestAdvance = advance;
                    }
                }
                if (next < 0)
                    break;
                run.Add(next);
                used.Add(next);
                at = next;
            }

            meanOffset = run.Average(i => Math.Sqrt(offset[i]));
            return run;
        }

        /// <summary>
        /// Where the ground is: the level the ANCHORS sit at.
        ///
        /// In this machine they define it. They are tied down on the two sides
        /// and stay there through the whole build, so the plane they lie in IS
        /// the floor the columns stand on.
        ///
        /// The lowest point of the geometry is NOT the ground, though it agrees
        /// with it whenever a vault stays above its own supports. The moment
        /// any part of one hangs below them, taking the minimum puts the floor
        /// under the dip and stands every column on it. The median of the
        /// anchors, so one stray anchor cannot move the floor.
        /// </summary>
        public static double GroundLevel(
            Point3d[] nodes,
            IEnumerable<int> anchorIds)
        {
            double[] levels = anchorIds
                .Where(i => i >= 0 && i < nodes.Length)
                .Select(i => nodes[i].Z)
                .OrderBy(z => z)
                .ToArray();
            if (levels.Length > 0)
                return levels[levels.Length / 2];
            return nodes.Length == 0 ? 0.0 : nodes.Min(p => p.Z);
        }

        /// <summary>
        /// A key naming everything <see cref="BareSurface"/> reads, so a caller
        /// can tell whether a cached answer still applies.
        ///
        /// Deliberately NOT the topology hash. That names the analysis network,
        /// and the solved vertices are not part of it: re-solving at a
        /// different height leaves the hash alone and moves every point, which
        /// is exactly the case a topology-keyed cache would get wrong. Hashing
        /// the coordinates bit for bit costs one pass and cannot drift.
        /// </summary>
        public static string SurfaceKey(Point3d[] target, bool[] pinned)
        {
            long rolling = 17;
            for (int i = 0; i < target.Length; i++)
            {
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].X);
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].Y);
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].Z);
            }
            long held = 19;
            for (int i = 0; i < pinned.Length; i++)
            {
                if (pinned[i])
                    held = (held * 37) + i;
            }
            return $"{target.Length}:{rolling}:{held}";
        }

        /// <summary>
        /// What the NET hands each notch of a bar, as a force vector in three
        /// dimensions.
        ///
        /// Only the infill cables count. The edges running ALONG the bar are
        /// the bar itself, and a beam does not load itself, so they are left
        /// out. Positive is tension, so a member pulls its node toward the far
        /// end and a negative one pushes it away.
        /// </summary>
        public static Vector3d[] BarLoads(
            List<int> bar,
            Point3d[] nodes,
            List<(int Other, double Force)>[] incident)
        {
            var along = new HashSet<long>();
            for (int k = 0; k + 1 < bar.Count; k++)
                along.Add(EdgeKey(bar[k], bar[k + 1]));

            var pull = new Vector3d[bar.Count];
            for (int k = 0; k < bar.Count; k++)
            {
                int node = bar[k];
                var total = Vector3d.Zero;
                foreach ((int other, double force) in incident[node])
                {
                    if (along.Contains(EdgeKey(node, other)))
                        continue;
                    Vector3d step = nodes[other] - nodes[node];
                    double length = step.Length;
                    if (length <= 1.0e-12)
                        continue;
                    // MAGNITUDE, deliberately. Every infill member of this
                    // mould is a CABLE and pulls its notch toward the far end,
                    // whatever sign the analysis attached to it. A Result's
                    // sign convention is not fixed: Display reads it off the
                    // Result rather than assuming, and a TNA thrust network is
                    // the COMPRESSION MIRROR of the net that will be built, so
                    // its member forces come back negative under positive
                    // tension. Taking the signed value flipped every pull
                    // upward, which made the aim ask a column to hold its notch
                    // DOWN, which no column can do, so every one of them fell
                    // back to plumb. That is what put straight posts under a
                    // steeply inclined bar and collapsed the trees to a fan.
                    total += (Math.Abs(force) / length) * step;
                }
                pull[k] = total;
            }
            return pull;
        }

        public static long EdgeKey(int a, int b) =>
            a < b
                ? ((long)a << 32) | (uint)b
                : ((long)b << 32) | (uint)a;

        /// <summary>
        /// The part of that pull the COLUMNS have to take.
        ///
        /// This is where Gaudi's rule lands in this machine, and it lands
        /// differently from how it reads at first. Inclining a column pays only
        /// when the force arriving at its head is ALREADY inclined; under a
        /// purely vertical load a lean costs axial force (P over cos) and hands
        /// the foot a sideways push (P times tan) that something then has to
        /// resist. Gaudi's columns lean because the vault delivers thrust, and
        /// the lean is what removes the buttress.
        ///
        /// Here the buttresses already exist: every principal bar runs from one
        /// anchor strip to the other and BOTH ITS ENDS ARE TIED TO THE GROUND,
        /// so the pull running along a bar travels to those anchors, not to the
        /// columns. Leaning a column to take that component would double up on
        /// work the anchors are already doing.
        ///
        /// What no one takes is the pull ACROSS the bar. The bars curve in
        /// plan, so the infill cables pull them sideways and their own tension
        /// around that plan curve pushes sideways too, and nothing resists it
        /// but the bar's own bending. That component, plus the weight, is the
        /// columns' share and it is what their lean should follow.
        ///
        /// So: project the pull off the bar's local tangent and keep the rest.
        /// On a bar lying in a vertical plane the remainder is vertical and the
        /// columns come out plumb, which is the right answer for that case.
        /// </summary>
        public static Vector3d[] BarTransverse(
            List<int> bar,
            Point3d[] nodes,
            Vector3d[] pull)
        {
            var across = new Vector3d[bar.Count];
            for (int k = 0; k < bar.Count; k++)
            {
                int before = Math.Max(k - 1, 0);
                int after = Math.Min(k + 1, bar.Count - 1);
                Vector3d tangent = nodes[bar[after]] - nodes[bar[before]];
                double length = tangent.Length;
                if (length <= 1.0e-12)
                {
                    across[k] = pull[k];
                    continue;
                }
                // Divided rather than Unitized: Vector3d.Unitize P/Invokes into
                // Rhino's native core, which puts it out of reach of the smoke
                // harness, and this runs per node per bar per solve anyway.
                tangent = new Vector3d(
                    tangent.X / length, tangent.Y / length, tangent.Z / length);
                across[k] = pull[k] - ((pull[k] * tangent) * tangent);
            }
            return across;
        }

        /// <summary>
        /// Which way a column must push, given what the net pulls across its
        /// bar there. One rule, used by Column Finder to place the arms and by
        /// Animate to re-aim them on every frame, so a rising column follows
        /// the same thrust line the finished one stands on.
        ///
        /// Capped at sixty degrees from vertical: past that a column pushes
        /// sideways more than it holds up and the sliding joint cannot reach
        /// the angle. A net pulling its notch DOWN onto the column has no
        /// thrust line to follow at all, so that one stands plumb.
        /// </summary>
        public static Vector3d AimFrom(Vector3d pulled)
        {
            Vector3d supply = -pulled;
            if (supply.Z <= 1.0e-9)
                return Vector3d.ZAxis;

            double horizontal = Math.Sqrt(
                (supply.X * supply.X) + (supply.Y * supply.Y));
            double allowed = Math.Tan(Math.PI / 3.0) * supply.Z;
            if (horizontal > allowed && horizontal > 1.0e-12)
            {
                double scale = allowed / horizontal;
                supply = new Vector3d(
                    supply.X * scale, supply.Y * scale, supply.Z);
            }
            double length = supply.Length;
            return length > 1.0e-12
                ? new Vector3d(
                    supply.X / length, supply.Y / length, supply.Z / length)
                : Vector3d.ZAxis;
        }

        /// <summary>
        /// Where a column forks, solved from the forces rather than set.
        ///
        /// Each notch the column reaches wants its branch to run along its own
        /// line of thrust, which puts the fork somewhere on the ray dropping
        /// from that notch along that line. With more than one notch those rays
        /// do not meet in general, so the fork goes where they come CLOSEST:
        /// the point minimising the force-weighted squared distance to every
        /// ray at once. That is a three-by-three solve, and it is what makes
        /// the fork height a consequence of the load rather than a number
        /// somebody picked.
        ///
        /// A branch that pulls its notch DOWN has no thrust line to stand on,
        /// so it contributes as a plumb one, which is the same fallback the
        /// arms use.
        /// </summary>
        public static Point3d ForkPoint(
            List<Point3d> reach,
            List<Vector3d> pushes,
            double ground)
        {
            // Sum of w * (I - d d^T) for each ray, and the matching right side.
            var a = new double[3, 3];
            var rhs = new double[3];
            for (int i = 0; i < reach.Count; i++)
            {
                Vector3d push = pushes[i];
                double weight = push.Length;
                if (weight <= 1.0e-12)
                    continue;
                Vector3d d = AimFrom(-push);
                double[] u = { d.X, d.Y, d.Z };
                double[] p = { reach[i].X, reach[i].Y, reach[i].Z };
                for (int r = 0; r < 3; r++)
                {
                    for (int s = 0; s < 3; s++)
                    {
                        double m = (r == s ? 1.0 : 0.0) - (u[r] * u[s]);
                        a[r, s] += weight * m;
                        rhs[r] += weight * m * p[s];
                    }
                }
            }

            if (!Solve3(a, rhs, out double x, out double y, out double z))
            {
                // Degenerate, which means every branch is parallel: the rays
                // never converge, so drop straight below the load centre.
                double sw = 0.0;
                double sx = 0.0;
                double sy = 0.0;
                double lowest = double.MaxValue;
                for (int i = 0; i < reach.Count; i++)
                {
                    double w = Math.Max(pushes[i].Length, 1.0e-9);
                    sx += reach[i].X * w;
                    sy += reach[i].Y * w;
                    sw += w;
                    lowest = Math.Min(lowest, reach[i].Z);
                }
                return new Point3d(sx / sw, sy / sw, lowest);
            }

            // A fork stands UNDER the notches it carries and ABOVE the floor.
            double ceiling = reach.Min(p => p.Z);
            return new Point3d(
                x, y, Math.Min(Math.Max(z, ground), ceiling));
        }

        /// <summary>Gaussian elimination on three unknowns.</summary>
        public static bool Solve3(
            double[,] a, double[] b, out double x, out double y, out double z)
        {
            x = 0.0;
            y = 0.0;
            z = 0.0;
            var m = new double[3, 4];
            for (int r = 0; r < 3; r++)
            {
                for (int c = 0; c < 3; c++)
                    m[r, c] = a[r, c];
                m[r, 3] = b[r];
            }
            for (int col = 0; col < 3; col++)
            {
                int pivot = col;
                for (int r = col + 1; r < 3; r++)
                {
                    if (Math.Abs(m[r, col]) > Math.Abs(m[pivot, col]))
                        pivot = r;
                }
                if (Math.Abs(m[pivot, col]) < 1.0e-9)
                    return false;
                if (pivot != col)
                {
                    for (int c = 0; c < 4; c++)
                        (m[col, c], m[pivot, c]) = (m[pivot, c], m[col, c]);
                }
                for (int r = 0; r < 3; r++)
                {
                    if (r == col)
                        continue;
                    double factor = m[r, col] / m[col, col];
                    for (int c = col; c < 4; c++)
                        m[r, c] -= factor * m[col, c];
                }
            }
            x = m[0, 3] / m[0, 0];
            y = m[1, 3] / m[1, 1];
            z = m[2, 3] / m[2, 2];
            return true;
        }

        /// <summary>
        /// Where a foot stands this frame.
        ///
        /// The strut cannot be shorter than its retracted length, so while the
        /// head is low the foot lies far out along its rail and the member is
        /// almost lying down. As the head rises the distance that keeps the
        /// strut retracted shrinks, which draws the foot IN: the slide. Once it
        /// has come in as far as the finished foot it stops there and the ram
        /// drives out to make up the rest: the extension. Neither phase is
        /// scheduled; the crossover is just which of the two distances is
        /// smaller.
        ///
        /// The rail runs along the LIVE thrust azimuth, so the foot tracks the
        /// line of force the whole way rather than only arriving on it. The
        /// lean cannot track it while the strut is retracted, because then the
        /// lean is whatever the length dictates.
        /// </summary>
        public static Point3d FootOnRail(
            Point3d head,
            Point3d finished,
            Vector3d carrying,
            double full,
            double extend,
            double ground,
            ref double slid)
        {
            double rise = head.Z - ground;
            var under = new Point3d(head.X, head.Y, ground);
            double retracted = full * (1.0 - extend);

            double railX = -carrying.X;
            double railY = -carrying.Y;
            double railLength = Math.Sqrt((railX * railX) + (railY * railY));
            if (railLength <= 1.0e-9)
            {
                railX = finished.X - under.X;
                railY = finished.Y - under.Y;
                railLength = Math.Sqrt((railX * railX) + (railY * railY));
            }
            if (railLength <= 1.0e-9)
            {
                railX = 1.0;
                railY = 0.0;
                railLength = 1.0;
            }
            railX /= railLength;
            railY /= railLength;

            double finishedOut = Math.Sqrt(
                PlanDistanceSquared(under, finished));
            double retractedOut = retracted > rise
                ? Math.Sqrt((retracted * retracted) - (rise * rise))
                : 0.0;

            if (retractedOut > finishedOut)
            {
                slid = Math.Max(slid, retractedOut - finishedOut);
                return new Point3d(
                    under.X + (railX * retractedOut),
                    under.Y + (railY * retractedOut),
                    ground);
            }
            return new Point3d(finished.X, finished.Y, ground);
        }

        /// <summary>
        /// Rebuild a branching column out of the bare lines Column Finder
        /// hands over.
        ///
        /// The wire between the two components carries geometry, not topology,
        /// so a forked column arrives as a heap of segments with nothing saying
        /// which branch belongs to which trunk. Animating them one at a time
        /// treated every branch as though it stood on the ground, which is what
        /// left a fork hanging in mid air.
        ///
        /// Two facts make the tree recoverable without a new contract. Every
        /// member runs LOWER end to UPPER end, an invariant Column Finder keeps
        /// deliberately, and a fork is one point shared exactly. So welding the
        /// endpoints and reading the direction back gives the whole structure:
        /// a node that is only ever an upper end is a NOTCH, one that is only
        /// ever a lower end is a FOOT, and anything that is both is a FORK.
        /// </summary>
        public sealed class ColumnTree
        {
            public List<Point3d> Nodes { get; } = new();

            public List<(int Lower, int Upper)> Members { get; } = new();

            public List<int> Notches { get; } = new();

            public List<int> Feet { get; } = new();

            /// <summary>Upper ends of each node, nearest the notches.</summary>
            public List<int>[] Above { get; set; } = Array.Empty<List<int>>();
        }

        public static ColumnTree BuildColumnTree(
            IReadOnlyList<Line> columns,
            double weldTolerance)
        {
            var tree = new ColumnTree();
            double squared = weldTolerance * weldTolerance;

            int Weld(Point3d point)
            {
                for (int i = 0; i < tree.Nodes.Count; i++)
                {
                    if (tree.Nodes[i].DistanceToSquared(point) <= squared)
                        return i;
                }
                tree.Nodes.Add(point);
                return tree.Nodes.Count - 1;
            }

            foreach (Line member in columns)
            {
                if (member.Length <= 1.0e-9)
                    continue;
                // Lower end first, which is the invariant Column Finder keeps.
                Point3d lower = member.From.Z <= member.To.Z
                    ? member.From : member.To;
                Point3d upper = member.From.Z <= member.To.Z
                    ? member.To : member.From;
                int a = Weld(lower);
                int b = Weld(upper);
                if (a != b)
                    tree.Members.Add((a, b));
            }

            var above = new List<int>[tree.Nodes.Count];
            for (int i = 0; i < tree.Nodes.Count; i++)
                above[i] = new List<int>();
            var isLower = new bool[tree.Nodes.Count];
            var isUpper = new bool[tree.Nodes.Count];
            foreach ((int lower, int upper) in tree.Members)
            {
                above[lower].Add(upper);
                isLower[lower] = true;
                isUpper[upper] = true;
            }
            tree.Above = above;
            for (int i = 0; i < tree.Nodes.Count; i++)
            {
                if (isUpper[i] && !isLower[i])
                    tree.Notches.Add(i);
                else if (isLower[i] && !isUpper[i])
                    tree.Feet.Add(i);
            }
            return tree;
        }

        /// <summary>
        /// The index of the node nearest a point IN PLAN. Plan, because a
        /// column drawn against the finished shape has to find its notch on a
        /// net that is still on the ground.
        /// </summary>
        public static int NearestNodeInPlan(Point3d point, Point3d[] nodes)
        {
            int best = -1;
            double closest = double.MaxValue;
            for (int i = 0; i < nodes.Length; i++)
            {
                double d = PlanDistanceSquared(point, nodes[i]);
                if (d < closest)
                {
                    closest = d;
                    best = i;
                }
            }
            return best;
        }


        /// <summary>Squared distance in plan, height ignored.</summary>
        public static double PlanDistanceSquared(Point3d a, Point3d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        /// <summary>
        /// Median edge length IN PLAN, so the snap radius is measured the same
        /// way the snapping is. Using the spatial length would set too generous
        /// a radius on a steep vault, where a short edge in plan can be long in
        /// space.
        /// </summary>
        public static double MedianEdgeLength(Point3d[] nodes, (int, int)[] edges)
        {
            double[] lengths = edges
                .Select(e => Math.Sqrt(
                    PlanDistanceSquared(nodes[e.Item1], nodes[e.Item2])))
                .Where(length => length > 0.0)
                .OrderBy(length => length)
                .ToArray();
            return lengths.Length == 0 ? 1.0 : lengths[lengths.Length / 2];
        }

        public static int[] PerimeterNodes(
            Mesh? mesh,
            int[] meshToNode,
            List<int>[] neighbours,
            int count)
        {
            if (mesh is not null && mesh.Vertices.Count > 0 &&
                meshToNode.Length == mesh.Vertices.Count)
            {
                bool[] naked = mesh.GetNakedEdgePointStatus();
                if (naked is not null && naked.Length == mesh.Vertices.Count)
                {
                    // The mesh was built from these very nodes, so the mapping
                    // is exact and no nearest-point search is needed. A set
                    // keeps this linear; List.Contains made it quadratic.
                    var found = new List<int>();
                    var seen = new HashSet<int>();
                    for (int v = 0; v < mesh.Vertices.Count; v++)
                    {
                        if (!naked[v])
                            continue;
                        int node = meshToNode[v];
                        if (node >= 0 && node < count && seen.Add(node))
                            found.Add(node);
                    }
                    if (found.Count > 0)
                        return found.ToArray();
                }
            }

            int[] degrees = neighbours.Select(list => list.Count).ToArray();
            if (degrees.Length == 0)
                return Array.Empty<int>();
            int[] sorted = degrees.OrderBy(d => d).ToArray();
            int interior = sorted[sorted.Length / 2];
            return Enumerable.Range(0, count)
                .Where(i => degrees[i] < interior)
                .ToArray();
        }

        /// <summary>
        /// Rebuild the thrust mesh from a Result's own form faces, so neither
        /// component needs a mesh wired in. Returns null for an FD result,
        /// which carries no faces, and null rather than throwing if the
        /// mapping is incomplete: a missing surface should not stop the
        /// animation.
        /// </summary>
        public static Mesh? ThrustMeshFromResult(
            ResultDto result,
            out int[] meshToNode)
        {
            meshToNode = Array.Empty<int>();
            EquilibriumResultDto? equilibrium = result.Equilibrium;
            TnaDiagramGraphDto? formGraph = result.FormGraph;
            TnaMappingsDto? mappings = result.Mappings;
            if (equilibrium is null || formGraph is null || mappings is null)
                return null;

            try
            {
                var formToEquilibrium = new Dictionary<int, int>();
                foreach (var item in mappings.SourceVertexToFormVertex)
                {
                    if (!item.FormVertexId.HasValue ||
                        !item.EquilibriumVertexId.HasValue)
                    {
                        continue;
                    }
                    formToEquilibrium[item.FormVertexId.Value] =
                        item.EquilibriumVertexId.Value;
                }

                var mesh = new Mesh();
                var formToMesh = new Dictionary<int, int>();
                var map = new List<int>();
                foreach (TnaGraphVertexDto vertex in
                         formGraph.Vertices.OrderBy(item => item.Id))
                {
                    if (!formToEquilibrium.TryGetValue(vertex.Id, out int eqId) ||
                        eqId < 0 || eqId >= equilibrium.Vertices.Count)
                    {
                        return null;
                    }
                    Point3Dto p = equilibrium.Vertices[eqId];
                    formToMesh[vertex.Id] = mesh.Vertices.Add(p.X, p.Y, p.Z);
                    map.Add(eqId);
                }

                foreach (TnaGraphFaceDto face in
                         formGraph.Faces.OrderBy(item => item.Id))
                {
                    var ids = new List<int>();
                    foreach (int id in face.Vertices)
                    {
                        if (!formToMesh.TryGetValue(id, out int meshId))
                            return null;
                        ids.Add(meshId);
                    }
                    if (ids.Count == 3)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2]);
                    }
                    else if (ids.Count == 4)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2], ids[3]);
                    }
                    else
                    {
                        for (int i = 1; i < ids.Count - 1; i++)
                            mesh.Faces.AddFace(ids[0], ids[i], ids[i + 1]);
                    }
                }

                if (mesh.Faces.Count == 0)
                    return null;
                mesh.Normals.ComputeNormals();
                // Compact would renumber vertices and break the mapping, and
                // there is nothing to compact: every vertex was just added and
                // every face references one.
                meshToNode = map.ToArray();
                return mesh;
            }
            catch (Exception)
            {
                return null;
            }
        }

        /// <summary>
        /// Bundle a frame into a MouldState. Member forces come from the
        /// Result, so they are the forces of the FINAL state whatever frame the
        /// geometry belongs to; Stress Analysis says as much rather than
        /// letting the pairing pass unremarked.
        /// </summary>
        public static MouldStateDto BuildState(
            string stage,
            double ground,
            Point3d[] live,
            (int, int)[] edges,
            int[] edgeSource,
            EquilibriumResultDto equilibrium,
            IEnumerable<int> principalIds,
            IEnumerable<int> anchorIds,
            IEnumerable<int> perimeterIds,
            IReadOnlyList<Point3d> columnFoot,
            IReadOnlyList<Point3d> columnHead,
            IReadOnlyList<double> columnForce)
        {
            var principal = new HashSet<int>(principalIds);
            var kinds = new string[edges.Length];
            for (int e = 0; e < edges.Length; e++)
            {
                // A member joining two notches of the same bar IS the bar;
                // everything else is an infill cable the steppers reel.
                kinds[e] = principal.Contains(edges[e].Item1) &&
                    principal.Contains(edges[e].Item2)
                    ? "bar"
                    : "infill";
            }

            var forces = new double[edges.Length];
            var densities = new double[edges.Length];
            for (int e = 0; e < edges.Length; e++)
            {
                // Index by where the edge came from, not by where it ended up.
                int src = e < edgeSource.Length ? edgeSource[e] : e;
                forces[e] = src < equilibrium.MemberForces.Count
                    ? equilibrium.MemberForces[src]
                    : 0.0;
                densities[e] = src < equilibrium.ForceDensities.Count
                    ? equilibrium.ForceDensities[src]
                    : 0.0;
            }

            return new MouldStateDto
            {
                Stage = stage,
                Ground = ground,
                Vertices = live.Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                Edges = edges.Select(e => new EdgeDto(e.Item1, e.Item2)).ToArray(),
                MemberForce = forces,
                ForceDensity = densities,
                EdgeKind = kinds,
                PrincipalNodes = principal.OrderBy(i => i).ToArray(),
                AnchorNodes = anchorIds.OrderBy(i => i).ToArray(),
                PerimeterNodes = perimeterIds.ToArray(),
                Reactions = equilibrium.Reactions.ToArray(),
                ColumnFoot = columnFoot
                    .Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                ColumnHead = columnHead
                    .Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                ColumnForce = columnForce.ToArray(),
            };
        }

        public static Mesh DeformMesh(Mesh source, int[] meshToNode, Point3d[] live)
        {
            Mesh deformed = source.DuplicateMesh();
            for (int v = 0; v < deformed.Vertices.Count && v < meshToNode.Length; v++)
            {
                int node = meshToNode[v];
                if (node < 0 || node >= live.Length)
                    continue;
                // Exact, from the mapping the mesh was built with, rather than
                // a nearest-point search that cost one pass over every node for
                // every vertex on every frame.
                deformed.Vertices.SetVertex(v, live[node]);
            }
            deformed.Normals.ComputeNormals();
            deformed.Compact();
            return deformed;
        }
    }
}
