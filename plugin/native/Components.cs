using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using Grasshopper.Kernel;
using RhinoCodePluginGH.Components;
using RhinoCodePluginGH.Parameters;

namespace Ananke.COMPAS
{
    public sealed class PortSpec
    {
        public PortSpec(string name, string type, GH_ParamAccess access = GH_ParamAccess.item)
        {
            Name = name;
            Type = type;
            Access = access;
        }

        public string Name { get; }
        public string Type { get; }
        public GH_ParamAccess Access { get; }
    }

    internal static class Embedded
    {
        private const string PythonBootstrap =
            "\nimport os as _ae_os\n" +
            "import sys as _ae_sys\n" +
            "_ae_root = _ae_os.path.join(_ae_os.environ.get('APPDATA', ''), " +
            "'Grasshopper', 'Libraries', 'Ananke_COMPAS', 'python')\n" +
            "if _ae_root and _ae_root not in _ae_sys.path:\n" +
            "    _ae_sys.path.insert(0, _ae_root)\n\n";

        private static readonly Assembly Assembly = typeof(Embedded).Assembly;
        private static readonly Dictionary<string, Bitmap> Icons =
            new Dictionary<string, Bitmap>(StringComparer.OrdinalIgnoreCase);

        public static string Script(string fileName)
        {
            string resourceName = "Ananke.COMPAS.Scripts." + fileName;
            using (Stream stream = Assembly.GetManifestResourceStream(resourceName))
            {
                if (stream == null)
                    throw new InvalidOperationException("Missing embedded script " + resourceName);

                using (var reader = new StreamReader(stream))
                {
                    string source = reader.ReadToEnd()
                        .Replace("# venv: ananke-equilibrium", "# venv: catenary-compas-2026");
                    int insertion = source.IndexOf("\"\"\"", StringComparison.Ordinal);
                    return insertion >= 0
                        ? source.Insert(insertion, PythonBootstrap)
                        : source + PythonBootstrap;
                }
            }
        }

        public static Bitmap Icon(string fileName)
        {
            lock (Icons)
            {
                Bitmap existing;
                if (Icons.TryGetValue(fileName, out existing))
                    return existing;

                string resourceName = "Ananke.COMPAS.Icons." + fileName;
                using (Stream stream = Assembly.GetManifestResourceStream(resourceName))
                {
                    if (stream == null)
                        throw new InvalidOperationException("Missing embedded icon " + resourceName);

                    // Detach the cached bitmap from the embedded-resource
                    // stream before that stream is disposed.
                    Bitmap bitmap;
                    using (var source = new Bitmap(stream))
                        bitmap = new Bitmap(source);
                    Icons[fileName] = bitmap;
                    return bitmap;
                }
            }
        }
    }

    public sealed class AnankeAssemblyInfo : GH_AssemblyInfo
    {
        public override string Name => "Ananke COMPAS";
        public override Bitmap Icon => Embedded.Icon("network.png");
        public override string Description =>
            "Bundle-first COMPAS FD, TNA, diagnostics, and graphic-statics workflow.";
        public override Guid Id => new Guid("d4c49da9-26d9-4c0d-89c0-958fa3ec5834");
        public override string AuthorName => "Edward / Ananke Eidos Studio";
        public override string AuthorContact => "edrowbo@googlemail.com";
    }

    public abstract class AnankeScriptComponent :
        BaseScriptComponent<ScriptParam, ScriptLibraryParam>
    {
        protected AnankeScriptComponent(
            Guid componentGuid,
            string name,
            string nickname,
            string description,
            string subcategory,
            string scriptFile,
            string iconFile,
            IEnumerable<PortSpec> inputs,
            IEnumerable<PortSpec> outputs)
            : base(
                componentGuid,
                Path.GetFileNameWithoutExtension(iconFile),
                Path.GetFileNameWithoutExtension(iconFile),
                name,
                nickname,
                description,
                "Ananke COMPAS",
                subcategory)
        {
            // BaseScriptComponent's protected constructor does not create the
            // editing context. Rhino's sealed ScriptComponent initializes it
            // immediately after the base call, so custom subclasses must do
            // the same before changing any script-parameter settings.
            Context = new ScriptContext(this);

            UsingScriptInputParam = false;
            UsingLibraryInputParam = false;
            UsingScriptOutputParam = false;
            UsingStandardOutputParam = false;

            foreach (IGH_Param parameter in Params.Input.ToArray())
                Params.UnregisterInputParameter(parameter, true);
            foreach (IGH_Param parameter in Params.Output.ToArray())
                Params.UnregisterOutputParameter(parameter, true);

            foreach (PortSpec spec in inputs)
                Params.RegisterInputParam(CreateParameter(spec));
            foreach (PortSpec spec in outputs)
                Params.RegisterOutputParam(CreateParameter(spec));

            Name = name;
            NickName = nickname;
            Description = description;
            Tooltip = description;
            Category = "Ananke COMPAS";
            SubCategory = subcategory;

            SetSource(Embedded.Script(scriptFile));
            SetParametersToScript();
            VariableParameterMaintenance();
            SetIcon(Embedded.Icon(iconFile));
        }

        private static ScriptVariableParam CreateParameter(PortSpec spec)
        {
            return new ScriptVariableParam(spec.Name)
            {
                VariableName = spec.Name,
                Name = spec.Name,
                NickName = spec.Name,
                PrettyName = spec.Name,
                Description = spec.Name + " (" + spec.Type + ")",
                Access = spec.Access,
                Optional = true
            };
        }
    }

    public sealed class NetworkComponent : AnankeScriptComponent
    {
        public NetworkComponent() : base(
            new Guid("736f0499-6598-4c05-9bb5-193f32cace4b"),
            "Network", "Network",
            "Register connected lines, polylines, or mesh edges as one topology.",
            "01 Inputs", "AE_Network.py", "network.png",
            new[]
            {
                new PortSpec("Geometry", "list[object]", GH_ParamAccess.list),
                new PortSpec("Kind", "str"),
                new PortSpec("AnalysisPlane", "object"),
                new PortSpec("Tolerance", "float"),
                new PortSpec("LengthUnit", "str")
            },
            new[]
            {
                new PortSpec("Topology", "TopologyBundle"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("736f0499-6598-4c05-9bb5-193f32cace4b");
    }

    public sealed class SupportSetComponent : AnankeScriptComponent
    {
        public SupportSetComponent() : base(
            new Guid("1839afa7-85de-4ea5-a62e-eadbf306218a"),
            "Support Set", "Supports",
            "Collect form-finding supports for a registered topology.",
            "01 Inputs", "AE_SupportSet.py", "support_set.png",
            new[]
            {
                new PortSpec("Topology", "TopologyBundle"),
                new PortSpec("Points", "list[point]", GH_ParamAccess.list),
                new PortSpec("NodeIDs", "list[int]", GH_ParamAccess.list),
                new PortSpec("Mode", "str"),
                new PortSpec("SnapTolerance", "float")
            },
            new[]
            {
                new PortSpec("Supports", "SupportSet"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("1839afa7-85de-4ea5-a62e-eadbf306218a");
    }

    public sealed class LoadCaseComponent : AnankeScriptComponent
    {
        public LoadCaseComponent() : base(
            new Guid("dfd21fc8-5c26-43fc-9c85-671cadf9469f"),
            "Load Case", "Loads",
            "Map nodal load vectors to a registered topology.",
            "01 Inputs", "AE_LoadCase.py", "load_case.png",
            new[]
            {
                new PortSpec("Topology", "TopologyBundle"),
                new PortSpec("Points", "list[point]", GH_ParamAccess.list),
                new PortSpec("NodeIDs", "list[int]", GH_ParamAccess.list),
                new PortSpec("Vectors", "list[vector]", GH_ParamAccess.list),
                new PortSpec("Distribution", "str"),
                new PortSpec("CaseName", "str"),
                new PortSpec("Factor", "float")
            },
            new[]
            {
                new PortSpec("Loads", "LoadCase"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("dfd21fc8-5c26-43fc-9c85-671cadf9469f");
    }

    public sealed class FDSettingsComponent : AnankeScriptComponent
    {
        public FDSettingsComponent() : base(
            new Guid("6e9fc3d6-216f-4a7b-b3a0-3ef8f639b670"),
            "FD Settings", "FD Settings",
            "Bundle scalar or member-aligned force densities.",
            "02 Form Finding", "AE_FDSettings.py", "fd_settings.png",
            new[] { new PortSpec("ForceDensity", "object") },
            new[]
            {
                new PortSpec("Config", "FDConfig"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("6e9fc3d6-216f-4a7b-b3a0-3ef8f639b670");
    }

    public sealed class TNAControlComponent : AnankeScriptComponent
    {
        public TNAControlComponent() : base(
            new Guid("0931fd73-1b02-4c31-b684-4dc712fefee1"),
            "TNA Control", "TNA Control",
            "Bundle height and advanced TNA iteration controls.",
            "02 Form Finding", "AE_TNAControl.py", "tna_control.png",
            new[]
            {
                new PortSpec("HeightMode", "str"),
                new PortSpec("HeightValue", "float"),
                new PortSpec("HorizontalAlpha", "float"),
                new PortSpec("HorizontalIterations", "int"),
                new PortSpec("VerticalIterations", "int"),
                new PortSpec("SolveTolerance", "float")
            },
            new[]
            {
                new PortSpec("Height", "HeightControl"),
                new PortSpec("Config", "TNAConfig"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("0931fd73-1b02-4c31-b684-4dc712fefee1");
    }

    public sealed class FDSolveComponent : AnankeScriptComponent
    {
        public FDSolveComponent() : base(
            new Guid("b4699bc8-7588-4334-98ae-19c1da05b348"),
            "FD Solve", "FD",
            "Run whole-network force-density form finding.",
            "02 Form Finding", "AE_FDSolve.py", "fd_solve.png",
            new[]
            {
                new PortSpec("Topology", "TopologyBundle"),
                new PortSpec("Supports", "SupportSet"),
                new PortSpec("Loads", "LoadCase"),
                new PortSpec("Config", "FDConfig")
            },
            new[]
            {
                new PortSpec("Case", "SolvedCase"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("b4699bc8-7588-4334-98ae-19c1da05b348");
    }

    public sealed class TNASolveComponent : AnankeScriptComponent
    {
        public TNASolveComponent() : base(
            new Guid("2f0207dc-0a0a-4922-9c78-b2ece7fc4e81"),
            "TNA Solve", "TNA",
            "Run whole-pattern thrust-network analysis.",
            "02 Form Finding", "AE_TNASolve.py", "tna_solve.png",
            new[]
            {
                new PortSpec("Topology", "TopologyBundle"),
                new PortSpec("Supports", "SupportSet"),
                new PortSpec("Loads", "LoadCase"),
                new PortSpec("Height", "HeightControl"),
                new PortSpec("Config", "TNAConfig")
            },
            new[]
            {
                new PortSpec("Case", "SolvedCase"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("2f0207dc-0a0a-4922-9c78-b2ece7fc4e81");
    }

    public sealed class ValidateComponent : AnankeScriptComponent
    {
        public ValidateComponent() : base(
            new Guid("739d6857-f5ab-41ee-9eb3-c09850253aa8"),
            "Validate", "Validate",
            "Report residual, closure, reciprocity, and planarity diagnostics.",
            "03 Diagnostics", "AE_Validate.py", "validate.png",
            new[]
            {
                new PortSpec("Case", "SolvedCase"),
                new PortSpec("ResidualTolerance", "float"),
                new PortSpec("ClosureTolerance", "float"),
                new PortSpec("AngleTolerance", "float"),
                new PortSpec("PlanarityTolerance", "float")
            },
            new[]
            {
                new PortSpec("Diagnostics", "list[Diagnostic]", GH_ParamAccess.list),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("739d6857-f5ab-41ee-9eb3-c09850253aa8");
    }

    public sealed class DiagramStyleComponent : AnankeScriptComponent
    {
        public DiagramStyleComponent() : base(
            new Guid("f7abccbd-ae6c-4f6b-bc57-857222c9d06f"),
            "Diagram Style", "Style",
            "Define graphic-statics colours, scales, labels, and construction display.",
            "04 Visualisation", "AE_DiagramStyle.py", "diagram_style.png",
            new[]
            {
                new PortSpec("Preset", "str"),
                new PortSpec("ForceScale", "float"),
                new PortSpec("VectorScale", "float"),
                new PortSpec("LabelDensity", "int"),
                new PortSpec("ShowLabels", "bool"),
                new PortSpec("ShowConstruction", "bool")
            },
            new[]
            {
                new PortSpec("Style", "DiagramStyle"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("f7abccbd-ae6c-4f6b-bc57-857222c9d06f");
    }

    public sealed class PreviewPayloadComponent : AnankeScriptComponent
    {
        public PreviewPayloadComponent() : base(
            new Guid("3b9febf7-22f1-4e04-83c3-1c28d401f65e"),
            "Preview Payload", "Preview",
            "Create display-ready form, force, load, reaction, label, and error geometry.",
            "04 Visualisation", "AE_PreviewPayload.py", "preview_payload.png",
            new[]
            {
                new PortSpec("Case", "SolvedCase"),
                new PortSpec("Style", "DiagramStyle"),
                new PortSpec("Kind", "str"),
                new PortSpec("Dimension", "int")
            },
            new[]
            {
                new PortSpec("Diagram", "DiagramBundle"),
                new PortSpec("Status", "str")
            }) { }

        public override Guid ComponentGuid =>
            new Guid("3b9febf7-22f1-4e04-83c3-1c28d401f65e");
    }
}
