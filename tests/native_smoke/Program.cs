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
                new[] { 0 },
            ["Ananke.COMPAS.Native.Components.SupportsComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.LoadsComponent"] =
                new[] { 2 },
            ["Ananke.COMPAS.Native.Components.FdSolveComponent"] =
                new[] { 1 }
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
            "Ananke.COMPAS.Native.Components.DisplayComponent"
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
                    // Course Height joined 2026-08-18 (the Face Courses
                    // banding knob); Face Polylines / Face Courses are the
                    // authored-tessellation feeds added the same day.
                    new[] { "Result", "Course Height" },
                    new[]
                    {
                        "Thrust Mesh",
                        "Member Lines",
                        "Form Lines",
                        "q",
                        "H",
                        "F",
                        "Force State",
                        "Member IDs",
                        "Node IDs",
                        "Support Points",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Points",
                        "Reaction Vectors",
                        "Residuals",
                        "Diagnostics",
                        "Report",
                        "Face Polylines",
                        "Face Courses"
                    })
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
                    new[] { "PAT", "A", "Tol", "RB" },
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
                    "02 Form Finding",
                    new[] { "PRB", "q", "Sag %", "FA" },
                    new[] { "RLX" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveComponent"] = (
                    "TNA Solve",
                    "TNA Solve",
                    "02 Form Finding",
                    new[] { "RLX", "H", "I", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent"] = (
                    "TNA Solve Algebraic",
                    "TNA Solve A",
                    "02 Form Finding",
                    new[] { "RLX", "H", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.FdSolveComponent"] = (
                    "FD Solve",
                    "FD Solve",
                    "02 Form Finding",
                    new[] { "PRB", "q", "Run" },
                    new[] { "RES", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.StyleComponent"] = (
                    "Style",
                    "Style",
                    "03 Visualise",
                    new[] { "Preset", "Weight", "Vector" },
                    new[] { "STY" }),
                ["Ananke.COMPAS.Native.Components.ImportPiecesComponent"] = (
                    "Import Pieces",
                    "Pieces",
                    "07 Delivery",
                    new[] { "P" },
                    // Addendum, 2026-08-20: the flat Courses (C) output is
                    // removed; M/K/S are trees branched by course, B is
                    // the new base-mesh item.
                    new[] { "M", "K", "S", "B", "D" })
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
        if (parameterTypes.Length != 13)
        {
            failures.Add(
                $"Expected 13 public persistent contract parameters, found " +
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
            ValidateTreeRelaxation(plugin);
            Console.WriteLine(
                "PASS  TreeBuilder.RelaxToForces: three equal forces on an "
                + "equilateral triangle put the junction at the centroid with "
                + "its members 120 degrees apart, which is Frei Otto's rule "
                + "recovered as the equal-force case; unequal forces balance "
                + "to a residual under a millionth of the load. Equilibrium is "
                + "MEASURED at the junction, not assumed from the geometry.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"TreeBuilder.RelaxToForces: {DescribeException(exception)}");
        }

        try
        {
            ValidateBeamPlacement(plugin);
            Console.WriteLine(
                "PASS  BeamSolver.ArmsForBar: sweeping symmetric arrangements "
                + "puts the least droop exactly at the station nearest the "
                + "textbook 0.2232L; the arms the solver picks land within one "
                + "station of that inset, beat evenly spaced arms on peak "
                + "deflection, and their reactions sum to the whole load. The "
                + "arm-placement argument is MEASURED.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"BeamSolver.ArmsForBar: {DescribeException(exception)}");
        }

        try
        {
            ValidateTreeDepth(plugin);
            Console.WriteLine(
                "PASS  TreeBuilder.MergeTopology: Depth counts FORKS and loses "
                + "no arms. Eight arms give 0 junctions and 8 roots at depth 0, "
                + "4 and 4 at depth 1, 6 and 2 at depth 2, 7 and 1 at depth 3, "
                + "and saturate there; every arm is still a leaf at every "
                + "depth, which the old tip-capping rule could not say.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"TreeBuilder.MergeTopology: {DescribeException(exception)}");
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

    private static void ValidateIcon(object instance, Type componentType)
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
        object icon = iconProperty?.GetValue(instance)
            ?? throw new InvalidOperationException(
                "Component icon is missing.");
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
        // Finder places by it and Animate re-aims by it on every frame, so
        // testing it once tests both.
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
    /// <c>TreeBuilder.RelaxToForces</c>: a branching junction has to sit where
    /// the forces meeting it sum to zero.
    ///
    /// What this replaced put every junction at the plain MIDPOINT of the two
    /// nodes it merged. A midpoint carries no forces: it is in equilibrium only
    /// when its two branches happen to be symmetric and equally loaded, so
    /// every real tree was being bent.
    ///
    /// Two cases, both on the same equilateral triangle of fixed tips, with one
    /// free junction joined to all three.
    ///
    ///   EQUAL FORCES land the junction on the centroid, and its three members
    ///   come out 120 degrees apart. That is FREI OTTO'S RULE, recovered here
    ///   as the equal-force corner of the general one rather than assumed:
    ///   three equal forces can only balance at 120 degrees.
    ///
    ///   UNEQUAL FORCES (1.5, 1, 1) have no such tidy answer, so the assertion
    ///   is the condition itself: the weighted sum of unit vectors from the
    ///   junction to its neighbours must vanish. Deliberately not 2, 1, 1,
    ///   which is the degenerate case where the heaviest force equals the sum
    ///   of the others and the optimum collapses onto its terminal.
    /// </summary>
    private static void ValidateTreeRelaxation(Assembly plugin)
    {
        Type builder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.TreeBuilder", throwOnError: true)
            ?? throw new InvalidOperationException("TreeBuilder not found.");
        MethodInfo relax = RequireStatic(builder, "RelaxToForces");

        ParameterInfo[] parameters = relax.GetParameters();
        Type point3d = parameters[0].ParameterType.GetGenericArguments()[0];
        Type vector3d = parameters[2].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "RelaxToForces' flow parameter is not an array.");

        double height = Math.Sqrt(3.0) / 2.0;
        var corners = new[]
        {
            (0.0, 0.0),
            (1.0, 0.0),
            (0.5, height),
        };

        CheckOneRelaxation(
            relax, point3d, vector3d, corners,
            new[] { 1.0, 1.0, 1.0 },
            expectCentroid: true, label: "equal forces");
        CheckOneRelaxation(
            relax, point3d, vector3d, corners,
            new[] { 1.5, 1.0, 1.0 },
            expectCentroid: false, label: "unequal forces");
    }

    private static void CheckOneRelaxation(
        MethodInfo relax,
        Type point3d,
        Type vector3d,
        (double X, double Y)[] corners,
        double[] forces,
        bool expectCentroid,
        string label)
    {
        Type listOfPoints = typeof(List<>).MakeGenericType(point3d);
        object nodes = Activator.CreateInstance(listOfPoints)!;
        MethodInfo add = listOfPoints.GetMethod("Add")!;
        foreach ((double x, double y) in corners)
            add.Invoke(nodes, new[] { Activator.CreateInstance(point3d, x, y, 0.0) });
        // The free junction starts well off the answer, so converging on it is
        // the relaxation's doing and not the starting guess's.
        add.Invoke(nodes, new[] { Activator.CreateInstance(point3d, 0.9, 0.9, 0.0) });

        var segments = new List<(int, int)>
        {
            (0, 3),
            (1, 3),
            (2, 3),
        };

        // The flow out of each tip is its own force; the junction's own entry
        // is unused because no segment names it as a child.
        Array flow = Array.CreateInstance(vector3d, 4);
        for (int index = 0; index < forces.Length; index++)
        {
            flow.SetValue(
                Activator.CreateInstance(vector3d, 0.0, 0.0, forces[index]),
                index);
        }
        flow.SetValue(Activator.CreateInstance(vector3d, 0.0, 0.0, 0.0), 3);

        relax.Invoke(
            null,
            new object?[] { nodes, segments, flow, 3, -1, 0.0 });

        MethodInfo item = listOfPoints.GetMethod("get_Item")!;
        (double X, double Y) At(int index)
        {
            object point = item.Invoke(nodes, new object[] { index })!;
            return (
                (double)point3d.GetProperty("X")!.GetValue(point)!,
                (double)point3d.GetProperty("Y")!.GetValue(point)!);
        }

        (double jx, double jy) = At(3);

        if (expectCentroid)
        {
            double cx = corners.Average(corner => corner.X);
            double cy = corners.Average(corner => corner.Y);
            if (Math.Abs(jx - cx) > 1.0e-6 || Math.Abs(jy - cy) > 1.0e-6)
            {
                throw new InvalidOperationException(
                    $"With {label} the junction must land on the centroid "
                    + $"({cx:G6}, {cy:G6}); it landed at ({jx:G6}, {jy:G6}).");
            }

            // Three equal forces balance only at 120 degrees apart.
            for (int a = 0; a < corners.Length; a++)
            {
                int b = (a + 1) % corners.Length;
                double angle = AngleBetween(
                    corners[a].X - jx, corners[a].Y - jy,
                    corners[b].X - jx, corners[b].Y - jy);
                if (Math.Abs(angle - 120.0) > 1.0e-4)
                {
                    throw new InvalidOperationException(
                        $"With {label} members {a} and {b} must meet at 120 "
                        + $"degrees; they meet at {angle:G8}. That is Frei "
                        + "Otto's rule and the relaxation has to recover it.");
                }
            }
        }

        // The condition itself, in both cases: the weighted unit vectors from
        // the junction to its neighbours must sum to nothing.
        double rx = 0.0;
        double ry = 0.0;
        for (int index = 0; index < corners.Length; index++)
        {
            double dx = corners[index].X - jx;
            double dy = corners[index].Y - jy;
            double length = Math.Sqrt((dx * dx) + (dy * dy));
            if (length <= 1.0e-12)
                continue;
            rx += forces[index] * dx / length;
            ry += forces[index] * dy / length;
        }
        double residual = Math.Sqrt((rx * rx) + (ry * ry)) / forces.Sum();
        if (residual > 1.0e-6)
        {
            throw new InvalidOperationException(
                $"With {label} the junction is not in equilibrium: the "
                + $"weighted directions leave a residual of {residual:G6} of "
                + "the load. A junction that does not balance is bending its "
                + "tree.");
        }
    }

    private static double AngleBetween(
        double ax, double ay, double bx, double by)
    {
        double la = Math.Sqrt((ax * ax) + (ay * ay));
        double lb = Math.Sqrt((bx * bx) + (by * by));
        double cosine = ((ax * bx) + (ay * by)) / (la * lb);
        cosine = Math.Min(Math.Max(cosine, -1.0), 1.0);
        return Math.Acos(cosine) * 180.0 / Math.PI;
    }

    /// <summary>
    /// <c>BeamSolver.ArmsForBar</c>: where the column arms stand under a bar.
    ///
    /// The whole placement argument rests on one classical result, and until
    /// now nothing had checked it. A uniformly loaded beam on two symmetric
    /// supports wants them about a fifth of its length in from each end,
    /// because that balances the cantilever moment over each support against
    /// the moment at midspan. The two figures usually quoted are
    ///
    ///   0.2071L  minimises the maximum BENDING MOMENT
    ///   0.2232L  minimises the maximum DEFLECTION
    ///
    /// and it matters which, because they are three percent apart and the
    /// solver has to be measured against the one it actually optimises. This
    /// one scores arrangements by peak deflection, so 0.2232L is its target.
    ///
    /// A forty-one station bar, unit span, uniform load, no anchors, two arms.
    /// Three assertions, none of which an evenly spaced fallback would pass:
    ///
    ///   the arms land SYMMETRICALLY, within one station of 0.2232L. Evenly
    ///   spaced would put them at 0.25L, which is outside that by design: the
    ///   window is one station spacing wide, so the test can tell a solved
    ///   answer from a spaced one rather than merely from a wild one.
    ///
    ///   the solved arrangement BEATS evenly spaced on peak deflection, run
    ///   through the solver's own Response so the comparison is like for like.
    ///
    ///   the reactions SUM TO THE WHOLE LOAD, which is the invariant that
    ///   catches a sign or scale error anywhere in the beam assembly.
    /// </summary>
    private static void ValidateBeamPlacement(Assembly plugin)
    {
        Type solver = plugin.GetType(
            "Ananke.COMPAS.Native.Components.BeamSolver", throwOnError: true)
            ?? throw new InvalidOperationException("BeamSolver not found.");
        MethodInfo arms = solver.GetMethod(
            "ArmsForBar", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException("ArmsForBar not found.");
        MethodInfo response = solver.GetMethod(
            "Response", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException("Response not found.");

        Type point3d = arms.GetParameters()[1].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "ArmsForBar' node parameter is not an array.");

        const int stations = 41;
        const int last = stations - 1;
        Array nodes = Array.CreateInstance(point3d, stations);
        var arc = new double[stations];
        var load = new double[stations];
        for (int index = 0; index < stations; index++)
        {
            double x = (double)index / last;
            arc[index] = x;
            load[index] = 1.0;
            nodes.SetValue(
                Activator.CreateInstance(point3d, x, 0.0, 0.0), index);
        }

        var bar = Enumerable.Range(0, stations).ToList();
        object result = arms.Invoke(
            null,
            new object?[] { bar, nodes, load, new HashSet<int>(), 2, 1.0 })
            ?? throw new InvalidOperationException("ArmsForBar returned null.");
        Type tuple = result.GetType();
        var chosen = ((IEnumerable)tuple.GetField("Item1")!.GetValue(result)!)
            .Cast<int>()
            .OrderBy(value => value)
            .ToArray();
        var reactions = (double[])tuple.GetField("Item3")!.GetValue(result)!;

        if (chosen.Length != 2)
        {
            throw new InvalidOperationException(
                $"Two arms were asked for; {chosen.Length} came back.");
        }
        // The classical number itself, measured where the grid cannot cheat:
        // among SYMMETRIC arrangements the best inset must be the station
        // nearest 0.2232, and the sweep either side of it must be worse.
        int textbook = (int)Math.Round(0.2232 * last);
        double bestSymmetric = double.MaxValue;
        int bestSymmetricAt = -1;
        for (int k = 4; k <= last / 2; k++)
        {
            double peak = PeakDeflection(
                response, arc, load, new[] { k, last - k });
            if (peak < bestSymmetric)
            {
                bestSymmetric = peak;
                bestSymmetricAt = k;
            }
        }
        if (bestSymmetricAt != textbook)
        {
            throw new InvalidOperationException(
                $"Among symmetric arrangements the least droop must be at "
                + $"station {textbook} (inset {(double)textbook / last:G4}, the "
                + "station nearest the textbook 0.2232); the sweep put it at "
                + $"{bestSymmetricAt} (inset "
                + $"{(double)bestSymmetricAt / last:G4}).");
        }

        // The arms the solver actually chose need not be symmetric. On a
        // discrete bar they usually are not, and that is correct rather than a
        // fault: with stations 0.025 apart, neither 0.200 nor 0.225 is the
        // optimum, and one arm at each straddles it and droops less than either
        // matched pair. Measured here: (8,31) peaks at 0.0149 against 0.0221
        // for the symmetric (9,31). So the assertion is that both arms land
        // within one station of the textbook inset, which evenly spaced arms
        // at 0.25 do not.
        double spacing = 1.0 / last;
        foreach (int arm in chosen)
        {
            double inset = Math.Min(arm, last - arm) / (double)last;
            if (Math.Abs(inset - 0.2232) > spacing)
            {
                throw new InvalidOperationException(
                    $"A uniformly loaded bar wants its arms 0.2232 of the way "
                    + $"in from each end; station {arm} is {inset:G4} in. "
                    + "Evenly spaced arms would read 0.25, so that is the "
                    + "likeliest way to fail this.");
            }
        }

        double solvedPeak = PeakDeflection(response, arc, load, chosen);
        double spacedPeak = PeakDeflection(
            response, arc, load, new[] { last / 4, 3 * last / 4 });
        if (!(solvedPeak < spacedPeak))
        {
            throw new InvalidOperationException(
                $"The solved arms must droop less than evenly spaced ones: "
                + $"solved peak {solvedPeak:G6}, spaced peak {spacedPeak:G6}. "
                + "If they are equal the solver is falling back to spacing.");
        }

        double carried = reactions.Sum();
        double applied = load.Sum();
        if (Math.Abs(carried - applied) > 1.0e-9 * applied)
        {
            throw new InvalidOperationException(
                $"The reactions must carry the whole load: {applied:G6} "
                + $"applied, {carried:G6} reacted.");
        }
    }

    private static double PeakDeflection(
        MethodInfo response,
        double[] arc,
        double[] load,
        int[] supports)
    {
        object result = response.Invoke(
            null, new object?[] { arc, load, supports, 1.0 })
            ?? throw new InvalidOperationException("Response returned null.");
        var deflection =
            (double[]?)result.GetType().GetField("Item1")!.GetValue(result)
            ?? throw new InvalidOperationException(
                "Response gave no deflections for a valid support set.");
        return deflection.Select(Math.Abs).Max();
    }

    /// <summary>
    /// <c>TreeBuilder.MergeTopology</c>: what Depth means, and that no arm is
    /// ever lost to it.
    ///
    /// It used to cap the number of TIPS at two to the power of Depth. That
    /// reads like a depth control and is not one: the tips ARE the arms, so a
    /// low Depth did not branch less, it threw away arm positions the beam
    /// solve had just worked out. Depth 0 aggregated every arm on a bar into a
    /// single post and Depth 1 into two, which is why the low numbers behaved
    /// so badly.
    ///
    /// Depth now counts LEVELS OF FORK, which is the thing an author is
    /// choosing, and every arm stays a leaf. Eight arms in a row:
    ///
    ///   depth 0   no fork at all, 8 roots straight to the foot: a fan
    ///   depth 1   4 pairs, 4 roots
    ///   depth 2   those pairs pair, 2 roots
    ///   depth 3   one trunk
    ///   depth 9   the same as 3; past a full binary tree there is nothing
    ///             left to merge, so it saturates instead of misbehaving
    ///
    /// The junction counts follow from that, and the last assertion is the one
    /// that matters most: at every depth all eight arms are still leaves.
    /// </summary>
    private static void ValidateTreeDepth(Assembly plugin)
    {
        Type builder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.TreeBuilder", throwOnError: true)
            ?? throw new InvalidOperationException("TreeBuilder not found.");
        MethodInfo merge = RequireStatic(builder, "MergeTopology");
        Type point3d = merge.GetParameters()[0].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "MergeTopology' tips parameter is not an array.");

        const int count = 8;
        Array tips = Array.CreateInstance(point3d, count);
        for (int index = 0; index < count; index++)
        {
            tips.SetValue(
                Activator.CreateInstance(point3d, (double)index, 0.0, 1.0),
                index);
        }

        var expected = new (int Depth, int Junctions, int Roots)[]
        {
            (0, 0, 8),
            (1, 4, 4),
            (2, 6, 2),
            (3, 7, 1),
            (9, 7, 1),
        };

        foreach ((int depth, int wantJunctions, int wantRoots) in expected)
        {
            object result = merge.Invoke(null, new object?[] { tips, depth })
                ?? throw new InvalidOperationException(
                    "MergeTopology returned null.");
            Type shape = result.GetType();
            var junctions = (Array)shape.GetField("Item1")!.GetValue(result)!;
            var segments = (IEnumerable)shape.GetField("Item2")!.GetValue(result)!;
            var roots = (IEnumerable)shape.GetField("Item3")!.GetValue(result)!;

            int rootCount = roots.Cast<int>().Count();
            if (junctions.Length != wantJunctions || rootCount != wantRoots)
            {
                throw new InvalidOperationException(
                    $"At depth {depth}, {count} arms must give "
                    + $"{wantJunctions} junctions and {wantRoots} roots; they "
                    + $"gave {junctions.Length} and {rootCount}.");
            }

            // Every arm still a leaf: it is either a root of its own or the
            // child of exactly one segment, and never a parent.
            var parents = new HashSet<int>();
            var children = new HashSet<int>();
            foreach (object pair in segments)
            {
                Type edge = pair.GetType();
                children.Add((int)edge.GetField("Item1")!.GetValue(pair)!);
                parents.Add((int)edge.GetField("Item2")!.GetValue(pair)!);
            }
            var rootSet = new HashSet<int>(roots.Cast<int>());
            for (int arm = 0; arm < count; arm++)
            {
                if (parents.Contains(arm))
                {
                    throw new InvalidOperationException(
                        $"At depth {depth}, arm {arm} is carrying another "
                        + "member. An arm is a leaf; only a junction forks.");
                }
                if (!children.Contains(arm) && !rootSet.Contains(arm))
                {
                    throw new InvalidOperationException(
                        $"At depth {depth}, arm {arm} vanished: it is neither "
                        + "joined to a junction nor a root of its own. Depth "
                        + "must change how the arms gather, never how many "
                        + "there are.");
                }
            }
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

        var json = method.Invoke(null, new[] { cellList }) as string
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
