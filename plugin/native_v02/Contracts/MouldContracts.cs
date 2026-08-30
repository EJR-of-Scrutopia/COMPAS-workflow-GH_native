#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Everything the mould adds to a solved Result, in ONE block, so a single
/// wire carries the whole mould design to whoever wants it.
///
/// Columns writes <see cref="Columns"/>. Animate writes <see cref="Frame"/>
/// and leaves Columns untouched, so the built geometry and the live geometry
/// coexist and a deviation field has both. Plain records in the
/// TnaPrepareConfigDto style: no Kind, no schema version, validated by the
/// parent, never on a wire of their own.
/// </summary>
public sealed record MouldDto
{
    /// <summary>The level the anchors sit at, which the columns stand on.</summary>
    public double Ground { get; init; }

    public MouldColumnsDto? Columns { get; init; }

    public MouldFrameDto? Frame { get; init; }

    internal void Validate(int vertexCount, string label, List<string> errors)
    {
        if (!ContractRules.IsFinite(Ground))
            errors.Add($"{label}.ground must be finite.");
        Columns?.Validate(vertexCount, $"{label}.columns", errors);
        Frame?.Validate(vertexCount, Columns?.Nodes.Count, $"{label}.frame", errors);
    }
}

/// <summary>
/// The built column trees. Members are (lower, upper) index pairs into
/// <see cref="Nodes"/>, lower end first always; <see cref="Trees"/> holds
/// member indices per tree, which is the branch structure Deconstruct hands
/// back; <see cref="HeadNode"/> names the net vertex each head stands on so
/// downstream alignment is by index and never by matching coordinates.
/// </summary>
public sealed record MouldColumnsDto
{
    public IReadOnlyList<Point3Dto> Nodes { get; init; } = Array.Empty<Point3Dto>();

    public IReadOnlyList<EdgeDto> Members { get; init; } = Array.Empty<EdgeDto>();

    /// <summary>N per member, compression positive, aligned with Members.</summary>
    public IReadOnlyList<double> MemberForce { get; init; } = Array.Empty<double>();

    public IReadOnlyList<IReadOnlyList<int>> Trees { get; init; } =
        Array.Empty<IReadOnlyList<int>>();

    public IReadOnlyList<int> Heads { get; init; } = Array.Empty<int>();

    public IReadOnlyList<int> Forks { get; init; } = Array.Empty<int>();

    public IReadOnlyList<int> Feet { get; init; } = Array.Empty<int>();

    /// <summary>Aligned with Heads: the equilibrium vertex under each head.</summary>
    public IReadOnlyList<int> HeadNode { get; init; } = Array.Empty<int>();

    public int Branching { get; init; } = 1;

    /// <summary>The Ground level asked for; -1 is Auto.</summary>
    public int GroundAsked { get; init; }

    /// <summary>
    /// Equal to GroundAsked except under Auto (-1), where it is the level
    /// chosen. No level is refused any more, so there is no fallback to
    /// record.
    /// </summary>
    public int GroundPlaced { get; init; }

    public double ForkFraction { get; init; }

    public int ForksRaised { get; init; }

    internal void Validate(int vertexCount, string label, List<string> errors)
    {
        int nodeCount = Nodes.Count;
        for (int i = 0; i < nodeCount; i++)
            ContractRules.ValidatePoint(Nodes[i], $"{label}.nodes[{i}]", errors);

        for (int i = 0; i < Members.Count; i++)
        {
            EdgeDto member = Members[i];
            if (member.U < 0 || member.U >= nodeCount ||
                member.V < 0 || member.V >= nodeCount)
            {
                errors.Add($"{label}.members[{i}] references a node outside nodes.");
            }
            else if (member.U == member.V)
            {
                errors.Add($"{label}.members[{i}] joins a node to itself.");
            }
        }

        if (MemberForce.Count != Members.Count)
            errors.Add($"{label}.memberForce must hold one value per member.");
        for (int i = 0; i < MemberForce.Count; i++)
        {
            if (!ContractRules.IsFinite(MemberForce[i]))
                errors.Add($"{label}.memberForce[{i}] must be finite.");
        }

        var used = new HashSet<int>();
        for (int t = 0; t < Trees.Count; t++)
        {
            foreach (int m in Trees[t])
            {
                if (m < 0 || m >= Members.Count)
                    errors.Add($"{label}.trees[{t}] references a member outside members.");
                else if (!used.Add(m))
                    errors.Add($"{label}.trees[{t}] uses member {m} twice.");
            }
        }

        CheckNodeIndices(Heads, nodeCount, $"{label}.heads", errors);
        CheckNodeIndices(Forks, nodeCount, $"{label}.forks", errors);
        CheckNodeIndices(Feet, nodeCount, $"{label}.feet", errors);

        if (HeadNode.Count != Heads.Count)
            errors.Add($"{label}.headNode must hold one net vertex per head.");
        for (int i = 0; i < HeadNode.Count; i++)
        {
            if (HeadNode[i] < 0 || HeadNode[i] >= vertexCount)
                errors.Add($"{label}.headNode[{i}] is outside the net.");
        }

        if (Branching < 1)
            errors.Add($"{label}.branching must be at least 1.");
        if (GroundAsked < -1)
            errors.Add($"{label}.groundAsked cannot be below -1 (Auto).");
        if (GroundPlaced < 0)
            errors.Add($"{label}.groundPlaced cannot be negative.");
        if (!ContractRules.IsFinite(ForkFraction) || ForkFraction < 0.0 || ForkFraction > 1.0)
            errors.Add($"{label}.forkFraction must be between 0 and 1.");
        if (ForksRaised < 0)
            errors.Add($"{label}.forksRaised cannot be negative.");
    }

    private static void CheckNodeIndices(
        IReadOnlyList<int> indices, int nodeCount, string label, List<string> errors)
    {
        for (int i = 0; i < indices.Count; i++)
        {
            if (indices[i] < 0 || indices[i] >= nodeCount)
                errors.Add($"{label}[{i}] is outside nodes.");
        }
    }
}

/// <summary>
/// ONE frame of the animation, never a history. Vertices share the index
/// space of Equilibrium.Vertices; ColumnNodes share that of
/// MouldColumnsDto.Nodes and is absent when there are no columns.
/// </summary>
public sealed record MouldFrameDto
{
    public double Time { get; init; }

    public string Phase { get; init; } = "final";

    public double Lift { get; init; }

    public double Sag { get; init; }

    public IReadOnlyList<Point3Dto> Vertices { get; init; } = Array.Empty<Point3Dto>();

    public IReadOnlyList<Point3Dto>? ColumnNodes { get; init; }

    internal void Validate(
        int vertexCount, int? columnNodeCount, string label, List<string> errors)
    {
        if (!ContractRules.IsFinite(Time) || Time < 0.0 || Time > 100.0)
            errors.Add($"{label}.time must be between 0 and 100.");
        if (!ContractRules.IsFinite(Lift) || Lift < 0.0 || Lift > 1.0)
            errors.Add($"{label}.lift must be between 0 and 1.");
        if (!ContractRules.IsFinite(Sag) || Sag < 0.0 || Sag > 1.0)
            errors.Add($"{label}.sag must be between 0 and 1.");
        if (Vertices.Count != vertexCount)
        {
            errors.Add(
                $"{label}.vertices must hold one point per net vertex " +
                $"({vertexCount}); it holds {Vertices.Count}.");
        }
        for (int i = 0; i < Vertices.Count; i++)
            ContractRules.ValidatePoint(Vertices[i], $"{label}.vertices[{i}]", errors);

        if (ColumnNodes is not null)
        {
            if (columnNodeCount is null)
                errors.Add($"{label}.columnNodes is present but the block carries no columns.");
            else if (ColumnNodes.Count != columnNodeCount.Value)
                errors.Add($"{label}.columnNodes must hold one point per column node.");
            for (int i = 0; i < ColumnNodes.Count; i++)
                ContractRules.ValidatePoint(ColumnNodes[i], $"{label}.columnNodes[{i}]", errors);
        }
    }
}
