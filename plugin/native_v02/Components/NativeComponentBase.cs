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

    private void CreateSuggestedValueLists(GH_Document document)
    {
        foreach (ComponentValueListSpec spec in SuggestedValueLists)
        {
            if (spec.InputIndex < 0 ||
                spec.InputIndex >= Params.Input.Count)
            {
                continue;
            }

            IGH_Param input = Params.Input[spec.InputIndex];
            if (input.SourceCount > 0 || input.HasProxySources)
                continue;

            var valueList = new GH_ValueList
            {
                Name = spec.Name,
                NickName = spec.Name,
                Description =
                    $"Supported values for {Params.Input[spec.InputIndex].Name}.",
                ListMode = GH_ValueListMode.DropDown
            };
            valueList.ListItems.Clear();
            foreach ((string label, string value) in spec.Items)
            {
                valueList.ListItems.Add(
                    new GH_ValueListItem(
                        label,
                        QuoteExpression(value)));
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
            valueList.SelectItem(selectedIndex);
            valueList.CreateAttributes();

            float x = Attributes?.Bounds.Left - 170.0f
                ?? input.Attributes?.Pivot.X - 170.0f
                ?? 0.0f;
            float y = input.Attributes?.Pivot.Y - 10.0f
                ?? Attributes?.Pivot.Y
                ?? 0.0f;
            if (valueList.Attributes is not null)
                valueList.Attributes.Pivot = new PointF(x, y);

            if (document.AddObject(valueList, false))
                input.AddSource(valueList);
        }
    }

    private static string QuoteExpression(string value) =>
        "\"" +
        value
            .Replace("\\", "\\\\", StringComparison.Ordinal)
            .Replace("\"", "\\\"", StringComparison.Ordinal) +
        "\"";

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

    private void CreateSuggestedValueLists(GH_Document document)
    {
        foreach (ComponentValueListSpec spec in SuggestedValueLists)
        {
            if (spec.InputIndex < 0 ||
                spec.InputIndex >= Params.Input.Count)
            {
                continue;
            }

            IGH_Param input = Params.Input[spec.InputIndex];
            if (input.SourceCount > 0 || input.HasProxySources)
                continue;

            var valueList = new GH_ValueList
            {
                Name = spec.Name,
                NickName = spec.Name,
                Description =
                    $"Supported values for {Params.Input[spec.InputIndex].Name}.",
                ListMode = GH_ValueListMode.DropDown
            };
            valueList.ListItems.Clear();
            foreach ((string label, string value) in spec.Items)
            {
                valueList.ListItems.Add(
                    new GH_ValueListItem(
                        label,
                        QuoteExpression(value)));
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
            valueList.SelectItem(selectedIndex);
            valueList.CreateAttributes();

            float x = Attributes?.Bounds.Left - 170.0f
                ?? input.Attributes?.Pivot.X - 170.0f
                ?? 0.0f;
            float y = input.Attributes?.Pivot.Y - 10.0f
                ?? Attributes?.Pivot.Y
                ?? 0.0f;
            if (valueList.Attributes is not null)
                valueList.Attributes.Pivot = new PointF(x, y);

            if (document.AddObject(valueList, false))
                input.AddSource(valueList);
        }
    }

    private static string QuoteExpression(string value) =>
        "\"" +
        value
            .Replace("\\", "\\\\", StringComparison.Ordinal)
            .Replace("\"", "\\\"", StringComparison.Ordinal) +
        "\"";

    protected void ReportException(string operation, Exception error)
    {
        string message = error.GetBaseException().Message;
        AddRuntimeMessage(
            GH_RuntimeMessageLevel.Error,
            $"{operation}: {message}");
    }
}
