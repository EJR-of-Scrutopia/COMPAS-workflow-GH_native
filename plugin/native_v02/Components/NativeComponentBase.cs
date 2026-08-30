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
/// Grasshopper subcategories, one per stage of the chain a Result travels.
///
/// The tabs used to be named after COMPAS's own extension families, which
/// answered "which package backs this" and nothing else; eight of the
/// nineteen components ended up under one of them. They are named after the
/// WORK now, in the order the work happens: model a pattern, solve it, build
/// the mould that makes it, read what came out, deliver it. A canvas is
/// built left to right and the tabs now read that way too.
///
/// The three reserved families keep their places at the end, renumbered out
/// of the way of the five that are in use, and they still name the packages
/// that would back them.
///
/// Subcategory is display grouping only. Component identity is the GUID, so
/// regrouping never invalidates a saved definition and no wire moves.
/// </summary>
internal static class ComponentCategories
{
    public const string Category = "Ananke COMPAS";

    // Pattern, Supports, Loads. No backend beyond compas itself.
    public const string Model = "01 Model";

    // TNA Relax, TNA Solve, TNA Solve Algebraic, FD Solve.
    // compas_fd, compas_tna. Capability: fd.solve, tna.solve. Extra: equilibrium.
    public const string Solve = "02 Solve";

    // Columns and Animate: the reconfigurable mould, which is what turns a
    // solved net into a machine. No backend.
    public const string Mould = "03 Mould";

    // Everything that reads a Result: Deconstruct, Monitor, Skin, Diagnose,
    // Frame, Style and Display. Geometry, numbers, words and the viewport.
    // No backend.
    public const string Read = "04 Read";

    // Export, Import Pieces, Armadillo Dual.
    // compas_model, compas_ifc. Capability: model, ifc. Extras: model, ifc.
    public const string Deliver = "05 Deliver";

    // compas_dem, compas_assembly, compas_cra. Capability: masonry. Extra:
    // masonry. Reserved.
    public const string Masonry = "06 Masonry";

    // compas_fea2 plus a solver backend. Capability: fea. Extra: fea.
    // Reserved.
    public const string Engineering = "07 Engineering";

    // compas_fab, compas_robots. Capability: fab. Extra: fab. Reserved.
    public const string Fabrication = "08 Fabrication";

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

    /// <summary>
    /// The warning a component owes a canvas whose saved ports are not the
    /// ports it registers today, or null when the two agree.
    ///
    /// Grasshopper matches archived parameter chunks to live parameters BY
    /// INDEX, and a wire is stored on the RECEIVING port as the source's
    /// instance guid, so the archived guid of old slot i is handed to
    /// whatever port now stands at slot i. A reshaped component therefore
    /// does not come back with broken wires: they reattach, silently
    /// wherever the two ports share a type or cast across, and
    /// <see cref="Restore"/> then relabels the port with its registered
    /// name, so the canvas looks self-consistent while it carries a
    /// different quantity. An archived slot beyond the new range is the
    /// only one that visibly breaks. Nothing else in a reopened file says
    /// the surface moved, so this does.
    ///
    /// Counting is not enough. Monitor's Result moved from the last output
    /// to the first with twenty-one outputs before and after, which leaves
    /// every tree wire one slot low on a tree of the same type: nothing
    /// breaks, nothing is coloured, and every number is the wrong number.
    /// So the NAMES are compared index by index as well, and the first
    /// difference is named in the warning.
    ///
    /// A null archived name is an archive this cannot read a name out of,
    /// not a rename. It is skipped, so an archive shape that stops carrying
    /// names degrades to the count comparison rather than warning about
    /// every file ever saved.
    ///
    /// Both sides agreeing is the ordinary case and stays silent, so a file
    /// saved against the current surface is charged nothing.
    /// </summary>
    internal static string? Mismatch(
        IReadOnlyList<string?> archivedInputs,
        IReadOnlyList<string?> archivedOutputs,
        IReadOnlyList<string> registeredInputs,
        IReadOnlyList<string> registeredOutputs)
    {
        bool countsAgree =
            archivedInputs.Count == registeredInputs.Count &&
            archivedOutputs.Count == registeredOutputs.Count;
        string? renamed =
            FirstRename("input", archivedInputs, registeredInputs)
            ?? FirstRename("output", archivedOutputs, registeredOutputs);
        if (countsAgree && renamed is null)
            return null;
        // Counts that AGREE are not evidence, and must not open the
        // sentence. Monitor's warning read "6 inputs and 21 outputs
        // archived, 6 and 21 registered; output 0 was 'Member Force' and is
        // now 'Result'", whose first clause reads as a denial of the second,
        // on the one component the name comparison exists for. Where only
        // the names moved, the rename leads and the equal counts become
        // what they actually are: the reason every wire came back attached
        // to something.
        if (countsAgree)
        {
            return
                "this component's ports changed since the file was saved: " +
                renamed +
                "; the counts are unchanged, so every wire reattached by " +
                "position: check each one";
        }
        return
            "this component's ports changed since the file was saved: " +
            $"{archivedInputs.Count} inputs and {archivedOutputs.Count} " +
            $"outputs archived, {registeredInputs.Count} and " +
            $"{registeredOutputs.Count} registered" +
            (renamed is null ? string.Empty : "; " + renamed) +
            "; wires may now sit on the wrong port, check every one";
    }

    /// <summary>
    /// The first slot whose archived name is not the name registered there
    /// now, said the way an author reads a port: which side, which slot,
    /// what it was, what it is. Null when every shared slot agrees or when
    /// no archived name could be read.
    /// </summary>
    private static string? FirstRename(
        string side,
        IReadOnlyList<string?> archived,
        IReadOnlyList<string> registered)
    {
        int index = FirstRenameIndex(archived, registered);
        return index < 0
            ? null
            : $"{side} {index} was '{archived[index]}' and is now " +
              $"'{registered[index]}'";
    }

    /// <summary>
    /// The index of the first shared slot whose archived name is not the
    /// name registered there now, or -1 when every shared slot agrees or no
    /// archived name could be read.
    /// </summary>
    private static int FirstRenameIndex(
        IReadOnlyList<string?> archived,
        IReadOnlyList<string> registered)
    {
        int shared = Math.Min(archived.Count, registered.Count);
        for (int index = 0; index < shared; index++)
        {
            string? was = archived[index];
            if (was is null)
                continue;
            if (!string.Equals(was, registered[index], StringComparison.Ordinal))
                return index;
        }
        return -1;
    }

    /// <summary>
    /// Whether ONE side's archived ports differ from the ports registered
    /// on that side now, by count or by any name.
    ///
    /// <see cref="Mismatch"/> asks the question of both sides at once,
    /// because a warning is owed for either. A component that ACTS on the
    /// finding rather than only saying it may need one side alone: an
    /// output-side change cannot land an archived wire on an input, so it
    /// cannot flip an input the component then obeys.
    /// </summary>
    internal static bool SideMoved(
        IReadOnlyList<string?> archived,
        IReadOnlyList<string> registered) =>
        archived.Count != registered.Count ||
        FirstRenameIndex(archived, registered) >= 0;

    /// <summary>
    /// The port NAMES one component's archive carries, in slot order, or
    /// nulls where it carries none.
    ///
    /// Grasshopper writes the counts as the "InputCount" and "OutputCount"
    /// items of a "ParameterData" chunk sitting directly under the
    /// container chunk a component's Read is handed, and each parameter as
    /// an indexed "InputParam" or "OutputParam" sub-chunk of it carrying
    /// its own "Name" item. That shape was read off a real definition
    /// rather than assumed: converting
    /// plugin/definitions/ananke_equilibrium_v01.gh through
    /// GH_Archive.Serialize_Xml gives Definition, DefinitionObjects,
    /// Object, Container, ParameterData, holding InputCount, the InputId
    /// guids, OutputCount, the OutputId guids, and the InputParam and
    /// OutputParam chunks, whose items include Name.
    ///
    /// An archive without that chunk, or without those counts, is one this
    /// cannot speak about: nulls come back and the caller says nothing
    /// rather than inventing a mismatch. A parameter chunk that is there
    /// but carries no readable Name gives a null in its own slot, which
    /// <see cref="Mismatch"/> skips.
    /// </summary>
    internal static (string?[]? Inputs, string?[]? Outputs) ArchivedNames(
        GH_IReader? reader)
    {
        if (reader is null)
            return (null, null);
        try
        {
            if (!reader.ChunkExists("ParameterData"))
                return (null, null);
            GH_IReader? chunk = reader.FindChunk("ParameterData");
            if (chunk is null)
                return (null, null);
            int inputs = 0;
            int outputs = 0;
            if (!chunk.TryGetInt32("InputCount", ref inputs) ||
                !chunk.TryGetInt32("OutputCount", ref outputs))
            {
                return (null, null);
            }
            return (
                ArchivedSide(chunk, "InputParam", inputs),
                ArchivedSide(chunk, "OutputParam", outputs));
        }
        catch (Exception)
        {
            // A file that cannot be interrogated must still open. This is
            // an advisory reading, and no advisory is worth failing a
            // document read for.
            return (null, null);
        }
    }

    private static string?[] ArchivedSide(
        GH_IReader chunk,
        string chunkName,
        int count)
    {
        var names = new string?[Math.Max(count, 0)];
        for (int index = 0; index < names.Length; index++)
        {
            if (!chunk.ChunkExists(chunkName, index))
                continue;
            GH_IReader? parameter = chunk.FindChunk(chunkName, index);
            if (parameter is null)
                continue;
            string value = string.Empty;
            if (parameter.TryGetString("Name", ref value))
                names[index] = value;
        }
        return names;
    }
}

public abstract class NativeComponentBase : GH_Component
{
    private readonly string _iconName;
    private bool _readFromArchive;
    private bool _suggestedListsAttempted;
    private string? _portsMoved;
    private bool _inputPortsMoved;

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
        // The snapshots were taken before the read, so their lengths are
        // the REGISTERED counts whatever the archive did to Params.
        (string?[]? archivedInputs, string?[]? archivedOutputs) =
            ParameterIdentity.ArchivedNames(reader);
        if (archivedInputs is not null && archivedOutputs is not null)
        {
            string[] registeredInputs =
                Array.ConvertAll(inputs, snapshot => snapshot.Name);
            _portsMoved = ParameterIdentity.Mismatch(
                archivedInputs,
                archivedOutputs,
                registeredInputs,
                Array.ConvertAll(outputs, snapshot => snapshot.Name));
            _inputPortsMoved = ParameterIdentity.SideMoved(
                archivedInputs, registeredInputs);
            if (_portsMoved is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning, _portsMoved);
            }
        }
        return result;
    }

    /// <summary>
    /// Whether the archive this component was read from carried a
    /// different number of ports than it registers today: the finding the
    /// load-time Warning announces, offered to the component so it can act
    /// on it and not only say it. A component whose solve has an effect
    /// outside the canvas needs that, because the wires may now sit on the
    /// wrong ports and a Warning cannot recall a side effect that has
    /// already gone out.
    /// </summary>
    protected bool PortsMovedOnLoad => _portsMoved is not null;

    /// <summary>
    /// Whether the INPUT side alone moved: the archive carried a different
    /// number of inputs, or a different name at some input index.
    ///
    /// This is the half that can change what a component DOES. Grasshopper
    /// reattaches an archived wire to the live port at the same index, so an
    /// input wire that used to feed one thing now feeds whatever stands
    /// there and the component obeys it. An output-side change cannot do
    /// that: it can only leave a downstream wire reading the wrong thing,
    /// which the Warning already says. A component holding back a side
    /// effect wants this rather than <see cref="PortsMovedOnLoad"/>, or it
    /// holds on every file saved before an output was renamed.
    /// </summary>
    protected bool InputPortsMovedOnLoad => _inputPortsMoved;

    /// <summary>
    /// Says again, on every solution, what the read found: a message added
    /// during Read does not survive the first solve, because expiring a
    /// component clears its runtime messages before SolveInstance runs, and
    /// a warning nobody ever sees is not a warning. Guarded on the message
    /// already standing so it cannot pile up if that ever stops being true.
    /// </summary>
    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        if (_portsMoved is null)
            return;
        if (RuntimeMessages(GH_RuntimeMessageLevel.Warning)
            .Contains(_portsMoved))
        {
            return;
        }
        AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, _portsMoved);
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
    private string? _portsMoved;
    private bool _inputPortsMoved;

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
        // The snapshots were taken before the read, so their lengths are
        // the REGISTERED counts whatever the archive did to Params.
        (string?[]? archivedInputs, string?[]? archivedOutputs) =
            ParameterIdentity.ArchivedNames(reader);
        if (archivedInputs is not null && archivedOutputs is not null)
        {
            string[] registeredInputs =
                Array.ConvertAll(inputs, snapshot => snapshot.Name);
            _portsMoved = ParameterIdentity.Mismatch(
                archivedInputs,
                archivedOutputs,
                registeredInputs,
                Array.ConvertAll(outputs, snapshot => snapshot.Name));
            _inputPortsMoved = ParameterIdentity.SideMoved(
                archivedInputs, registeredInputs);
            if (_portsMoved is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning, _portsMoved);
            }
        }
        return result;
    }

    /// <summary>
    /// Whether the archive this component was read from carried a
    /// different number of ports than it registers today: the finding the
    /// load-time Warning announces, offered to the component so it can act
    /// on it and not only say it. A component whose solve has an effect
    /// outside the canvas needs that, because the wires may now sit on the
    /// wrong ports and a Warning cannot recall a side effect that has
    /// already gone out.
    /// </summary>
    protected bool PortsMovedOnLoad => _portsMoved is not null;

    /// <summary>
    /// Whether the INPUT side alone moved: the archive carried a different
    /// number of inputs, or a different name at some input index.
    ///
    /// This is the half that can change what a component DOES. Grasshopper
    /// reattaches an archived wire to the live port at the same index, so an
    /// input wire that used to feed one thing now feeds whatever stands
    /// there and the component obeys it. An output-side change cannot do
    /// that: it can only leave a downstream wire reading the wrong thing,
    /// which the Warning already says. A component holding back a side
    /// effect wants this rather than <see cref="PortsMovedOnLoad"/>, or it
    /// holds on every file saved before an output was renamed.
    /// </summary>
    protected bool InputPortsMovedOnLoad => _inputPortsMoved;

    /// <summary>
    /// Says again, on every solution, what the read found: a message added
    /// during Read does not survive the first solve, because expiring a
    /// component clears its runtime messages before SolveInstance runs, and
    /// a warning nobody ever sees is not a warning. Guarded on the message
    /// already standing so it cannot pile up if that ever stops being true.
    /// </summary>
    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        if (_portsMoved is null)
            return;
        if (RuntimeMessages(GH_RuntimeMessageLevel.Warning)
            .Contains(_portsMoved))
        {
            return;
        }
        AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, _portsMoved);
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
