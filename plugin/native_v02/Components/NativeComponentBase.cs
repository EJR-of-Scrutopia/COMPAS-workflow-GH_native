using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using GH_IO.Serialization;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;

namespace Ananke.COMPAS.Native.Components;

internal static class ComponentCategories
{
    public const string Category = "Ananke COMPAS";
    public const string Model = "01 Model";
    public const string FormFinding = "02 Form Finding";
    public const string GraphicStatics = "03 Graphic Statics";
    public const string Visualisation = "05 Visualisation";
    public const string Query = "90 Query";
}

public sealed record ComponentValueListSpec(
    int InputIndex,
    string Name,
    IReadOnlyList<(string Label, string Value)> Items,
    string DefaultValue);

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
                ListMode = GH_ValueListMode.DropDown
            };
            valueList.ListItems.Clear();
            foreach ((string label, string value) in spec.Items)
            {
                valueList.ListItems.Add(
                    new GH_ValueListItem(label, QuoteExpression(value)));
            }

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
        return base.Read(reader);
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
        return base.Read(reader);
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
