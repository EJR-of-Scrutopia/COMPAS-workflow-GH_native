#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Diagnose: read every diagnostic the chain wrote into a Result and say,
    /// in words, what is wrong and which lever to pull.
    ///
    /// It renders what Columns, Animate and Monitor appended, severity first
    /// and grouped by source, and adds the CROSS-CHECKS no single component
    /// can make: Columns ran on a Result with no principal runs; Animate ran
    /// with no Columns upstream; every anchor is in a strip of its own; more
    /// than half the net wants pushing up. Every check names the lever.
    /// </summary>
    public sealed class DiagnoseComponent : NativeComponentBase
    {
        private static readonly string[] NativeOrder = { "Columns", "Animate", "Monitor", "Diagnose" };

        public DiagnoseComponent()
            : base(
                "Diagnose",
                "DG",
                "Read every diagnostic the chain wrote into a Result and say in "
                    + "plain English what is wrong and which lever to pull. "
                    + "Replaces the Report ports the mould components used to "
                    + "carry.",
                ComponentCategories.Visualise,
                "diagnose")
        {
        }

        public override Guid ComponentGuid =>
            new("3f6b2c41-8d9e-4a57-b1c0-5e2f7a9d4c18");

        protected override void RegisterInputParams(GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Any Result in the chain. The further down the chain it comes "
                    + "from, the more it has to say.",
                GH_ParamAccess.item);
        }

        protected override void RegisterOutputParams(GH_OutputParamManager parameters)
        {
            parameters.AddTextParameter(
                "Text",
                "T",
                "The diagnostics in words, errors first, grouped by the "
                    + "component that raised them, the solver's own report last.",
                GH_ParamAccess.item);
            parameters.AddTextParameter("Source", "S",
                "Which component raised each entry. A TREE branched by source; "
                    + "Code, Severity, Message and Value are branched and ordered "
                    + "identically.",
                GH_ParamAccess.tree);
            parameters.AddTextParameter("Code", "C",
                "The entry's code, namespaced by its source (columns.lean).",
                GH_ParamAccess.tree);
            parameters.AddTextParameter("Severity", "SV",
                "ok, info, warning or error.", GH_ParamAccess.tree);
            parameters.AddTextParameter("Message", "M",
                "The entry in words.", GH_ParamAccess.tree);
            parameters.AddNumberParameter("Value", "V",
                "The entry's number where it has one; NaN where it does not, so "
                    + "the tree stays aligned with Message.",
                GH_ParamAccess.tree);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) || goo?.Value is not ResultDto result)
                return;

            List<DiagnosticDto> all = Collect(result);

            IReadOnlyList<(string Source, List<DiagnosticDto> Entries)> groups = Group(all);
            data.SetData(0, Render(result, all));
            data.SetDataTree(1, OutputTree.Strings(groups.Select(g => g.Entries.Select(_ => g.Source))));
            data.SetDataTree(2, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Code))));
            data.SetDataTree(3, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Severity))));
            data.SetDataTree(4, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Message))));
            data.SetDataTree(5, OutputTree.Numbers(groups.Select(g => g.Entries.Select(e => e.Value ?? double.NaN))));
            Message = all.Any(e => e.Severity == "error") ? "errors"
                : all.Any(e => e.Severity == "warning") ? $"{all.Count(e => e.Severity == "warning")} warnings"
                : "clean";
        }

        /// <summary>
        /// Everything Diagnose has to say about a Result: the entries it
        /// already carries, plus the cross-checks when it validates, or one
        /// error entry per validation failure when it does not. Static so
        /// the harness can drive the invalid path without Grasshopper.
        /// </summary>
        internal static List<DiagnosticDto> Collect(ResultDto result)
        {
            var all = new List<DiagnosticDto>(result.Diagnostics);
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
            {
                foreach (string error in errors)
                {
                    all.Add(ResultDiagnostics.Entry("Diagnose", "diagnose.invalid_result", "error",
                        $"this Result does not validate: {error}"));
                }
            }
            else
            {
                all.AddRange(CrossChecks(result));
            }
            return all;
        }

        /// <summary>
        /// The checks no single component can make, computed from the Result
        /// alone. Each one names the lever to pull.
        /// </summary>
        internal static List<DiagnosticDto> CrossChecks(ResultDto result)
        {
            const string S = "Diagnose";
            var d = new List<DiagnosticDto>();
            EquilibriumResultDto? eq = result.Equilibrium;
            MouldDto? mould = result.Mould;
            if (eq is null)
                return d;
            int n = eq.Vertices.Count;

            if (mould?.Columns is not null && MouldGeometry.PrincipalRuns(eq, n).Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "diagnose.no_principal_runs", "warning",
                    "Columns ran on a Result that carries no principal runs, so it "
                        + "had nothing to stand under. Draw Principal Lines into "
                        + "Pattern upstream."));
            }
            if (mould?.Frame is not null && mould.Columns is null)
            {
                d.Add(ResultDiagnostics.Entry(S, "diagnose.frame_without_columns", "warning",
                    "Animate ran with no Columns upstream, so this frame has no "
                        + "columns to raise. Wire Columns between Solve and Animate."));
            }
            if (n > 0)
            {
                (int, int)[] edges = MouldGeometry.ValidEdges(eq, n, out _);
                List<int>[] grouping = MouldGeometry.GroupingAdjacency(result, edges, n);
                var anchors = eq.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n).ToList();
                if (anchors.Count > 1 &&
                    MouldGeometry.ConnectedGroups(anchors, grouping).Count == anchors.Count)
                {
                    d.Add(ResultDiagnostics.Entry(S, "diagnose.anchors_all_isolated", "warning",
                        "every anchor is in a strip of its own: no two anchors are "
                            + "joined in either the plan or the solved net, which means "
                            + "this Result has lost its source Pattern. Re-solve from "
                            + "Pattern so the sides are continuous.",
                        anchors.Count, unit: "anchors"));
                }
            }

            DiagnosticDto? push = result.Diagnostics.FirstOrDefault(x => x.Code == "animate.nodes_want_push");
            if (push?.Value is double wants &&
                push.Context.TryGetValue("total", out string? totalText) &&
                int.TryParse(totalText, NumberStyles.Integer, CultureInfo.InvariantCulture, out int total) &&
                total > 0 && wants * 2.0 > total)
            {
                d.Add(ResultDiagnostics.Entry(S, "diagnose.push_needed", "warning",
                    $"{wants:0} of {total} nodes want pushing up, and a reel only "
                        + "pulls. More than half the net asks for a mechanism this "
                        + "machine does not have: tighten the rib spacing, shape the "
                        + "bays as saddles, or lift from below at the fewest points, "
                        + "in that order.",
                    wants, total / 2.0, "nodes"));
            }
            return d;
        }

        internal static IReadOnlyList<(string Source, List<DiagnosticDto> Entries)> Group(
            IEnumerable<DiagnosticDto> all)
        {
            var bySource = new Dictionary<string, List<DiagnosticDto>>(StringComparer.Ordinal);
            var order = new List<string>();
            foreach (DiagnosticDto entry in all)
            {
                string source = ResultDiagnostics.SourceOf(entry);
                if (!bySource.TryGetValue(source, out List<DiagnosticDto>? list))
                {
                    list = new List<DiagnosticDto>();
                    bySource[source] = list;
                    order.Add(source);
                }
                list.Add(entry);
            }
            // Worker sources first in the order met, then the natives in chain order.
            var ordered = order.Where(s => !NativeOrder.Contains(s)).ToList();
            ordered.AddRange(NativeOrder.Where(bySource.ContainsKey));
            return ordered.Select(s => (s, bySource[s])).ToList();
        }

        internal static string Render(ResultDto result, IReadOnlyList<DiagnosticDto> all)
        {
            int Rank(string severity) => severity switch
            {
                "error" => 0,
                "warning" => 1,
                "info" => 2,
                _ => 3,
            };
            var text = new StringBuilder();
            foreach ((string source, List<DiagnosticDto> entries) in Group(all))
            {
                text.AppendLine($"{source}:");
                foreach (DiagnosticDto e in entries.OrderBy(e => Rank(e.Severity)))
                {
                    text.Append("  [").Append(e.Severity).Append("] ").Append(e.Message);
                    if (e.Value is double value)
                    {
                        text.Append(" (").Append(value.ToString("G6", CultureInfo.InvariantCulture));
                        if (!string.IsNullOrWhiteSpace(e.Unit))
                            text.Append(' ').Append(e.Unit);
                        if (e.Tolerance is double tolerance)
                            text.Append(", limit ").Append(tolerance.ToString("G6", CultureInfo.InvariantCulture));
                        text.Append(')');
                    }
                    text.AppendLine();
                }
                text.AppendLine();
            }

            var notRun = new List<string>();
            if (result.Mould?.Columns is null)
                notRun.Add("Columns");
            if (result.Mould?.Frame is null)
                notRun.Add("Animate");
            if (!all.Any(e => ResultDiagnostics.SourceOf(e) == "Monitor"))
                notRun.Add("Monitor");
            if (notRun.Count > 0)
                text.AppendLine($"not yet run on this Result: {string.Join(", ", notRun)}").AppendLine();

            text.AppendLine("solver report:");
            text.AppendLine(string.IsNullOrWhiteSpace(result.Report)
                ? (string.Equals(result.Solver, "fd", StringComparison.OrdinalIgnoreCase)
                    ? "FD result: no reciprocal diagram."
                    : "(none)")
                : result.Report);
            return text.ToString().TrimEnd();
        }
    }
}
