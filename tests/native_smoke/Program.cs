using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json.Nodes;

namespace Ananke.COMPAS.NativeSmoke;

internal static class Program
{
    private const string GrasshopperComponentBase =
        "Grasshopper.Kernel.GH_Component";
    private const string GrasshopperPersistentParamBase =
        "Grasshopper.Kernel.GH_PersistentParam`1";
    private const string RhinoCodeNamespace = "RhinoCodePluginGH";

    private static readonly object ResolverLock = new();
    private static readonly HashSet<string> Resolving = new(
        StringComparer.OrdinalIgnoreCase);
    private static readonly IReadOnlyDictionary<string, int[]> FlattenedInputs =
        new Dictionary<string, int[]>(StringComparer.Ordinal)
        {
            ["Ananke.COMPAS.Native.Components.PatternComponent"] =
                new[] { 0, 4 },
            ["Ananke.COMPAS.Native.Components.SupportsComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.LoadsComponent"] =
                new[] { 2 },
            ["Ananke.COMPAS.Native.Components.FdSolveComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.ExportComponent"] =
                new[] { 4, 5 }
        };
    private static readonly HashSet<string> RequiredPreviewComponents = new(
        StringComparer.Ordinal)
        {
            "Ananke.COMPAS.Native.Components.PatternComponent",
            "Ananke.COMPAS.Native.Components.SupportsComponent",
            "Ananke.COMPAS.Native.Components.LoadsComponent",
            "Ananke.COMPAS.Native.Components.TnaRelaxComponent",
            "Ananke.COMPAS.Native.Components.TnaSolveComponent",
            "Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent",
            "Ananke.COMPAS.Native.Components.FdSolveComponent",
            "Ananke.COMPAS.Native.Components.DisplayComponent",
            // Animate is the clearest case this set exists for: one output,
            // custom Goo, and everything an author sees of the machine is
            // its viewport drawing. Nothing else in the plugin says that
            // drawing has to keep existing.
            "Ananke.COMPAS.Native.Components.MouldAnimateComponent"
        };
    private static readonly HashSet<string> NativeVisibilityGuardComponents =
        new(StringComparer.Ordinal)
        {
            "Ananke.COMPAS.Native.Components.PatternComponent",
            "Ananke.COMPAS.Native.Components.SupportsComponent",
            "Ananke.COMPAS.Native.Components.LoadsComponent",
            "Ananke.COMPAS.Native.Components.DisplayComponent"
        };
    /// <summary>
    /// Deconstruct is the one merged extraction surface over the unified
    /// <c>ResultDto</c>, replacing the four deleted v0.2 query components
    /// (TNA Geometry, TNA Members, TNA Actions, Result Breakdown). Checked
    /// the same way those were: full parameter Names, in registration
    /// order, against the plan's fixed output list.
    /// </summary>
    private static readonly IReadOnlyDictionary<
        string,
        (string[] Inputs, string[] Outputs)> VisualiseContracts =
            new Dictionary<
                string,
                (string[] Inputs, string[] Outputs)>(StringComparer.Ordinal)
            {
                ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = (
                    new[] { "Result" },
                    new[]
                    {
                        // TEN outputs since the readers rework: Thrust Mesh,
                        // Columns, Heads and Feet moved to Frame, every
                        // remaining wire shifted, and the name-comparing
                        // load warning is what tells a reopened definition.
                        "Member Lines",
                        "Form Lines",
                        "Member IDs",
                        "Node IDs",
                        "Support Points",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Points",
                        "Reaction Vectors",
                        "Force Lines"
                    }),
                // Skin is pinned because THIS rework reshaped it: input 1
                // was "Course Height" and is now "Pattern", so a wired CH
                // slider must move to slot 3, and the outputs renamed with
                // their meanings kept. The names below are what the
                // ports-moved warning compares a saved definition against.
                ["Ananke.COMPAS.Native.Components.SkinComponent"] = (
                    new[] { "Result", "Pattern", "Size", "Course Height" },
                    new[] { "Cells", "Courses", "Flowlines", "Diagnostics" }),
                // Display DRAWS. Its six outputs went to Deconstruct (the
                // member and form lines, the load and reaction points and
                // vectors) and to Diagnose (the report), which carry them
                // already; what is left here is the drawing, so the pin is
                // seven inputs and NO outputs. RequiredPreviewComponents and
                // NativeVisibilityGuardComponents keep it, because the
                // viewport is now the whole of it.
                ["Ananke.COMPAS.Native.Components.DisplayComponent"] = (
                    new[]
                    {
                        "Result", "Style", "Elements", "Metric", "Weight",
                        "Vector Scale", "Gap"
                    },
                    Array.Empty<string>()),
                // Fit owns the geometry-against-the-solved-state half of
                // Monitor's old surface: deviation in vertex order, the sag
                // per bar, pinned for the same reason the other children are.
                ["Ananke.COMPAS.Native.Components.FitComponent"] = (
                    new[] { "Result", "EI", "Tolerance" },
                    new[]
                    {
                        "Result",
                        "Deviation", "Deviation Stats", "Reachable",
                        "Unreachable", "Bar Sag"
                    }),
                // Forces owns the member half of Monitor's old surface:
                // every number tree here is READ AGAINST a Deconstruct
                // geometry tree by slot, so the names and the order are the
                // canvas contract.
                ["Ananke.COMPAS.Native.Components.ForcesComponent"] = (
                    new[] { "Result", "EA", "Cable Capacity" },
                    new[]
                    {
                        "Result",
                        "Member Force", "Force Density", "Horizontal Force",
                        "Slack", "Spool Length", "Unstrained Length",
                        "Residuals", "Cable Utilisation"
                    }),
                // Supports owns the ground half: anchors by strip, columns
                // by tree, aligned with Deconstruct's Reaction Points and
                // Frame's Columns.
                ["Ananke.COMPAS.Native.Components.SupportsReaderComponent"] = (
                    new[] { "Result", "Column Capacity" },
                    new[]
                    {
                        "Result",
                        "Anchor Along", "Anchor Across", "Tip Reaction",
                        "Column Force", "Thrust", "Lean", "Column Utilisation"
                    }),
                // Animate MAKES a frame and emits the Result carrying it.
                // Its geometry is Frame's, below, so there is one port here
                // and the RES-first rule holds on both sides of it.
                ["Ananke.COMPAS.Native.Components.MouldAnimateComponent"] = (
                    new[] { "Result", "Time", "Pre-Sag", "Extension" },
                    new[] { "Result" }),
                // Frame READS one. Every port here is an index a downstream
                // branch is read by, so pinning them by name in order is what
                // stops a reorder silently rewiring a canvas.
                ["Ananke.COMPAS.Native.Components.FrameComponent"] = (
                    new[] { "Result" },
                    new[]
                    {
                        "Mesh",
                        "Cables",
                        "Principal Lines",
                        "Principal Nodes",
                        "Anchor Nodes",
                        "Perimeter Nodes",
                        "Perimeter Lines",
                        "Columns",
                        "Phase",
                        // APPENDED at 9 by the readers rework, so no
                        // existing wire moved.
                        "Anchor Lines"
                    }),
                // Export's ports are pinned because Format's removal moved
                // every input after slot 0 up one: the order below IS the
                // canvas contract. The outputs are one JSON list and one
                // Status, and a reader tells the kinds apart by the schema
                // key each text carries rather than by slot.
                ["Ananke.COMPAS.Native.Components.ExportComponent"] = (
                    new[]
                    {
                        "Result", "Path", "Write", "Name", "Cells", "Courses",
                        "Live", "Studio", "Column Radius"
                    },
                    new[] { "JSON", "Status" })
            };
    private static readonly IReadOnlyDictionary<
        string,
        (string Name, string NickName, string Tab, string[] InputNickNames,
            string[] OutputNickNames)> SpineComponentContracts =
            new Dictionary<
                string,
                (string Name, string NickName, string Tab,
                    string[] InputNickNames, string[] OutputNickNames)>(
                StringComparer.Ordinal)
            {
                ["Ananke.COMPAS.Native.Components.PatternComponent"] = (
                    "Pattern",
                    "Pattern",
                    "01 Model",
                    // P/RS/RD joined 2026-08-26: the principal lines are
                    // resolved to vertex runs HERE, where the curves and the
                    // geometry still agree, and carried down the contract.
                    new[] { "G", "M", "R", "Tol", "P" },
                    new[] { "PAT" }),
                ["Ananke.COMPAS.Native.Components.SupportsComponent"] = (
                    "Supports",
                    "Supports",
                    "01 Model",
                    new[] { "PAT", "A", "Tol" },
                    new[] { "SUP" }),
                ["Ananke.COMPAS.Native.Components.LoadsComponent"] = (
                    "Loads",
                    "Loads",
                    "01 Model",
                    new[] { "SUP", "V", "ID", "F" },
                    new[] { "PRB" }),
                ["Ananke.COMPAS.Native.Components.TnaRelaxComponent"] = (
                    "TNA Relax",
                    "TNA Relax",
                    "02 Solve",
                    new[] { "PRB", "q", "Sag %", "FA" },
                    new[] { "RLX" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveComponent"] = (
                    "TNA Solve",
                    "TNA Solve",
                    "02 Solve",
                    new[] { "RLX", "H", "I", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent"] = (
                    "TNA Solve Algebraic",
                    "TNA Solve A",
                    "02 Solve",
                    new[] { "RLX", "H", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.FdSolveComponent"] = (
                    "FD Solve",
                    "FD Solve",
                    "02 Solve",
                    new[] { "PRB", "q", "Run" },
                    new[] { "RES", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.StyleComponent"] = (
                    "Style",
                    "Style",
                    "04 Read",
                    new[] { "Preset", "Weight", "Vector" },
                    new[] { "STY" }),
                // Columns is pinned because slot 2 is RENAMED from Ground to
                // Type and keeps its slot: the nicknames are the canvas
                // contract, and a saved wire has to land on the same port it
                // left. Its TAB is pinned for the same reason at one remove:
                // 03 Mould is a panel of two, and a component that drifts out
                // of it is a component nobody can find.
                ["Ananke.COMPAS.Native.Components.ColumnsComponent"] = (
                    "Columns",
                    "Columns",
                    "03 Mould",
                    new[] { "RES", "B", "T" },
                    new[] { "RES" }),
                // Frame is pinned nickname by nickname because it is the one
                // component whose whole job is the ORDER of its ports: ten
                // trees read by index downstream. AL is APPENDED so nothing
                // above it moved.
                ["Ananke.COMPAS.Native.Components.FrameComponent"] = (
                    "Frame",
                    "FR",
                    "04 Read",
                    new[] { "RES" },
                    new[] { "M", "C", "PL", "PN", "AN", "PRN", "PRL", "CO", "PH", "AL" }),
                ["Ananke.COMPAS.Native.Components.ImportPiecesComponent"] = (
                    "Import Pieces",
                    "Pieces",
                    "05 Deliver",
                    new[] { "P" },
                    // Addendum, 2026-08-20: the flat Courses (C) output is
                    // removed; M/K/S are trees branched by course, B is
                    // the new base-mesh item.
                    new[] { "M", "K", "S", "B", "D" })
            };

    /// <summary>
    /// The icon family: every component's key and the two letters on its
    /// badge, as spec section 6 fixes them. The CATEGORY is not pinned here
    /// on purpose: it is read off the component's own registered
    /// subcategory, so the map and the panels cannot disagree without one of
    /// them being wrong about a component that exists.
    /// </summary>
    private static readonly IReadOnlyDictionary<string, (string Key, string Label)>
        NativeIconEntries = new Dictionary<string, (string Key, string Label)>(
            StringComparer.Ordinal)
        {
            ["Ananke.COMPAS.Native.Components.PatternComponent"] = ("tna_pattern", "PA"),
            ["Ananke.COMPAS.Native.Components.SupportsComponent"] = ("tna_supports", "SU"),
            ["Ananke.COMPAS.Native.Components.LoadsComponent"] = ("load_case", "LO"),
            ["Ananke.COMPAS.Native.Components.TnaRelaxComponent"] = ("tna_relax", "RX"),
            ["Ananke.COMPAS.Native.Components.TnaSolveComponent"] = ("tna_solve", "TS"),
            ["Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent"] =
                ("tna_solve_algebraic", "TA"),
            ["Ananke.COMPAS.Native.Components.FdSolveComponent"] = ("fd_solve", "FD"),
            ["Ananke.COMPAS.Native.Components.ColumnsComponent"] = ("column_finder", "CO"),
            ["Ananke.COMPAS.Native.Components.MouldAnimateComponent"] = ("mould_animate", "AN"),
            ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = ("result_breakdown", "DE"),
            ["Ananke.COMPAS.Native.Components.FitComponent"] = ("fit", "FI"),
            ["Ananke.COMPAS.Native.Components.ForcesComponent"] = ("forces", "FO"),
            ["Ananke.COMPAS.Native.Components.SupportsReaderComponent"] = ("supports", "SP"),
            ["Ananke.COMPAS.Native.Components.SkinComponent"] = ("skin", "SK"),
            ["Ananke.COMPAS.Native.Components.DiagnoseComponent"] = ("diagnose", "DG"),
            ["Ananke.COMPAS.Native.Components.FrameComponent"] = ("frame", "FR"),
            ["Ananke.COMPAS.Native.Components.StyleComponent"] = ("diagram_style", "ST"),
            ["Ananke.COMPAS.Native.Components.DisplayComponent"] =
                ("graphic_diagram_display", "DI"),
            ["Ananke.COMPAS.Native.Components.ExportComponent"] = ("export", "EX"),
            ["Ananke.COMPAS.Native.Components.ImportPiecesComponent"] = ("import_pieces", "IP"),
            ["Ananke.COMPAS.Native.Components.BackendHealthComponent"] = ("backend_health", "BH"),
        };

    public static int Main(string[] args)
    {
        try
        {
            Options options = Options.Parse(args);
            return Run(options);
        }
        catch (UsageException exception)
        {
            Console.Error.WriteLine($"ERROR: {exception.Message}");
            Console.Error.WriteLine(
                "Usage: dotnet run --project tests/native_smoke -- " +
                "<plugin.gha> [--rhino-root <Rhino 8 directory>]");
            return 2;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"ERROR: Native component smoke test could not run: " +
                $"{DescribeException(exception)}");
            Console.Error.WriteLine(exception.StackTrace);
            return 3;
        }
    }

    private static int Run(Options options)
    {
        string pluginPath = Path.GetFullPath(options.PluginPath);
        if (!File.Exists(pluginPath))
            throw new UsageException($"Plugin does not exist: {pluginPath}");

        string rhinoRoot = ResolveRhinoRoot(options.RhinoRoot);
        string rhinoSystem = Path.Combine(rhinoRoot, "System");
        string grasshopperDirectory = Path.Combine(
            rhinoRoot,
            "Plug-ins",
            "Grasshopper");

        string rhinoCommonPath = RequireFile(
            Path.Combine(rhinoSystem, "RhinoCommon.dll"));
        string ghIoPath = RequireFile(
            Path.Combine(grasshopperDirectory, "GH_IO.dll"));
        string grasshopperPath = RequireFile(
            Path.Combine(grasshopperDirectory, "Grasshopper.dll"));

        string pluginDirectory =
            Path.GetDirectoryName(pluginPath)
            ?? throw new InvalidOperationException(
                "The plugin path has no parent directory.");
        string[] probingDirectories =
        {
            pluginDirectory,
            rhinoSystem,
            grasshopperDirectory,
            Path.Combine(grasshopperDirectory, "Components"),
            rhinoRoot,
            Path.Combine(rhinoRoot, "Plug-ins")
        };

        AssemblyLoadContext.Default.Resolving += (_, assemblyName) =>
            ResolveAssembly(assemblyName, probingDirectories);

        // Establish the same type identity the plugin expects before loading it.
        LoadAssembly(rhinoCommonPath);
        LoadAssembly(ghIoPath);
        LoadAssembly(grasshopperPath);
        Assembly plugin = LoadAssembly(pluginPath);
        // The engine's OWN plan-validity predicates, resolved once, so
        // RequireDisjointSimplePlans measures with the same arithmetic
        // the engines filter with. See its doc comment.
        SkinPlanSelfCrosses =
            RequirePublicStatic(
                RequireComponentType(plugin, "SkinPatterns"),
                "PlanSelfCrosses");
        SkinPlansOverlap =
            RequirePublicStatic(
                RequireComponentType(plugin, "SkinPatterns"),
                "PlansOverlap");

        Type[] componentTypes = GetLoadableTypes(plugin)
            .Where(IsConcretePublicGrasshopperComponent)
            .OrderBy(type => type.FullName, StringComparer.Ordinal)
            .ToArray();
        Type[] parameterTypes = GetLoadableTypes(plugin)
            .Where(IsConcretePublicPersistentParameter)
            .OrderBy(type => type.FullName, StringComparer.Ordinal)
            .ToArray();

        Console.WriteLine($"Plugin: {plugin.FullName}");
        Console.WriteLine($"Path: {pluginPath}");
        Console.WriteLine($"Rhino root: {rhinoRoot}");

        if (componentTypes.Length == 0)
        {
            Console.Error.WriteLine(
                "ERROR: No concrete public GH_Component types were found.");
            return 4;
        }

        var failures = new List<string>();
        var documentGuids = new Dictionary<Guid, string>();
        foreach (Type componentType in componentTypes)
        {
            Type? forbiddenBase = FindRhinoCodeBase(componentType);
            if (forbiddenBase is not null)
            {
                failures.Add(
                    $"{componentType.FullName}: derives from forbidden " +
                    $"RhinoCode script base {forbiddenBase.FullName}.");
                continue;
            }

            object? instance = null;
            try
            {
                instance = Activator.CreateInstance(componentType);
                if (instance is null)
                    throw new InvalidOperationException(
                        "Activator.CreateInstance returned null.");

                string displayName = ReadDisplayName(instance, componentType);
                ValidateFlattenedInputs(instance, componentType);
                ValidatePreviewCapability(instance, componentType);
                ValidateNativePreviewVisibilityGuard(instance, componentType);
                ValidateVisualiseContract(instance, componentType);
                ValidateSpineComponentContract(instance, componentType);
                ValidateIcon(instance, componentType);
                RecordDocumentGuid(
                    instance,
                    componentType,
                    documentGuids,
                    failures);
                Console.WriteLine(
                    $"PASS  {displayName} [{componentType.FullName}]");
            }
            catch (Exception exception)
            {
                failures.Add(
                    $"{componentType.FullName}: constructor failed: " +
                    DescribeException(exception));
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }

        Console.WriteLine($"Components discovered: {componentTypes.Length}");
        int componentFailureCount = failures.Count;
        Console.WriteLine(
            $"Components passed: {componentTypes.Length - componentFailureCount}");

        foreach (Type parameterType in parameterTypes)
        {
            object? instance = null;
            try
            {
                instance = Activator.CreateInstance(parameterType);
                if (instance is null)
                    throw new InvalidOperationException(
                        "Activator.CreateInstance returned null.");
                RecordDocumentGuid(
                    instance,
                    parameterType,
                    documentGuids,
                    failures);
                Console.WriteLine(
                    $"PASS  parameter [{parameterType.FullName}]");
            }
            catch (Exception exception)
            {
                failures.Add(
                    $"{parameterType.FullName}: constructor failed: " +
                    DescribeException(exception));
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }
        if (componentTypes.Length != 21)
        {
            // Spec 6 pins three counts and only two were enforced. A
            // component quietly dropped from the assembly, by a failed
            // registration or a merge, would have left the whole suite green
            // with nineteen components' worth of contract untested. 21 is
            // the skin rework: Skin and Armadillo Dual became ONE Skin
            // component in 05 Deliver, three patterns behind one flag.
            failures.Add(
                $"Expected 21 concrete public components, found " +
                $"{componentTypes.Length}.");
        }
        if (parameterTypes.Length != 12)
        {
            failures.Add(
                $"Expected 12 public persistent contract parameters, found " +
                $"{parameterTypes.Length}.");
        }
        Console.WriteLine($"Parameters discovered: {parameterTypes.Length}");
        Console.WriteLine(
            $"Parameters passed: " +
            $"{parameterTypes.Length - (failures.Count - componentFailureCount)}");

        try
        {
            ValidateResultContract(plugin);
            Console.WriteLine(
                "PASS  ResultDto contract: valid TNA, valid FD, and " +
                "invalid-without-graphs cases validate correctly.");
        }
        catch (Exception exception)
        {
            failures.Add($"ResultDto contract: {DescribeException(exception)}");
        }

        try
        {
            ValidateSpineContracts(plugin);
            Console.WriteLine(
                "PASS  Spine contracts: AnchoredPattern, Problem, and " +
                "Relaxed validate correctly (valid and invalid cases), " +
                "and Problem attaches to ResultDto.");
        }
        catch (Exception exception)
        {
            failures.Add($"Spine contracts: {DescribeException(exception)}");
        }

        try
        {
            ValidateResultGooRawWireSnapshot(plugin);
            Console.WriteLine(
                "PASS  ResultGoo RawWire snapshot: construction and " +
                "Duplicate() both preserve RawWire, and Contract-mode " +
                "serialisation still excludes it.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ResultGoo RawWire snapshot: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportCoursesValidation(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.HasNegativeCourse: flags every " +
                "offending index/value and leaves a clean Courses list " +
                "alone.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.HasNegativeCourse: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateExportTessellationJsonOptions(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.BuildTessellationJson: shape and " +
                "byte content match the studio's bench.tessellation/1 " +
                "sidecar contract under the shared ContractJson.Options.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.BuildTessellationJson: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateImportPiecesParsing(plugin);
            Console.WriteLine(
                "PASS  ImportPiecesComponent.ParseDocument: piece count, " +
                "drop-order preservation, vertex/face array shapes, and " +
                "base_mesh presence/shape match the committed " +
                "bench.pieces/1 fixture (2 courses, 14 pieces); the " +
                "course-tree partitioning is MEASURED against the exact " +
                "per-course counts and in-branch order; a doctored copy " +
                "with no base_mesh key still parses (BaseMesh null); " +
                "doctored schema/units copies are refused naming what " +
                "was found.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ImportPiecesComponent.ParseDocument: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateSkinNet(plugin);
            Console.WriteLine(
                "PASS  SkinPatterns.ReadNet: a TNA Result's form faces " +
                "come back as plain vertex/face arrays mapped through " +
                "SourceVertexToFormVertex onto equilibrium positions " +
                "(form ids deliberately offset from equilibrium ids); an " +
                "FD Result gives null, not empty.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"SkinPatterns.ReadNet: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinSetout(plugin);
            Console.WriteLine(
                "PASS  Skin setout map: the barrel cut gives two OPEN " +
                "length-6 strips seamed at their arc midpoints with " +
                "PointAt walking signed offsets and Run keeping trace " +
                "vertices; the dome cuts give CLOSED loops, the lowest " +
                "seamed at the +X vertex, the next propagated nearest in " +
                "plan, and u wraps.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin setout map: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinCourses(plugin);
            Console.WriteLine(
                "PASS  Skin courses engine: the barrel's joint sets are " +
                "pinned exactly (even courses ten 0.6 pieces with a " +
                "joint at the seam, odd courses staggered half a pitch " +
                "with 0.3 end pieces, mirror-symmetric about the seam); " +
                "the dome's closed courses are round(L/S) equal pieces " +
                "rotated half a pitch on odd courses; cells arrive in " +
                "build order (course, then position along it), engine " +
                "outlines are open rings, the sliver-merge rule holds, " +
                "and every plan projection is disjoint and simple.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin courses engine: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinOrientation(plugin);
            Console.WriteLine(
                "PASS  Skin curve orientation: a scrambled-face-order " +
                "barrel whose lower rows trace east to west and whose " +
                "upper rows trace west to east is normalised to one " +
                "direction, closed dome loops are turned " +
                "counter-clockwise to their pinned signed plan area, and " +
                "the courses engine gives the ordered fixture's 84 cells " +
                "back cell for cell with disjoint simple plans, the " +
                "honeycomb its 76.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin curve orientation: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinTransitions(plugin);
            Console.WriteLine(
                "PASS  Skin topology transitions: refused on the " +
                "CORRESPONDENCE, not the count. A two-peak net whose one " +
                "level loop splits into two above z 0.9, a two-hump " +
                "barrel whose strips become hump loops, and a net where " +
                "one island splits as another dies, all three holding " +
                "their component count across the change, each have the " +
                "one courses band and the two lattice rows that reach " +
                "across it REFUSED whole, named in the diagnostics with " +
                "their heights and counted for the component's Warning, " +
                "every other band still built and every emitted plan " +
                "disjoint and simple bar the ones named in the check; " +
                "the same two-hump barrel TURNED 37 degrees in plan is " +
                "refused identically, cell count for cell count, because " +
                "a rotation about world Z cannot change which curves " +
                "correspond; the barrel and the dome refuse nothing; and " +
                "an ANNULAR shell, whose every cut is two nested loops, " +
                "is refused NOWHERE and proposed on by both engines at " +
                "five course heights.");
        }
        catch (Exception exception)
        {
            failures.Add(
                "Skin topology transitions: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateSkinRingVaultMeshings(plugin);
            Console.WriteLine(
                "PASS  Skin correspondence is the GEOMETRY's, not the " +
                "mesh's: one annular shell meshed five ways, quad, " +
                "triangulated, its ridge ring turned by a tenth of a " +
                "degree and by half its own spacing, and with unequal " +
                "ring densities, traces two nested loops of nesting " +
                "depth 0 and 1 at every mid height of every meshing, " +
                "refuses no band on any of them, and BUILDS the quad " +
                "fixture's own 312, 208 and 52 courses cells and 252, " +
                "180 and 108 honeycomb cells at CH 0.35, 0.5 and 1.9, " +
                "every survivor disjoint and simple. The one count that " +
                "moves is derived, not tolerated: a 32-gon is longer " +
                "than a 16-gon, so the unequal meshing's third band " +
                "rounds to one more piece and its CH 0.35 courses are " +
                "313.");
        }
        catch (Exception exception)
        {
            failures.Add(
                "Skin correspondence is the geometry's: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateSkinHexagonal(plugin);
            Console.WriteLine(
                "PASS  Skin hexagonal engine: the barrel's honeycomb is " +
                "pinned at 76 cells with 36 clipped rim cells KEPT, an " +
                "interior cell carries the stated six vertex offsets in " +
                "order, lattice neighbours share mapped corners, course " +
                "indices follow the centre bands on unclipped and " +
                "clipped cells alike, membership measures u against the " +
                "candidate's OWN centre-row curve, and the plans are " +
                "disjoint and simple on the barrel, on the shallow " +
                "shell and on the dome at CH 0.2 and 0.5, the dome's " +
                "0.35 and 0.8 being a pre-existing crown breach the " +
                "check names rather than asserts.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin hexagonal engine: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinPlanFilter(plugin);
            Console.WriteLine(
                "PASS  Skin plan filter: the guarantee spec section 4 " +
                "argues for is ENFORCED. Both engines run the plan " +
                "validity filter over the sorted cells before they are " +
                "returned, dropping a cell whose plan projection " +
                "self-crosses and then one that overlaps a cell already " +
                "kept, counting each kind into its own diagnostics line " +
                "and the component's Warning. A non-convex L-shaped " +
                "shell at CH 0.5 builds one self-crossing courses cell " +
                "out of 95, and 94 disjoint simple ones come back; the " +
                "same shell at six other course heights drops nothing. " +
                "The engine's own predicates are what this harness " +
                "measures with, so the two cannot disagree, and they " +
                "are themselves exercised on a bow tie, a square, and " +
                "squares apart, sharing an edge, overlapping and " +
                "nested.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin plan filter: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinGuards(plugin);
            Console.WriteLine(
                "PASS  Skin floors: S and Course Height below 1 mm, NaN " +
                "included, are refused by the negated-comparison guard " +
                "in both engines.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin floors: {DescribeException(exception)}");
        }

        try
        {
            ValidateSkinIdentity(plugin);
            Console.WriteLine(
                "PASS  Skin identity: the old Skin GUID kept, the " +
                "Armadillo Dual class and GUID gone from every " +
                "component, the Pattern value list pinned (input 1, " +
                "default 0, courses/hexagonal/force aligned), all " +
                "four outputs VISIBLE, the proposer convention, and the " +
                "task-capable base whose iteration-indexed TaskList is " +
                "the premise of the placeholder rule read in the check.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin identity: {DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalLineSnapping(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.SnapSampledLineToNodes: a line drawn down the "
                + "middle of a bay, with the node column either side of it "
                + "inside the catch radius, matches ONE connected column end "
                + "to end (9 nodes, every consecutive pair joined by a mesh "
                + "edge, x constant, y strictly increasing) and reports its "
                + "0.5 offset; a line drawn on a column matches that column "
                + "at zero offset. The zigzag regression is MEASURED, not "
                + "inspected.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"MouldGeometry.SnapSampledLineToNodes: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateColumnAim(plugin);
            Console.WriteLine(
                "PASS  ColumnFinder load and aim: a symmetric bay pulls a notch "
                + "straight down and the column comes out plumb; a one-sided "
                + "bay at 45 degrees leans the column 45 degrees the other way, "
                + "its foot on the side the cable pulls toward; a nearly "
                + "horizontal pull is held at the 60-degree cap. Measured "
                + "against hand-computed vectors, not inspected.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ColumnFinder load and aim: {DescribeException(exception)}");
        }

        try
        {
            ValidateRunDeduplication(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder.Deduplicate: one line traced from "
                + "both ends is ONE bar even when the two traces finish on "
                + "different nodes, which is the case matching their endpoints "
                + "could not catch and which gave one line two full sets of "
                + "columns; separate lines and merely crossing lines both "
                + "survive as two.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder deduplication: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateDerivationRemoved(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder: the anchor derivation is GONE. A "
                + "principal line is a decision Param draws into Pattern; "
                + "nothing in the plugin derives one from the anchors any more.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder derivation removed: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalOutcome(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder.Outcome: no curves is silence, a "
                + "dropped curve is a warning naming the count, two curves on "
                + "one run is a remark that says merged, and curves with NO "
                + "run at all is an error that says no Pattern is emitted.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder.Outcome: {DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalPreviewOwner(plugin, componentTypes);
            Console.WriteLine(
                "PASS  Preview ownership: Pattern is the ONLY component holding "
                + "a principal-line preview, and the Result-side helper that "
                + "fed the others is gone. Nine components painted the same "
                + "red bars, and with a solver's preview underneath each bar "
                + "drew twice; one owner, one drawing.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Principal preview owner: {DescribeException(exception)}");
        }

        try
        {
            ValidateRegisteredMappingWins(plugin);
            Console.WriteLine(
                "PASS  ParameterIdentity.Restore: a mapping the plugin REGISTERED "
                + "wins over the archive, so Pattern's P re-flattens in every "
                + "definition saved before it flattened; a port registered with "
                + "no mapping keeps the graft the author set by hand, which the "
                + "first fix would have wiped on every reopen.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ParameterIdentity registered mapping: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateColumnPlacement(plugin);
            Console.WriteLine(
                "PASS  ColumnPlacement: nine notches at Branching 2 group into a "
                + "centre single and four mirrored pairs with mirrored mains, "
                + "eight at Branching 3 into two triples and a single at each "
                + "anchor end; the fork lies on the foot-to-main segment at "
                + "65% height with trunk and main branch collinear; an arch "
                + "whose pulls carry a flank scale and an along-chord skew "
                + "still puts every mirrored pair of feet astride the span's "
                + "midpoint and its centre foot ON it, plumb; three bars of "
                + "one family, one of them traced backwards, carry the same "
                + "feet in their own frames; a wide arch asked for one "
                + "central foot PLACES it and peels the flank trunks that "
                + "would pass the 60 degree cap, and at two feet its bands "
                + "come out mirrored with the centre tree on the midpoint on "
                + "its own foot; a symmetric arch puts its one foot on the "
                + "span centre within a hundredth of the span; feet inside the clearance stay two unless they are a "
                + "mirrored pair, which stands on its span's midpoint; "
                + "mid-bar anchors give half-spans and no head; two bars "
                + "ending on an anchor-free rim get one ring tree at their "
                + "tangents' plan intersection; a crossing node is held once; "
                + "at Branching 3 a branch below the fork still leaves lower "
                + "end first and no held head becomes a foot in mid-air; "
                + "CountCollisions refuses two members at half the clearance, "
                + "passes them at twice, and refuses a member that rises "
                + "above the nearest net vertex; no level is refused, and "
                + "Auto places the shortest load path among the levels that "
                + "do not collide.");
        }
        catch (Exception exception)
        {
            failures.Add($"ColumnPlacement: {DescribeException(exception)}");
        }

        try
        {
            ValidateStiffnessSeparation(plugin);
            Console.WriteLine(
                "PASS  EI separation: bar sag scales exactly as one over EI, "
                + "which is what lets Fit's one number turn a bending "
                + "shape into millimetres; lean from vertical is measured "
                + "against hand-computed angles.");
        }
        catch (Exception exception)
        {
            failures.Add($"EI separation: {DescribeException(exception)}");
        }

        try
        {
            ValidateMouldContract(plugin);
            Console.WriteLine(
                "PASS  Mould contract: one block on the Result carries the "
                + "built columns and one live frame; counts that must agree "
                + "are refused when they do not, the block survives the JSON "
                + "round trip every Goo boundary makes, and a Result without "
                + "it serialises with no mould key at all.");
        }
        catch (Exception exception)
        {
            failures.Add($"Mould contract: {DescribeException(exception)}");
        }

        try
        {
            ValidateDiagnosticsAppend(plugin);
            Console.WriteLine(
                "PASS  Diagnostics append: native entries land after the "
                + "worker's and leave them untouched, a source replaces its "
                + "own earlier entries instead of piling up, every entry "
                + "validates, and a non-finite value is dropped rather than "
                + "written.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnostics append: {DescribeException(exception)}");
        }

        try
        {
            ValidateColumnsBlock(plugin);
            Console.WriteLine(
                "PASS  Columns block: bare lines become a block whose force "
                + "stays aligned through welding, whose heads name the net "
                + "vertex under them, and whose trees are the members on "
                + "each foot; read back it is the tree Animate walks.");
        }
        catch (Exception exception)
        {
            failures.Add($"Columns block: {DescribeException(exception)}");
        }

        try
        {
            ValidateDeconstructColumnTrees(plugin);
            Console.WriteLine(
                "PASS  Deconstruct column trees: one branch per tree, every "
                + "member lower end to upper end, heads and feet per tree, and "
                + "an absent block gives empty trees rather than an error.");
        }
        catch (Exception exception)
        {
            failures.Add($"Deconstruct column trees: {DescribeException(exception)}");
        }

        try
        {
            ValidateDeconstructForceLines(plugin);
            Console.WriteLine(
                "PASS  Deconstruct force lines: one line per member row, "
                + "between the force-graph vertices of the force edge that "
                + "row's state NAMES, and empty for an FD Result.");
        }
        catch (Exception exception)
        {
            failures.Add($"Deconstruct force lines: {DescribeException(exception)}");
        }

        try
        {
            ValidateDiagnoseRules(plugin);
            Console.WriteLine(
                "PASS  Diagnose rules: the cross-checks no single component "
                + "can make (no principal runs under Columns, a frame with no "
                + "columns, every anchor isolated, more than half the net "
                + "wanting to be pushed) fire on Results built to trigger "
                + "them and stay silent on a clean one; Render prints the "
                + "worker report last and names the components that have not "
                + "run.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnose rules: {DescribeException(exception)}");
        }

        try
        {
            ValidateOutputGrouping(plugin);
            Console.WriteLine(
                "PASS  Output grouping: the anchors of a vault come back as "
                + "SEPARATE STRIPS rather than one merged list, each walked "
                + "end to end instead of sorted by node index, and a closed "
                + "loop comes back walked round. An edge supplied twice, which "
                + "is what the union of the plan and the solved net hands over, "
                + "still leaves the strip walked end to end. A member cutting a "
                + "corner between two notches of one bar is infill, not part of "
                + "that bar. This is what the new tree outputs branch by.");
        }
        catch (Exception exception)
        {
            failures.Add($"Output grouping: {DescribeException(exception)}");
        }

        try
        {
            ValidatePerimeterFromFaces(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.PerimeterFromFaces: an edge used by exactly "
                + "one face is a boundary edge, so a 2x2 grid of quads hands "
                + "back its eight rim nodes and never the centre. This is what "
                + "an FD Result's boundary comes from, since it carries no "
                + "thrust mesh to read naked edges off; with no faces at all it "
                + "returns nothing, which is the caller's cue to say the "
                + "perimeter is an estimate.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"MouldGeometry.PerimeterFromFaces: {DescribeException(exception)}");
        }

        try
        {
            ValidatePhases(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.Phases: reel 0 to 30 brings the sag to Pre-Sag "
                + "with the net still on the ground, raise 30 to 60 lifts it, "
                + "finish 60 to 90 reels the rest, hold 90 to 100 moves nothing, "
                + "at Pre-Sag 0, 0.4 and 1; sag and lift are continuous across "
                + "every boundary to 1e-9 and never decrease anywhere along the "
                + "timeline.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.Phases: {DescribeException(exception)}");
        }

        try
        {
            ValidateLiveColumnNodes(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.LiveColumnNodes: with the net at its solved "
                + "shape every column node is where it was built; with the net "
                + "flat on the ground and drawn in every node lies on the ground "
                + "and the fork sits at its built fraction along the rail; "
                + "halfway up the fork keeps its fraction and trunk, fork and "
                + "main head stay collinear. The fraction is measured, not "
                + "assumed, the main branch is the collinear one and not the "
                + "first listed, and heads are found by HeadNode, which is "
                + "permuted here so plan matching would land them elsewhere.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.LiveColumnNodes: {DescribeException(exception)}");
        }

        try
        {
            ValidateFrameGeometry(plugin);
            Console.WriteLine(
                "PASS  FrameGeometry.Read: a Result carrying a frame is read at "
                + "the frame's own vertices and phase, cables and all; a Result "
                + "with no frame is read at its solved vertices and stands at "
                + "phase final; a frame with no columns block gives an empty "
                + "Columns tree; and where the frame carries column nodes they "
                + "win over the ones the block was built at. With no faces "
                + "anywhere the boundary comes back as an ESTIMATE that never "
                + "closes, and with no principal runs every cable lands in the "
                + "one infill branch.");
        }
        catch (Exception exception)
        {
            failures.Add($"FrameGeometry.Read: {DescribeException(exception)}");
        }

        try
        {
            ValidateMonitorMath(plugin);
            Console.WriteLine(
                "PASS  MonitorMath: an anchor's reaction splits along its "
                + "tensioner axis and across it, signed and against an axis "
                + "that does not arrive unit, the axis is the mean of the "
                + "cables leaving it, the deviation statistics are the RMS, the "
                + "worst and the 95th percentile of the ABSOLUTE values of a "
                + "hand-built field and zero on an empty one, and the "
                + "unstrained length divides by one plus force over EA except "
                + "where that denominator collapses or the EA is not a "
                + "stiffness. A Result's force reaches the newtons EA, EI and "
                + "the capacities are wired in through one factor, 1 for N and "
                + "1000 for kN and null for a unit it does not know, so 0.1 kN "
                + "against EA 1000 cuts to the same 2/1.1 as 100 N.");
        }
        catch (Exception exception)
        {
            failures.Add($"MonitorMath: {DescribeException(exception)}");
        }

        try
        {
            ValidateForcesReadings(plugin);
            Console.WriteLine(
                "PASS  Forces readings: on a net of one bar and one infill "
                + "the member, density and horizontal trees come back bar "
                + "first and infill LAST with Monitor's old numbers, the "
                + "slack flag sits on the pushing infill alone, a 2 m spool "
                + "cuts to 1/1.1 + 1/1.2 with EA wired because 0.1 kN "
                + "became 100 N, one residual per vertex holds its own "
                + "node, utilisation converts kN to N against the capacity, "
                + "and the RES leaves carrying forces.* entries alone, "
                + "Forces as their source, no monitor.* anywhere.");
        }
        catch (Exception exception)
        {
            failures.Add($"Forces readings: {DescribeException(exception)}");
        }

        try
        {
            ValidateSupportsReadings(plugin);
            Console.WriteLine(
                "PASS  Supports readings: two anchors joined only through a "
                + "free node come back as two strips, each reaction split "
                + "SIGNED along its own tensioner axis and across it; a "
                + "plumb post and a diagonal post hand back tip reactions "
                + "along their members, thrusts of 0 and 0.4 over root two, "
                + "leans of 0 and 45 degrees, and utilisations of 5 and 4 "
                + "against 100 N because the kN forces were converted; and "
                + "the RES leaves carrying supports.* entries alone with no "
                + "monitor.* anywhere.");
        }
        catch (Exception exception)
        {
            failures.Add($"Supports readings: {DescribeException(exception)}");
        }

        try
        {
            ValidateSupportsSharedGrouping(plugin);
            Console.WriteLine(
                "PASS  Supports shared grouping: a columns block of three "
                + "members whose Trees name only member 0 falls back, inside "
                + "FrameGeometry.ColumnGroups, to TreesByFoot, and Supports "
                + "branches by THAT: two branches, the count ColumnGroups "
                + "itself returns, all three members measured as [0.5, 0.3] "
                + "on foot 0 and [0.4] on foot 3, and no supports.no_columns; "
                + "with Trees EMPTY beside the same members every member is "
                + "still measured and no_columns still absent; and Forces "
                + "counts the same 3 columns through the same call.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Supports shared grouping: {DescribeException(exception)}");
        }

        try
        {
            ValidateFitReadings(plugin);
            Console.WriteLine(
                "PASS  Fit readings: a frame standing 1, 10 and -2 mm off "
                + "the solved state reads those SIGNED deviations in vertex "
                + "order, RMS root 35 with worst and 95th percentile 10 by "
                + "absolute value, node 1 alone outside the 5 mm tolerance "
                + "and reachability a warning naming the count; no principal "
                + "runs means an empty Bar Sag and fit.bar_sag_absent; the "
                + "intermediate frame is named; a run held at BOTH ends "
                + "under a 0.3 kN hanger sags the hand-computed 50 mm at "
                + "its middle notch and zero at the held ones, because "
                + "0.3 kN became 300 N before it met EI 1000, with "
                + "fit.bar_sag naming the worst; held at one notch the "
                + "same run is a mechanism, three zeros and a "
                + "fit.bar_unheld warning; and the RES leaves carrying "
                + "fit.* entries alone with no monitor.* anywhere.");
        }
        catch (Exception exception)
        {
            failures.Add($"Fit readings: {DescribeException(exception)}");
        }

        try
        {
            ValidateReaderChaining(plugin);
            Console.WriteLine(
                "PASS  Reader chaining: Forces then Supports then Fit "
                + "accumulate all three prefixes on one RES, none clobbering "
                + "another's entries, re-running Forces REPLACES its own "
                + "rather than stacking them, and the monitor.* prefix is "
                + "extinct.");
        }
        catch (Exception exception)
        {
            failures.Add($"Reader chaining: {DescribeException(exception)}");
        }

        try
        {
            ValidateFrameAnchorLines(plugin);
            Console.WriteLine(
                "PASS  FrameGeometry.AnchorLines: a strip of three nodes "
                + "gives two lines joining node i to node i+1 in strip "
                + "order, a single-node strip keeps an EMPTY branch, and "
                + "the branch count equals the strips', so Anchor Lines "
                + "reads against Anchor Nodes branch for branch.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"FrameGeometry.AnchorLines: {DescribeException(exception)}");
        }

        try
        {
            ValidateResultTablesOrder(plugin);
            Console.WriteLine(
                "PASS  ResultTables order: the one table Deconstruct's geometry "
                + "and Forces' numbers are both branched from hands back the "
                + "members in edge order with their ends, forces and ids, no "
                + "force density or horizontal force where an FD Result carries "
                + "none, the support ids as the Result lists them, each "
                + "reaction at the node it acts on, and every node's residual "
                + "on its own node with a zero where the Result carries none. "
                + "On a TNA Result whose state ids and equilibrium edge ids "
                + "disagree the rows come back in ID order with the ends of the "
                + "edge each state names, a support this net does not have is "
                + "dropped, and a zero reaction is not a reaction.");
        }
        catch (Exception exception)
        {
            failures.Add($"ResultTables order: {DescribeException(exception)}");
        }

        try
        {
            ValidateParameterMismatch(plugin);
            Console.WriteLine(
                "PASS  ParameterIdentity.Mismatch: a definition saved against a "
                + "component's older ports is told they moved, naming both what "
                + "was archived and what is registered; one saved against the "
                + "current ports is told nothing; MONITOR's case, twenty-one "
                + "outputs before and after with the Result moved to the front, "
                + "is caught by NAME where a count says nothing; Export's seven "
                + "inputs and two outputs against nine and two is named; and an "
                + "archived chunk with no readable Name raises nothing by "
                + "itself; and where only a name moved, the rename LEADS and "
                + "the equal counts follow it as the reason every wire "
                + "reattached. A count change names WHAT changed: "
                + "Deconstruct's slim lists 'Thrust Mesh', 'Columns', "
                + "'Heads' and 'Feet' as removed, in archived order, and "
                + "still closes check-every-wire; Frame's pure append names "
                + "'Anchor Lines' and closes with existing wires keeping "
                + "their ports instead. SideMoved, which Export's Live hold reads, "
                + "answers for ONE side: an input move holds, by count or "
                + "by name, and this branch's own output-only move does "
                + "not.");
        }
        catch (Exception exception)
        {
            failures.Add($"ParameterIdentity.Mismatch: {DescribeException(exception)}");
        }

        try
        {
            ValidateArchivedNamesFromDefinition(plugin, pluginPath);
            Console.WriteLine(
                "PASS  ParameterIdentity.ArchivedNames: a real Grasshopper "
                + "file, plugin/definitions/ananke_equilibrium_v01.gh, read "
                + "headless through GH_Archive down to the same Container "
                + "chunk a component's Read is handed, gives back the five "
                + "input names and two output names the file actually holds. "
                + "A wrong chunk or item name returns nulls, and nulls are "
                + "silence: the whole load-time warning would stop firing "
                + "with nothing else failing anywhere.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ParameterIdentity.ArchivedNames: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportDefaultTessellation(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.ChooseCells: wired cells win, an "
                + "unwired Cells with faces on the Result is tessellated by "
                + "Export itself, neither gives no sidecar at all, and Courses "
                + "wired alone is ignored with a remark, and only where a "
                + "default tessellation is actually coming; four faces of a "
                + "Result's own mesh, the second of them vertical in plan, "
                + "come out as three cells in face order at course 0, the "
                + "unusable one SKIPPED and counted rather than costing the "
                + "contract, the COMPAS document and every other kind; "
                + "and the sidecar those faces make declares pattern "
                + "'faces', where an author's own cells declare "
                + "'authored'.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.ChooseCells: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportPlan(plugin);
            Console.WriteLine(
                "PASS  ExportPlan: contract and compas always, tessellation "
                + "with cells, columns with a block, in that order; and a "
                + "study Name is ONE path segment, so a separator, a colon "
                + "or a dot-dot is refused before it can write the set "
                + "outside the folder the author chose.");
        }
        catch (Exception exception)
        {
            failures.Add($"ExportPlan: {DescribeException(exception)}");
        }

        try
        {
            ValidateColumnsMesh(plugin);
            Console.WriteLine(
                "PASS  ColumnsMesh: one member is a closed prism of six "
                + "quads and eight cap triangles at the radius asked, a "
                + "zero-length member is nothing and is absent from the "
                + "members list too, two members index cleanly, a DIAGONAL "
                + "member's caps are perpendicular to the member and not to "
                + "world Z, and the radius the document declares is the one "
                + "the mesh was built at.");
        }
        catch (Exception exception)
        {
            failures.Add($"ColumnsMesh: {DescribeException(exception)}");
        }

        try
        {
            ValidateLiveUploader(plugin);
            Console.WriteLine(
                "PASS  LiveUploader: the retry schedule is 2, 4, 8 seconds "
                + "then deferred, the routes are the studio's, a 2xx is "
                + "stored, a 409 retries until the schedule runs out, "
                + "anything else is refused, and the set key reads the "
                + "Name, the Studio and every kind EXCEPT the compas "
                + "document's own bytes, whose fresh uuid per serialisation "
                + "would stop the key ever repeating; the compas kind's "
                + "presence still counts. The study name is escaped into "
                + "both routes, and a deferred kind names the run the "
                + "studio is busy with when the 409 body carries one.");
        }
        catch (Exception exception)
        {
            failures.Add($"LiveUploader: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportWriteFolder(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.TryResolveWriteFolder: an "
                + "extensionless Path is the folder to write into even "
                + "before it exists, a Path with an extension gives its "
                + "own directory, and a Path that is not rooted, a bare "
                + "name or a relative path with directories of its own, "
                + "is refused rather than written to whatever the "
                + "process's working directory happens to be.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.TryResolveWriteFolder: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateIconMap(plugin, componentTypes, pluginPath);
            Console.WriteLine(
                "PASS  Icon family: every component has "
                + "exactly one icon-map entry, keyed the way the loader reads "
                + "the resource, labelled the two letters the spec gives, "
                + "categorised as the panel the component actually registers "
                + "under, and drawn in that category's own fill, sampled off "
                + "the embedded badge at (12, 20).");
        }
        catch (Exception exception)
        {
            failures.Add($"Icon family: {DescribeException(exception)}");
        }

        if (failures.Count == 0)
        {
            Console.WriteLine(
                "Native component smoke test passed; Rhino was not launched.");
            return 0;
        }

        Console.Error.WriteLine(
            $"ERROR: {failures.Count} native component validation " +
            $"{(failures.Count == 1 ? "failure" : "failures")}:");
        foreach (string failure in failures)
            Console.Error.WriteLine($"  - {failure}");
        return 5;
    }

    private static Assembly LoadAssembly(string path)
    {
        string fullPath = Path.GetFullPath(path);
        AssemblyName requested = AssemblyName.GetAssemblyName(fullPath);
        Assembly? loaded = AssemblyLoadContext.Default.Assemblies.FirstOrDefault(
            assembly => AssemblyName.ReferenceMatchesDefinition(
                assembly.GetName(),
                requested));
        return loaded
            ?? AssemblyLoadContext.Default.LoadFromAssemblyPath(fullPath);
    }

    private static Assembly? ResolveAssembly(
        AssemblyName assemblyName,
        IEnumerable<string> probingDirectories)
    {
        string simpleName = assemblyName.Name ?? string.Empty;
        if (string.IsNullOrWhiteSpace(simpleName))
            return null;

        lock (ResolverLock)
        {
            if (!Resolving.Add(simpleName))
                return null;
        }

        try
        {
            Assembly? loaded =
                AssemblyLoadContext.Default.Assemblies.FirstOrDefault(
                    assembly => AssemblyName.ReferenceMatchesDefinition(
                        assembly.GetName(),
                        assemblyName));
            if (loaded is not null)
                return loaded;

            foreach (string directory in probingDirectories)
            {
                foreach (string extension in new[] { ".dll", ".gha" })
                {
                    string candidate =
                        Path.Combine(directory, simpleName + extension);
                    if (!File.Exists(candidate))
                        continue;
                    try
                    {
                        return AssemblyLoadContext.Default
                            .LoadFromAssemblyPath(candidate);
                    }
                    catch (FileLoadException)
                    {
                        // A candidate with the same filename may have a
                        // different identity; continue to the next location.
                    }
                    catch (BadImageFormatException)
                    {
                        // Ignore native or incompatible files in Rhino's
                        // probing directories.
                    }
                }
            }

            return null;
        }
        finally
        {
            lock (ResolverLock)
                Resolving.Remove(simpleName);
        }
    }

    private static IEnumerable<Type> GetLoadableTypes(Assembly assembly)
    {
        try
        {
            return assembly.GetTypes();
        }
        catch (ReflectionTypeLoadException exception)
        {
            string details = string.Join(
                Environment.NewLine,
                exception.LoaderExceptions
                    .Where(item => item is not null)
                    .Select(item => $"  - {DescribeException(item!)}"));
            throw new InvalidOperationException(
                "One or more plugin types could not be loaded:" +
                Environment.NewLine +
                details,
                exception);
        }
    }

    private static bool IsConcretePublicGrasshopperComponent(Type type)
    {
        return type.IsClass
            && !type.IsAbstract
            && type.IsVisible
            && EnumerateBaseTypes(type)
                .Any(baseType =>
                    string.Equals(
                        baseType.FullName,
                        GrasshopperComponentBase,
                        StringComparison.Ordinal));
    }

    private static bool IsConcretePublicPersistentParameter(Type type)
    {
        return type.IsClass
            && !type.IsAbstract
            && type.IsVisible
            && EnumerateBaseTypes(type)
                .Any(baseType =>
                    baseType.IsGenericType &&
                    string.Equals(
                        baseType.GetGenericTypeDefinition().FullName,
                        GrasshopperPersistentParamBase,
                        StringComparison.Ordinal));
    }

    private static Type? FindRhinoCodeBase(Type componentType)
    {
        return EnumerateBaseTypes(componentType)
            .FirstOrDefault(baseType =>
            {
                string namespaceName = baseType.Namespace ?? string.Empty;
                string fullName = baseType.FullName ?? string.Empty;
                string assemblyName =
                    baseType.Assembly.GetName().Name ?? string.Empty;
                return namespaceName.StartsWith(
                           RhinoCodeNamespace,
                           StringComparison.OrdinalIgnoreCase)
                    || fullName.Contains(
                        RhinoCodeNamespace,
                        StringComparison.OrdinalIgnoreCase)
                    || assemblyName.Contains(
                        RhinoCodeNamespace,
                        StringComparison.OrdinalIgnoreCase);
            });
    }

    private static IEnumerable<Type> EnumerateBaseTypes(Type type)
    {
        for (Type? current = type.BaseType;
             current is not null;
             current = current.BaseType)
        {
            yield return current;
        }
    }

    private static string ReadDisplayName(object instance, Type componentType)
    {
        try
        {
            object? value = componentType.GetProperty("Name")?.GetValue(instance);
            if (value is string name && !string.IsNullOrWhiteSpace(name))
                return name;
        }
        catch (TargetInvocationException)
        {
            // Name is diagnostic sugar; constructor validation has succeeded.
        }

        return componentType.Name;
    }

    private static void ValidateFlattenedInputs(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!FlattenedInputs.TryGetValue(typeName, out int[]? expected))
            return;

        object? parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance);
        object? inputs = parameters?
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters);
        if (inputs is not IList list)
            throw new InvalidOperationException(
                "Could not inspect component input parameters.");

        foreach (int index in expected)
        {
            object parameter = list[index]
                ?? throw new InvalidOperationException(
                    $"Input {index} is null.");
            string mapping = parameter
                .GetType()
                .GetProperty("DataMapping")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    mapping,
                    "Flatten",
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    $"Input {index} must flatten bundle collection trees; " +
                    $"mapping was '{mapping}'.");
            }
        }
    }

    private static void ValidatePreviewCapability(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!RequiredPreviewComponents.Contains(typeName))
            return;

        object? value = componentType
            .GetProperty("IsPreviewCapable")
            ?.GetValue(instance);
        if (value is not true)
        {
            throw new InvalidOperationException(
                "Graphic-statics display components must explicitly remain " +
                "viewport-preview-capable even when their primary input or " +
                "output is custom Goo.");
        }
    }

    private static void ValidateNativePreviewVisibilityGuard(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!NativeVisibilityGuardComponents.Contains(typeName))
            return;

        Type? previewBase = componentType.BaseType;
        if (!string.Equals(
                previewBase?.FullName,
                "Ananke.COMPAS.Native.Components.NativePreviewComponentBase",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Custom diagram preview components must derive from the " +
                "shared native visibility guard so Grasshopper's Preview " +
                "toggle controls all renderer-owned geometry.");
        }

        PropertyInfo hiddenProperty = componentType.GetProperty("Hidden")
            ?? throw new InvalidOperationException(
                "Preview component does not expose Grasshopper's Hidden state.");
        if (!hiddenProperty.CanRead || !hiddenProperty.CanWrite)
        {
            throw new InvalidOperationException(
                "Preview component Hidden state must remain readable and " +
                "writable by Grasshopper.");
        }

        hiddenProperty.SetValue(instance, true);
        if (hiddenProperty.GetValue(instance) is not true)
        {
            throw new InvalidOperationException(
                "Preview component did not retain Grasshopper's hidden state.");
        }
        hiddenProperty.SetValue(instance, false);
    }

    private static void ValidateVisualiseContract(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!VisualiseContracts.TryGetValue(
                typeName,
                out (string[] Inputs, string[] Outputs) contract))
        {
            return;
        }

        object parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance)
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} parameters.");
        IList inputs = parameters
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} inputs.");
        IList outputs = parameters
            .GetType()
            .GetProperty("Output")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} outputs.");
        ValidateParameterNames(
            inputs,
            contract.Inputs,
            componentType.Name,
            "input");
        ValidateParameterNames(
            outputs,
            contract.Outputs,
            componentType.Name,
            "output");
    }

    /// <summary>
    /// Spine components (Pattern, Supports, and later stages on the same
    /// wire) key their ports on the type nickname, not a descriptive word,
    /// so a wire is self-describing. This asserts the component's own
    /// Name/NickName, its tab (SubCategory), and every port's NickName
    /// against the redesign's fixed surface.
    /// </summary>
    private static void ValidateSpineComponentContract(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!SpineComponentContracts.TryGetValue(
                typeName,
                out (string Name, string NickName, string Tab,
                    string[] InputNickNames, string[] OutputNickNames)
                    contract))
        {
            return;
        }

        string actualName =
            componentType.GetProperty("Name")?.GetValue(instance) as string
            ?? string.Empty;
        if (!string.Equals(actualName, contract.Name, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} Name must be '{contract.Name}'; " +
                $"received '{actualName}'.");
        }

        string actualNickName =
            componentType.GetProperty("NickName")?.GetValue(instance) as string
            ?? string.Empty;
        if (!string.Equals(
                actualNickName,
                contract.NickName,
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} NickName must be " +
                $"'{contract.NickName}'; received '{actualNickName}'.");
        }

        string actualTab =
            componentType.GetProperty("SubCategory")?.GetValue(instance)
                as string
            ?? string.Empty;
        if (!string.Equals(actualTab, contract.Tab, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} tab must be '{contract.Tab}'; " +
                $"received '{actualTab}'.");
        }

        object parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance)
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} parameters.");
        IList inputs = parameters
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} inputs.");
        IList outputs = parameters
            .GetType()
            .GetProperty("Output")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} outputs.");
        ValidateParameterNickNames(
            inputs,
            contract.InputNickNames,
            componentType.Name,
            "input");
        ValidateParameterNickNames(
            outputs,
            contract.OutputNickNames,
            componentType.Name,
            "output");
    }

    private static void ValidateParameterNickNames(
        IList parameters,
        IReadOnlyList<string> expected,
        string owner,
        string label)
    {
        if (parameters.Count != expected.Count)
        {
            throw new InvalidOperationException(
                $"{owner} expected {expected.Count} {label}s, " +
                $"found {parameters.Count}.");
        }

        for (int index = 0; index < expected.Count; index++)
        {
            object parameter = parameters[index]
                ?? throw new InvalidOperationException(
                    $"{owner} {label} {index} is null.");
            string actual = parameter
                .GetType()
                .GetProperty("NickName")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    actual,
                    expected[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{owner} {label} {index} nickname must be " +
                    $"'{expected[index]}'; received '{actual}'.");
            }
        }
    }

    private static void ValidateParameterNames(
        IList parameters,
        IReadOnlyList<string> expected,
        string owner,
        string label)
    {
        if (parameters.Count != expected.Count)
        {
            throw new InvalidOperationException(
                $"{owner} expected {expected.Count} {label}s, " +
                $"found {parameters.Count}.");
        }

        for (int index = 0; index < expected.Count; index++)
        {
            object parameter = parameters[index]
                ?? throw new InvalidOperationException(
                    $"{owner} {label} {index} is null.");
            string actual = parameter
                .GetType()
                .GetProperty("Name")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    actual,
                    expected[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{owner} {label} {index} must be " +
                    $"'{expected[index]}'; received '{actual}'.");
            }
        }
    }

    /// <summary>
    /// The most-derived Icon property, which is where a component's badge
    /// comes from: <c>PluginResources.Icon</c> returns null for a resource
    /// that is not embedded, and a null icon is a component with no badge on
    /// the toolbar at all.
    /// </summary>
    private static object RequireIconBitmap(object instance, Type componentType)
    {
        PropertyInfo? iconProperty = null;
        for (Type? current = componentType;
             current is not null && iconProperty is null;
             current = current.BaseType)
        {
            iconProperty = current.GetProperty(
                "Icon",
                BindingFlags.Instance |
                BindingFlags.NonPublic |
                BindingFlags.DeclaredOnly);
        }
        return iconProperty?.GetValue(instance)
            ?? throw new InvalidOperationException(
                "Component icon is missing.");
    }

    private static void ValidateIcon(object instance, Type componentType)
    {
        object icon = RequireIconBitmap(instance, componentType);
        int width = Convert.ToInt32(
            icon.GetType().GetProperty("Width")?.GetValue(icon));
        int height = Convert.ToInt32(
            icon.GetType().GetProperty("Height")?.GetValue(icon));
        if (width != 24 || height != 24)
        {
            throw new InvalidOperationException(
                $"Component icon must be 24x24; received {width}x{height}.");
        }
    }

    private static void RecordDocumentGuid(
        object instance,
        Type objectType,
        IDictionary<Guid, string> documentGuids,
        ICollection<string> failures)
    {
        object? value = objectType
            .GetProperty("ComponentGuid")
            ?.GetValue(instance);
        if (value is not Guid guid || guid == Guid.Empty)
        {
            failures.Add(
                $"{objectType.FullName}: ComponentGuid is missing or empty.");
            return;
        }
        string name = objectType.FullName ?? objectType.Name;
        if (documentGuids.TryGetValue(guid, out string? existing))
        {
            failures.Add(
                $"{name}: ComponentGuid {guid} duplicates {existing}.");
            return;
        }
        documentGuids.Add(guid, name);
    }

    /// <summary>
    /// Constructs the unified <c>ResultDto</c> directly from the loaded
    /// plugin assembly via reflection (this harness has no compile-time
    /// reference to <c>Ananke.COMPAS.Native.Contracts</c>) and exercises
    /// its <c>Validate()</c> rules: a valid TNA result (with reciprocal
    /// graphs), a valid FD result (without them), and an invalid TNA
    /// result missing its graphs.
    /// </summary>
    private static void ValidateResultContract(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");

        object validTna = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: CreateInstance(graphType),
            forceGraph: CreateInstance(graphType));
        RequireNoValidationErrors(validTna, "Valid TNA ResultDto");

        object validFd = CreateResultDto(
            resultType,
            solver: "fd",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        RequireNoValidationErrors(validFd, "Valid FD ResultDto");

        object invalidTna = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        RequireValidationErrors(
            invalidTna,
            "Invalid TNA ResultDto without reciprocal graphs");
    }

    /// <summary>
    /// <c>ResultDto.RawWire</c> is <c>[JsonIgnore]</c>, so the shared
    /// <c>ContractJson.DeepClone</c> round trip every other snapshot
    /// boundary relies on would silently drop it. <c>ResultGoo</c>
    /// overrides <c>ContractGoo{TContract}.Snapshot</c> to reattach it;
    /// this exercises the exact paths the whole-branch review flagged as
    /// broken: the public constructor (what
    /// <c>SolverComponents.cs</c>'s <c>new ResultGoo(result.Result)</c>
    /// calls on every live solve) and <c>Duplicate()</c> (what a
    /// Grasshopper wire fan-out calls) must both preserve RawWire, while
    /// Contract-mode serialisation (<c>ContractJson.Serialize</c>) must
    /// still exclude it from the persisted contract.
    /// </summary>
    private static void ValidateResultGooRawWireSnapshot(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type resultGooType = RequireContractType(plugin, "ResultGoo");
        const string rawWire = "{\"worker\":\"raw\"}";

        object result = CreateResultDto(
            resultType,
            solver: "fd",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        SetContractProperty(result, resultType, "RawWire", rawWire);

        object goo = Activator.CreateInstance(resultGooType, result)
            ?? throw new InvalidOperationException(
                $"Could not construct {resultGooType.FullName}.");
        RequireRawWire(goo, resultType, rawWire, "Constructed ResultGoo");

        MethodInfo duplicateMethod = resultGooType.GetMethod("Duplicate")
            ?? throw new InvalidOperationException(
                "ResultGoo.Duplicate() was not found.");
        object duplicated = duplicateMethod.Invoke(goo, null)
            ?? throw new InvalidOperationException(
                "ResultGoo.Duplicate() returned null.");
        RequireRawWire(duplicated, resultType, rawWire, "Duplicated ResultGoo");

        Type contractJsonType = RequireContractType(plugin, "ContractJson");
        MethodInfo serializeMethod = contractJsonType.GetMethod(
            "Serialize",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ContractJson.Serialize was not found.");
        string serialized =
            serializeMethod.MakeGenericMethod(resultType)
                .Invoke(null, new object[] { result }) as string
            ?? throw new InvalidOperationException(
                "ContractJson.Serialize returned an unexpected type.");
        if (serialized.Contains("rawWire", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "Contract-mode serialisation must exclude RawWire, but the " +
                "serialised ResultDto contains it.");
        }
    }

    private static void RequireRawWire(
        object goo,
        Type resultType,
        string expected,
        string label)
    {
        PropertyInfo valueProperty = goo.GetType().GetProperty("Value")
            ?? throw new InvalidOperationException(
                $"{goo.GetType().FullName} does not expose Value.");
        object? value = valueProperty.GetValue(goo);
        if (value is null || !resultType.IsInstanceOfType(value))
        {
            throw new InvalidOperationException(
                $"{label} lost its ResultDto payload.");
        }

        string? rawWire =
            resultType.GetProperty("RawWire")?.GetValue(value) as string;
        if (!string.Equals(rawWire, expected, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{label} lost RawWire; expected '{expected}', found " +
                $"'{rawWire ?? "<null>"}'.");
        }
    }

    private static object CreateResultDto(
        Type resultType,
        string solver,
        object equilibrium,
        object? formGraph,
        object? forceGraph)
    {
        object instance = CreateInstance(resultType);
        SetContractProperty(instance, resultType, "Solver", solver);
        SetContractProperty(instance, resultType, "Equilibrium", equilibrium);
        SetContractProperty(instance, resultType, "FormGraph", formGraph);
        SetContractProperty(instance, resultType, "ForceGraph", forceGraph);
        return instance;
    }

    private static object CreateInstance(Type type)
    {
        return Activator.CreateInstance(type)
            ?? throw new InvalidOperationException(
                $"Could not construct {type.FullName}.");
    }

    private static void SetContractProperty(
        object instance,
        Type type,
        string propertyName,
        object? value)
    {
        PropertyInfo property = type.GetProperty(propertyName)
            ?? throw new InvalidOperationException(
                $"{type.FullName} does not expose property '{propertyName}'.");
        property.SetValue(instance, value);
    }

    private static void RequireNoValidationErrors(object instance, string label)
    {
        IReadOnlyList<string> errors = InvokeValidate(instance);
        if (errors.Count > 0)
        {
            throw new InvalidOperationException(
                $"{label} failed validation: {string.Join(" ", errors)}");
        }
    }

    private static void RequireValidationErrors(object instance, string label)
    {
        IReadOnlyList<string> errors = InvokeValidate(instance);
        if (errors.Count == 0)
        {
            throw new InvalidOperationException(
                $"{label} unexpectedly passed validation.");
        }
    }

    private static IReadOnlyList<string> InvokeValidate(object instance)
    {
        MethodInfo validateMethod = instance.GetType().GetMethod("Validate")
            ?? throw new InvalidOperationException(
                $"{instance.GetType().FullName} does not expose Validate().");
        object? result = validateMethod.Invoke(instance, null);
        return result as IReadOnlyList<string>
            ?? throw new InvalidOperationException(
                "Validate() returned an unexpected type.");
    }

    /// <summary>
    /// The Mould block: one nullable block on the Result that carries the
    /// built columns and one live frame. Validation is measured on the
    /// counts that must agree, and the round trip is measured because every
    /// Goo boundary deep-clones through JSON, so a block that does not
    /// survive serialisation does not exist.
    /// </summary>
    private static void ValidateMouldContract(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Points(params object[] items)
        {
            Array array = Array.CreateInstance(point, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        Array Edges(params (int U, int V)[] pairs)
        {
            Array array = Array.CreateInstance(edge, pairs.Length);
            for (int i = 0; i < pairs.Length; i++)
                array.SetValue(Activator.CreateInstance(edge, pairs[i].U, pairs[i].V), i);
            return array;
        }
        object Equilibrium()
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices",
                Points(P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(3, 0, 0)));
            return eq;
        }
        object Columns(double[] force, int[] headNode)
        {
            object c = CreateInstance(columnsType);
            SetContractProperty(c, columnsType, "Nodes",
                Points(P(0, 0, 0), P(0, 0, 5), P(3, 0, 0), P(3, 0, 6)));
            SetContractProperty(c, columnsType, "Members", Edges((0, 1), (2, 3)));
            SetContractProperty(c, columnsType, "MemberForce", force);
            SetContractProperty(c, columnsType, "Trees",
                new int[][] { new[] { 0 }, new[] { 1 } });
            SetContractProperty(c, columnsType, "Heads", new[] { 1, 3 });
            SetContractProperty(c, columnsType, "Feet", new[] { 0, 2 });
            SetContractProperty(c, columnsType, "HeadNode", headNode);
            SetContractProperty(c, columnsType, "Branching", 1);
            SetContractProperty(c, columnsType, "ForkFraction", 0.65);
            return c;
        }
        object Frame(int vertexCount, Array? columnNodes)
        {
            object f = CreateInstance(frameType);
            SetContractProperty(f, frameType, "Time", 50.0);
            SetContractProperty(f, frameType, "Phase", "raise");
            SetContractProperty(f, frameType, "Lift", 0.5);
            SetContractProperty(f, frameType, "Sag", 0.5);
            SetContractProperty(f, frameType, "Vertices",
                Points(Enumerable.Range(0, vertexCount)
                    .Select(i => P(i, 0, 1)).ToArray()));
            SetContractProperty(f, frameType, "ColumnNodes", columnNodes);
            return f;
        }
        object Mould(object? columns, object? frame)
        {
            object m = CreateInstance(mouldType);
            SetContractProperty(m, mouldType, "Ground", 0.0);
            SetContractProperty(m, mouldType, "Columns", columns);
            SetContractProperty(m, mouldType, "Frame", frame);
            return m;
        }
        object Result(object mould)
        {
            object r = CreateResultDto(resultType, "fd", Equilibrium(), null, null);
            SetContractProperty(r, resultType, "Mould", mould);
            return r;
        }

        // Good: two posts, one frame with live column nodes for all four.
        object good = Result(Mould(
            Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 }),
            Frame(4, Points(P(0, 0, 0), P(0, 0, 4), P(3, 0, 0), P(3, 0, 5)))));
        RequireNoValidationErrors(good, "Result with a full Mould block");

        RequireValidationErrors(
            Result(Mould(Columns(new[] { 100.0 }, new[] { 1, 2 }), null)),
            "MemberForce one short of Members");
        RequireValidationErrors(
            Result(Mould(Columns(new[] { 100.0, 200.0 }, new[] { 1, 99 }), null)),
            "HeadNode outside the net");
        RequireValidationErrors(
            Result(Mould(null, Frame(3, null))),
            "Frame with the wrong vertex count");
        RequireValidationErrors(
            Result(Mould(null, Frame(4, Points(P(0, 0, 0))))),
            "ColumnNodes present with Columns absent");

        // Round trip through the same serialiser every Goo boundary uses.
        Type json = RequireContractType(plugin, "ContractJson");
        MethodInfo serialize = json.GetMethod("Serialize")!.MakeGenericMethod(resultType);
        MethodInfo deserialize = json.GetMethod("Deserialize")!.MakeGenericMethod(resultType);
        string text = (string)serialize.Invoke(null, new[] { good })!;
        if (!text.Contains("\"mould\"", StringComparison.Ordinal) ||
            !text.Contains("\"headNode\"", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A Result with a Mould block must serialise its mould and headNode keys.");
        }
        object back = deserialize.Invoke(null, new object[] { text })!;
        RequireNoValidationErrors(back, "Round-tripped Result with Mould");
        object mouldBack = resultType.GetProperty("Mould")!.GetValue(back)
            ?? throw new InvalidOperationException("Mould was lost in the round trip.");
        object columnsBack = mouldType.GetProperty("Columns")!.GetValue(mouldBack)
            ?? throw new InvalidOperationException("Mould.Columns was lost in the round trip.");
        int members = ((ICollection)columnsType.GetProperty("Members")!.GetValue(columnsBack)!).Count;
        if (members != 2)
            throw new InvalidOperationException($"Two members went in and {members} came back.");
        int trees = ((ICollection)columnsType.GetProperty("Trees")!.GetValue(columnsBack)!).Count;
        int[] headNode = ((IEnumerable)columnsType.GetProperty("HeadNode")!.GetValue(columnsBack)!).Cast<int>().ToArray();
        object frameBack = mouldType.GetProperty("Frame")!.GetValue(mouldBack)
            ?? throw new InvalidOperationException("Mould.Frame was lost in the round trip.");
        double time = (double)frameType.GetProperty("Time")!.GetValue(frameBack)!;
        int columnNodes = ((ICollection)frameType.GetProperty("ColumnNodes")!.GetValue(frameBack)!).Count;
        if (trees != 2 || !headNode.SequenceEqual(new[] { 1, 2 }) || Math.Abs(time - 50.0) > 1e-12 || columnNodes != 4)
        {
            throw new InvalidOperationException(
                $"The round trip must keep every field: trees {trees}, headNode [{string.Join(",", headNode)}], time {time}, columnNodes {columnNodes}.");
        }

        // A Result without the block serialises exactly as it always did.
        string bare = (string)serialize.Invoke(
            null, new[] { CreateResultDto(resultType, "fd", Equilibrium(), null, null) })!;
        if (bare.Contains("\"mould\"", StringComparison.Ordinal))
            throw new InvalidOperationException("A Result with no Mould block must not write a mould key.");
        RequireNoValidationErrors(
            deserialize.Invoke(null, new object[] { bare })!,
            "Old-shape Result JSON with no mould key");

        // Ground -1 is Auto, which is a level asked for and so has to travel
        // in the block. Anything below it is not a level at all.
        object autoColumns = Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 });
        SetContractProperty(autoColumns, columnsType, "GroundAsked", -1);
        RequireNoValidationErrors(
            Result(Mould(autoColumns, null)), "Mould block asking for Ground -1 (Auto)");

        object belowColumns = Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 });
        SetContractProperty(belowColumns, columnsType, "GroundAsked", -2);
        IReadOnlyList<string> groundErrors =
            InvokeValidate(Result(Mould(belowColumns, null)));
        if (!groundErrors.Any(e => e.Contains("groundAsked", StringComparison.Ordinal)))
        {
            throw new InvalidOperationException(
                "GroundAsked -2 is below Auto and must be refused by name; got "
                + $"[{string.Join("; ", groundErrors)}].");
        }
    }

    /// <summary>
    /// Native components append diagnostics INTO the Result instead of
    /// printing a report. The worker's entries stay first and untouched, a
    /// source's own earlier entries are replaced rather than piled up, and
    /// every native entry passes DiagnosticDto.Validate, because the worker
    /// codecs throw on an invalid one and Diagnose must be able to trust the
    /// list.
    /// </summary>
    private static void ValidateDiagnosticsAppend(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type diagnosticType = RequireContractType(plugin, "DiagnosticDto");
        Type helper = RequireComponentType(plugin, "ResultDiagnostics");
        MethodInfo entry = RequirePublicStatic(helper, "Entry");
        MethodInfo replace = RequirePublicStatic(helper, "Replace");
        MethodInfo sourceOf = RequirePublicStatic(helper, "SourceOf");

        object Worker(string code)
        {
            object d = CreateInstance(diagnosticType);
            SetContractProperty(d, diagnosticType, "Code", code);
            SetContractProperty(d, diagnosticType, "Severity", "info");
            SetContractProperty(d, diagnosticType, "Message", "from the worker");
            SetContractProperty(d, diagnosticType, "Provenance",
                new Dictionary<string, string> { ["source"] = "COMPAS TNA worker" });
            return d;
        }
        object Native(string code, double? value)
        {
            return entry.Invoke(null, new object?[]
            {
                "Columns", code, "info", "measured by Columns", value, 60.0, "degrees", null,
            })!;
        }
        Array Typed(params object[] items)
        {
            Array array = Array.CreateInstance(diagnosticType, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        IReadOnlyList<object> DiagnosticsOf(object result) =>
            ((IEnumerable)resultType.GetProperty("Diagnostics")!.GetValue(result)!)
                .Cast<object>().ToList();

        object workerA = Worker("worker.a");
        object workerB = Worker("worker.b");
        object result = CreateResultDto(
            resultType, "fd", CreateInstance(equilibriumType), null, null);
        SetContractProperty(result, resultType, "Diagnostics", Typed(workerA, workerB));

        object appended = replace.Invoke(null, new object?[]
        {
            result, "Columns",
            Typed(Native("columns.lean", 12.0), Native("columns.bars", 2.0), Native("columns.force_max", 900.0)),
        })!;
        IReadOnlyList<object> all = DiagnosticsOf(appended);
        if (all.Count != 5)
            throw new InvalidOperationException($"Two worker plus three native entries is five; got {all.Count}.");
        if (!ReferenceEquals(all[0], workerA) || !ReferenceEquals(all[1], workerB))
            throw new InvalidOperationException("The worker's entries must stay first and untouched.");
        for (int i = 2; i < 5; i++)
        {
            RequireNoValidationErrors(all[i], $"native diagnostic {i}");
            string source = (string)sourceOf.Invoke(null, new[] { all[i] })!;
            if (source != "Columns")
                throw new InvalidOperationException($"Native entry {i} has source '{source}', expected 'Columns'.");
        }

        object replaced = replace.Invoke(null, new object?[]
        {
            appended, "Columns", Typed(Native("columns.lean", 15.0)),
        })!;
        if (DiagnosticsOf(replaced).Count != 3)
            throw new InvalidOperationException("Replacing a source's entries must drop its earlier ones, leaving two worker plus one.");

        object nan = Native("columns.foot_drift", double.NaN);
        if (diagnosticType.GetProperty("Value")!.GetValue(nan) is not null)
            throw new InvalidOperationException("A non-finite Value must be dropped to null, not written and refused later.");
    }

    /// <summary>
    /// The block builder: bare lines in, a block out whose members keep
    /// their force aligned even though welding drops zero-length lines,
    /// whose heads name the net vertex under them, and whose trees are the
    /// members that stand on each foot. Read back into a ColumnTree it is
    /// the same tree Animate walks today.
    /// </summary>
    private static void ValidateColumnsBlock(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo columnsBlock = RequirePublicStatic(geometry, "ColumnsBlock");
        MethodInfo treeFromBlock = RequirePublicStatic(geometry, "TreeFromBlock");
        MethodInfo treesByFoot = RequirePublicStatic(geometry, "TreesByFoot");

        Type lineList = columnsBlock.GetParameters()[0].ParameterType;
        Type line = lineList.GetGenericArguments()[0];
        Type point3d = columnsBlock.GetParameters()[2].ParameterType.GetElementType()!;

        object Pt(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        Type concreteList = typeof(List<>).MakeGenericType(line);
        object members = Activator.CreateInstance(concreteList)!;
        MethodInfo add = concreteList.GetMethod("Add")!;
        void Member(object from, object to) =>
            add.Invoke(members, new[] { Activator.CreateInstance(line, from, to) });

        // Tree A: trunk to a fork, two branches. Tree B: one post. The
        // zero-length line between the trunk and the first branch welds
        // both ends to the same node and is dropped, along with its
        // sentinel force, so a naive pass-through would misalign every
        // force after it.
        Member(Pt(0, 0, 0), Pt(0, 0, 5));
        Member(Pt(0, 0, 5), Pt(1, 0, 8));
        Member(Pt(0, 0, 5), Pt(0, 0, 5));
        Member(Pt(0, 0, 5), Pt(-1, 0, 8));
        Member(Pt(10, 0, 0), Pt(10, 0, 6));
        double[] force = { 300.0, 100.0, 999.0, 100.0, 200.0 };

        Array net = Array.CreateInstance(point3d, 4);
        net.SetValue(Pt(1, 0, 8), 0);
        net.SetValue(Pt(-1, 0, 8), 1);
        net.SetValue(Pt(10, 0, 6), 2);
        net.SetValue(Pt(5, 0, 0), 3);

        object block = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, 0, 0, 0.65, 0,
        })!;
        Type blockType = block.GetType();
        int[] Ints(string name) =>
            ((IEnumerable)blockType.GetProperty(name)!.GetValue(block)!).Cast<int>().ToArray();
        double[] Doubles(string name) =>
            ((IEnumerable)blockType.GetProperty(name)!.GetValue(block)!).Cast<double>().ToArray();
        int Count(string name) =>
            ((ICollection)blockType.GetProperty(name)!.GetValue(block)!).Count;

        if (Count("Nodes") != 6 || Count("Members") != 4)
            throw new InvalidOperationException($"Six nodes and four members; got {Count("Nodes")} and {Count("Members")}.");
        if (!Doubles("MemberForce").SequenceEqual(new[] { 300.0, 100.0, 100.0, 200.0 }))
            throw new InvalidOperationException("A dropped member must take its force with it and leave the rest aligned.");
        if (!Ints("Heads").SequenceEqual(new[] { 2, 3, 5 }))
            throw new InvalidOperationException($"Heads are the nodes that are only ever an upper end: expected 2,3,5, got {string.Join(",", Ints("Heads"))}.");
        if (!Ints("Forks").SequenceEqual(new[] { 1 }))
            throw new InvalidOperationException("The one node that is both a lower and an upper end is the fork.");
        if (!Ints("Feet").SequenceEqual(new[] { 0, 4 }))
            throw new InvalidOperationException("Feet are the nodes that are only ever a lower end.");
        if (!Ints("HeadNode").SequenceEqual(new[] { 0, 1, 2 }))
            throw new InvalidOperationException($"Each head names the net vertex under it: expected 0,1,2, got {string.Join(",", Ints("HeadNode"))}.");
        var trees = ((IEnumerable)blockType.GetProperty("Trees")!.GetValue(block)!)
            .Cast<IEnumerable<int>>().Select(t => t.ToArray()).ToArray();
        if (trees.Length != 2 || !trees[0].SequenceEqual(new[] { 0, 1, 2 }) || !trees[1].SequenceEqual(new[] { 3 }))
            throw new InvalidOperationException("Two feet give two trees: members 0,1,2 stand on the first foot and member 3 on the second.");

        object tree = treeFromBlock.Invoke(null, new[] { block })!;
        Type treeType = tree.GetType();
        int nodes = ((ICollection)treeType.GetProperty("Nodes")!.GetValue(tree)!).Count;
        int notches = ((ICollection)treeType.GetProperty("Notches")!.GetValue(tree)!).Count;
        int feet = ((ICollection)treeType.GetProperty("Feet")!.GetValue(tree)!).Count;
        if (nodes != 6 || notches != 3 || feet != 2)
            throw new InvalidOperationException($"Read back, the tree has {nodes} nodes, {notches} notches, {feet} feet; expected 6, 3, 2.");
        var byFoot = ((IEnumerable)treesByFoot.Invoke(null, new[] { tree })!)
            .Cast<IEnumerable<int>>().Select(t => t.ToArray()).ToArray();
        if (byFoot.Length != 2 || byFoot[0].Length != 3 || byFoot[1].Length != 1)
            throw new InvalidOperationException("TreesByFoot on the read-back tree must give the same two groups.");

        // Auto is GroundAsked -1 and the block must carry it. The contract
        // was relaxed to accept -1 and the harness fixture accepts it, but
        // both exercised a hand-built DTO; the block builder clamped the -1
        // the component passes to 0, so no Result the production path can
        // build ever carried it and Auto was indistinguishable from Ground 0
        // downstream.
        object auto = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, -1, 3, 0.65, 0,
        })!;
        Type autoType = auto.GetType();
        if ((int)autoType.GetProperty("GroundAsked")!.GetValue(auto)! != -1)
            throw new InvalidOperationException("A block built by Auto must carry GroundAsked -1, not a 0 that reads as Ground 0 asked.");
        if ((int)autoType.GetProperty("GroundPlaced")!.GetValue(auto)! != 3)
            throw new InvalidOperationException("GroundPlaced is what was built and is never negative.");
        object below = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, -7, 0, 0.65, 0,
        })!;
        if ((int)below.GetType().GetProperty("GroundAsked")!.GetValue(below)! != -1)
            throw new InvalidOperationException("Anything below -1 clamps to -1, the floor the contract allows.");
    }

    /// <summary>
    /// <c>MouldGeometry.Phases</c>: the four phases the spine spec bound from
    /// the seven-questions state machine, with the split Param chose (30, 30,
    /// 30, 10). Measured at every boundary because a discontinuity in sag or
    /// lift is a visible jump on the timeline slider.
    /// </summary>
    /// <summary>
    /// <c>MouldGeometry.PerimeterFromFaces</c>: the boundary from topology
    /// rather than from a guess.
    ///
    /// An FD Result carries no faces of its own, so Animate has no thrust mesh
    /// to read naked edges off and used to fall back to node degree: keep
    /// every node joined to fewer neighbours than the middle of the net. That
    /// is not a boundary and on a coarse quad net it is not even close. A 5x5
    /// net has four corners at degree 2, twelve edge nodes at degree 3 and
    /// nine interior at degree 4, so the median is 3 and the "perimeter" comes
    /// back as the four CORNERS, each isolated from the others.
    ///
    /// The face rule has no such failure: an edge used by exactly one face is
    /// on the boundary, an edge shared by two is not. The fixture is the
    /// smallest grid that has an interior vertex to get wrong, four quads on
    /// nine nodes, and the centre node is the assertion that matters.
    /// </summary>
    private static void ValidatePerimeterFromFaces(Assembly plugin)
    {
        Type mouldGeometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry",
            throwOnError: true)!;
        MethodInfo fromFaces = RequirePublicStatic(
            mouldGeometry, "PerimeterFromFaces");

        //   6 7 8
        //   3 4 5
        //   0 1 2
        var faces = new List<IReadOnlyList<int>>
        {
            new[] { 0, 1, 4, 3 },
            new[] { 1, 2, 5, 4 },
            new[] { 3, 4, 7, 6 },
            new[] { 4, 5, 8, 7 },
        };
        var rim = (int[])fromFaces.Invoke(null, new object?[] { faces, 9 })!;
        var expectedRim = new[] { 0, 1, 2, 3, 5, 6, 7, 8 };
        if (!rim.SequenceEqual(expectedRim))
        {
            throw new InvalidOperationException(
                "The rim of a 2x2 grid of quads is its eight outer nodes: "
                + $"expected [{string.Join(",", expectedRim)}] and got "
                + $"[{string.Join(",", rim)}]. Node 4 is the centre, shared by "
                + "all four faces, so every edge touching it is used twice and "
                + "it cannot be on the boundary.");
        }

        var none = (int[])fromFaces.Invoke(
            null, new object?[] { new List<IReadOnlyList<int>>(), 9 })!;
        if (none.Length != 0)
        {
            throw new InvalidOperationException(
                "With no faces there is no boundary to read, and the empty "
                + "array is what tells the caller to fall back to the degree "
                + $"estimate and say so; got {none.Length} node(s).");
        }
    }

    private static void ValidatePhases(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo phases = RequirePublicStatic(geometry, "Phases");

        (double Sag, double Lift, string Phase) At(double time, double pre)
        {
            object result = phases.Invoke(null, new object?[] { time, pre })!;
            Type type = result.GetType();
            return (
                (double)type.GetField("Item1")!.GetValue(result)!,
                (double)type.GetField("Item2")!.GetValue(result)!,
                (string)type.GetField("Item3")!.GetValue(result)!);
        }

        void Expect(double time, double pre, string phase, double sag, double lift)
        {
            (double s, double l, string p) = At(time, pre);
            if (p != phase)
                throw new InvalidOperationException($"Time {time} at Pre-Sag {pre} is '{phase}', got '{p}'.");
            if (Math.Abs(s - sag) > 1.0e-9 || Math.Abs(l - lift) > 1.0e-9)
                throw new InvalidOperationException($"Time {time} ({phase}) at Pre-Sag {pre} should give sag {sag}, lift {lift}; got sag {s:0.####}, lift {l:0.####}.");
        }

        // Every phase boundary at THREE pre-sags, the two ends included, with
        // the expected sag computed from the table rather than written out:
        // reel runs 0 to pre, raise holds pre, finish runs pre to 1. Checking
        // 0.4 alone left a Phases that ignored its second argument passing at
        // the boundaries, since 0.4 appears in the answer either way.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            Expect(0.0, pre, "reel", 0.0, 0.0);
            Expect(0.15, pre, "reel", pre * 0.5, 0.0);
            Expect(0.3, pre, "raise", pre, 0.0);
            Expect(0.45, pre, "raise", pre, 0.5);
            Expect(0.6, pre, "finish", pre, 1.0);
            Expect(0.75, pre, "finish", pre + ((1.0 - pre) * 0.5), 1.0);
            Expect(0.9, pre, "hold", 1.0, 1.0);
            Expect(1.0, pre, "hold", 1.0, 1.0);
        }

        // Continuity: just below each boundary matches the boundary, to 1e-9,
        // which is what the spec binds. The step back has to be SMALLER than
        // the tolerance divided by the slope, or the probe fails an exact
        // function: at 1e-9 the sag inside reel has already moved 1.33e-9, so
        // the old probe could only ever be asserted at 1e-6. At 1e-12 the gap
        // is 1.33e-12 and the spec's own tolerance holds.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            foreach (double boundary in new[] { 0.3, 0.6, 0.9 })
            {
                (double sBelow, double lBelow, _) = At(boundary - 1.0e-12, pre);
                (double sAt, double lAt, _) = At(boundary, pre);
                if (Math.Abs(sBelow - sAt) > 1.0e-9 || Math.Abs(lBelow - lAt) > 1.0e-9)
                    throw new InvalidOperationException($"Sag or lift jumps at time {boundary} with Pre-Sag {pre}: {sBelow:0.############}/{lBelow:0.############} below, {sAt:0.############}/{lAt:0.############} at.");
            }
        }

        // MONOTONE across the whole timeline. Continuity at three boundaries
        // says nothing about what happens between them, and a build that ran
        // backwards mid-phase would reel a cable out again: neither the sag
        // nor the lift may ever decrease as Time advances.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            double lastSag = -1.0;
            double lastLift = -1.0;
            for (int step = 0; step <= 100; step++)
            {
                double t = step / 100.0;
                (double s, double l, _) = At(t, pre);
                if (s < lastSag - 1.0e-12 || l < lastLift - 1.0e-12)
                {
                    throw new InvalidOperationException(
                        $"Sag and lift must never decrease: at Pre-Sag {pre}, time {t:0.##} gave sag {s:0.######} and lift {l:0.######} after {lastSag:0.######} and {lastLift:0.######}.");
                }
                lastSag = s;
                lastLift = l;
            }
        }
        // Out-of-range inputs clamp rather than throw.
        (double sOver, double lOver, string pOver) = At(1.5, 2.0);
        if (pOver != "hold" || Math.Abs(sOver - 1.0) > 1.0e-9 || Math.Abs(lOver - 1.0) > 1.0e-9)
            throw new InvalidOperationException("Time past 1 and Pre-Sag past 1 clamp to hold at full sag and lift.");
    }

    /// <summary>
    /// <c>MouldGeometry.LiveColumnNodes</c>: the rigid rotation. A tree's foot
    /// is where the block put it, its heads are on the live net by HeadNode,
    /// and its fork keeps the fraction it was built at along the live
    /// foot-to-main segment, so the trunk turns about its foot as one body.
    /// Two trees share one foot here, and one of them forks.
    ///
    /// The fixture is built so that each of the three rules FAILS SEPARATELY
    /// if it is ever reverted:
    ///
    ///   THE FRACTION is 0.4, not the 0.65 an earlier fixture used, so a
    ///   hard-coded constant cannot pass by matching the test's own number.
    ///
    ///   THE MAIN BRANCH is listed SECOND in Members, so <c>Above[fork]</c>
    ///   reads {B, M} and a MainBranch that took the first entry above the
    ///   fork would put the fork on the arm's segment instead of the trunk's.
    ///
    ///   THE HEADS are found by HeadNode, which is permuted to {2, 1, 0}, and
    ///   the net at time zero is DRAWN IN in plan the way a reeling net is. So
    ///   the main head's built plan position is nearest to a different live
    ///   vertex from the one HeadNode names, and a revert to plan matching
    ///   puts that head, and the fork under it, somewhere else.
    /// </summary>
    private static void ValidateLiveColumnNodes(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo liveNodes = RequirePublicStatic(geometry, "LiveColumnNodes");
        Type point3d = liveNodes.GetParameters()[1].ParameterType.GetElementType()!;
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");

        // Foot F at the origin; fork K at 0.4 of the way to main head M; a
        // branch head B off the fork; a second tree from the same foot to
        // head H. HeadNode is permuted: M stands on net vertex 2, B on 1,
        // H on 0.
        double[][] built =
        {
            new[] { 0.0, 0.0, 0.0 },        // 0 F
            new[] { 0.4, 0.0, 0.8 },        // 1 K, exactly 0.4 of F to M
            new[] { 1.0, 0.0, 2.0 },        // 2 M
            new[] { 2.0, 0.0, 1.5 },        // 3 B
            new[] { -1.0, 0.0, 2.0 },       // 4 H
        };
        Array nodes = Array.CreateInstance(point, built.Length);
        for (int i = 0; i < built.Length; i++)
            nodes.SetValue(Activator.CreateInstance(point, built[i][0], built[i][1], built[i][2]), i);
        Array members = Array.CreateInstance(edge, 4);
        members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
        // The ARM before the trunk's continuation on purpose, so Above[1]
        // reads {3, 2} and picking the first entry gives the wrong branch.
        members.SetValue(Activator.CreateInstance(edge, 1, 3), 1);
        members.SetValue(Activator.CreateInstance(edge, 1, 2), 2);
        members.SetValue(Activator.CreateInstance(edge, 0, 4), 3);
        object block = CreateInstance(columnsType);
        SetContractProperty(block, columnsType, "Nodes", nodes);
        SetContractProperty(block, columnsType, "Members", members);
        SetContractProperty(block, columnsType, "MemberForce", new[] { 3.0, 1.0, 1.0, 1.0 });
        SetContractProperty(block, columnsType, "Trees", new int[][] { new[] { 0, 1, 2, 3 } });
        SetContractProperty(block, columnsType, "Heads", new[] { 2, 3, 4 });
        SetContractProperty(block, columnsType, "Forks", new[] { 1 });
        SetContractProperty(block, columnsType, "Feet", new[] { 0 });
        SetContractProperty(block, columnsType, "HeadNode", new[] { 2, 1, 0 });

        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;
        object[] Run(params object[] live)
        {
            Array array = Array.CreateInstance(point3d, live.Length);
            for (int i = 0; i < live.Length; i++)
                array.SetValue(live[i], i);
            return ((Array)liveNodes.Invoke(null, new object?[] { block, array })!).Cast<object>().ToArray();
        }
        void Near(object got, double x, double y, double z, string what)
        {
            if (Math.Abs(X(got) - x) > 1.0e-9 || Math.Abs(Y(got) - y) > 1.0e-9 || Math.Abs(Z(got) - z) > 1.0e-9)
                throw new InvalidOperationException($"{what} should be ({x}, {y}, {z}); got ({X(got):0.####}, {Y(got):0.####}, {Z(got):0.####}).");
        }

        // The solved net: every node where it was built. Live vertex 2 is
        // under M, 1 under B, 0 under H, as HeadNode says.
        object[] final = Run(P(-1.0, 0.0, 2.0), P(2.0, 0.0, 1.5), P(1.0, 0.0, 2.0));
        if (final.Length != 5)
            throw new InvalidOperationException($"One position per block node; got {final.Length}.");
        for (int i = 0; i < built.Length; i++)
            Near(final[i], built[i][0], built[i][1], built[i][2], $"node {i} at the solved net");

        // Time zero: the net flat on the ground and DRAWN IN in plan, which is
        // where the plan as drawn differs from the solved plan and so the one
        // frame that can tell HeadNode from plan matching. Head M is named
        // vertex 2 at plan x 0.5, while the vertex nearest M's own built plan
        // position (x 1.0) is vertex 1: matching in plan would put M, and the
        // fork under it, half a metre out.
        object[] flat = Run(P(-0.5, 0.0, 0.0), P(1.0, 0.0, 0.0), P(0.5, 0.0, 0.0));
        Near(flat[0], 0.0, 0.0, 0.0, "the foot at time zero");
        Near(flat[2], 0.5, 0.0, 0.0, "the main head at time zero, on the vertex HeadNode names");
        Near(flat[3], 1.0, 0.0, 0.0, "the branch head at time zero");
        Near(flat[4], -0.5, 0.0, 0.0, "the second tree's head at time zero");
        Near(flat[1], 0.2, 0.0, 0.0, "the fork at time zero, on the rail at its built fraction");

        // Halfway: the fork keeps its fraction and stays on the line.
        object[] mid = Run(P(-0.75, 0.0, 1.0), P(1.5, 0.0, 0.75), P(0.75, 0.0, 1.0));
        Near(mid[1], 0.3, 0.0, 0.4, "the fork halfway up");
        double angle = AngleDeg(
            X(mid[1]) - X(mid[0]), Y(mid[1]) - Y(mid[0]), Z(mid[1]) - Z(mid[0]),
            X(mid[2]) - X(mid[1]), Y(mid[2]) - Y(mid[1]), Z(mid[2]) - Z(mid[1]));
        if (angle > 0.5)
            throw new InvalidOperationException($"Trunk, fork and main head must stay collinear; they kink by {angle:0.###} degrees halfway up.");
    }

    /// <summary>
    /// Deconstruct's column trees: one branch per tree in the block's own
    /// order, every member a line from lower end to upper end, heads and
    /// feet as points per tree, and an absent block giving empty trees
    /// rather than an error.
    /// </summary>
    private static void ValidateDeconstructColumnTrees(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo columnsBlock = RequirePublicStatic(geometry, "ColumnsBlock");
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo columnTrees = RequireStatic(deconstruct, "ColumnTrees");

        Type lineList = columnsBlock.GetParameters()[0].ParameterType;
        Type line = lineList.GetGenericArguments()[0];
        Type point3d = columnsBlock.GetParameters()[2].ParameterType.GetElementType()!;
        object Pt(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        Type concreteList = typeof(List<>).MakeGenericType(line);
        object members = Activator.CreateInstance(concreteList)!;
        MethodInfo add = concreteList.GetMethod("Add")!;
        // Given upper end FIRST on purpose: the block must still hand back
        // lower to upper.
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(0, 0, 0)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(1, 0, 8)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(-1, 0, 8)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(10, 0, 0), Pt(10, 0, 6)) });
        Array net = Array.CreateInstance(point3d, 3);
        net.SetValue(Pt(1, 0, 8), 0);
        net.SetValue(Pt(-1, 0, 8), 1);
        net.SetValue(Pt(10, 0, 6), 2);
        object block = columnsBlock.Invoke(null, new object?[]
        {
            members, new[] { 300.0, 100.0, 100.0, 200.0 }, net, 1.0e-6, 2, 0, 0, 0.65, 0,
        })!;

        object trees = columnTrees.Invoke(null, new[] { block })!;
        Type tuple = trees.GetType();
        var lines = ((IEnumerable)tuple.GetField("Item1")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();
        var heads = ((IEnumerable)tuple.GetField("Item2")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();
        var feet = ((IEnumerable)tuple.GetField("Item3")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();

        if (lines.Length != 2 || lines[0].Length != 3 || lines[1].Length != 1)
            throw new InvalidOperationException("Two trees of three and one members; got " + string.Join("/", lines.Select(b => b.Length)) + ".");
        foreach (object member in lines.SelectMany(b => b))
        {
            object from = line.GetProperty("From")!.GetValue(member)!;
            object to = line.GetProperty("To")!.GetValue(member)!;
            double fromZ = (double)point3d.GetProperty("Z")!.GetValue(from)!;
            double toZ = (double)point3d.GetProperty("Z")!.GetValue(to)!;
            if (fromZ > toZ)
                throw new InvalidOperationException("Every column line runs from its lower end to its upper end.");
        }
        if (heads[0].Length != 2 || feet[0].Length != 1 || heads[1].Length != 1 || feet[1].Length != 1)
            throw new InvalidOperationException("Tree 0 has two heads and one foot; tree 1 has one of each.");

        object empty = columnTrees.Invoke(null, new object?[] { null })!;
        if (((ICollection)empty.GetType().GetField("Item1")!.GetValue(empty)!).Count != 0)
            throw new InvalidOperationException("No block means empty trees, never an error.");
    }

    /// <summary>
    /// <c>ParameterIdentity.ArchivedNames</c> against a REAL Grasshopper
    /// file, read headless.
    ///
    /// The whole load-time warning, the count comparison included, is gated
    /// on getting names out of the archive: <c>Read</c> calls this first and
    /// says nothing at all when it comes back nulls. A wrong chunk or item
    /// name would therefore not fail anywhere. It would return
    /// <c>(null, null)</c>, every component would fall silent, and Monitor's
    /// same-count reshuffle, the case this branch exists for, would reopen
    /// unwarned with a green harness behind it. Nothing about the shape can
    /// be asserted from a hand-built archive either, because a hand-built
    /// archive is written by the same guesses it would be checked against.
    ///
    /// So this drives a definition that is in the repository, written by
    /// Grasshopper itself: <c>plugin/definitions/ananke_equilibrium_v01.gh</c>.
    /// <c>GH_Archive</c> is pure serialisation and reads it with no Rhino
    /// running. Its first object is the v0.1 script component "Network", and
    /// the seven names below were read out of the file's own XML dump before
    /// they were pinned here, not assumed:
    ///
    ///   Root > Definition > DefinitionObjects > Object[0] > Container
    ///     > ParameterData
    ///       items    InputCount 5, OutputCount 2, and the InputId/OutputId
    ///                guids
    ///       chunks   InputParam[0..4], OutputParam[0..1], each carrying a
    ///                Name item of type gh_string
    ///
    /// The Container chunk is exactly the reader a component's <c>Read</c>
    /// override is handed, so this walks to the same place Grasshopper does
    /// and asks the same question from it.
    /// </summary>
    private static void ValidateArchivedNamesFromDefinition(
        Assembly plugin,
        string pluginPath)
    {
        Type identity = RequireComponentType(plugin, "ParameterIdentity");
        MethodInfo archivedNames = RequireStatic(identity, "ArchivedNames");
        // GH_IO as the PLUGIN binds to it, so this cannot end up reading one
        // assembly's archive with another's reader.
        Type readerType = archivedNames.GetParameters()[0].ParameterType;
        Type archiveType = readerType.Assembly.GetType(
            "GH_IO.Serialization.GH_Archive", throwOnError: true)!;

        string definitionPath = FindRepositoryFile(
            pluginPath,
            new[]
            {
                Path.Combine(
                    "plugin", "definitions", "ananke_equilibrium_v01.gh"),
                Path.Combine("definitions", "ananke_equilibrium_v01.gh")
            },
            "plugin/definitions/ananke_equilibrium_v01.gh",
            "the archive shape is checked against a file Grasshopper wrote");

        object archive = Activator.CreateInstance(archiveType)
            ?? throw new InvalidOperationException(
                "GH_Archive could not be constructed.");
        MethodInfo readFromFile = archiveType.GetMethod(
            "ReadFromFile", new[] { typeof(string) })
            ?? throw new InvalidOperationException(
                "GH_Archive.ReadFromFile(string) was not found.");
        if (readFromFile.Invoke(archive, new object[] { definitionPath })
            is not true)
        {
            throw new InvalidOperationException(
                $"GH_Archive refused to read {definitionPath}.");
        }
        object root =
            archiveType.GetProperty("GetRootNode")?.GetValue(archive)
            ?? throw new InvalidOperationException(
                "GH_Archive.GetRootNode gave nothing to read.");

        object Chunk(object reader, string name)
        {
            MethodInfo find = reader.GetType().GetMethod(
                "FindChunk", new[] { typeof(string) })
                ?? throw new InvalidOperationException(
                    "FindChunk(string) was not found on the archive reader.");
            return find.Invoke(reader, new object[] { name })
                ?? throw new InvalidOperationException(
                    $"The definition carries no '{name}' chunk where one was "
                    + "expected.");
        }
        object IndexedChunk(object reader, string name, int index)
        {
            MethodInfo find = reader.GetType().GetMethod(
                "FindChunk", new[] { typeof(string), typeof(int) })
                ?? throw new InvalidOperationException(
                    "FindChunk(string, int) was not found on the archive "
                    + "reader.");
            return find.Invoke(reader, new object[] { name, index })
                ?? throw new InvalidOperationException(
                    $"The definition carries no '{name}' chunk at {index}.");
        }
        string Text(object reader, string item)
        {
            MethodInfo tryGet = reader.GetType().GetMethod(
                "TryGetString",
                new[] { typeof(string), typeof(string).MakeByRefType() })
                ?? throw new InvalidOperationException(
                    "TryGetString was not found on the archive reader.");
            object?[] arguments = { item, string.Empty };
            return tryGet.Invoke(reader, arguments) is true
                ? arguments[1] as string ?? string.Empty
                : string.Empty;
        }

        object first = IndexedChunk(
            Chunk(Chunk(root, "Definition"), "DefinitionObjects"),
            "Object",
            0);
        string component = Text(first, "Name");
        if (!string.Equals(component, "Network", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The first object of ananke_equilibrium_v01.gh is the "
                + "'Network' component, whose ports the names below are "
                + $"pinned from; the file now opens with '{component}', so "
                + "either the definition was re-saved or the walk to it is "
                + "wrong.");
        }
        object container = Chunk(first, "Container");

        object names = archivedNames.Invoke(null, new[] { container })
            ?? throw new InvalidOperationException(
                "ArchivedNames returned nothing.");
        Type pair = names.GetType();
        var inputs = pair.GetField("Item1")!.GetValue(names) as string?[];
        var outputs = pair.GetField("Item2")!.GetValue(names) as string?[];
        if (inputs is null || outputs is null)
        {
            throw new InvalidOperationException(
                "ArchivedNames read nothing out of a real Grasshopper file. "
                + "Nulls are how it says an archive cannot be spoken about, "
                + "and Read then says nothing at all, so a wrong chunk or "
                + "item name kills the whole load-time warning in silence: "
                + "no component would announce a moved port, and nothing "
                + "else would fail.");
        }

        string?[] expectedInputs =
        {
            "Geometry", "Kind", "AnalysisPlane", "Tolerance", "LengthUnit"
        };
        string?[] expectedOutputs = { "Topology", "Status" };
        void Same(string side, string?[] found, string?[] expected)
        {
            if (found.Length == expected.Length &&
                found.SequenceEqual(expected, StringComparer.Ordinal))
            {
                return;
            }
            throw new InvalidOperationException(
                $"The {side} names read out of the archive are not the ones "
                + "the file holds; expected ["
                + string.Join(", ", expected)
                + "] and got ["
                + string.Join(
                    ", ", found.Select(name => name ?? "<null>"))
                + "].");
        }
        Same("input", inputs, expectedInputs);
        Same("output", outputs, expectedOutputs);
    }

    /// <summary>
    /// Deconstruct's Force Lines: the reciprocal FORCE diagram, which had no
    /// port anywhere in the plugin between Display giving up its outputs and
    /// this one being appended.
    ///
    /// The rule is one line per MEMBER ROW, in row order, drawn between the
    /// force-graph vertices of the force edge that row's state NAMES. Naming
    /// is the whole of it, so the fixture makes every cheaper reading wrong:
    /// the edge states are listed out of Id order, no state's ForceEdgeId is
    /// its own Id, and no force edge's id is its own position in the list. A
    /// reader that took the force edge at the row's index, or at the state's
    /// place in the list, or that matched Id to Id, would get three different
    /// answers here and none of them this one.
    ///
    /// And nothing at all for FD, which carries no reciprocal diagram: the
    /// port is registered for both solvers, so it has to come back empty
    /// rather than reach for graphs an FD Result does not have.
    /// </summary>
    private static void ValidateDeconstructForceLines(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type graphVertexType = RequireContractType(plugin, "TnaGraphVertexDto");
        Type graphEdgeType = RequireContractType(plugin, "TnaGraphEdgeDto");
        Type edgeStateType = RequireContractType(plugin, "TnaEdgeStateDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type tables = RequireComponentType(plugin, "ResultTables");
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo members = RequirePublicStatic(tables, "Members");
        MethodInfo forceLines = RequireStatic(deconstruct, "ForceLines");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        object Vertex(int id, object at)
        {
            object vertex = CreateInstance(graphVertexType);
            SetContractProperty(vertex, graphVertexType, "Id", id);
            SetContractProperty(vertex, graphVertexType, "Point", at);
            return vertex;
        }
        object GraphEdge(int id, int u, int v)
        {
            object edge = CreateInstance(graphEdgeType);
            SetContractProperty(edge, graphEdgeType, "Id", id);
            SetContractProperty(edge, graphEdgeType, "U", u);
            SetContractProperty(edge, graphEdgeType, "V", v);
            return edge;
        }
        object State(int id, int equilibriumEdge, int forceEdge)
        {
            object state = CreateInstance(edgeStateType);
            SetContractProperty(state, edgeStateType, "Id", id);
            SetContractProperty(
                state, edgeStateType, "EquilibriumEdgeId", equilibriumEdge);
            SetContractProperty(state, edgeStateType, "ForceEdgeId", forceEdge);
            return state;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!,
                Activator.CreateInstance(edgeType, 2, 0)!));

        // The force polygon: three vertices at three separable heights, so a
        // line read off the wrong edge is read straight off its Z.
        object forceGraph = CreateInstance(graphType);
        SetContractProperty(forceGraph, graphType, "Vertices",
            Of(graphVertexType,
                Vertex(70, P(0, 0, 10)),
                Vertex(80, P(0, 0, 20)),
                Vertex(90, P(0, 0, 30))));
        SetContractProperty(forceGraph, graphType, "Edges",
            Of(graphEdgeType,
                GraphEdge(300, 70, 80),
                GraphEdge(301, 80, 90),
                GraphEdge(302, 90, 70)));

        object tna = CreateResultDto(
            resultType,
            "tna",
            equilibrium,
            CreateInstance(graphType),
            forceGraph);
        SetContractProperty(tna, resultType, "Mappings", CreateInstance(mappingsType));
        SetContractProperty(tna, resultType, "EdgeStates",
            Of(edgeStateType,
                State(2, 1, 300),
                State(0, 2, 301),
                State(1, 0, 302)));

        Array rows = (Array)members.Invoke(null, new[] { tna })!;
        Array lines = (Array)forceLines.Invoke(null, new[] { tna, rows })!;
        if (lines.Length != rows.Length || lines.Length != 3)
        {
            throw new InvalidOperationException(
                "One force line per member row and no more; got "
                + $"{lines.Length} against {rows.Length} rows.");
        }
        Type lineType = lines.GetType().GetElementType()!;
        Type point3d = lineType.GetProperty("From")!.PropertyType;
        double End(int at, string end)
        {
            object line = lines.GetValue(at)!;
            object corner = lineType.GetProperty(end)!.GetValue(line)!;
            return (double)point3d.GetProperty("Z")!.GetValue(corner)!;
        }
        // Row 0 is state 0, which names force edge 301: 20 to 30. Row 1 is
        // state 1, force edge 302: 30 to 10. Row 2 is state 2, force edge
        // 300: 10 to 20.
        (double From, double To)[] expected =
        {
            (20.0, 30.0), (30.0, 10.0), (10.0, 20.0)
        };
        for (int at = 0; at < expected.Length; at++)
        {
            if (Math.Abs(End(at, "From") - expected[at].From) > 1.0e-9 ||
                Math.Abs(End(at, "To") - expected[at].To) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Force line {at} runs between the force-graph vertices "
                    + "of the edge that row's state NAMES, not of the edge at "
                    + $"its own index; expected {expected[at].From} to "
                    + $"{expected[at].To}, got {End(at, "From")} to "
                    + $"{End(at, "To")}.");
            }
        }

        object fd = CreateResultDto(
            resultType, "fd", equilibrium, null, null);
        Array fdRows = (Array)members.Invoke(null, new[] { fd })!;
        Array fdLines = (Array)forceLines.Invoke(null, new[] { fd, fdRows })!;
        if (fdLines.Length != 0)
        {
            throw new InvalidOperationException(
                "An FD Result carries no reciprocal diagram, so Force Lines "
                + $"comes back empty rather than guessing; got {fdLines.Length} "
                + "lines.");
        }
    }

    /// <summary>
    /// Diagnose's cross-checks, the things no single component can see:
    /// Columns ran on a Result with no principal runs; Animate ran with no
    /// Columns upstream; every anchor is isolated; more than half the net
    /// wants pushing up. A clean Result raises nothing.
    /// </summary>
    private static void ValidateDiagnoseRules(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type diagnosticType = RequireContractType(plugin, "DiagnosticDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");
        Type diagnose = RequireComponentType(plugin, "DiagnoseComponent");
        MethodInfo crossChecks = RequireStatic(diagnose, "CrossChecks");
        MethodInfo render = RequireStatic(diagnose, "Render");
        MethodInfo collect = RequireStatic(diagnose, "Collect");

        object P(double x, double y, double z) => Activator.CreateInstance(point, x, y, z)!;
        Array Points(params object[] items)
        {
            Array array = Array.CreateInstance(point, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        object Equilibrium(int[] supports)
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices",
                Points(P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(3, 0, 0)));
            SetContractProperty(eq, equilibriumType, "ResolvedSupportNodeIds", supports);
            return eq;
        }
        object Result(int[] supports, object? mould)
        {
            object r = CreateResultDto(resultType, "fd", Equilibrium(supports), null, null);
            SetContractProperty(r, resultType, "Mould", mould);
            return r;
        }
        object Mould(object? columns, object? frame)
        {
            object m = CreateInstance(mouldType);
            SetContractProperty(m, mouldType, "Columns", columns);
            SetContractProperty(m, mouldType, "Frame", frame);
            return m;
        }
        object Frame(int vertexCount)
        {
            object f = CreateInstance(frameType);
            SetContractProperty(f, frameType, "Vertices",
                Points(Enumerable.Range(0, vertexCount).Select(i => P(i, 0, 1)).ToArray()));
            return f;
        }
        string[] Codes(object result) =>
            ((IEnumerable)crossChecks.Invoke(null, new[] { result })!)
                .Cast<object>()
                .Select(d => (string)diagnosticType.GetProperty("Code")!.GetValue(d)!)
                .ToArray();
        void Expect(object result, string code)
        {
            string[] codes = Codes(result);
            if (!codes.Contains(code))
                throw new InvalidOperationException($"Expected {code}; got [{string.Join(", ", codes)}].");
        }

        // Columns block on a Result with no principal runs.
        object noRuns = Result(Array.Empty<int>(), Mould(ColumnsBlockForRules(plugin), null));
        Expect(noRuns, "diagnose.no_principal_runs");

        // A frame with no columns upstream.
        Expect(Result(Array.Empty<int>(), Mould(null, Frame(4))), "diagnose.frame_without_columns");

        // Two anchors and no edges at all: each is its own strip.
        Expect(Result(new[] { 0, 1 }, null), "diagnose.anchors_all_isolated");

        // 380 of 441 nodes want pushing up, said by Animate.
        object pushy = Result(Array.Empty<int>(), null);
        object push = CreateInstance(diagnosticType);
        SetContractProperty(push, diagnosticType, "Code", "animate.nodes_want_push");
        SetContractProperty(push, diagnosticType, "Severity", "warning");
        SetContractProperty(push, diagnosticType, "Message", "380 nodes sit above the bare surface");
        SetContractProperty(push, diagnosticType, "Value", 380.0);
        SetContractProperty(push, diagnosticType, "Context", new Dictionary<string, string> { ["total"] = "441" });
        SetContractProperty(push, diagnosticType, "Provenance", new Dictionary<string, string> { ["source"] = "Animate" });
        Array one = Array.CreateInstance(diagnosticType, 1);
        one.SetValue(push, 0);
        SetContractProperty(pushy, resultType, "Diagnostics", one);
        Expect(pushy, "diagnose.push_needed");

        // Clean: nothing to say.
        string[] clean = Codes(Result(Array.Empty<int>(), null));
        if (clean.Length != 0)
            throw new InvalidOperationException($"A clean Result raises nothing; got [{string.Join(", ", clean)}].");

        // An invalid Result: a frame of three vertices on a net of four, and
        // no columns, which would ALSO trip frame_without_columns if the
        // cross-checks ran. They must not: one error entry per validation
        // failure, and nothing else from Diagnose.
        object broken = Result(Array.Empty<int>(), Mould(null, Frame(3)));
        string[] collected = ((IEnumerable)collect.Invoke(null, new[] { broken })!)
            .Cast<object>()
            .Select(d => (string)diagnosticType.GetProperty("Code")!.GetValue(d)!)
            .ToArray();
        if (!collected.Contains("diagnose.invalid_result"))
            throw new InvalidOperationException($"An invalid Result must yield diagnose.invalid_result; got [{string.Join(", ", collected)}].");
        if (collected.Any(c => c.StartsWith("diagnose.", StringComparison.Ordinal) && c != "diagnose.invalid_result"))
            throw new InvalidOperationException($"Cross-checks must be skipped on an invalid Result; got [{string.Join(", ", collected)}].");

        // Render says the words and prints the worker report last.
        object rendered = Result(Array.Empty<int>(), null);
        SetContractProperty(rendered, resultType, "Report", "solver said so");
        Array none = Array.CreateInstance(diagnosticType, 0);
        string text = (string)render.Invoke(null, new object[] { rendered, none })!;
        if (!text.Contains("solver said so", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must print the worker's Report.");
        if (!text.Contains("Columns", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must say which mould components have not run.");
        if (!text.Contains(
                "not yet run on this Result: Columns, Animate, Forces, Fit, Supports",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Render's not-run line names each reader separately on a "
                + "Result none of them has annotated.");
        }

        // An FD Result with no report prints the standing FD line.
        string fdText = (string)render.Invoke(null, new object[] { Result(Array.Empty<int>(), null), none })!;
        if (!fdText.Contains("FD result: no reciprocal diagram.", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must print the FD line when an FD Result carries no report.");
    }

    private static object ColumnsBlockForRules(Assembly plugin)
    {
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");
        object c = CreateInstance(columnsType);
        Array nodes = Array.CreateInstance(point, 2);
        nodes.SetValue(Activator.CreateInstance(point, 0.0, 0.0, 0.0), 0);
        nodes.SetValue(Activator.CreateInstance(point, 0.0, 0.0, 5.0), 1);
        Array members = Array.CreateInstance(edge, 1);
        members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
        SetContractProperty(c, columnsType, "Nodes", nodes);
        SetContractProperty(c, columnsType, "Members", members);
        SetContractProperty(c, columnsType, "MemberForce", new[] { 100.0 });
        SetContractProperty(c, columnsType, "Trees", new int[][] { new[] { 0 } });
        SetContractProperty(c, columnsType, "Heads", new[] { 1 });
        SetContractProperty(c, columnsType, "Feet", new[] { 0 });
        SetContractProperty(c, columnsType, "HeadNode", new[] { 0 });
        return c;
    }

    private static Type RequireContractType(Assembly plugin, string typeName)
    {
        const string ContractsNamespace = "Ananke.COMPAS.Native.Contracts";
        return plugin.GetType($"{ContractsNamespace}.{typeName}", throwOnError: true)
            ?? throw new InvalidOperationException(
                $"Type '{ContractsNamespace}.{typeName}' was not found.");
    }

    /// <summary>
    /// <c>MouldGeometry.SnapCurveToNodes</c>: a drawn principal line must
    /// match a CONNECTED run of net nodes, not merely the set of nodes near
    /// it.
    ///
    /// The regression this pins, found in the viewport 2026-08-26: the obvious
    /// implementation collects every node inside a catch radius of the curve
    /// and sorts them by how far along the curve they lie. A line drawn down
    /// the middle of a bay catches the column of nodes EITHER SIDE of it, and
    /// the two columns' positions along the curve interleave, so the sorted
    /// run crosses the bay on every step. It draws as a zigzag, and it is
    /// worse than a drawing fault: Animate pins that run and Column Finder
    /// solves it as a beam, so the bar has notches on both sides of a bay and
    /// is reported at roughly twice its true length.
    ///
    /// The fixture is that exact case. A five-by-nine unit grid; the line
    /// drawn at x = 1.5, halfway between the columns at x = 1 and x = 2, so
    /// both sit 0.5 from it and the catch radius (0.6 of the unit median edge)
    /// takes in both. A correct match picks ONE column and walks it end to
    /// end. The sorted implementation returns 18 nodes alternating between
    /// the two columns; the walk returns 9 on one.
    ///
    /// A second case draws the line ON the column at x = 2, where only that
    /// column is inside the radius, and asserts the offset comes back at zero
    /// so the reported offset is not merely always the same number.
    ///
    /// Reflection-only, in this harness's usual manner: no Rhino document and
    /// no SolveInstance, only the static geometry method and the RhinoCommon
    /// types it already has loaded.
    /// </summary>
    private static void ValidatePrincipalLineSnapping(Assembly plugin)
    {
        Type mouldGeometry = RequireComponentType(plugin, "MouldGeometry");
        MethodInfo snap = mouldGeometry.GetMethod(
            "SnapSampledLineToNodes",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "MouldGeometry.SnapSampledLineToNodes was not found.");

        // Take the Rhino types off the method's own signature rather than
        // naming an assembly: whatever RhinoCommon the plugin was loaded
        // against is by definition the one these arguments must satisfy.
        // Point3d is a plain struct and needs no native core; a Curve would,
        // which is exactly why the walk takes sampled points instead.
        ParameterInfo[] parameters = snap.GetParameters();
        Type point3d = parameters[0].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "SnapSampledLineToNodes' first parameter is not an array.");

        const int columns = 5;
        const int rows = 9;
        Array nodes = Array.CreateInstance(point3d, columns * rows);
        for (int row = 0; row < rows; row++)
        for (int column = 0; column < columns; column++)
        {
            nodes.SetValue(
                Activator.CreateInstance(
                    point3d, (double)column, (double)row, 0.0),
                (row * columns) + column);
        }

        var edges = new List<(int, int)>();
        for (int row = 0; row < rows; row++)
        for (int column = 0; column < columns; column++)
        {
            int id = (row * columns) + column;
            if (column + 1 < columns)
                edges.Add((id, id + 1));
            if (row + 1 < rows)
                edges.Add((id, id + columns));
        }
        var adjacency = new HashSet<(int, int)>();
        foreach ((int u, int v) in edges)
        {
            adjacency.Add((u, v));
            adjacency.Add((v, u));
        }
        (int, int)[] edgeArray = edges.ToArray();

        CheckOneSnap(
            snap, point3d, nodes, edgeArray, adjacency,
            drawnAt: 1.5, expectedOffset: 0.5, label: "drawn down a bay");
        CheckOneSnap(
            snap, point3d, nodes, edgeArray, adjacency,
            drawnAt: 2.0, expectedOffset: 0.0, label: "drawn on a column");
    }

    private static void CheckOneSnap(
        MethodInfo snap,
        Type point3d,
        Array nodes,
        (int, int)[] edges,
        HashSet<(int, int)> adjacency,
        double drawnAt,
        double expectedOffset,
        string label)
    {
        const int columns = 5;
        const int rows = 9;

        // The line the author drew, sampled the way the component samples it:
        // straight down the grid at x = drawnAt, running past both ends.
        const int samples = 512;
        Array sampled = Array.CreateInstance(point3d, samples + 1);
        for (int index = 0; index <= samples; index++)
        {
            double y = -1.0 + (10.0 * index / samples);
            sampled.SetValue(
                Activator.CreateInstance(point3d, drawnAt, y, 0.0),
                index);
        }

        object?[] arguments = { sampled, nodes, edges, 0.0 };
        object? returned = snap.Invoke(null, arguments);
        double offset = (double)arguments[3]!;
        List<int> run = (returned as IEnumerable
            ?? throw new InvalidOperationException(
                $"SnapCurveToNodes ({label}) returned no run."))
            .Cast<int>()
            .ToList();

        if (run.Count != rows)
        {
            throw new InvalidOperationException(
                $"A principal line {label} must match one node per row, "
                + $"{rows} in all; it matched {run.Count}. "
                + (run.Count > rows
                    ? "More than one per row is the zigzag: the run is "
                      + "crossing the bay instead of following it."
                    : "Fewer means the walk stopped short of the far side."));
        }

        int first = run[0];
        int firstColumn = first % columns;
        for (int step = 0; step < run.Count; step++)
        {
            int node = run[step];
            if (node % columns != firstColumn)
            {
                throw new InvalidOperationException(
                    $"A principal line {label} left its column at step "
                    + $"{step}: node {node} is in column {node % columns}, "
                    + $"the run started in column {firstColumn}. A bar "
                    + "cannot cross the bay it runs down.");
            }
            if (node / columns != step)
            {
                throw new InvalidOperationException(
                    $"A principal line {label} is out of order at step "
                    + $"{step}: node {node} is in row {node / columns}. The "
                    + "run must advance one row per step, end to end.");
            }
            if (step > 0 && !adjacency.Contains((run[step - 1], node)))
            {
                throw new InvalidOperationException(
                    $"A principal line {label} jumped at step {step}: nodes "
                    + $"{run[step - 1]} and {node} share no mesh edge. A bar "
                    + "is a connected chain of notches.");
            }
        }

        // The offset is measured to the nearest SAMPLE, not perpendicular to
        // the line, so half a sample spacing is the tightest it can honestly
        // be pinned. Derived from the sampling rather than hardcoded, because
        // a hardcoded number would quietly become wrong if the density
        // changed. It still separates the two cases by fifty to one, which is
        // the whole point: half a bay off reads as half a bay off.
        double tolerance = (0.5 * 10.0 / samples) + 1.0e-9;
        if (Math.Abs(offset - expectedOffset) > tolerance)
        {
            throw new InvalidOperationException(
                $"A principal line {label} must report an offset of "
                + $"{expectedOffset:G3} from the curve that asked for it; it "
                + $"reported {offset:G6}.");
        }
    }

    /// <summary>
    /// <c>FrameGeometry.Read</c>: the one reading of a Result that Animate's
    /// viewport and Frame's ports both come from.
    ///
    /// The rule measured here is spec section 3's: positions come from
    /// <c>Mould.Frame.Vertices</c> when the Result carries a frame and from
    /// the solved equilibrium when it does not, so Frame on a Solve or a
    /// Columns Result is the finished vault and Frame on an Animate Result
    /// is that frame. The columns follow the same rule one level down:
    /// <c>Frame.ColumnNodes</c> when the frame carries them, the block's own
    /// nodes otherwise.
    ///
    /// The fixture is a three-by-three unit grid, twelve edges, anchored at
    /// its four corners, with no faces anywhere: no thrust mesh (an FD
    /// Result carries none) and no pattern topology, which is exactly the
    /// case where the boundary can only be ESTIMATED from node degree. The
    /// corners are the only nodes below the median degree, so the estimate
    /// is the four corners, each its own group because no two corners are
    /// joined. The Result carries no principal runs either, so every cable
    /// lands in the infill branch, and Cables is one branch: the infill is
    /// LAST, and with no bars it is also first.
    ///
    /// <c>Read</c> is the half that can run here. <c>Build</c> adds the
    /// thrust mesh and the polyline curves, both of which P/Invoke
    /// rhcommon_c and neither of which this process has a Rhino for; both
    /// read <c>Net.Positions</c>, which is what this pins.
    ///
    /// Four further fixtures round out the corner cases the plain grid
    /// cannot reach on its own: a frame whose Vertices, or whose
    /// ColumnNodes, do not match the net falls back to the solved geometry,
    /// and Phase must fall back to <c>FinalPhase</c> on the SAME guard
    /// rather than still say the frame's own word over solved positions; a
    /// Result with ONE principal run measures Cables' branch structure
    /// (the bar's own members in branch 0, the infill LAST in branch 1),
    /// which the plain grid cannot, because with no bars at all first and
    /// last are the same branch; and a Result with pattern faces gives a
    /// REAL boundary loop, so <c>PerimeterCloses</c> is measured true for
    /// once rather than only ever in its all-false, estimated form.
    /// </summary>
    private static void ValidateFrameGeometry(Assembly plugin)
    {
        Type geometry = RequireComponentType(plugin, "FrameGeometry");
        MethodInfo read = RequirePublicStatic(geometry, "Read");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");
        Type equilibriumProblemType =
            RequireContractType(plugin, "EquilibriumProblemDto");
        Type topologyType = RequireContractType(plugin, "TopologyDto");
        Type problemType = RequireContractType(plugin, "ProblemDto");
        Type anchoredType = RequireContractType(plugin, "AnchoredPatternDto");
        Type tnaPatternType = RequireContractType(plugin, "TnaPatternDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Points(IEnumerable<object> items)
        {
            object[] all = items.ToArray();
            Array array = Array.CreateInstance(point, all.Length);
            for (int i = 0; i < all.Length; i++)
                array.SetValue(all[i], i);
            return array;
        }
        object[] Grid(double z) => Enumerable
            .Range(0, 9)
            .Select(i => P(i % 3, i / 3, z))
            .ToArray();

        var pairs = new List<(int U, int V)>();
        for (int row = 0; row < 3; row++)
        {
            for (int column = 0; column < 2; column++)
                pairs.Add(((row * 3) + column, (row * 3) + column + 1));
        }
        for (int column = 0; column < 3; column++)
        {
            for (int row = 0; row < 2; row++)
                pairs.Add(((row * 3) + column, ((row + 1) * 3) + column));
        }
        Array edges = Array.CreateInstance(edge, pairs.Count);
        for (int i = 0; i < pairs.Count; i++)
            edges.SetValue(Activator.CreateInstance(edge, pairs[i].U, pairs[i].V), i);

        object Equilibrium()
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices", Points(Grid(0.0)));
            SetContractProperty(eq, equilibriumType, "Edges", edges);
            SetContractProperty(
                eq, equilibriumType, "ResolvedSupportNodeIds", new[] { 0, 2, 6, 8 });
            return eq;
        }
        object Columns(Array nodes)
        {
            object block = CreateInstance(columnsType);
            SetContractProperty(block, columnsType, "Nodes", nodes);
            Array members = Array.CreateInstance(edge, 1);
            members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
            SetContractProperty(block, columnsType, "Members", members);
            SetContractProperty(block, columnsType, "MemberForce", new[] { 100.0 });
            SetContractProperty(
                block, columnsType, "Trees", new int[][] { new[] { 0 } });
            SetContractProperty(block, columnsType, "Heads", new[] { 1 });
            SetContractProperty(block, columnsType, "Feet", new[] { 0 });
            SetContractProperty(block, columnsType, "HeadNode", new[] { 4 });
            return block;
        }
        object Frame(Array? columnNodes)
        {
            object frame = CreateInstance(frameType);
            SetContractProperty(frame, frameType, "Time", 50.0);
            SetContractProperty(frame, frameType, "Phase", "raise");
            SetContractProperty(frame, frameType, "Lift", 0.5);
            SetContractProperty(frame, frameType, "Sag", 0.5);
            SetContractProperty(frame, frameType, "Vertices", Points(Grid(1.0)));
            SetContractProperty(frame, frameType, "ColumnNodes", columnNodes);
            return frame;
        }
        object Result(object? columns, object? frame)
        {
            object result =
                CreateResultDto(resultType, "fd", Equilibrium(), null, null);
            if (columns is null && frame is null)
                return result;
            object mould = CreateInstance(mouldType);
            SetContractProperty(mould, mouldType, "Ground", 0.0);
            SetContractProperty(mould, mouldType, "Columns", columns);
            SetContractProperty(mould, mouldType, "Frame", frame);
            SetContractProperty(result, resultType, "Mould", mould);
            return result;
        }
        object Read(object result) =>
            read.Invoke(null, new object?[] { result, null, Array.Empty<int>() })
            ?? throw new InvalidOperationException("FrameGeometry.Read returned null.");
        T Field<T>(object owner, string name) =>
            (T)(owner.GetType().GetProperty(name)
                ?? throw new InvalidOperationException(
                    $"FrameGeometry.Net has no {name}."))
                .GetValue(owner)!;

        // ---- The frame the Result carries wins.
        object framed = Read(Result(null, Frame(null)));
        Array positions = Field<Array>(framed, "Positions");
        Type point3d = positions.GetType().GetElementType()!;
        double Axis(object value, string axis) =>
            (double)point3d.GetProperty(axis)!.GetValue(value)!;
        if (positions.Length != 9)
        {
            throw new InvalidOperationException(
                "One position per net node; nine went in and "
                + $"{positions.Length} came back.");
        }
        for (int i = 0; i < 9; i++)
        {
            object at = positions.GetValue(i)!;
            if (Math.Abs(Axis(at, "Z") - 1.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "Positions come from Mould.Frame.Vertices when the Result "
                    + $"carries a frame; node {i} came back at z "
                    + $"{Axis(at, "Z"):0.####}, not the frame's 1.");
            }
        }
        string phase = Field<string>(framed, "Phase");
        if (!string.Equals(phase, "raise", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"Phase is the frame's own word; got '{phase}'.");
        }

        // ---- Cables: one branch, because there are no principal runs, and
        // every end on the frame's own positions.
        IList cables = Field<IList>(framed, "Cables");
        if (cables.Count != 1)
        {
            throw new InvalidOperationException(
                "With no principal runs every member is infill, and the infill "
                + $"is one branch; got {cables.Count} branches.");
        }
        IList infill = (IList)cables[0]!;
        if (infill.Count != 12)
        {
            throw new InvalidOperationException(
                $"Twelve edges went in and {infill.Count} cables came back.");
        }
        foreach (object? item in infill)
        {
            object line = item!;
            object from = line.GetType().GetProperty("From")!.GetValue(line)!;
            object to = line.GetType().GetProperty("To")!.GetValue(line)!;
            if (Math.Abs(Axis(from, "Z") - 1.0) > 1.0e-9 ||
                Math.Abs(Axis(to, "Z") - 1.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "Every cable end stands at the frame's positions, so both "
                    + "ends are at z 1; one came back at "
                    + $"{Axis(from, "Z"):0.####} to {Axis(to, "Z"):0.####}.");
            }
        }

        // ---- The anchors and the estimated boundary.
        IList anchors = Field<IList>(framed, "AnchorGroups");
        if (anchors.Count != 4 || ((IList)anchors[0]!).Count != 1)
        {
            throw new InvalidOperationException(
                "The four corners are anchored and no two of them are joined, "
                + $"so each is a strip of its own; got {anchors.Count} strips.");
        }
        if (!Field<bool>(framed, "PerimeterEstimated"))
        {
            throw new InvalidOperationException(
                "This Result carries no faces of its own and no pattern "
                + "topology, so the boundary is a degree ESTIMATE and has to "
                + "say so; Perimeter Lines draws nothing from an estimate.");
        }
        int perimeterCount = Field<int>(framed, "PerimeterCount");
        if (perimeterCount != 4)
        {
            throw new InvalidOperationException(
                "The estimate is the nodes below the median degree, which on a "
                + $"three-by-three grid is the four corners; got {perimeterCount}.");
        }
        bool[] closes = Field<bool[]>(framed, "PerimeterCloses");
        if (closes.Length != Field<IList>(framed, "PerimeterLoops").Count ||
            closes.Any(one => one))
        {
            throw new InvalidOperationException(
                "One closing verdict per loop, and an estimated boundary never "
                + "closes: a single node is not a loop.");
        }

        // ---- No columns block: an empty tree, not an error.
        if (Field<IList>(framed, "ColumnBranches").Count != 0)
        {
            throw new InvalidOperationException(
                "A Result with a frame and no columns block gives an EMPTY "
                + "Columns tree; Diagnose's frame_without_columns is what says "
                + "so in words.");
        }

        // ---- No frame at all: the solved state, phase final.
        object solved = Read(Result(null, null));
        Array solvedPositions = Field<Array>(solved, "Positions");
        for (int i = 0; i < 9; i++)
        {
            object at = solvedPositions.GetValue(i)!;
            if (Math.Abs(Axis(at, "Z")) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "With no frame the positions are the SOLVED vertices, so "
                    + $"node {i} stands at z 0; got {Axis(at, "Z"):0.####}.");
            }
        }
        string solvedPhase = Field<string>(solved, "Phase");
        if (!string.Equals(solvedPhase, "final", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A Result with no frame stands at its finished shape, and the "
                + $"word for that is 'final'; got '{solvedPhase}'.");
        }

        // ---- The frame's column nodes win over the block's own. The block
        // is built two metres tall and the frame stands it at three, so a
        // reading that took the block's nodes measures 2 and this measures 3.
        object standing = Read(Result(
            Columns(Points(new[] { P(0.0, 0.0, 0.0), P(0.0, 0.0, 2.0) })),
            Frame(Points(new[] { P(0.0, 0.0, 0.0), P(0.0, 0.0, 3.0) }))));
        IList branches = Field<IList>(standing, "ColumnBranches");
        if (branches.Count != 1 || ((IList)branches[0]!).Count != 1)
        {
            throw new InvalidOperationException(
                "One tree of one member gives one branch holding one line; got "
                + $"{branches.Count} branches.");
        }
        object member = ((IList)branches[0]!)[0]!;
        object lower = member.GetType().GetProperty("From")!.GetValue(member)!;
        object upper = member.GetType().GetProperty("To")!.GetValue(member)!;
        double height = Axis(upper, "Z") - Axis(lower, "Z");
        if (Math.Abs(height - 3.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The column stands where the FRAME puts it, not where it was "
                + $"built: the frame says 3 and the block says 2, and {height:0.####} "
                + "came back.");
        }

        // ---- A frame whose Vertices count does not match the net falls
        // back to the solved positions; Phase must fall back to FinalPhase
        // on the SAME guard, not report the frame's own word over geometry
        // that is really the solved shape. The same is true when the frame's
        // ColumnNodes count does not match the block. Both are otherwise
        // unreachable from Animate, which only ever writes a frame whose
        // counts hold, but Frame can be handed any Result.
        object shortFrame = CreateInstance(frameType);
        SetContractProperty(shortFrame, frameType, "Time", 50.0);
        SetContractProperty(shortFrame, frameType, "Phase", "raise");
        SetContractProperty(shortFrame, frameType, "Lift", 0.5);
        SetContractProperty(shortFrame, frameType, "Sag", 0.5);
        SetContractProperty(
            shortFrame,
            frameType,
            "Vertices",
            Points(new[] { P(0.0, 0.0, 1.0), P(1.0, 0.0, 1.0), P(0.0, 1.0, 1.0) }));
        object mismatched = Read(Result(null, shortFrame));
        string mismatchedPhase = Field<string>(mismatched, "Phase");
        if (!string.Equals(mismatchedPhase, "final", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A frame whose Vertices count does not match the net falls "
                + "back to the SOLVED positions, and Phase must fall back "
                + $"with it rather than still say 'raise'; got "
                + $"'{mismatchedPhase}'.");
        }

        object shortColumnsFrame = Frame(Points(new[] { P(0.0, 0.0, 0.0) }));
        object mismatchedColumns = Read(Result(
            Columns(Points(new[] { P(0.0, 0.0, 0.0), P(0.0, 0.0, 2.0) })),
            shortColumnsFrame));
        string mismatchedColumnsPhase = Field<string>(mismatchedColumns, "Phase");
        if (!string.Equals(mismatchedColumnsPhase, "final", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A frame whose ColumnNodes count does not match the block "
                + "falls back to the block's own nodes, and Phase must fall "
                + "back with it; got '" + mismatchedColumnsPhase + "'.");
        }

        // ---- Cables' branch structure with ONE principal run: the bar's
        // own members land in branch 0, and everything else, the infill,
        // lands in a LAST branch. Every earlier fixture above has no
        // principal runs at all, so with no bars first and last are the
        // SAME branch and an infill-first Read would still pass; this is
        // the one that would fail it.
        object runTopology = CreateInstance(topologyType);
        SetContractProperty(
            runTopology,
            topologyType,
            "PrincipalRuns",
            new int[][] { new[] { 0, 1, 2 } });
        object equilibriumProblem = CreateInstance(equilibriumProblemType);
        SetContractProperty(
            equilibriumProblem, equilibriumProblemType, "Topology", runTopology);
        object equilibriumWithRun = Equilibrium();
        SetContractProperty(
            equilibriumWithRun, equilibriumType, "Problem", equilibriumProblem);
        object resultWithRun =
            CreateResultDto(resultType, "fd", equilibriumWithRun, null, null);
        object withRun = Read(resultWithRun);
        IList runCables = Field<IList>(withRun, "Cables");
        if (runCables.Count != 2)
        {
            throw new InvalidOperationException(
                "One principal run gives two branches, the bar and the "
                + $"infill LAST; got {runCables.Count}.");
        }
        IList barBranch = (IList)runCables[0]!;
        IList infillBranch = (IList)runCables[1]!;
        if (barBranch.Count != 2)
        {
            throw new InvalidOperationException(
                "The run 0,1,2 covers two consecutive members, (0,1) and "
                + $"(1,2); branch 0 came back with {barBranch.Count}.");
        }
        if (infillBranch.Count != 10)
        {
            throw new InvalidOperationException(
                "Twelve edges minus the bar's own two leaves ten in the "
                + $"infill LAST branch; got {infillBranch.Count}.");
        }

        // ---- A real boundary, from pattern faces: PerimeterCloses reads
        // true for that loop. Every fixture above carries no faces, so
        // PerimeterCloses is only ever measured in its all-false, estimated
        // form; this is the one that exercises the grouping[last].Contains
        // (first) rule that keeps Perimeter Lines from drawing a chord and
        // calling it the boundary.
        object faceTopology = CreateInstance(topologyType);
        SetContractProperty(faceTopology, topologyType, "Vertices", Points(Grid(0.0)));
        SetContractProperty(
            faceTopology,
            topologyType,
            "Faces",
            new int[][]
            {
                new[] { 0, 1, 4, 3 },
                new[] { 1, 2, 5, 4 },
                new[] { 3, 4, 7, 6 },
                new[] { 4, 5, 8, 7 }
            });
        object tnaPattern = CreateInstance(tnaPatternType);
        SetContractProperty(tnaPattern, tnaPatternType, "Topology", faceTopology);
        object anchoredPattern = CreateInstance(anchoredType);
        SetContractProperty(anchoredPattern, anchoredType, "Pattern", tnaPattern);
        object problemWithFaces = CreateInstance(problemType);
        SetContractProperty(problemWithFaces, problemType, "Anchored", anchoredPattern);
        object resultWithFaces =
            CreateResultDto(resultType, "fd", Equilibrium(), null, null);
        SetContractProperty(resultWithFaces, resultType, "Problem", problemWithFaces);
        object withFaces = Read(resultWithFaces);
        if (Field<bool>(withFaces, "PerimeterEstimated"))
        {
            throw new InvalidOperationException(
                "Pattern faces give a REAL boundary, not an estimate; "
                + "PerimeterEstimated came back true.");
        }
        int facePerimeterCount = Field<int>(withFaces, "PerimeterCount");
        if (facePerimeterCount != 8)
        {
            throw new InvalidOperationException(
                "Four quad faces over the three-by-three grid leave the "
                + "eight outer nodes on the boundary and the centre off it; "
                + $"got {facePerimeterCount}.");
        }
        bool[] faceCloses = Field<bool[]>(withFaces, "PerimeterCloses");
        if (faceCloses.Length != 1 || !faceCloses[0])
        {
            throw new InvalidOperationException(
                "The eight boundary nodes form one closed loop around the "
                + "centre; PerimeterCloses must read true for it, not "
                + $"[{string.Join(", ", faceCloses)}].");
        }
    }

    /// <summary>
    /// <c>MonitorMath</c>: the four pure rules the readers' outputs rest on,
    /// measured on hand-built inputs so a wrong sign or a wrong percentile
    /// rank cannot pass.
    /// </summary>
    private static void ValidateMonitorMath(Assembly plugin)
    {
        Type math = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MonitorMath", throwOnError: true)!;
        MethodInfo split = RequirePublicStatic(math, "AnchorSplit");
        MethodInfo axis = RequirePublicStatic(math, "TensionerAxis");
        MethodInfo stats = RequirePublicStatic(math, "DeviationStats");
        MethodInfo unstrained = RequirePublicStatic(math, "UnstrainedLength");
        MethodInfo toNewtons = RequirePublicStatic(math, "ToNewtons");
        Type vector3d = split.GetParameters()[0].ParameterType;
        Type point3d = axis.GetParameters()[1].ParameterType.GetElementType()!;

        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double Get(object o, string name) => (double)o.GetType().GetProperty(name)!.GetValue(o)!;

        object parts = split.Invoke(null, new[] { V(3.0, 4.0, 0.0), V(1.0, 0.0, 0.0) })!;
        double along = (double)parts.GetType().GetField("Item1")!.GetValue(parts)!;
        double across = (double)parts.GetType().GetField("Item2")!.GetValue(parts)!;
        if (Math.Abs(along - 3.0) > 1.0e-9 || Math.Abs(across - 4.0) > 1.0e-9)
            throw new InvalidOperationException($"Reaction (3,4,0) on axis x splits into along 3, across 4; got {along}, {across}.");
        // The axis does NOT arrive unit. (2,0,0) is the same direction as
        // (1,0,0) and must give the same split; an implementation that
        // dropped the normalisation would double the along part here and
        // pass every other case in this check.
        object longAxis = split.Invoke(null, new[] { V(3.0, 4.0, 0.0), V(2.0, 0.0, 0.0) })!;
        double alongLong = (double)longAxis.GetType().GetField("Item1")!.GetValue(longAxis)!;
        double acrossLong = (double)longAxis.GetType().GetField("Item2")!.GetValue(longAxis)!;
        if (Math.Abs(alongLong - 3.0) > 1.0e-9 || Math.Abs(acrossLong - 4.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The axis is a DIRECTION, so (2,0,0) splits (3,4,0) exactly as "
                + $"(1,0,0) does, into 3 and 4; got {alongLong}, {acrossLong}. A "
                + "different answer means the axis was used unnormalised.");
        }
        // The SIGN of the along part is the port's whole content: a tensioner
        // pulling and a tensioner being pushed are the two cases, and a
        // magnitude cannot tell them apart.
        object pushed = split.Invoke(null, new[] { V(-3.0, 4.0, 0.0), V(1.0, 0.0, 0.0) })!;
        double alongPushed = (double)pushed.GetType().GetField("Item1")!.GetValue(pushed)!;
        double acrossPushed = (double)pushed.GetType().GetField("Item2")!.GetValue(pushed)!;
        if (Math.Abs(alongPushed + 3.0) > 1.0e-9 || Math.Abs(acrossPushed - 4.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Reaction (-3,4,0) on axis x pulls the OTHER way along it, so "
                + $"along is -3 and across is 4; got {alongPushed}, {acrossPushed}. "
                + "A positive along means the magnitude was taken and the sign lost.");
        }

        // Anchor 0 at the origin with cables to (1,0,0) and (0,1,0).
        Array nodes = Array.CreateInstance(point3d, 3);
        nodes.SetValue(P(0.0, 0.0, 0.0), 0);
        nodes.SetValue(P(1.0, 0.0, 0.0), 1);
        nodes.SetValue(P(0.0, 1.0, 0.0), 2);
        var neighbours = new List<int>[] { new() { 1, 2 }, new() { 0 }, new() { 0 } };
        object a = axis.Invoke(null, new object?[] { 0, nodes, neighbours })!;
        double r = 1.0 / Math.Sqrt(2.0);
        if (Math.Abs(Get(a, "X") - r) > 1.0e-9 || Math.Abs(Get(a, "Y") - r) > 1.0e-9 || Math.Abs(Get(a, "Z")) > 1.0e-9)
            throw new InvalidOperationException($"The tensioner axis is the unit mean of the cables leaving the anchor; got ({Get(a, "X"):0.###}, {Get(a, "Y"):0.###}, {Get(a, "Z"):0.###}).");
        object none = axis.Invoke(null, new object?[] { 1, nodes, new List<int>[] { new(), new(), new() } })!;
        if (Math.Abs(Get(none, "Z") - 1.0) > 1.0e-9)
            throw new InvalidOperationException("An anchor with no cable has a vertical axis.");

        object s = stats.Invoke(null, new object?[] { new List<double> { 1.0, -2.0, 3.0, -4.0, 5.0 } })!;
        double rms = (double)s.GetType().GetField("Item1")!.GetValue(s)!;
        double max = (double)s.GetType().GetField("Item2")!.GetValue(s)!;
        double p95 = (double)s.GetType().GetField("Item3")!.GetValue(s)!;
        if (Math.Abs(rms - Math.Sqrt(11.0)) > 1.0e-9 || Math.Abs(max - 5.0) > 1.0e-9 || Math.Abs(p95 - 5.0) > 1.0e-9)
            throw new InvalidOperationException($"Stats of (1,-2,3,-4,5) are RMS sqrt(11), max 5, p95 5; got {rms:0.####}, {max}, {p95}.");
        // A field whose worst reading is NEGATIVE. The frame sitting below
        // the state it is heading for is exactly that field, and an
        // implementation taking values.Max() returns 2 here.
        object below = stats.Invoke(null, new object?[] { new List<double> { -9.0, 1.0, 2.0 } })!;
        double belowMax = (double)below.GetType().GetField("Item2")!.GetValue(below)!;
        double belowP95 = (double)below.GetType().GetField("Item3")!.GetValue(below)!;
        if (Math.Abs(belowMax - 9.0) > 1.0e-9 || Math.Abs(belowP95 - 9.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The worst and the 95th percentile of (-9,1,2) are both 9, the "
                + $"worst ABSOLUTE deviation; got {belowMax} and {belowP95}. A 2 "
                + "means the signed maximum was taken, which reads a frame sagging "
                + "9 mm low as the flattest thing on the model.");
        }
        object empty = stats.Invoke(null, new object?[] { new List<double>() })!;
        double emptyRms = (double)empty.GetType().GetField("Item1")!.GetValue(empty)!;
        double emptyMax = (double)empty.GetType().GetField("Item2")!.GetValue(empty)!;
        double emptyP95 = (double)empty.GetType().GetField("Item3")!.GetValue(empty)!;
        if (emptyRms != 0.0 || emptyMax != 0.0 || emptyP95 != 0.0)
        {
            throw new InvalidOperationException(
                "Stats of nothing are zero in ALL THREE places; got "
                + $"{emptyRms}, {emptyMax}, {emptyP95}.");
        }
        // Twenty values 1..20: the nearest-rank 95th percentile is the 19th, 19.
        object twenty = stats.Invoke(null, new object?[] { Enumerable.Range(1, 20).Select(i => (double)i).ToList() })!;
        double p95twenty = (double)twenty.GetType().GetField("Item3")!.GetValue(twenty)!;
        if (Math.Abs(p95twenty - 19.0) > 1.0e-9)
            throw new InvalidOperationException($"The nearest-rank 95th percentile of 1..20 is 19; got {p95twenty}.");

        double u = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 1000.0 })!;
        if (Math.Abs(u - (2.0 / 1.1)) > 1.0e-9)
            throw new InvalidOperationException($"Unstrained length of 2 under 100 N with EA 1000 is 2/1.1; got {u:0.######}.");
        double raw = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 0.0 })!;
        if (Math.Abs(raw - 2.0) > 1.0e-9)
            throw new InvalidOperationException("Without EA the strained length is returned.");
        // One plus force over EA goes NEGATIVE here, and dividing by it would
        // hand back a length of -2: a bar to cut to a negative number.
        double collapsed = (double)unstrained.Invoke(
            null, new object?[] { 2.0, -2000.0, 1000.0 })!;
        if (Math.Abs(collapsed - 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A member whose EA cannot carry its own compression has no "
                + "unstrained length worth reporting, so the STRAINED 2 comes "
                + $"back; got {collapsed:0.######}.");
        }
        // A negative EA is not a stiffness at all, and 1 + 100/-5 = -19 would
        // otherwise divide 2 into a small negative length.
        double negativeEA = (double)unstrained.Invoke(
            null, new object?[] { 2.0, 100.0, -5.0 })!;
        if (Math.Abs(negativeEA - 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A negative EA is no stiffness, so the strained 2 comes back; "
                + $"got {negativeEA:0.######}.");
        }

        // The ONE conversion between a Result's force and the newtons every
        // stiffness and capacity is wired in. Null, not one, on a unit it
        // does not know: a silent factor of one is the fault it exists to
        // stop.
        double? Factor(string unit) => (double?)toNewtons.Invoke(null, new object?[] { unit });
        if (Factor("N") != 1.0 || Factor(" n ") != 1.0)
            throw new InvalidOperationException("A force already in N is multiplied by 1, trimmed and either case.");
        if (Factor("kN") != 1000.0 || Factor(" KN ") != 1000.0)
            throw new InvalidOperationException("A force in kN is multiplied by 1000, trimmed and either case.");
        if (Factor("lbf") is not null || Factor("") is not null || Factor(null!) is not null)
            throw new InvalidOperationException("A unit this does not know comes back NULL, so the caller has to decide rather than scaling by one behind its back.");

        // The whole point, end to end: 0.1 kN against an EA of 1000 N is the
        // same 2 / 1.1 that 100 N gives. Unconverted it would be 2 / 1.0001,
        // and a bar would be cut to very nearly its tensioned length.
        double kiloNewtonCut = (double)unstrained.Invoke(
            null, new object?[] { 2.0, 0.1 * Factor("kN")!.Value, 1000.0 })!;
        if (Math.Abs(kiloNewtonCut - (2.0 / 1.1)) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A force of 0.1 kN converted through ToNewtons against EA 1000 N "
                + $"gives the same 2/1.1 as 100 N does; got {kiloNewtonCut:0.######}.");
        }
    }

    /// <summary>
    /// Every diagnostic on a Result as (Code, Severity, Source, Message)
    /// rows, read through the plugin's own SourceOf, so the reader checks
    /// assert prefixes and provenance without binding to DiagnosticDto.
    /// </summary>
    private static List<(string Code, string Severity, string Source, string Message)>
        DiagnosticRows(Assembly plugin, object result)
    {
        Type helper = RequireComponentType(plugin, "ResultDiagnostics");
        MethodInfo sourceOf = RequirePublicStatic(helper, "SourceOf");
        var rows = new List<(string, string, string, string)>();
        var list = (IEnumerable)result.GetType()
            .GetProperty("Diagnostics")!.GetValue(result)!;
        foreach (object entry in list)
        {
            Type type = entry.GetType();
            rows.Add((
                (string)type.GetProperty("Code")!.GetValue(entry)!,
                (string)type.GetProperty("Severity")!.GetValue(entry)!,
                (string)sourceOf.Invoke(null, new[] { entry })!,
                (string)type.GetProperty("Message")!.GetValue(entry)!));
        }
        return rows;
    }

    /// <summary>
    /// The one fixture the reader checks share: an FD Result of four
    /// vertices, one principal run 0-1-2 carrying members (0,1) and (1,2)
    /// at 0.1 and 0.2 kN, one infill member (1,3) at -0.3 kN (slack under
    /// positive_tension), one support at node 2 with a reaction (0,0,7)
    /// and a residual (0,0,13). Small forces on purpose: 0.1 kN is 100 N,
    /// so the EA and capacity conversions give clean hand numbers.
    /// </summary>
    private static object ReaderFixtureResult(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type nodalType = RequireContractType(plugin, "NodalVectorDto");
        Type topologyType = RequireContractType(plugin, "TopologyDto");
        Type equilibriumProblemType =
            RequireContractType(plugin, "EquilibriumProblemDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(1, 1, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!,
                Activator.CreateInstance(edgeType, 1, 3)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 0.1, 0.2, -0.3 });
        SetContractProperty(equilibrium, equilibriumType, "ForceUnit", "kN");
        SetContractProperty(
            equilibrium, equilibriumType, "SignConvention", "positive_tension");
        SetContractProperty(
            equilibrium, equilibriumType, "ResolvedSupportNodeIds", new[] { 2 });
        SetContractProperty(equilibrium, equilibriumType, "Reactions",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 7))!));
        SetContractProperty(equilibrium, equilibriumType, "Residuals",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 13))!));
        object topology = CreateInstance(topologyType);
        SetContractProperty(topology, topologyType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(1, 1, 0)));
        SetContractProperty(topology, topologyType, "PrincipalRuns",
            new int[][] { new[] { 0, 1, 2 } });
        object problem = CreateInstance(equilibriumProblemType);
        SetContractProperty(problem, equilibriumProblemType, "Topology", topology);
        SetContractProperty(equilibrium, equilibriumType, "Problem", problem);
        return CreateResultDto(resultType, "fd", equilibrium, null, null);
    }

    /// <summary>
    /// <c>ForcesComponent.Read</c>: the member half of what Monitor used to
    /// compute, measured through the child on the shared fixture, port by
    /// port against hand numbers, and the RES it emits carrying forces.*
    /// entries alone with Forces as their source and no monitor.* anywhere.
    /// </summary>
    private static void ValidateForcesReadings(Assembly plugin)
    {
        Type forces = RequireComponentType(plugin, "ForcesComponent");
        MethodInfo read = RequireStatic(forces, "Read");
        object result = ReaderFixtureResult(plugin);

        object readings = read.Invoke(
            null, new object?[] { result, 1000.0, 50.0 })!;
        object Prop(string name) =>
            readings.GetType().GetProperty(name)!.GetValue(readings)!;
        double[][] Branches(string name) =>
            ((IEnumerable)Prop(name)).Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>()
                    .Select(Convert.ToDouble).ToArray())
                .ToArray();
        string Render(double[][] tree) => string.Join(" | ", tree.Select(
            branch => string.Join(",", branch.Select(value =>
                value.ToString("0.####",
                    System.Globalization.CultureInfo.InvariantCulture)))));
        void SameTree(string name, double[][] expected)
        {
            double[][] actual = Branches(name);
            bool same = actual.Length == expected.Length;
            for (int b = 0; same && b < expected.Length; b++)
            {
                same = actual[b].Length == expected[b].Length;
                for (int i = 0; same && i < expected[b].Length; i++)
                    same = Math.Abs(actual[b][i] - expected[b][i]) <= 1.0e-9;
            }
            if (!same)
            {
                throw new InvalidOperationException(
                    $"{name} must be [{Render(expected)}], the bar's members "
                    + "in branch 0 and the infill LAST; got "
                    + $"[{Render(actual)}].");
            }
        }

        SameTree("MemberForce", new[] { new[] { 0.1, 0.2 }, new[] { -0.3 } });
        // This FD fixture carries no q and no H, so both are worked out at
        // the geometry: unit lengths make them equal the force.
        SameTree("ForceDensity", new[] { new[] { 0.1, 0.2 }, new[] { -0.3 } });
        SameTree("Horizontal", new[] { new[] { 0.1, 0.2 }, new[] { -0.3 } });
        SameTree("CableUtilisation", new[] { new[] { 2.0, 4.0 }, new[] { 6.0 } });
        if ((bool)Prop("EmitCableUtilisation") is not true ||
            (bool)Prop("EmitUnstrained") is not true)
        {
            throw new InvalidOperationException(
                "With EA 1000 and Cable Capacity 50 both wired, Unstrained "
                + "Length and Cable Utilisation are both emitted.");
        }

        bool[][] slack = ((IEnumerable)Prop("Slack")).Cast<IEnumerable>()
            .Select(branch => branch.Cast<object>()
                .Select(item => (bool)item).ToArray())
            .ToArray();
        if (slack.Length != 2 || slack[0].Length != 2 ||
            slack[0][0] || slack[0][1] ||
            slack[1].Length != 1 || !slack[1][0])
        {
            throw new InvalidOperationException(
                "A bar member is never slack and the pushing infill (1,3) is: "
                + "Slack must be [false,false | true].");
        }

        double[] spool = ((IEnumerable)Prop("Spool")).Cast<object>()
            .Select(Convert.ToDouble).ToArray();
        if (spool.Length != 1 || Math.Abs(spool[0] - 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "One bar of two unit segments spools 2 m; got "
                + $"[{string.Join(",", spool)}].");
        }
        double[] unstrained = ((IEnumerable)Prop("Unstrained")).Cast<object>()
            .Select(Convert.ToDouble).ToArray();
        double expectedCut = (1.0 / 1.1) + (1.0 / 1.2);
        if (unstrained.Length != 1 ||
            Math.Abs(unstrained[0] - expectedCut) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "0.1 and 0.2 kN convert to 100 and 200 N against EA 1000, so "
                + $"the bar cuts to 1/1.1 + 1/1.2 = {expectedCut:0.######}; "
                + $"got [{string.Join(",", unstrained)}]. The wrong number "
                + "here is the ForceUnit trap: an unconverted kN force cuts "
                + "the bar to very nearly its tensioned length.");
        }

        Array residuals = (Array)Prop("Residuals");
        if (residuals.Length != 4)
        {
            throw new InvalidOperationException(
                "Residuals come back ONE PER VERTEX, four here; got "
                + $"{residuals.Length}.");
        }
        double Rz(int at) => (double)residuals.GetValue(at)!.GetType()
            .GetProperty("Z")!.GetValue(residuals.GetValue(at))!;
        if (Math.Abs(Rz(2) - 13.0) > 1.0e-9 || Math.Abs(Rz(0)) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Node 2's residual lands on node 2 and an absent one is a "
                + $"zero; got item 0 = {Rz(0)}, item 2 = {Rz(2)}.");
        }

        var rows = DiagnosticRows(plugin, Prop("Result"));
        foreach (string code in new[]
        {
            "forces.counts", "forces.cable_tension", "forces.slack_cables",
            "forces.bar_force", "forces.spool", "forces.utilisation",
            "forces.demand_only"
        })
        {
            if (!rows.Any(row => row.Code == code))
            {
                throw new InvalidOperationException(
                    $"The emitted RES must carry {code}; it does not.");
            }
        }
        if (rows.Any(row => row.Code.StartsWith("monitor.", StringComparison.Ordinal)))
            throw new InvalidOperationException("The monitor.* prefix must be extinct.");
        if (rows.Where(row => row.Code.StartsWith("forces.", StringComparison.Ordinal))
                .Any(row => row.Source != "Forces"))
        {
            throw new InvalidOperationException(
                "Every forces.* entry names Forces as its source, or Replace "
                + "cannot own them on the next solve.");
        }
        (string Code, string Severity, string Source, string Message) One(
            string code) => rows.Single(row => row.Code == code);
        if (!One("forces.counts").Message.Contains(
                "1 infill cables, 2 bar members, 0 columns, 1 anchors",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "forces.counts keeps Monitor's full four-population sentence; "
                + $"got '{One("forces.counts").Message}'.");
        }
        if (One("forces.slack_cables").Severity != "warning")
            throw new InvalidOperationException("One slack cable is a warning.");
        if (One("forces.utilisation").Severity != "warning" ||
            !One("forces.utilisation").Message.Contains("up to 6", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The infill's 300 N over 50 N is 6, over one and a warning; "
                + $"got '{One("forces.utilisation").Message}'.");
        }
    }

    /// <summary>
    /// <c>SupportsReaderComponent.Read</c>: the ground half of what Monitor
    /// used to compute, measured through the child on a fixture with two
    /// isolated anchors and two one-member column trees, port by port
    /// against hand numbers, and the RES it emits carrying supports.*
    /// entries alone with no monitor.* anywhere.
    /// </summary>
    private static void ValidateSupportsReadings(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type nodalType = RequireContractType(plugin, "NodalVectorDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type supports = RequireComponentType(plugin, "SupportsReaderComponent");
        MethodInfo read = RequireStatic(supports, "Read");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 0.1, 0.2 });
        SetContractProperty(equilibrium, equilibriumType, "ForceUnit", "kN");
        SetContractProperty(
            equilibrium, equilibriumType, "SignConvention", "positive_tension");
        SetContractProperty(
            equilibrium, equilibriumType, "ResolvedSupportNodeIds", new[] { 0, 2 });
        // Node 0's tensioner axis points at node 1, along +X, so (2,0,5)
        // splits into along 2 and across 5. Node 2's axis points back at
        // node 1, along -X, so (1,0,1) splits into along -1 and across 1.
        SetContractProperty(equilibrium, equilibriumType, "Reactions",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 0, P(0, 0, 0), P(2, 0, 5))!,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(1, 0, 1))!));

        // Two one-member trees: a plumb post of 0.5 kN two metres tall, and
        // a diagonal post of 0.4 kN running one across and one up.
        object block = CreateInstance(columnsType);
        SetContractProperty(block, columnsType, "Nodes",
            Of(point, P(1, 0, 0), P(1, 0, 2), P(3, 0, 0), P(4, 0, 1)));
        SetContractProperty(block, columnsType, "Members",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 2, 3)!));
        SetContractProperty(block, columnsType, "MemberForce", new[] { 0.5, 0.4 });
        SetContractProperty(block, columnsType, "Trees",
            new int[][] { new[] { 0 }, new[] { 1 } });
        SetContractProperty(block, columnsType, "Heads", new[] { 1, 3 });
        SetContractProperty(block, columnsType, "Feet", new[] { 0, 2 });
        SetContractProperty(block, columnsType, "HeadNode", new[] { 1, 1 });
        SetContractProperty(block, columnsType, "Branching", 1);
        SetContractProperty(block, columnsType, "ForkFraction", 0.65);
        object mould = CreateInstance(mouldType);
        SetContractProperty(mould, mouldType, "Ground", 0.0);
        SetContractProperty(mould, mouldType, "Columns", block);
        object result = CreateResultDto(resultType, "fd", equilibrium, null, null);
        SetContractProperty(result, resultType, "Mould", mould);

        object readings = read.Invoke(null, new object?[] { result, 100.0 })!;
        object Prop(string name) =>
            readings.GetType().GetProperty(name)!.GetValue(readings)!;
        double[][] Branches(string name) =>
            ((IEnumerable)Prop(name)).Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>()
                    .Select(Convert.ToDouble).ToArray())
                .ToArray();
        string Render(double[][] tree) => string.Join(" | ", tree.Select(
            branch => string.Join(",", branch.Select(value =>
                value.ToString("0.####",
                    System.Globalization.CultureInfo.InvariantCulture)))));
        void SameTree(string name, double[][] expected)
        {
            double[][] actual = Branches(name);
            bool same = actual.Length == expected.Length;
            for (int b = 0; same && b < expected.Length; b++)
            {
                same = actual[b].Length == expected[b].Length;
                for (int i = 0; same && i < expected[b].Length; i++)
                    same = Math.Abs(actual[b][i] - expected[b][i]) <= 1.0e-9;
            }
            if (!same)
            {
                throw new InvalidOperationException(
                    $"{name} must be [{Render(expected)}]; got "
                    + $"[{Render(actual)}].");
            }
        }

        // Two supports joined only through the free node 1 are two strips.
        SameTree("AnchorAlong", new[] { new[] { 2.0 }, new[] { -1.0 } });
        SameTree("AnchorAcross", new[] { new[] { 5.0 }, new[] { 1.0 } });
        SameTree("ColumnForce", new[] { new[] { 0.5 }, new[] { 0.4 } });
        double diagonal = 0.4 / Math.Sqrt(2.0);
        SameTree("Thrust", new[] { new[] { 0.0 }, new[] { diagonal } });
        SameTree("Lean", new[] { new[] { 0.0 }, new[] { 45.0 } });
        SameTree("ColumnUtilisation", new[] { new[] { 5.0 }, new[] { 4.0 } });
        if ((bool)Prop("EmitColumnUtilisation") is not true)
        {
            throw new InvalidOperationException(
                "With Column Capacity 100 wired, Column Utilisation is emitted.");
        }

        object[][] tips = ((IEnumerable)Prop("TipReaction")).Cast<IEnumerable>()
            .Select(branch => branch.Cast<object>().ToArray())
            .ToArray();
        double Axis(object vector, string name) =>
            (double)vector.GetType().GetProperty(name)!.GetValue(vector)!;
        if (tips.Length != 2 || tips[0].Length != 1 || tips[1].Length != 1)
        {
            throw new InvalidOperationException(
                "Two one-member trees give two tip branches of one head each; "
                + $"got {tips.Length} branches.");
        }
        if (Math.Abs(Axis(tips[0][0], "X")) > 1.0e-9 ||
            Math.Abs(Axis(tips[0][0], "Z") - 0.5) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The plumb post's tip reaction points straight up at 0.5; got "
                + $"({Axis(tips[0][0], "X")}, {Axis(tips[0][0], "Z")}).");
        }
        if (Math.Abs(Axis(tips[1][0], "X") - diagonal) > 1.0e-9 ||
            Math.Abs(Axis(tips[1][0], "Z") - diagonal) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The diagonal post's tip reaction runs along its member, 0.4 "
                + $"over root two on X and Z; got ({Axis(tips[1][0], "X")}, "
                + $"{Axis(tips[1][0], "Z")}).");
        }

        var rows = DiagnosticRows(plugin, Prop("Result"));
        foreach (string code in new[]
        {
            "supports.column_force", "supports.thrust_into_ground",
            "supports.anchor_horizontal", "supports.anchor_split",
            "supports.utilisation", "supports.demand_only"
        })
        {
            if (!rows.Any(row => row.Code == code))
            {
                throw new InvalidOperationException(
                    $"The emitted RES must carry {code}; it does not.");
            }
        }
        if (rows.Any(row => row.Code == "supports.no_columns"))
        {
            throw new InvalidOperationException(
                "This Result carries columns, so supports.no_columns must not "
                + "be raised.");
        }
        if (rows.Any(row => row.Code.StartsWith("monitor.", StringComparison.Ordinal)))
            throw new InvalidOperationException("The monitor.* prefix must be extinct.");
        if (rows.Where(row => row.Code.StartsWith("supports.", StringComparison.Ordinal))
                .Any(row => row.Source != "Supports"))
        {
            throw new InvalidOperationException(
                "Every supports.* entry names Supports as its source.");
        }
        (string Code, string Severity, string Source, string Message) One(
            string code) => rows.Single(row => row.Code == code);
        if (One("supports.utilisation").Severity != "warning" ||
            !One("supports.utilisation").Message.Contains("up to 5", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "500 N over 100 N is 5, over one and a warning; got "
                + $"'{One("supports.utilisation").Message}'.");
        }
    }

    /// <summary>
    /// <c>SupportsReaderComponent.Read</c> and <c>ForcesComponent.Read</c>
    /// take their column groups from <c>FrameGeometry.ColumnGroups</c>, the
    /// code path Frame's Columns output branches by, so the readers cannot
    /// diverge from Frame on a block whose Trees do not cover its members.
    ///
    /// The fixture: a valid columns block of five nodes and THREE members,
    /// m0 = (0,1), m1 = (1,2), m2 = (3,4) at 0.5, 0.3 and 0.4 kN, whose
    /// Trees name [[0]] only. That UNDER-COVERS: the Trees sum to 1 member
    /// against the block's 3, so ColumnGroups' coverage test fails and
    /// TreesByFoot answers instead. Deriving that by hand: the members make
    /// nodes 0, 1 and 3 lower ends and 1, 2 and 4 upper ends, so the feet,
    /// lower and never upper, are 0 and 3, taken ascending. Climbing foot 0
    /// reaches 0, 1, 2, so m0 and m1 (lower ends 0 and 1) stand on it;
    /// climbing foot 3 reaches 3, 4, so m2 stands on it. TWO groups,
    /// [0, 1] and [2]: two branches, three members in all, Column Force
    /// [0.5, 0.3] and [0.4] in member order. Every member is one metre
    /// long, none collapsed, so Frame would draw exactly those 3 lines.
    /// The raw block.Trees walk this replaces would have given ONE branch
    /// of one member, dropping m1 and m2 from every column port while
    /// Frame drew them.
    ///
    /// The same block with Trees EMPTY is the harsher half of the defect:
    /// the raw walk measured nothing and raised supports.no_columns while
    /// Frame drew both trees. Through the shared call it reads identically
    /// to the under-covering case, and supports.no_columns fires only when
    /// the grouping itself yields no groups, which is when Frame hands
    /// back no branches.
    ///
    /// Forces counts the same population through the same call: 3 columns
    /// in forces.counts, the sum of the shared grouping's group sizes,
    /// 2 + 1.
    /// </summary>
    private static void ValidateSupportsSharedGrouping(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type supports = RequireComponentType(plugin, "SupportsReaderComponent");
        MethodInfo read = RequireStatic(supports, "Read");
        Type forcesType = RequireComponentType(plugin, "ForcesComponent");
        MethodInfo forcesRead = RequireStatic(forcesType, "Read");
        Type frameGeometry = RequireComponentType(plugin, "FrameGeometry");
        MethodInfo columnGroups = RequirePublicStatic(frameGeometry, "ColumnGroups");
        Type mouldGeometry = RequireComponentType(plugin, "MouldGeometry");
        MethodInfo treeFromBlock = RequirePublicStatic(mouldGeometry, "TreeFromBlock");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        (object Result, object Block) Build(int[][] trees)
        {
            object equilibrium = CreateInstance(equilibriumType);
            SetContractProperty(equilibrium, equilibriumType, "Vertices",
                Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
            SetContractProperty(equilibrium, equilibriumType, "Edges",
                Of(edgeType,
                    Activator.CreateInstance(edgeType, 0, 1)!,
                    Activator.CreateInstance(edgeType, 1, 2)!));
            SetContractProperty(equilibrium, equilibriumType, "MemberForces",
                new[] { 0.1, 0.2 });
            SetContractProperty(equilibrium, equilibriumType, "ForceUnit", "kN");
            SetContractProperty(
                equilibrium, equilibriumType, "SignConvention", "positive_tension");
            SetContractProperty(
                equilibrium, equilibriumType, "ResolvedSupportNodeIds", new[] { 0, 2 });

            object block = CreateInstance(columnsType);
            SetContractProperty(block, columnsType, "Nodes",
                Of(point, P(0, 0, 0), P(0, 0, 1), P(0, 0, 2), P(2, 0, 0), P(2, 0, 1)));
            SetContractProperty(block, columnsType, "Members",
                Of(edgeType,
                    Activator.CreateInstance(edgeType, 0, 1)!,
                    Activator.CreateInstance(edgeType, 1, 2)!,
                    Activator.CreateInstance(edgeType, 3, 4)!));
            SetContractProperty(block, columnsType, "MemberForce",
                new[] { 0.5, 0.3, 0.4 });
            SetContractProperty(block, columnsType, "Trees", trees);
            SetContractProperty(block, columnsType, "Heads", new[] { 2, 4 });
            SetContractProperty(block, columnsType, "Feet", new[] { 0, 3 });
            SetContractProperty(block, columnsType, "HeadNode", new[] { 1, 1 });
            SetContractProperty(block, columnsType, "Branching", 1);
            SetContractProperty(block, columnsType, "ForkFraction", 0.65);
            object mould = CreateInstance(mouldType);
            SetContractProperty(mould, mouldType, "Ground", 0.0);
            SetContractProperty(mould, mouldType, "Columns", block);
            object result = CreateResultDto(resultType, "fd", equilibrium, null, null);
            SetContractProperty(result, resultType, "Mould", mould);
            return (result, block);
        }

        void CheckOne(int[][] trees, string label)
        {
            (object result, object block) = Build(trees);

            // The count the shared code path itself returns for this block,
            // asked through the same two calls Frame's Columns makes.
            object tree = treeFromBlock.Invoke(null, new[] { block })!;
            int[] groupSizes = ((IEnumerable)columnGroups
                .Invoke(null, new[] { block, tree })!)
                .Cast<IEnumerable>()
                .Select(group => group.Cast<object>().Count())
                .ToArray();
            if (!groupSizes.SequenceEqual(new[] { 2, 1 }))
            {
                throw new InvalidOperationException(
                    $"{label}: TreesByFoot puts m0 and m1 on foot 0 and m2 on "
                    + "foot 3, so ColumnGroups returns groups of [2, 1]; got "
                    + $"[{string.Join(",", groupSizes)}].");
            }

            object readings = read.Invoke(null, new object?[] { result, 0.0 })!;
            object Prop(string name) =>
                readings.GetType().GetProperty(name)!.GetValue(readings)!;
            double[][] force = ((IEnumerable)Prop("ColumnForce"))
                .Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>()
                    .Select(Convert.ToDouble).ToArray())
                .ToArray();
            if (force.Length != groupSizes.Length)
            {
                throw new InvalidOperationException(
                    $"{label}: Supports must branch by the {groupSizes.Length} "
                    + "groups ColumnGroups returns, the same tree Frame draws; "
                    + $"got {force.Length} branches.");
            }
            // All 3 members measured: Frame draws 3 lines here, every
            // member a metre long and none collapsed, 2 + 1 across the
            // groups.
            int measured = force.Sum(branch => branch.Length);
            if (measured != 3)
            {
                throw new InvalidOperationException(
                    $"{label}: every member is measured, 3 Column Force items "
                    + $"over all branches; got {measured}.");
            }
            bool values =
                force[0].Length == 2 &&
                Math.Abs(force[0][0] - 0.5) <= 1.0e-9 &&
                Math.Abs(force[0][1] - 0.3) <= 1.0e-9 &&
                force[1].Length == 1 &&
                Math.Abs(force[1][0] - 0.4) <= 1.0e-9;
            if (!values)
            {
                throw new InvalidOperationException(
                    $"{label}: Column Force reads [0.5, 0.3] on foot 0's tree "
                    + "and [0.4] on foot 3's, in member order; got ["
                    + string.Join(" | ", force.Select(branch =>
                        string.Join(",", branch.Select(value =>
                            value.ToString("0.####",
                                System.Globalization.CultureInfo.InvariantCulture)))))
                    + "].");
            }
            var rows = DiagnosticRows(plugin, Prop("Result"));
            if (rows.Any(row => row.Code == "supports.no_columns"))
            {
                throw new InvalidOperationException(
                    $"{label}: the shared grouping yields two groups, so "
                    + "supports.no_columns must be absent; Frame draws these "
                    + "columns.");
            }

            // Forces counts the same population: 2 + 1 = 3 columns.
            object counted = forcesRead.Invoke(
                null, new object?[] { result, 0.0, 0.0 })!;
            object countedResult = counted.GetType()
                .GetProperty("Result")!.GetValue(counted)!;
            var countRows = DiagnosticRows(plugin, countedResult);
            (string Code, string Severity, string Source, string Message) counts =
                countRows.Single(row => row.Code == "forces.counts");
            if (!counts.Message.Contains("3 columns", StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{label}: forces.counts follows the shared grouping, 3 "
                    + $"columns; got '{counts.Message}'.");
            }
        }

        CheckOne(new int[][] { new[] { 0 } }, "under-covering Trees [[0]]");
        CheckOne(Array.Empty<int[]>(), "empty Trees beside three members");
    }

    /// <summary>
    /// <c>FitComponent.Read</c>: the solved-state half of what Monitor used
    /// to compute, measured through the child on a framed fixture against
    /// hand numbers, and the RES it emits carrying fit.* entries alone with
    /// no monitor.* anywhere. Bar Sag is driven all three ways: no principal
    /// runs is an empty tree, a run held at both ends sags a hand-computed
    /// 50 mm through the moved BarBending (the kN-to-N conversion and the
    /// metres-to-mm scale both load-bearing), and a run held at one notch
    /// is a mechanism reported by fit.bar_unheld.
    /// </summary>
    private static void ValidateFitReadings(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");
        Type fit = RequireComponentType(plugin, "FitComponent");
        MethodInfo read = RequireStatic(fit, "Read");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 0.1, 0.2 });
        SetContractProperty(equilibrium, equilibriumType, "ForceUnit", "kN");
        SetContractProperty(
            equilibrium, equilibriumType, "SignConvention", "positive_tension");
        SetContractProperty(
            equilibrium, equilibriumType, "ResolvedSupportNodeIds", new[] { 0, 2 });

        // The frame stands 1 mm high, 10 mm high and 2 mm LOW: a signed
        // field whose one offender is node 1 against a 5 mm tolerance.
        object frame = CreateInstance(frameType);
        SetContractProperty(frame, frameType, "Time", 50.0);
        SetContractProperty(frame, frameType, "Phase", "raise");
        SetContractProperty(frame, frameType, "Lift", 0.5);
        SetContractProperty(frame, frameType, "Sag", 0.5);
        SetContractProperty(frame, frameType, "Vertices",
            Of(point, P(0, 0, 0.001), P(1, 0, 0.010), P(2, 0, -0.002)));
        object mould = CreateInstance(mouldType);
        SetContractProperty(mould, mouldType, "Ground", 0.0);
        SetContractProperty(mould, mouldType, "Frame", frame);
        object result = CreateResultDto(resultType, "fd", equilibrium, null, null);
        SetContractProperty(result, resultType, "Mould", mould);

        object readings = read.Invoke(null, new object?[] { result, 0.0, 5.0 })!;
        object Prop(string name) =>
            readings.GetType().GetProperty(name)!.GetValue(readings)!;

        double[] deviation = ((IEnumerable)Prop("Deviation")).Cast<object>()
            .Select(Convert.ToDouble).ToArray();
        var expected = new[] { 1.0, 10.0, -2.0 };
        if (deviation.Length != 3 ||
            deviation.Zip(expected, (a, b) => Math.Abs(a - b)).Any(gap => gap > 1.0e-9))
        {
            throw new InvalidOperationException(
                "Deviation is SIGNED millimetres in vertex order, [1, 10, -2] "
                + $"here; got [{string.Join(",", deviation)}].");
        }
        double rms = (double)Prop("Rms");
        double max = (double)Prop("Max");
        double p95 = (double)Prop("P95");
        if (Math.Abs(rms - Math.Sqrt(35.0)) > 1.0e-9 ||
            Math.Abs(max - 10.0) > 1.0e-9 ||
            Math.Abs(p95 - 10.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The stats of (1, 10, -2) are RMS root 35 with worst and 95th "
                + $"percentile 10, ABSOLUTE values throughout; got {rms:0.####}, "
                + $"{max}, {p95}.");
        }
        if ((bool)Prop("Reachable") is not false)
        {
            throw new InvalidOperationException(
                "Node 1 sits 10 mm off against a 5 mm tolerance, so Reachable "
                + "is false.");
        }
        int[] unreachable = ((IEnumerable)Prop("Unreachable")).Cast<object>()
            .Select(Convert.ToInt32).ToArray();
        if (!unreachable.SequenceEqual(new[] { 1 }))
        {
            throw new InvalidOperationException(
                "Node 1 alone is outside tolerance; got "
                + $"[{string.Join(",", unreachable)}].");
        }
        if (((IEnumerable)Prop("BarSag")).Cast<object>().Any())
        {
            throw new InvalidOperationException(
                "This Result carries no principal runs, so Bar Sag is EMPTY "
                + "and fit.bar_sag_absent says why.");
        }

        var rows = DiagnosticRows(plugin, Prop("Result"));
        foreach (string code in new[]
        {
            "fit.deviation", "fit.reachability", "fit.bar_sag_absent",
            "fit.intermediate_frame"
        })
        {
            if (!rows.Any(row => row.Code == code))
            {
                throw new InvalidOperationException(
                    $"The emitted RES must carry {code}; it does not.");
            }
        }
        if (rows.Any(row => row.Code.StartsWith("monitor.", StringComparison.Ordinal)))
            throw new InvalidOperationException("The monitor.* prefix must be extinct.");
        if (rows.Where(row => row.Code.StartsWith("fit.", StringComparison.Ordinal))
                .Any(row => row.Source != "Fit"))
        {
            throw new InvalidOperationException(
                "Every fit.* entry names Fit as its source.");
        }
        (string Code, string Severity, string Source, string Message) reach =
            rows.Single(row => row.Code == "fit.reachability");
        if (reach.Severity != "warning" ||
            !reach.Message.Contains("1 of 3 nodes", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "One node out of three outside tolerance is a warning naming "
                + $"the count; got '{reach.Message}'.");
        }

        // The positive Bar Sag path, through the moved BarBending: the same
        // three-notch run held at BOTH ends, one 0.3 kN hanger pulling the
        // middle notch straight down. 0.3 kN converts to 300 N before it
        // meets EI, the span is 2 m of unit segments, so a simply supported
        // beam with EI 1000 N.m2 sags P L^3 / 48 EI at the middle notch:
        // 300 x 8 / 48000 = 0.05 m, which the port reports as 50 mm, zero
        // at the two held notches (the Hermite beam elements are nodally
        // exact for a point load at a notch).
        Type topologyType = RequireContractType(plugin, "TopologyDto");
        Type problemType = RequireContractType(plugin, "EquilibriumProblemDto");
        object sagEquilibrium = CreateInstance(equilibriumType);
        SetContractProperty(sagEquilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(1, 0, -1)));
        SetContractProperty(sagEquilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!,
                Activator.CreateInstance(edgeType, 1, 3)!));
        SetContractProperty(sagEquilibrium, equilibriumType, "MemberForces",
            new[] { 0.1, 0.2, -0.3 });
        SetContractProperty(sagEquilibrium, equilibriumType, "ForceUnit", "kN");
        SetContractProperty(
            sagEquilibrium, equilibriumType, "SignConvention", "positive_tension");
        SetContractProperty(
            sagEquilibrium, equilibriumType, "ResolvedSupportNodeIds", new[] { 0, 2 });
        object sagTopology = CreateInstance(topologyType);
        SetContractProperty(sagTopology, topologyType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(1, 0, -1)));
        SetContractProperty(sagTopology, topologyType, "PrincipalRuns",
            new int[][] { new[] { 0, 1, 2 } });
        object sagProblem = CreateInstance(problemType);
        SetContractProperty(sagProblem, problemType, "Topology", sagTopology);
        SetContractProperty(sagEquilibrium, equilibriumType, "Problem", sagProblem);
        object sagResult = CreateResultDto(
            resultType, "fd", sagEquilibrium, null, null);

        object sagReadings = read.Invoke(
            null, new object?[] { sagResult, 1000.0, 5.0 })!;
        object SagProp(string name) =>
            sagReadings.GetType().GetProperty(name)!.GetValue(sagReadings)!;
        double[][] Tree(object value) =>
            ((IEnumerable)value).Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>()
                    .Select(Convert.ToDouble).ToArray())
                .ToArray();
        string Render(double[][] tree) => string.Join(" | ", tree.Select(
            branch => string.Join(",", branch.Select(value =>
                value.ToString("0.####",
                    System.Globalization.CultureInfo.InvariantCulture)))));
        double[][] sagTree = Tree(SagProp("BarSag"));
        if (sagTree.Length != 1 || sagTree[0].Length != 3 ||
            Math.Abs(sagTree[0][0]) > 1.0e-9 ||
            Math.Abs(sagTree[0][1] - 50.0) > 1.0e-6 ||
            Math.Abs(sagTree[0][2]) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A 0.3 kN hanger on the middle notch of a 2 m run held at "
                + "both ends sags P L^3 / 48 EI = 50 mm there and zero at "
                + "the held notches, so Bar Sag is [0, 50, 0]; got "
                + $"[{Render(sagTree)}]. 0.05 here is the missing "
                + "metres-to-mm scale; 0.05 mm is the ForceUnit trap, the "
                + "kN load meeting EI unconverted.");
        }
        var sagRows = DiagnosticRows(plugin, SagProp("Result"));
        (string Code, string Severity, string Source, string Message) sagEntry =
            sagRows.Single(row => row.Code == "fit.bar_sag");
        if (sagEntry.Severity != "info" ||
            !sagEntry.Message.Contains("up to 50 mm", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "fit.bar_sag is info and names the worst sag; got "
                + $"'{sagEntry.Message}'.");
        }
        if (sagRows.Any(row => row.Code == "fit.bar_unheld"))
        {
            throw new InvalidOperationException(
                "Both ends held solves every bar, so fit.bar_unheld does "
                + "not appear.");
        }

        // A run held at ONE notch is a mechanism, not a beam: zeros for
        // alignment and fit.bar_unheld saying why. The shared reader
        // fixture holds node 2 alone, so with EI wired it is exactly this
        // case.
        object unheldReadings = read.Invoke(
            null, new object?[] { ReaderFixtureResult(plugin), 1000.0, 5.0 })!;
        object UnheldProp(string name) =>
            unheldReadings.GetType().GetProperty(name)!.GetValue(unheldReadings)!;
        double[][] unheldTree = Tree(UnheldProp("BarSag"));
        if (unheldTree.Length != 1 || unheldTree[0].Length != 3 ||
            unheldTree[0].Any(value => Math.Abs(value) > 1.0e-9))
        {
            throw new InvalidOperationException(
                "One held notch is a mechanism, not a beam: its branch is "
                + "three zeros for alignment, nothing solved; got "
                + $"[{Render(unheldTree)}].");
        }
        var unheldRows = DiagnosticRows(plugin, UnheldProp("Result"));
        if (!unheldRows.Any(row => row.Code == "fit.bar_unheld"
                && row.Severity == "warning"))
        {
            throw new InvalidOperationException(
                "A bar held at one notch raises fit.bar_unheld as a "
                + "warning.");
        }
    }

    /// <summary>
    /// The chaining rule of spec section 5: each child REPLACES only its own
    /// prefix, so Forces then Supports then Fit accumulate all three sets on
    /// one RES, re-running a child does not stack its entries, and the
    /// monitor.* prefix is extinct.
    /// </summary>
    private static void ValidateReaderChaining(Assembly plugin)
    {
        object result = ReaderFixtureResult(plugin);
        object Step(string component, object input, params object[] rest)
        {
            Type type = RequireComponentType(plugin, component);
            MethodInfo read = RequireStatic(type, "Read");
            object[] arguments = new[] { input }.Concat(rest).ToArray();
            object readings = read.Invoke(null, arguments)!;
            return readings.GetType().GetProperty("Result")!.GetValue(readings)!;
        }

        object afterForces = Step("ForcesComponent", result, 1000.0, 50.0);
        object afterSupports = Step("SupportsReaderComponent", afterForces, 100.0);
        object afterFit = Step("FitComponent", afterSupports, 0.0, 5.0);
        var rows = DiagnosticRows(plugin, afterFit);
        foreach (string prefix in new[] { "forces.", "supports.", "fit." })
        {
            if (!rows.Any(row => row.Code.StartsWith(prefix, StringComparison.Ordinal)))
            {
                throw new InvalidOperationException(
                    $"After chaining all three children the RES must carry "
                    + $"{prefix}* entries; it does not.");
            }
        }
        if (rows.Any(row => row.Code.StartsWith("monitor.", StringComparison.Ordinal)))
            throw new InvalidOperationException("The monitor.* prefix must be extinct.");

        int forcesEntries = rows.Count(
            row => row.Code.StartsWith("forces.", StringComparison.Ordinal));
        object again = Step("ForcesComponent", afterFit, 1000.0, 50.0);
        var reRun = DiagnosticRows(plugin, again);
        if (reRun.Count(row => row.Code.StartsWith("forces.", StringComparison.Ordinal))
            != forcesEntries)
        {
            throw new InvalidOperationException(
                "Re-running Forces must REPLACE its own entries, not stack "
                + "them.");
        }
        if (reRun.Count != rows.Count)
        {
            throw new InvalidOperationException(
                "Re-running Forces must leave the other children's entries "
                + $"untouched: {rows.Count} entries before, {reRun.Count} "
                + "after.");
        }
    }

    /// <summary>
    /// <c>FrameGeometry.AnchorLines</c>: spec section 4's rule, measured on
    /// hand-built strips. A strip of three nodes gives two lines, node i to
    /// node i+1 in strip order; a single-node strip keeps an EMPTY branch;
    /// and the branch count equals the strips', which is what lets Anchor
    /// Lines be read against Anchor Nodes branch for branch.
    /// </summary>
    private static void ValidateFrameAnchorLines(Assembly plugin)
    {
        Type geometry = RequireComponentType(plugin, "FrameGeometry");
        MethodInfo anchorLines = RequirePublicStatic(geometry, "AnchorLines");
        Type outerList = anchorLines.GetParameters()[0].ParameterType;
        Type innerList = outerList.GetGenericArguments()[0];
        Type point3d = innerList.GetGenericArguments()[0];
        MethodInfo outerAdd = outerList.GetMethod("Add")!;
        MethodInfo innerAdd = innerList.GetMethod("Add")!;

        object groups = Activator.CreateInstance(outerList)!;
        void Strip(params (double X, double Y, double Z)[] nodes)
        {
            object strip = Activator.CreateInstance(innerList)!;
            foreach ((double x, double y, double z) in nodes)
            {
                innerAdd.Invoke(strip, new[]
                {
                    Activator.CreateInstance(point3d, x, y, z)
                });
            }
            outerAdd.Invoke(groups, new[] { strip });
        }
        Strip((0, 0, 0), (1, 0, 0), (1, 1, 0));
        Strip((5, 5, 5));
        Strip();

        object[][] branches =
            ((IEnumerable)anchorLines.Invoke(null, new[] { groups })!)
                .Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>().ToArray())
                .ToArray();
        if (branches.Length != 3)
        {
            throw new InvalidOperationException(
                "Three strips give three branches, empties kept, so AL and AN "
                + $"stay branch for branch; got {branches.Length}.");
        }
        if (branches[0].Length != 2 || branches[1].Length != 0 ||
            branches[2].Length != 0)
        {
            throw new InvalidOperationException(
                "A strip of three nodes is two lines and a strip of one, or "
                + "none, is an EMPTY branch; got lengths "
                + $"{branches[0].Length}, {branches[1].Length}, "
                + $"{branches[2].Length}.");
        }
        double At(object line, string end, string axis)
        {
            object point = line.GetType().GetProperty(end)!.GetValue(line)!;
            return (double)point.GetType().GetProperty(axis)!.GetValue(point)!;
        }
        if (Math.Abs(At(branches[0][0], "From", "X")) > 1.0e-9 ||
            Math.Abs(At(branches[0][0], "To", "X") - 1.0) > 1.0e-9 ||
            Math.Abs(At(branches[0][1], "From", "X") - 1.0) > 1.0e-9 ||
            Math.Abs(At(branches[0][1], "To", "Y") - 1.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Line i joins node i to node i+1 IN STRIP ORDER: (0,0,0) to "
                + "(1,0,0), then (1,0,0) to (1,1,0).");
        }
    }

    /// <summary>
    /// <c>ResultTables</c> is the ONE order Deconstruct's geometry trees and
    /// Forces' number trees are both built from, and nothing measured it:
    /// the two components agreed because they call the same method, not
    /// because anything said what that method hands back. A minimal FD Result
    /// of three vertices, two edges, one support and one reaction pins the
    /// rows.
    /// </summary>
    private static void ValidateResultTablesOrder(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type nodalType = RequireContractType(plugin, "NodalVectorDto");
        Type tables = RequireComponentType(plugin, "ResultTables");
        MethodInfo members = RequirePublicStatic(tables, "Members");
        MethodInfo supportNodes = RequirePublicStatic(tables, "SupportNodes");
        MethodInfo reactions = RequirePublicStatic(tables, "Reactions");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 11.0, -22.0 });
        SetContractProperty(equilibrium, equilibriumType, "ResolvedSupportNodeIds",
            new[] { 2 });
        SetContractProperty(equilibrium, equilibriumType, "Reactions",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 7))!));
        // ONE residual, and on the LAST node on purpose: a positional reader
        // lands on item 0 and the correct reader on item 2, and that gap is
        // the whole fault being measured.
        SetContractProperty(equilibrium, equilibriumType, "Residuals",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 13))!));
        object result = CreateResultDto(resultType, "fd", equilibrium, null, null);

        Array rows = (Array)members.Invoke(null, new[] { result })!;
        if (rows.Length != 2)
        {
            throw new InvalidOperationException(
                $"Two edges must give two member rows; got {rows.Length}.");
        }
        Type rowType = rows.GetType().GetElementType()!;
        int Whole(int at, string name) =>
            (int)rowType.GetProperty(name)!.GetValue(rows.GetValue(at))!;
        double Real(int at, string name) =>
            (double)rowType.GetProperty(name)!.GetValue(rows.GetValue(at))!;

        if (Whole(0, "U") != 0 || Whole(0, "V") != 1 ||
            Whole(1, "U") != 1 || Whole(1, "V") != 2)
        {
            throw new InvalidOperationException(
                "The rows keep the edges in order with their own ends; got "
                + $"({Whole(0, "U")},{Whole(0, "V")}) then "
                + $"({Whole(1, "U")},{Whole(1, "V")}).");
        }
        if (Math.Abs(Real(0, "Force") - 11.0) > 1.0e-9 ||
            Math.Abs(Real(1, "Force") + 22.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Each row carries its own edge's signed force; got "
                + $"{Real(0, "Force")} and {Real(1, "Force")}.");
        }
        if (Whole(0, "Id") != 0 || Whole(1, "Id") != 1 ||
            Whole(0, "EquilibriumEdgeId") != 0 || Whole(1, "EquilibriumEdgeId") != 1)
        {
            throw new InvalidOperationException(
                "An FD row's id and equilibrium edge id are its edge index.");
        }
        // NaN, not zero: this Result carries no force densities and an FD
        // Result carries no horizontal force at all, and zero is a reading a
        // monitor would draw and believe.
        if (!double.IsNaN(Real(0, "Q")) || !double.IsNaN(Real(0, "H")))
        {
            throw new InvalidOperationException(
                "A missing force density or horizontal force must arrive as "
                + $"NaN; got {Real(0, "Q")} and {Real(0, "H")}.");
        }

        int[] supports = ((IEnumerable)supportNodes.Invoke(null, new[] { result })!)
            .Cast<int>()
            .ToArray();
        if (!supports.SequenceEqual(new[] { 2 }))
        {
            throw new InvalidOperationException(
                $"The support ids are the Result's own; got [{string.Join(",", supports)}].");
        }

        Array acting = (Array)reactions.Invoke(null, new[] { result })!;
        if (acting.Length != 1)
        {
            throw new InvalidOperationException(
                $"One reaction went in and {acting.Length} came back.");
        }
        object pair = acting.GetValue(0)!;
        int node = (int)pair.GetType().GetField("Item1")!.GetValue(pair)!;
        object vector = pair.GetType().GetField("Item2")!.GetValue(pair)!;
        double z = (double)vector.GetType().GetProperty("Z")!.GetValue(vector)!;
        if (node != 2 || Math.Abs(z - 7.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"The reaction comes back at node 2 with Z 7; got node {node}, Z {z}.");
        }

        // The residual table: one slot per VERTEX, not one per sparse entry.
        MethodInfo residualTable = RequirePublicStatic(tables, "Residuals");
        Array placed = (Array)residualTable.Invoke(null, new[] { result })!;
        if (placed.Length != 3)
        {
            throw new InvalidOperationException(
                "The residuals come back ONE PER VERTEX, three here, however few "
                + $"the Result's sparse list carries; got {placed.Length}. A length "
                + "equal to the sparse list is the positional read this exists to "
                + "stop.");
        }
        double Rz(int at) => (double)placed.GetValue(at)!.GetType()
            .GetProperty("Z")!.GetValue(placed.GetValue(at))!;
        if (Math.Abs(Rz(2) - 13.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"Node 2's residual must land at item 2; got {Rz(2)} there. Reading "
                + "13 at item 0 means the sparse list was read positionally, which "
                + "puts every node's residual on some other node.");
        }
        if (Math.Abs(Rz(0)) > 1.0e-9 || Math.Abs(Rz(1)) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A node the Result carries no residual for holds its slot as a ZERO "
                + $"rather than shifting its neighbours up; got {Rz(0)} and {Rz(1)}.");
        }

        // ---- the TNA path, which is where the table makes decisions -------
        // The FD path above is a straight walk of the edge list. Everything
        // that could actually misalign the two components lives here: the
        // sort by Id, the ends read through the edge each state NAMES, the
        // out-of-range support drop and the zero-reaction drop.
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type supportType = RequireContractType(plugin, "TnaSupportMappingDto");
        Type edgeStateType = RequireContractType(plugin, "TnaEdgeStateDto");

        object tnaEquilibrium = CreateInstance(equilibriumType);
        SetContractProperty(tnaEquilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(tnaEquilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!,
                Activator.CreateInstance(edgeType, 2, 0)!));

        object State(int id, int edge, double axial)
        {
            object state = CreateInstance(edgeStateType);
            SetContractProperty(state, edgeStateType, "Id", id);
            SetContractProperty(state, edgeStateType, "EquilibriumEdgeId", edge);
            SetContractProperty(state, edgeStateType, "AxialForce", axial);
            return state;
        }
        object At(int vertex, object reaction)
        {
            object item = CreateInstance(supportType);
            SetContractProperty(item, supportType, "EquilibriumVertexId", vertex);
            SetContractProperty(item, supportType, "Reaction", reaction);
            return item;
        }

        object mappings = CreateInstance(mappingsType);
        // Support 7 is not a vertex of this net. TnaMappingsDto validates
        // nothing and ResultDto.Validate never reaches it, so it has to be
        // dropped in the table or one reader indexes off the end of the
        // vertex list while the other walks past it.
        SetContractProperty(mappings, mappingsType, "Supports",
            Of(supportType, At(0, P(0, 0, 0)), At(7, P(0, 0, 0)), At(2, P(0, 0, 0))));
        SetContractProperty(mappings, mappingsType, "Reactions",
            Of(supportType, At(0, P(0, 0, 0)), At(2, P(0, 0, 5))));

        object tna = CreateResultDto(
            resultType,
            "tna",
            tnaEquilibrium,
            CreateInstance(graphType),
            CreateInstance(graphType));
        SetContractProperty(tna, resultType, "Mappings", mappings);
        // Id order and EquilibriumEdgeId order DISAGREE, and the list order is
        // neither: sorting by the wrong key, or not sorting at all, gives
        // three different answers here and only one of them is right.
        SetContractProperty(tna, resultType, "EdgeStates",
            Of(edgeStateType, State(2, 1, 30.0), State(0, 2, 10.0), State(1, 0, 20.0)));

        Array tnaRows = (Array)members.Invoke(null, new[] { tna })!;
        if (tnaRows.Length != 3)
        {
            throw new InvalidOperationException(
                $"Three edge states must give three member rows; got {tnaRows.Length}.");
        }
        int TnaWhole(int at, string name) =>
            (int)rowType.GetProperty(name)!.GetValue(tnaRows.GetValue(at))!;
        double TnaReal(int at, string name) =>
            (double)rowType.GetProperty(name)!.GetValue(tnaRows.GetValue(at))!;
        if (TnaWhole(0, "Id") != 0 || TnaWhole(1, "Id") != 1 || TnaWhole(2, "Id") != 2)
        {
            throw new InvalidOperationException(
                "The rows come back in EDGE STATE ID order, whatever order the "
                + $"Result lists them in; got ids {TnaWhole(0, "Id")}, "
                + $"{TnaWhole(1, "Id")}, {TnaWhole(2, "Id")}. This is the one "
                + "ordering that decides whether Deconstruct's Member Lines and "
                + "Forces' member forces describe the same member.");
        }
        if (TnaWhole(0, "U") != 2 || TnaWhole(0, "V") != 0 ||
            TnaWhole(1, "U") != 0 || TnaWhole(1, "V") != 1 ||
            TnaWhole(2, "U") != 1 || TnaWhole(2, "V") != 2)
        {
            throw new InvalidOperationException(
                "Each row's ends are those of the equilibrium edge its state "
                + "NAMES, not of the edge at its own index; state 0 names edge 2, "
                + $"so it runs 2 to 0. Got ({TnaWhole(0, "U")},{TnaWhole(0, "V")}), "
                + $"({TnaWhole(1, "U")},{TnaWhole(1, "V")}), "
                + $"({TnaWhole(2, "U")},{TnaWhole(2, "V")}).");
        }
        if (Math.Abs(TnaReal(0, "Force") - 10.0) > 1.0e-9 ||
            Math.Abs(TnaReal(1, "Force") - 20.0) > 1.0e-9 ||
            Math.Abs(TnaReal(2, "Force") - 30.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Each row keeps its own state's axial force through the sort; got "
                + $"{TnaReal(0, "Force")}, {TnaReal(1, "Force")}, "
                + $"{TnaReal(2, "Force")}.");
        }

        int[] tnaSupports = ((IEnumerable)supportNodes.Invoke(null, new[] { tna })!)
            .Cast<int>()
            .ToArray();
        if (!tnaSupports.SequenceEqual(new[] { 0, 2 }))
        {
            throw new InvalidOperationException(
                "A support naming a vertex this net does not have is dropped in "
                + "the TABLE, so both readers drop the same one; expected [0,2], "
                + $"got [{string.Join(",", tnaSupports)}].");
        }

        Array tnaReactions = (Array)reactions.Invoke(null, new[] { tna })!;
        if (tnaReactions.Length != 1)
        {
            throw new InvalidOperationException(
                "A zero reaction is not a reaction: two went in and only the "
                + $"non-zero one comes back; got {tnaReactions.Length}. Keeping the "
                + "zero would give Deconstruct and Supports different stray branches.");
        }
        object tnaPair = tnaReactions.GetValue(0)!;
        int tnaNode = (int)tnaPair.GetType().GetField("Item1")!.GetValue(tnaPair)!;
        object tnaVector = tnaPair.GetType().GetField("Item2")!.GetValue(tnaPair)!;
        double tnaZ = (double)tnaVector.GetType().GetProperty("Z")!.GetValue(tnaVector)!;
        if (tnaNode != 2 || Math.Abs(tnaZ - 5.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"The surviving reaction is node 2's, Z 5; got node {tnaNode}, Z {tnaZ}.");
        }
    }

    /// <summary>
    /// <c>ParameterIdentity.Mismatch</c>: the one thing that tells a reopened
    /// definition that the component it is wired to has changed shape.
    ///
    /// Grasshopper matches archived parameter chunks to live parameters by
    /// INDEX, so a reshaped component does not come back with broken wires:
    /// they reattach to whatever now stands at that index, silently wherever
    /// the two ports share a type. Counting the ports catches a component
    /// that grew or shrank. It does NOT catch Monitor, whose Result moved
    /// from the last output to the first with the count unchanged, which
    /// puts every one of twenty tree wires one slot down on a same-typed
    /// tree. So the NAMES are compared too, index by index.
    ///
    /// A null archived name is not evidence of anything: it is an archive
    /// this cannot read a name out of, and it is skipped rather than counted
    /// as a difference, so a future Grasshopper that stops writing Name
    /// degrades to the count check instead of warning every file in the
    /// world.
    /// </summary>
    private static void ValidateParameterMismatch(Assembly plugin)
    {
        Type identity = RequireComponentType(plugin, "ParameterIdentity");
        MethodInfo mismatch = RequireStatic(identity, "Mismatch");

        string?[] Names(int count, string stem) => Enumerable
            .Range(0, count)
            .Select(index => (string?)($"{stem} {index}"))
            .ToArray();
        string[] Registered(int count, string stem) => Enumerable
            .Range(0, count)
            .Select(index => $"{stem} {index}")
            .ToArray();
        string? Ask(
            IReadOnlyList<string?> archivedIn,
            IReadOnlyList<string?> archivedOut,
            IReadOnlyList<string> registeredIn,
            IReadOnlyList<string> registeredOut) =>
            mismatch.Invoke(
                null,
                new object?[]
                {
                    archivedIn, archivedOut, registeredIn, registeredOut
                }) as string;

        // Deconstruct's own move, the case this check was born on: two
        // inputs and twenty outputs archived against the one and fourteen
        // it registers now.
        string? moved = Ask(
            Names(2, "in"),
            Names(20, "out"),
            Registered(1, "in"),
            Registered(14, "out"));
        if (moved is not string text)
        {
            throw new InvalidOperationException(
                "A definition saved against 2 inputs and 20 outputs, opened "
                + "against 1 and 14, must be warned that its wires moved; nothing "
                + "came back.");
        }
        if (!text.Contains("20", StringComparison.Ordinal) ||
            !text.Contains("14", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The warning must name what was archived and what is registered, "
                + $"so the author knows which surface moved; got '{text}'.");
        }

        // The ordinary case: a file saved against the surface the plugin
        // registers today, name for name.
        string? unchanged = Ask(
            Names(4, "in"),
            Names(9, "out"),
            Registered(4, "in"),
            Registered(9, "out"));
        if (unchanged is not null)
        {
            throw new InvalidOperationException(
                "A file saved against the CURRENT surface must stay silent, or "
                + "every reopened definition carries a warning that means nothing; "
                + $"got '{unchanged}'.");
        }

        // MONITOR's case, and the whole reason names are read: twenty-one
        // outputs before and twenty-one after, with the Result moved from
        // the end to the front. The counts agree, so a count check says
        // nothing at all while every tree wire sits one slot low.
        var monitorTrees = new[]
        {
            "Member Force", "Force Density", "Horizontal Force", "Slack",
            "Spool Length", "Unstrained Length",
            "Anchor Along", "Anchor Across",
            "Tip Reaction", "Column Force", "Thrust", "Lean",
            "Deviation", "Deviation Stats", "Reachable", "Unreachable",
            "Bar Sag", "Residuals",
            "Cable Utilisation", "Column Utilisation"
        };
        string?[] archivedMonitor = monitorTrees
            .Select(name => (string?)name)
            .Append("Result")
            .ToArray();
        string[] registeredMonitor = new[] { "Result" }
            .Concat(monitorTrees)
            .ToArray();
        string?[] monitorInputs = new string?[]
        {
            "Result", "EI", "EA", "Tolerance", "Cable Capacity",
            "Column Capacity"
        };
        string? monitorMoved = Ask(
            monitorInputs,
            archivedMonitor,
            monitorInputs.Select(name => name!).ToArray(),
            registeredMonitor);
        if (monitorMoved is not string monitorText ||
            !monitorText.Contains("Member Force", StringComparison.Ordinal) ||
            !monitorText.Contains("Result", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Monitor keeps twenty-one outputs and moves the Result to the "
                + "front, so the counts agree and only the names say the wires "
                + "moved; the warning must name the port that changed. Got "
                + $"'{monitorMoved}'.");
        }
        // And it must LEAD with that name. Opening on counts that agree
        // reads as a denial of the rename that follows it, on the one
        // component the whole name comparison was built for.
        if (monitorText.Contains("outputs archived", StringComparison.Ordinal) ||
            !monitorText.Contains(
                "the counts are unchanged", StringComparison.Ordinal) ||
            monitorText.IndexOf("Member Force", StringComparison.Ordinal) >
                monitorText.IndexOf("counts", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Where only a name moved, the rename LEADS and the equal "
                + "counts are given after it as the reason every wire came "
                + "back attached; counts that agree are not evidence and "
                + $"must not open the sentence. Got '{monitorText}'.");
        }

        // Export's own move, and the reason it holds Live: a definition
        // saved before the export-live branch carries seven inputs and two
        // outputs against the nine and two registered now, so every INPUT
        // wire in it lands on a different port, three of them silently, and
        // one of those three is the Live toggle. The output count came back
        // to two by a different route (one JSON list and one Status), so
        // the outputs alone would say nothing.
        string? exportMoved = Ask(
            Names(7, "in"),
            Names(2, "out"),
            Registered(9, "in"),
            Registered(2, "out"));
        if (exportMoved is not string exportText ||
            !exportText.Contains("7 inputs and 2 outputs", StringComparison.Ordinal) ||
            !exportText.Contains("9 and 2", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A saved Export, 7 inputs and 2 outputs against the 9 and 2 it "
                + "registers now, must be warned and both counts named: the "
                + "output count came back to two by a different route and every "
                + "input wire still moved; got "
                + $"'{exportMoved}'.");
        }

        // THIS branch's Deconstruct slim, with the real port names: 14
        // outputs archived against the 10 registered, the Result input
        // untouched. The four archived names registered nowhere any more,
        // Thrust Mesh (old slot 0), Columns (10), Heads (11) and Feet
        // (12), must be NAMED as removed, in archived order, because every
        // remaining wire reattached one or more slots off and the counts
        // alone never say which quantities are simply gone. Spec section 8
        // and the taxonomy's Deconstruct row both promise exactly this.
        string?[] deconstructArchived =
        {
            "Thrust Mesh", "Member Lines", "Form Lines", "Member IDs",
            "Node IDs", "Support Points", "Load Points", "Load Vectors",
            "Reaction Points", "Reaction Vectors", "Columns", "Heads",
            "Feet", "Force Lines"
        };
        string[] deconstructRegistered =
        {
            "Member Lines", "Form Lines", "Member IDs", "Node IDs",
            "Support Points", "Load Points", "Load Vectors",
            "Reaction Points", "Reaction Vectors", "Force Lines"
        };
        string? slimmed = Ask(
            new string?[] { "Result" },
            deconstructArchived,
            new[] { "Result" },
            deconstructRegistered);
        if (slimmed is not string slimText ||
            !slimText.Contains("14 outputs archived", StringComparison.Ordinal) ||
            !slimText.Contains("1 and 10 registered", StringComparison.Ordinal) ||
            !slimText.Contains(
                "removed: 'Thrust Mesh', 'Columns', 'Heads', 'Feet'",
                StringComparison.Ordinal) ||
            !slimText.Contains("check every", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Deconstruct's slim, 14 outputs to 10, must name both counts "
                + "and the four removed ports in archived order, so the "
                + "author knows which quantities are GONE rather than moved, "
                + "and must still send them to check every reattached wire; "
                + $"got '{slimmed}'.");
        }

        // Frame's own append: nine outputs archived against the ten
        // registered, Anchor Lines new at the END, every shared slot still
        // holding its name and the Result input untouched (ten archived
        // ports against eleven registered in all). Nothing moved, so the
        // author is told WHAT was appended and that the wires kept their
        // ports, not sent to check every one of them for a change that
        // could not have moved any.
        string?[] frameArchived =
        {
            "Mesh", "Cables", "Principal Lines", "Principal Nodes",
            "Anchor Nodes", "Perimeter Nodes", "Perimeter Lines",
            "Columns", "Phase"
        };
        string[] frameRegistered =
        {
            "Mesh", "Cables", "Principal Lines", "Principal Nodes",
            "Anchor Nodes", "Perimeter Nodes", "Perimeter Lines",
            "Columns", "Phase", "Anchor Lines"
        };
        string? appended = Ask(
            new string?[] { "Result" },
            frameArchived,
            new[] { "Result" },
            frameRegistered);
        if (appended is not string appendText ||
            !appendText.Contains(
                "'Anchor Lines' was appended", StringComparison.Ordinal) ||
            !appendText.Contains(
                "existing wires kept their ports", StringComparison.Ordinal) ||
            appendText.Contains("check every", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Frame's append, nine outputs to ten with Anchor Lines new "
                + "at the end, must name the append and say the wires kept "
                + "their ports; 'check every' has no business in a warning "
                + $"about a change that moved nothing; got '{appended}'.");
        }

        // The INPUT SIDE alone, which is what Export's Live hold reads.
        //
        // A Warning is owed for either side moving, so Mismatch asks about
        // both. Acting on the finding is a different question: Grasshopper
        // reattaches an archived wire to the live port at its own index, so
        // only an INPUT wire can land on a port the component then obeys,
        // and Export's Live toggle is one of those ports. An output-side
        // change cannot flip it. Export's outputs went from six to two on
        // this branch with its nine inputs untouched, so a hold on any port
        // move would have held Live on every definition in existence for a
        // change that could not have moved a single input wire.
        MethodInfo sideMoved = RequireStatic(identity, "SideMoved");
        bool Side(
            IReadOnlyList<string?> archived,
            IReadOnlyList<string> registered) =>
            sideMoved.Invoke(null, new object?[] { archived, registered })
                is true;

        // The case the hold exists for: a pre-export-live definition, seven
        // archived inputs against the nine registered now.
        if (!Side(Names(7, "in"), Registered(9, "in")))
        {
            throw new InvalidOperationException(
                "Seven archived inputs against nine registered is an input "
                + "move, and Export must hold Live on it: three input wires "
                + "land on ports they did not leave, one of them the Live "
                + "toggle, and a Warning cannot recall a study already "
                + "pushed to a studio.");
        }
        // The same shape with only a NAME moved, which is the half a count
        // comparison cannot see.
        string?[] renamedInputs =
        {
            "Result", "Path", "Write", "Name", "Courses", "Cells", "Live",
            "Studio", "Column Radius"
        };
        string[] registeredInputs =
        {
            "Result", "Path", "Write", "Name", "Cells", "Courses", "Live",
            "Studio", "Column Radius"
        };
        if (!Side(renamedInputs, registeredInputs))
        {
            throw new InvalidOperationException(
                "Nine inputs before and nine after, with two of them "
                + "swapped, is still an input move: the counts agree and "
                + "every wire reattached to the wrong port, which is the "
                + "case names were compared for in the first place.");
        }
        // THIS BRANCH's own move, and the one that must NOT hold: the
        // outputs went six to two and the nine inputs did not move.
        if (Side(Names(9, "in"), Registered(9, "in")))
        {
            throw new InvalidOperationException(
                "Export's outputs went from six to two on this branch with "
                + "its nine inputs untouched. The Warning is owed, and "
                + "Mismatch gives it; the HOLD is not, because no output "
                + "change can put an archived wire on the Live toggle. "
                + "Holding here would hold Live on every definition in "
                + "existence.");
        }
        if (!Side(Names(6, "out"), Registered(2, "out")))
        {
            throw new InvalidOperationException(
                "Six archived outputs against two registered is a move on "
                + "the side it is asked about; the previous case rests on "
                + "the OUTPUT side having really changed while the input "
                + "side stayed still.");
        }
        // And both sides agreeing is silence, as it is for Mismatch.
        if (Side(Names(9, "in"), Registered(9, "in")) ||
            Side(registeredInputs.Select(name => (string?)name).ToArray(),
                 registeredInputs))
        {
            throw new InvalidOperationException(
                "A side whose archived names and counts are the ports "
                + "registered there now has not moved, and nothing may be "
                + "held on it.");
        }

        // A longer archived list: the one case that visibly breaks in
        // Grasshopper anyway, and it must still be announced.
        string? shrunk = Ask(
            Names(1, "in"),
            Names(9, "out"),
            Registered(1, "in"),
            Registered(6, "out"));
        if (shrunk is null)
        {
            throw new InvalidOperationException(
                "Nine archived outputs against six registered must be "
                + "announced; three of those wires have nowhere to land.");
        }

        // A name the archive does not carry is not a rename. Everything
        // else agreeing, this stays silent.
        string?[] blind = new string?[] { "Result", null, "Elements" };
        string? unreadable = Ask(
            blind,
            Names(0, "out"),
            new[] { "Result", "Style", "Elements" },
            Array.Empty<string>());
        if (unreadable is not null)
        {
            throw new InvalidOperationException(
                "An archived parameter chunk this cannot read a Name out of is "
                + "no evidence that anything moved, and must not raise a "
                + $"warning on its own; got '{unreadable}'.");
        }
    }

    /// <summary>
    /// <c>ColumnFinderComponent</c>'s load path and column aiming, measured
    /// against vectors worked out by hand.
    ///
    /// This path had never had a number checked, and when it finally was, it
    /// was reading the load off <c>equilibrium.Reactions</c>, which exist only
    /// at SUPPORTS: every interior notch read zero, so each bar was solved as a
    /// beam with no load on it. The load now comes from the solve's own member
    /// forces, and the direction that falls out of it aims the column.
    ///
    /// Three bars, each three notches long, running along Y at x = 0, one metre
    /// up. Only the middle notch is loaded, and only its infill cables differ:
    ///
    ///   SYMMETRIC   cables to (-1, y, 0) and (1, y, 0), 100 N each. The
    ///               horizontal halves cancel and the pull is straight down, so
    ///               the column must come out PLUMB. Leaning it would cost
    ///               axial force and hand its foot a sideways push for nothing,
    ///               which is the whole reason a lean has to be earned.
    ///
    ///   ONE-SIDED   one cable to (1, y, 0), 100 N, so the pull runs down and
    ///               toward +x at 45 degrees. The column supplies the opposite,
    ///               so it aims up and toward -x at 45 degrees and its FOOT
    ///               lands on the +x side: it leans against the pull. This is
    ///               Gaudi's rule, and the sign is the half of it that is easy
    ///               to get backwards.
    ///
    ///   SHALLOW     one cable to (1, y, 0.9), so the pull is nearly
    ///               horizontal and would want a 84-degree lean. Held at the
    ///               60-degree cap instead, because past that a column pushes
    ///               sideways more than it holds up and the sliding joint
    ///               cannot reach the angle.
    ///
    /// The bar runs along Y throughout, so its tangent is Y and the projection
    /// that sends along-bar pull to the anchors takes nothing away here. That
    /// is deliberate: it keeps these three cases about the aiming.
    /// </summary>
    private static void ValidateColumnAim(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo loads = finder.GetMethod("BarLoads", BindingFlags.Public | BindingFlags.Static)!;
        MethodInfo transverse = finder.GetMethod("BarTransverse", BindingFlags.Public | BindingFlags.Static)!;
        // The aim rule itself now lives in MouldGeometry, shared: Column
        // Finder PLACES by it, and Animate only MEASURES its trunks against
        // it, so testing it once tests both. Animate re-aims nothing: a trunk
        // points where its foot and its notch put it, and the aim is read to
        // report how far that is from the force path at this frame.
        MethodInfo armAim = finder.GetMethod(
            "AimFrom", BindingFlags.Public | BindingFlags.Static)!;

        Type point3d = loads.GetParameters()[1].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "BarLoads' node parameter is not an array.");
        Type incidentArray = loads.GetParameters()[2].ParameterType;
        Type incidentList = incidentArray.GetElementType()
            ?? throw new InvalidOperationException(
                "BarLoads' incident parameter is not an array.");

        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.0, twoSided: true,
            expectedX: 0.0, expectedZ: 1.0, label: "symmetric bay");
        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.0, twoSided: false,
            expectedX: -Math.Sqrt(0.5), expectedZ: Math.Sqrt(0.5),
            label: "one-sided bay");

        // Capped: the direction is held at sixty degrees from vertical, so the
        // horizontal part is sin(60) and the vertical cos(60), leaning toward
        // -x as before.
        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.9, twoSided: false,
            expectedX: -Math.Sin(Math.PI / 3.0),
            expectedZ: Math.Cos(Math.PI / 3.0),
            label: "capped shallow pull");
    }

    /// <summary>
    /// <c>ColumnPlacement</c>, the engine that replaced the beam search:
    /// every rule of spec section 3, driven on hand-built nets. A net here is
    /// an arch of notches in the XZ plane, anchored at both ends, with a
    /// vertical pull on every notch; that is enough to measure grouping,
    /// feet, fork, rejection and Auto, and it is the case Param's three
    /// screenshots were of.
    /// </summary>
    private static void ValidateColumnPlacement(Assembly plugin)
    {
        Type engine = plugin.GetType(
            "Ananke.COMPAS.Native.Components.ColumnPlacement", throwOnError: true)!;
        MethodInfo group = RequirePublicStatic(engine, "Group");
        MethodInfo place = RequirePublicStatic(engine, "Place");
        MethodInfo segment = RequirePublicStatic(engine, "SegmentDistance");
        MethodInfo symmetrise = RequirePublicStatic(engine, "Symmetrise");
        Type point3d = place.GetParameters()[0].ParameterType.GetElementType()!;
        Type vector3d = place.GetParameters()[3].ParameterType.GetElementType()!.GetElementType()!;
        double forkFraction = (double)engine.GetField("ForkFraction")!.GetValue(null)!;
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        double maxLean = (double)geometry.GetField("MaxLeanDegrees")!.GetValue(null)!;
        double alignmentCap = (double)engine.GetField("AlignmentDegrees")!.GetValue(null)!;

        // ---- Grouping.
        (int[][] Groups, int[] Mains) Grouped(int count, int branching)
        {
            object result = group.Invoke(null, new object?[] { count, branching })!;
            Type type = result.GetType();
            return (
                (int[][])type.GetField("Item1")!.GetValue(result)!,
                (int[])type.GetField("Item2")!.GetValue(result)!);
        }
        string Show(int[][] groups) => string.Join(" ", groups.Select(g => "[" + string.Join(",", g) + "]"));

        (int[][] nine, int[] nineMains) = Grouped(9, 2);
        string nineText = Show(nine);
        if (nineText != "[0,1] [2,3] [4] [5,6] [7,8]")
            throw new InvalidOperationException($"Nine notches at Branching 2 must be a centre single and four mirrored pairs; got {nineText}.");
        if (!nineMains.SequenceEqual(new[] { 1, 3, 4, 5, 7 }))
            throw new InvalidOperationException($"Mains must be the innermost notch of each group, mirrored; got [{string.Join(",", nineMains)}].");
        (int[][] eight, _) = Grouped(8, 3);
        string eightText = Show(eight);
        if (eightText != "[0] [1,2,3] [4,5,6] [7]")
            throw new InvalidOperationException($"Eight notches at Branching 3 must be two triples with a single at each anchor end; got {eightText}.");
        (int[][] five, _) = Grouped(5, 1);
        if (five.Length != 5 || five.Any(g => g.Length != 1))
            throw new InvalidOperationException($"Five notches at Branching 1 are five singles; got {Show(five)}.");
        (int[][] none, _) = Grouped(0, 2);
        if (none.Length != 0)
            throw new InvalidOperationException("No notches group into nothing.");

        // ---- A hand-built arch.
        // count notches from x = 0 to x = width, z = rise * 4 * s * (1 - s),
        // anchored at both ends, every notch pulled straight down by `load`.
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;

        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Arch(int count, double width, double rise, double load)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                acrossBar.SetValue(V(0.0, 0.0, -load), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        object Run((Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net, int[][] loops, double median, int branching, int ground)
        {
            return place.Invoke(null, new object?[]
            {
                net.Nodes, net.Bars, net.Anchors, net.Across, loops, 0.0, median, branching, ground,
            })!;
        }
        T Get<T>(object o, string name)
        {
            Type type = o.GetType();
            object value = type.GetField(name)?.GetValue(o) ?? type.GetProperty(name)?.GetValue(o)
                ?? throw new InvalidOperationException($"{type.Name} has no {name}.");
            return (T)value;
        }
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;
        double VX(object v) => (double)vector3d.GetProperty("X")!.GetValue(v)!;
        double VY(object v) => (double)vector3d.GetProperty("Y")!.GetValue(v)!;
        double VZ(object v) => (double)vector3d.GetProperty("Z")!.GetValue(v)!;

        // A parabolic arch whose across pulls are mirrored in SHAPE, carrying
        // the two asymmetries a solved net always has. `bend` is the mirrored
        // part (positive leans the pulls outward from the midpoint), `skew` a
        // common along-chord tilt on every notch, `flank` a scale on the left
        // half alone. Neither asymmetry survives the mirror rule of spec 3.4,
        // and both move the feet today.
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) SkewArch(
            int count, double width, double rise, double bend, double skew, double flank)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            double middle = (count - 1) / 2.0;
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                double scale = i < middle ? flank : 1.0;
                acrossBar.SetValue(V(scale * ((side * bend) + skew), 0.0, -scale), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        // A bar that curves IN PLAN, which is the case BarTransverse exists
        // for and the case every other fixture in this file is blind to.
        //
        // Ten nodes read in a chord frame: u along the chord in unit steps
        // from -4.5 to 4.5, v across it, a plan parabola with a sagitta of 2
        // at the crown falling to zero at both ends, so the two ANCHORS are
        // the chord itself and all eight free notches stand off it. Elevation
        // is the usual parabola, rise 3. The whole plan is then turned onto
        // the direction (1, 2)/sqrt(5). That direction matters: a bounding box
        // mirrors correctly about a chord running along either axis or at 45
        // degrees, and it mirrors correctly here too whenever a band's world X
        // and Y extremes fall on the same two notches, which a plan bulge
        // rising monotonically toward the crown arranges at most chord
        // angles. At this one the world X of a band turns back on itself
        // (the steps are -0.083, +0.094, +0.271), so the X extreme moves off
        // the band's end notch and the box stops mirroring while the mean
        // still does.
        //
        // Every pull leans INWARD along the chord by `lean` to 1 with no
        // across-chord part at all, so the span's own mean across is zero and
        // it keeps the frame its node order gives it.
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) PlanCurved(double lean)
        {
            const int count = 10;
            const double half = 4.5;
            const double sag = 2.0;
            const double rise = 3.0;
            double cx = 1.0 / Math.Sqrt(5.0);
            double cy = 2.0 / Math.Sqrt(5.0);
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            for (int i = 0; i < count; i++)
            {
                double u = i - half;
                double v = sag * (1.0 - ((u / half) * (u / half)));
                double s = (double)i / (count - 1);
                nodes.SetValue(
                    P((u * cx) - (v * cy), (u * cy) + (v * cx), rise * 4.0 * s * (1.0 - s)), i);
                double along = (i * 2) < count ? lean : -lean;
                acrossBar.SetValue(V(along * cx, along * cy, -1.0), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        // A span's own frame, read off its first and last node: how far along
        // the chord from its midpoint a plan point stands, and how far across.
        (double Along, double Across) InSpanFrame(Array netNodes, int[] bar, object span, object point)
        {
            object first = netNodes.GetValue(bar[Get<int>(span, "First")])!;
            object last = netNodes.GetValue(bar[Get<int>(span, "Last")])!;
            double dx = X(last) - X(first);
            double dy = Y(last) - Y(first);
            double length = Math.Sqrt((dx * dx) + (dy * dy));
            dx /= length;
            dy /= length;
            double ox = X(point) - (0.5 * (X(first) + X(last)));
            double oy = Y(point) - (0.5 * (Y(first) + Y(last)));
            return ((ox * dx) + (oy * dy), (ox * -dy) + (oy * dx));
        }

        (int Lower, int Upper)[] MembersOf(object level) =>
            ((IEnumerable)Get<object>(level, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!,
                    (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();

        // Which node each tree stands on: the lower end of the first member
        // of that tree that leaves a foot.
        int[] FootOfTree(object level, int treeCount)
        {
            (int Lower, int Upper)[] members = MembersOf(level);
            var feet = ((IEnumerable)Get<object>(level, "Feet")).Cast<int>().ToHashSet();
            int[] memberTree = ((IEnumerable)Get<object>(level, "MemberTree")).Cast<int>().ToArray();
            int[] byTree = Enumerable.Repeat(-1, treeCount).ToArray();
            for (int m = 0; m < members.Length; m++)
            {
                int t = memberTree[m];
                if (byTree[t] < 0 && feet.Contains(members[m].Lower))
                    byTree[t] = members[m].Lower;
            }
            return byTree;
        }

        // ---- Mirrored feet (spec 6). Eleven notches, span ten, rise 2.5:
        // the across pulls mirrored in shape and leaning outward, the LEFT
        // flank scaled by 1.1, and every notch skewed one degree along the
        // chord. Spec 3.4 mirrors the resultants about the span's midpoint
        // before a single foot is placed, so the scale and the skew both go:
        // the along-chord parts of a pair are made equal and opposite, its
        // across and down parts equal, and the centre tree stands plumb.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int m = trees.Length;
            if (m != 9)
                throw new InvalidOperationException($"Eleven notches anchored at both ends hold nine trees at Branching 1; got {m}.");
            int[] footNode = FootOfTree(built, m);
            const double midpoint = 5.0;
            for (int i = 0; i < m / 2; i++)
            {
                double left = X(nodes[footNode[i]]);
                double right = X(nodes[footNode[m - 1 - i]]);
                if (Math.Abs((left + right) - (2.0 * midpoint)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Trees {i} and {m - 1 - i} are a mirrored pair and their feet straddle the span's midpoint: "
                        + $"{left:0.#########} and {right:0.#########} sum to {left + right:0.#########}, not {2.0 * midpoint:0.#}. "
                        + "The feet are following each tree's RAW resultant, which the along-chord skew tilts the same way on both flanks.");
                }
            }
            double centre = X(nodes[footNode[m / 2]]);
            if (Math.Abs(centre - midpoint) > 1.0e-9)
                throw new InvalidOperationException($"The centre tree stands outside the pairing and its foot is ON the midpoint; it is at {centre:0.#########}.");
            if (Get<int>(built, "Banded") != 0)
                throw new InvalidOperationException($"Type 0 cuts no bands at all, so no tree is handed one; Banded is {Get<int>(built, "Banded")}.");
            int[] memberTree = ((IEnumerable)Get<object>(built, "MemberTree")).Cast<int>().ToArray();
            (int Lower, int Upper)[] members = MembersOf(built);
            for (int k = 0; k < members.Length; k++)
            {
                if (memberTree[k] != m / 2)
                    continue;
                object a = nodes[members[k].Lower];
                object b = nodes[members[k].Upper];
                double lean = AngleDeg(
                    X(b) - X(a), Y(b) - Y(a), Z(b) - Z(a), 0.0, 0.0, 1.0);
                if (lean > 1.0e-9)
                    throw new InvalidOperationException($"The centre tree's along-chord pull is mirrored away, so its member stands vertical; it leans {lean:0.######} degrees.");
            }
            double moved = Get<double>(placed, "AsymmetryRemoved");
            // Not "more than zero": every notch of this arch carries a one
            // degree along-chord skew that the mirror rule takes off the
            // centre tree entirely, so the angle removed is at least a whole
            // degree. Against a bare `> 0` an implementation that moved an aim
            // by a millionth of a degree, or that reported floating-point
            // noise, would pass.
            if (moved <= 0.5)
                throw new InvalidOperationException($"Symmetrise reports the largest angle it moved an aim through, and the one degree skew on every notch of this arch puts that above half a degree; it reported {moved:0.######}.");
            int[] partner = Get<int[]>(placed, "Partner");
            for (int i = 0; i < m; i++)
            {
                int expected = i == m / 2 ? m / 2 : m - 1 - i;
                if (partner[i] != expected)
                {
                    throw new InvalidOperationException(
                        $"Tree {i} must pair with its mirror partner about the span's midpoint, {expected} (the centre tree {m / 2} is its own partner); "
                        + $"Partner[{i}] is {partner[i]}.");
                }
            }
            int families = Get<int>(placed, "Families");
            if (families != 1)
                throw new InvalidOperationException($"One span holding trees falls into one family; Families is {families}.");
            int centreTrees = Get<int>(placed, "CentreTrees");
            if (centreTrees != 1)
                throw new InvalidOperationException($"Eleven notches at Branching 1 give one centre tree, its own partner; CentreTrees is {centreTrees}.");
        }

        // ---- Idempotent (spec 3.4, Minor 4). Symmetrise runs once inside
        // Place, but Tasks 2 and 3 edit the code around that call site, so a
        // second call on the SAME Placement must be a no-op: it would
        // otherwise overwrite RawResultant with the already-symmetrised
        // vector and report the asymmetry removed as zero.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            double firstMoved = Get<double>(placed, "AsymmetryRemoved");
            var beforeResultant = trees.Select(t => Get<object>(t, "Resultant")).ToArray();
            var beforeRaw = trees.Select(t => Get<object>(t, "RawResultant")).ToArray();
            double secondMoved = (double)symmetrise.Invoke(null, new object?[] { placed, arch.Nodes, arch.Bars })!;
            if (Math.Abs(secondMoved - firstMoved) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"A second Symmetrise call on the same Placement must be a no-op and report the same asymmetry removed; "
                    + $"the first call reported {firstMoved:0.######}, the second {secondMoved:0.######}.");
            }
            for (int t = 0; t < trees.Length; t++)
            {
                object raw = Get<object>(trees[t], "RawResultant");
                if (Math.Abs(VX(raw) - VX(beforeRaw[t])) > 1.0e-12 ||
                    Math.Abs(VY(raw) - VY(beforeRaw[t])) > 1.0e-12 ||
                    Math.Abs(VZ(raw) - VZ(beforeRaw[t])) > 1.0e-12)
                {
                    throw new InvalidOperationException(
                        $"A second Symmetrise call must not overwrite RawResultant with the already-symmetrised vector; tree {t}'s raw resultant moved from "
                        + $"({VX(beforeRaw[t]):0.#########}, {VY(beforeRaw[t]):0.#########}, {VZ(beforeRaw[t]):0.#########}) to "
                        + $"({VX(raw):0.#########}, {VY(raw):0.#########}, {VZ(raw):0.#########}).");
                }
                object resultant = Get<object>(trees[t], "Resultant");
                if (Math.Abs(VX(resultant) - VX(beforeResultant[t])) > 1.0e-12 ||
                    Math.Abs(VY(resultant) - VY(beforeResultant[t])) > 1.0e-12 ||
                    Math.Abs(VZ(resultant) - VZ(beforeResultant[t])) > 1.0e-12)
                {
                    throw new InvalidOperationException($"A second Symmetrise call must not change Resultant; tree {t}'s symmetrised resultant moved.");
                }
            }
        }

        // ---- Dead band, measured (spec 3.4, Minor 2). A one-degree
        // across-chord pull on a mirrored pair of notches: the pair step
        // leaves both members' across at tan(1 degree) unchanged (across is
        // already equal for the pair) and along at zero, so the one-degree
        // residual lean is real, not a byproduct of a centre tree's along
        // being zeroed by the mirror rule. One degree is inside
        // PlumbDegrees (2), so each foot must land exactly under its own
        // main notch in plan.
        {
            const double lean1 = 0.0174550649282176;   // tan(1 degree)
            Array nodes = Array.CreateInstance(point3d, 4);
            Array acrossBar = Array.CreateInstance(vector3d, 4);
            nodes.SetValue(P(0.0, 0.0, 0.0), 0);
            nodes.SetValue(P(1.0, 0.0, 1.0), 1);
            nodes.SetValue(P(2.0, 0.0, 1.0), 2);
            nodes.SetValue(P(3.0, 0.0, 0.0), 3);
            acrossBar.SetValue(V(0.0, 0.0, 0.0), 0);
            acrossBar.SetValue(V(0.0, lean1, -1.0), 1);
            acrossBar.SetValue(V(0.0, lean1, -1.0), 2);
            acrossBar.SetValue(V(0.0, 0.0, 0.0), 3);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            var band = (nodes, new[] { new[] { 0, 1, 2, 3 } }, new[] { 0, 3 }, across, Array.Empty<(int, int)>());
            object placed = Run(band, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 2)
                throw new InvalidOperationException($"Four notches anchored at both ends hold two trees at Branching 1; got {trees.Length}.");
            int[] footNode = FootOfTree(built, trees.Length);
            for (int t = 0; t < trees.Length; t++)
            {
                int mainNode = Get<int[]>(trees[t], "Nodes")[0];
                object main = nodes.GetValue(mainNode)!;
                object foot = levelNodes[footNode[t]];
                if (Math.Abs(X(foot) - X(main)) > 1.0e-9 || Math.Abs(Y(foot) - Y(main)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Tree {t}'s one-degree residual lean is inside PlumbDegrees and must read as plumb, so its foot stands exactly under its main notch in plan: "
                        + $"foot ({X(foot):0.#########}, {Y(foot):0.#########}) against notch ({X(main):0.#########}, {Y(main):0.#########}).");
                }
            }
        }

        // ---- One family (spec 6). The same arch four times, offset in Y by
        // 0, 1, 2 and 3, the second with every pull scaled by 1.05, the third
        // with its nodes in REVERSED bar order, and the fourth turned through
        // 180 degrees in plan with its pull turned with it. A family is the
        // spans alike in free-notch count and in chord length (Branching is
        // one slider, so the tree count and layout follow), and it shares the
        // ALONG and DOWN profiles at each index while every span keeps its own
        // ACROSS. Every principal line of a family therefore carries the same
        // columns in its own frame.
        {
            const double skew = 0.0174550649282176;
            // A uniform across-chord pull, the same on every notch of every
            // bar: a wind load, not a mirrored shape.
            //
            // The backwards bar and the rotated bar now hold TRIVIALLY, and
            // that is the point of the rule they are here for. A family
            // shares `along` and `down` only. After each span's own pair step
            // `along` is antisymmetric and `down` symmetric, so reading a span
            // from either end gives the same `along[i]` and `down[i]`, and
            // tree i of one span is tree i of the family whichever way the bar
            // was traced. `across` is the one that comes out negated, and it
            // is never shared: each span keeps its own, already mirrored
            // within itself by the pair step, so it is rebuilt against that
            // span's own normal and lands back in the world where the net put
            // it. Congruence by translation and congruence by rotation both
            // hold by construction, with no rule left to get wrong.
            //
            // What these four bars still measure is that the SHARED profiles
            // land at the right index (a wrong index mapping would put a
            // flank tree's along on the other flank, which the offsets check
            // below would see) and that each span's own across survives into
            // the world unchanged. The case that distinguishes sharing across
            // from not sharing it is the crown bar below; this one does not,
            // because all four of these bars carry the same across.
            const double lateral = 0.3;
            const int count = 11;
            const int barCount = 4;
            Array nodes = Array.CreateInstance(point3d, barCount * count);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), barCount);
            var bars = new int[barCount][];
            var anchors = new List<int>();
            double middle = (count - 1) / 2.0;
            for (int b = 0; b < barCount; b++)
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    int node = (b * count) + i;
                    // Bar 3 is bar 0 rotated 180 degrees in plan about
                    // (5, 1.5), the point halfway between the two bars on the
                    // arch's own plan centreline: its plan x runs backwards
                    // while its node ORDER does not, so its chord is
                    // antiparallel to the lead's, and its pull is turned with
                    // it, both plan components negated. In its own frame it is
                    // bar 0 exactly, notch for notch.
                    double x = b == 3 ? 10.0 - (10.0 * s) : 10.0 * s;
                    nodes.SetValue(P(x, b, 2.5 * 4.0 * s * (1.0 - s)), node);
                    double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                    double flank = i < middle ? 1.1 : 1.0;
                    double scale = flank * (b == 1 ? 1.05 : 1.0);
                    double turn = b == 3 ? -1.0 : 1.0;
                    // Bar 2 is traced from its far end: bar position k holds
                    // the node at count-1-k, and the pull at that POSITION is
                    // the pull that node carries.
                    int position = b == 2 ? count - 1 - i : i;
                    bar[position] = node;
                    acrossBar.SetValue(
                        V(turn * scale * ((side * 0.25) + skew), turn * lateral, -scale),
                        position);
                }
                bars[b] = bar;
                across.SetValue(acrossBar, b);
                anchors.Add(b * count);
                anchors.Add((b * count) + count - 1);
            }
            var family = (nodes, bars, anchors.ToArray(), across, Array.Empty<(int, int)>());
            object placed = Run(family, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != barCount)
                throw new InvalidOperationException($"Four bars anchored at both ends give four spans; got {spans.Length}.");
            int[] footNode = FootOfTree(built, trees.Length);
            // What each span's OWN frame must read once the family has been
            // averaged, derived by hand rather than recomputed from the rule
            // under test. A span's across is its own and is never shared, so
            // it reads the world-frame lateral pull with the sign its own
            // trace gives it: bars 0 and 1 are traced along +x with the pull
            // to +y, so +lateral; bar 2 is the same physical line traced
            // backwards, so its own normal points the other way and it reads
            // -lateral; bar 3 is bar 0 turned through 180 degrees with its
            // pull turned too, so its chord AND its normal are both reversed
            // and it reads +lateral again. All four therefore stand in the
            // same place in the world, which is what the offsets check below
            // says in the spans' own frames.
            double[] expectedOwnAcross = { lateral, lateral, -lateral, lateral };
            var offsets = new List<(double Along, double Across)>[spans.Length];
            var readsNegative = new bool[spans.Length];
            for (int s = 0; s < spans.Length; s++)
            {
                object span = spans[s];
                int[] bar = bars[Get<int>(span, "Bar")];
                object first = nodes.GetValue(bar[Get<int>(span, "First")])!;
                object last = nodes.GetValue(bar[Get<int>(span, "Last")])!;
                double cx = X(last) - X(first);
                double cy = Y(last) - Y(first);
                double length = Math.Sqrt((cx * cx) + (cy * cy));
                cx /= length;
                cy /= length;
                double midX = 0.5 * (X(first) + X(last));
                double midY = 0.5 * (Y(first) + Y(last));
                double expectedAcross = expectedOwnAcross[s];
                readsNegative[s] = expectedAcross < 0.0;
                offsets[s] = new List<(double Along, double Across)>();
                for (int t = 0; t < trees.Length; t++)
                {
                    if (Get<int>(trees[t], "Span") != s)
                        continue;
                    object foot = levelNodes[footNode[t]];
                    double dx = X(foot) - midX;
                    double dy = Y(foot) - midY;
                    offsets[s].Add(((dx * cx) + (dy * cy), (dx * -cy) + (dy * cx)));

                    // The value itself, not just cross-span agreement: each
                    // span keeps the WHOLE across-chord pull its own net hands
                    // it, so a span's own frame (R.n with n = (-c.y, c.x), the
                    // production sign convention) reads the hand-derived value
                    // above. Any rule that pooled across over the family would
                    // have to decide which way round each span was, and would
                    // shrink or flip these four readings the moment one bar's
                    // own reading disagreed with another's.
                    object resultant = Get<object>(trees[t], "Resultant");
                    double acrossForce = (VX(resultant) * -cy) + (VY(resultant) * cx);
                    if (Math.Abs(acrossForce - expectedAcross) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"Every tree of a family keeps its own span's across-chord pull whole: span {s} "
                            + $"({(readsNegative[s] ? "reading negative" : "reading positive")}) reads {acrossForce:0.#########}, not {expectedAcross:0.#}.");
                    }
                }
            }
            for (int s = 1; s < spans.Length; s++)
            {
                if (offsets[s].Count != offsets[0].Count)
                    throw new InvalidOperationException($"Every span of a family holds the same trees; span {s} holds {offsets[s].Count} against {offsets[0].Count}.");
                // Along is antisymmetric within a pair by construction (the
                // mirror rule takes the pair's DIFFERENCE), so reading a span
                // from either end gives the same own-frame Along and the
                // shared profile lands at the same index on every bar. Across
                // is the span's own, so a bar whose own frame reads the world
                // pull negative stands at the NEGATIVE own-frame offset,
                // which is the same place in the world.
                double sign = readsNegative[s] ? -1.0 : 1.0;
                for (int i = 0; i < offsets[0].Count; i++)
                {
                    double expectedAcross = sign * offsets[0][i].Across;
                    if (Math.Abs(offsets[s][i].Along - offsets[0][i].Along) > 1.0e-9 ||
                        Math.Abs(offsets[s][i].Across - expectedAcross) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"Foot {i} of span {s}, read in its OWN frame, stands where foot {i} of the family's first span stands (Across negated where "
                            + $"that span's own frame reads the world pull negative): ({offsets[s][i].Along:0.#########}, {offsets[s][i].Across:0.#########}) "
                            + $"against ({offsets[0][i].Along:0.#########}, {expectedAcross:0.#########}). The shared along profile is landing at the wrong "
                            + "index, or a span is being read in the world's frame rather than its own.");
                    }
                }
            }

            // The same family at Type 2. Everything above runs at Type 0, so
            // the BAND path had never been driven on a span traced backwards
            // or on one turned through 180 degrees at all: the member of each
            // mirror pair with the smaller chord parameter takes the band its
            // main projects into and its partner takes the mirrored one, and
            // on these spans that parameter rises with the grouping order
            // whichever way the bar was traced, so what is measured here is
            // that the bands come out mirrored in each span's OWN frame, not
            // that the parameter is read in preference to the index.
            //
            // Nine trees at Branching 1: four mirror pairs into two bands, and
            // the centre tree, which has no central band at an even Type,
            // standing on its own foot on the mirror plane. Three feet per
            // span, twelve in all.
            {
                object banded = Run(family, Array.Empty<int[]>(), 1.0, 1, 2);
                object bandedBuilt = Get<object>(banded, "Built");
                var bandedNodes = ((IEnumerable)Get<object>(bandedBuilt, "Nodes")).Cast<object>().ToArray();
                var bandedTrees = ((IEnumerable)Get<object>(banded, "Trees")).Cast<object>().ToArray();
                var bandedSpans = ((IEnumerable)Get<object>(banded, "Spans")).Cast<object>().ToArray();
                if (Get<int>(bandedBuilt, "Peeled") != 0)
                    throw new InvalidOperationException($"Every trunk reaches its band foot here, the outermost leaning 59 degrees; {Get<int>(bandedBuilt, "Peeled")} peeled.");
                var bandedFeet = ((IEnumerable)Get<object>(bandedBuilt, "Feet")).Cast<int>().ToArray();
                if (bandedFeet.Length != 12)
                    throw new InvalidOperationException($"Two band feet and one centre foot on each of four spans is twelve; {bandedFeet.Length} built.");
                int[] bandedFoot = FootOfTree(bandedBuilt, bandedTrees.Length);
                for (int s = 0; s < bandedSpans.Length; s++)
                {
                    int[] bar = bars[Get<int>(bandedSpans[s], "Bar")];
                    int[] own = Enumerable.Range(0, bandedTrees.Length)
                        .Where(t => Get<int>(bandedTrees[t], "Span") == s).ToArray();
                    int m = own.Length;
                    for (int i = 0; i < m / 2; i++)
                    {
                        (double Along, double Across) low = InSpanFrame(
                            nodes, bar, bandedSpans[s], bandedNodes[bandedFoot[own[i]]]);
                        (double Along, double Across) high = InSpanFrame(
                            nodes, bar, bandedSpans[s], bandedNodes[bandedFoot[own[m - 1 - i]]]);
                        if (Math.Abs(low.Along + high.Along) > 1.0e-9 ||
                            Math.Abs(low.Across - high.Across) > 1.0e-9)
                        {
                            throw new InvalidOperationException(
                                $"Trees {i} and {m - 1 - i} of span {s} are a mirror pair, so their band feet are mirror images about that span's own "
                                + $"midpoint: equal and opposite along the chord, equal across it. They stand at ({low.Along:0.#########}, "
                                + $"{low.Across:0.#########}) and ({high.Along:0.#########}, {high.Across:0.#########}).");
                        }
                    }
                    (double Along, double Across) centre = InSpanFrame(
                        nodes, bar, bandedSpans[s], bandedNodes[bandedFoot[own[m / 2]]]);
                    if (Math.Abs(centre.Along) > 1.0e-9)
                        throw new InvalidOperationException($"The centre tree of span {s} stands in the mirror plane, no distance along the chord from the midpoint; it stands {centre.Along:0.#########} along.");
                }
            }
        }

        // ---- A rib in the structure's own mirror plane does not lean
        // (spec 3.4, amended). Three congruent bars, ten wide and 2.5 up, at
        // y = -2, 0 and +2: one family, since they hold nine free notches
        // each on chords of equal length. Every notch is pulled OUTWARD along
        // its own chord, by 0.2 on the flanks and 0.5 on the crown, and the
        // two flank bars are also pulled sideways toward the middle of the
        // structure, by +0.5 and -0.5. The CROWN bar lies in the structure's
        // own mirror plane, is pulled equally from both sides, and has no
        // across-chord pull at all.
        //
        // A family shares the ALONG and DOWN profiles and nothing else, so
        // every tree of every bar comes out with
        //
        //     along  = side x (0.2 + 0.5 + 0.2)/3 = side x 0.3
        //     down   = -(1.0 + 1.2 + 1.0)/3       = -16/15
        //     across = its own span's: +0.5, 0, -0.5
        //
        // and a Type 0 foot stands (along / |down|) x z along the chord from
        // its main notch and (across / |down|) x z across it:
        //
        //     along offset  = side x 0.3 x 15/16 x z = side x 0.28125 z
        //     across offset = +0.46875 z, 0, -0.46875 z
        //
        // The crown bar's feet therefore stand exactly under their own notches
        // ACROSS the chord, and its centre tree, which has no along pull
        // either, stands plumb.
        //
        // Sharing the across profile across the family cannot do that. It
        // needs a rule for which way round each span is, and every such rule
        // has a null exactly here: the crown's own mean across is zero, so it
        // has no opinion, and whatever the rule falls back on is the order
        // Pattern happened to trace the curve in. Under the frame each span
        // oriented for itself, the two flanks read +0.5 and -0.5 in their own
        // frames, the second is turned round to agree, the family mean comes
        // out 1/3, and the crown is handed it: 0.3125 z out of the plane it
        // lies in, to whichever side its node order picked, and to the other
        // side if the same curve were drawn the other way.
        {
            const int count = 11;
            const int barCount = 3;
            double[] barY = { -2.0, 0.0, 2.0 };
            double[] barAcross = { 0.5, 0.0, -0.5 };
            double[] barBend = { 0.2, 0.5, 0.2 };
            double[] barDown = { 1.0, 1.2, 1.0 };
            const double sharedBend = 0.3;          // (0.2 + 0.5 + 0.2) / 3
            const double sharedDown = 16.0 / 15.0;  // (1.0 + 1.2 + 1.0) / 3
            Array nodes = Array.CreateInstance(point3d, barCount * count);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), barCount);
            var bars = new int[barCount][];
            var anchors = new List<int>();
            double middle = (count - 1) / 2.0;
            for (int b = 0; b < barCount; b++)
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    int node = (b * count) + i;
                    nodes.SetValue(P(10.0 * s, barY[b], 2.5 * 4.0 * s * (1.0 - s)), node);
                    bar[i] = node;
                    double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                    acrossBar.SetValue(
                        V(side * barBend[b], barAcross[b], -barDown[b]), i);
                }
                bars[b] = bar;
                across.SetValue(acrossBar, b);
                anchors.Add(b * count);
                anchors.Add((b * count) + count - 1);
            }
            var ribs = (nodes, bars, anchors.ToArray(), across, Array.Empty<(int, int)>());
            object placed = Run(ribs, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (Get<int>(placed, "Families") != 1)
                throw new InvalidOperationException($"Three bars of nine notches on chords of equal length are ONE family, or this fixture is not measuring what a family does; Families is {Get<int>(placed, "Families")}.");
            if (Get<int>(placed, "AsymmetricSpans") != 0)
                throw new InvalidOperationException($"Every one of these spans is symmetric about its own midpoint; {Get<int>(placed, "AsymmetricSpans")} were placed unmirrored.");
            int[] footNode = FootOfTree(built, trees.Length);
            // The crown first, because it is the whole case: a bar in the
            // structure's own mirror plane, pulled equally from both sides,
            // stands in that plane.
            for (int t = 0; t < trees.Length; t++)
            {
                if (Get<int>(trees[t], "Span") != 1)
                    continue;
                object crownMain = nodes.GetValue(Get<int[]>(trees[t], "Nodes")[0])!;
                object crownFoot = levelNodes[footNode[t]];
                if (Math.Abs(Y(crownFoot) - Y(crownMain)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"The crown bar lies in the structure's own mirror plane and is pulled equally from both sides, so its feet stand "
                        + $"exactly under their notches ACROSS the chord; tree {t} stands {Y(crownFoot) - Y(crownMain):0.#########} off, which is a lean "
                        + "out of that plane, to the side its node order picked. The family is sharing an across profile that belongs to "
                        + "each span alone.");
                }
            }
            for (int t = 0; t < trees.Length; t++)
            {
                int b = Get<int>(trees[t], "Span");
                object main = nodes.GetValue(Get<int[]>(trees[t], "Nodes")[0])!;
                double side = X(main) < 5.0 ? -1.0 : (X(main) > 5.0 ? 1.0 : 0.0);
                double z = Z(main);
                object resultant = Get<object>(trees[t], "Resultant");
                if (Math.Abs(VX(resultant) - (side * sharedBend)) > 1.0e-9 ||
                    Math.Abs(VY(resultant) - barAcross[b]) > 1.0e-9 ||
                    Math.Abs(VZ(resultant) + sharedDown) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"A family shares ALONG and DOWN and leaves ACROSS alone, so tree {t} of bar {b} carries "
                        + $"({side * sharedBend:0.#########}, {barAcross[b]:0.#########}, {-sharedDown:0.#########}); it carries "
                        + $"({VX(resultant):0.#########}, {VY(resultant):0.#########}, {VZ(resultant):0.#########}).");
                }
                object foot = levelNodes[footNode[t]];
                double expectedX = X(main) + (side * sharedBend / sharedDown * z);
                double expectedY = Y(main) + (barAcross[b] / sharedDown * z);
                if (Math.Abs(X(foot) - expectedX) > 1.0e-9 || Math.Abs(Y(foot) - expectedY) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Tree {t} of bar {b} stands at ({expectedX:0.#########}, {expectedY:0.#########}); it stands at "
                        + $"({X(foot):0.#########}, {Y(foot):0.#########}).");
                }
            }
        }

        // ---- The guard's other half (spec 3.4). The case above measures that
        // a second Symmetrise on the same trees is a no-op; this one measures
        // that a call after a tree has been ADDED runs again, which is what
        // keys the guard on the tree count as well as the flag. Without it the
        // new tree would stand on the raw aim it came in with while every
        // other tree stood on a symmetrised one, in silence.
        //
        // The added tree holds the arch's CENTRE notch, so the span's free
        // notch parameters stay symmetric about the midpoint (0.5 is its own
        // partner, twice over) and the span goes from nine trees with a centre
        // to ten trees in five pairs: CentreTrees falls from 1 to 0, and
        // Partner is rebuilt ten long.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            if (Get<int>(placed, "CentreTrees") != 1 || Get<int[]>(placed, "Partner").Length != 9)
                throw new InvalidOperationException("Eleven notches at Branching 1 hold nine trees, the middle one its own partner.");
            Type treeType = engine.GetNestedType("Tree", BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException("ColumnPlacement has no Tree.");
            object extra = Activator.CreateInstance(treeType)!;
            treeType.GetField("Bar")!.SetValue(extra, 0);
            treeType.GetField("Span")!.SetValue(extra, 0);
            treeType.GetField("Nodes")!.SetValue(extra, new[] { 5 });
            treeType.GetField("Load")!.SetValue(extra, new[] { 1.0 });
            treeType.GetField("Resultant")!.SetValue(extra, V(0.4, 0.0, -1.0));
            object treeList = Get<object>(placed, "Trees");
            treeList.GetType().GetMethod("Add")!.Invoke(treeList, new[] { extra });
            symmetrise.Invoke(null, new object?[] { placed, arch.Nodes, arch.Bars });
            int[] partner = Get<int[]>(placed, "Partner");
            if (partner.Length != 10)
                throw new InvalidOperationException($"A Placement that gained a tree is symmetrised again, so Partner is rebuilt for every tree it now holds; it is {partner.Length} long against 10 trees.");
            if (Get<int>(placed, "CentreTrees") != 0)
                throw new InvalidOperationException($"Ten trees on one span pair off completely, so no tree is its own partner; CentreTrees is {Get<int>(placed, "CentreTrees")}, which is the count from before the tree was added.");
            object addedRaw = Get<object>(extra, "RawResultant");
            if (Math.Abs(VX(addedRaw) - 0.4) > 1.0e-12 ||
                Math.Abs(VY(addedRaw)) > 1.0e-12 ||
                Math.Abs(VZ(addedRaw) + 1.0) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"The added tree's raw resultant is captured by the re-run, so it reads (0.4, 0, -1); it reads "
                    + $"({VX(addedRaw):0.#########}, {VY(addedRaw):0.#########}, {VZ(addedRaw):0.#########}), which is what a guard "
                    + "keyed on the flag alone leaves behind.");
            }
        }

        // ---- A family is not a notch count (spec 3.4, amended). Two spans
        // of nine free notches each: one ten wide and shallow whose pulls
        // lean hard OUTWARD along the chord, one three wide and three high
        // whose pulls hang straight down and ask for plumb columns. Keyed on
        // the notch count alone they are ONE family, and the short span takes
        // the mean of the two: its outermost tree's along-chord pull becomes
        // -1 against a down of -1, an aim 45 degrees outward, and its notch
        // 1.08 above the ground puts its foot at x = 0.3 - 1.08 = -0.78,
        // three quarters of a metre BEYOND its own anchor. Chord length is in
        // the key, within a tenth of the family lead's, and 3 is not within a
        // tenth of 10, so they are two families and the short span keeps the
        // plumb aims its own net asked for.
        {
            const int count = 11;
            Array nodes = Array.CreateInstance(point3d, 2 * count);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            var bars = new int[2][];
            var anchors = new List<int>();
            double middle = (count - 1) / 2.0;
            for (int b = 0; b < 2; b++)
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                double width = b == 0 ? 10.0 : 3.0;
                double rise = b == 0 ? 2.5 : 3.0;
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    int node = (b * count) + i;
                    nodes.SetValue(P(width * s, 5.0 * b, rise * 4.0 * s * (1.0 - s)), node);
                    bar[i] = node;
                    double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                    acrossBar.SetValue(V(b == 0 ? side * 2.0 : 0.0, 0.0, -1.0), i);
                }
                bars[b] = bar;
                across.SetValue(acrossBar, b);
                anchors.Add(b * count);
                anchors.Add((b * count) + count - 1);
            }
            var unlike = (nodes, bars, anchors.ToArray(), across, Array.Empty<(int, int)>());
            object placed = Run(unlike, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int families = Get<int>(placed, "Families");
            if (families != 2)
                throw new InvalidOperationException($"A ten metre span and a three metre one holding nine notches each are TWO families, however many notches they share; Families is {families}.");
            int[] footNode = FootOfTree(built, trees.Length);
            for (int t = 0; t < trees.Length; t++)
            {
                if (Get<int>(trees[t], "Span") != 1)
                    continue;
                object main = nodes.GetValue(Get<int[]>(trees[t], "Nodes")[0])!;
                object foot = levelNodes[footNode[t]];
                double parameter = X(foot) / 3.0;
                if (parameter < -1.0e-9 || parameter > 1.0 + 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"The short span's feet stand within its own chord, parameter 0 to 1; tree {t} stands at {parameter:0.#########} "
                        + $"(x {X(foot):0.#########}). Keyed on the notch count alone it inherits the long span's outward pull and its "
                        + "outermost foot lands at -0.78, beyond its own anchor.");
                }
                if (Math.Abs(X(foot) - X(main)) > 1.0e-9 || Math.Abs(Y(foot) - Y(main)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"The short span's net hangs its notches straight down, so each of its trees stands PLUMB under its own main notch: "
                        + $"foot ({X(foot):0.#########}, {Y(foot):0.#########}) against notch ({X(main):0.#########}, {Y(main):0.#########}).");
                }
            }
        }

        // ---- A span whose free notches are not symmetric is placed
        // UNMIRRORED (spec 3.4, amended). An eleven-notch arch crossed at its
        // position 3 by a second bar, which holds that notch because it is
        // the lower-indexed bar: the arch is left with free notches at chord
        // parameters 0.1, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8 and 0.9, where 0.7 has
        // no partner at 0.3. Index i and index m-1-i of that list are not
        // geometric mirrors, so pairing them would force equal and opposite
        // along-chord pulls onto trees that do not straddle the mirror plane,
        // and would merge a "pair" onto a midpoint that is not between them.
        // The arch therefore keeps every raw resultant it came in with, its
        // trees take Partner -1, and it is counted in AsymmetricSpans. The
        // crossing bar's own span, one notch at parameter 0.5 exactly, IS
        // symmetric and IS mirrored, which is why its along-chord pull of 0.3
        // comes back zeroed.
        {
            Array nodes = Array.CreateInstance(point3d, 13);
            for (int i = 0; i < 11; i++)
            {
                double s = i / 10.0;
                nodes.SetValue(P(10.0 * s, 0.0, 2.5 * 4.0 * s * (1.0 - s)), i);
            }
            nodes.SetValue(P(3.0, -2.0, 0.0), 11);
            nodes.SetValue(P(3.0, 2.0, 0.0), 12);
            Array crossBar = Array.CreateInstance(vector3d, 3);
            crossBar.SetValue(V(0.0, 0.0, 0.0), 0);
            crossBar.SetValue(V(0.0, 0.3, -1.0), 1);
            crossBar.SetValue(V(0.0, 0.0, 0.0), 2);
            Array archBar = Array.CreateInstance(vector3d, 11);
            for (int p = 0; p < 11; p++)
                archBar.SetValue(V(0.1 * p, 0.0, -1.0), p);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(crossBar, 0);
            across.SetValue(archBar, 1);
            var crossed = (nodes, new[] { new[] { 11, 3, 12 }, Enumerable.Range(0, 11).ToArray() },
                new[] { 0, 10, 11, 12 }, across, Array.Empty<(int, int)>());
            object placed = Run(crossed, Array.Empty<int[]>(), 1.0, 1, 2);
            if (Get<int>(placed, "GroundPlaced") != 2)
                throw new InvalidOperationException($"An unmirrored span is placed like any other, its bands read off each tree's own projection; it placed {Get<int>(placed, "GroundPlaced")}.");
            // The deviation against the bound, by hand. Eight free notches
            // remain on the arch, so the test allows a quarter of that span's
            // own spacing, 0.25 / 9 = 0.027778 in chord parameter. The pair
            // the crossing broke is (0.4, 0.7), which sums to 1.1: a deviation
            // of 0.1, outside the bound by a factor of 3.6. The bound scales
            // with the span and with nothing else, so this margin is the same
            // on a span of three metres and on one of thirty.
            const double crossedDeviation = 0.1;
            const double crossedBound = 0.25 / 9.0;
            if (crossedDeviation <= crossedBound)
                throw new InvalidOperationException($"This fixture only measures anything while the removed notch's deviation, {crossedDeviation:0.######}, is outside the quarter-spacing bound of {crossedBound:0.######}.");
            if (Get<int>(placed, "AsymmetricSpans") != 1)
                throw new InvalidOperationException($"One of the two spans lost an interior notch to the crossing, so a pair of its free notches sums to 1.1 rather than 1, a deviation of {crossedDeviation:0.######} against a bound of {crossedBound:0.######}; AsymmetricSpans is {Get<int>(placed, "AsymmetricSpans")}.");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 9)
                throw new InvalidOperationException($"One tree on the crossing bar and eight on the arch, whose ninth notch is the crossing itself; got {trees.Length}.");
            int[] partner = Get<int[]>(placed, "Partner");
            if (partner[0] != 0)
                throw new InvalidOperationException($"The crossing bar's single notch sits at parameter 0.5, so that span IS symmetric and its one tree is its own partner; Partner[0] is {partner[0]}.");
            object crossing = Get<object>(trees[0], "Resultant");
            if (Math.Abs(VX(crossing)) > 1.0e-9 || Math.Abs(VY(crossing)) > 1.0e-9 || Math.Abs(VZ(crossing) + 1.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"A symmetric span IS still mirrored: the crossing tree is its own partner, so its along-chord pull of 0.3 goes and it is left with (0, 0, -1); it reads "
                    + $"({VX(crossing):0.#########}, {VY(crossing):0.#########}, {VZ(crossing):0.#########}).");
            }
            for (int t = 1; t < trees.Length; t++)
            {
                if (partner[t] != -1)
                    throw new InvalidOperationException($"No tree of an unmirrored span has a mirror partner; Partner[{t}] is {partner[t]}.");
                object raw = Get<object>(trees[t], "RawResultant");
                object now = Get<object>(trees[t], "Resultant");
                if (Math.Abs(VX(now) - VX(raw)) > 1.0e-12 ||
                    Math.Abs(VY(now) - VY(raw)) > 1.0e-12 ||
                    Math.Abs(VZ(now) - VZ(raw)) > 1.0e-12)
                {
                    throw new InvalidOperationException(
                        $"An unmirrored span keeps its own aims: tree {t}'s resultant moved from ({VX(raw):0.#########}, {VY(raw):0.#########}, {VZ(raw):0.#########}) "
                        + $"to ({VX(now):0.#########}, {VY(now):0.#########}, {VZ(now):0.#########}). Its pulls ramp along the bar and are not mirrored in shape, so any pairing shows here.");
                }
            }
            // The same arch with nothing taken out of it is symmetric.
            object whole = Run(Arch(11, 10.0, 2.5, 1.0), Array.Empty<int[]>(), 1.0, 1, 2);
            if (Get<int>(whole, "AsymmetricSpans") != 0)
                throw new InvalidOperationException($"An arch anchored at both ends with every notch free IS symmetric; AsymmetricSpans is {Get<int>(whole, "AsymmetricSpans")}.");
        }

        // ---- A band foot is the plan CENTROID of its mains (spec 3.5,
        // amended), on the plan-curved bar at Type 2. Eight free notches, so
        // the four mirror pairs put trees 0 to 3 in band 0 (chord parameters
        // 1/9 to 4/9, every one under a half) and their partners 4 to 7 in
        // band 1. Band 0's mains stand at chord u = -3.5, -2.5, -1.5, -0.5
        // and across v = 64/81, 112/81, 144/81, 160/81, so its centroid is
        // u = -2, v = (480/81)/4 = 40/27, and band 1's is its exact mirror.
        // The centre of the axis-aligned bounding box, which is what stood
        // here, comes out at u = -2.0185, v = 1.4198 for band 0 against
        // u = 2, v = 1.3827 for band 1: not mirror images, on geometry that
        // is exactly symmetric, because a reflection about this chord is not
        // axis aligned and band 0's world X extreme falls on its second main
        // rather than on an end one.
        {
            var curved = PlanCurved(0.15);
            object placed = Run(curved, Array.Empty<int[]>(), 4.0, 1, 2);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (trees.Length != 8)
                throw new InvalidOperationException($"Ten nodes anchored at both ends hold eight trees at Branching 1; got {trees.Length}.");
            if (Get<int>(built, "Peeled") != 0)
                throw new InvalidOperationException($"Every trunk reaches its band foot here, the outermost leaning 54 degrees; {Get<int>(built, "Peeled")} peeled, so a band foot is in the wrong place.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 2)
                throw new InvalidOperationException($"Two bands, two feet, four unit steps apart; {feet.Length} built.");
            int[] footNode = FootOfTree(built, trees.Length);
            (double Along, double Across) low = InSpanFrame(curved.Nodes, curved.Bars[0], spans[0], levelNodes[footNode[0]]);
            (double Along, double Across) high = InSpanFrame(curved.Nodes, curved.Bars[0], spans[0], levelNodes[footNode[7]]);
            const double centroidAlong = 2.0;
            const double centroidAcross = 40.0 / 27.0;
            if (Math.Abs(low.Along + centroidAlong) > 1.0e-9 || Math.Abs(low.Across - centroidAcross) > 1.0e-9 ||
                Math.Abs(high.Along - centroidAlong) > 1.0e-9 || Math.Abs(high.Across - centroidAcross) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"A band's foot is the plan MEAN of its mains, so on this bar the two bands stand at chord (-2, {centroidAcross:0.#########}) and "
                    + $"(2, {centroidAcross:0.#########}), exact mirror images; they stand at ({low.Along:0.#########}, {low.Across:0.#########}) and "
                    + $"({high.Along:0.#########}, {high.Across:0.#########}). The centre of an axis-aligned bounding box does not commute with a mirror "
                    + "about a chord that runs along neither axis.");
            }
        }

        // ---- A centre pair merges onto the MEAN of its two feet (spec 3.5,
        // amended), on the same plan-curved bar at Type 0. The innermost
        // mirror pair's mains stand at chord u = -0.5 and 0.5, both across at
        // v = 160/81 and both 240/81 above the ground; the inward pull of
        // 0.15 to 1 runs each foot 0.15 x 240/81 = 4/9 toward the middle, to
        // u = -1/18 and 1/18, a gap of 1/9 inside a clearance of 0.2. Their
        // mean is chord (0, 160/81): on the mirror plane, and off the CHORD
        // midpoint (0, 0) by the plan sagitta at those notches, very nearly
        // two whole units. Merging onto the chord midpoint, which is what
        // stood here, moved both feet that far sideways, out from under the
        // bar, in the name of symmetry.
        {
            var curved = PlanCurved(0.15);
            object placed = Run(curved, Array.Empty<int[]>(), 4.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (Get<int>(built, "FeetMerged") != 1)
                throw new InvalidOperationException($"Exactly one mirrored pair lies inside the clearance here; {Get<int>(built, "FeetMerged")} merges reported.");
            int[] footNode = FootOfTree(built, trees.Length);
            if (footNode[3] != footNode[4])
                throw new InvalidOperationException("The innermost mirrored pair stands on ONE foot.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 7)
                throw new InvalidOperationException($"Eight trees on seven feet once the pair has merged; {feet.Length} built.");
            (double Along, double Across) merged = InSpanFrame(curved.Nodes, curved.Bars[0], spans[0], levelNodes[footNode[3]]);
            const double pairAcross = 160.0 / 81.0;
            if (Math.Abs(merged.Along) > 1.0e-9 || Math.Abs(merged.Across - pairAcross) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"A merged pair stands on the mean of its own two feet, chord (0, {pairAcross:0.#########}), which is on the mirror plane and NOT on the "
                    + $"chord midpoint (0, 0); it stands at ({merged.Along:0.#########}, {merged.Across:0.#########}). The clearance test bounds how far apart "
                    + "a pair's feet are ALONG the chord and says nothing at all about how far off it they sit.");
            }
        }

        // ---- The same plan-curved bar, crossed (spec 3.4). A second bar
        // holds its position-3 notch, so seven free notches remain at chord
        // parameters 1/9, 2/9, 4/9, 5/9, 6/9, 7/9, 8/9. Sorted and paired
        // across the midpoint, the middle pair is (4/9, 6/9), which sums to
        // 10/9: a deviation of 1/9 = 0.1111 against a bound of a quarter of
        // that span's own spacing, 0.25 / 8 = 0.03125. Outside by 3.6, so the
        // span is placed unmirrored, which is what a lost interior notch has
        // to do.
        //
        // This is the case the NET's median plan edge could not judge. These
        // fixtures run at a median of 4 on a chord of 9 whose notches are one
        // unit apart, which is a perfectly ordinary net with widely spaced
        // principal lines and fine notching along them; scaled by that, the
        // bound came out at 0.25 x 4 / 9 = 1/9, exactly the deviation, so this
        // removal sat on the boundary and its answer was decided by the last
        // bit of a division. The span's own spacing knows nothing about how
        // far apart the bars are.
        {
            var curved = PlanCurved(0.15);
            // Two anchors either side of the plan-curved bar's node 3, out
            // along the chord normal, so the crossing bar's own single notch
            // sits at parameter 0.5 and its span stays symmetric.
            double cx = 1.0 / Math.Sqrt(5.0);
            double cy = 2.0 / Math.Sqrt(5.0);
            object crossed = curved.Nodes.GetValue(3)!;
            Array nodes = Array.CreateInstance(point3d, 12);
            for (int i = 0; i < 10; i++)
                nodes.SetValue(curved.Nodes.GetValue(i)!, i);
            nodes.SetValue(P(X(crossed) + (2.0 * cy), Y(crossed) - (2.0 * cx), 0.0), 10);
            nodes.SetValue(P(X(crossed) - (2.0 * cy), Y(crossed) + (2.0 * cx), 0.0), 11);
            Array crossBar = Array.CreateInstance(vector3d, 3);
            crossBar.SetValue(V(0.0, 0.0, 0.0), 0);
            crossBar.SetValue(V(0.0, 0.0, -1.0), 1);
            crossBar.SetValue(V(0.0, 0.0, 0.0), 2);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(crossBar, 0);
            across.SetValue(((Array)curved.Across.GetValue(0)!), 1);
            var net = (nodes, new[] { new[] { 10, 3, 11 }, Enumerable.Range(0, 10).ToArray() },
                new[] { 0, 9, 10, 11 }, across, Array.Empty<(int, int)>());
            object placed = Run(net, Array.Empty<int[]>(), 4.0, 1, 0);
            const double removedDeviation = 1.0 / 9.0;
            const double removedBound = 0.25 / 8.0;
            if (removedDeviation <= removedBound)
                throw new InvalidOperationException($"This fixture only measures anything while the deviation {removedDeviation:0.######} is outside the bound {removedBound:0.######}.");
            if (Get<int>(placed, "AsymmetricSpans") != 1)
            {
                throw new InvalidOperationException(
                    $"The plan-curved bar lost an interior notch, so its free notches no longer straddle its midpoint: the middle pair sums to 10/9, a "
                    + $"deviation of {removedDeviation:0.######} against a bound of {removedBound:0.######}. AsymmetricSpans is "
                    + $"{Get<int>(placed, "AsymmetricSpans")}. Scaled by the NET's median plan edge, 4 on a chord of 9, the bound was 1/9: the same "
                    + "deviation exactly, so this span sat on the boundary.");
            }
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 8)
                throw new InvalidOperationException($"One tree on the crossing bar and seven on what is left of the plan-curved one; got {trees.Length}.");
            int[] partner = Get<int[]>(placed, "Partner");
            if (partner[0] != 0)
                throw new InvalidOperationException($"The crossing bar's one notch sits at parameter 0.5, so its span IS symmetric and its tree is its own partner; Partner[0] is {partner[0]}.");
            for (int t = 1; t < trees.Length; t++)
            {
                if (partner[t] != -1)
                    throw new InvalidOperationException($"No tree of an unmirrored span has a mirror partner; Partner[{t}] is {partner[t]}.");
            }
        }

        // ---- A band that loses trees to the peel rebuilds its foot from the
        // survivors (spec 3.5, amended), on the same bar at Type 1. All eight
        // trees take the one band, whose first foot is the centroid of all
        // eight mains, chord (0, 40/27). The two outermost trunks lean 71.6
        // degrees to it and peel onto their own feet; the six that stay would
        // then be standing on a foot two of whose eight mains have walked
        // away. Rebuilt from the six survivors it is chord (0, 832/486), a
        // fifth of a unit further across, and their worst lean falls to 50.6
        // degrees, so nothing else steps off.
        {
            var curved = PlanCurved(0.15);
            object placed = Run(curved, Array.Empty<int[]>(), 4.0, 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (Get<int>(built, "Peeled") != 2)
                throw new InvalidOperationException($"The outermost trunk on each flank leans 71.6 degrees to the shared foot and peels; {Get<int>(built, "Peeled")} peeled.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 3)
                throw new InvalidOperationException($"One band foot and two peeled feet is three; {feet.Length} built.");
            int[] footNode = FootOfTree(built, trees.Length);
            (double Along, double Across) band = InSpanFrame(curved.Nodes, curved.Bars[0], spans[0], levelNodes[footNode[3]]);
            const double survivorsAcross = 832.0 / 486.0;
            if (Math.Abs(band.Along) > 1.0e-9 || Math.Abs(band.Across - survivorsAcross) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"The band foot is the centroid of the trees still STANDING on it, chord (0, {survivorsAcross:0.#########}); it stands at "
                    + $"({band.Along:0.#########}, {band.Across:0.#########}). Built once from all eight mains and left there it would read "
                    + $"(0, {40.0 / 27.0:0.#########}), positioned in part by two trunks that have walked away.");
            }
        }

        // ---- Type 1 is PLACED, not refused (spec 3.5 and 3.7). The wide
        // arch, rise 2.5 on a span of ten: the flank trunks to a single
        // central foot would lean 77 and 62 degrees, past the 60 degree cap,
        // so those four trees step off onto their own feet and the level
        // stands. It used to be refused whole and fall back to Type 0, which
        // is what made the slider look dead.
        {
            var wide = Arch(11, 10.0, 2.5, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            if (Get<int>(placed, "GroundAsked") != 1 || Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"Type 1 asked is Type 1 placed; asked {Get<int>(placed, "GroundAsked")}, placed {Get<int>(placed, "GroundPlaced")}.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            if (tried.Length != 1)
                throw new InvalidOperationException($"Type N asked builds level N alone; {tried.Length} levels were built.");
            if (tried.Any(t => Get<string>(t, "Rule") == "lean"))
                throw new InvalidOperationException("No level can name lean any more: the peel holds every trunk inside the cap.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 4)
                throw new InvalidOperationException($"The two trunks on each flank lean 77 and 62 degrees to the central foot and peel; {Get<int>(built, "Peeled")} peeled.");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 5)
                throw new InvalidOperationException($"One band foot and four peeled feet is five; {feet.Length} built.");
            // Every one of the nine trees was HANDED a band here (Type 1 is
            // odd, so even the centre tree takes the central one), and Banded
            // counts them before the peel runs, which is what lets the
            // component tell "four trunks stepped off" from "nothing gathered
            // at all".
            if (Get<int>(built, "Banded") != 9)
                throw new InvalidOperationException($"At an odd Type every tree of the span takes a band, so all nine were banded before four of them peeled; Banded is {Get<int>(built, "Banded")}.");
            foreach ((int lower, int upper) in MembersOf(built))
            {
                if (!feet.Contains(lower))
                    continue;
                double lean = AngleDeg(
                    X(nodes[upper]) - X(nodes[lower]), Y(nodes[upper]) - Y(nodes[lower]), Z(nodes[upper]) - Z(nodes[lower]),
                    0.0, 0.0, 1.0);
                if (lean > maxLean + 1.0e-9)
                    throw new InvalidOperationException($"Every trunk stands inside the {maxLean:0} degree cap once the peel has run; one leans {lean:0.###}.");
            }
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, trees.Length);
            int shared = footNode[4];
            if (Math.Abs(X(nodes[shared]) - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"The band's foot stands on the plan centre of the main notches it carries, x = 5; it is at {X(nodes[shared]):0.#########}.");
            for (int t = 2; t <= 6; t++)
            {
                if (footNode[t] != shared)
                    throw new InvalidOperationException($"The five centre trees share the band foot; tree {t} stands on node {footNode[t]} against {shared}.");
            }
        }

        // ---- Type 2 on the same wide arch (spec 3.5, amended): the band is
        // decided PER MIRROR PAIR, so a pair lands in mirrored bands wherever
        // the boundaries fall. The centre notch of a uniform arch projects
        // EXACTLY onto the mirror plane, which at an even Type is a band
        // boundary: reading its own projection put it in the upper band, so
        // the two bands held four trees and five and their feet came out at
        // 2.5 and 7, unmirrored on a symmetric arch. It has no central band
        // to take, so it stands on its own Type 0 foot, which is on the
        // midpoint, and the two bands come out at 2.5 and 7.5.
        {
            var wide = Arch(11, 10.0, 2.5, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 2);
            if (Get<int>(placed, "GroundPlaced") != 2)
                throw new InvalidOperationException($"Type 2 asked is Type 2 placed; it placed {Get<int>(placed, "GroundPlaced")}.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 0)
                throw new InvalidOperationException($"Every trunk reaches its band foot here, the outermost leaning 59 degrees; {Get<int>(built, "Peeled")} peeled, so a band foot is in the wrong place.");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int m = trees.Length;
            int[] footNode = FootOfTree(built, m);
            for (int i = 0; i < m / 2; i++)
            {
                double left = X(nodes[footNode[i]]);
                double right = X(nodes[footNode[m - 1 - i]]);
                if (Math.Abs((left + right) - 10.0) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Trees {i} and {m - 1 - i} are a mirrored pair, so their BANDS are mirrored and their feet straddle the midpoint: "
                        + $"{left:0.#########} and {right:0.#########} sum to {left + right:0.#########}, not 10. "
                        + "A band read from each tree's own projection puts the centre notch, which sits exactly on the boundary, in the upper band.");
                }
            }
            double centre = X(nodes[footNode[m / 2]]);
            if (Math.Abs(centre - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"At an EVEN Type the centre tree has no central band and stands on its own foot, on the midpoint; it stands at {centre:0.#########}.");
            if (footNode[m / 2] == footNode[0] || footNode[m / 2] == footNode[m - 1])
                throw new InvalidOperationException("At an even Type the centre tree stands on its OWN foot, not on either band's.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 3)
                throw new InvalidOperationException($"Two band feet at 2.5 and 7.5 and the centre tree's own at 5 is three; {feet.Length} built.");
            if (Get<int>(built, "Banded") != 8)
                throw new InvalidOperationException($"At an EVEN Type the centre tree has no central band to take and stands on its own foot, so eight of the nine trees were banded; Banded is {Get<int>(built, "Banded")}.");
        }

        // ---- Neighbours stay apart (spec 3.5). A narrow bay, span four,
        // seven notches, the across pulls leaning INWARD hard enough that the
        // two feet either side of the centre land a fortieth of a unit from
        // it, inside a clearance of a thirtieth. Neither is a mirrored pair
        // with it, so nothing merges: five trees keep five feet and the close
        // pairs are counted instead. Welding them is what turned leaning
        // neighbours into accidental V's and X's on the review arch.
        {
            var bay = SkewArch(7, 4.0, 2.5, bend: -0.28875, skew: 0.0, flank: 1.0);
            object placed = Run(bay, Array.Empty<int[]>(), 2.0 / 3.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (trees.Length != 5)
                throw new InvalidOperationException($"Seven notches anchored at both ends hold five trees at Branching 1; got {trees.Length}.");
            if (feet.Length != trees.Length)
                throw new InvalidOperationException($"No two of these feet are a mirrored pair inside the clearance, so every tree keeps its own foot; {feet.Length} feet under {trees.Length} trees.");
            if (Get<int>(built, "FeetMerged") != 0)
                throw new InvalidOperationException($"Nothing merges here; {Get<int>(built, "FeetMerged")} merges reported.");
            if (Get<int>(built, "FeetClose") < 1)
                throw new InvalidOperationException("Feet that stand within the clearance and stay two are counted, so the author can raise Type or space the lines; none was.");
        }

        // ---- The centre pair merges (spec 3.5). Ten notches, an even count,
        // so there is no centre tree and the two innermost trees ARE a
        // mirrored pair. Node 4 is nudged two hundredths off the mirror, so
        // the pair's mains stand at x 3.98 and 5, both 2.469 above the ground,
        // and an inward pull of 0.2 to 1 runs each foot 0.494 toward the
        // middle: 4.4738 and 4.5062, a gap of 0.0323 inside a clearance of
        // 0.05 and far outside the weld epsilon. They stand on ONE foot at the
        // MEAN of the two, x = (3.98 + 5)/2 = 4.49 exactly, the two rise terms
        // cancelling. The span's chord MIDPOINT is 4.5, so a merge that snaps
        // a pair to the chord rather than to itself reads a hundredth out.
        //
        // The nudge is a fiftieth of the notch spacing, and the symmetry test
        // of 3.4 allows a quarter of it, so the span is still mirrored: a
        // solved net never puts its notches on the mirror to the last digit,
        // and a tolerance that demanded it would hand an ordinary arch back
        // its unmirrored placement.
        {
            var arch = SkewArch(10, 9.0, 2.5, bend: -0.2, skew: 0.0, flank: 1.0);
            object node4 = arch.Nodes.GetValue(4)!;
            arch.Nodes.SetValue(P(3.98, 0.0, Z(node4)), 4);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 8)
                throw new InvalidOperationException($"Ten notches anchored at both ends hold eight trees at Branching 1; got {trees.Length}.");
            if (Get<int>(built, "FeetMerged") != 1)
                throw new InvalidOperationException($"Exactly one mirrored pair lies inside the clearance here; {Get<int>(built, "FeetMerged")} merges reported.");
            int[] footNode = FootOfTree(built, trees.Length);
            if (footNode[3] != footNode[4])
                throw new InvalidOperationException("The innermost mirrored pair stands on ONE foot.");
            if (Get<int>(placed, "AsymmetricSpans") != 0)
                throw new InvalidOperationException($"A notch a fiftieth of the spacing off the mirror is still mirrored; the span was placed unmirrored, so the symmetry tolerance is tighter than a solved net can ever be.");
            if (Math.Abs(X(nodes[footNode[3]]) - 4.49) > 1.0e-9)
                throw new InvalidOperationException($"A merged pair stands on the MEAN of its own two feet, x = (4.4738 + 4.5062) / 2 = 4.49, and NOT on the span's chord midpoint of 4.5; it stands at {X(nodes[footNode[3]]):0.#########}.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 7)
                throw new InvalidOperationException($"Eight trees on seven feet once the pair has merged; {feet.Length} built.");
        }

        // ---- Fork on the segment, collinear. Rise five over eight: when
        // this arch is reused below at Ground 1 its outer trunks lean 54
        // degrees, inside the 60-degree cap, and alignment is judged at the
        // FOOT, where mirrored trunks sum to a vertical push. Judging each
        // trunk alone against its plumb aim refused this arch, and every
        // ordinary arch with it; the rise needed to pass that way was
        // fifteen, which is not an arch anyone builds.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 2, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var members = ((IEnumerable)Get<object>(built, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!, (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToHashSet();
            if (members.Any(m => Z(nodes[m.Item1]) > Z(nodes[m.Item2]) + 1.0e-9))
                throw new InvalidOperationException("Every member must leave the engine lower end first.");
            int forks = 0;
            foreach ((int lower, int upper) in members)
            {
                if (!feet.Contains(lower))
                    continue;
                // A trunk. Its upper end is a fork when something leaves it.
                var above = members.Where(m => m.Item1 == upper).ToArray();
                if (above.Length == 0)
                    continue;
                forks++;
                object foot = nodes[lower];
                object fork = nodes[upper];
                // The main branch is the one collinear with the trunk.
                double bestAngle = double.MaxValue;
                object? main = null;
                foreach ((int _, int notch) in above)
                {
                    double angle = AngleDeg(
                        X(fork) - X(foot), Y(fork) - Y(foot), Z(fork) - Z(foot),
                        X(nodes[notch]) - X(fork), Y(nodes[notch]) - Y(fork), Z(nodes[notch]) - Z(fork));
                    if (angle < bestAngle)
                    {
                        bestAngle = angle;
                        main = nodes[notch];
                    }
                }
                if (bestAngle > 0.5)
                    throw new InvalidOperationException($"Trunk and main branch must be collinear within 0.5 degrees; a fork kinks by {bestAngle:0.###}.");
                double expectedZ = Z(foot) + ((Z(main!) - Z(foot)) * forkFraction);
                if (Math.Abs(Z(fork) - expectedZ) > 1.0e-9)
                    throw new InvalidOperationException($"The fork must sit at {forkFraction:0.##} of the main notch height; it sits at z {Z(fork):0.###} against {expectedZ:0.###}.");
            }
            if (forks < 2)
                throw new InvalidOperationException($"Nine notches at Branching 2 must build forked trees; {forks} forks found.");
        }

        // ---- The same arch at Branching 3, where a tree holds a notch BELOW
        // 65% of its main notch's height. Group(7,3) gives {1,2,3} with main
        // 3 at z 4.6875, so the spec's fork height is z 3.047 while bar
        // position 1 sits at z 2.1875, under it. Two things must hold and
        // neither did: every member leaves the engine lower end first, and a
        // node that is only ever a lower end is a FOOT, so it stands on the
        // ground. The branch used to be emitted (fork, notch) with the notch
        // below, which made columns.lean read 90 degrees on the canvas, and
        // once the block sorted it by Z that held head became a foot in
        // mid-air for Deconstruct, Monitor and Animate alike.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 3, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var members = ((IEnumerable)Get<object>(built, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!, (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();
            if (members.Any(m => Z(nodes[m.Item1]) > Z(nodes[m.Item2]) + 1.0e-9))
                throw new InvalidOperationException("At Branching 3 a branch running down from the fork must still leave the engine lower end first.");
            var isLower = new bool[nodes.Length];
            var isUpper = new bool[nodes.Length];
            foreach ((int lower, int upper) in members)
            {
                isLower[lower] = true;
                isUpper[upper] = true;
            }
            for (int i = 0; i < nodes.Length; i++)
            {
                if (isLower[i] && !isUpper[i] && Z(nodes[i]) > 1.0e-9)
                    throw new InvalidOperationException($"A node that is only ever a lower end is read as a FOOT by the block; this one stands at z {Z(nodes[i]):0.###}, a column head turned into a foot in mid-air. The fork must sit below every notch it serves.");
            }
        }

        // ---- The shallow arch twelve wide, which USED to refuse Type 1 on
        // lean and fall back to Type 0. Three trunks on each flank pass the
        // cap to a foot at the span's centre and peel onto their own feet;
        // the level itself stands, and nothing names lean.
        {
            var wide = Arch(13, 12.0, 2.0, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            int asked = Get<int>(placed, "GroundAsked");
            int got = Get<int>(placed, "GroundPlaced");
            if (asked != 1 || got != 1)
                throw new InvalidOperationException($"A level is never refused now: Type 1 asked is Type 1 placed; asked {asked}, placed {got}.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 6)
                throw new InvalidOperationException($"The three trunks on each flank lean 83, 74 and 63 degrees to the central foot and peel; {Get<int>(built, "Peeled")} peeled.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object first = tried[0];
            if (Get<int>(first, "Ground") != 1 || Get<string>(first, "Rule") == "lean")
                throw new InvalidOperationException($"The level built is level 1 and it names no lean; it names '{Get<string>(first, "Rule")}'.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 7)
                throw new InvalidOperationException($"Six peeled feet and one band foot is seven; {feet.Length} built.");
        }

        // ---- The centred foot, odd and even counts.
        foreach (int count in new[] { 9, 8 })
        {
            var arch = Arch(count, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 1);
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"A rise-five arch eight wide holds one central foot: its outer trunks lean 54 degrees and the mirrored pairs sum to a vertical push at the foot; {count} notches fell back.");
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 1)
                throw new InvalidOperationException($"Ground 1 on one bar is one foot; {feet.Length} built with {count} notches.");
            double off = Math.Abs(X(nodes[feet[0]]) - 4.0);
            if (off > 0.08)
                throw new InvalidOperationException($"The one foot must stand on the span's plan centre within a hundredth of the span; it is {off:0.####} off with {count} notches. This is Param's off-centre foot, refused.");
        }

        // ---- A held ring: mid-bar anchors cut the bar and are never heads.
        // Anchors at 0, 3, 5 and 8 on nine notches leave three spans: 1..2,
        // the single notch 4 between two anchors, and 6..7.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            var held = (arch.Nodes, arch.Bars, new[] { 0, 3, 5, 8 }, arch.Across, arch.Edges);
            object placed = Run(held, Array.Empty<int[]>(), 1.0, 1, 0);
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 3)
                throw new InvalidOperationException($"Anchors at 0, 3, 5 and 8 cut a nine-notch bar into three spans; got {spans.Length}.");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var headNodes = trees.SelectMany(t => ((int[])Get<object>(t, "Nodes"))).ToArray();
            if (headNodes.Any(h => h == 0 || h == 3 || h == 5 || h == 8))
                throw new InvalidOperationException("An anchor is never a head.");
            if (headNodes.Length != 5)
                throw new InvalidOperationException($"Five free notches must all be held; {headNodes.Length} heads built.");
        }

        // ---- A free rim: two bars ending on an anchor-free loop.
        {
            // Bar 0 along +x from an anchor at x=-4 to a rim notch at x=-1;
            // bar 1 along +y from an anchor at y=-4 to a rim notch at y=-1.
            // The hole's rim is the loop {2, 5, 6}; node 6 is a spare rim node.
            Array nodes = Array.CreateInstance(point3d, 7);
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.5, 0.0, 2.0), 1);
            nodes.SetValue(P(-1.0, 0.0, 3.0), 2);
            nodes.SetValue(P(0.0, -4.0, 0.0), 3);
            nodes.SetValue(P(0.0, -2.5, 2.0), 4);
            nodes.SetValue(P(0.0, -1.0, 3.0), 5);
            nodes.SetValue(P(1.0, 1.0, 3.0), 6);
            Array acrossA = Array.CreateInstance(vector3d, 3);
            Array acrossB = Array.CreateInstance(vector3d, 3);
            for (int i = 0; i < 3; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2 }, new[] { 3, 4, 5 } }, new[] { 0, 3 }, across, new[] { (0, 1), (1, 2), (3, 4), (4, 5), (2, 6), (5, 6), (2, 5) });
            object placed = Run(net, new[] { new[] { 2, 5, 6 } }, 1.5, 1, 0);
            object? ring = Get<object?>(placed, "RingTree");
            if (ring is null)
                throw new InvalidOperationException("Two bars ending on an anchor-free rim must get a ring tree.");
            object foot = Get<object>(ring, "FixedFoot");
            if (Math.Abs(X(foot)) > 0.04 || Math.Abs(Y(foot)) > 0.04)
                throw new InvalidOperationException($"The ring foot is the plan intersection of the end tangents, the origin here within a hundredth of the span; it is at ({X(foot):0.###}, {Y(foot):0.###}).");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var allHeads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (allHeads.Count(h => h == 2) != 1 || allHeads.Count(h => h == 5) != 1)
                throw new InvalidOperationException("Each rim notch is held exactly once, by the ring tree.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Any(s => Get<string>(s, "LastKind") != "rim" && Get<string>(s, "FirstKind") != "rim"))
                throw new InvalidOperationException("Every span on these bars ends at the rim notch.");
        }

        // ---- A crossing: the shared node is held once, by the lower bar.
        {
            Array nodes = Array.CreateInstance(point3d, 9);
            // Bar 0 along x through the crossing at index 2; bar 1 along y
            // through the same node.
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.0, 0.0, 2.0), 1);
            nodes.SetValue(P(0.0, 0.0, 3.0), 2);
            nodes.SetValue(P(2.0, 0.0, 2.0), 3);
            nodes.SetValue(P(4.0, 0.0, 0.0), 4);
            nodes.SetValue(P(0.0, -4.0, 0.0), 5);
            nodes.SetValue(P(0.0, -2.0, 2.0), 6);
            nodes.SetValue(P(0.0, 2.0, 2.0), 7);
            nodes.SetValue(P(0.0, 4.0, 0.0), 8);
            Array acrossA = Array.CreateInstance(vector3d, 5);
            Array acrossB = Array.CreateInstance(vector3d, 5);
            for (int i = 0; i < 5; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2, 3, 4 }, new[] { 5, 6, 2, 7, 8 } }, new[] { 0, 4, 5, 8 }, across,
                new[] { (0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 2), (2, 7), (7, 8) });
            object placed = Run(net, Array.Empty<int[]>(), 2.0, 1, 1);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var heads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (heads.Count(h => h == 2) != 1)
                throw new InvalidOperationException($"The crossing node is held exactly once; it is held {heads.Count(h => h == 2)} times.");
            object owner = trees.First(t => ((int[])Get<object>(t, "Nodes")).Contains(2));
            if (Get<int>(owner, "Bar") != 0)
                throw new InvalidOperationException("The crossing belongs to the lower-indexed bar.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 2)
                throw new InvalidOperationException($"A crossing does not cut a span: two bars give two spans, got {spans.Length}.");
            object built = Get<object>(placed, "Built");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"Ground 1 on this cross is feasible (rise three over a half-width of four leans the outer trunks 53 degrees, and the mirrored pairs sum vertical at the foot) and must be placed; placed {Get<int>(placed, "GroundPlaced")}.");
            if (feet.Length != 1)
                throw new InvalidOperationException($"Type 1 on a cross puts both bars' feet on the same point, where they are one node; {feet.Length} built.");
            if (Get<int>(built, "FeetMerged") != 0)
                throw new InvalidOperationException($"Two feet at the SAME point are one node whatever put them there, which is a WELD and is neither a merge nor a close pair; {Get<int>(built, "FeetMerged")} merges reported.");
        }

        // ---- The segment distance, the primitive under the member rule.
        {
            double D(double[] a, double[] b, double[] c, double[] d) =>
                (double)segment.Invoke(null, new[] { P(a[0], a[1], a[2]), P(b[0], b[1], b[2]), P(c[0], c[1], c[2]), P(d[0], d[1], d[2]) })!;
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.0, 0.5, 0.0 }, new[] { 1.0, 0.5, 0.0 }) - 0.5) > 1.0e-9)
                throw new InvalidOperationException("Parallel unit segments half a unit apart are half a unit apart.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.5, -1.0, 0.2 }, new[] { 0.5, 1.0, 0.2 }) - 0.2) > 1.0e-9)
                throw new InvalidOperationException("A segment crossing over another at height 0.2 is 0.2 away.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 3.0, 0.0, 0.0 }, new[] { 4.0, 0.0, 0.0 }) - 2.0) > 1.0e-9)
                throw new InvalidOperationException("Collinear segments two apart are two apart.");
        }

        // ---- The collision RULE, spec 6, on CountCollisions itself. The
        // segment distance above is only its primitive; nothing used to drive
        // the rule, so neither the member test nor the net test had ever been
        // measured and a level could be refused on "collision" untested.
        {
            Type levelType = engine.GetNestedType("Level", BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException("ColumnPlacement has no Level.");
            MethodInfo countCollisions = RequirePublicStatic(engine, "CountCollisions");

            object BuildLevel(double[][] points, (int, int)[] pairs)
            {
                object level = Activator.CreateInstance(levelType, nonPublic: true)!;
                object nodeList = levelType.GetField("Nodes")!.GetValue(level)!;
                MethodInfo addNode = nodeList.GetType().GetMethod("Add")!;
                foreach (double[] point in points)
                    addNode.Invoke(nodeList, new[] { P(point[0], point[1], point[2]) });
                object memberList = levelType.GetField("Members")!.GetValue(level)!;
                Type pair = memberList.GetType().GetGenericArguments()[0];
                MethodInfo addMember = memberList.GetType().GetMethod("Add")!;
                foreach ((int lower, int upper) in pairs)
                    addMember.Invoke(memberList, new[] { Activator.CreateInstance(pair, lower, upper) });
                return level;
            }

            int Collisions(object level, double[][] netVertices, double clearance)
            {
                Array netNodes = Array.CreateInstance(point3d, netVertices.Length);
                for (int i = 0; i < netVertices.Length; i++)
                    netNodes.SetValue(P(netVertices[i][0], netVertices[i][1], netVertices[i][2]), i);
                return (int)countCollisions.Invoke(null, new object?[]
                {
                    level, netNodes, new HashSet<int>(), clearance,
                })!;
            }

            const double clearance = 0.1;
            var empty = Array.Empty<double[]>();
            object half = BuildLevel(
                new[]
                {
                    new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 },
                    new[] { 0.0, 0.05, 0.0 }, new[] { 1.0, 0.05, 0.0 },
                },
                new[] { (0, 1), (2, 3) });
            if (Collisions(half, empty, clearance) != 1)
                throw new InvalidOperationException("Two parallel members that share no end, at half the clearance, collide.");
            object twice = BuildLevel(
                new[]
                {
                    new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 },
                    new[] { 0.0, 0.2, 0.0 }, new[] { 1.0, 0.2, 0.0 },
                },
                new[] { (0, 1), (2, 3) });
            if (Collisions(twice, empty, clearance) != 0)
                throw new InvalidOperationException("The same two members at twice the clearance do not collide.");

            // The net test: a member whose interior rises above the net
            // vertex nearest it in plan is through the net. The same member
            // under a net that passes above it is not.
            object flat = BuildLevel(
                new[] { new[] { 0.0, 0.0, 1.0 }, new[] { 2.0, 0.0, 1.0 } },
                new[] { (0, 1) });
            if (Collisions(flat, new[] { new[] { 1.0, 0.0, 0.0 } }, clearance) != 1)
                throw new InvalidOperationException("A member whose midpoint rises above the nearest net vertex collides with the net.");
            if (Collisions(flat, new[] { new[] { 1.0, 0.0, 5.0 } }, clearance) != 0)
                throw new InvalidOperationException("A member under the net does not collide with it.");
        }

        // Spec 3.7's Auto rule, recomputed by the check from what the engine
        // recorded: the shortest load path among the levels with NO
        // collision, ties to the higher level; and when every level collides,
        // the shortest of them all.
        int AutoWinner(object[] levels)
        {
            object? best = null;
            object? bestAny = null;
            foreach (object level in levels.OrderByDescending(l => Get<int>(l, "Ground")))
            {
                if (bestAny is null || Get<double>(level, "LoadPath") < Get<double>(bestAny, "LoadPath"))
                    bestAny = level;
                if (Get<int>(level, "Collisions") == 0 &&
                    (best is null || Get<double>(level, "LoadPath") < Get<double>(best, "LoadPath")))
                    best = level;
            }
            return Get<int>(best ?? bestAny!, "Ground");
        }

        // ---- Auto picks the shorter load path where both are feasible.
        {
            // Spec 6's case, which the old fixture did not build: Ground 1
            // and Ground 0 BOTH feasible and Ground 1 the shorter load path,
            // so Auto places 1.
            //
            // A steep narrow arch of three free notches whose transverse
            // pulls lean OUTWARD. Ground 0 stands each tree on its own
            // AimFrom foot, which throws the outer feet past the anchors and
            // lengthens their members; Ground 1 puts one foot on the span
            // centre, and the three trunks arriving there sum to a vertical
            // push against a vertical wanted, so alignment passes. Levels 2,
            // 3 and 4 hand every tree its own plumb foot again, where a
            // single tilted aim is 35 degrees off its own plumb trunk, past
            // the 30-degree cap, so alignment is the worst measure each of
            // them names. Nothing is refused any more, and Auto weighs all
            // five levels by load path.
            const double tilt = 0.7;
            Array archNodes = Array.CreateInstance(point3d, 5);
            Array archAcross = Array.CreateInstance(vector3d, 5);
            var archEdges = new List<(int, int)>();
            for (int i = 0; i < 5; i++)
            {
                double s = i / 4.0;
                archNodes.SetValue(P(3.0 * s, 0.0, 3.0 * 4.0 * s * (1.0 - s)), i);
                double lean = i < 2 ? -tilt : (i > 2 ? tilt : 0.0);
                archAcross.SetValue(V(lean, 0.0, -1.0), i);
                if (i > 0)
                    archEdges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(archAcross, 0);
            var outward = (archNodes, new[] { new[] { 0, 1, 2, 3, 4 } }, new[] { 0, 4 }, across, archEdges.ToArray());

            object placed = Run(outward, Array.Empty<int[]>(), 0.75, 1, -1);
            if (Get<int>(placed, "GroundAsked") != -1)
                throw new InvalidOperationException("Auto records GroundAsked as -1.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object AtLevel(int level) =>
                tried.FirstOrDefault(t => Get<int>(t, "Ground") == level)
                ?? throw new InvalidOperationException($"Auto must evaluate every level; {level} is missing.");
            object one = AtLevel(1);
            object zero = AtLevel(0);
            if (!Get<bool>(one, "Feasible"))
                throw new InvalidOperationException($"Feasible now means no collision, and Type 1 has none here; it reports {Get<int>(one, "Collisions")}.");
            if (!Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException($"Feasible now means no collision, and Type 0 has none here; it reports {Get<int>(zero, "Collisions")}.");
            if (Get<double>(one, "LoadPath") >= Get<double>(zero, "LoadPath"))
                throw new InvalidOperationException($"Ground 1 must carry the SHORTER load path here; it scores {Get<double>(one, "LoadPath"):0.###} against Ground 0 at {Get<double>(zero, "LoadPath"):0.###}.");
            // Levels 2, 3 and 4 hand every tree its own plumb foot under a
            // tilted aim, 35 degrees off the thrust the foot is asked for.
            // That USED to refuse them. Spec 3.7 judges and never refuses:
            // they stand, alignment is named as the worst measure, and Auto
            // weighs them by load path like any other level.
            foreach (int level in new[] { 2, 3, 4 })
            {
                object judged = AtLevel(level);
                if (!Get<bool>(judged, "Feasible"))
                    throw new InvalidOperationException($"Level {level} has no collision here, so it is feasible; it came back refused on {Get<string>(judged, "Rule")}.");
                if (Get<string>(judged, "Rule") != "alignment")
                    throw new InvalidOperationException($"Level {level} stands a plumb trunk under a tilted aim, so alignment is the worst measure it names; it names '{Get<string>(judged, "Rule")}'.");
                if (Get<double>(judged, "Value") <= alignmentCap)
                    throw new InvalidOperationException($"The named alignment is the measured angle, past the {alignmentCap:0} degree bound; it is {Get<double>(judged, "Value"):0.###}.");
            }
            int winner = AutoWinner(tried);
            if (Get<int>(placed, "GroundPlaced") != winner)
                throw new InvalidOperationException($"Auto places the shortest load path among the levels with no collision, ties to the higher; that is {winner} and it placed {Get<int>(placed, "GroundPlaced")}.");
        }

        // ---- Auto prefers the level that does not collide (spec 3.7). The
        // rise-five arch eight wide at a clearance of 1.2 (a median plan edge
        // of 24 gives ClearanceFraction 0.05 that) stands its seven Type 0
        // feet one unit apart, so every neighbouring pair of members is
        // inside the clearance and Type 0 collides six times. Type 1 gathers
        // all seven onto one foot, where every member shares an end and
        // nothing can collide. Type 0 still carries the SHORTEST load path,
        // being plumb throughout, so an Auto that only minimised the load
        // path would take it.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 24.0, 1, -1);
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            if (tried.Length != 5)
                throw new InvalidOperationException($"Auto builds all five levels; it built {tried.Length}.");
            object AtLevel(int level) =>
                tried.FirstOrDefault(t => Get<int>(t, "Ground") == level)
                ?? throw new InvalidOperationException($"Auto must build every level; {level} is missing.");
            object zero = AtLevel(0);
            object one = AtLevel(1);
            if (Get<int>(zero, "Collisions") == 0)
                throw new InvalidOperationException("This fixture wants Type 0 to collide: seven plumb members a unit apart inside a clearance of 1.2.");
            if (Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException("Feasible means no collision, and Type 0 collides here.");
            if (Get<string>(zero, "Rule") != "collision")
                throw new InvalidOperationException($"A colliding level names the collision as its worst measure; it names '{Get<string>(zero, "Rule")}'.");
            if (Get<int>(one, "Collisions") != 0)
                throw new InvalidOperationException($"Type 1 gathers every tree onto one foot, where every member shares an end; it reports {Get<int>(one, "Collisions")} collisions.");
            if (tried.Any(t => Get<double>(t, "LoadPath") < Get<double>(zero, "LoadPath")))
                throw new InvalidOperationException("Type 0 carries the shortest load path here, or the preference for a collision-free level is not being tested at all.");
            int winner = AutoWinner(tried);
            if (winner == 0)
                throw new InvalidOperationException("The recomputed winner is a collision-free level, and Type 0 is not one.");
            if (Get<int>(placed, "GroundPlaced") != winner)
                throw new InvalidOperationException($"Auto places the shortest load path among the levels with no collision, ties to the higher; that is {winner} and it placed {Get<int>(placed, "GroundPlaced")}.");
        }
    }

    private static double AngleDeg(double ax, double ay, double az, double bx, double by, double bz)
    {
        double la = Math.Sqrt((ax * ax) + (ay * ay) + (az * az));
        double lb = Math.Sqrt((bx * bx) + (by * by) + (bz * bz));
        if (la <= 1.0e-12 || lb <= 1.0e-12)
            return 0.0;
        double c = ((ax * bx) + (ay * by) + (az * bz)) / (la * lb);
        return Math.Acos(Math.Min(Math.Max(c, -1.0), 1.0)) * 180.0 / Math.PI;
    }

    private static object Step(string name, Func<object?> call)
    {
        try
        {
            return call()
                ?? throw new InvalidOperationException($"{name} returned null.");
        }
        catch (TargetInvocationException error)
        {
            throw new InvalidOperationException(
                $"{name} threw: {DescribeException(error.InnerException ?? error)}",
                error);
        }
    }

    /// <summary>
    /// <c>MouldGeometry.ConnectedGroups</c> and
    /// <c>MouldGeometry.MemberRunIndex</c>: the two rules the tree outputs of
    /// Mould Animate and Deconstruct branch by.
    ///
    /// Param's complaint was that anchors and principal lines arrived as flat
    /// lists that were "so difficult to organise after". The flat list is not
    /// merely unhelpful, it is lossy: the anchors of a vault are two strips
    /// down opposite sides, and merging them into one list sorted by node index
    /// destroys both which strip a node was on and the order along it. Node
    /// index order is not geometric, so node 7 can sit at the far end of the
    /// far side from node 6.
    ///
    /// So the two things worth measuring are exactly the two things a flat list
    /// threw away. First, that two strips come back as TWO groups and not one.
    /// Second, that each group is WALKED rather than sorted, which is tested on
    /// a strip whose node indices deliberately disagree with its geometry:
    /// index order gives 0,1,2,3,4 and the connectivity gives 0,3,1,4,2, so a
    /// sort cannot pass by accident.
    ///
    /// The member rule has one case that a naive test would miss. A cable can
    /// join two notches of the SAME bar without being part of that bar, by
    /// cutting a corner across the net. Membership is therefore consecutiveness
    /// along the run, not "both ends are on it", and the corner-cutting member
    /// has to land in the infill branch where it belongs.
    /// </summary>
    private static void ValidateOutputGrouping(Assembly plugin)
    {
        Type mouldGeometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry",
            throwOnError: true)!;
        MethodInfo connected = RequirePublicStatic(
            mouldGeometry, "ConnectedGroups");
        MethodInfo runIndex = RequirePublicStatic(
            mouldGeometry, "MemberRunIndex");
        MethodInfo buildAdjacency = RequirePublicStatic(
            mouldGeometry, "BuildAdjacency");

        Type edgeArrayType = buildAdjacency.GetParameters()[1].ParameterType;
        Type edgeType = edgeArrayType.GetElementType()!;

        Array Edges(params (int A, int B)[] pairs)
        {
            Array array = Array.CreateInstance(edgeType, pairs.Length);
            for (int i = 0; i < pairs.Length; i++)
            {
                array.SetValue(
                    Activator.CreateInstance(
                        edgeType, pairs[i].A, pairs[i].B),
                    i);
            }
            return array;
        }

        int[][] Groups(int count, int[] ids, params (int A, int B)[] pairs)
        {
            object neighbours = buildAdjacency.Invoke(
                null, new object?[] { count, Edges(pairs) })!;
            object result = connected.Invoke(
                null, new object?[] { ids, neighbours })!;
            return ((IEnumerable)result)
                .Cast<IEnumerable<int>>()
                .Select(group => group.ToArray())
                .ToArray();
        }

        // TWO STRIPS, the case that made this necessary. Two rows of five,
        // joined along each row and never across, asked for together.
        int[][] sides = Groups(
            10,
            Enumerable.Range(0, 10).ToArray(),
            (0, 1), (1, 2), (2, 3), (3, 4),
            (5, 6), (6, 7), (7, 8), (8, 9));
        if (sides.Length != 2)
        {
            throw new InvalidOperationException(
                "Two anchor strips down opposite sides are TWO groups; "
                + $"{sides.Length} came back. One group means the strips were "
                + "merged, which is the flat list this replaces.");
        }
        if (!sides[0].SequenceEqual(new[] { 0, 1, 2, 3, 4 }) ||
            !sides[1].SequenceEqual(new[] { 5, 6, 7, 8, 9 }))
        {
            throw new InvalidOperationException(
                "The two strips came back as "
                + $"[{string.Join(",", sides[0])}] and "
                + $"[{string.Join(",", sides[1])}]; expected 0..4 and 5..9, "
                + "each whole and in order.");
        }

        // WALKED, NOT SORTED. The chain 0-3-1-4-2 is deliberately laid out so
        // that node index order and connectivity order disagree, so a sort
        // cannot pass this by luck.
        int[][] tangled = Groups(
            5,
            new[] { 0, 1, 2, 3, 4 },
            (0, 3), (3, 1), (1, 4), (4, 2));
        if (tangled.Length != 1)
        {
            throw new InvalidOperationException(
                $"One connected chain is one group; {tangled.Length} came "
                + "back.");
        }
        if (!tangled[0].SequenceEqual(new[] { 0, 3, 1, 4, 2 }))
        {
            throw new InvalidOperationException(
                "A strip must come back WALKED, in the order its members "
                + "connect: expected 0,3,1,4,2 and got "
                + $"{string.Join(",", tangled[0])}. Getting 0,1,2,3,4 means it "
                + "was sorted by node index, which is not a geometric order "
                + "and is the thing the flat list already did.");
        }

        // THE SAME EDGE TWICE, which is the ordinary case rather than a freak
        // one: GroupingAdjacency unions the plan's edges onto the solved ones,
        // so every edge present in both graphs arrives twice. Counting list
        // entries rather than distinct neighbours made BOTH ends of an open
        // strip count two, so no end was recognised and the walk fell back to
        // the lowest index. The chain here is 2-0-3-1-4, whose lowest index
        // sits in the MIDDLE, so a walk that starts there dead-ends after one
        // step and the rest is appended by index.
        int[][] doubled = Groups(
            5,
            new[] { 0, 1, 2, 3, 4 },
            (2, 0), (0, 3), (3, 1), (1, 4),
            (2, 0), (0, 3), (3, 1), (1, 4));
        if (doubled.Length != 1 ||
            !doubled[0].SequenceEqual(new[] { 2, 0, 3, 1, 4 }))
        {
            throw new InvalidOperationException(
                "A strip whose edges are supplied twice must still walk end to "
                + "end: expected one group of 2,0,3,1,4 and got "
                + $"{doubled.Length} group(s), the first ["
                + string.Join(
                    ",",
                    doubled.Length > 0 ? doubled[0] : Array.Empty<int>())
                + "]. Getting 0,2,... means the duplicate entries hid the ends "
                + "of the strip from the walk.");
        }

        // A CLOSED LOOP has no end to start from, and must still come back
        // whole and walked round rather than split.
        int[][] loop = Groups(
            4,
            new[] { 0, 1, 2, 3 },
            (0, 1), (1, 2), (2, 3), (3, 0));
        if (loop.Length != 1 || loop[0].Length != 4)
        {
            throw new InvalidOperationException(
                $"A closed boundary loop is one group of four; got "
                + $"{loop.Length} group(s) of "
                + $"{string.Join("/", loop.Select(g => g.Length))}.");
        }
        if (!loop[0].SequenceEqual(new[] { 0, 1, 2, 3 }) &&
            !loop[0].SequenceEqual(new[] { 0, 3, 2, 1 }))
        {
            throw new InvalidOperationException(
                "A loop must come back walked round, either way about: got "
                + $"{string.Join(",", loop[0])}.");
        }

        // THE WRONG-GRAPH REGRESSION, which showed as 42 branches of one node
        // each.
        //
        // A TNA analysis topology carries no edge between two supports: such
        // an edge joins two fixed nodes, contributes no unknown, and the
        // network never needs it. Six anchors joined only to the interior and
        // never to each other IS that graph. Grouping over it can only give
        // singletons, and asserting it here says the walk is not at fault, so
        // nobody goes hunting for the bug inside it.
        int[][] byNetOnly = Groups(
            10,
            new[] { 0, 1, 2, 6, 7, 8 },
            // every anchor to an interior node, and no anchor to an anchor
            (0, 3), (1, 4), (2, 5), (6, 3), (7, 4), (8, 5));
        if (byNetOnly.Length != 6)
        {
            throw new InvalidOperationException(
                "Anchors joined only to the interior must come back as six "
                + $"singletons; got {byNetOnly.Length} group(s). This case "
                + "documents WHY the solved net is the wrong graph to group "
                + "by, so it has to keep reproducing.");
        }

        // The same anchors over the UNION with the plan as drawn, where each
        // side IS continuous. Two sides, three nodes each, walked in order.
        int[][] byUnion = Groups(
            10,
            new[] { 0, 1, 2, 6, 7, 8 },
            (0, 3), (1, 4), (2, 5), (6, 3), (7, 4), (8, 5),
            (0, 1), (1, 2),      // side A, joined in the plan
            (6, 7), (7, 8));     // side B, joined in the plan
        if (byUnion.Length != 2)
        {
            throw new InvalidOperationException(
                "Adding the plan's own side edges must give TWO strips; got "
                + $"{byUnion.Length}. That union is the fix: group over the "
                + "plan together with the solved net, not the net alone.");
        }
        if (!byUnion[0].SequenceEqual(new[] { 0, 1, 2 }) ||
            !byUnion[1].SequenceEqual(new[] { 6, 7, 8 }))
        {
            throw new InvalidOperationException(
                "The two sides came back as "
                + $"[{string.Join(",", byUnion[0])}] and "
                + $"[{string.Join(",", byUnion[1])}]; expected 0,1,2 and "
                + "6,7,8, each whole and walked in order.");
        }

        // Coverage note: this measures the GROUPING, which is where the
        // observable behaviour is. MouldGeometry.GroupingAdjacency, which
        // unions the two edge sets and guards on the pattern carrying the same
        // vertex count, is exercised only through the components; a fixture
        // for it needs a whole nested ResultDto.

        // MEMBER OWNERSHIP. Two bars, and four members put to them.
        var runs = new List<IReadOnlyList<int>>
        {
            new List<int> { 0, 1, 2, 3 },
            new List<int> { 10, 11, 12 },
        };
        Array members = Edges(
            (0, 1),    // bar 0
            (2, 1),    // bar 0, given backwards
            (10, 11),  // bar 1
            (0, 2),    // BOTH ends on bar 0, but not consecutive: infill
            (5, 6));   // nowhere near a bar: infill
        var owner = (int[])runIndex.Invoke(
            null, new object?[] { members, runs })!;
        var expected = new[] { 0, 0, 1, -1, -1 };
        if (!owner.SequenceEqual(expected))
        {
            throw new InvalidOperationException(
                $"Members belong to [{string.Join(",", expected)}]; got "
                + $"[{string.Join(",", owner)}]. Index 1 is the same member "
                + "given end for end and must still be bar 0. Index 3 joins "
                + "two notches of bar 0 by cutting the corner between them, "
                + "which makes it INFILL: membership is consecutiveness along "
                + "the run, not both ends lying on it.");
        }
    }

    /// <summary>
    /// What EI is still for, and the lean rule, both measured.
    ///
    /// Nothing chooses where a column stands by stiffness any more: every
    /// notch is held, so there is no arrangement for EI to pick between and
    /// no way for it to tune a placement while claiming not to. EI is asked
    /// for on Fit and nowhere else, and it has one job left, which has
    /// to be exact: DEFLECTION SCALES AS ONE OVER EI. The beam knows the
    /// SHAPE of the sag between the notches a column holds, and that exact
    /// reciprocal is what turns the shape into millimetres, which is the
    /// unit a build tolerance is written in.
    ///
    /// The other half is LeanFromVertical, the rule the trunks are held to.
    /// A Ground level that would lean a trunk past sixty degrees is refused
    /// and the next lower one tried, so the measurement that decides it is
    /// checked against angles computed by hand.
    /// </summary>
    private static void ValidateStiffnessSeparation(Assembly plugin)
    {
        Type solver = plugin.GetType(
            "Ananke.COMPAS.Native.Components.BeamSolver", throwOnError: true)!;
        MethodInfo response = RequirePublicStatic(solver, "Response");

        const int stations = 31;
        var arc = new double[stations];
        var load = new double[stations];
        for (int i = 0; i < stations; i++)
        {
            double x = (double)i / (stations - 1);
            arc[i] = x;
            // Deliberately NOT uniform. A flat load is the one case where a
            // dependence on stiffness could hide behind symmetry.
            load[i] = 1.0 + (0.4 * Math.Sin(6.0 * x));
        }

        // Deflection is exactly reciprocal in EI.
        var supports = new[] { 0, stations / 2, stations - 1 };
        double[] Deflect(double EI)
        {
            object result = response.Invoke(
                null, new object?[] { arc, load, supports, EI })!;
            return (double[])result.GetType()
                .GetField("Item1")!.GetValue(result)!;
        }

        double[] one = Deflect(1.0);
        double[] four = Deflect(4.0);
        for (int i = 0; i < one.Length; i++)
        {
            double expected = one[i] / 4.0;
            if (Math.Abs(four[i] - expected) > 1.0e-9 * (1.0 + Math.Abs(expected)))
            {
                throw new InvalidOperationException(
                    $"Deflection must scale as one over EI: node {i} gave "
                    + $"{four[i]:G6} at EI 4 against {expected:G6} expected "
                    + $"from {one[i]:G6} at EI 1. Without that exact "
                    + "reciprocal, one EI cannot convert the placement's "
                    + "bending shape into millimetres.");
            }
        }

        // The lean rule the trunks are held to.
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo lean = RequirePublicStatic(geometry, "LeanFromVertical");
        Type point3d = lean.GetParameters()[0].ParameterType;
        double Lean(double dx, double rise)
        {
            object foot = Activator.CreateInstance(point3d, 0.0, 0.0, 0.0)!;
            object top = Activator.CreateInstance(point3d, dx, 0.0, rise)!;
            return (double)lean.Invoke(null, new[] { foot, top })!;
        }

        if (Math.Abs(Lean(0.0, 1.0)) > 1.0e-9)
            throw new InvalidOperationException("A plumb member leans 0 degrees.");
        if (Math.Abs(Lean(1.0, 1.0) - 45.0) > 1.0e-9)
            throw new InvalidOperationException("One across, one up, is 45 degrees.");
        if (Math.Abs(Lean(Math.Sqrt(3.0), 1.0) - 60.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Root three across, one up, is exactly 60 degrees, which is "
                + "the limit itself and so the value that decides whether a "
                + "Ground level is refused.");
        }
    }

    private static MethodInfo RequirePublicStatic(Type owner, string name) =>
        owner.GetMethod(
            name,
            BindingFlags.Public | BindingFlags.Static)
        ?? throw new InvalidOperationException(
            $"{owner.Name}.{name} was not found.");

    private static MethodInfo RequireStatic(Type owner, string name) =>
        owner.GetMethod(
            name,
            BindingFlags.NonPublic | BindingFlags.Static)
        ?? throw new InvalidOperationException(
            $"{owner.Name}.{name} was not found.");

    private static void CheckOneAim(
        MethodInfo loads,
        MethodInfo transverse,
        MethodInfo armAim,
        Type point3d,
        Type incidentArray,
        Type incidentList,
        double farX,
        double farZ,
        bool twoSided,
        double expectedX,
        double expectedZ,
        string label)
    {
        // 0,1,2 are the bar along Y at x = 0, z = 1. 3 and 4 are the far ends
        // of the middle notch's infill cables.
        var coordinates = new List<(double X, double Y, double Z)>
        {
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
            (0.0, 2.0, 1.0),
            (farX, 1.0, farZ),
            (-farX, 1.0, farZ),
        };
        Array nodes = Array.CreateInstance(point3d, coordinates.Count);
        for (int index = 0; index < coordinates.Count; index++)
        {
            (double x, double y, double z) = coordinates[index];
            nodes.SetValue(Activator.CreateInstance(point3d, x, y, z), index);
        }

        // Positive is tension, so each cable pulls node 1 toward its far end.
        var cables = new List<(int Node, int Other)> { (1, 3) };
        if (twoSided)
            cables.Add((1, 4));

        Array incident = Array.CreateInstance(
            incidentList, coordinates.Count);
        MethodInfo add = incidentList.GetMethod("Add")
            ?? throw new InvalidOperationException("List.Add was not found.");
        for (int index = 0; index < coordinates.Count; index++)
            incident.SetValue(Activator.CreateInstance(incidentList), index);
        foreach ((int node, int other) in cables)
        {
            add.Invoke(
                incident.GetValue(node),
                new object[] { (other, 100.0) });
            add.Invoke(
                incident.GetValue(other),
                new object[] { (node, 100.0) });
        }
        // The bar's own edges, which BarLoads must leave out.
        add.Invoke(incident.GetValue(0), new object[] { (1, 50.0) });
        add.Invoke(incident.GetValue(1), new object[] { (0, 50.0) });
        add.Invoke(incident.GetValue(1), new object[] { (2, 50.0) });
        add.Invoke(incident.GetValue(2), new object[] { (1, 50.0) });

        var bar = new List<int> { 0, 1, 2 };
        object pull = Step("BarLoads", () => loads.Invoke(
            null, new object?[] { bar, nodes, incident }));
        object across = Step("BarTransverse", () => transverse.Invoke(
            null, new object?[] { bar, nodes, pull }));

        object loaded = ((Array)across).GetValue(1)
            ?? throw new InvalidOperationException(
                "BarTransverse returned nothing for the loaded notch.");
        object direction = Step("AimFrom", () => armAim.Invoke(
            null, new object?[] { loaded }));
        Type vector3d = direction.GetType();
        double aimX = (double)vector3d.GetProperty("X")!.GetValue(direction)!;
        double aimY = (double)vector3d.GetProperty("Y")!.GetValue(direction)!;
        double aimZ = (double)vector3d.GetProperty("Z")!.GetValue(direction)!;

        const double tolerance = 1.0e-9;
        if (Math.Abs(aimX - expectedX) > tolerance ||
            Math.Abs(aimY) > tolerance ||
            Math.Abs(aimZ - expectedZ) > tolerance)
        {
            throw new InvalidOperationException(
                $"The column for a {label} must aim ("
                + $"{expectedX:G6}, 0, {expectedZ:G6}); it aims "
                + $"({aimX:G6}, {aimY:G6}, {aimZ:G6}). A wrong sign on X means "
                + "the column leans WITH the pull instead of against it.");
        }
    }

    /// <summary>
    /// <c>PrincipalRunFinder.FromCurves</c>: one bar, however many times it
    /// was traced.
    ///
    /// The same physical line arrives twice more easily than it looks. From the
    /// anchors, a line traced from one strip reaches the other, so the strip
    /// opposite traces it backwards. From drawn curves, two curves laid near
    /// the same run of nodes both snap to it. The duplicate is INVISIBLE in the
    /// viewport, because the second bar draws exactly on top of the first, and
    /// it is ruinous downstream: each bar is given its own full set of columns,
    /// each mirrored about its own slightly different midpoint, so the columns
    /// land on one line at two offset spacings and read as hopelessly
    /// lopsided.
    ///
    /// This is measured because the fix was written once for the ANCHOR path
    /// and shipped, and it fixed nothing at all for a definition whose lines
    /// come from curves. A rule that has two callers needs a check that covers
    /// both, so this drives the curve path and the shared rule under it.
    ///
    /// Five nodes in a row with a curve down them, twice, is one bar. A second
    /// curve down a genuinely different row is a second bar.
    /// </summary>
    private static void ValidateRunDeduplication(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        MethodInfo dedupe = finder.GetMethod(
            "Deduplicate", BindingFlags.NonPublic | BindingFlags.Static)!;

        int Kept(params int[][] runs)
        {
            var input = new List<List<int>>();
            foreach (int[] run in runs)
                input.Add(new List<int>(run));
            object result = dedupe.Invoke(null, new object?[] { input })!;
            return ((IEnumerable)result).Cast<object>().Count();
        }

        // The same five nodes, traced twice, ending one node apart. One bar.
        int doubled = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 4, 3, 2, 1, 0 });
        if (doubled != 1)
        {
            throw new InvalidOperationException(
                "One line traced from both ends is one bar; "
                + $"{doubled} came back.");
        }

        // The realistic case: the two traces disagree at their ends, which is
        // exactly why matching endpoints could not catch this.
        int ragged = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 5, 3, 2, 1, 0 });
        if (ragged != 1)
        {
            throw new InvalidOperationException(
                "Two traces of one line that finish on DIFFERENT nodes are "
                + $"still one bar; {ragged} came back. Matching their ends is "
                + "what failed before, so this is the case that matters.");
        }

        // A genuinely separate line must survive.
        int separate = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 10, 11, 12, 13, 14 });
        if (separate != 2)
        {
            throw new InvalidOperationException(
                "Two lines sharing no nodes are two bars; "
                + $"{separate} came back. Deduplication must not swallow a "
                + "real second line.");
        }

        // Crossing at one node is not the same line.
        int crossing = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 20, 21, 2, 22, 23 });
        if (crossing != 2)
        {
            throw new InvalidOperationException(
                "Two lines that merely CROSS share one node and are still two "
                + $"bars; {crossing} came back.");
        }
    }

    /// <summary>
    /// The anchor derivation is deleted, and stays deleted. A principal line
    /// is a decision the author draws into Pattern. When Supports derived
    /// lines whenever Pattern carried none, a definition that forgot its
    /// curves quietly got bars it never asked for, which is a second author
    /// of one fact. This pins the deletion so it cannot creep back under
    /// another refactor.
    /// </summary>
    private static void ValidateDerivationRemoved(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        if (finder.GetMethods(Any).Any(m => m.Name == "DeriveFromAnchors"))
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.DeriveFromAnchors still exists. Principal "
                + "lines are input only; nothing derives them from anchors.");
        }
        if (finder.GetMethod("FromCurves", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.FromCurves is missing; it is the one way in.");
        }
        if (finder.GetMethod("Deduplicate", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.Deduplicate is missing; it is the safety net "
                + "for two curves snapping to one run.");
        }
    }

    /// <summary>
    /// <c>PrincipalRunFinder.Outcome</c>: what Pattern says about the curves
    /// it was handed, as one pure function of three counts, so the error path
    /// is measured rather than trusted. The error case matters most: curves
    /// wired and none placed used to fall through silently to no runs, and the
    /// first sign was Columns with nothing to stand under.
    /// </summary>
    private static void ValidatePrincipalOutcome(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        MethodInfo outcome = finder.GetMethod(
            "Outcome", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "PrincipalRunFinder.Outcome(int, int, int) is missing.");

        (string Severity, string Message) Run(int supplied, int unmatched, int kept)
        {
            object result = outcome.Invoke(
                null, new object?[] { supplied, unmatched, kept })!;
            Type type = result.GetType();
            string severity = (string)type.GetProperty("Severity")!
                .GetValue(result)!;
            string message = (string)type.GetProperty("Message")!
                .GetValue(result)!;
            return (severity, message);
        }

        void Expect(
            (int, int, int) counts, string severity, string contains)
        {
            (int supplied, int unmatched, int kept) = counts;
            (string got, string message) = Run(supplied, unmatched, kept);
            if (got != severity)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should be "
                    + $"'{severity}'; it was '{got}' with message '{message}'.");
            }
            if (contains.Length > 0 &&
                !message.Contains(contains, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) message should "
                    + $"contain '{contains}'; it was '{message}'.");
            }
            if (contains.Length == 0 && message.Length != 0)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should carry no "
                    + $"message; it was '{message}'.");
            }
        }

        Expect((0, 0, 0), "none", "");
        Expect((2, 0, 2), "none", "");
        Expect((3, 1, 2), "warning", "1 of 3");
        Expect((3, 0, 2), "remark", "merged");
        Expect((2, 2, 0), "error", "No Pattern");
        Expect((2, 0, 0), "error", "No Pattern");
    }

    /// <summary>
    /// <c>ParameterIdentity.Restore</c> after a document read: a mapping the
    /// plugin REGISTERED wins over the archive, a mapping it did not register
    /// belongs to the author.
    ///
    /// Pattern's Principal Lines port shipped without its Flatten and gained
    /// it later. Grasshopper resets every mapping from the archive on load,
    /// so without this rule every definition saved before the flatten
    /// reopened with P unflattened and one Pattern per branch of curves. The
    /// first fix re-asserted EVERY port's registered mapping, which would
    /// have wiped any graft or flatten the author set by hand, on every port
    /// of every component, on every reopen. Both halves are measured here by
    /// playing the archive's part: leave the ports as a load would, call
    /// Restore, read them back.
    /// </summary>
    private static void ValidateRegisteredMappingWins(Assembly plugin)
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static;
        Type identity = plugin.GetType(
            "Ananke.COMPAS.Native.Components.ParameterIdentity",
            throwOnError: true)!;
        MethodInfo capture = identity.GetMethod("Capture", Any)
            ?? throw new InvalidOperationException(
                "ParameterIdentity.Capture is missing.");
        MethodInfo restore = identity.GetMethod("Restore", Any)
            ?? throw new InvalidOperationException(
                "ParameterIdentity.Restore is missing.");

        Type patternType = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PatternComponent",
            throwOnError: true)!;
        object pattern = Activator.CreateInstance(patternType)
            ?? throw new InvalidOperationException(
                "PatternComponent could not be constructed.");
        try
        {
            object parameters = patternType.GetProperty("Params")!
                .GetValue(pattern)!;
            object inputs = parameters.GetType().GetProperty("Input")!
                .GetValue(parameters)!;
            var list = (IList)inputs;
            object principal = list[4]!;
            object mode = list[1]!;
            PropertyInfo principalMapping =
                principal.GetType().GetProperty("DataMapping")!;
            PropertyInfo modeMapping =
                mode.GetType().GetProperty("DataMapping")!;
            Type mappingType = principalMapping.PropertyType;
            object none = Enum.Parse(mappingType, "None");
            object flatten = Enum.Parse(mappingType, "Flatten");
            object graft = Enum.Parse(mappingType, "Graft");

            if (!Equals(principalMapping.GetValue(principal), flatten))
            {
                throw new InvalidOperationException(
                    "Pattern's Principal Lines port must register Flatten; "
                    + $"it registers {principalMapping.GetValue(principal)}.");
            }
            if (!Equals(modeMapping.GetValue(mode), none))
            {
                throw new InvalidOperationException(
                    "Pattern's Mode port must register no mapping for this "
                    + "check to mean anything; it registers "
                    + $"{modeMapping.GetValue(mode)}.");
            }

            // Capture runs before the archive is read, on the registered
            // identity, exactly as the Read override does.
            object snapshots = capture.Invoke(null, new[] { inputs })!;

            // The archive's part: an old definition saved P before it
            // flattened, and the author grafted Mode by hand.
            principalMapping.SetValue(principal, none);
            modeMapping.SetValue(mode, graft);

            restore.Invoke(null, new object?[] { inputs, snapshots });

            if (!Equals(principalMapping.GetValue(principal), flatten))
            {
                throw new InvalidOperationException(
                    "The registered Flatten on Principal Lines did not win over "
                    + "the archived None; definitions saved before the flatten "
                    + "reopen unflattened.");
            }
            if (!Equals(modeMapping.GetValue(mode), graft))
            {
                throw new InvalidOperationException(
                    "The author's graft on an unmapped port was wiped by "
                    + "Restore; a registered None must not be re-asserted.");
            }
        }
        finally
        {
            if (pattern is IDisposable disposable)
                disposable.Dispose();
        }
    }

    /// <summary>
    /// Pattern is the only component that previews principal runs. Every
    /// other component used to hold a <c>List&lt;Line&gt;</c> of red bars and
    /// paint it over its own preview, so two components on one canvas showed
    /// each bar twice: the "dual lining" that read as a doubled principal
    /// line. The rule is mechanical: an instance field of type List of Line
    /// whose name contains "Principal" exists on PatternComponent and on no
    /// other component, and the helper that read runs off a Result for the
    /// others, <c>TnaWorkflowPreview.ResultPrincipalLines</c>, is gone.
    /// </summary>
    private static void ValidatePrincipalPreviewOwner(
        Assembly plugin,
        Type[] componentTypes)
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        Type preview = plugin.GetType(
            "Ananke.COMPAS.Native.Components.TnaWorkflowPreview",
            throwOnError: true)!;
        if (preview.GetMethods(Any).Any(m => m.Name == "ResultPrincipalLines"))
        {
            throw new InvalidOperationException(
                "TnaWorkflowPreview.ResultPrincipalLines still exists. Pattern is "
                + "the only component that previews principal runs, and it reads "
                + "a topology, not a Result.");
        }

        const BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Instance | BindingFlags.DeclaredOnly;
        var owners = new List<string>();
        foreach (Type componentType in componentTypes)
        {
            for (Type? at = componentType; at is not null; at = at.BaseType)
            {
                foreach (FieldInfo field in at.GetFields(Fields))
                {
                    if (!field.Name.Contains(
                            "Principal", StringComparison.OrdinalIgnoreCase))
                        continue;
                    Type type = field.FieldType;
                    bool listOfLine = type.IsGenericType
                        && type.GetGenericTypeDefinition() == typeof(List<>)
                        && type.GetGenericArguments()[0].Name == "Line";
                    if (listOfLine)
                        owners.Add(componentType.FullName ?? componentType.Name);
                }
            }
        }

        const string Pattern = "Ananke.COMPAS.Native.Components.PatternComponent";
        if (!owners.Contains(Pattern))
        {
            throw new InvalidOperationException(
                "PatternComponent holds no principal-line preview field; it is "
                + "the one component that must.");
        }
        string[] others = owners.Where(o => o != Pattern).Distinct().ToArray();
        if (others.Length > 0)
        {
            throw new InvalidOperationException(
                "Only Pattern previews principal runs; these still hold a "
                + $"principal preview field: {string.Join(", ", others)}.");
        }
    }

    /// <summary>
    /// The barrel fixture: x 0..6 along the barrel (7 columns), a tent
    /// profile in y: z = 2 - |y - 2| over y 0..4, so both eaves sit at
    /// z 0 and the crest at z 2. Every level cut is a PAIR of OPEN
    /// strips, each a straight line of length 6, mirror-symmetric about
    /// x = 3; on the front strip (y below 2) a mapped point's y and z
    /// are EQUAL, which is what lets the checks read setout coordinates
    /// straight off the geometry.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinBarrelNet()
    {
        var vertices = new List<double[]>();
        for (int j = 0; j <= 4; j++)
        {
            double z = 2.0 - Math.Abs(j - 2.0);
            for (int i = 0; i <= 6; i++)
                vertices.Add(new double[] { i, j, z });
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 4; j++)
        {
            for (int i = 0; i < 6; i++)
            {
                int a = j * 7 + i;
                faces.Add(new[] { a, a + 1, a + 8, a + 7 });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// The barrel fixture again, vertex for vertex and face for face,
    /// with the faces emitted in a deliberately SCRAMBLED order. It is
    /// the fixture that measures Ruling A of the whole-branch review:
    /// the cells must be a property of the geometry, not of the face
    /// array.
    ///
    /// The derivation, so the scramble is chosen rather than stirred.
    /// Around one quad face (j, i) of the barrel the two crossings are
    /// met at column i + 1 first and column i second, so the crossing
    /// INDICES, and with them the degree-one crossing Trace starts an
    /// open walk from, follow the order that row's faces are emitted in.
    /// A cut at a height in (0, 1) crosses rows 0 (front) and 3 (back);
    /// a cut in (1, 2) crosses rows 1 (front) and 2 (back); the
    /// half-open rule puts a cut at exactly z = 1 in rows 0 and 3.
    ///
    /// Rows 0 and 3 are emitted 5, 2, 0, 4, 1, 3. Face 5 comes first, so
    /// the crossing at x = 6 takes index 0 and is the first degree-one
    /// crossing found: the walk runs EAST TO WEST.
    /// Rows 1 and 2 are emitted 0, 3, 1, 5, 2, 4. Face 0 comes first, so
    /// the crossing at x = 1 takes index 0 and the one at x = 0 index 1,
    /// which is the first degree-one crossing found: the walk runs WEST
    /// TO EAST.
    ///
    /// So the lower half of the barrel traces one way and the upper half
    /// the other, only the rows' END faces having moved, which is the
    /// exact shape the review's verifier reproduced bow-tie cells with:
    /// at S 0.6 and CH 0.5, course band 2 spans z 1.0 to 1.5 and takes
    /// its LOWER boundary curve from row 0 and its mid and upper curves
    /// from row 1, so without the normalisation its cells map one joint
    /// onto two curves running opposite ways.
    ///
    /// The row BLOCKS stay in ascending j on purpose. A cut's front row
    /// index is always below its back row index (0 below 3, 1 below 2),
    /// so the front strip's crossings always take the lower indices and
    /// the front strip is always component 0, exactly as in the ordered
    /// fixture. Traced component ORDER follows the face array as well,
    /// but that is ordering rather than orientation and it is outside
    /// Ruling A; keeping it fixed is what lets this check compare the
    /// two fixtures cell for cell.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinBarrelScrambledNet()
    {
        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        int[] lowerRows = { 5, 2, 0, 4, 1, 3 };
        int[] upperRows = { 0, 3, 1, 5, 2, 4 };
        var scrambled = new List<int[]>(faces.Length);
        for (int j = 0; j < 4; j++)
        {
            int[] order = j == 0 || j == 3 ? lowerRows : upperRows;
            foreach (int i in order)
                scrambled.Add(faces[j * 6 + i]);
        }
        return (vertices, scrambled.ToArray());
    }

    /// <summary>
    /// The dome fixture: two octagonal rings and an apex. Ring 0 has
    /// radius 2 at z 0, ring 1 radius 1 at z 1, the apex (0, 0, 2);
    /// quads between the rings, triangles to the apex. The radius at
    /// height h is 2 - h throughout, so a level curve at h is a CLOSED
    /// octagon of perimeter 16 (2 - h) sin(pi/8), with a vertex on the
    /// +X axis.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinDomeNet()
    {
        var vertices = new List<double[]>();
        for (int ring = 0; ring < 2; ring++)
        {
            double radius = 2.0 - ring;
            for (int k = 0; k < 8; k++)
            {
                double angle = Math.PI * 2.0 * k / 8.0;
                vertices.Add(new[]
                {
                    radius * Math.Cos(angle),
                    radius * Math.Sin(angle),
                    (double)ring
                });
            }
        }
        vertices.Add(new double[] { 0.0, 0.0, 2.0 });
        var faces = new List<int[]>();
        for (int k = 0; k < 8; k++)
        {
            int next = (k + 1) % 8;
            faces.Add(new[] { k, next, 8 + next, 8 + k });
            faces.Add(new[] { 8 + k, 8 + next, 16 });
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// The dome fixture again, vertex for vertex and face for face, moved
    /// in PLAN by (dx, dy). It is the fixture that measures the centred
    /// shoelace: nothing about the surface changes, only where in the
    /// world it is sited, which is the one thing a signed area must not
    /// depend on.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinDomeSitedNet(
        double dx,
        double dy)
    {
        (double[][] vertices, int[][] faces) = SkinDomeNet();
        double[][] moved = vertices
            .Select(vertex => new[]
            {
                vertex[0] + dx, vertex[1] + dy, vertex[2]
            })
            .ToArray();
        return (moved, faces);
    }

    /// <summary>
    /// Any fixture, turned about the world Z axis by the given angle in
    /// PLAN: (x, y) becomes (x cos a - y sin a, x sin a + y cos a) with z
    /// untouched, vertex for vertex and face for face.
    ///
    /// It is the fixture that measures the ROTATION INVARIANCE of the
    /// correspondence. A rotation about world Z moves no z, no face and
    /// no traced component: the cut at a height is the same cut, made of
    /// the same crossings, in the same order, and the count of
    /// components at every height is identical at every angle. Nothing
    /// about which curve corresponds to which can therefore depend on
    /// the angle, and a rule whose answer does is reading the world axes
    /// rather than the surface. The rule it caught was the overlap area
    /// of AXIS-ALIGNED plan bounding boxes: a long thin strip lying at
    /// an angle has a box inflated by roughly its own length times the
    /// sine of that angle, which manufactures an overlap where the
    /// strips are nowhere near one another.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinRotatedInPlan(
        (double[][] Vertices, int[][] Faces) fixture,
        double degrees)
    {
        double angle = degrees * Math.PI / 180.0;
        double cos = Math.Cos(angle);
        double sin = Math.Sin(angle);
        double[][] turned = fixture.Vertices
            .Select(vertex => new[]
            {
                vertex[0] * cos - vertex[1] * sin,
                vertex[0] * sin + vertex[1] * cos,
                vertex[2]
            })
            .ToArray();
        return (turned, fixture.Faces);
    }

    /// <summary>
    /// The ANNULAR shell, an oculus dome: five rings of sixteen vertices
    /// at radii 4, 3.2, 2.5, 1.8 and 1.0 and heights 0, 1.2, 2.0, 1.2
    /// and 0, quads between consecutive rings. The outer skirt climbs
    /// from the rim at radius 4 to the ridge circle at radius 2.5 and
    /// the inner skirt falls back to the oculus rim at radius 1, so
    /// every cut strictly between the rims and the ridge is TWO NESTED
    /// closed loops, an outer and an inner. That is what a level curve
    /// of a surface with a hole in it is, and an oculus dome is an
    /// ordinary funicular form.
    ///
    /// It is the fixture that measures what a bounding box cannot say.
    /// The outer loop's plan box CONTAINS the inner loop's at every
    /// height, and here the inner loop's arc length GROWS with height
    /// while the outer's shrinks, so the inner loop's box overlap with
    /// the outer loop below exceeded its overlap with the inner loop
    /// below: both loops claimed the outer, no bijection existed
    /// anywhere, and both engines refused the WHOLE surface at every
    /// course height tried, zero cells, while the diagnostics asserted
    /// that the level curves do not correspond when they correspond
    /// perfectly, outer to outer and inner to inner. Box area cannot
    /// express nesting; a distance can, because the inner loop lies
    /// close to the inner loop and far from the outer.
    ///
    /// One arithmetic convenience of these radii, used by the check: the
    /// outer and inner radii SUM to 5.0 at every height, since both
    /// skirts are linear in z and 4 + 1 = 3.2 + 1.8 = 2.5 + 2.5 = 5.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinRingVaultNet()
    {
        double[] radii = { 4.0, 3.2, 2.5, 1.8, 1.0 };
        double[] heights = { 0.0, 1.2, 2.0, 1.2, 0.0 };
        var vertices = new List<double[]>();
        for (int ring = 0; ring < radii.Length; ring++)
        {
            for (int k = 0; k < 16; k++)
            {
                double angle = Math.PI * 2.0 * k / 16.0;
                vertices.Add(new[]
                {
                    radii[ring] * Math.Cos(angle),
                    radii[ring] * Math.Sin(angle),
                    heights[ring]
                });
            }
        }
        var faces = new List<int[]>();
        for (int ring = 0; ring + 1 < radii.Length; ring++)
        {
            for (int k = 0; k < 16; k++)
            {
                int next = (k + 1) % 16;
                faces.Add(new[]
                {
                    ring * 16 + k,
                    ring * 16 + next,
                    (ring + 1) * 16 + next,
                    (ring + 1) * 16 + k
                });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// The ring vault TRIANGULATED: the same vertices and the same
    /// surface, with every quad split on the diagonal that joins its
    /// lower-ring corner k to its upper-ring corner k + 1, so the net
    /// holds triangles alone.
    ///
    /// It is one of the four meshings that must give ONE answer, and it
    /// is the one whose answer can be derived rather than measured. Each
    /// quad of this shell is PLANAR: its two chords, one on each ring,
    /// are parallel, because the rings are concentric regular 16-gons
    /// sharing their angular offsets, and two parallel lines lie in a
    /// plane. Height restricted to that plane is affine, so the level set
    /// at any height is a straight LINE within it, and the diagonal's
    /// crossing therefore lies exactly ON the segment the two edge
    /// crossings already gave. Writing u for the lower chord, v for the
    /// left edge and lambda = (r1 - r0) / r0, the quad's corners are A0,
    /// A0 + u, A0 + v and A0 + (1 + lambda) u + v, and the three
    /// crossings at parameter t come out A0 + t v, A0 + (1 + t lambda) u
    /// + t v and A0 + t (1 + lambda) u + t v: the same v coefficient, so
    /// the same line.
    ///
    /// So triangulating adds a collinear vertex to every traced
    /// component and changes NOTHING else: measured, every mid-level
    /// curve of the CH 0.35 grid comes back at the quad fixture's own
    /// length to five decimals (24.24322 and 6.97123 at the first mid,
    /// and so on down the six), and every course therefore carries the
    /// same round(L / S) pieces. Against the build before this wave the
    /// courses engine gave 260 cells here against the quad fixture's
    /// 312 at CH 0.35 and 156 against 208 at CH 0.5, with a band refused
    /// on a shell that has no transition anywhere, because the
    /// correspondence was scored point to point and the extra sample
    /// points moved the score.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinRingVaultTriangulatedNet()
    {
        (double[][] vertices, int[][] quads) = SkinRingVaultNet();
        var faces = new List<int[]>(quads.Length * 2);
        foreach (int[] quad in quads)
        {
            faces.Add(new[] { quad[0], quad[1], quad[2] });
            faces.Add(new[] { quad[0], quad[2], quad[3] });
        }
        return (vertices, faces.ToArray());
    }

    /// <summary>
    /// The ring vault with its RIDGE RING alone turned about world Z:
    /// ring 2, the sixteen vertices of radius 2.5 at z 2.0, rotated by
    /// the given angle while every other ring stays where it was.
    ///
    /// It is the fixture that reproduces this wave's defect, and it was
    /// chosen because it is so nearly nothing. Turning one ring moves no
    /// height, no face and no level set: every cut between the rims and
    /// the ridge is still two nested loops, the outer still contains the
    /// inner, and the component count at every height is what it was.
    /// Measured against the build before this wave, driving the courses
    /// engine at S 0.6 and CH 1.9: 0.00 degrees gave 52 cells and
    /// refused nothing, 0.05 degrees the same, and 0.10 degrees, which
    /// is 4.4 mm of arc on a 2.5 m circle, gave ZERO cells with one band
    /// refused and the diagnostics stating that the level curves do not
    /// correspond. 0.25 degrees the same. A tenth of a degree turned a
    /// whole pattern into nothing.
    ///
    /// The two angles pinned are 0.1, the smallest measured that broke
    /// it, and 11.25, which is HALF the ring's own 22.5 degree spacing
    /// and so the furthest a ring can be turned from its neighbours: the
    /// two ends of the range rather than two samples from the middle of
    /// it. At 11.25 degrees the traced lengths do move a little, because
    /// the faces either side of the ridge are genuinely differently
    /// shaped (19.84069 m becomes 19.83154 m on the fourth mid), but a
    /// nine millimetre change in a 19.8 m course is 0.015 of a piece and
    /// nowhere near the half-piece that would move round(L / S), so
    /// every course carries the same count.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinRingVaultRidgeTurnedNet(double degrees)
    {
        (double[][] vertices, int[][] faces) = SkinRingVaultNet();
        double angle = degrees * Math.PI / 180.0;
        double cos = Math.Cos(angle);
        double sin = Math.Sin(angle);
        double[][] turned = vertices
            .Select((vertex, index) => index / 16 == 2
                ? new[]
                {
                    vertex[0] * cos - vertex[1] * sin,
                    vertex[0] * sin + vertex[1] * cos,
                    vertex[2]
                }
                : vertex)
            .ToArray();
        return (turned, faces);
    }

    /// <summary>
    /// The ring vault with UNEQUAL ring densities, 16, 16, 16, 32, 32:
    /// the outer rim, the outer skirt and the ridge keep their sixteen
    /// vertices and the two inner rings carry thirty-two, so the mesh is
    /// fine on the oculus side and coarse on the rim side. Between the
    /// 16-ring and the 32-ring, vertex A[k] sits over B[2k] and the gap
    /// is filled by the quad A[k], A[k+1], B[2k+2], B[2k+1] and the
    /// triangle A[k], B[2k+1], B[2k].
    ///
    /// It is the meshing that separates a real answer from a lucky one.
    /// The quad fixture is the ONE annular mesh whose equal sampling
    /// makes the tangential error of a point-to-point score cancel, so
    /// it broke the tie correctly by luck; give the rings different
    /// densities and the luck goes. Against the build before this wave
    /// the courses engine gave 261 cells here at CH 0.35 against the
    /// quad fixture's 312, with a band refused on a shell that has no
    /// transition.
    ///
    /// One count genuinely MOVES on this meshing and it is not a defect:
    /// its courses at CH 0.35 are 313, not 312. Spec section 5 sets a
    /// course's piece count from round(L / S) on its own mid curve, and
    /// L is the length of the polygon the mesh actually traces. A
    /// regular 32-gon inscribed in a circle is LONGER than a 16-gon
    /// inscribed in the same circle: 64 R sin(pi / 32) = 6.273100 R
    /// against 32 R sin(pi / 16) = 6.242890 R. At the third mid, z
    /// 0.875, the inner radius is 1 + 0.8 (0.875 / 1.2) = 1.583333, so
    /// the 32-gon measures 9.93240 m and the 16-gon 9.88458 m; divided
    /// by S 0.6 that is 16.554 pieces against 16.474, and the first
    /// rounds to 17 while the second rounds to 16. That one course is
    /// the whole difference: the six bands read (40, 12), (38, 14),
    /// (36, 17), (33, 19), (30, 22) and (27, 25), which is 52, 52, 53,
    /// 52, 52, 52 = 313 against the quad fixture's 312. At CH 0.5 and
    /// CH 1.9 no course crosses a rounding boundary and the counts
    /// agree exactly.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinRingVaultUnequalNet()
    {
        double[] radii = { 4.0, 3.2, 2.5, 1.8, 1.0 };
        double[] heights = { 0.0, 1.2, 2.0, 1.2, 0.0 };
        int[] counts = { 16, 16, 16, 32, 32 };
        var starts = new int[radii.Length];
        var vertices = new List<double[]>();
        for (int ring = 0; ring < radii.Length; ring++)
        {
            starts[ring] = vertices.Count;
            for (int k = 0; k < counts[ring]; k++)
            {
                double angle = Math.PI * 2.0 * k / counts[ring];
                vertices.Add(new[]
                {
                    radii[ring] * Math.Cos(angle),
                    radii[ring] * Math.Sin(angle),
                    heights[ring]
                });
            }
        }
        var faces = new List<int[]>();
        for (int ring = 0; ring + 1 < radii.Length; ring++)
        {
            int lower = starts[ring];
            int upper = starts[ring + 1];
            int here = counts[ring];
            int there = counts[ring + 1];
            for (int k = 0; k < here; k++)
            {
                int next = (k + 1) % here;
                if (here == there)
                {
                    faces.Add(new[]
                    {
                        lower + k, lower + next,
                        upper + next, upper + k
                    });
                    continue;
                }
                faces.Add(new[]
                {
                    lower + k, lower + next,
                    upper + (2 * k + 2) % there,
                    upper + (2 * k + 1) % there
                });
                faces.Add(new[]
                {
                    lower + k,
                    upper + (2 * k + 1) % there,
                    upper + 2 * k % there
                });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// The two-peak fixture, whose level curves SPLIT. A height field on
    /// the barrel's own 7 by 5 grid of quads, row-major, with the rim at
    /// z 0, the whole interior ring at 0.9, and two peaks of 2.0 at
    /// (2, 2) and (4, 2) with the saddle between them left at 0.9:
    ///
    ///   j = 4:   0    0    0    0    0    0    0
    ///   j = 3:   0   0.9  0.9  0.9  0.9  0.9   0
    ///   j = 2:   0   0.9  2.0  0.9  2.0  0.9   0
    ///   j = 1:   0   0.9  0.9  0.9  0.9  0.9   0
    ///   j = 0:   0    0    0    0    0    0    0
    ///
    /// The superlevel set {z at or above h} is the whole 5 by 3 interior
    /// block for every h in (0, 0.9], which is connected, so each of
    /// those cuts is ONE closed loop; for h in (0.9, 2) it is the two
    /// peak vertices alone, so each of those cuts is TWO. The split
    /// height is 0.9, and no vertex sits at 0.25, 0.5, 0.75, 1.0, 1.25,
    /// 1.5 or 1.75, so no cut of the CH 0.5 course grid passes through a
    /// vertex and every crossing is a clean interior point.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinTwoPeakNet()
    {
        double[][] field =
        {
            new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.9, 0.9, 0.9, 0.9, 0.9, 0.0 },
            new[] { 0.0, 0.9, 2.0, 0.9, 2.0, 0.9, 0.0 },
            new[] { 0.0, 0.9, 0.9, 0.9, 0.9, 0.9, 0.0 },
            new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 }
        };
        var vertices = new List<double[]>();
        for (int j = 0; j <= 4; j++)
        {
            for (int i = 0; i <= 6; i++)
                vertices.Add(new[] { (double)i, (double)j, field[j][i] });
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 4; j++)
        {
            for (int i = 0; i < 6; i++)
            {
                int a = j * 7 + i;
                faces.Add(new[] { a, a + 1, a + 8, a + 7 });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// The TWO-HUMP BARREL, whose level curves keep their COUNT and change
    /// their components. A height field on the barrel's own 7 by 5 grid of
    /// quads, row-major: the ridge along j = 2 runs the whole length of
    /// the vault and reaches both x ends, but it dips to 0.9 at x = 0,
    /// x = 3 and x = 6, leaving two humps of 2.0 between the dips:
    ///
    ///   j = 4:   0    0    0    0    0    0    0
    ///   j = 3:  0.4  0.5  0.5  0.5  0.5  0.5  0.4
    ///   j = 2:  0.9  2.0  2.0  0.9  2.0  2.0  0.9
    ///   j = 1:  0.4  0.5  0.5  0.5  0.5  0.5  0.4
    ///   j = 0:   0    0    0    0    0    0    0
    ///
    /// For h in (0.5, 0.9] the superlevel set {z at or above h} is the
    /// whole j = 2 ridge, which reaches the x = 0 and x = 6 boundary
    /// edges, so a cut at 0.75 gives the front and back open STRIPS. For
    /// h in (0.9, 2) it is the four hump vertices alone, in two groups
    /// strictly inside the mesh either side of the middle dip, so a cut
    /// at 1.0 gives two closed LOOPS, one round each hump. TWO components
    /// at both heights and not the same two, which is exactly what a
    /// count test cannot see. No vertex sits at 0.25, 0.5, 0.75, 1.0,
    /// 1.25, 1.5 or 1.75, so no cut of the CH 0.5 course grid passes
    /// through a vertex.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinTwoHumpBarrelNet()
    {
        double[][] field =
        {
            new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
            new[] { 0.4, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4 },
            new[] { 0.9, 2.0, 2.0, 0.9, 2.0, 2.0, 0.9 },
            new[] { 0.4, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4 },
            new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 }
        };
        return SkinHeightField(field);
    }

    /// <summary>
    /// The SPLIT-AND-DEATH net: one island SPLITS in the same band where
    /// another island DIES, so the count is preserved while nothing above
    /// corresponds to anything below. A height field on a 13 by 5 grid of
    /// quads, row-major, two 5-wide interior blocks either side of a zero
    /// column at i = 6:
    ///
    ///   j = 4:  0   0    0    0    0    0   0   0    0    0    0    0   0
    ///   j = 3:  0  0.6  0.6  0.6  0.6  0.6  0  0.6  0.6  0.6  0.6  0.6  0
    ///   j = 2:  0  0.6  0.6  0.6  0.6  0.6  0  0.6  2.0  0.6  2.0  0.6  0
    ///   j = 1:  0  0.6  0.6  0.6  0.6  0.6  0  0.6  0.6  0.6  0.6  0.6  0
    ///   j = 0:  0   0    0    0    0    0   0   0    0    0    0    0   0
    ///
    /// For h in (0, 0.6] the superlevel set is the two interior blocks,
    /// both strictly inside the mesh, so each of those cuts is TWO closed
    /// loops. For h in (0.6, 2) it is the two peak vertices of the RIGHT
    /// block alone: the left island has died and the right one has split
    /// in the same interval, so each of those cuts is TWO closed loops
    /// again. The counts read 2 at every one of the nine course heights,
    /// and 0.6 is not one of them.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces)
        SkinSplitAndDeathNet()
    {
        double[][] field =
        {
            new[]
            {
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            },
            new[]
            {
                0.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.0,
                0.6, 0.6, 0.6, 0.6, 0.6, 0.0
            },
            new[]
            {
                0.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.0,
                0.6, 2.0, 0.6, 2.0, 0.6, 0.0
            },
            new[]
            {
                0.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.0,
                0.6, 0.6, 0.6, 0.6, 0.6, 0.0
            },
            new[]
            {
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            }
        };
        return SkinHeightField(field);
    }

    /// <summary>
    /// The L-SHAPED shell, a NON-CONVEX plan. A height field on a 9 by 9
    /// grid of vertices whose support is the 7 by 7 interior with the
    /// top-right 3 by 3 block (i and j both 5 or more) left at zero, so
    /// the plan of every level set is an L with a re-entrant corner.
    /// Inside the support the height is 0.5 min(a_i, a_j) with
    /// a = 0, 1, 2, 3, 4, 3, 2, 1, 0 along each axis, a pyramid of ridges
    /// that reaches 2.0 at (4, 4), so the rise is the barrel's own 2 m.
    ///
    /// It is the fixture for the plan guarantee itself. Spec section 4's
    /// claim that a height-field setout cannot produce a self-crossing
    /// cell is argued from a convex picture; a re-entrant corner breaks
    /// the argument. At CH 0.5 the courses engine builds ONE cell whose
    /// plan projection self-crosses, out of 95, and at CH 0.3, 0.4,
    /// 0.45, 0.55, 0.6 and 0.7 it builds none: one bad cell out of six
    /// clean course heights, which is exactly the kind of rare breach an
    /// argued guarantee cannot see and a filter can. One bad cell is
    /// enough, because Bench Studio rejects a whole tessellation for it.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces) SkinLShapedNet()
    {
        var field = new double[9][];
        for (int j = 0; j < 9; j++)
            field[j] = new double[9];
        for (int j = 1; j <= 7; j++)
        {
            for (int i = 1; i <= 7; i++)
            {
                if (i >= 5 && j >= 5)
                    continue;
                double across = Math.Min(Math.Min(i, 8 - i), 4);
                double along = Math.Min(Math.Min(j, 8 - j), 4);
                field[j][i] = 0.5 * Math.Min(across, along);
            }
        }
        return SkinHeightField(field);
    }

    /// <summary>A height field on a unit grid of quads, row-major, the
    /// shape SkinTwoPeakNet builds by hand: vertex (i, j) sits at
    /// (i, j, field[j][i]) and face (j, i) is the quad below and left of
    /// (j + 1, i + 1), wound the same way.</summary>
    private static (double[][] Vertices, int[][] Faces) SkinHeightField(
        double[][] field)
    {
        int rows = field.Length;
        int columns = field[0].Length;
        var vertices = new List<double[]>();
        for (int j = 0; j < rows; j++)
        {
            for (int i = 0; i < columns; i++)
                vertices.Add(new[] { (double)i, (double)j, field[j][i] });
        }
        var faces = new List<int[]>();
        for (int j = 0; j + 1 < rows; j++)
        {
            for (int i = 0; i + 1 < columns; i++)
            {
                int a = j * columns + i;
                faces.Add(new[]
                {
                    a, a + 1, a + columns + 1, a + columns
                });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// SkinPatterns.ReadNet: the pure half of the ThrustMesh walk. A TNA
    /// Result's form faces come back as plain vertex and face arrays
    /// mapped through Mappings.SourceVertexToFormVertex onto the
    /// equilibrium positions, ordered by form vertex id and re-indexed
    /// into net positions; an FD Result, which carries no reciprocal
    /// block, comes back null rather than empty, so the component can say
    /// WHY there are no cells. The form ids are 10..13 ON PURPOSE,
    /// distinct from the equilibrium ids, so an engine that reads a form
    /// id as an index fails loudly here.
    ///
    /// The other half of spec section 11's FD bullet, the REMARK the
    /// component shows beside the empty outputs, is SolveInstance
    /// behaviour: it needs an IGH_DataAccess this harness has no native
    /// core to build, so the null contract measured here is the engine
    /// half and the Remark itself is read, not run, the same honest
    /// reduction ValidateExportDefaultTessellation records for
    /// FacePolylines.
    /// </summary>
    private static void ValidateSkinNet(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        MethodInfo readNet = RequirePublicStatic(patterns, "ReadNet");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType =
            RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type graphVertexType =
            RequireContractType(plugin, "TnaGraphVertexDto");
        Type graphFaceType = RequireContractType(plugin, "TnaGraphFaceDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type vertexMappingType =
            RequireContractType(plugin, "TnaSourceVertexMappingDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(1, 1, 1), P(0, 1, 1)));

        object GraphVertex(int id)
        {
            object vertex = CreateInstance(graphVertexType);
            SetContractProperty(vertex, graphVertexType, "Id", id);
            return vertex;
        }
        object face = CreateInstance(graphFaceType);
        SetContractProperty(face, graphFaceType, "Id", 0);
        SetContractProperty(
            face, graphFaceType, "Vertices", new[] { 10, 11, 12, 13 });
        object formGraph = CreateInstance(graphType);
        SetContractProperty(formGraph, graphType, "Vertices",
            Of(graphVertexType,
                GraphVertex(10), GraphVertex(11),
                GraphVertex(12), GraphVertex(13)));
        SetContractProperty(formGraph, graphType, "Faces",
            Of(graphFaceType, face));

        object Mapping(int formId, int equilibriumId)
        {
            object item = CreateInstance(vertexMappingType);
            SetContractProperty(
                item, vertexMappingType, "FormVertexId", formId);
            SetContractProperty(
                item, vertexMappingType, "EquilibriumVertexId",
                equilibriumId);
            return item;
        }
        object mappings = CreateInstance(mappingsType);
        SetContractProperty(mappings, mappingsType,
            "SourceVertexToFormVertex",
            Of(vertexMappingType,
                Mapping(10, 0), Mapping(11, 1),
                Mapping(12, 2), Mapping(13, 3)));

        object result = CreateResultDto(
            resultType, "tna", equilibrium,
            CreateInstance(graphType), CreateInstance(graphType));
        SetContractProperty(result, resultType, "FormGraph", formGraph);
        SetContractProperty(result, resultType, "Mappings", mappings);

        object? net = readNet.Invoke(null, new[] { result });
        if (net is null)
        {
            throw new InvalidOperationException(
                "A TNA Result with faces must give a net; null came back.");
        }
        IList vertices =
            (IList)net.GetType().GetProperty("Vertices")!.GetValue(net)!;
        IList faces =
            (IList)net.GetType().GetProperty("Faces")!.GetValue(net)!;
        if (vertices.Count != 4 || faces.Count != 1)
        {
            throw new InvalidOperationException(
                "Four form vertices and one face went in; " +
                $"{vertices.Count} vertices and {faces.Count} faces " +
                "came back.");
        }
        double[] second = (double[])vertices[1]!;
        if (Math.Abs(second[0] - 1.0) > 1.0e-12 ||
            Math.Abs(second[2]) > 1.0e-12)
        {
            throw new InvalidOperationException(
                "Net vertices are the EQUILIBRIUM positions in form-id " +
                "order; vertex 1 must be (1, 0, 0), got " +
                $"({second[0]}, {second[1]}, {second[2]}).");
        }
        int[] corners = (int[])faces[0]!;
        if (!corners.SequenceEqual(new[] { 0, 1, 2, 3 }))
        {
            throw new InvalidOperationException(
                "Face corners are re-indexed into net positions; got [" +
                string.Join(",", corners) + "].");
        }

        object fd = CreateResultDto(
            resultType, "fd", CreateInstance(equilibriumType), null, null);
        if (readNet.Invoke(null, new[] { fd }) is not null)
        {
            throw new InvalidOperationException(
                "An FD Result carries no faces and must give a NULL net, " +
                "so the component can name the reason.");
        }
    }

    /// <summary>
    /// The setout map (spec section 4), measured. Barrel: a cut gives two
    /// OPEN strips of length 6 whose seam is the arc midpoint, PointAt
    /// walks signed offsets from it, and Run keeps the trace vertices
    /// between its ends. Dome: cuts give CLOSED loops; the lowest loop's
    /// seam takes the trace vertex on the +X bearing from its plan
    /// centroid, the loop above PROPAGATES from it (nearest in plan), and
    /// PointAt wraps.
    /// </summary>
    private static void ValidateSkinSetout(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo traceAll = RequirePublicStatic(patterns, "TraceAll");
        MethodInfo pointAt = RequirePublicStatic(patterns, "PointAt");
        MethodInfo runMethod = RequirePublicStatic(patterns, "Run");

        object Net((double[][] Vertices, int[][] Faces) fixture) =>
            Activator.CreateInstance(
                netType, new object[] { fixture.Vertices, fixture.Faces })!;
        T Reading<T>(object curve, string name) =>
            (T)curve.GetType().GetProperty(name)!.GetValue(curve)!;
        double[] At(object curve, double u) =>
            (double[])pointAt.Invoke(null, new[] { curve, (object)u })!;

        object barrel = Net(SkinBarrelNet());
        IList levels = (IList)traceAll.Invoke(
            null, new object[] { barrel, new double[] { 0.75 } })!;
        IList strips = (IList)levels[0]!;
        if (strips.Count != 2)
        {
            throw new InvalidOperationException(
                "A cut at 0.75 crosses the tent twice, one strip each " +
                $"side of the crest; got {strips.Count} components.");
        }
        foreach (object? item in strips)
        {
            object strip = item!;
            if (Reading<bool>(strip, "Closed"))
            {
                throw new InvalidOperationException(
                    "A strip ending on the boundary is OPEN.");
            }
            if (Math.Abs(Reading<double>(strip, "Length") - 6.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "Each strip runs the full 6 m of the barrel; got " +
                    $"{Reading<double>(strip, "Length")}.");
            }
            if (Math.Abs(Reading<double>(strip, "Seam") - 3.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "An open strip's seam is its arc-length MIDPOINT, " +
                    "the centre-outward setout rule; got " +
                    $"{Reading<double>(strip, "Seam")}.");
            }
            double[] mid = At(strip, 0.0);
            if (Math.Abs(mid[0] - 3.0) > 1.0e-9 ||
                Math.Abs(mid[2] - 0.75) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "u = 0 is the seam: x 3 at the cut height; got " +
                    $"({mid[0]}, {mid[1]}, {mid[2]}).");
            }
            double[] left = At(strip, -3.0);
            double[] right = At(strip, 3.0);
            if (Math.Abs(left[0]) > 1.0e-9 ||
                Math.Abs(right[0] - 6.0) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    "u runs signed from the seam: -3 is x 0 and +3 is " +
                    $"x 6; got x {left[0]} and x {right[0]}.");
            }
        }
        IList sampled = (IList)runMethod.Invoke(
            null, new object[] { strips[0]!, -1.5, 1.5 })!;
        double[] xs = sampled.Cast<double[]>()
            .Select(p => p[0])
            .ToArray();
        double[] expectedXs = { 1.5, 2.0, 3.0, 4.0, 4.5 };
        if (xs.Length != expectedXs.Length ||
            xs.Zip(expectedXs).Any(pair =>
                Math.Abs(pair.First - pair.Second) > 1.0e-9))
        {
            throw new InvalidOperationException(
                "Run(-1.5, 1.5) keeps the trace vertices between its " +
                "ends: x 1.5, 2, 3, 4, 4.5; got [" +
                string.Join(", ", xs) + "].");
        }

        object dome = Net(SkinDomeNet());
        IList domeLevels = (IList)traceAll.Invoke(
            null, new object[] { dome, new double[] { 0.25, 0.75 } })!;
        IList lower = (IList)domeLevels[0]!;
        IList upper = (IList)domeLevels[1]!;
        if (lower.Count != 1 || upper.Count != 1)
        {
            throw new InvalidOperationException(
                "Each dome cut is ONE closed loop; got " +
                $"{lower.Count} and {upper.Count}.");
        }
        object lowerLoop = lower[0]!;
        object upperLoop = upper[0]!;
        if (!Reading<bool>(lowerLoop, "Closed") ||
            !Reading<bool>(upperLoop, "Closed"))
        {
            throw new InvalidOperationException(
                "A loop that returns to its first crossing is CLOSED.");
        }
        double expectedLower = 16.0 * 1.75 * Math.Sin(Math.PI / 8.0);
        if (Math.Abs(Reading<double>(lowerLoop, "Length") - expectedLower)
            > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The 0.25 loop is an octagon of radius 1.75: perimeter " +
                $"{expectedLower}; got " +
                $"{Reading<double>(lowerLoop, "Length")}.");
        }
        double[] lowerSeam = At(lowerLoop, 0.0);
        if (Math.Abs(lowerSeam[0] - 1.75) > 1.0e-9 ||
            Math.Abs(lowerSeam[1]) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The LOWEST loop's seam is the trace vertex on the +X " +
                "bearing from its plan centroid: (1.75, 0); got " +
                $"({lowerSeam[0]}, {lowerSeam[1]}).");
        }
        double[] upperSeam = At(upperLoop, 0.0);
        if (Math.Abs(upperSeam[0] - 1.25) > 1.0e-9 ||
            Math.Abs(upperSeam[1]) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A higher loop's seam PROPAGATES from the loop below, " +
                "nearest in plan: (1.25, 0); got " +
                $"({upperSeam[0]}, {upperSeam[1]}).");
        }
        double upperLength = Reading<double>(upperLoop, "Length");
        double[] wrapped = At(upperLoop, upperLength + 0.1);
        double[] direct = At(upperLoop, 0.1);
        if (Math.Abs(wrapped[0] - direct[0]) > 1.0e-9 ||
            Math.Abs(wrapped[1] - direct[1]) > 1.0e-9 ||
            Math.Abs(wrapped[2] - direct[2]) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A closed loop's u WRAPS: u = L + 0.1 is u = 0.1.");
        }
    }

    /// <summary>Read a SkinPatternResult's cells through reflection into
    /// plain tuples the checks can measure.</summary>
    private static (int Course, double[][] Outline, bool Clipped,
        double U0, double U1)[] SkinCells(object generated)
    {
        IList cells = (IList)generated.GetType()
            .GetProperty("Cells")!.GetValue(generated)!;
        var read = new List<(int, double[][], bool, double, double)>();
        foreach (object? item in cells)
        {
            object cell = item!;
            Type type = cell.GetType();
            IList outline =
                (IList)type.GetProperty("Outline")!.GetValue(cell)!;
            read.Add((
                (int)type.GetProperty("Course")!.GetValue(cell)!,
                outline.Cast<double[]>().ToArray(),
                (bool)type.GetProperty("Clipped")!.GetValue(cell)!,
                (double)type.GetProperty("U0")!.GetValue(cell)!,
                (double)type.GetProperty("U1")!.GetValue(cell)!));
        }
        return read.ToArray();
    }

    private static double PlanCentroidY(double[][] outline) =>
        outline.Average(point => point[1]);

    /// <summary>The engine's own plan-validity predicates,
    /// <c>SkinPatterns.PlanSelfCrosses</c> and
    /// <c>SkinPatterns.PlansOverlap</c>, resolved once in
    /// <see cref="Run"/>.</summary>
    private static MethodInfo? SkinPlanSelfCrosses;

    private static MethodInfo? SkinPlansOverlap;

    /// <summary>
    /// The height-field guarantee, asserted (spec section 4): cells set
    /// out through the map project to plan without overlap. Every
    /// outline must be SIMPLE in plan (no two non-adjacent edges
    /// properly crossing) and every pair DISJOINT (no proper edge
    /// crossing between cells, and no cell's own interior centroid
    /// strictly inside another). Touching along a shared joint edge is
    /// not overlap, so every test is strict.
    ///
    /// The arithmetic is NOT this harness's own. Both tests call the
    /// engine's public predicates, the same two methods the engines now
    /// FILTER with before they emit, so the two cannot disagree about
    /// what a bad cell is. A filter that dropped what this check would
    /// have accepted, or kept what it would have refused, would be
    /// worse than no filter at all, and a second copy of the arithmetic
    /// here is exactly how the two would drift apart. The harness's
    /// contribution is the message: WHICH cell, and against what claim.
    /// </summary>
    private static void RequireDisjointSimplePlans(
        IReadOnlyList<double[][]> outlines,
        string label)
    {
        MethodInfo? crossesMethod = SkinPlanSelfCrosses;
        MethodInfo? overlapMethod = SkinPlansOverlap;
        if (crossesMethod is null || overlapMethod is null)
        {
            throw new InvalidOperationException(
                "SkinPatterns must expose PlanSelfCrosses and " +
                "PlansOverlap publicly: the engines filter on them and " +
                "this check measures on them, and one copy of the " +
                "arithmetic is the whole point.");
        }
        bool SelfCrosses(double[][] outline) =>
            (bool)crossesMethod.Invoke(
                null, new object[] { outline })!;
        bool Overlap(double[][] first, double[][] second) =>
            (bool)overlapMethod.Invoke(
                null, new object[] { first, second })!;

        for (int at = 0; at < outlines.Count; at++)
        {
            if (SelfCrosses(outlines[at]))
            {
                throw new InvalidOperationException(
                    $"{label}: cell {at}'s plan projection " +
                    "self-crosses, which the height-field " +
                    "setout guarantees against.");
            }
        }
        for (int a = 0; a < outlines.Count; a++)
        {
            for (int b = a + 1; b < outlines.Count; b++)
            {
                if (Overlap(outlines[a], outlines[b]))
                {
                    throw new InvalidOperationException(
                        $"{label}: cells {a} and {b} overlap in plan, " +
                        "which the height-field setout guarantees " +
                        "against.");
                }
            }
        }
    }

    /// <summary>
    /// The plan guarantee is enforced, and enforcement is NOT a licence
    /// to stop caring: a fixture that was clean must go on being clean,
    /// so every clean case asserts that the engine dropped NOTHING.
    /// Without this the filter would quietly absorb a regression and
    /// ship a smaller pattern with the gate still green.
    /// </summary>
    private static void RequireNothingDropped(object generated, string label)
    {
        Type type = generated.GetType();
        int degenerate = (int)type
            .GetProperty("PlanDegenerateDropped")!.GetValue(generated)!;
        int overlap = (int)type
            .GetProperty("PlanOverlapDropped")!.GetValue(generated)!;
        if (degenerate != 0 || overlap != 0)
        {
            throw new InvalidOperationException(
                $"{label}: this pattern is clean in plan by " +
                "construction, so the plan-validity filter must drop " +
                $"NOTHING; it dropped {degenerate} self-crossing and " +
                $"{overlap} overlapping. The filter is a guarantee, not " +
                "a licence to start producing bad cells.");
        }
        string diagnostics = (string)type
            .GetProperty("Diagnostics")!.GetValue(generated)!;
        if (!diagnostics.Contains(
                "Plan-degenerate cells dropped: 0",
                StringComparison.Ordinal) ||
            !diagnostics.Contains(
                "Plan-overlap cells dropped: 0",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{label}: both drop counts are reported in the " +
                "diagnostics as their own lines, zero included, so the " +
                "guarantee is legible rather than merely true; got " +
                $"'{diagnostics}'.");
        }
    }

    /// <summary>
    /// The courses engine (spec section 5), measured joint for joint.
    /// Barrel (S 0.6, CH 0.5, four bands of the 2 m rise): every course
    /// on each strip carries the EXACT pinned joint set: even courses
    /// eleven joints at -3 + 0.6k (ten pieces of 0.6, a joint AT the
    /// seam), odd courses those shifted half a pitch plus the two strip
    /// ends (eleven pieces, the two 0.3 end pieces absorbing the phase),
    /// which pins the pitch, the phase, the truncation, the half-piece
    /// stagger and the mirror symmetry in one assertion. Dome: each
    /// closed course is round(L/S) EQUAL pieces (L from the octagon
    /// perimeter formula), rotated half a pitch on odd courses. Both:
    /// cells arrive sorted by course, outlines are real polygons, and
    /// the plan projections are pairwise disjoint and simple, the
    /// height-field guarantee. Groups are taken in ARRIVAL order, never
    /// re-sorted, so the ascending joint and span pins also assert spec
    /// section 3's within-course ordering, the studio's build sequence.
    /// BandCount's sliver-merge branch is exercised directly (a 2.05 m
    /// rise merges its 0.05 sliver, a 2.2 m rise ships its 0.2 top
    /// band). Outlines are asserted OPEN rings, first point not
    /// repeated: the closing repeat is appended by the component's
    /// ClosedOutlineCurve, which, like the C and CO tree building beside
    /// it, lives in SolveInstance and needs an IGH_DataAccess this
    /// harness cannot build, so spec section 11's "every cell closed"
    /// and "trees aligned" bullets are covered here by their engine
    /// halves (the open-ring convention pinned, one sorted cell list for
    /// both trees) and the component halves are read, not run, the
    /// ValidateExportDefaultTessellation convention.
    /// </summary>
    private static void ValidateSkinCourses(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");

        (double[][] barrelVertices, int[][] barrelFaces) = SkinBarrelNet();
        object barrelNet = Activator.CreateInstance(
            netType, new object[] { barrelVertices, barrelFaces })!;
        object generated = courses.Invoke(
            null, new object[] { barrelNet, 0.6, 0.5 })!;
        var cells = SkinCells(generated);
        int courseCount = (int)generated.GetType()
            .GetProperty("CourseCount")!.GetValue(generated)!;
        if (courseCount != 4)
        {
            throw new InvalidOperationException(
                "A 2 m rise at CH 0.5 is four courses (no sliver to " +
                $"merge); got {courseCount}.");
        }
        MethodInfo bandCount = RequirePublicStatic(patterns, "BandCount");
        int Bands(double zMax) => (int)bandCount.Invoke(
            null, new object[] { 0.0, zMax, 0.5 })!;
        if (Bands(2.05) != 4 || Bands(2.2) != 5)
        {
            throw new InvalidOperationException(
                "The sliver-merge rule: a top band whose rise is under " +
                "a quarter of CH merges into the band below (a 2.05 m " +
                "rise at CH 0.5 is FOUR bands, the 0.05 sliver merged), " +
                "while one over it ships (a 2.2 m rise is FIVE, the " +
                "0.2 top band kept).");
        }
        for (int at = 1; at < cells.Length; at++)
        {
            if (cells[at].Course < cells[at - 1].Course)
            {
                throw new InvalidOperationException(
                    "Cells arrive sorted by course then position, the " +
                    "studio's build sequence.");
            }
        }
        for (int course = 0; course < 4; course++)
        {
            foreach (bool front in new[] { true, false })
            {
                // ARRIVAL order, deliberately un-sorted: the ascending
                // joint comparison below then also asserts the
                // within-course ordering the studio's build sequence
                // depends on (the engine's ThenBy(U0)).
                var group = cells
                    .Where(cell =>
                        cell.Course == course &&
                        (PlanCentroidY(cell.Outline) < 2.0) == front)
                    .ToArray();
                double[] joints = course % 2 == 0
                    ? Enumerable.Range(0, 11)
                        .Select(k => -3.0 + 0.6 * k)
                        .ToArray()
                    : new[] { -3.0 }
                        .Concat(Enumerable.Range(0, 10)
                            .Select(k => -2.7 + 0.6 * k))
                        .Concat(new[] { 3.0 })
                        .ToArray();
                if (group.Length != joints.Length - 1)
                {
                    throw new InvalidOperationException(
                        $"Course {course} on one strip carries " +
                        $"{joints.Length - 1} pieces; got " +
                        $"{group.Length}.");
                }
                for (int at = 0; at < group.Length; at++)
                {
                    if (Math.Abs(group[at].U0 - joints[at]) > 1.0e-9 ||
                        Math.Abs(group[at].U1 - joints[at + 1]) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            "The seam-anchored pitch grid: course " +
                            $"{course} piece {at} must span " +
                            $"[{joints[at]}, {joints[at + 1]}]; got " +
                            $"[{group[at].U0}, {group[at].U1}]. Even " +
                            "courses put a joint AT the seam, odd " +
                            "courses centre a piece on it, and only " +
                            "the end pieces absorb the phase.");
                    }
                }
                foreach (var cell in group)
                {
                    if (!group.Any(other =>
                        Math.Abs(other.U0 + cell.U1) < 1.0e-9 &&
                        Math.Abs(other.U1 + cell.U0) < 1.0e-9))
                    {
                        throw new InvalidOperationException(
                            "A mirror-symmetric fixture gets " +
                            "mirror-symmetric joints: the span " +
                            $"[{cell.U0}, {cell.U1}] has no mirrored " +
                            "partner about the seam.");
                    }
                }
                bool[] clippedFlags =
                    group.Select(cell => cell.Clipped).ToArray();
                int endPieces = clippedFlags.Count(flag => flag);
                if (course % 2 == 0 ? endPieces != 0 : endPieces != 2)
                {
                    throw new InvalidOperationException(
                        "On this fixture only the odd courses' two end " +
                        $"pieces are clipped; course {course} flags " +
                        $"{endPieces}.");
                }
            }
        }
        foreach (var cell in cells)
        {
            if (cell.Outline.Length < 3)
            {
                throw new InvalidOperationException(
                    "Every cell is a real polygon of at least three " +
                    "distinct points.");
            }
            double[] first = cell.Outline[0];
            double[] last = cell.Outline[^1];
            if (Math.Abs(first[0] - last[0]) < 1.0e-9 &&
                Math.Abs(first[1] - last[1]) < 1.0e-9 &&
                Math.Abs(first[2] - last[2]) < 1.0e-9)
            {
                throw new InvalidOperationException(
                    "Engine outlines are OPEN rings: the closing repeat " +
                    "belongs to the component's ClosedOutlineCurve, and " +
                    "this pin is the convention that method depends on.");
            }
        }
        RequireDisjointSimplePlans(
            cells.Select(cell => cell.Outline).ToArray(),
            "courses/barrel");
        RequireNothingDropped(generated, "courses/barrel");
        string diagnostics = (string)generated.GetType()
            .GetProperty("Diagnostics")!.GetValue(generated)!;
        if (!diagnostics.Contains("Pattern: courses",
                StringComparison.Ordinal) ||
            !diagnostics.Contains("Boundary-clipped cells: 8",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Diagnostics name the pattern and count the clipped " +
                "cells (two odd courses, two strips, two end pieces " +
                $"each: 8); got '{diagnostics}'.");
        }

        (double[][] domeVertices, int[][] domeFaces) = SkinDomeNet();
        object domeNet = Activator.CreateInstance(
            netType, new object[] { domeVertices, domeFaces })!;
        object domeGenerated = courses.Invoke(
            null, new object[] { domeNet, 0.6, 0.5 })!;
        var domeCells = SkinCells(domeGenerated);
        int domeCourses = (int)domeGenerated.GetType()
            .GetProperty("CourseCount")!.GetValue(domeGenerated)!;
        if (domeCourses != 4)
        {
            throw new InvalidOperationException(
                $"The dome's 2 m rise at CH 0.5 is four courses; got " +
                $"{domeCourses}.");
        }
        for (int course = 0; course < 4; course++)
        {
            // ARRIVAL order here too: the indexed span pin below
            // asserts the ordering along the loop.
            var ring = domeCells
                .Where(cell => cell.Course == course)
                .ToArray();
            double midHeight = course == 3 ? 1.75 : 0.25 + 0.5 * course;
            double expectedLength =
                16.0 * (2.0 - midHeight) * Math.Sin(Math.PI / 8.0);
            int expectedPieces = Math.Max(
                1, (int)Math.Round(expectedLength / 0.6));
            if (ring.Length != expectedPieces)
            {
                throw new InvalidOperationException(
                    $"A closed course is n = max(1, round(L/S)) equal " +
                    $"pieces: course {course} (L {expectedLength:F3}) " +
                    $"must carry {expectedPieces}; got {ring.Length}.");
            }
            double pitch = expectedLength / expectedPieces;
            double expectedPhase = course % 2 == 0 ? 0.0 : pitch / 2.0;
            for (int at = 0; at < ring.Length; at++)
            {
                double expectedU0 = expectedPhase + at * pitch;
                if (Math.Abs(ring[at].U0 - expectedU0) > 1.0e-9 ||
                    Math.Abs(ring[at].U1 - ring[at].U0 - pitch) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        "A closed course is EQUAL pieces of pitch " +
                        $"{pitch:F4} in arrival order from the phase " +
                        "(rotated half a pitch on odd courses): piece " +
                        $"{at} of course {course} must span " +
                        $"[{expectedU0:F4}, {expectedU0 + pitch:F4}]; " +
                        $"got [{ring[at].U0:F4}, {ring[at].U1:F4}].");
                }
            }
        }
        RequireDisjointSimplePlans(
            domeCells.Select(cell => cell.Outline).ToArray(),
            "courses/dome");
        RequireNothingDropped(domeGenerated, "courses/dome");
    }

    /// <summary>
    /// Ruling B of the whole-branch review as item B2 corrects it,
    /// measured: a band whose level curves do not CORRESPOND one for one
    /// is REFUSED whole, named in the diagnostics, and counted, rather
    /// than filled with cells that pair curves which are not the same
    /// piece of surface.
    ///
    /// The test is of the MATCHING, not of the count. Counting is too
    /// weak, and two ordinary surfaces show it: a two-hump barrel cuts
    /// into two STRIPS low down and two hump LOOPS higher up, and a net
    /// where one island splits in the same band as another dies reads
    /// two at every height. Both are fixtures here, both keep the count
    /// at 2 throughout, and against the build before B2 both had every
    /// band built and cells laid over one another. The rule is a mutual
    /// BIJECTION under MatchBelow in both directions: no curve claimed
    /// by two, none unclaimed, the two maps inverses of each other. One
    /// test catches split, death, swap and simultaneous split-and-death.
    ///
    /// The two-peak fixture splits at z 0.9 (the derivation is in
    /// SkinTwoPeakNet: one closed loop up to 0.9, two above it).
    ///
    /// COURSES at S 0.6 and CH 0.5. A 2 m rise is four bands, and the
    /// nine traced heights are, in order, zMin + eps, 0.25, 0.5, 0.75,
    /// 1.0, 1.25, 1.5, 1.75 and zMax - eps, carrying 1, 1, 1, 1, 2, 2,
    /// 2, 2 and 2 components. Band r spans levels 2r, 2r + 1 and
    /// 2r + 2, so band 0 sees 1, 1, 1; band 1 sees 1, 1, 2; band 2 sees
    /// 2, 2, 2; band 3 sees 2, 2, 2. Exactly ONE band, band 1, is a
    /// transition, and it spans z 0.500 to z 1.000, which is what the
    /// diagnostics line must name. Courses 0, 2 and 3 still carry cells;
    /// course 1 carries none.
    ///
    /// HEXAGONAL on the same net. Its five traced heights are
    /// zMin + eps, 0.5, 1.0, 1.5 and zMax - eps, carrying 1, 1, 2, 2 and
    /// 2, so the one transition interval is again 0.500 to 1.000. A
    /// lattice cell of centre row c reaches from row c - 1 to row c + 1,
    /// that is from z 0.5(c - 1) to z 0.5(c + 1) clamped to the surface,
    /// so the interval falls inside the span of rows c = 1 (z 0 to 1.0)
    /// and c = 2 (z 0.5 to 1.5) and of no other: TWO lattice bands are
    /// refused. Their clamped centre heights are 0.5 and 1.0, which are
    /// courses 1 and 2, so the surviving cells carry courses 0 and 3
    /// alone.
    ///
    /// Neither the barrel nor the dome has a transition anywhere, so
    /// both engines must report none on them: the check that the refusal
    /// is a refusal and not a habit.
    ///
    /// Two more fixtures measure that the correspondence is a property
    /// of the GEOMETRY rather than of the world axes, which the overlap
    /// area of axis-aligned plan bounding boxes was not.
    ///
    /// The two-hump barrel TURNED 37 degrees in plan must be refused
    /// exactly as the upright one is, cell count for cell count. A
    /// rotation about world Z moves no z, no face and no traced
    /// component, so the transition is at the same heights and the
    /// refusal must be the same refusal.
    ///
    /// An ANNULAR shell, whose every cut is two NESTED closed loops,
    /// must be refused NOWHERE: nested loops correspond perfectly, outer
    /// to outer and inner to inner, and an oculus dome is an ordinary
    /// funicular form the component may not propose nothing for while
    /// stating a false reason. Box area cannot express nesting, because
    /// the outer loop's box contains the inner's; a distance can.
    ///
    /// The component's own half of the ruling, the runtime Warning that
    /// says the skin has a HOLE, lives in SolveInstance and needs an
    /// IGH_DataAccess this harness has no native core to build. What is
    /// measured here is the engine half the component reads: the
    /// TransitionBands count the Warning is raised on, and the
    /// diagnostics text the Warning points at. The Warning itself is
    /// READ, not run, the ValidateExportDefaultTessellation convention.
    /// </summary>
    private static void ValidateSkinTransitions(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");

        object Net((double[][] Vertices, int[][] Faces) fixture) =>
            Activator.CreateInstance(
                netType, new object[] { fixture.Vertices, fixture.Faces })!;
        static T Reading<T>(object generated, string name) =>
            (T)generated.GetType().GetProperty(name)!.GetValue(generated)!;

        object twoPeak = Net(SkinTwoPeakNet());

        object built = courses.Invoke(
            null, new object[] { twoPeak, 0.6, 0.5 })!;
        var cells = SkinCells(built);
        if (Reading<int>(built, "CourseCount") != 4)
        {
            throw new InvalidOperationException(
                "The two-peak net's 2 m rise at CH 0.5 is four bands; " +
                $"got {Reading<int>(built, "CourseCount")}.");
        }
        if (Reading<int>(built, "TransitionBands") != 1)
        {
            throw new InvalidOperationException(
                "Exactly one courses band, band 1, spans the split (its " +
                "three levels carry 1, 1 and 2 components); got " +
                $"{Reading<int>(built, "TransitionBands")}.");
        }
        const string CoursesLine =
            "Transition bands skipped: 1 (level curves do not correspond " +
            "between z=0.500 and z=1.000; courses cannot bond across it)";
        string diagnostics = Reading<string>(built, "Diagnostics");
        if (!diagnostics.Contains(CoursesLine, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The diagnostics must NAME the refused band and the " +
                $"heights it sits between: '{CoursesLine}'; got " +
                $"'{diagnostics}'.");
        }
        if (cells.Any(cell => cell.Course == 1))
        {
            throw new InvalidOperationException(
                "A transition band emits NO cells, so nothing may carry " +
                "course 1; a stated hole beats overlapping cells.");
        }
        foreach (int course in new[] { 0, 2, 3 })
        {
            if (!cells.Any(cell => cell.Course == course))
            {
                throw new InvalidOperationException(
                    "Only the transition band is refused: course " +
                    $"{course} must still carry cells.");
            }
        }
        RequireDisjointSimplePlans(
            cells.Select(cell => cell.Outline).ToArray(),
            "courses/two peaks");
        RequireNothingDropped(built, "courses/two peaks");

        object hexBuilt = hexagonal.Invoke(
            null, new object[] { twoPeak, 0.6, 0.5 })!;
        var hexCells = SkinCells(hexBuilt);
        if (Reading<int>(hexBuilt, "TransitionBands") != 2)
        {
            throw new InvalidOperationException(
                "Two lattice bands reach across the 0.500 to 1.000 " +
                "transition, centre rows 1 and 2; got " +
                $"{Reading<int>(hexBuilt, "TransitionBands")}.");
        }
        const string HexagonalLine =
            "Transition bands skipped: 2 (level curves do not correspond " +
            "between z=0.500 and z=1.000; hexagonal cannot bond across it)";
        string hexDiagnostics = Reading<string>(hexBuilt, "Diagnostics");
        if (!hexDiagnostics.Contains(
                HexagonalLine, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The honeycomb names its refused bands the same way: " +
                $"'{HexagonalLine}'; got '{hexDiagnostics}'.");
        }
        if (hexCells.Length == 0)
        {
            throw new InvalidOperationException(
                "Only the bands that span the split are refused; the " +
                "rest of the honeycomb still grows.");
        }
        if (hexCells.Any(cell => cell.Course == 1 || cell.Course == 2))
        {
            throw new InvalidOperationException(
                "The refused lattice rows are the ones whose clamped " +
                "centres sit at z 0.5 and z 1.0, courses 1 and 2, so no " +
                "surviving cell may carry either.");
        }
        foreach (int course in new[] { 0, 3 })
        {
            if (!hexCells.Any(cell => cell.Course == course))
            {
                throw new InvalidOperationException(
                    $"The honeycomb still carries course {course}.");
            }
        }
        RequireDisjointSimplePlans(
            hexCells.Select(cell => cell.Outline).ToArray(),
            "hexagonal/two peaks");
        RequireNothingDropped(hexBuilt, "hexagonal/two peaks");

        // ---- the refusal is a refusal, not a habit.
        foreach ((string label, (double[][], int[][]) fixture) in
                 new (string, (double[][], int[][]))[]
                 {
                     ("barrel", SkinBarrelNet()),
                     ("dome", SkinDomeNet())
                 })
        {
            object net = Net(fixture);
            foreach (MethodInfo engine in new[] { courses, hexagonal })
            {
                object plain = engine.Invoke(
                    null, new object[] { net, 0.6, 0.5 })!;
                if (Reading<int>(plain, "TransitionBands") != 0 ||
                    Reading<string>(plain, "Diagnostics").Contains(
                        "Transition bands skipped",
                        StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"The {label} keeps the same component count at " +
                        $"every height, so {engine.Name} must refuse no " +
                        "band and say nothing about transitions; it " +
                        $"reported {Reading<int>(plain, "TransitionBands")}.");
                }
            }
        }

        // ---- the two nets a COUNT test cannot see. Both hold two
        // components at every one of the nine course heights and change
        // WHAT those components are across band 1, so only the
        // correspondence catches them. Both were reproduced against the
        // build before item B2: no band refused, no warning, and cells
        // laid over one another (the two-hump barrel at S 0.6 and CH 0.5
        // gave 70 courses cells with 10 self-crossing and 166 overlapping
        // pairs, and 72 honeycomb cells with 8 and 85; the
        // split-and-death net gave 80 courses cells with 49 overlapping
        // pairs and 116 honeycomb cells with 24 self-crossing and 155).
        //
        // Both refuse the SAME band as the two-peak net, and for the same
        // arithmetic. COURSES: the nine heights are zMin + eps, 0.25,
        // 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, zMax - eps, band r spans
        // levels 2r, 2r + 1 and 2r + 2, and the change is between 0.75
        // and 1.0 on the two-hump barrel (strips become hump loops) and
        // between 0.5 and 0.75 on the split-and-death net (block loops
        // become peak loops), so band 1, spanning z 0.500 to 1.000, is
        // the one band whose three levels do not correspond.
        // HEXAGONAL: its heights are the clamped lattice rows -1 to 5,
        // which distinct gives zMin + eps, 0.5, 1.0, 1.5, zMax - eps, and
        // the consecutive pair that fails to correspond is again 0.500 to
        // 1.000. A lattice cell of centre row c reaches from
        // z 0.5(c - 1) to z 0.5(c + 1), so that interval falls inside the
        // span of rows c = 1 and c = 2 and of no other: TWO rows refused,
        // their clamped centres at z 0.5 and z 1.0, which are courses 1
        // and 2.
        // The drops are given per fixture and per engine, and what comes
        // back is what each engine BUILT, kept plus dropped, which is
        // the quantity a rotation must leave alone.
        (int CoursesBuilt, int HexagonsBuilt) RefusesTheMiddleBand(
            string label,
            (double[][] Vertices, int[][] Faces) fixture,
            (int Degenerate, int Overlap) expectedCourseDrops,
            (int Degenerate, int Overlap) expectedHexagonDrops)
        {
            (int Degenerate, int Overlap) Drops(object generated)
            {
                Type type = generated.GetType();
                return (
                    (int)type.GetProperty("PlanDegenerateDropped")!
                        .GetValue(generated)!,
                    (int)type.GetProperty("PlanOverlapDropped")!
                        .GetValue(generated)!);
            }
            void RequireDrops(
                object generated,
                string which,
                (int Degenerate, int Overlap) expected)
            {
                (int degenerate, int overlap) = Drops(generated);
                if (degenerate != expected.Degenerate ||
                    overlap != expected.Overlap)
                {
                    throw new InvalidOperationException(
                        $"{which}/{label}: the plan-validity filter is " +
                        $"pinned at {expected.Degenerate} self-crossing " +
                        $"and {expected.Overlap} overlapping cells " +
                        $"dropped; it dropped {degenerate} and " +
                        $"{overlap}.");
                }
            }

            object subject = Net(fixture);

            object byCourses = courses.Invoke(
                null, new object[] { subject, 0.6, 0.5 })!;
            var courseCells = SkinCells(byCourses);
            if (Reading<int>(byCourses, "TransitionBands") != 1)
            {
                throw new InvalidOperationException(
                    $"The {label} holds two components at every height " +
                    "and changes which two across band 1, so exactly one " +
                    "courses band is refused on the CORRESPONDENCE; got " +
                    $"{Reading<int>(byCourses, "TransitionBands")}.");
            }
            string courseText = Reading<string>(byCourses, "Diagnostics");
            if (!courseText.Contains(CoursesLine, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"The {label}'s refused courses band is named with " +
                    $"its heights: '{CoursesLine}'; got '{courseText}'.");
            }
            if (courseCells.Any(cell => cell.Course == 1))
            {
                throw new InvalidOperationException(
                    $"The {label}'s refused band emits NO cells, so " +
                    "nothing may carry course 1.");
            }
            foreach (int course in new[] { 0, 2, 3 })
            {
                if (!courseCells.Any(cell => cell.Course == course))
                {
                    throw new InvalidOperationException(
                        "Only the transition band is refused: course " +
                        $"{course} of the {label} must still carry cells.");
                }
            }
            RequireDisjointSimplePlans(
                courseCells.Select(cell => cell.Outline).ToArray(),
                $"courses/{label}");
            RequireDrops(byCourses, "courses", expectedCourseDrops);

            object byHexagons = hexagonal.Invoke(
                null, new object[] { subject, 0.6, 0.5 })!;
            var hexagons = SkinCells(byHexagons);
            if (Reading<int>(byHexagons, "TransitionBands") != 2)
            {
                throw new InvalidOperationException(
                    $"Two lattice rows of the {label} reach across the " +
                    "0.500 to 1.000 transition, centre rows 1 and 2; got " +
                    $"{Reading<int>(byHexagons, "TransitionBands")}.");
            }
            string hexagonText = Reading<string>(byHexagons, "Diagnostics");
            if (!hexagonText.Contains(
                    HexagonalLine, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"The {label}'s honeycomb names its refused rows the " +
                    $"same way: '{HexagonalLine}'; got '{hexagonText}'.");
            }
            if (hexagons.Length == 0)
            {
                throw new InvalidOperationException(
                    "Only the rows that span the change are refused; the " +
                    $"rest of the {label}'s honeycomb still grows.");
            }
            if (hexagons.Any(
                    cell => cell.Course == 1 || cell.Course == 2))
            {
                throw new InvalidOperationException(
                    "The refused lattice rows are the ones whose clamped " +
                    "centres sit at z 0.5 and z 1.0, courses 1 and 2, so " +
                    $"no surviving {label} cell may carry either.");
            }
            RequireDisjointSimplePlans(
                hexagons.Select(cell => cell.Outline).ToArray(),
                $"hexagonal/{label}");
            RequireDrops(byHexagons, "hexagonal", expectedHexagonDrops);
            return (
                courseCells.Length +
                    expectedCourseDrops.Degenerate +
                    expectedCourseDrops.Overlap,
                hexagons.Length +
                    expectedHexagonDrops.Degenerate +
                    expectedHexagonDrops.Overlap);
        }
        (int CoursesBuilt, int HexagonsBuilt) upright =
            RefusesTheMiddleBand(
                "two-hump barrel", SkinTwoHumpBarrelNet(), (0, 0), (0, 0));
        // The split-and-death HONEYCOMB's plans were left UNASSERTED in
        // the previous wave, because four of its cells self-crossed in
        // plan at the far ends of a square loop's u domain, where the
        // anti-seam cut folds the clipped outline back on itself. They
        // are asserted now: the plan-validity filter drops those four
        // before the pattern is emitted, and the four is pinned, so the
        // defect underneath is measured rather than tolerated. It is a
        // pre-existing honeycomb defect on closed level curves, not a
        // transition defect, and it belongs to the next sub-project with
        // the dome crown's.
        RefusesTheMiddleBand(
            "split-and-death", SkinSplitAndDeathNet(), (0, 0), (4, 0));

        // ---- the same two-hump barrel TURNED IN PLAN. A rotation about
        // world Z leaves every z, every face and every traced component
        // where it was, so the transition at z 0.500 to 1.000 is there at
        // every angle and the refusal must be too. Against the build
        // before this item the two-hump barrel swept 0 to 180 degrees in
        // 5 degree steps was refused at EXACTLY five angles, 0, 45, 90,
        // 135 and 180; at the other thirty-two TransitionBands came back
        // 0, no line was written, no warning fired, and the courses
        // engine emitted 84 cells with 12 to 14 self-crossing and 152 to
        // 214 overlapping pairs in plan. 37 degrees is the measured worst
        // case (13 and 183) and is the angle pinned here; the upright
        // case above pins the other alignment, so both are measured.
        //
        // What is asserted equal between the two alignments is the
        // number of cells BUILT, kept plus dropped, which is the
        // invariance itself rather than a number: a rotation cannot add
        // or remove a lattice site or a piece of a course. The cells are
        // NOT asserted cell for cell, and deliberately so. A closed
        // loop's seam falls back to the trace vertex on the +X bearing
        // from the loop's plan centroid, a stated GLOBAL rule that reads
        // the world axes on purpose (as the lowest open strip's does),
        // so turning the model moves the seam to a different vertex and
        // with it every setout coordinate of the hump loops. That is the
        // rule working: the SET of cells is a property of the geometry,
        // and where the setout starts along a closed loop is a stated
        // convention.
        //
        // Moving the seam is also why the turned fixture DROPS where the
        // upright one does not: the top course's two hump loops each end
        // up with one piece whose plan projection self-crosses, and two
        // honeycomb cells go the same way with two more overlapping. It
        // happens at 30, 37, 45, 90 and 137 degrees alike and not at 0
        // or 17. It is NOT correspondence damage: TransitionBands is 1
        // at every angle and the refused band carries no cells at any of
        // them. It is a cell-shape defect on a re-entrant closed loop,
        // the same family as the L-shaped shell's, and the filter is
        // what answers it: the plans that survive ARE asserted disjoint
        // and simple, on both engines, at both alignments.
        (int CoursesBuilt, int HexagonsBuilt) turned =
            RefusesTheMiddleBand(
                "two-hump barrel rotated 37 degrees",
                SkinRotatedInPlan(SkinTwoHumpBarrelNet(), 37.0),
                (2, 0),
                (2, 2));
        if (turned.CoursesBuilt != upright.CoursesBuilt ||
            turned.HexagonsBuilt != upright.HexagonsBuilt ||
            upright.CoursesBuilt == 0 ||
            upright.HexagonsBuilt == 0)
        {
            throw new InvalidOperationException(
                "Turning a model about world Z cannot add or remove a " +
                "cell: the two-hump barrel BUILDS " +
                $"{upright.CoursesBuilt} courses and " +
                $"{upright.HexagonsBuilt} honeycomb cells upright and " +
                $"{turned.CoursesBuilt} and {turned.HexagonsBuilt} at " +
                "37 degrees, kept plus dropped.");
        }

        // ---- the ANNULAR shell, whose every cut is two NESTED loops.
        // This is the check that would have caught a whole surface class
        // being silently refused: against the build before this item the
        // oculus dome came back with ZERO cells on both engines at every
        // course height tried, every band counted as a transition, and
        // the diagnostics asserting that the level curves do not
        // correspond when they correspond perfectly, outer to outer and
        // inner to inner (the mechanism is in SkinRingVaultNet).
        //
        // The courses count is pinned at CH 0.35, the shipped default,
        // and hand-derived here. A 2 m rise at CH 0.35 is
        // ceil(2/0.35) = 6 bands, and the top band's own rise,
        // 2 - 5 x 0.35 = 0.25, is above CH/4 = 0.0875 so no sliver
        // merges. Band r is set out on its mid height, which is
        // (r CH + bandTop)/2 with bandTop = (r + 1) CH except on the top
        // band where it is the crown: 0.175, 0.525, 0.875, 1.225, 1.575
        // and 1.875. Each mid carries TWO loops, and a regular 16-gon of
        // circumradius R has perimeter 32 R sin(pi/16) = 6.242890 R. The
        // outer and inner radii SUM to 5.0 at every height (both skirts
        // are linear in z and 4 + 1 = 3.2 + 1.8 = 2.5 + 2.5 = 5), so the
        // two perimeters of a band sum to 6.242890 x 5 = 31.214452 m and
        // L/S = 52.024 pieces. Taking the two loops separately, every
        // band's pair rounds to 52: the six pairs are (40, 12), (38, 14),
        // (36, 16), (33, 19), (30, 22) and (27, 25). 6 x 52 = 312.
        //
        // The honeycomb's count is NOT pinned: its per-row column counts
        // over two charts have no short derivation, and what this fixture
        // exists to measure is that the surface is not refused, which the
        // structural assertions carry.
        object ring = Net(SkinRingVaultNet());
        foreach (double ringHeight in new[] { 0.2, 0.35, 0.5, 0.8, 1.9 })
        {
            foreach (MethodInfo engine in new[] { courses, hexagonal })
            {
                object built2 = engine.Invoke(
                    null, new object[] { ring, 0.6, ringHeight })!;
                var ringCells = SkinCells(built2);
                if (Reading<int>(built2, "TransitionBands") != 0 ||
                    Reading<string>(built2, "Diagnostics").Contains(
                        "Transition bands skipped",
                        StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        "An annular shell's nested loops CORRESPOND, " +
                        "outer to outer and inner to inner, so " +
                        $"{engine.Name} must refuse no band of it at CH " +
                        $"{ringHeight}; it reported " +
                        $"{Reading<int>(built2, "TransitionBands")}.");
                }
                if (ringCells.Length == 0)
                {
                    throw new InvalidOperationException(
                        "An oculus dome is an ordinary funicular form " +
                        $"and {engine.Name} must propose a pattern on " +
                        $"it at CH {ringHeight}; it proposed nothing.");
                }
                if (engine == courses && ringHeight == 0.35 &&
                    ringCells.Length != 312)
                {
                    throw new InvalidOperationException(
                        "The annular shell's courses at CH 0.35 are 312 " +
                        "cells by the derivation in this check (six " +
                        "bands, each a pair of nested loops rounding to " +
                        $"52 pieces); got {ringCells.Length}.");
                }
                // The PLANS, at every one of the ten cases. The courses
                // engine drops nothing anywhere on this shell; the
                // honeycomb drops 4 self-crossing and 2 overlapping
                // cells at CH 0.5, 6 and 0 at CH 0.8 and 12 and 5 at CH
                // 1.9, and nothing at CH 0.2 or 0.35. Those are not a
                // correspondence defect: they are the same pre-existing
                // family the dome crown and the split-and-death
                // honeycomb are in, the honeycomb laying its lattice in
                // ABSOLUTE arc length across rows whose lengths differ,
                // and here the inner loop's length GROWS with height
                // while the outer's shrinks, which is the sharpest case
                // of it in the harness. Pinned as measurements, not
                // derivations, so the size of the inherited problem is
                // on the record and cannot grow unseen.
                RequireDisjointSimplePlans(
                    ringCells.Select(cell => cell.Outline).ToArray(),
                    $"{engine.Name}/ring vault CH {ringHeight}");
                (int Degenerate, int Overlap) expectedDrops =
                    engine == courses
                        ? (0, 0)
                        : ringHeight switch
                        {
                            0.5 => (4, 2),
                            0.8 => (6, 0),
                            1.9 => (12, 5),
                            _ => (0, 0)
                        };
                int ringDegenerate = Reading<int>(
                    built2, "PlanDegenerateDropped");
                int ringOverlap = Reading<int>(
                    built2, "PlanOverlapDropped");
                if (ringDegenerate != expectedDrops.Degenerate ||
                    ringOverlap != expectedDrops.Overlap)
                {
                    throw new InvalidOperationException(
                        $"{engine.Name} on the annular shell at CH " +
                        $"{ringHeight} is pinned to drop " +
                        $"{expectedDrops.Degenerate} self-crossing and " +
                        $"{expectedDrops.Overlap} overlapping cells; it " +
                        $"dropped {ringDegenerate} and {ringOverlap}.");
                }
            }
        }
    }

    /// <summary>
    /// ONE surface, FIVE meshings, ONE answer. This is the check that
    /// makes the correspondence a property of the geometry rather than
    /// of the mesh, and it is the check the previous wave's gate passed
    /// by luck.
    ///
    /// The luck, stated plainly. The correspondence scores a pair of
    /// curves by the mean distance from each sample point of one to the
    /// nearest SAMPLE POINT of the other, so its answer carries an error
    /// of about half the other curve's sample spacing. On an annular
    /// shell the outer and the inner loop of a level lie a few
    /// millionths of a metre apart at the ridge, far inside that error,
    /// so the mesh decided which loop corresponded to which. The quad
    /// ring vault is the one annular mesh whose equal sampling makes the
    /// tangential half of that error cancel, so it broke the tie
    /// correctly and the gate was green. Measured against the build
    /// before this wave, at S 0.6, courses cells kept:
    ///
    ///   CH 0.35: quad 312, triangulated 260, ridge turned 0.1 deg 312,
    ///            ridge turned 11.25 deg 260, unequal densities 261
    ///   CH 0.5:  quad 208, triangulated 156, ridge turned 0.1 deg 208,
    ///            ridge turned 11.25 deg 156, unequal densities 156
    ///   CH 1.9:  quad  52, triangulated   0, ridge turned 0.1 deg   0,
    ///            ridge turned 11.25 deg   0, unequal densities   0
    ///
    /// Five meshings of one surface, five answers, and four of them
    /// wrong, with a band or the whole shell refused and the diagnostics
    /// stating that the level curves do not correspond when they
    /// correspond perfectly, outer to outer and inner to inner. A
    /// fixture that only passes on one meshing is not a fixture.
    ///
    /// The check is in three parts.
    ///
    /// 1. THE CLASSIFICATION ITSELF. On every one of the five meshings,
    /// every mid-height level of the CH 0.35 course grid must trace TWO
    /// CLOSED components, one of nesting depth 0 and one of depth 1, and
    /// the depth-1 one must be the SHORTER. The six mid heights are
    /// hand-derived: a 2 m rise at CH 0.35 is ceil(2 / 0.35) = 6 bands,
    /// the top band's own rise 2 - 5 x 0.35 = 0.25 being above CH / 4 =
    /// 0.0875 so nothing merges, and band r is set out on
    /// (r CH + bandTop) / 2 with bandTop = (r + 1) CH except on the top
    /// band where it is the crown: 0.175, 0.525, 0.875, 1.225, 1.575 and
    /// 1.875. That the inner loop is the shorter is arithmetic and not
    /// observation: the outer and inner radii SUM to 5.0 at every height
    /// of this shell, so below the 2.5 m ridge the inner radius is under
    /// 2.5 and the outer over it, and a loop of smaller radius is a
    /// shorter loop. Asserting the depths directly is what makes the
    /// rule legible; asserting them on all five meshings is what makes
    /// it topological.
    ///
    /// 2. THE QUAD FIXTURE'S OWN COUNTS, pinned by hand. A regular
    /// 16-gon of circumradius R has perimeter 32 R sin(pi / 16) =
    /// 6.242890 R, and the two radii of a band sum to 5.0, so the two
    /// loops of any band together measure 31.214452 m, which is 52.024
    /// pieces at S 0.6; taken separately every band's pair rounds to 52.
    ///   CH 0.35, six bands: (40, 12), (38, 14), (36, 16), (33, 19),
    ///   (30, 22), (27, 25). 6 x 52 = 312.
    ///   CH 0.5, four bands with mids 0.25, 0.75, 1.25 and 1.75:
    ///   (40, 12), (36, 16), (33, 19), (28, 24). 4 x 52 = 208.
    ///   CH 1.9, ONE band: ceil(2 / 1.9) = 2 bands, and the top band's
    ///   own rise 2 - 1.9 = 0.1 is under CH / 4 = 0.475 so it merges
    ///   into the one below; the single mid is the crown-to-base
    ///   midpoint z 1.0, where the radii are 3.333333 and 1.666667 and
    ///   the perimeters 20.80963 m and 10.40482 m, giving 35 and 17.
    ///   1 x 52 = 52.
    /// The honeycomb's counts have no such derivation, so they are
    /// declared MEASUREMENTS and pinned as measurements: 252, 180 and
    /// 108 cells BUILT at the three course heights.
    ///
    /// 3. THE FOUR OTHER MESHINGS GIVE THE QUAD FIXTURE'S ANSWER. At
    /// each of the three course heights and on both engines: no band
    /// refused, nothing said about transitions, cells emitted, the plans
    /// disjoint and simple, and the number of cells BUILT, kept plus
    /// dropped, equal to the quad fixture's.
    ///
    /// BUILT and not KEPT, and the reason is the same one the rotated
    /// two-hump barrel gives. What a remeshing must not change is which
    /// curves correspond and therefore how many cells the setout lays
    /// down; WHICH of those cells the plan-validity filter then drops is
    /// a property of the pre-existing absolute-arc-length defect, which
    /// damages different cells on different meshes. The drops are pinned
    /// per meshing below so that the inherited problem stays visible and
    /// cannot grow unseen, and the courses engine is required to drop
    /// NOTHING on any of the five.
    ///
    /// ONE count moves, and it is not a defect: the unequal-density
    /// meshing's courses at CH 0.35 are 313 rather than 312, because a
    /// 32-gon inscribed in a circle is longer than a 16-gon and the
    /// third band's inner course crosses a rounding boundary. The
    /// derivation is in SkinRingVaultUnequalNet.
    /// </summary>
    private static void ValidateSkinRingVaultMeshings(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");
        MethodInfo traceAll = RequirePublicStatic(patterns, "TraceAll");

        object Net((double[][] Vertices, int[][] Faces) fixture) =>
            Activator.CreateInstance(
                netType, new object[] { fixture.Vertices, fixture.Faces })!;
        static T Reading<T>(object generated, string name) =>
            (T)generated.GetType().GetProperty(name)!.GetValue(generated)!;

        var meshings =
            new (string Label,
                 (double[][] Vertices, int[][] Faces) Fixture)[]
            {
                ("quad, 16 a ring", SkinRingVaultNet()),
                ("triangulated", SkinRingVaultTriangulatedNet()),
                ("ridge turned 0.1 degrees",
                    SkinRingVaultRidgeTurnedNet(0.1)),
                ("ridge turned 11.25 degrees",
                    SkinRingVaultRidgeTurnedNet(11.25)),
                ("rings 16/16/16/32/32", SkinRingVaultUnequalNet())
            };

        // ---- 1. the nesting depths themselves, on every meshing.
        double[] mids = { 0.175, 0.525, 0.875, 1.225, 1.575, 1.875 };
        foreach ((string label,
                  (double[][] Vertices, int[][] Faces) fixture) in meshings)
        {
            IList levels = (IList)traceAll.Invoke(
                null, new object[] { Net(fixture), mids })!;
            for (int at = 0; at < mids.Length; at++)
            {
                IList level = (IList)levels[at]!;
                if (level.Count != 2)
                {
                    throw new InvalidOperationException(
                        $"The ring vault meshed {label} cuts into two " +
                        $"nested loops at every mid height; at z {mids[at]}" +
                        $" it gave {level.Count} components.");
                }
                var depths = new List<int>();
                var lengths = new List<double>();
                foreach (object? item in level)
                {
                    object curve = item!;
                    PropertyInfo? depth =
                        curve.GetType().GetProperty("Depth");
                    if (depth is null)
                    {
                        throw new InvalidOperationException(
                            "A traced level curve must carry the NESTING " +
                            "DEPTH the correspondence classifies on: " +
                            "without it the matching falls back to a " +
                            "distance, and no distance can separate two " +
                            "loops that coincide in plan at a ridge.");
                    }
                    if (!(bool)curve.GetType()
                            .GetProperty("Closed")!.GetValue(curve)!)
                    {
                        throw new InvalidOperationException(
                            "An annular shell's level components are " +
                            "closed loops, not strips.");
                    }
                    depths.Add((int)depth.GetValue(curve)!);
                    lengths.Add((double)curve.GetType()
                        .GetProperty("Length")!.GetValue(curve)!);
                }
                int outer = depths.IndexOf(0);
                int inner = depths.IndexOf(1);
                if (outer < 0 || inner < 0)
                {
                    throw new InvalidOperationException(
                        $"The ring vault meshed {label} at z {mids[at]} " +
                        "holds an OUTER loop of nesting depth 0 and an " +
                        "INNER loop of depth 1, at every mesh density and " +
                        "every angle, because containment is topological; " +
                        $"got depths [{string.Join(",", depths)}].");
                }
                if (!(lengths[inner] < lengths[outer]))
                {
                    throw new InvalidOperationException(
                        "The depth-1 loop is the one round the oculus, so " +
                        "it is the SHORTER: the two radii of this shell " +
                        "sum to 5.0 at every height, so below the 2.5 m " +
                        $"ridge the inner is under 2.5. On {label} at z " +
                        $"{mids[at]} the depth-1 loop measured " +
                        $"{lengths[inner]} against {lengths[outer]}.");
                }
            }
        }

        // ---- 2 and 3. one answer across the five meshings.
        double[] courseHeights = { 0.35, 0.5, 1.9 };
        // The quad fixture's own counts, part 2 above. Courses derived,
        // honeycomb declared measurements.
        var pinnedBuilt = new Dictionary<(string, double), int>
        {
            { ("Courses", 0.35), 312 },
            { ("Courses", 0.5), 208 },
            { ("Courses", 1.9), 52 },
            { ("Hexagonal", 0.35), 252 },
            { ("Hexagonal", 0.5), 180 },
            { ("Hexagonal", 1.9), 108 }
        };
        // The plan-validity drops, per meshing and per course height,
        // MEASUREMENTS of the pre-existing absolute-arc-length defect
        // and not derivations. The courses engine drops nothing on any
        // of the five, which is asserted rather than tabled.
        var pinnedDrops =
            new Dictionary<(string, double), (int Degenerate, int Overlap)>
            {
                { ("quad, 16 a ring", 0.35), (0, 0) },
                { ("quad, 16 a ring", 0.5), (4, 2) },
                { ("quad, 16 a ring", 1.9), (12, 5) },
                { ("triangulated", 0.35), (1, 0) },
                { ("triangulated", 0.5), (5, 2) },
                { ("triangulated", 1.9), (12, 6) },
                { ("ridge turned 0.1 degrees", 0.35), (0, 0) },
                { ("ridge turned 0.1 degrees", 0.5), (3, 1) },
                { ("ridge turned 0.1 degrees", 1.9), (13, 5) },
                { ("ridge turned 11.25 degrees", 0.35), (2, 2) },
                { ("ridge turned 11.25 degrees", 0.5), (5, 2) },
                { ("ridge turned 11.25 degrees", 1.9), (14, 3) },
                { ("rings 16/16/16/32/32", 0.35), (0, 0) },
                { ("rings 16/16/16/32/32", 0.5), (2, 2) },
                { ("rings 16/16/16/32/32", 1.9), (12, 5) }
            };

        foreach ((string label,
                  (double[][] Vertices, int[][] Faces) fixture) in meshings)
        {
            object subject = Net(fixture);
            foreach (double courseHeight in courseHeights)
            {
                foreach (MethodInfo engine in new[] { courses, hexagonal })
                {
                    object generated = engine.Invoke(
                        null, new object[] { subject, 0.6, courseHeight })!;
                    var emitted = SkinCells(generated);
                    string text = Reading<string>(generated, "Diagnostics");
                    if (Reading<int>(generated, "TransitionBands") != 0 ||
                        text.Contains(
                            "Transition bands skipped",
                            StringComparison.Ordinal))
                    {
                        throw new InvalidOperationException(
                            $"The ring vault meshed {label} has no " +
                            "transition anywhere: a remeshing moves no " +
                            "level set, so " + engine.Name + " must " +
                            $"refuse no band of it at CH {courseHeight}; " +
                            "it reported " +
                            $"{Reading<int>(generated, "TransitionBands")}.");
                    }
                    if (emitted.Length == 0)
                    {
                        throw new InvalidOperationException(
                            $"{engine.Name} must propose a pattern on the " +
                            $"ring vault meshed {label} at CH " +
                            $"{courseHeight}; it proposed nothing.");
                    }
                    int degenerate =
                        Reading<int>(generated, "PlanDegenerateDropped");
                    int overlap = Reading<int>(generated, "PlanOverlapDropped");
                    if (engine == courses && (degenerate != 0 || overlap != 0))
                    {
                        throw new InvalidOperationException(
                            $"The courses engine is clean in plan on this " +
                            $"shell at every meshing, so it must drop " +
                            $"NOTHING on {label} at CH {courseHeight}; it " +
                            $"dropped {degenerate} and {overlap}.");
                    }
                    if (engine == hexagonal)
                    {
                        (int Degenerate, int Overlap) expected =
                            pinnedDrops[(label, courseHeight)];
                        if (degenerate != expected.Degenerate ||
                            overlap != expected.Overlap)
                        {
                            throw new InvalidOperationException(
                                $"The honeycomb on {label} at CH " +
                                $"{courseHeight} is pinned to drop " +
                                $"{expected.Degenerate} self-crossing and " +
                                $"{expected.Overlap} overlapping cells, a " +
                                "MEASUREMENT of the absolute-arc-length " +
                                "defect the next round inherits; it " +
                                $"dropped {degenerate} and {overlap}.");
                        }
                    }
                    int built = emitted.Length + degenerate + overlap;
                    int pinned = pinnedBuilt[(engine.Name, courseHeight)];
                    // The unequal-density meshing measures a LONGER inner
                    // curve, and at CH 0.35 the third band's inner course
                    // crosses a rounding boundary: 313 rather than 312,
                    // derived in SkinRingVaultUnequalNet.
                    if (label == "rings 16/16/16/32/32" &&
                        engine == courses &&
                        courseHeight == 0.35)
                    {
                        pinned = 313;
                    }
                    if (built != pinned)
                    {
                        throw new InvalidOperationException(
                            "One surface, five meshings, one answer: " +
                            $"{engine.Name} on the ring vault meshed " +
                            $"{label} at CH {courseHeight} must BUILD " +
                            $"{pinned} cells, kept plus dropped, as the " +
                            $"quad fixture does; it built {built} " +
                            $"({emitted.Length} kept, {degenerate} and " +
                            $"{overlap} dropped).");
                    }
                    RequireDisjointSimplePlans(
                        emitted.Select(cell => cell.Outline).ToArray(),
                        $"{engine.Name}/ring vault {label} CH " +
                        $"{courseHeight}");
                }
            }
        }
    }

    /// <summary>
    /// Ruling A of the whole-branch review, measured: level-curve
    /// orientation is NORMALISED after tracing and before seams, so the
    /// pattern a net produces depends on the net's geometry and not on
    /// the order its faces happen to arrive in.
    ///
    /// Three assertions, each pinning one half of the rule.
    ///
    /// 1. OPEN strips, direction. The scrambled barrel's rows are
    /// emitted so the lower half walks east to west and the upper half
    /// west to east (the derivation is in SkinBarrelScrambledNet). After
    /// normalisation every traced strip must run WEST TO EAST: first
    /// point at x = 0, last at x = 6, at BOTH 0.75 (rows 0 and 3) and
    /// 1.25 (rows 1 and 2). Without the rule the 0.75 strips come back
    /// x 6 to x 0 and the two heights disagree.
    ///
    /// 2. CLOSED loops, direction. The dome's loops are traced clockwise
    /// from its ring-major face order, and the rule turns them
    /// counter-clockwise, so the signed plan area must be POSITIVE. Its
    /// value is pinned too: a regular n-gon of circumradius R has area
    /// (1/2) n R^2 sin(2 pi / n), and the 0.25 cut of a dome whose
    /// radius at height h is 2 - h is a regular octagon of circumradius
    /// 1.75, so the area is 0.5 x 8 x 1.75^2 x sin(pi / 4) = 12.25
    /// sin(pi / 4), about 8.6621 m2. Before the fix that number came
    /// back with a minus sign.
    ///
    /// 3. The cells themselves. The courses engine on the scrambled
    /// barrel must give the ORDERED barrel's cells back, cell for cell
    /// within 1e-9: same count, same course, same clipped flag, same
    /// setout span, same outline points in the same order. The count is
    /// 84, hand-derived from the joint sets ValidateSkinCourses already
    /// pins: per strip, courses 0 and 2 carry ten 0.6 pieces each and
    /// courses 1 and 3 carry eleven each (nine 0.6 pieces plus two 0.3
    /// end pieces), 42 per strip, two strips. The plans must be
    /// disjoint and simple, and the hexagonal engine run over the same
    /// scrambled net must give its pinned 76 cells with disjoint simple
    /// plans as well: bow ties are exactly what
    /// RequireDisjointSimplePlans catches, and against the shipped code
    /// the review's verifier saw all ten cells of one band self-cross.
    ///
    /// 4. The same closed-loop rule on a model SITED away from the world
    /// origin, which is the case an uncentred shoelace breaks on. The
    /// raw sum's terms are of order d squared for a model d metres out
    /// while the answer it is asked for is the loop's own area, so the
    /// cancellation error grows with the square of the distance and a
    /// SMALL loop far out loses its sign. The dome's crown cut is that
    /// small loop: the extreme trace is pulled inside the surface by
    /// epsilon = (zMax - zMin) x 1e-6 = 2e-6 m, and the dome's radius at
    /// height h is 2 - h, so the crown loop is a regular octagon of
    /// circumradius 2e-6 m and area (1/2) x 8 x (2e-6)^2 x sin(pi / 4) =
    /// 1.131371e-11 m2. Translated by (500, 300) the raw shoelace sums
    /// terms of order 1.5e5 to reach that, which is 1e-16 of the terms
    /// and below what a double can carry: measured against the build
    /// before the fix it returned exactly 0.0, read as "not negative",
    /// left the crown loop clockwise against every loop below it, and
    /// the top band's cells came back with one self-crossing cell and
    /// three properly crossing pairs. Measured at 0, 100 and 300 m the
    /// same build was clean, so the case only appears once a studio
    /// sites its model, which an OS-gridded site does by hundreds of
    /// kilometres.
    ///
    /// The area is measured here in the CENTRED form too, because that
    /// is the only form that can read a small loop 500 m out at all; the
    /// tolerance is 1e-13 m2, hand-derived: subtracting a plan mean of
    /// order 500 leaves each coordinate carrying about 500 x 2^-52 =
    /// 1.1e-13 m of rounding, each shoelace term multiplies that by the
    /// loop's own 2e-6 m reach, and eight terms sum to about 4e-18 m2,
    /// five orders inside the tolerance. The 0.25 loop is asserted at
    /// its origin value as well, unmoved by the siting: a translation
    /// changes no area.
    /// </summary>
    private static void ValidateSkinOrientation(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo traceAll = RequirePublicStatic(patterns, "TraceAll");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");

        object Net((double[][] Vertices, int[][] Faces) fixture) =>
            Activator.CreateInstance(
                netType, new object[] { fixture.Vertices, fixture.Faces })!;
        double[][] Points(object curve) =>
            ((IList)curve.GetType().GetProperty("Points")!.GetValue(curve)!)
            .Cast<double[]>().ToArray();
        static double SignedPlanArea(double[][] points)
        {
            double twice = 0.0;
            for (int i = 0; i < points.Length; i++)
            {
                double[] a = points[i];
                double[] b = points[(i + 1) % points.Length];
                twice += a[0] * b[1] - b[0] * a[1];
            }
            return twice / 2.0;
        }
        // The same area measured from the points' own plan mean. A loop
        // sited hundreds of metres out cannot be read any other way: the
        // raw sum above returns 0.0 for the dome's crown loop at 500 m,
        // which is the defect this check exists for, so the MEASUREMENT
        // has to be centred even where the engine's rule is what is
        // under test.
        static double CentredPlanArea(double[][] points)
        {
            double cx = points.Average(point => point[0]);
            double cy = points.Average(point => point[1]);
            double twice = 0.0;
            for (int i = 0; i < points.Length; i++)
            {
                double[] a = points[i];
                double[] b = points[(i + 1) % points.Length];
                twice +=
                    (a[0] - cx) * (b[1] - cy) -
                    (b[0] - cx) * (a[1] - cy);
            }
            return twice / 2.0;
        }

        // ---- 1. open strips run one way, at every height.
        object scrambled = Net(SkinBarrelScrambledNet());
        IList levels = (IList)traceAll.Invoke(
            null,
            new object[] { scrambled, new[] { 0.75, 1.25 } })!;
        foreach (double height in new[] { 0.75, 1.25 })
        {
            IList strips =
                (IList)levels[height < 1.0 ? 0 : 1]!;
            if (strips.Count != 2)
            {
                throw new InvalidOperationException(
                    "The scrambled barrel is the SAME surface: a cut at " +
                    $"{height} still gives two strips; got {strips.Count}.");
            }
            foreach (object? item in strips)
            {
                double[][] points = Points(item!);
                if (Math.Abs(points[0][0]) > 1.0e-9 ||
                    Math.Abs(points[^1][0] - 6.0) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        "Every traced strip runs west to east once the " +
                        "direction is normalised, whatever order the " +
                        $"faces arrived in: the cut at {height} gives a " +
                        $"strip from x {points[0][0]} to x " +
                        $"{points[^1][0]}, not 0 to 6.");
                }
            }
        }

        // ---- 2. closed loops run counter-clockwise in plan.
        object dome = Net(SkinDomeNet());
        IList domeLevels = (IList)traceAll.Invoke(
            null, new object[] { dome, new[] { 0.25, 0.75 } })!;
        double expectedArea =
            0.5 * 8.0 * 1.75 * 1.75 * Math.Sin(Math.PI / 4.0);
        double area = SignedPlanArea(Points(((IList)domeLevels[0]!)[0]!));
        if (Math.Abs(area - expectedArea) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A CLOSED loop runs counter-clockwise in plan, so its " +
                "signed plan area is POSITIVE: the 0.25 cut is a regular " +
                "octagon of circumradius 1.75 and area " +
                $"{expectedArea:F6} m2; got {area:F6}.");
        }
        double upperArea =
            SignedPlanArea(Points(((IList)domeLevels[1]!)[0]!));
        if (!(upperArea > 0.0))
        {
            throw new InvalidOperationException(
                "Every closed loop is turned counter-clockwise, not just " +
                $"the lowest; the 0.75 loop's signed area is {upperArea}.");
        }

        // ---- 3. the cells are the ordered fixture's, cell for cell.
        object ordered = Net(SkinBarrelNet());
        object orderedBuilt = courses.Invoke(
            null, new object[] { ordered, 0.6, 0.5 })!;
        object scrambledBuilt = courses.Invoke(
            null, new object[] { scrambled, 0.6, 0.5 })!;
        var orderedCells = SkinCells(orderedBuilt);
        var scrambledCells = SkinCells(scrambledBuilt);
        RequireNothingDropped(orderedBuilt, "courses/barrel ordered");
        RequireNothingDropped(scrambledBuilt, "courses/barrel scrambled");
        if (orderedCells.Length != 84 ||
            scrambledCells.Length != orderedCells.Length)
        {
            throw new InvalidOperationException(
                "The barrel's courses carry 84 cells (per strip: ten 0.6 " +
                "pieces on courses 0 and 2, eleven on courses 1 and 3; " +
                "42 per strip, two strips), and the scrambled net must " +
                $"carry the same; got {orderedCells.Length} ordered and " +
                $"{scrambledCells.Length} scrambled.");
        }
        for (int at = 0; at < orderedCells.Length; at++)
        {
            var expected = orderedCells[at];
            var actual = scrambledCells[at];
            bool same =
                expected.Course == actual.Course &&
                expected.Clipped == actual.Clipped &&
                Math.Abs(expected.U0 - actual.U0) <= 1.0e-9 &&
                Math.Abs(expected.U1 - actual.U1) <= 1.0e-9 &&
                expected.Outline.Length == actual.Outline.Length;
            for (int p = 0; same && p < expected.Outline.Length; p++)
            {
                for (int c = 0; c < 3; c++)
                {
                    same &= Math.Abs(
                        expected.Outline[p][c] - actual.Outline[p][c])
                        <= 1.0e-9;
                }
            }
            if (!same)
            {
                throw new InvalidOperationException(
                    "Scrambling the face order must not move a single " +
                    $"cell: cell {at} came back as course " +
                    $"{actual.Course} spanning [{actual.U0:F4}, " +
                    $"{actual.U1:F4}] with {actual.Outline.Length} " +
                    $"points, against course {expected.Course} spanning " +
                    $"[{expected.U0:F4}, {expected.U1:F4}] with " +
                    $"{expected.Outline.Length} points on the ordered " +
                    "net.");
            }
        }
        RequireDisjointSimplePlans(
            scrambledCells.Select(cell => cell.Outline).ToArray(),
            "courses/barrel scrambled");

        object scrambledHexBuilt = hexagonal.Invoke(
            null, new object[] { scrambled, 0.6, 0.5 })!;
        var scrambledHexagons = SkinCells(scrambledHexBuilt);
        RequireNothingDropped(
            scrambledHexBuilt, "hexagonal/barrel scrambled");
        if (scrambledHexagons.Length != 76)
        {
            throw new InvalidOperationException(
                "The scrambled net grows the same honeycomb the ordered " +
                "one does, 38 cells per chart and 76 in all; got " +
                $"{scrambledHexagons.Length}.");
        }
        RequireDisjointSimplePlans(
            scrambledHexagons.Select(cell => cell.Outline).ToArray(),
            "hexagonal/barrel scrambled");

        // ---- 4. a model SITED away from the world origin keeps every
        // loop counter-clockwise, crown loop included.
        object sited = Net(SkinDomeSitedNet(500.0, 300.0));
        IList sitedLevels = (IList)traceAll.Invoke(
            null,
            new object[] { sited, new[] { 0.25, 2.0 - 2.0e-6 } })!;
        double sitedLowArea =
            CentredPlanArea(Points(((IList)sitedLevels[0]!)[0]!));
        if (Math.Abs(sitedLowArea - expectedArea) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Siting the dome 500 m east and 300 m north moves no " +
                "area and turns no loop: the 0.25 cut is still the " +
                $"counter-clockwise octagon of area {expectedArea:F6} " +
                $"m2; got {sitedLowArea:F6}.");
        }
        double crownArea =
            CentredPlanArea(Points(((IList)sitedLevels[1]!)[0]!));
        double expectedCrown =
            0.5 * 8.0 * 2.0e-6 * 2.0e-6 * Math.Sin(Math.PI / 4.0);
        if (!(crownArea > 0.0) ||
            Math.Abs(crownArea - expectedCrown) > 1.0e-13)
        {
            throw new InvalidOperationException(
                "The CROWN loop of a sited dome runs counter-clockwise " +
                "like every other: a regular octagon of circumradius " +
                "2e-6 m (the epsilon the extreme trace is pulled in by) " +
                $"and area {expectedCrown:E6} m2, POSITIVE; got " +
                $"{crownArea:E6}. An uncentred shoelace returns 0.0 " +
                "here, reads it as not negative, and leaves the crown " +
                "loop running against every loop below it.");
        }
        object sitedBuilt = courses.Invoke(
            null, new object[] { sited, 0.6, 0.5 })!;
        var sitedCells = SkinCells(sitedBuilt);
        RequireNothingDropped(sitedBuilt, "courses/dome sited 500 m out");
        if (sitedCells.Length != 42)
        {
            throw new InvalidOperationException(
                "The sited dome carries the origin dome's courses: the " +
                "mid-height loop of band r has round(L / S) pieces for " +
                "L = 16 (2 - h) sin(pi / 8), so mids at 0.25, 0.75, " +
                "1.25 and 1.75 give 18, 13, 8 and 3 pieces, 42 in all; " +
                $"got {sitedCells.Length}.");
        }
        RequireDisjointSimplePlans(
            sitedCells.Select(cell => cell.Outline).ToArray(),
            "courses/dome sited 500 m out");
    }

    /// <summary>
    /// The hexagonal engine (spec section 6), measured on the barrel,
    /// where the front strip's setout maps to x = 3 + u and z = z, so
    /// setout coordinates read straight off the geometry.
    ///
    /// The kept and clipped counts are pinned at 76 and 36, hand-derived
    /// from the lattice under Ruling D's interval-overlap membership. A
    /// candidate is a cell when its raw (u, z) extent meets the chart's
    /// interior, its u extent measured against the half-length of the
    /// level curve at its own CENTRE row (item D2's correction: the
    /// widest of the rows a candidate spans admits candidates lying
    /// wholly beyond the curve they sit on). On this fixture the
    /// correction moves NOTHING and the two numbers stand unchanged,
    /// which is itself the derivation: every level curve of a barrel
    /// chart is the whole 6 m strip, so the centre row's half-length and
    /// the widest are both 3 at every height and the two rules are the
    /// same rule here. The dome grid below is where they part.
    ///
    /// Every level curve of a barrel chart is the whole 6 m
    /// strip, so the chart's half-length is 3 at every height and the u
    /// test admits column i while |0.75 S i| - S/2 is under 3, that is
    /// |0.45 i| - 0.3 &lt; 3: i = 7 gives 2.85 and is admitted, i = 8
    /// gives 3.3 and is refused, so 15 columns, i = -7 to 7. The z test
    /// admits centre row c while CH(c + 1) is above zMin and CH(c - 1)
    /// below zMax, that is 0.5(c + 1) &gt; 0 and 0.5(c - 1) &lt; 2, so c
    /// runs 0 to 4. Since c = 1 + i + 2j, an even column carries the ODD
    /// rows of that set and an odd column the EVEN ones: the 7 even
    /// columns (0, +-2, +-4, +-6) carry rows 1 and 3, two cells each,
    /// and the 8 odd columns (+-1, +-3, +-5, +-7) carry rows 0, 2 and 4,
    /// three each. 14 + 24 = 38 per chart, 76 over the two charts.
    ///
    /// Clipped: an even column's two cells reach rows 0 and 4, whose
    /// heights clamp by only the epsilon the extreme traces are pulled
    /// in by (2e-6, under the 10-epsilon clip tolerance), and their u
    /// never passes the half-length, so none of the 14 is flagged. In
    /// the six odd columns +-1, +-3, +-5 the row-0 cell reaches row -1
    /// and the row-4 cell reaches row 5, both a clear 0.5 outside the
    /// surface, so 12 are flagged and the six row-2 cells are not. In
    /// the two rim columns +-7 the hexagon's u reaches 3.45 against a
    /// half-length of 3, so all 6 of their cells are flagged. 18 per
    /// chart, 36 over both.
    ///
    /// Course indices are asserted on UNCLIPPED and CLIPPED cells alike,
    /// under the engine's stated centre rule (the Task 3
    /// centre-for-centroid note). The clipped population splits by each
    /// outline's own height range: 16 bottom-clipped in course 0 (the
    /// six odd columns' row-0 cells plus the two rim columns', per
    /// chart), 16 top-clipped in course 3 (the row-4 cells the same
    /// way), and 4 rim cells whose outlines span z 0.5 to 1.5 in course
    /// 2 (the rim columns' row-2 cells).
    ///
    /// Ruling D's own case is pinned at the end: a CH at or above the
    /// rise, which the shipped 0.35 default reaches on any shell rising
    /// less than that, must give ONE clipped course of cells instead of
    /// nothing. It too is unmoved by the centre-row correction, and for
    /// the same reason: the chart is the epsilon-pulled base and crown,
    /// both the whole 6 m strip, so the centre row's half-length is 3
    /// like every other.
    /// </summary>
    private static void ValidateSkinHexagonal(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");

        (double[][] barrelVertices, int[][] barrelFaces) = SkinBarrelNet();
        object barrelNet = Activator.CreateInstance(
            netType, new object[] { barrelVertices, barrelFaces })!;
        object generated = hexagonal.Invoke(
            null, new object[] { barrelNet, 0.6, 0.5 })!;
        var cells = SkinCells(generated);

        if (cells.Length != 76)
        {
            throw new InvalidOperationException(
                "Every lattice site whose raw (u, z) extent meets a " +
                "chart is a cell, clipped rim cells KEPT: 14 from the " +
                "seven even columns and 24 from the eight odd ones, 38 " +
                $"per chart, 76 in all; got {cells.Length}.");
        }
        int clipped = cells.Count(cell => cell.Clipped);
        if (clipped != 36)
        {
            throw new InvalidOperationException(
                "The rim is clipped, not dropped: 12 from the six inner " +
                "odd columns and 6 from the two rim columns, 18 per " +
                $"chart, 36 in all; got {clipped}.");
        }

        // ---- one interior cell, corner by corner: column i = 1 of the
        // front chart, centre (0.45, 1.0). Its six corners in (x, z),
        // x = 3 + u on this fixture, in outline order.
        (double X, double Z)[] corners =
        {
            (3.3, 0.5), (3.6, 0.5), (3.75, 1.0),
            (3.6, 1.5), (3.3, 1.5), (3.15, 1.0)
        };
        var interior = cells.Where(cell =>
                !cell.Clipped &&
                cell.Course == 2 &&
                Math.Abs(cell.U0 - 0.15) < 1.0e-9 &&
                Math.Abs(cell.U1 - 0.75) < 1.0e-9 &&
                PlanCentroidY(cell.Outline) < 2.0)
            .ToArray();
        if (interior.Length != 1)
        {
            throw new InvalidOperationException(
                "Exactly one unclipped front-chart cell spans " +
                "[0.15, 0.75] in course 2 (the column-1 interior " +
                $"hexagon); got {interior.Length}.");
        }
        double[][] outline = interior[0].Outline;
        var where = new int[corners.Length];
        for (int c = 0; c < corners.Length; c++)
        {
            where[c] = Array.FindIndex(outline, point =>
                Math.Abs(point[0] - corners[c].X) < 1.0e-6 &&
                Math.Abs(point[2] - corners[c].Z) < 1.0e-6);
            if (where[c] < 0)
            {
                throw new InvalidOperationException(
                    "An interior cell is six-sided with the stated " +
                    "vertex offsets (S/4 and S/2 across, CH up); " +
                    $"corner ({corners[c].X}, {corners[c].Z}) is not " +
                    "in the outline.");
            }
            if (c > 0 && where[c] <= where[c - 1])
            {
                throw new InvalidOperationException(
                    "The six corners appear in outline order: bottom " +
                    "edge, east point, top edge back, west point.");
            }
        }

        // ---- lattice neighbours share edges: the column-2 cell one
        // translation (0.75 S, CH) away shares two corners with it,
        // mapped to the same 3D points.
        var neighbour = cells.Where(cell =>
                cell.Course == 3 &&
                Math.Abs(cell.U0 - 0.6) < 1.0e-9 &&
                PlanCentroidY(cell.Outline) < 2.0)
            .ToArray();
        if (neighbour.Length != 1)
        {
            throw new InvalidOperationException(
                "The (0.75 S, CH) neighbour of the interior cell " +
                "exists once, spanning [0.6, 1.2] in course 3; got " +
                $"{neighbour.Length}.");
        }
        foreach ((double x, double z) in
                 new[] { (3.75, 1.0), (3.6, 1.5) })
        {
            bool inFirst = outline.Any(point =>
                Math.Abs(point[0] - x) < 1.0e-9 &&
                Math.Abs(point[2] - z) < 1.0e-9);
            bool inSecond = neighbour[0].Outline.Any(point =>
                Math.Abs(point[0] - x) < 1.0e-9 &&
                Math.Abs(point[2] - z) < 1.0e-9);
            if (!inFirst || !inSecond)
            {
                throw new InvalidOperationException(
                    "Lattice neighbours SHARE their edge: the corner " +
                    $"({x}, {z}) must appear in both outlines, mapped " +
                    "to the same point.");
            }
        }

        // ---- course indices follow the centre bands. An unclipped
        // cell's outline mean z is its lattice centre height, give or
        // take the epsilon the extreme traces are pulled inside the
        // surface by (about 2e-6 here), so the banding slack is 1e-4:
        // far above that pull, far below the 0.25 gap to the next band.
        foreach (var cell in cells.Where(cell => !cell.Clipped))
        {
            double meanZ = cell.Outline.Average(point => point[2]);
            int band = Math.Min(3, Math.Max(0,
                (int)Math.Floor(meanZ / 0.5 + 1.0e-4)));
            if (cell.Course != band)
            {
                throw new InvalidOperationException(
                    "The course index is the band holding the cell's " +
                    $"centre height; a cell centred at z {meanZ:F3} " +
                    $"carries course {cell.Course}, not {band}.");
            }
        }

        // ---- course indices on the CLIPPED cells, the only ones where
        // the engine's centre rule and the spec's centroid wording could
        // diverge. On this fixture the clamped lattice centres give:
        // bottom-clipped cells (centre row 0, outline never above z
        // 0.5) course 0; top-clipped (centre row 4, outline never below
        // z 1.5) course 3; the u-clipped rim cells (centre row 2)
        // course 2. 16, 16 and 4 of them across both charts.
        int bottomClipped = 0;
        int topClipped = 0;
        int rimClipped = 0;
        foreach (var cell in cells.Where(cell => cell.Clipped))
        {
            double maxZ = cell.Outline.Max(point => point[2]);
            double minZ = cell.Outline.Min(point => point[2]);
            int expected;
            if (maxZ <= 0.5 + 1.0e-6)
            {
                expected = 0;
                bottomClipped++;
            }
            else if (minZ >= 1.5 - 1.0e-6)
            {
                expected = 3;
                topClipped++;
            }
            else
            {
                expected = 2;
                rimClipped++;
            }
            if (cell.Course != expected)
            {
                throw new InvalidOperationException(
                    "A clipped cell's course is the band of its " +
                    $"clamped lattice centre: expected {expected}, got " +
                    $"{cell.Course} (outline z {minZ:F3}..{maxZ:F3}).");
            }
        }
        if (bottomClipped != 16 || topClipped != 16 || rimClipped != 4)
        {
            throw new InvalidOperationException(
                "The clipped population splits 16 bottom (course 0), " +
                "16 top (course 3) and 4 rim (course 2); got " +
                $"{bottomClipped}, {topClipped} and {rimClipped}.");
        }

        RequireDisjointSimplePlans(
            cells.Select(cell => cell.Outline).ToArray(),
            "hexagonal/barrel");
        RequireNothingDropped(generated, "hexagonal/barrel");
        string diagnostics = (string)generated.GetType()
            .GetProperty("Diagnostics")!.GetValue(generated)!;
        if (!diagnostics.Contains("Pattern: hexagonal",
                StringComparison.Ordinal) ||
            !diagnostics.Contains("Boundary-clipped cells: 36",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Diagnostics name the pattern and count the clipped " +
                $"cells; got '{diagnostics}'.");
        }

        // ---- the dome: closed loops, and the only fixture here whose
        // level curves SHORTEN with height. The honeycomb is cut at the
        // meridian opposite the seam rather than wrapped (the plan's
        // Task 3 spec-deviation note). The dome's assertions are
        // otherwise STRUCTURAL: cells exist, clipped cells are kept,
        // courses are in range, plans disjoint where the guarantee
        // holds. Spec section 11's vertex-offset, neighbour-sharing and
        // course-band bullets are measured exactly on the barrel above,
        // where x = 3 + u reads the setout straight off the geometry.
        // One count IS pinned, at CH 0.5, because it is the only thing
        // in the harness that can tell item D2's centre-row membership
        // from the widest-row membership it replaced; its derivation and
        // its dependence on the anti-seam cut are written out beside it.
        //
        // Item D2 widened this from the single CH 0.5 case to a GRID of
        // course heights, so the guarantee is measured where the shipped
        // default 0.35 actually lives rather than only where it happens
        // to hold, and left two of the four unasserted because the
        // honeycomb still breached there. It no longer breaches
        // ANYWHERE, because the plan-validity filter drops what breaches
        // before it is emitted, so all four are asserted disjoint now.
        //
        // What is pinned instead is WHAT THE FILTER DROPS, which is the
        // measure of the defect underneath it. The honeycomb lays its
        // lattice in ABSOLUTE arc length across rows whose lengths
        // differ, so equal u is a different fraction of each row and the
        // cells shear until they overlap; the answer is a per-row cell
        // count, a redesign belonging to the next sub-project. On this
        // fixture the filter drops 2 self-crossing cells and no
        // overlapping one at CH 0.35, and 6 and 2 at CH 0.8, and nothing
        // at CH 0.2 or 0.5. Those four pairs are pinned as MEASUREMENTS,
        // not derivations: they are the size of the inherited problem,
        // and pinning them means it can neither grow nor be quietly
        // reintroduced elsewhere, and that the next round will see them
        // fall to zero. The measurements are tabled in
        // .superpowers/sdd/2026-08-31-skin/final-fix-report-3.md.
        (double[][] domeVertices, int[][] domeFaces) = SkinDomeNet();
        object domeNet = Activator.CreateInstance(
            netType, new object[] { domeVertices, domeFaces })!;
        foreach ((double domeHeight, int expected,
                  int expectedDegenerate, int expectedOverlap) in
                 new[]
                 {
                     (0.2, 0, 0, 0),
                     (0.35, 0, 2, 0),
                     (0.5, 38, 0, 0),
                     (0.8, 0, 6, 2)
                 })
        {
            object domeGenerated = hexagonal.Invoke(
                null, new object[] { domeNet, 0.6, domeHeight })!;
            var domeCells = SkinCells(domeGenerated);
            if (domeCells.Length == 0)
            {
                throw new InvalidOperationException(
                    $"The dome grows a honeycomb at CH {domeHeight}.");
            }
            // The one hand-derived dome count, and the assertion that
            // measures item B2's centre-row correction, because the
            // barrel cannot: on a barrel every level curve is the same
            // length so the centre row and the widest row agree, and
            // only a chart whose curves SHORTEN with height tells the
            // two rules apart.
            //
            // At S 0.6 and CH 0.5 the dome's chart is the five clamped
            // lattice heights zMin + eps, 0.5, 1.0, 1.5 and zMax - eps.
            // The cut at height h is a regular octagon of circumradius
            // 2 - h, so its perimeter is 16 (2 - h) sin(pi / 8) and its
            // half-length is 8 (2 - h) sin(pi / 8): 6.1229, 4.5922,
            // 3.0615, 1.5307 and 6.12e-6 at those five heights. The z
            // test admits centre rows 0 to 4 (row -1 lies at or below
            // the base, row 5 at or above the crown), and c = 1 + i + 2j
            // makes an even column carry the ODD rows of that set and an
            // odd column the EVEN ones. The u test admits column i while
            // |0.45 i| is under halfAtCentre + 0.3, halfAtCentre being
            // the half-length at the row's OWN clamped height:
            //   c = 0, half 6.1229, |i| up to 14, odd i: 14 columns
            //   c = 1, half 4.5922, |i| up to 10, even i: 11 columns
            //   c = 2, half 3.0615, |i| up to  7, odd i:  8 columns
            //   c = 3, half 1.5307, |i| up to  4, even i: 5 columns
            //   c = 4, half 6.1e-6, |i| up to  0, odd i:  0 columns
            // 14 + 11 + 8 + 5 + 0 = 38.
            //
            // Under the WIDEST rule the same arithmetic runs on the
            // largest half-length among rows c - 1, c and c + 1, which
            // gives 6.1229, 6.1229, 4.5922, 3.0615 and 1.5307 and so 14,
            // 15, 10, 7 and 4 columns, 50 cells. Those extra 12 are the
            // candidates that lie wholly beyond the curve they sit on,
            // and they are what the correction removes.
            //
            // The count depends on the anti-seam cut as well, a closed
            // loop's u domain running from -half to +half rather than
            // wrapping, which is the plan's Task 3 deviation and not yet
            // blessed by the spec review. If that rule moves, so does
            // this number.
            if (expected > 0 && domeCells.Length != expected)
            {
                throw new InvalidOperationException(
                    $"The dome honeycomb at CH {domeHeight} is " +
                    $"{expected} cells by the derivation in this check " +
                    "(14 + 11 + 8 + 5 + 0 columns over centre rows 0 to " +
                    $"4); got {domeCells.Length}. Measuring u against " +
                    "the widest of the rows a candidate spans instead of " +
                    "its own centre row gives 50.");
            }
            if (!domeCells.Any(cell => cell.Clipped))
            {
                throw new InvalidOperationException(
                    "The dome's rim and anti-seam cells are CLIPPED and " +
                    $"kept, not dropped, at CH {domeHeight}.");
            }
            int domeCourses = (int)domeGenerated.GetType()
                .GetProperty("CourseCount")!.GetValue(domeGenerated)!;
            foreach (var cell in domeCells)
            {
                if (cell.Outline.Length < 3 ||
                    cell.Course < 0 || cell.Course >= domeCourses)
                {
                    throw new InvalidOperationException(
                        "Every dome cell is a real polygon in a real " +
                        $"course band, at CH {domeHeight} as anywhere.");
                }
            }
            RequireDisjointSimplePlans(
                domeCells.Select(cell => cell.Outline).ToArray(),
                $"hexagonal/dome CH {domeHeight}");
            int droppedDegenerate = (int)domeGenerated.GetType()
                .GetProperty("PlanDegenerateDropped")!
                .GetValue(domeGenerated)!;
            int droppedOverlap = (int)domeGenerated.GetType()
                .GetProperty("PlanOverlapDropped")!
                .GetValue(domeGenerated)!;
            if (droppedDegenerate != expectedDegenerate ||
                droppedOverlap != expectedOverlap)
            {
                throw new InvalidOperationException(
                    "The plan-validity filter's drops on the dome " +
                    $"honeycomb at CH {domeHeight} are pinned at " +
                    $"{expectedDegenerate} self-crossing and " +
                    $"{expectedOverlap} overlapping, the measured size " +
                    "of the honeycomb's absolute-arc-length defect over " +
                    $"closed level curves; got {droppedDegenerate} and " +
                    $"{droppedOverlap}.");
            }
        }

        // ---- Ruling D: a SHALLOW shell, CH at or above the rise. The
        // barrel rises 2 m, so CH 2.0 sits exactly on the rise and CH
        // 2.5 above it; the shipped default 0.35 sits there for any
        // shell rising less than 0.35, which is why this is not an
        // exotic case. Both give a chart of just two levels, the
        // epsilon-pulled base and crown, and the interval rule then
        // admits exactly ONE centre row per column: a candidate's z
        // extent is CH either side of its centre, so with CH at or
        // above the rise row -1 lies wholly at or below the base and
        // row 2 wholly at or above the crown, leaving row 1 for the
        // even columns and row 0 for the odd ones (c = 1 + i + 2j fixes
        // the parity). The u test is the barrel's own: the chart's
        // half-length is 3 at both levels, so columns i = -7 to 7 are
        // admitted, 15 of them. 15 cells per chart, 30 over the two.
        // Every one reaches a lattice row a clear CH outside the
        // surface, so every one is CLIPPED, and a 2 m rise at CH 2.0 or
        // 2.5 is a single band, so every one carries course 0. Before
        // the interval rule this case gave ZERO cells while the courses
        // engine on the same shell built a band.
        foreach (double shallowHeight in new[] { 2.0, 2.5 })
        {
            object shallow = hexagonal.Invoke(
                null,
                new object[] { barrelNet, 0.6, shallowHeight })!;
            var shallowCells = SkinCells(shallow);
            int shallowBands = (int)shallow.GetType()
                .GetProperty("CourseCount")!.GetValue(shallow)!;
            if (shallowCells.Length != 30)
            {
                throw new InvalidOperationException(
                    $"At CH {shallowHeight}, at or above the barrel's " +
                    "2 m rise, the honeycomb is one clipped course of " +
                    "15 cells per chart, 30 in all, not nothing; got " +
                    $"{shallowCells.Length}.");
            }
            if (shallowBands != 1 ||
                shallowCells.Any(cell => cell.Course != 0))
            {
                throw new InvalidOperationException(
                    "A rise no greater than one course height is ONE " +
                    "band, so every cell carries course 0; got " +
                    $"{shallowBands} bands.");
            }
            if (shallowCells.Any(cell => !cell.Clipped))
            {
                throw new InvalidOperationException(
                    "Every shallow-shell cell reaches a lattice row a " +
                    "clear course height outside the surface, so every " +
                    "one is CLIPPED and kept.");
            }
            RequireDisjointSimplePlans(
                shallowCells.Select(cell => cell.Outline).ToArray(),
                $"hexagonal/shallow CH {shallowHeight}");
            RequireNothingDropped(
                shallow, $"hexagonal/shallow CH {shallowHeight}");
        }
    }

    /// <summary>
    /// The plan guarantee ENFORCED (spec section 4), measured on the
    /// surface that breaks the argument it used to rest on.
    ///
    /// Three parts, and the first is the one that makes the other two
    /// mean anything.
    ///
    /// 1. THE PREDICATE ITSELF. Every plan assertion in this harness now
    /// calls the engine's own PlanSelfCrosses and PlansOverlap, so the
    /// filter and the check cannot drift apart; the price is that a
    /// predicate that always answered "no" would make every plan
    /// assertion in the file vacuous and drop nothing. So the predicate
    /// is exercised on hand-built cases with hand-known answers. The bow
    /// tie (0,0), (1,0), (0,1), (1,1) crosses itself: its second edge
    /// runs along x + y = 1 and its closing edge along y = x, and those
    /// meet at (0.5, 0.5), strictly inside both, while the unit square
    /// (0,0), (1,0), (1,1), (0,1) does not. Two unit squares a clear gap
    /// apart do not overlap; two that SHARE an edge do not either, which
    /// is the whole reason the crossing test is strict, since every pair
    /// of neighbours in a course shares its joint; two offset by
    /// (0.5, 0.5) do, by a proper edge crossing; and a small square
    /// wholly inside a large one does, by containment, which no edge
    /// crossing can see.
    ///
    /// 2. THE L-SHAPED SHELL at CH 0.5, the case the argument misses
    /// (the derivation is in SkinLShapedNet). The courses engine builds
    /// 95 cells there and exactly ONE of them self-crosses in plan; the
    /// filter drops it, reports it, and hands back 94 whose plans are
    /// disjoint and simple. The 94 is 95 minus the one, and the 95 is
    /// not pinned separately because it is the arithmetic of a
    /// nine-column L nobody can read off in one line: what is pinned is
    /// the DROP, one self-crossing and no overlapping, and the fact that
    /// what remains is clean.
    ///
    /// 3. THE FILTER IS NOT A BLANKET. At CH 0.3, 0.4, 0.45, 0.55, 0.6
    /// and 0.7 the same shell drops NOTHING, which is what makes CH 0.5
    /// a defect rather than a policy, and it is the same discipline
    /// every other clean fixture in this file now keeps through
    /// RequireNothingDropped.
    ///
    /// NOT MEASURED, and the reason is the same one ValidateSkinIdentity
    /// gives: the author-facing WARNING lives in SolveInstance and needs
    /// an IGH_DataAccess this harness has no native core to build. What
    /// is measured here is the two counts the warning is raised on and
    /// the two diagnostics lines it points at. The warning's own
    /// sentence is READ, not run, and it is recorded here so a reviewer
    /// can read it beside what it claims. It is SCALED TO THE FRACTION
    /// DROPPED, because the sentence it replaced promised "a small hole
    /// where each one was" while handing back an empty tree. A
    /// HELICOIDAL shell is the case, and it was reproduced outside this
    /// harness against the built plugin: on a three-turn ramp of inner
    /// radius 1 and outer radius 2 climbing 2 m, at S 0.6, the honeycomb
    /// drops 11 of 11 at CH 0.35 and 8 of 8 at CH 0.5 and the pattern is
    /// EMPTY, while the courses engine drops 10 of 15 and 3 of 10.
    /// Dropping everything there is the right answer, a level curve that
    /// wraps not being a height field's; only the sentence was wrong.
    /// The three branches, in SkinComponent.SolveNative:
    ///   nothing survives: "NOTHING survived, so this pattern is EMPTY
    ///   and covers none of the surface."
    ///   at most a tenth dropped: "The skin has a small hole where each
    ///   one was, and the tessellation Export writes still imports."
    ///   more than a tenth: "That is N per cent of this pattern, so the
    ///   skin has a LARGE hole and it covers only part of the surface;
    ///   the tessellation Export writes still imports."
    /// and every branch is preceded by the count against the TOTAL the
    /// pattern built, "D of the B cells this pattern built were DROPPED
    /// to keep it valid in plan", so the fraction is legible whichever
    /// branch fires.
    /// </summary>
    private static void ValidateSkinPlanFilter(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo selfCrosses =
            RequirePublicStatic(patterns, "PlanSelfCrosses");
        MethodInfo overlap = RequirePublicStatic(patterns, "PlansOverlap");

        // ---- 1. the predicate, on hand-built cases.
        bool Crossing(double[][] outline) =>
            (bool)selfCrosses.Invoke(null, new object[] { outline })!;
        bool Overlapping(double[][] first, double[][] second) =>
            (bool)overlap.Invoke(null, new object[] { first, second })!;
        double[][] Square(double x, double y, double side) => new[]
        {
            new[] { x, y, 0.0 },
            new[] { x + side, y, 0.0 },
            new[] { x + side, y + side, 0.0 },
            new[] { x, y + side, 0.0 }
        };
        double[][] bowTie =
        {
            new[] { 0.0, 0.0, 0.0 },
            new[] { 1.0, 0.0, 0.0 },
            new[] { 0.0, 1.0, 0.0 },
            new[] { 1.0, 1.0, 0.0 }
        };
        if (!Crossing(bowTie))
        {
            throw new InvalidOperationException(
                "A bow tie self-crosses in plan: the engine's own " +
                "PlanSelfCrosses must say so, or every plan assertion " +
                "in this harness is vacuous and the filter drops " +
                "nothing.");
        }
        if (Crossing(Square(0.0, 0.0, 1.0)))
        {
            throw new InvalidOperationException(
                "A unit square does not self-cross, and a predicate " +
                "that says it does would empty every pattern.");
        }
        if (Overlapping(Square(0.0, 0.0, 1.0), Square(3.0, 3.0, 1.0)))
        {
            throw new InvalidOperationException(
                "Two squares a clear gap apart do not overlap.");
        }
        if (Overlapping(Square(0.0, 0.0, 1.0), Square(1.0, 0.0, 1.0)))
        {
            throw new InvalidOperationException(
                "Two squares SHARING an edge do not overlap: every " +
                "pair of neighbours in a course shares its joint, which " +
                "is why the crossing test is strict.");
        }
        if (!Overlapping(Square(0.0, 0.0, 1.0), Square(0.5, 0.5, 1.0)))
        {
            throw new InvalidOperationException(
                "Two squares offset by half their side overlap, by a " +
                "proper edge crossing.");
        }
        if (!Overlapping(Square(0.0, 0.0, 4.0), Square(1.0, 1.0, 1.0)))
        {
            throw new InvalidOperationException(
                "A square wholly INSIDE another overlaps it, and no " +
                "edge crossing can see that: containment is the case " +
                "the interior-point test exists for.");
        }

        // ---- 2 and 3. the L-shaped shell.
        (double[][] vertices, int[][] faces) = SkinLShapedNet();
        object net = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        object built = courses.Invoke(
            null, new object[] { net, 0.6, 0.5 })!;
        var cells = SkinCells(built);
        int degenerate = (int)built.GetType()
            .GetProperty("PlanDegenerateDropped")!.GetValue(built)!;
        int dropped = (int)built.GetType()
            .GetProperty("PlanOverlapDropped")!.GetValue(built)!;
        if (degenerate != 1 || dropped != 0)
        {
            throw new InvalidOperationException(
                "A non-convex L-shaped shell at CH 0.5 builds exactly " +
                "ONE courses cell whose plan projection self-crosses, " +
                "and the filter drops it: 1 self-crossing and 0 " +
                $"overlapping; got {degenerate} and {dropped}.");
        }
        if (cells.Length != 94)
        {
            throw new InvalidOperationException(
                "95 cells built less the one dropped leaves 94; got " +
                $"{cells.Length}.");
        }
        string diagnostics = (string)built.GetType()
            .GetProperty("Diagnostics")!.GetValue(built)!;
        if (!diagnostics.Contains(
                "Plan-degenerate cells dropped: 1",
                StringComparison.Ordinal) ||
            !diagnostics.Contains(
                "Plan-overlap cells dropped: 0",
                StringComparison.Ordinal) ||
            !diagnostics.Contains("Cells: 94", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A dropped cell is never silent: both counts are their " +
                "own diagnostics lines and the cell count is the " +
                $"SURVIVORS'; got '{diagnostics}'.");
        }
        RequireDisjointSimplePlans(
            cells.Select(cell => cell.Outline).ToArray(),
            "courses/L-shaped shell CH 0.5");

        foreach (double height in
                 new[] { 0.3, 0.4, 0.45, 0.55, 0.6, 0.7 })
        {
            object clean = courses.Invoke(
                null, new object[] { net, 0.6, height })!;
            RequireNothingDropped(
                clean, $"courses/L-shaped shell CH {height}");
            RequireDisjointSimplePlans(
                SkinCells(clean).Select(cell => cell.Outline).ToArray(),
                $"courses/L-shaped shell CH {height}");
        }
    }

    /// <summary>
    /// The floors, engine level (spec section 3): S and CH refuse below
    /// 1 mm through the negated-comparison guard, so NaN is refused too.
    /// The component floors CH with a warning before calling; the engine
    /// refusal is what the harness can measure.
    /// </summary>
    private static void ValidateSkinGuards(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");

        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        object net = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;

        void MustRefuse(MethodInfo engine, double size,
            double courseHeight, string expectedFragment)
        {
            try
            {
                engine.Invoke(
                    null, new object[] { net, size, courseHeight });
            }
            catch (TargetInvocationException wrapped)
                when (wrapped.InnerException is ArgumentException inner &&
                      inner.Message.Contains(
                          expectedFragment, StringComparison.Ordinal))
            {
                return;
            }
            throw new InvalidOperationException(
                $"{engine.Name}({size}, {courseHeight}) must refuse " +
                $"with '{expectedFragment}'.");
        }

        MustRefuse(courses, 0.0, 0.35, "S must be greater than 1 mm");
        MustRefuse(courses, double.NaN, 0.35,
            "S must be greater than 1 mm");
        MustRefuse(courses, 0.6, 0.0005,
            "Course Height must be greater than 1 mm");
        MustRefuse(hexagonal, -1.0, 0.35,
            "S must be greater than 1 mm");
        MustRefuse(hexagonal, 0.6, double.NaN,
            "Course Height must be greater than 1 mm");
    }

    /// <summary>
    /// The one-component identity (spec section 2): the old Skin GUID is
    /// KEPT, so a saved definition's Skin placement becomes the new
    /// component under the ports-moved warning rather than an orphan; the
    /// Armadillo Dual GUID retires and no component may ever carry it;
    /// the Pattern input offers the three-entry value list the way
    /// Columns' Type does, defaulting to courses; and the outputs are
    /// VISIBLE, the proposer convention, because seeing the pattern the
    /// moment it computes is the point of the component.
    ///
    /// The last pin here is the PREMISE of Ruling C: Skin is a
    /// GH_TaskCapableComponent, and that base indexes its TaskList BY
    /// ITERATION. What follows from it cannot be measured in this
    /// harness, and it is worth saying plainly WHICH parts are read
    /// rather than run, the ValidateExportDefaultTessellation
    /// convention:
    ///
    /// NOT MEASURED, read in SkinComponent.SolveInstance instead. In the
    /// pre phase, EVERY iteration now adds to TaskList: the force-
    /// aligned pattern adds the real dispatch, and both the paths that
    /// dispatch nothing, the TryReadInputs failure and any Pattern other
    /// than 2, add the completed null-carrying placeholder NoTask
    /// returns, so an iteration's index into the list is its own. In the
    /// post phase the guard before the synchronous recompute now reads
    /// "!haveTaskResult || taskResult is null || taskResult.Error is
    /// OperationCanceledException", so a placeholder retrieved for an
    /// iteration whose Pattern changed to 2 between the phases is a MISS
    /// and not an empty result. Both halves need an IGH_DataAccess with
    /// a real iteration index and a running Grasshopper solution, which
    /// this harness has no native core to build. A single-item pattern-2
    /// solve is unchanged by either half: it dispatches at iteration 0
    /// and retrieves a real, non-null result at iteration 0, exactly as
    /// the retired ArmadilloDualComponent did at base 405ff14.
    /// </summary>
    private static void ValidateSkinIdentity(Assembly plugin)
    {
        Type skin = RequireComponentType(plugin, "SkinComponent");
        var keptGuid = new Guid("7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063");
        var retiredGuid = new Guid("51f4ade8-f918-4455-9823-563afbf201f4");

        if (plugin.GetType(
                "Ananke.COMPAS.Native.Components.ArmadilloDualComponent")
            is not null)
        {
            throw new InvalidOperationException(
                "ArmadilloDualComponent is retired; its class must not " +
                "exist.");
        }

        object instance = Activator.CreateInstance(skin)
            ?? throw new InvalidOperationException(
                "Could not construct SkinComponent.");
        try
        {
            Guid guid = (Guid)skin.GetProperty("ComponentGuid")!
                .GetValue(instance)!;
            if (guid != keptGuid)
            {
                throw new InvalidOperationException(
                    "Skin keeps the OLD Skin's GUID " +
                    $"{keptGuid}, so saved placements load; got {guid}.");
            }

            foreach (Type componentType in GetLoadableTypes(plugin)
                .Where(IsConcretePublicGrasshopperComponent))
            {
                object other = Activator.CreateInstance(componentType)!;
                try
                {
                    Guid otherGuid = (Guid)componentType
                        .GetProperty("ComponentGuid")!.GetValue(other)!;
                    if (otherGuid == retiredGuid)
                    {
                        throw new InvalidOperationException(
                            $"{componentType.Name} carries the RETIRED " +
                            "Armadillo Dual GUID, which is never " +
                            "reused.");
                    }
                }
                finally
                {
                    if (other is IDisposable disposableOther)
                        disposableOther.Dispose();
                }
            }

            // ---- the Pattern value list, the Columns Type mechanism.
            // DeclaredOnly on the component type itself: the pin is that
            // SkinComponent OVERRIDES the base's empty list.
            PropertyInfo listsProperty = skin.GetProperty(
                "SuggestedValueLists",
                BindingFlags.Instance | BindingFlags.NonPublic |
                BindingFlags.DeclaredOnly)
                ?? throw new InvalidOperationException(
                    "SkinComponent must OVERRIDE SuggestedValueLists " +
                    "with the Pattern list, the Columns Type mechanism.");
            IList specs = (IList)listsProperty.GetValue(instance)!;
            if (specs.Count != 1)
            {
                throw new InvalidOperationException(
                    $"One suggested list, Pattern; got {specs.Count}.");
            }
            object spec = specs[0]!;
            Type specType = spec.GetType();
            int inputIndex =
                (int)specType.GetProperty("InputIndex")!.GetValue(spec)!;
            string name =
                (string)specType.GetProperty("Name")!.GetValue(spec)!;
            string fallback = (string)specType
                .GetProperty("DefaultValue")!.GetValue(spec)!;
            IList items =
                (IList)specType.GetProperty("Items")!.GetValue(spec)!;
            string[] labels = items.Cast<object>()
                .Select(item => (string)item.GetType()
                    .GetField("Item1")!.GetValue(item)!)
                .ToArray();
            string[] values = items.Cast<object>()
                .Select(item => (string)item.GetType()
                    .GetField("Item2")!.GetValue(item)!)
                .ToArray();
            string[] expectedLabels =
            {
                "0 · courses", "1 · hexagonal", "2 · force aligned"
            };
            if (inputIndex != 1 ||
                !string.Equals(name, "Pattern", StringComparison.Ordinal) ||
                !string.Equals(fallback, "0", StringComparison.Ordinal) ||
                !labels.SequenceEqual(expectedLabels, StringComparer.Ordinal) ||
                !values.SequenceEqual(
                    new[] { "0", "1", "2" }, StringComparer.Ordinal))
            {
                throw new InvalidOperationException(
                    "The Pattern list pins: input 1, named Pattern, " +
                    "default 0, items '0 · courses', '1 · hexagonal', " +
                    "'2 · force aligned' with values 0, 1, 2. Got " +
                    $"index {inputIndex}, name '{name}', default " +
                    $"'{fallback}', labels [{string.Join(", ", labels)}].");
            }

            // ---- VISIBLE outputs, the proposer convention.
            object server =
                skin.GetProperty("Params")!.GetValue(instance)!;
            IEnumerable outputs = (IEnumerable)server.GetType()
                .GetProperty("Output")!.GetValue(server)!;
            int outputCount = 0;
            foreach (object? output in outputs)
            {
                outputCount++;
                PropertyInfo? hidden =
                    output!.GetType().GetProperty("Hidden");
                if (hidden is not null &&
                    hidden.GetValue(output) is bool isHidden && isHidden)
                {
                    throw new InvalidOperationException(
                        "Skin is a PROPOSER: no output starts Hidden; " +
                        "seeing the pattern the moment it computes is " +
                        "the point of the component.");
                }
            }
            if (outputCount != 4)
            {
                throw new InvalidOperationException(
                    $"Four outputs (C, CO, FL, D); got {outputCount}.");
            }

            // ---- Ruling C's premise. Everything the ruling turns on is
            // that this base indexes TaskList by ITERATION; the two
            // halves of the fix are read in the doc comment above.
            bool taskCapable = false;
            for (Type? at = skin; at is not null; at = at.BaseType)
            {
                taskCapable |= at.Name.StartsWith(
                    "GH_TaskCapableComponent", StringComparison.Ordinal);
            }
            if (!taskCapable)
            {
                throw new InvalidOperationException(
                    "Skin is a GH_TaskCapableComponent: its TaskList is " +
                    "indexed by iteration, which is why every iteration " +
                    "has to add to it, dispatching or not.");
            }
        }
        finally
        {
            if (instance is IDisposable disposable)
                disposable.Dispose();
        }
    }

    private static Type RequireComponentType(Assembly plugin, string typeName)
    {
        const string ComponentsNamespace = "Ananke.COMPAS.Native.Components";
        return plugin.GetType($"{ComponentsNamespace}.{typeName}", throwOnError: true)
            ?? throw new InvalidOperationException(
                $"Type '{ComponentsNamespace}.{typeName}' was not found.");
    }

    /// <summary>
    /// Finding 1 of the 2026-08-20 plugin sweep: a negative Courses value
    /// becomes a "c-1p0"-style key deep in the studio's
    /// tessellation.from_document import (which pins course &gt;= 0 and
    /// refuses it), so ExportComponent now catches it itself, naming
    /// every offending index and value. <c>SolveInstance</c> needs a live
    /// <c>IGH_DataAccess</c>/Grasshopper document this harness never
    /// launches (it never calls SolveInstance on anything, only
    /// constructors and static contract methods), so the standalone
    /// guard behind that check -- <c>HasNegativeCourse</c> -- is as far
    /// as this repo's reflection-based pattern reaches; the component
    /// wiring around it (AddRuntimeMessage, "no file written") is not
    /// exercised here.
    /// </summary>
    private static void ValidateExportCoursesValidation(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        MethodInfo method = exportType.GetMethod(
            "HasNegativeCourse",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.HasNegativeCourse was not found.");

        object?[] negativeArgs = { new List<int> { 0, -1, 2, -3 }, null };
        var flagged = (bool)method.Invoke(null, negativeArgs)!;
        var detail = (string)negativeArgs[1]!;
        if (!flagged)
        {
            throw new InvalidOperationException(
                "HasNegativeCourse did not flag a Courses list containing " +
                "negative values.");
        }
        if (!detail.Contains("index 1 = -1", StringComparison.Ordinal) ||
            !detail.Contains("index 3 = -3", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "HasNegativeCourse did not name every offending index " +
                $"and value; received '{detail}'.");
        }

        object?[] validArgs = { new List<int> { 0, 1, 2 }, null };
        var flaggedValid = (bool)method.Invoke(null, validArgs)!;
        if (flaggedValid)
        {
            throw new InvalidOperationException(
                "HasNegativeCourse flagged a Courses list with no " +
                "negative values.");
        }
    }

    /// <summary>
    /// Finding 2 of the 2026-08-20 plugin sweep: BuildTessellationJson now
    /// serialises through the shared ContractJson.Options rather than
    /// default JsonSerializer options. Every field in this payload is
    /// non-null and every key is already a camelCase literal, so no
    /// option ContractJson.Options sets actually changes a byte for this
    /// shape (confirmed separately, outside this harness, by comparing
    /// the built .gha's output before and after the change); what this
    /// asserts is that the exact schema the studio's
    /// tessellation.from_document expects -- key/course/outline per
    /// cell, the bench.tessellation/1 envelope -- still comes out
    /// byte-for-byte as written.
    /// </summary>
    private static void ValidateExportTessellationJsonOptions(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        Type cellType = RequireComponentType(plugin, "TessellationCell");
        MethodInfo method = exportType.GetMethod(
            "BuildTessellationJson",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.BuildTessellationJson was not found.");

        var outline = new List<double[]>
        {
            new[] { 0.0, 0.0 },
            new[] { 1.0, 0.0 },
            new[] { 0.0, 1.0 }
        };
        object cell = Activator.CreateInstance(cellType, 0, outline)
            ?? throw new InvalidOperationException(
                $"Could not construct {cellType.FullName}.");
        Type cellListType = typeof(List<>).MakeGenericType(cellType);
        object cellList = Activator.CreateInstance(cellListType)
            ?? throw new InvalidOperationException(
                $"Could not construct {cellListType.FullName}.");
        MethodInfo addMethod = cellListType.GetMethod("Add")
            ?? throw new InvalidOperationException(
                $"{cellListType.FullName} does not expose Add.");
        addMethod.Invoke(cellList, new[] { cell });

        var json =
            method.Invoke(null, new object[] { cellList, 1.0, "authored" })
                as string
            ?? throw new InvalidOperationException(
                "BuildTessellationJson returned an unexpected type.");
        const string expected =
            "{\"schema\":\"bench.tessellation/1\",\"units\":\"m\"," +
            "\"domain\":\"plan\",\"pattern\":\"authored\",\"cells\":[" +
            "{\"key\":\"c0p0\",\"course\":0," +
            "\"outline\":[[0,0],[1,0],[0,1]]}]}";
        if (!string.Equals(json, expected, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "BuildTessellationJson output changed shape; expected " +
                $"'{expected}', received '{json}'.");
        }

        // A millimetre document. The sidecar declares metres and the
        // studio reads metres only, refusing any other declaration
        // outright, so the corners have to BE metres by the time they
        // are written. Before this factor existed the component wrote
        // document coordinates under a metre label, which the studio
        // accepts without complaint and reads a thousand times too
        // large: the one shape of unit error that never raises.
        var millimetres =
            method.Invoke(null, new object[] { cellList, 0.001, "authored" })
                as string
            ?? throw new InvalidOperationException(
                "BuildTessellationJson returned an unexpected type.");
        const string expectedMillimetres =
            "{\"schema\":\"bench.tessellation/1\",\"units\":\"m\"," +
            "\"domain\":\"plan\",\"pattern\":\"authored\",\"cells\":[" +
            "{\"key\":\"c0p0\",\"course\":0," +
            "\"outline\":[[0,0],[0.001,0],[0,0.001]]}]}";
        if (!string.Equals(millimetres, expectedMillimetres, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "BuildTessellationJson did not convert document units to " +
                $"metres; expected '{expectedMillimetres}', received " +
                $"'{millimetres}'.");
        }
    }

    /// <summary>
    /// <c>ExportComponent.ChooseCells</c> and the JSON the default cells
    /// make: where a tessellation comes from when nobody wired one.
    ///
    /// The rule of spec section 4. Wired cells always win, whatever the
    /// Result carries. With no cells wired and faces on the Result, Export
    /// tessellates the faces itself, one cell per face in face order at
    /// course 0, so the sidecar is there for every TNA Result and the
    /// studio's build animation has something to draw even before anyone
    /// authors a pattern. With neither there is no sidecar. Courses wired
    /// alone is ignored, with a remark, because a course belongs to a cell
    /// and there are no authored cells for it to belong to.
    ///
    /// Split for the same reason FrameGeometry is: the decision is
    /// arithmetic and runs here, while the faces themselves are a Rhino mesh
    /// this process has no Rhino for. The cells the decision leads to are
    /// measured through DefaultTessellationCells, which takes plain corner
    /// points, and then through BuildTessellationJson, which is the code
    /// that actually writes them.
    ///
    /// One half stays unmeasured and cannot be measured here: the plumbing
    /// between the two, which rebuilds the thrust mesh, asks
    /// SkinComponent.FacePolylines for one closed polyline per face and
    /// reads the corners back off it. That needs a Mesh, a Curve and an
    /// IGH_DataAccess, and this harness has RhinoCommon's structs but no
    /// native core to build any of them with, so deleting the Faces branch
    /// of TryReadInputs would leave this check green. Read, not run.
    /// </summary>
    private static void ValidateExportDefaultTessellation(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        MethodInfo choose = RequireStatic(exportType, "ChooseCells");
        string Source(int cells, int courses, int faces, out string? remark)
        {
            object?[] arguments = { cells, courses, faces, null };
            object verdict = choose.Invoke(null, arguments)
                ?? throw new InvalidOperationException("ChooseCells returned null.");
            remark = arguments[3] as string;
            return verdict.ToString() ?? string.Empty;
        }
        // The verdict's own consequence: which word the sidecar's "pattern"
        // key carries. Separate from ChooseCells so both halves can be
        // driven here, because the plumbing between them lives in
        // TryReadInputs, which needs a Rhino curve and an IGH_DataAccess.
        MethodInfo patternFor = RequireStatic(exportType, "PatternFor");
        Type cellSourceType = choose.ReturnType;
        string PatternOf(string verdict) =>
            patternFor.Invoke(
                null,
                new[] { Enum.Parse(cellSourceType, verdict) }) as string
            ?? throw new InvalidOperationException(
                "PatternFor returned an unexpected type.");
        if (PatternOf("Wired") != "authored" || PatternOf("Faces") != "faces")
        {
            throw new InvalidOperationException(
                "Cells somebody wired were AUTHORED and the Result's own "
                + "faces were not; the studio reads that key to know whether "
                + "a cutting pattern was ever chosen, and the fallback "
                + "claiming authorship is the one lie it cannot detect. Got "
                + $"'{PatternOf("Wired")}' and '{PatternOf("Faces")}'.");
        }

        if (Source(12, 12, 400, out string? wiredRemark) != "Wired" ||
            wiredRemark is not null)
        {
            throw new InvalidOperationException(
                "Cells wired always win, however many faces the Result "
                + "carries, and nothing is remarked on.");
        }
        if (Source(0, 0, 400, out string? facesRemark) != "Faces" ||
            facesRemark is not null)
        {
            throw new InvalidOperationException(
                "With no cells wired and faces on the Result, Export "
                + "tessellates the faces itself.");
        }
        if (Source(0, 0, 0, out _) != "None")
        {
            throw new InvalidOperationException(
                "No cells and no faces is no tessellation: an FD Result "
                + "carries no faces and gets the contract and the compas "
                + "document alone.");
        }
        if (Source(0, 7, 400, out string? ignored) != "Faces" ||
            ignored is null ||
            !ignored.Contains("Courses", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Courses wired with no Cells is IGNORED and said out loud, "
                + "because a course belongs to a cell and the default "
                + $"tessellation is course 0 throughout; got '{ignored}'.");
        }
        if (Source(0, 7, 0, out string? silent) != "None" ||
            silent is not null)
        {
            throw new InvalidOperationException(
                "Courses wired against a Result with no faces at all earns "
                + "no remark: the remark describes the tessellation Export "
                + "would have built from the faces, and on this path it "
                + $"builds none; got '{silent}'.");
        }

        // The cells the Faces verdict leads to, through the code that
        // builds them. Four faces of a Result's own mesh are handed over,
        // each as the closed ring FacePolylines makes (the closing repeat
        // is dropped here, as the sidecar wants). Point3d is a plain
        // struct and needs no native core, which is why this seam takes
        // corners rather than the polylines themselves.
        //
        // The SECOND face is vertical in plan: three distinct corners in
        // space, one corner in plan. Nobody wired it, and nobody asked for
        // this tessellation at all, so it is SKIPPED and counted, never an
        // error. Before this the whole export went down with it: the
        // contract, the COMPAS document, the columns mesh, the disk write
        // and the live push, on a solve with an empty Cells port.
        MethodInfo build = exportType.GetMethod(
            "BuildTessellationJson",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.BuildTessellationJson was not found.");
        MethodInfo defaults =
            RequireStatic(exportType, "DefaultTessellationCells");
        Type faceType = defaults.GetParameters()[0].ParameterType
            .GetGenericArguments()[0];
        Type point3d = faceType.GetElementType()
            ?? throw new InvalidOperationException(
                "DefaultTessellationCells takes something other than arrays "
                + "of points per face.");
        Array faces = Array.CreateInstance(faceType, 4);
        void Face(int slot, params (double X, double Y, double Z)[] corners)
        {
            Array face = Array.CreateInstance(point3d, corners.Length);
            for (int corner = 0; corner < corners.Length; corner++)
            {
                face.SetValue(
                    Activator.CreateInstance(
                        point3d,
                        corners[corner].X,
                        corners[corner].Y,
                        corners[corner].Z),
                    corner);
            }
            faces.SetValue(face, slot);
        }
        Face(0, (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0));
        Face(1, (9, 9, 0), (9, 9, 1), (9, 9, 2), (9, 9, 0));
        Face(2, (1, 0, 0), (2, 0, 0), (1, 1, 0), (1, 0, 0));
        Face(3, (2, 0, 0), (3, 0, 0), (2, 1, 0), (2, 0, 0));
        object?[] defaultArguments = { faces, null };
        object cellList = defaults.Invoke(null, defaultArguments)
            ?? throw new InvalidOperationException(
                "DefaultTessellationCells returned null.");
        var skipped = (int)defaultArguments[1]!;
        if (skipped != 1)
        {
            throw new InvalidOperationException(
                "The one face that will not reduce to three distinct plan "
                + "corners is skipped and counted, and the other three "
                + $"survive; the skipped count came back {skipped}.");
        }
        string json =
            build.Invoke(
                null,
                new object[] { cellList, 1.0, PatternOf("Faces") }) as string
            ?? throw new InvalidOperationException(
                "BuildTessellationJson returned an unexpected type.");
        const string expected =
            "{\"schema\":\"bench.tessellation/1\",\"units\":\"m\"," +
            "\"domain\":\"plan\",\"pattern\":\"faces\",\"cells\":[" +
            "{\"key\":\"c0p0\",\"course\":0,\"outline\":[[0,0],[1,0],[0,1]]}," +
            "{\"key\":\"c0p1\",\"course\":0,\"outline\":[[1,0],[2,0],[1,1]]}," +
            "{\"key\":\"c0p2\",\"course\":0,\"outline\":[[2,0],[3,0],[2,1]]}]}";
        if (!string.Equals(json, expected, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The three usable faces give three cells, in face order, "
                + "every one at course 0, renumbered c0p0 to c0p2 with the "
                + "skipped face leaving no hole and no error; expected "
                + $"'{expected}', received '{json}'.");
        }
    }

    private static void ValidateExportPlan(Assembly plugin)
    {
        Type plan = plugin.GetType("Ananke.COMPAS.Native.Components.ExportPlan", throwOnError: true)!;
        MethodInfo kinds = RequirePublicStatic(plan, "Kinds");
        string Show(bool cells, bool columns) =>
            string.Join(",", (string[])kinds.Invoke(null, new object?[] { cells, columns })!);
        if (Show(false, false) != "contract,compas") throw new InvalidOperationException($"No cells, no columns: contract,compas; got {Show(false, false)}.");
        if (Show(true, false) != "contract,compas,tessellation") throw new InvalidOperationException($"Cells add tessellation; got {Show(true, false)}.");
        if (Show(false, true) != "contract,compas,columns") throw new InvalidOperationException($"Columns add columns; got {Show(false, true)}.");
        if (Show(true, true) != "contract,compas,tessellation,columns") throw new InvalidOperationException($"All four in order; got {Show(true, true)}.");

        // The study name rule. A Name is one path segment because it is
        // both a file name stem inside the folder the author chose and
        // one segment of the studio's route: a separator or a dot-dot in
        // it writes the set somewhere the author never named, quietly and
        // successfully, and reaches a route nobody asked for.
        MethodInfo segment = RequirePublicStatic(plan, "NameIsOneSegment");
        bool OneSegment(string name) => (bool)segment.Invoke(null, new object?[] { name })!;
        if (!OneSegment("study-1"))
            throw new InvalidOperationException("An ordinary study name is one segment.");
        foreach (string refused in new[] { "..", ".", @"a\b", "a/b", "a:b", "a?b", "", "   " })
        {
            if (OneSegment(refused))
            {
                throw new InvalidOperationException(
                    $"'{refused}' is not one path segment and must be refused: "
                    + "a Name carrying a separator, a colon, a dot-dot or a "
                    + "character no file name may hold escapes the folder the "
                    + "author chose.");
            }
        }
    }

    private static void ValidateColumnsMesh(Assembly plugin)
    {
        Type mesh = plugin.GetType("Ananke.COMPAS.Native.Components.ColumnsMesh", throwOnError: true)!;
        MethodInfo build = RequirePublicStatic(mesh, "Build");
        Type memberList = build.GetParameters()[0].ParameterType;   // IReadOnlyList<(Point3d, Point3d, double)>
        Type tuple = memberList.GetGenericArguments()[0];
        Type point3d = tuple.GetGenericArguments()[0];
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object Member(double x0, double y0, double z0, double x1, double y1, double z1, double f) =>
            Activator.CreateInstance(tuple, P(x0, y0, z0), P(x1, y1, z1), f)!;
        object ListOf(params object[] members)
        {
            var list = (System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(tuple))!;
            foreach (object m in members) list.Add(m);
            return list;
        }
        (double[][] V, int[][] F) Run(object members, double radius)
        {
            object result = build.Invoke(null, new object?[] { members, radius, 6 })!;
            Type t = result.GetType();
            return ((double[][])t.GetField("Item1")!.GetValue(result)!, (int[][])t.GetField("Item2")!.GetValue(result)!);
        }

        (double[][] v, int[][] f) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 5.0)), 0.1);
        if (v.Length != 12) throw new InvalidOperationException($"A six-sided prism has 12 vertices; got {v.Length}.");
        if (f.Count(x => x.Length == 4) != 6 || f.Count(x => x.Length == 3) != 8)
            throw new InvalidOperationException($"Six side quads and eight cap triangles; got {f.Count(x => x.Length == 4)} quads and {f.Count(x => x.Length == 3)} triangles.");
        foreach (double[] p in v)
        {
            double r = Math.Sqrt((p[0] * p[0]) + (p[1] * p[1]));
            if (Math.Abs(r - 0.1) > 1.0e-9) throw new InvalidOperationException($"Every vertex sits at the radius; one is at {r:0.######}.");
            if (Math.Abs(p[2]) > 1.0e-9 && Math.Abs(p[2] - 2.0) > 1.0e-9) throw new InvalidOperationException($"Cap vertices sit at the member's ends; one is at z {p[2]:0.######}.");
        }
        foreach (int[] face in f)
            foreach (int i in face)
                if (i < 0 || i >= v.Length) throw new InvalidOperationException("A face indexes outside the vertices.");
        (double[][] none, int[][] noneF) = Run(ListOf(Member(1, 1, 1, 1, 1, 1, 1.0)), 0.1);
        if (none.Length != 0 || noneF.Length != 0) throw new InvalidOperationException("A zero-length member draws nothing.");
        (double[][] two, int[][] twoF) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 1.0), Member(1, 0, 0, 3, 0, 0, 1.0)), 0.1);
        if (two.Length != 24) throw new InvalidOperationException($"Two members give 24 vertices; got {two.Length}.");
        if (twoF.SelectMany(x => x).Any(i => i < 0 || i >= 24)) throw new InvalidOperationException("Two members' faces index within 24 vertices.");

        // A DIAGONAL member. Every case above lies on an axis, so all of
        // them would pass against a prism whose cap circle was drawn in
        // world XY and only stretched along the member: the circle has to
        // be perpendicular to the MEMBER, and this is where that shows.
        (double[][] diagonal, int[][] _) = Run(ListOf(Member(0, 0, 0, 1, 1, 1, 1.0)), 0.1);
        if (diagonal.Length != 12)
            throw new InvalidOperationException($"A diagonal member is a prism too; got {diagonal.Length} vertices.");
        double unit = 1.0 / Math.Sqrt(3.0);
        for (int i = 0; i < diagonal.Length; i++)
        {
            double end = i < 6 ? 0.0 : 1.0;
            double ox = diagonal[i][0] - end;
            double oy = diagonal[i][1] - end;
            double oz = diagonal[i][2] - end;
            double along = (ox * unit) + (oy * unit) + (oz * unit);
            double across = Math.Sqrt((ox * ox) + (oy * oy) + (oz * oz));
            if (Math.Abs(along) > 1.0e-9)
                throw new InvalidOperationException(
                    $"Cap vertex {i} is {along:0.#########} off its cap plane: the "
                    + "circle must be perpendicular to the member, not to world Z.");
            if (Math.Abs(across - 0.1) > 1.0e-9)
                throw new InvalidOperationException(
                    $"Cap vertex {i} sits at {across:0.#########} from the axis point, not at the radius asked.");
        }

        // The document beside the mesh. The radius it declares is the one
        // the mesh was built at, floored once for both, and a member too
        // short to be drawn is absent from the members list as well as
        // from the prisms, so the nth of one is the nth of the other.
        MethodInfo json = RequirePublicStatic(mesh, "Json");
        string Document(object members, double radius) =>
            (string)json.Invoke(null, new object?[] { members, radius, "kN", 1.0 })!;
        JsonNode skipped = JsonNode.Parse(
            Document(ListOf(Member(1, 1, 1, 1, 1, 1, 1.0)), 0.1))!;
        if (skipped["vertices"]!.AsArray().Count != 0 ||
            skipped["members"]!.AsArray().Count != 0)
        {
            throw new InvalidOperationException(
                "A member too short to draw is skipped in BOTH lists; the "
                + "document listed one of them.");
        }
        JsonNode clamped = JsonNode.Parse(
            Document(ListOf(Member(0, 0, 0, 0, 0, 2, 1.0)), 0.0))!;
        if (Math.Abs(clamped["radius"]!.GetValue<double>() - 1.0e-9) > 1.0e-18)
        {
            throw new InvalidOperationException(
                "The radius in the document is the one the mesh was built at: "
                + "a zero radius is floored once, for both, not floored inside "
                + $"the mesh and declared raw beside it (got {clamped["radius"]!.GetValue<double>()}).");
        }
    }

    private static void ValidateLiveUploader(Assembly plugin)
    {
        Type uploader = plugin.GetType("Ananke.COMPAS.Native.Components.LiveUploader", throwOnError: true)!;
        MethodInfo delay = RequirePublicStatic(uploader, "RetryDelay");
        MethodInfo route = RequirePublicStatic(uploader, "RouteFor");
        MethodInfo outcome = RequirePublicStatic(uploader, "Outcome");
        MethodInfo key = RequirePublicStatic(uploader, "SetKey");
        int? Delay(int attempt) => (int?)delay.Invoke(null, new object?[] { attempt });
        if (Delay(0) != 2000 || Delay(1) != 4000 || Delay(2) != 8000 || Delay(3) is not null)
            throw new InvalidOperationException("The retry schedule is 2000, 4000, 8000 then null.");
        string Route(string kind, string name, string studio) => (string)route.Invoke(null, new object?[] { kind, name, studio })!;
        if (Route("contract", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/exports/arch/contract")
            throw new InvalidOperationException($"Contract route wrong: {Route("contract", "arch", "http://127.0.0.1:8600")}.");
        if (Route("tessellation", "arch", "http://127.0.0.1:8600/") != "http://127.0.0.1:8600/api/uploads/exports/arch/tessellation")
            throw new InvalidOperationException("A trailing slash on Studio is tolerated.");
        if (Route("columns", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/columns/arch-columns.json")
            throw new InvalidOperationException($"Columns route wrong: {Route("columns", "arch", "http://127.0.0.1:8600")}.");
        // The study name is free text off the canvas and lands in a URL
        // path segment. Interpolated raw, a space breaks the URI and a #
        // cuts the rest of the route off as a fragment, so the PUT goes
        // somewhere nobody asked for and the author sees only a 404.
        if (Route("contract", "my study#1", "http://127.0.0.1:8600") !=
            "http://127.0.0.1:8600/api/uploads/exports/my%20study%231/contract")
        {
            throw new InvalidOperationException(
                "A Name with a space and a # must be escaped into the route; got "
                + Route("contract", "my study#1", "http://127.0.0.1:8600") + ".");
        }
        if (Route("columns", "my study#1", "http://127.0.0.1:8600") !=
            "http://127.0.0.1:8600/api/uploads/columns/my%20study%231-columns.json")
        {
            throw new InvalidOperationException(
                "The columns route escapes the Name too; got "
                + Route("columns", "my study#1", "http://127.0.0.1:8600") + ".");
        }
        string Verdict(int status, int attempt) => (string)outcome.Invoke(null, new object?[] { status, attempt })!;
        if (Verdict(200, 0) != "stored" || Verdict(204, 5) != "stored") throw new InvalidOperationException("2xx is stored.");
        if (Verdict(409, 0) != "retry" || Verdict(409, 2) != "retry") throw new InvalidOperationException("409 retries while the schedule has entries.");
        if (Verdict(409, 3) != "deferred") throw new InvalidOperationException("409 after the schedule is deferred.");
        if (Verdict(400, 0) != "refused" || Verdict(500, 0) != "refused") throw new InvalidOperationException("Anything else is refused.");
        // What a deferred kind says it is waiting behind. The studio's
        // 409 body names the run it is busy with, and that run id is what
        // the author looks for in the studio; pasting the document raw
        // makes them read JSON off a component chin.
        MethodInfo deferred = RequirePublicStatic(uploader, "DeferredDetail");
        string Detail(string body) => (string)deferred.Invoke(null, new object?[] { body })!;
        if (Detail("{\"run\": \"r-42\"}") != "(run r-42)")
            throw new InvalidOperationException($"A 409 body naming a run reads as the run; got {Detail("{\"run\": \"r-42\"}")}.");
        if (Detail("study is busy") != "study is busy")
            throw new InvalidOperationException("A body that is not that JSON falls back to the body itself.");
        if (Detail("{\"detail\": \"busy\"}") != "{\"detail\": \"busy\"}")
            throw new InvalidOperationException("JSON carrying no run falls back to the body itself.");
        // The set key. It decides whether a re-solve sends again, and the
        // component expires itself on every outcome, so a key that cannot
        // repeat is an unbounded loop of worker calls and PUTs rather than
        // a cosmetic defect. What it must read: the Name, the Studio and
        // every kind by name and by content. What it must NOT read: the
        // compas document's own bytes, because the worker's json_dumps
        // stamps a fresh uuid4 into every serialisation of the same Result
        // (compas/data/data.py), so those bytes differ on every solve of
        // an unchanged definition.
        string Key(string name, string studio, List<(string, string)> set) =>
            (string)key.Invoke(null, new object?[] { name, studio, set })!;
        const string Studio = "http://127.0.0.1:8600";
        var a = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"aaa\"}") };
        var b = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"aaa\"}") };
        if (Key("arch", Studio, a) != Key("arch", Studio, b))
            throw new InvalidOperationException("Equal sets key the same.");
        // The loop guard itself: same Result, second solve, a fresh guid
        // inside the compas document and nothing else changed.
        var freshGuid = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"bbb\"}") };
        if (Key("arch", Studio, a) != Key("arch", Studio, freshGuid))
        {
            throw new InvalidOperationException(
                "Two sets differing ONLY in the compas kind's JSON must key the SAME: "
                + "the worker mints a fresh uuid per serialisation, so a key that read "
                + "those bytes could never repeat and the expire-on-outcome loop would "
                + "never terminate.");
        }
        // What the key does read, one part at a time.
        var changedContract = new List<(string, string)> { ("contract", "{\"a\":2}"), ("compas", "{\"guid\":\"aaa\"}") };
        if (Key("arch", Studio, a) == Key("arch", Studio, changedContract))
            throw new InvalidOperationException("A set differing in the contract kind's JSON keys differently.");
        var withoutCompas = new List<(string, string)> { ("contract", "{\"a\":1}") };
        if (Key("arch", Studio, a) == Key("arch", Studio, withoutCompas))
        {
            throw new InvalidOperationException(
                "A set carrying a compas kind and the same set without one must key "
                + "differently: the compas kind's PRESENCE counts even though its bytes "
                + "do not, so a set recovered after a worker failure is sent.");
        }
        if (Key("arch", Studio, a) == Key("arch-b", Studio, a))
            throw new InvalidOperationException("The same set under a different Name keys differently.");
        if (Key("arch", Studio, a) == Key("arch", "http://127.0.0.1:8601", a))
            throw new InvalidOperationException("The same set going to a different Studio keys differently.");
        var d = new List<(string, string)> { ("contract", "{\"a\":1}") };
        var e = new List<(string, string)> { ("compas", "{\"a\":1}") };
        if (Key("arch", Studio, d) == Key("arch", Studio, e))
            throw new InvalidOperationException("A set differing only in Kind keys differently.");
    }

    /// <summary>
    /// Export's Path resolution, which decides where a whole set of files
    /// lands. Reflection only: the method is pure (it reads
    /// <c>Directory.Exists</c> but creates nothing and writes nothing), so
    /// this asserts against paths that do not exist on this machine.
    /// </summary>
    private static void ValidateExportWriteFolder(Assembly plugin)
    {
        Type export = RequireComponentType(plugin, "ExportComponent");
        MethodInfo resolve = export.GetMethod(
            "TryResolveWriteFolder",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.TryResolveWriteFolder was not found.");
        (bool Ok, string Folder, string Refusal) Resolve(string path)
        {
            object?[] args = { path, null, null };
            bool ok = (bool)resolve.Invoke(null, args)!;
            return (ok, (string)args[1]!, (string)args[2]!);
        }

        // A folder the author means to create: read as a file path, the
        // whole set landed one level up, silently, beside it.
        (bool ok, string folder, string refusal) = Resolve(@"C:\ananke-smoke-nowhere\my-study");
        if (!ok || folder != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException(
                $"An extensionless Path is the folder, whether or not it exists yet; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve(@"C:\ananke-smoke-nowhere\my-study\");
        if (!ok || folder.TrimEnd('\\') != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException(
                $"A trailing separator is a folder; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve(@"C:\ananke-smoke-nowhere\study.json");
        if (!ok || folder != @"C:\ananke-smoke-nowhere")
            throw new InvalidOperationException(
                $"A Path with an extension uses its own directory; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve("  C:\\ananke-smoke-nowhere\\my-study  ");
        if (!ok || folder != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException("The Path is trimmed before it is read.");
        // A bare name has no folder in it at all, so the set would land in
        // the process working directory, which under Rhino is not
        // somewhere an author can find.
        (ok, folder, refusal) = Resolve("my-study");
        if (ok || refusal.Length == 0 || !refusal.Contains("my-study", StringComparison.Ordinal))
            throw new InvalidOperationException(
                $"A bare relative name is refused, naming the path; got ok={ok}, refusal '{refusal}'.");
        (ok, folder, refusal) = Resolve("study.json");
        if (ok || refusal.Length == 0)
            throw new InvalidOperationException(
                $"A bare file name is refused; got ok={ok}, refusal '{refusal}'.");

        // A relative Path with directories of its own is not a bare name,
        // but it is still not rooted: today it resolves against the
        // process working directory the same way a bare name would, which
        // under Rhino is nobody's intent. Refused, naming the path, the
        // same as a bare name.
        (ok, folder, refusal) = Resolve(@"sub\study");
        if (ok || refusal.Length == 0 ||
            !refusal.Contains(@"sub\study", StringComparison.Ordinal))
            throw new InvalidOperationException(
                $"A non-rooted relative Path is refused, naming the path; got ok={ok}, refusal '{refusal}'.");
        // A relative Path with an extension already fell out refused
        // before this rule existed, but for an unrelated reason (the
        // pre-rule depth check happened to reject it once its own
        // directory name was peeled off). The refusal text below is
        // specific to the rootedness rule, so this assertion still fails
        // against the pre-rule code even though its ok/false verdict
        // alone would not have.
        (ok, folder, refusal) = Resolve(@"sub\study.json");
        if (ok || refusal.Length == 0 ||
            !refusal.Contains("rooted", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                $"A non-rooted relative Path with an extension is refused for being unrooted; got ok={ok}, refusal '{refusal}'.");

        // The rooted equivalent of each relative Path above is accepted,
        // with the same folder the existing rooted rules already give:
        // an extensionless Path is the folder itself, a Path with an
        // extension uses its own directory. Built from a temp folder path
        // so the check needs nothing on disk; Directory.Exists on a path
        // that does not exist is simply false, which these rules already
        // tolerate.
        string rootedCheckRoot = Path.Combine(
            Path.GetTempPath(), "ananke-smoke-rooted-check");
        string rootedNoExt = Path.Combine(rootedCheckRoot, "sub", "study");
        (ok, folder, refusal) = Resolve(rootedNoExt);
        if (!ok || folder != rootedNoExt)
            throw new InvalidOperationException(
                $"A rooted extensionless Path is still the folder itself; got ok={ok}, folder '{folder}'.");
        string rootedWithExt = Path.Combine(
            rootedCheckRoot, "sub", "study.json");
        (ok, folder, refusal) = Resolve(rootedWithExt);
        if (!ok || folder != Path.Combine(rootedCheckRoot, "sub"))
            throw new InvalidOperationException(
                $"A rooted Path with an extension still uses its own directory; got ok={ok}, folder '{folder}'.");
    }

    /// <summary>
    /// The cross-repo fixture check: <c>ImportPiecesComponent.ParseDocument</c>
    /// driven with a bench.pieces/1 document generated by the UI repo's own
    /// pieces-export test suite (<c>assets/fixture-pieces.json</c>,
    /// provenance recorded in <c>assets/README.md</c>). Asserts piece
    /// count, order preservation (keys stay in the document's own drop
    /// order), and vertex/face array shapes, then doctors an in-memory
    /// copy's schema and units to confirm ParseDocument refuses each,
    /// naming what it found -- the binding spec's "component Error naming
    /// what was found," as far as this harness's reflection-only reach
    /// (no live Rhino document, no SolveInstance) can exercise it.
    ///
    /// Addendum, 2026-08-20: also asserts BaseMesh's shape against the
    /// committed fixture (regenerated with base_mesh present via the UI
    /// route's real code), and separately proves ParseDocument tolerates
    /// a document with NO base_mesh key at all -- doctored by removing
    /// the property wholesale from an in-memory JSON copy, not merely
    /// nulling it, so old documents (written before this addendum) are
    /// proven to stay loadable.
    ///
    /// Addendum follow-up, 2026-08-20: the fixture was regenerated again
    /// (size 0.6, not 0.9) so it cuts 2 courses instead of 1 -- a
    /// single-course fixture could assert order preservation but never
    /// the addendum's actual point, that M/K/S PARTITION by course. This
    /// method now groups the parsed PieceRecords by Course (the same
    /// field SolveInstance keys GH_Path on) and asserts the exact
    /// per-course counts and in-branch document order against the
    /// fixture's own known shape, measuring the partitioning contract
    /// instead of merely inspecting the component's source for it.
    /// </summary>
    private static void ValidateImportPiecesParsing(Assembly plugin)
    {
        string fixturePath = Path.Combine(
            AppContext.BaseDirectory,
            "assets",
            "fixture-pieces.json");
        if (!File.Exists(fixturePath))
        {
            throw new FileNotFoundException(
                "Committed fixture not found (expected it copied to the " +
                "build output by the harness's assets/ convention): " +
                fixturePath,
                fixturePath);
        }
        string json = File.ReadAllText(fixturePath);

        Type importType = RequireComponentType(plugin, "ImportPiecesComponent");
        MethodInfo parseMethod = importType.GetMethod(
            "ParseDocument",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ImportPiecesComponent.ParseDocument was not found.");

        object document = parseMethod.Invoke(null, new object[] { json })
            ?? throw new InvalidOperationException(
                "ParseDocument returned null for the committed fixture.");
        Type documentType = document.GetType();

        // The fixture's own document order (piece keys, verbatim), across
        // BOTH of its courses: 10 course-0 pieces, then 4 course-1 pieces,
        // not the sorted/alphabetical order the keys would fall into on
        // their own, and not grouped by course in the document itself
        // (that grouping is exactly what GH_Path(piece.Course) partitions
        // out downstream -- asserted separately below). Addendum
        // follow-up, 2026-08-20: regenerated at size 0.6 (was 0.9) so the
        // fixture actually cuts 2 courses; a single-course fixture could
        // never prove the tree PARTITIONS.
        var expectedKeys = new[]
        {
            "c0p5", "c0p6", "c0p7", "c0p8", "c0p9",
            "c0p0", "c0p1", "c0p2", "c0p3", "c0p4",
            "c1p2", "c1p3", "c1p0", "c1p1",
        };

        object? pieceCountValue =
            documentType.GetProperty("PieceCount")?.GetValue(document);
        if (pieceCountValue is not int pieceCount ||
            pieceCount != expectedKeys.Length)
        {
            throw new InvalidOperationException(
                $"PiecesDocument.PieceCount must be {expectedKeys.Length}; " +
                $"received '{pieceCountValue}'.");
        }

        IList pieces = documentType.GetProperty("Pieces")?.GetValue(document)
            as IList
            ?? throw new InvalidOperationException(
                "PiecesDocument.Pieces could not be inspected.");
        if (pieces.Count != expectedKeys.Length)
        {
            throw new InvalidOperationException(
                $"Expected {expectedKeys.Length} pieces, found " +
                $"{pieces.Count}.");
        }

        for (int index = 0; index < expectedKeys.Length; index++)
        {
            object piece = pieces[index]
                ?? throw new InvalidOperationException(
                    $"Piece {index} is null.");
            Type pieceType = piece.GetType();
            string key =
                pieceType.GetProperty("Key")?.GetValue(piece) as string
                ?? string.Empty;
            if (!string.Equals(
                    key,
                    expectedKeys[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"Piece {index} key must be '{expectedKeys[index]}' " +
                    $"(the document's own drop order); received '{key}'.");
            }

            IList vertices =
                pieceType.GetProperty("Vertices")?.GetValue(piece) as IList
                ?? throw new InvalidOperationException(
                    $"Piece '{key}' Vertices could not be inspected.");
            if (vertices.Count == 0)
            {
                throw new InvalidOperationException(
                    $"Piece '{key}' has no vertices.");
            }
            foreach (object? vertex in vertices)
            {
                if (vertex is not double[] xyz || xyz.Length != 3)
                {
                    throw new InvalidOperationException(
                        $"Piece '{key}' has a vertex that is not an " +
                        "[x, y, z] triple.");
                }
            }

            IList faces =
                pieceType.GetProperty("Faces")?.GetValue(piece) as IList
                ?? throw new InvalidOperationException(
                    $"Piece '{key}' Faces could not be inspected.");
            if (faces.Count == 0)
            {
                throw new InvalidOperationException(
                    $"Piece '{key}' has no faces.");
            }
            foreach (object? face in faces)
            {
                if (face is not int[] corners || corners.Length < 3)
                {
                    throw new InvalidOperationException(
                        $"Piece '{key}' has a face with fewer than 3 " +
                        "corners.");
                }
            }
        }

        // Addendum follow-up, 2026-08-20: the partitioning contract,
        // MEASURED rather than merely inspected by reading the
        // component's source. Groups the parsed PieceRecords by their
        // own Course value -- the exact field ImportPiecesComponent's
        // SolveInstance keys GH_Path(piece.Course) on -- in document
        // order, then asserts the result against the committed fixture's
        // own known shape: 2 distinct course branches, exact per-course
        // counts, and document order preserved WITHIN each branch. This
        // is what GH_Path(course) partitioning produces without needing
        // to run inside Grasshopper: Append-in-order grouped by key is
        // the same operation either way.
        var courseOrder = new List<int>();
        var courseGroups = new Dictionary<int, List<string>>();
        foreach (object piece in pieces)
        {
            Type pieceType = piece.GetType();
            object? courseValue =
                pieceType.GetProperty("Course")?.GetValue(piece);
            if (courseValue is not int pieceCourse)
            {
                throw new InvalidOperationException(
                    "PieceRecord.Course could not be inspected.");
            }
            string pieceKey =
                pieceType.GetProperty("Key")?.GetValue(piece) as string
                ?? string.Empty;

            if (!courseGroups.TryGetValue(pieceCourse, out List<string>? keys))
            {
                keys = new List<string>();
                courseGroups[pieceCourse] = keys;
                courseOrder.Add(pieceCourse);
            }
            keys.Add(pieceKey);
        }

        if (courseGroups.Count < 2)
        {
            throw new InvalidOperationException(
                "The fixture must carry >= 2 distinct course values to " +
                $"prove tree partitioning; found {courseGroups.Count}.");
        }

        var expectedCourseGroups = new (int Course, string[] Keys)[]
        {
            (0, new[]
            {
                "c0p5", "c0p6", "c0p7", "c0p8", "c0p9",
                "c0p0", "c0p1", "c0p2", "c0p3", "c0p4",
            }),
            (1, new[] { "c1p2", "c1p3", "c1p0", "c1p1" }),
        };

        if (courseOrder.Count != expectedCourseGroups.Length)
        {
            throw new InvalidOperationException(
                $"Expected {expectedCourseGroups.Length} distinct course " +
                $"branches (the GH_Path partitioning this fixture must " +
                $"prove); found {courseOrder.Count}.");
        }

        foreach ((int course, string[] expectedCourseKeys) in expectedCourseGroups)
        {
            if (!courseGroups.TryGetValue(course, out List<string>? actualKeys))
            {
                throw new InvalidOperationException(
                    $"Course {course} branch is missing from the parsed " +
                    "pieces.");
            }
            if (actualKeys.Count != expectedCourseKeys.Length)
            {
                throw new InvalidOperationException(
                    $"Course {course} branch (GH_Path({course})) must " +
                    $"carry {expectedCourseKeys.Length} piece(s); found " +
                    $"{actualKeys.Count}.");
            }
            for (int index = 0; index < expectedCourseKeys.Length; index++)
            {
                if (!string.Equals(
                        actualKeys[index],
                        expectedCourseKeys[index],
                        StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"Course {course} branch item {index} must be " +
                        $"'{expectedCourseKeys[index]}' (document order " +
                        "preserved within the branch); received " +
                        $"'{actualKeys[index]}'.");
                }
            }
        }

        // Addendum, 2026-08-20: base_mesh shape, against the committed
        // fixture (regenerated to carry one).
        object? baseMeshValue =
            documentType.GetProperty("BaseMesh")?.GetValue(document);
        if (baseMeshValue is null)
        {
            throw new InvalidOperationException(
                "PiecesDocument.BaseMesh must be present for the " +
                "committed fixture (regenerated with base_mesh); found " +
                "null.");
        }
        Type baseMeshType = baseMeshValue.GetType();
        IList baseMeshVertices =
            baseMeshType.GetProperty("Vertices")?.GetValue(baseMeshValue)
                as IList
            ?? throw new InvalidOperationException(
                "BaseMesh.Vertices could not be inspected.");
        IList baseMeshFaces =
            baseMeshType.GetProperty("Faces")?.GetValue(baseMeshValue)
                as IList
            ?? throw new InvalidOperationException(
                "BaseMesh.Faces could not be inspected.");
        if (baseMeshVertices.Count == 0 || baseMeshFaces.Count == 0)
        {
            throw new InvalidOperationException(
                "BaseMesh must carry at least one vertex and one face " +
                "for the committed fixture.");
        }
        foreach (object? vertex in baseMeshVertices)
        {
            if (vertex is not double[] xyz || xyz.Length != 3)
            {
                throw new InvalidOperationException(
                    "BaseMesh has a vertex that is not an [x, y, z] " +
                    "triple.");
            }
        }
        foreach (object? face in baseMeshFaces)
        {
            if (face is not int[] corners || corners.Length < 3)
            {
                throw new InvalidOperationException(
                    "BaseMesh has a face with fewer than 3 corners.");
            }
        }

        // Addendum, 2026-08-20: absence tolerance. Strip base_mesh from
        // an in-memory copy of the fixture's own JSON (property removed
        // entirely, not nulled) and confirm ParseDocument still succeeds
        // with BaseMesh coming back null -- an export written before
        // this addendum must stay loadable.
        string jsonWithoutBaseMesh = RemoveJsonProperty(json, "base_mesh");
        object documentWithoutBaseMesh =
            parseMethod.Invoke(null, new object[] { jsonWithoutBaseMesh })
            ?? throw new InvalidOperationException(
                "ParseDocument returned null for a fixture doctored to " +
                "omit base_mesh.");
        object? baseMeshWhenAbsent = documentType
            .GetProperty("BaseMesh")
            ?.GetValue(documentWithoutBaseMesh);
        if (baseMeshWhenAbsent is not null)
        {
            throw new InvalidOperationException(
                "PiecesDocument.BaseMesh must be null when the document " +
                "has no base_mesh key; ParseDocument must tolerate " +
                "absence, not fabricate a value.");
        }

        RequireParseRefusal(
            parseMethod,
            json.Replace(
                "\"schema\": \"bench.pieces/1\"",
                "\"schema\": \"bench.pieces/2\""),
            "schema",
            "bench.pieces/2",
            "a doctored bad-schema copy");
        RequireParseRefusal(
            parseMethod,
            json.Replace(
                "\"units\": \"m\"",
                "\"units\": \"mm\""),
            "units",
            "mm",
            "a doctored bad-units copy");
    }

    /// <summary>
    /// Removes one top-level property from a JSON document, returning the
    /// re-serialized text -- used to prove ParseDocument tolerates a
    /// document with a key entirely ABSENT, not merely present-and-null,
    /// which a simple string replace of the property's value could not
    /// distinguish.
    /// </summary>
    private static string RemoveJsonProperty(string json, string propertyName)
    {
        JsonNode node = JsonNode.Parse(json)
            ?? throw new InvalidOperationException(
                "JSON did not parse to a node.");
        JsonObject root = node.AsObject();
        root.Remove(propertyName);
        return root.ToJsonString();
    }

    /// <summary>
    /// Invokes <c>ParseDocument</c> with a doctored copy and requires it
    /// to throw naming both the offending field and the value that was
    /// actually found (not merely "invalid").
    /// </summary>
    private static void RequireParseRefusal(
        MethodInfo parseMethod,
        string doctoredJson,
        string expectedField,
        string expectedFoundValue,
        string label)
    {
        try
        {
            parseMethod.Invoke(null, new object[] { doctoredJson });
        }
        catch (TargetInvocationException invocation)
            when (invocation.InnerException is not null)
        {
            string message = invocation.InnerException.Message;
            if (!message.Contains(
                    expectedField,
                    StringComparison.OrdinalIgnoreCase) ||
                !message.Contains(expectedFoundValue, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{label} was refused, but the message did not name " +
                    $"'{expectedField}'/'{expectedFoundValue}': '{message}'.");
            }
            return;
        }
        throw new InvalidOperationException(
            $"{label} was not refused by ParseDocument.");
    }

    // A minimal, internally consistent triangle fixture (3 vertices, 3
    // edges, 1 face) shared by every JSON template below. Building genuine
    // JSON and deserializing it through the plugin's own ContractJson codec
    // exercises the exact path Grasshopper document persistence uses,
    // rather than merely poking properties by reflection.
    private const string TopologyJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.topology"",
  ""networkKind"": ""faced"",
  ""vertices"": [
    {""x"": 0.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 1.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}
  ],
  ""edges"": [
    {""u"": 0, ""v"": 1},
    {""u"": 1, ""v"": 2},
    {""u"": 2, ""v"": 0}
  ],
  ""faces"": [[0, 1, 2]],
  ""lengthUnit"": ""m"",
  ""topologyHash"": ""__HASH__""
}";

    private const string SupportSetJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.support_set"",
  ""topologyHash"": ""__HASH__"",
  ""mode"": ""explicit"",
  ""nodeIds"": [0]
}";

    private const string TnaPatternJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.tna_pattern"",
  ""patternMode"": ""mesh"",
  ""topology"": __TOPOLOGY__,
  ""supports"": __SUPPORTS__
}";

    private const string LoadCaseJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.load_case"",
  ""topologyHash"": ""__HASH__"",
  ""name"": ""spine-smoke"",
  ""distribution"": ""point"",
  ""nodeIds"": [0],
  ""vectors"": [{""x"": 0.0, ""y"": 0.0, ""z"": -1.0}]
}";

    private const string AnchoredPatternJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""AnchoredPattern"",
  ""pattern"": __PATTERN__,
  ""anchorNodeIds"": __ANCHORS__
}";

    private const string ProblemJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Problem"",
  ""anchored"": __ANCHORED__,
  ""load"": __LOAD__
}";

    private const string TnaPreparedPatternJson = @"
{
  ""patternKind"": ""faced"",
  ""vertices"": [
    {""x"": 0.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 1.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}
  ],
  ""edges"": [
    {""u"": 0, ""v"": 1},
    {""u"": 1, ""v"": 2},
    {""u"": 2, ""v"": 0}
  ],
  ""faces"": [[0, 1, 2]],
  ""edgeForceDensities"": [1.0, 1.0, 1.0]
}";

    private const string TnaDiagramGraphJson = @"
{
  ""vertices"": [
    {""id"": 0, ""point"": {""x"": 0.0, ""y"": 0.0, ""z"": 0.0}},
    {""id"": 1, ""point"": {""x"": 1.0, ""y"": 0.0, ""z"": 0.0}},
    {""id"": 2, ""point"": {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}}
  ],
  ""edges"": [
    {""id"": 0, ""u"": 0, ""v"": 1},
    {""id"": 1, ""u"": 1, ""v"": 2},
    {""id"": 2, ""u"": 2, ""v"": 0}
  ]
}";

    private const string TnaPreparedMappingsJson = @"
{
  ""patternVertexToTopologyVertex"": [0, 1, 2],
  ""backendSourceToTopologyVertex"": [
    {""topologyVertexId"": 0},
    {""topologyVertexId"": 1},
    {""topologyVertexId"": 2}
  ],
  ""sourceEdgeToPatternEdge"": [
    {""sourceEdgeId"": 0, ""patternEdgeId"": 0, ""u"": 0, ""v"": 1},
    {""sourceEdgeId"": 1, ""patternEdgeId"": 1, ""u"": 1, ""v"": 2},
    {""sourceEdgeId"": 2, ""patternEdgeId"": 2, ""u"": 2, ""v"": 0}
  ],
  ""supportNodeIds"": [0],
  ""fixedPlanNodeIds"": [],
  ""formEdgeToForceEdge"": [
    {""formEdgeId"": 0, ""targetEdgeId"": 0},
    {""formEdgeId"": 1, ""targetEdgeId"": 1},
    {""formEdgeId"": 2, ""targetEdgeId"": 2}
  ]
}";

    private const string TnaPreparedJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.tna_prepared"",
  ""source"": __PATTERN__,
  ""workerTopologyHash"": ""__HASH__"",
  ""supportSet"": __SUPPORTS__,
  ""pattern"": __PREPARED_PATTERN__,
  ""formGraph"": __FORM_GRAPH__,
  ""forceGraph"": __FORCE_GRAPH__,
  ""mappings"": __MAPPINGS__
}";

    private const string RelaxedJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Relaxed"",
  ""prepared"": __PREPARED__,
  ""problem"": __PROBLEM__
}";

    private const string RelaxedEmptyJson = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Relaxed""
}";

    /// <summary>
    /// The icon family, checked against the components themselves.
    ///
    /// Five of the twenty badges used to be drawn by a different hand, in a
    /// different shape, and the map that owns the rest had sixteen entries
    /// naming components that had been deleted while naming none of the five
    /// that existed. Nothing measured any of that, because nothing connected
    /// the map to the assembly. This does: every component's icon key has
    /// exactly one entry, its category IS the panel the component registers
    /// under, its label is the two letters the spec fixes, its filename is
    /// the key (which is what PluginResources.Icon reads), and the badge's
    /// own pixels carry the category's fill.
    ///
    /// The fill is sampled at (12, 20). The badge is a rounded rectangle
    /// filled edge to edge under a lighter top band of four rows; the label
    /// is two five-by-seven glyphs at scale two, centred, so it occupies
    /// rows 5 to 18 and a shadow row 19, and columns 1 to 22 with a
    /// two-pixel gap between the glyphs. Row 20 is below all of it and
    /// inside the rounded box, so it is the fill and nothing else.
    /// </summary>
    private static void ValidateIconMap(
        Assembly plugin,
        Type[] componentTypes,
        string pluginPath)
    {
        string mapPath = FindIconMap(pluginPath);
        JsonNode map = JsonNode.Parse(File.ReadAllText(mapPath))
            ?? throw new InvalidOperationException(
                $"{mapPath} did not parse as JSON.");
        JsonObject categories = map["categories"]?.AsObject()
            ?? throw new InvalidOperationException(
                "icon-map.json carries no categories.");
        JsonArray native = map["native_components"]?.AsArray()
            ?? throw new InvalidOperationException(
                "icon-map.json carries no native_components.");

        var byKey = new Dictionary<string, JsonNode>(StringComparer.Ordinal);
        foreach (JsonNode? entry in native)
        {
            JsonNode row = entry
                ?? throw new InvalidOperationException(
                    "icon-map.json has a null native_components entry.");
            string key = (string?)row["key"]
                ?? throw new InvalidOperationException(
                    "A native_components entry carries no key.");
            if (!byKey.TryAdd(key, row))
            {
                throw new InvalidOperationException(
                    $"'{key}' has more than one native_components entry, so "
                    + "two entries own one PNG and the last generated wins.");
            }
        }
        if (byKey.Count != componentTypes.Length)
        {
            throw new InvalidOperationException(
                $"{componentTypes.Length} components and {byKey.Count} icons: "
                + "the family covers every component and nothing else, or a "
                + "deleted component's badge stays embedded for ever.");
        }

        foreach (Type componentType in componentTypes)
        {
            string typeName = componentType.FullName ?? componentType.Name;
            if (!NativeIconEntries.TryGetValue(
                    typeName, out (string Key, string Label) expected))
            {
                throw new InvalidOperationException(
                    $"{typeName} has no pinned icon key and label; every "
                    + "component wears one badge from the one family.");
            }
            object instance = Activator.CreateInstance(componentType)
                ?? throw new InvalidOperationException(
                    $"Could not construct {typeName}.");
            try
            {
                string key = IconKeyOf(instance, componentType);
                if (!string.Equals(key, expected.Key, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name} asks for icon '{key}'; the "
                        + $"family gives it '{expected.Key}'.");
                }
                if (!byKey.TryGetValue(key, out JsonNode? row))
                {
                    throw new InvalidOperationException(
                        $"'{key}' has no native_components entry, so nothing "
                        + "generates that badge and the component wears "
                        + "whatever PNG happens to be lying beside the map.");
                }
                string label = (string?)row["label"] ?? string.Empty;
                if (!string.Equals(label, expected.Label, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name}'s badge reads '{label}'; the "
                        + $"spec gives it '{expected.Label}'.");
                }
                string filename = (string?)row["filename"] ?? string.Empty;
                if (!string.Equals(filename, key + ".png", StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"'{key}' is drawn into '{filename}', but the loader "
                        + $"reads the resource '{key}.png' and would find "
                        + "nothing.");
                }
                string category = (string?)row["category"] ?? string.Empty;
                string subCategory =
                    componentType.GetProperty("SubCategory")?.GetValue(instance)
                        as string
                    ?? string.Empty;
                if (!string.Equals(category, subCategory, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name} sits under '{subCategory}' and "
                        + $"its badge is filled for '{category}': the colour "
                        + "is the panel, so a component that moves tab and "
                        + "keeps its fill lies about where it lives.");
                }
                string fill = (string?)categories[category]?["fill"]
                    ?? throw new InvalidOperationException(
                        $"icon-map.json has no fill for category '{category}'.");
                (int r, int g, int b) = ParseFill(fill);
                (int actualR, int actualG, int actualB) =
                    BadgeFill(RequireIconBitmap(instance, componentType));
                if (r != actualR || g != actualG || b != actualB)
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name}'s badge is filled "
                        + $"#{actualR:X2}{actualG:X2}{actualB:X2} where "
                        + $"'{category}' is {fill}: the PNG on disk is not the "
                        + "one this map describes, so the generator has not "
                        + "been run since the map changed.");
                }
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }
    }

    /// <summary>
    /// The icon key a component names to its base constructor, which is also
    /// the embedded resource name and so the file name. Held in a private
    /// field on both native bases, so the walk goes up until it finds one.
    /// </summary>
    private static string IconKeyOf(object instance, Type componentType)
    {
        for (Type? current = componentType;
             current is not null;
             current = current.BaseType)
        {
            FieldInfo? field = current.GetField(
                "_iconName",
                BindingFlags.Instance |
                BindingFlags.NonPublic |
                BindingFlags.DeclaredOnly);
            if (field is null)
                continue;
            return field.GetValue(instance) as string ?? string.Empty;
        }
        throw new InvalidOperationException(
            $"{componentType.Name} carries no icon key; every native "
            + "component names one to its base constructor.");
    }

    /// <summary>
    /// The badge's own fill, read off the embedded bitmap at (12, 20).
    /// Reflected rather than referenced, in this harness's usual manner, so
    /// nothing here has to bind to System.Drawing at compile time.
    /// </summary>
    private static (int R, int G, int B) BadgeFill(object icon)
    {
        MethodInfo getPixel = icon.GetType().GetMethod(
            "GetPixel", new[] { typeof(int), typeof(int) })
            ?? throw new InvalidOperationException(
                "The icon is not a bitmap with pixels to read.");
        object colour = getPixel.Invoke(icon, new object[] { 12, 20 })
            ?? throw new InvalidOperationException(
                "GetPixel returned nothing.");
        Type colourType = colour.GetType();
        int Channel(string name) => Convert.ToInt32(
            colourType.GetProperty(name)?.GetValue(colour));
        return (Channel("R"), Channel("G"), Channel("B"));
    }

    private static (int R, int G, int B) ParseFill(string value)
    {
        if (value.Length != 7 || value[0] != '#')
        {
            throw new InvalidOperationException(
                $"A category fill is #RRGGBB; got '{value}'.");
        }
        return (
            Convert.ToInt32(value.Substring(1, 2), 16),
            Convert.ToInt32(value.Substring(3, 2), 16),
            Convert.ToInt32(value.Substring(5, 2), 16));
    }

    /// <summary>
    /// plugin/icons/icon-map.json, found by walking up from the .gha under
    /// test and then from this harness's own output directory. The map is
    /// the generator's manifest and lives in the repository, not in the
    /// build, so there is nothing to resolve it by but the tree.
    /// </summary>
    private static string FindIconMap(string pluginPath) =>
        FindRepositoryFile(
            pluginPath,
            new[]
            {
                Path.Combine("plugin", "icons", "icon-map.json"),
                Path.Combine("icons", "icon-map.json")
            },
            "plugin/icons/icon-map.json",
            "the icon family is checked against that map");

    /// <summary>
    /// A file that lives in the REPOSITORY rather than in the build, found
    /// by walking up from the plugin under test and then from this harness's
    /// own output directory. Each candidate is a path relative to a
    /// repository root, tried in order at every level.
    /// </summary>
    private static string FindRepositoryFile(
        string pluginPath,
        IReadOnlyList<string> candidates,
        string what,
        string why)
    {
        var starts = new List<string>();
        string? beside = Path.GetDirectoryName(Path.GetFullPath(pluginPath));
        if (beside is not null)
            starts.Add(beside);
        starts.Add(AppContext.BaseDirectory);
        foreach (string start in starts)
        {
            for (DirectoryInfo? directory = new(start);
                 directory is not null;
                 directory = directory.Parent)
            {
                foreach (string candidate in candidates)
                {
                    string full = Path.Combine(directory.FullName, candidate);
                    if (File.Exists(full))
                        return full;
                }
            }
        }
        throw new InvalidOperationException(
            what + " was not found above " +
            string.Join(" or ", starts) +
            "; " + why + ", so it has to be findable from the plugin under "
            + "test.");
    }

    /// <summary>
    /// Constructs the three spine contracts (<c>AnchoredPatternDto</c>,
    /// <c>ProblemDto</c>, <c>RelaxedDto</c>) via JSON round-tripped through
    /// the plugin's own <c>ContractJson</c> codec, exercising one valid and
    /// one invalid case per type, then confirms a <c>ProblemDto</c> attaches
    /// to <c>ResultDto.Problem</c> without breaking a valid TNA result.
    /// </summary>
    private static void ValidateSpineContracts(Assembly plugin)
    {
        Type topologyType = RequireContractType(plugin, "TopologyDto");
        Type anchoredType = RequireContractType(plugin, "AnchoredPatternDto");
        Type problemType = RequireContractType(plugin, "ProblemDto");
        Type preparedType = RequireContractType(plugin, "TnaPreparedDto");
        Type relaxedType = RequireContractType(plugin, "RelaxedDto");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");

        string zeroHash = new string('0', 64);
        object draftTopology = DeserializeContract(
            plugin,
            topologyType,
            TopologyJsonTemplate.Replace("__HASH__", zeroHash));
        string topologyHash = ComputeTopologyHash(plugin, draftTopology);
        string topologyJson = TopologyJsonTemplate.Replace("__HASH__", topologyHash);
        string supportSetJson =
            SupportSetJsonTemplate.Replace("__HASH__", topologyHash);
        string patternJson = TnaPatternJsonTemplate
            .Replace("__TOPOLOGY__", topologyJson)
            .Replace("__SUPPORTS__", supportSetJson);

        // AnchoredPatternDto: valid (one anchor) and invalid (no anchors).
        string validAnchoredJson = AnchoredPatternJsonTemplate
            .Replace("__PATTERN__", patternJson)
            .Replace("__ANCHORS__", "[0]");
        object validAnchored =
            DeserializeContract(plugin, anchoredType, validAnchoredJson);
        RequireNoValidationErrors(validAnchored, "Valid AnchoredPatternDto");

        object invalidAnchored = DeserializeContract(
            plugin,
            anchoredType,
            AnchoredPatternJsonTemplate
                .Replace("__PATTERN__", patternJson)
                .Replace("__ANCHORS__", "[]"));
        RequireValidationErrors(
            invalidAnchored,
            "Invalid AnchoredPatternDto without anchor node IDs");

        // ProblemDto: valid (matching topology hash) and invalid
        // (load.topologyHash does not match the anchored pattern).
        string validLoadJson = LoadCaseJsonTemplate.Replace("__HASH__", topologyHash);
        string validProblemJson = ProblemJsonTemplate
            .Replace("__ANCHORED__", validAnchoredJson)
            .Replace("__LOAD__", validLoadJson);
        object validProblem =
            DeserializeContract(plugin, problemType, validProblemJson);
        RequireNoValidationErrors(validProblem, "Valid ProblemDto");

        object invalidProblem = DeserializeContract(
            plugin,
            problemType,
            ProblemJsonTemplate
                .Replace("__ANCHORED__", validAnchoredJson)
                .Replace(
                    "__LOAD__",
                    LoadCaseJsonTemplate.Replace("__HASH__", zeroHash)));
        RequireValidationErrors(
            invalidProblem,
            "Invalid ProblemDto with a load from a different source topology");

        // RelaxedDto: valid (both members present and valid) and invalid
        // (both members missing).
        string preparedJson = TnaPreparedJsonTemplate
            .Replace("__PATTERN__", patternJson)
            .Replace("__HASH__", topologyHash)
            .Replace("__SUPPORTS__", supportSetJson)
            .Replace("__PREPARED_PATTERN__", TnaPreparedPatternJson)
            .Replace("__FORM_GRAPH__", TnaDiagramGraphJson)
            .Replace("__FORCE_GRAPH__", TnaDiagramGraphJson)
            .Replace("__MAPPINGS__", TnaPreparedMappingsJson);
        object prepared = DeserializeContract(plugin, preparedType, preparedJson);
        RequireNoValidationErrors(
            prepared,
            "Valid TnaPreparedDto (spine smoke fixture)");

        object validRelaxed = DeserializeContract(
            plugin,
            relaxedType,
            RelaxedJsonTemplate
                .Replace("__PREPARED__", preparedJson)
                .Replace("__PROBLEM__", validProblemJson));
        RequireNoValidationErrors(validRelaxed, "Valid RelaxedDto");

        object invalidRelaxed =
            DeserializeContract(plugin, relaxedType, RelaxedEmptyJson);
        RequireValidationErrors(
            invalidRelaxed,
            "Invalid RelaxedDto missing both prepared and problem");

        // ResultDto.Problem: optional provenance attach (Task 4 step 4)
        // must not disturb an otherwise-valid TNA result.
        object resultWithProblem = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: CreateInstance(graphType),
            forceGraph: CreateInstance(graphType));
        SetContractProperty(resultWithProblem, resultType, "Problem", validProblem);
        RequireNoValidationErrors(
            resultWithProblem,
            "Valid TNA ResultDto with an attached Problem");
    }

    private static object DeserializeContract(
        Assembly plugin,
        Type contractType,
        string json)
    {
        Type contractJsonType = RequireContractType(plugin, "ContractJson");
        MethodInfo generic = contractJsonType.GetMethod(
            "Deserialize",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ContractJson.Deserialize was not found.");
        MethodInfo bound = generic.MakeGenericMethod(contractType);
        return bound.Invoke(null, new object[] { json })
            ?? throw new InvalidOperationException(
                $"Deserializing {contractType.FullName} returned null.");
    }

    private static string ComputeTopologyHash(Assembly plugin, object topology)
    {
        Type fingerprintType = RequireContractType(plugin, "TopologyFingerprint");
        MethodInfo computeMethod = fingerprintType.GetMethod(
            "Compute",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "TopologyFingerprint.Compute was not found.");
        return computeMethod.Invoke(null, new object[] { topology }) as string
            ?? throw new InvalidOperationException(
                "TopologyFingerprint.Compute returned an unexpected type.");
    }

    private static string DescribeException(Exception exception)
    {
        Exception current = exception;
        var chain = new List<string>();
        while (true)
        {
            chain.Add($"{current.GetType().Name}: {current.Message}");
            if (current.InnerException is null)
                break;
            current = current.InnerException;
        }
        return string.Join(" -> ", chain);
    }

    private static string ResolveRhinoRoot(string? requestedRoot)
    {
        var candidates = new[]
        {
            requestedRoot,
            Environment.GetEnvironmentVariable("RHINO8_ROOT"),
            Path.Combine(
                Environment.GetFolderPath(
                    Environment.SpecialFolder.ProgramFiles),
                "Rhino 8")
        };

        foreach (string? candidate in candidates)
        {
            if (string.IsNullOrWhiteSpace(candidate))
                continue;
            string fullPath = Path.GetFullPath(candidate);
            if (Directory.Exists(fullPath))
                return fullPath;
        }

        throw new UsageException(
            "Rhino 8 was not found. Pass --rhino-root or set RHINO8_ROOT.");
    }

    private static string RequireFile(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException(
                $"Required Rhino/Grasshopper dependency was not found: {path}",
                path);
        return Path.GetFullPath(path);
    }

    private sealed record Options(string PluginPath, string? RhinoRoot)
    {
        public static Options Parse(IReadOnlyList<string> args)
        {
            if (args.Count == 0)
                throw new UsageException("A built .gha path is required.");

            string? pluginPath = null;
            string? rhinoRoot = null;
            for (int index = 0; index < args.Count; index++)
            {
                string argument = args[index];
                if (string.Equals(
                    argument,
                    "--rhino-root",
                    StringComparison.OrdinalIgnoreCase))
                {
                    if (++index >= args.Count)
                        throw new UsageException(
                            "--rhino-root requires a directory.");
                    rhinoRoot = args[index];
                    continue;
                }

                if (argument.StartsWith("-", StringComparison.Ordinal))
                    throw new UsageException(
                        $"Unknown option: {argument}");
                if (pluginPath is not null)
                    throw new UsageException(
                        "Only one plugin path may be supplied.");
                pluginPath = argument;
            }

            if (string.IsNullOrWhiteSpace(pluginPath))
                throw new UsageException("A built .gha path is required.");
            return new Options(pluginPath, rhinoRoot);
        }
    }

    private sealed class UsageException : Exception
    {
        public UsageException(string message)
            : base(message)
        {
        }
    }
}
