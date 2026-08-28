using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using GH_IO.Serialization;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Grasshopper subcategories, one per COMPAS extension family.
///
/// The naming follows COMPAS's own family names deliberately, so a tab answers
/// "which package family backs this" without a lookup. Each backed tab pairs
/// with one capability flag reported by Backend Health and one optional
/// dependency group in pyproject.toml, so a tab that does nothing is explained
/// by a missing package rather than being a mystery.
///
/// Subcategory is display grouping only. Component identity is the GUID, so
/// regrouping never invalidates a saved definition.
/// </summary>
internal static class ComponentCategories
{
    public const string Category = "Ananke COMPAS";

    // Shared spine. No backend beyond compas itself.
    public const string Model = "01 Model";

    // compas_fd, compas_tna. Capability: fd.solve, tna.solve. Extra: equilibrium.
    public const string FormFinding = "02 Form Finding";

    // Viewport preview only. No backend.
    public const string Visualise = "03 Visualise";

    // compas_dem, compas_assembly, compas_cra. Capability: masonry. Extra: masonry.
    // Reserved.
    public const string Masonry = "04 Masonry";

    // compas_fea2 plus a solver backend. Capability: fea. Extra: fea.
    public const string Engineering = "05 Engineering";

    // compas_fab, compas_robots. Capability: fab. Extra: fab.
    public const string Fabrication = "06 Fabrication";

    // compas_model, compas_ifc. Capability: model, ifc. Extras: model, ifc.
    public const string Delivery = "07 Delivery";

    // Backend Health and other diagnostics. No solver backend of its own.
    public const string System = "90 System";
}

public sealed record ComponentValueListSpec(
    int InputIndex,
    string Name,
    IReadOnlyList<(string Label, string Value)> Items,
    string DefaultValue,
    bool CheckList = false);

/// <summary>
/// Places populated value lists beside the inputs they answer, so the valid
/// values are visible on the canvas without reading the documentation.
///
/// The placement is shared by every native base class here. It used to be
/// duplicated, and the duplicate carried the same defect twice.
/// </summary>
internal static class SuggestedValueListPlacement
{
    public static void Create(
        GH_Component owner,
        IReadOnlyList<ComponentValueListSpec> specs,
        GH_Document document)
    {
        foreach (ComponentValueListSpec spec in specs)
        {
            if (spec.InputIndex < 0 ||
                spec.InputIndex >= owner.Params.Input.Count)
            {
                continue;
            }

            IGH_Param input = owner.Params.Input[spec.InputIndex];
            if (input.SourceCount > 0 || input.HasProxySources)
                continue;

            var valueList = new GH_ValueList
            {
                Name = spec.Name,
                NickName = spec.Name,
                Description = $"Supported values for {input.Name}.",
                ListMode = spec.CheckList ? GH_ValueListMode.CheckList : GH_ValueListMode.DropDown
            };
            valueList.ListItems.Clear();
            foreach ((string label, string value) in spec.Items)
            {
                valueList.ListItems.Add(
                    new GH_ValueListItem(label, QuoteExpression(value)));
            }

            if (spec.CheckList)
            {
                // Split DefaultValue on comma, trim, collect for matching
                var selectedValues = (spec.DefaultValue ?? string.Empty)
                    .Split(',')
                    .Select(v => v.Trim())
                    .ToList();

                // Mark items as selected based on raw value comparison
                // Iterate through original Items and corresponding ListItems
                int itemIndex = 0;
                foreach ((string label, string value) in spec.Items)
                {
                    valueList.ListItems[itemIndex].Selected = selectedValues.Contains(
                        value,
                        StringComparer.OrdinalIgnoreCase);
                    itemIndex++;
                }
            }
            else
            {
                // Original single-select logic for DropDown
                int selectedIndex = spec.Items
                    .Select((item, index) => (item.Value, index))
                    .Where(item => string.Equals(
                        item.Value,
                        spec.DefaultValue,
                        StringComparison.OrdinalIgnoreCase))
                    .Select(item => item.index)
                    .DefaultIfEmpty(0)
                    .First();

                // Set the selection both ways round rather than trusting
                // SelectItem alone, because whether it assigns or toggles cannot
                // be established here without Rhino running. Clearing first makes
                // the outcome identical under either reading.
                foreach (GH_ValueListItem item in valueList.ListItems)
                    item.Selected = false;
                valueList.SelectItem(selectedIndex);
            }
            valueList.CreateAttributes();

            // Placement is a convenience, not a requirement. Attributes can
            // legitimately be null before they have been created, so fall
            // back to the default position rather than throwing.
            if (owner.Attributes is not null &&
                input.Attributes is not null &&
                valueList.Attributes is not null)
            {
                // Attributes.Pivot is not a stored point. It is read off the
                // centre of Bounds, and Bounds on a freshly dropped component
                // holds whatever the last layout pass computed, not where the
                // object visibly sits. Reading it without forcing a layout
                // lands the lists near the canvas origin instead of beside
                // their input. ExpireLayout marks the cached boxes stale and
                // PerformLayout recomputes them immediately, every param box
                // included, so the input's own Pivot is real on return.
                //
                // AddedToDocument fires on a drop or a file reopen, never
                // while Grasshopper is solving, so mutating the canvas from
                // it directly is safe.
                owner.Attributes.ExpireLayout();
                owner.Attributes.PerformLayout();

                PointF pivot = input.Attributes.Pivot;
                valueList.Attributes.Pivot =
                    new PointF(pivot.X - 220.0f, pivot.Y - 10.0f);

                // The same forcing aimed at the new list. Its Bounds were
                // sized for an empty control back at CreateAttributes, before
                // it held any items or had a pivot, so lay it out again to
                // size it to what it actually holds.
                valueList.Attributes.ExpireLayout();
                valueList.Attributes.PerformLayout();
            }

            if (document.AddObject(valueList, false))
            {
                input.AddSource(valueList);
                valueList.ExpireSolution(true);
            }
        }
    }

    private static string QuoteExpression(string value) =>
        "\"" +
        value
            .Replace("\\", "\\\\", StringComparison.Ordinal)
            .Replace("\"", "\\\"", StringComparison.Ordinal) +
        "\"";
}

/// <summary>
/// Re-asserts each parameter's registered identity after a document read.
///
/// Grasshopper restores parameter names, nicknames, optionality, preview
/// visibility, and data mapping (graft/flatten) from the saved definition.
/// When a component's surface changed between plugin versions (ports
/// renamed, removed, or made optional), the archived values land on
/// whichever current port shares the index: a required "V" appears where
/// an optional "I" now lives, and the component errors on inputs that are
/// meant to be blank. The registered identity, captured before the read,
/// wins.
///
/// Data mapping is the one property with two owners. A mapping the plugin
/// REGISTERED (Flatten on a list port) is part of that port's identity and
/// wins over the archive, so a flatten added in a later plugin version
/// reaches definitions saved before it. A port registered with NO mapping
/// is the author's to graft or flatten on the canvas, and the archive
/// keeps their choice; re-asserting None there would silently undo it on
/// every reopen.
/// </summary>
internal static class ParameterIdentity
{
    internal readonly record struct Snapshot(
        string Name,
        string NickName,
        string Description,
        bool Optional,
        bool? Hidden,
        GH_DataMapping DataMapping);

    internal static Snapshot[] Capture(IList<IGH_Param> parameters)
    {
        var snapshots = new Snapshot[parameters.Count];
        for (int index = 0; index < parameters.Count; index++)
        {
            IGH_Param parameter = parameters[index];
            snapshots[index] = new Snapshot(
                parameter.Name,
                parameter.NickName,
                parameter.Description,
                parameter.Optional,
                parameter is IGH_PreviewObject preview
                    ? preview.Hidden
                    : null,
                parameter.DataMapping);
        }
        return snapshots;
    }

    internal static void Restore(
        IList<IGH_Param> parameters,
        Snapshot[] snapshots)
    {
        int count = Math.Min(parameters.Count, snapshots.Length);
        for (int index = 0; index < count; index++)
        {
            IGH_Param parameter = parameters[index];
            Snapshot snapshot = snapshots[index];
            parameter.Name = snapshot.Name;
            parameter.NickName = snapshot.NickName;
            parameter.Description = snapshot.Description;
            parameter.Optional = snapshot.Optional;
            if (snapshot.Hidden is bool hidden &&
                parameter is IGH_PreviewObject preview)
            {
                preview.Hidden = hidden;
            }
            if (snapshot.DataMapping != GH_DataMapping.None)
                parameter.DataMapping = snapshot.DataMapping;
        }
    }
}

public abstract class NativeComponentBase : GH_Component
{
    private readonly string _iconName;
    private bool _readFromArchive;
    private bool _suggestedListsAttempted;

    protected NativeComponentBase(
        string name,
        string nickname,
        string description,
        string subcategory,
        string iconName)
        : base(
            name,
            nickname,
            description,
            ComponentCategories.Category,
            subcategory)
    {
        _iconName = iconName;
    }

    protected override Bitmap? Icon => PluginResources.Icon(_iconName);

    public override GH_Exposure Exposure => GH_Exposure.primary;

    private protected virtual IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists =>
        Array.Empty<ComponentValueListSpec>();

    public override bool Read(GH_IReader reader)
    {
        _readFromArchive = true;
        ParameterIdentity.Snapshot[] inputs =
            ParameterIdentity.Capture(Params.Input);
        ParameterIdentity.Snapshot[] outputs =
            ParameterIdentity.Capture(Params.Output);
        bool result = base.Read(reader);
        ParameterIdentity.Restore(Params.Input, inputs);
        ParameterIdentity.Restore(Params.Output, outputs);
        return result;
    }

    public override void AddedToDocument(GH_Document document)
    {
        base.AddedToDocument(document);

        if (_readFromArchive || _suggestedListsAttempted)
            return;

        _suggestedListsAttempted = true;
        CreateSuggestedValueLists(document);
    }

    protected override void AppendAdditionalComponentMenuItems(
        ToolStripDropDown menu)
    {
        base.AppendAdditionalComponentMenuItems(menu);
        if (SuggestedValueLists.Count == 0)
            return;

        Menu_AppendSeparator(menu);
        Menu_AppendItem(
            menu,
            "Create suggested value lists",
            (_, _) =>
            {
                GH_Document? document = OnPingDocument();
                if (document is not null)
                    CreateSuggestedValueLists(document);
            });
    }

    private void CreateSuggestedValueLists(GH_Document document) =>
        SuggestedValueListPlacement.Create(
            this,
            SuggestedValueLists,
            document);

    protected void ReportException(string operation, Exception error)
    {
        string message = error.GetBaseException().Message;
        AddRuntimeMessage(
            GH_RuntimeMessageLevel.Error,
            $"{operation}: {message}");
    }
}

public abstract class NativeTaskComponentBase<TResult> :
    GH_TaskCapableComponent<TResult>
{
    private readonly string _iconName;
    private bool _readFromArchive;
    private bool _suggestedListsAttempted;

    protected NativeTaskComponentBase(
        string name,
        string nickname,
        string description,
        string subcategory,
        string iconName)
        : base(
            name,
            nickname,
            description,
            ComponentCategories.Category,
            subcategory)
    {
        _iconName = iconName;
        UseTasks = true;
    }

    protected override Bitmap? Icon => PluginResources.Icon(_iconName);

    public override GH_Exposure Exposure => GH_Exposure.primary;

    private protected virtual IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists =>
        Array.Empty<ComponentValueListSpec>();

    public override bool Read(GH_IReader reader)
    {
        _readFromArchive = true;
        ParameterIdentity.Snapshot[] inputs =
            ParameterIdentity.Capture(Params.Input);
        ParameterIdentity.Snapshot[] outputs =
            ParameterIdentity.Capture(Params.Output);
        bool result = base.Read(reader);
        ParameterIdentity.Restore(Params.Input, inputs);
        ParameterIdentity.Restore(Params.Output, outputs);
        return result;
    }

    public override void AddedToDocument(GH_Document document)
    {
        base.AddedToDocument(document);
        if (_readFromArchive || _suggestedListsAttempted)
            return;

        _suggestedListsAttempted = true;
        CreateSuggestedValueLists(document);
    }

    protected override void AppendAdditionalComponentMenuItems(
        ToolStripDropDown menu)
    {
        base.AppendAdditionalComponentMenuItems(menu);
        if (SuggestedValueLists.Count == 0)
            return;

        Menu_AppendSeparator(menu);
        Menu_AppendItem(
            menu,
            "Create suggested value lists",
            (_, _) =>
            {
                GH_Document? document = OnPingDocument();
                if (document is not null)
                    CreateSuggestedValueLists(document);
            });
    }

    private void CreateSuggestedValueLists(GH_Document document) =>
        SuggestedValueListPlacement.Create(
            this,
            SuggestedValueLists,
            document);

    protected void ReportException(string operation, Exception error)
    {
        string message = error.GetBaseException().Message;
        AddRuntimeMessage(
            GH_RuntimeMessageLevel.Error,
            $"{operation}: {message}");
    }
}
