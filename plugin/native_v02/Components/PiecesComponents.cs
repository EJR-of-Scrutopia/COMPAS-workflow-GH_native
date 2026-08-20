#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// One piece as the bench.pieces/1 document carries it: plain numbers only
/// (no Rhino types), so it can be built entirely off the solve thread. The
/// vertex/face topology is reused verbatim, exactly as the studio's own
/// piece_solids extrusion wrote it -- no weld pass, no rebuild.
/// </summary>
public sealed record PieceRecord(
    string Key,
    int Course,
    bool IsSupport,
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces);

/// <summary>
/// The parsed bench.pieces/1 document: the schema/units contract already
/// checked, pieces in the document's own order (the studio's drop order),
/// untouched.
/// </summary>
public sealed record PiecesDocument(
    string Schema,
    string Units,
    int Courses,
    int PieceCount,
    double Thickness,
    IReadOnlyList<string> DegenerateDropped,
    IReadOnlyList<PieceRecord> Pieces);

public sealed record ImportPiecesTaskResult(
    PiecesDocument? Document,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// Reads a bench.pieces/1 export and lands the studio's final cut-block
/// solids on the canvas: one mesh per piece, plus its course/key/support
/// flag, all in the document's own order (course ascending from the rim,
/// anticlockwise within a course -- the studio's drop order).
///
/// File read + JSON parse happen off the solve thread (the background
/// task only ever produces plain arrays, never live Rhino geometry);
/// Rhino.Geometry.Mesh construction happens in the post phase on the
/// solve thread, following the TnaResultGeometry.ThrustMesh pattern
/// (Vertices.Add, Faces.AddFace for 3/4-corner faces with a fan fallback,
/// ComputeNormals, Compact) -- and, unlike ThrustMesh, no weld pass: the
/// document's vertices arrive exact, caps deliberately disjoint.
/// </summary>
public sealed class ImportPiecesComponent :
    NativeTaskComponentBase<ImportPiecesTaskResult>
{
    private const string ExpectedSchema = "bench.pieces/1";
    private const string ExpectedUnits = "m";

    public ImportPiecesComponent()
        : base(
            "Import Pieces",
            "Pieces",
            "Read a bench.pieces/1 export and land the studio's final " +
            "cut-block solids on the canvas as aligned mesh/course/" +
            "key/support lists, in the export's own drop order.",
            ComponentCategories.Delivery,
            "import_pieces")
    {
    }

    public override Guid ComponentGuid =>
        new("24758d7e-3db2-4a03-b758-7bd2bd0e9d87");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Path",
            "P",
            "A bench.pieces/1 JSON file written by the studio's " +
            "pieces-export route.",
            GH_ParamAccess.item);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddMeshParameter(
            "Meshes",
            "M",
            "One closed solid mesh per piece, in the document's own " +
            "order. A piece that failed to build is a null placeholder " +
            "in this list, so Courses/Keys/Supports stay index-aligned " +
            "with Meshes; cross-reference Keys at that index to find " +
            "which piece dropped out.",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Courses",
            "C",
            "The course index of each piece (0-up from the rim), " +
            "aligned with Meshes.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Keys",
            "K",
            "The piece key (for example c0p3) of each piece, aligned " +
            "with Meshes.",
            GH_ParamAccess.list);
        parameters.AddBooleanParameter(
            "Supports",
            "S",
            "True where the piece is a support/base piece, aligned " +
            "with Meshes.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Diagnostics",
            "D",
            "Schema, units, piece count, courses, thickness, the " +
            "degenerate_dropped keys the export already reported, the " +
            "metres-to-model-units factor applied, and a warning line " +
            "naming any piece that failed to build.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        // Sync-sibling shape (Export/FdSolve/Deconstruct): without a
        // local catch here, an unexpected exception would climb out of
        // SolveInstance and land on Grasshopper's own framework-level
        // handler, which reports a far uglier message than
        // AddRuntimeMessage does.
        try
        {
            if (InPreSolve)
            {
                if (!TryReadInputs(data, out string path, report: false))
                    return;
                TaskList.Add(Task.Run(
                    () => ComputeAsync(path, CancelToken),
                    CancelToken));
                return;
            }

            if (!TryReadInputs(data, out string postPath))
                return;

            ImportPiecesTaskResult taskResult;
            bool haveTaskResult = GetSolveResults(data, out taskResult!);
            if (!haveTaskResult ||
                taskResult.Error is OperationCanceledException)
            {
                // A cancelled background task is a scheduling race, not a
                // verdict on the current Path; recompute synchronously so
                // a late cancellation cannot strand the canvas.
                taskResult = ComputeAsync(postPath, CancellationToken.None)
                    .GetAwaiter()
                    .GetResult();
            }

            if (taskResult.Error is not null)
            {
                Message = taskResult.Error is OperationCanceledException
                    ? "Cancelled"
                    : "Failed";
                AddRuntimeMessage(
                    taskResult.Error is OperationCanceledException
                        ? GH_RuntimeMessageLevel.Warning
                        : GH_RuntimeMessageLevel.Error,
                    "Import Pieces: " +
                    taskResult.Error.GetBaseException().Message);
                return;
            }
            if (taskResult.Document is null)
            {
                Message = "Failed";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Import Pieces produced no document.");
                return;
            }

            BuildOutputs(data, taskResult.Document);
        }
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Import Pieces failed", error);
        }
    }

    /// <summary>
    /// Read this component's own Path. The pre phase reads quietly; the
    /// post phase repeats the read and owns the reporting, so an invalid
    /// input surfaces once (the Export/TryReadInputs shape).
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out string path,
        bool report = true)
    {
        path = string.Empty;
        string pathInput = string.Empty;
        if (!data.GetData(0, ref pathInput) ||
            string.IsNullOrWhiteSpace(pathInput))
        {
            if (report)
            {
                Message = "Invalid";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Path is required.");
            }
            return false;
        }

        path = pathInput;
        return true;
    }

    /// <summary>
    /// The background task: file read and JSON parse only, off the solve
    /// thread. Every value it can produce (<see cref="PiecesDocument"/>,
    /// its <see cref="PieceRecord"/> pieces) is plain numbers/strings, so
    /// nothing here touches Rhino.Geometry.
    /// </summary>
    private static async Task<ImportPiecesTaskResult> ComputeAsync(
        string path,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            string json = await File
                .ReadAllTextAsync(path, cancellationToken)
                .ConfigureAwait(false);
            PiecesDocument document = ParseDocument(json);
            stopwatch.Stop();
            return new ImportPiecesTaskResult(document, null, stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new ImportPiecesTaskResult(null, error, stopwatch.Elapsed);
        }
    }

    /// <summary>
    /// Parses a bench.pieces/1 document from JSON text: pure, off-thread
    /// safe, no file I/O of its own. Schema and units are checked first
    /// and refused with a message naming exactly what was found -- the
    /// binding spec's "component Error naming what was found." Pieces
    /// are returned in the document's own order, untouched.
    /// </summary>
    private static PiecesDocument ParseDocument(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        JsonElement root = document.RootElement;

        string schema = RequireString(root, "schema");
        if (!string.Equals(schema, ExpectedSchema, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"expected schema '{ExpectedSchema}', found '{schema}'.");
        }
        string units = RequireString(root, "units");
        if (!string.Equals(units, ExpectedUnits, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"expected units '{ExpectedUnits}', found '{units}'.");
        }

        int courses = OptionalInt(root, "courses");
        int pieceCount = OptionalInt(root, "piece_count");
        double thickness = OptionalDouble(root, "thickness");
        List<string> degenerateDropped =
            ReadStringList(root, "degenerate_dropped");

        if (!root.TryGetProperty("pieces", out JsonElement piecesElement) ||
            piecesElement.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException("document has no 'pieces' array.");
        }

        var pieces = new List<PieceRecord>(piecesElement.GetArrayLength());
        foreach (JsonElement pieceElement in piecesElement.EnumerateArray())
            pieces.Add(ParsePiece(pieceElement));

        return new PiecesDocument(
            schema,
            units,
            courses,
            pieceCount,
            thickness,
            degenerateDropped,
            pieces);
    }

    private static PieceRecord ParsePiece(JsonElement element)
    {
        string key = RequireString(element, "key");
        int course = RequireInt(element, "course");
        bool isSupport =
            element.TryGetProperty("is_support", out JsonElement supportElement)
            && supportElement.ValueKind == JsonValueKind.True;

        if (!element.TryGetProperty("vertices", out JsonElement verticesElement) ||
            verticesElement.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException(
                $"piece '{key}' has no 'vertices' array.");
        }
        var vertices = new List<double[]>(verticesElement.GetArrayLength());
        foreach (JsonElement vertexElement in verticesElement.EnumerateArray())
        {
            if (vertexElement.ValueKind != JsonValueKind.Array ||
                vertexElement.GetArrayLength() != 3)
            {
                throw new InvalidDataException(
                    $"piece '{key}' has a vertex that is not an " +
                    "[x, y, z] triple.");
            }
            var xyz = new double[3];
            int index = 0;
            foreach (JsonElement component in vertexElement.EnumerateArray())
                xyz[index++] = component.GetDouble();
            vertices.Add(xyz);
        }

        if (!element.TryGetProperty("faces", out JsonElement facesElement) ||
            facesElement.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException(
                $"piece '{key}' has no 'faces' array.");
        }
        var faces = new List<int[]>(facesElement.GetArrayLength());
        foreach (JsonElement faceElement in facesElement.EnumerateArray())
        {
            if (faceElement.ValueKind != JsonValueKind.Array ||
                faceElement.GetArrayLength() < 3)
            {
                throw new InvalidDataException(
                    $"piece '{key}' has a face with fewer than 3 corners.");
            }
            var corners = new int[faceElement.GetArrayLength()];
            int index = 0;
            foreach (JsonElement corner in faceElement.EnumerateArray())
                corners[index++] = corner.GetInt32();
            faces.Add(corners);
        }

        return new PieceRecord(key, course, isSupport, vertices, faces);
    }

    private static string RequireString(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.String)
        {
            throw new InvalidDataException($"'{propertyName}' must be a string.");
        }
        return value.GetString() ?? string.Empty;
    }

    private static int RequireInt(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.Number ||
            !value.TryGetInt32(out int result))
        {
            throw new InvalidDataException(
                $"'{propertyName}' must be an integer.");
        }
        return result;
    }

    private static int OptionalInt(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out JsonElement value) &&
        value.ValueKind == JsonValueKind.Number &&
        value.TryGetInt32(out int result)
            ? result
            : 0;

    private static double OptionalDouble(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out JsonElement value) &&
        value.ValueKind == JsonValueKind.Number
            ? value.GetDouble()
            : 0.0;

    private static List<string> ReadStringList(
        JsonElement element,
        string propertyName)
    {
        var result = new List<string>();
        if (element.TryGetProperty(propertyName, out JsonElement value) &&
            value.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in value.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.String)
                    result.Add(item.GetString() ?? string.Empty);
            }
        }
        return result;
    }

    /// <summary>
    /// The post phase, on the solve thread: builds one Rhino mesh per
    /// piece (the TnaResultGeometry.ThrustMesh pattern, minus the weld
    /// pass the document's exact vertices do not need), scales every
    /// point by the active RhinoDoc's metres-to-model-units factor, and
    /// writes the four aligned lists plus Diagnostics.
    /// </summary>
    private void BuildOutputs(IGH_DataAccess data, PiecesDocument document)
    {
        double unitFactor = ResolveUnitFactor();

        var meshes = new List<Mesh?>(document.Pieces.Count);
        var courses = new List<int>(document.Pieces.Count);
        var keys = new List<string>(document.Pieces.Count);
        var supports = new List<bool>(document.Pieces.Count);
        var failedKeys = new List<string>();

        foreach (PieceRecord piece in document.Pieces)
        {
            Mesh? mesh;
            try
            {
                mesh = BuildPieceMesh(piece, unitFactor);
                if (mesh.Faces.Count == 0 || mesh.Vertices.Count == 0)
                    mesh = null;
            }
            catch (Exception)
            {
                // A malformed piece (an out-of-range face index, most
                // plausibly) must not take the whole import down with
                // it: the GH idiom here is a null Mesh entry at this
                // piece's index -- Grasshopper renders it as an empty/
                // "null" branch item rather than collapsing the list, so
                // Courses/Keys/Supports stay index-aligned with Meshes.
                mesh = null;
            }

            if (mesh is null)
                failedKeys.Add(piece.Key);

            meshes.Add(mesh);
            courses.Add(piece.Course);
            keys.Add(piece.Key);
            supports.Add(piece.IsSupport);
        }

        data.SetDataList(0, meshes);
        data.SetDataList(1, courses);
        data.SetDataList(2, keys);
        data.SetDataList(3, supports);
        data.SetData(4, BuildDiagnostics(document, unitFactor, failedKeys));

        if (failedKeys.Count > 0)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                $"Import Pieces: {failedKeys.Count} piece(s) failed to " +
                $"build ({string.Join(", ", failedKeys)}); Meshes carries " +
                "a null placeholder at each so Courses/Keys/Supports stay " +
                "aligned.");
        }

        Message = string.Format(
            CultureInfo.InvariantCulture,
            "{0} piece(s) - x{1:0.####}",
            document.Pieces.Count,
            unitFactor);
    }

    /// <summary>
    /// The TnaResultGeometry.ThrustMesh pattern (Vertices.Add, Faces.
    /// AddFace for 3/4-corner faces with a fan fallback beyond 4,
    /// ComputeNormals, Compact) with one deliberate omission: no weld
    /// pass. The binding spec is explicit that the document's vertices
    /// ship exactly as materialized -- caps disjoint by design at any
    /// thickness >= 0.05 m -- so welding here would silently undo the
    /// server's own geometry.
    /// </summary>
    private static Mesh BuildPieceMesh(PieceRecord piece, double unitFactor)
    {
        var mesh = new Mesh();
        foreach (double[] vertex in piece.Vertices)
        {
            mesh.Vertices.Add(
                vertex[0] * unitFactor,
                vertex[1] * unitFactor,
                vertex[2] * unitFactor);
        }
        foreach (int[] face in piece.Faces)
        {
            if (face.Length == 3)
            {
                mesh.Faces.AddFace(face[0], face[1], face[2]);
            }
            else if (face.Length == 4)
            {
                mesh.Faces.AddFace(face[0], face[1], face[2], face[3]);
            }
            else
            {
                for (int index = 1; index < face.Length - 1; index++)
                    mesh.Faces.AddFace(face[0], face[index], face[index + 1]);
            }
        }
        if (mesh.Faces.Count > 0)
            mesh.Normals.ComputeNormals();
        mesh.Compact();
        return mesh;
    }

    /// <summary>
    /// The document is intrados-metres; the active Rhino document's unit
    /// system is not assumed to be metres. RhinoDoc.ActiveDoc may be
    /// null in headless contexts (this harness's own reflection pattern
    /// never launches Rhino at all), so the guard defaults to 1.0 -- the
    /// factor actually applied is always disclosed in Diagnostics.
    /// </summary>
    private static double ResolveUnitFactor()
    {
        RhinoDoc? activeDoc = RhinoDoc.ActiveDoc;
        if (activeDoc is null)
            return 1.0;
        return RhinoMath.UnitScale(UnitSystem.Meters, activeDoc.ModelUnitSystem);
    }

    private static string BuildDiagnostics(
        PiecesDocument document,
        double unitFactor,
        IReadOnlyList<string> failedKeys)
    {
        var lines = new List<string>
        {
            $"schema: {document.Schema}",
            $"units: {document.Units}",
            $"pieces: {document.Pieces.Count}",
            $"courses: {document.Courses}",
            "thickness: " +
                document.Thickness.ToString("0.####", CultureInfo.InvariantCulture) +
                " m",
            "unit factor applied (m -> doc units): " +
                unitFactor.ToString(
                    "0.################",
                    CultureInfo.InvariantCulture),
            document.DegenerateDropped.Count > 0
                ? "degenerate_dropped: " +
                  string.Join(", ", document.DegenerateDropped)
                : "degenerate_dropped: none"
        };
        if (failedKeys.Count > 0)
        {
            lines.Add(
                $"warning: {failedKeys.Count} piece(s) failed to build " +
                $"({string.Join(", ", failedKeys)}); see Meshes for the " +
                "null placeholders.");
        }
        return string.Join(Environment.NewLine, lines);
    }
}
