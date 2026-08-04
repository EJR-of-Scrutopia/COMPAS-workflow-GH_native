"""Pull numbers out of a solved step, in a shape the main bench can read.

Everything here reads from the step's field results, which only exist
because the step requested field outputs before solving and because the
solve went through ananke_fea.compat.analyse rather than the
double-extracting convenience wrapper that Problem also offers. Without the
first there is no results table at all; without the second every row
appears twice and every sum is doubled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def displacement_summary(step) -> Dict[str, Any]:
    """Peak displacement and where it is."""

    results = list(step.displacement_field.results)
    if not results:
        raise ValueError(
            "no displacement results. Was DisplacementFieldResults requested "
            "with step.add_output before solving?"
        )
    peak = max(results, key=lambda result: result.magnitude)
    return {
        "count": len(results),
        "peak_magnitude": float(peak.magnitude),
        "peak_vector": [float(component) for component in peak.vector],
        "peak_node_xyz": [float(value) for value in peak.node.xyz],
    }


def reaction_summary(step) -> Dict[str, Any]:
    """Summed reactions, which should cancel the factored applied load."""

    results = list(step.reaction_field.results)
    if not results:
        raise ValueError(
            "no reaction results. Was ReactionFieldResults requested with "
            "step.add_output before solving?"
        )
    total = [0.0, 0.0, 0.0]
    for result in results:
        for axis in range(3):
            total[axis] += float(result.vector[axis])
    return {
        "count": len(results),
        "total": total,
        "magnitude": sum(component**2 for component in total) ** 0.5,
    }


def write(path, payload: Mapping[str, Any]) -> Path:
    """Write a result JSON, creating the directory if needed."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def stress_summary(step, preset) -> Dict[str, Any]:
    """Principal stresses against the preset's design strengths.

    Sign convention here is tension positive, matching the export. A shell
    that is genuinely funicular under its design load should report no
    tension at all; anything else is the signal the cable sizing responds to.

    The API this was originally written against does not exist: at this
    compas_fea2_opensees pin, the step's stress field attribute is fed by
    the core's global-tensor DB path (table "s", 6 columns), which
    compat.apply_patches() deliberately does not feed correctly (see its
    docstring). There is no exploratory attribute-chasing route to a real
    shell stress here; the backend exposes nothing usable for it. This
    reads the raw eleResponse dump apply_patches() causes OpenSees to write
    (s.out) and does the plate-theory surface-stress conversion itself,
    bypassing that attribute entirely.
    """

    part = next(iter(step.problem.model.parts))
    section = next(iter(part.elements)).section
    thickness = section.t

    resultants = _element_resultants(step)

    peak_tension = 0.0
    peak_compression = 0.0
    for values in resultants.values():
        tension, compression = surface_principal_stresses(values, thickness)
        peak_tension = max(peak_tension, tension)
        peak_compression = min(peak_compression, compression)

    return {
        "count": len(resultants),
        "peak_tension": peak_tension,
        "peak_compression": peak_compression,
        "tension_present": peak_tension > 0.0,
        "utilisation": abs(peak_compression) / preset.compressive_strength,
        "tension_utilisation": (
            peak_tension / preset.tensile_strength
            if preset.tensile_strength
            else None
        ),
    }


def _element_resultants(step) -> Dict[int, list]:
    """Per-element averaged shell resultants from the raw s.out dump.

    Thin wrapper over _parse_resultants that derives the file path from a
    solved step, kept separate so the parser itself can be tested directly
    against a synthetic file rather than a real solve.
    """

    path = Path(step.problem.path) / "s.out"
    if not path.is_file():
        raise ValueError(
            "no s.out beside the analysis: was StressFieldResults requested "
            "and apply_patches() called before the solve?"
        )
    return _parse_resultants(path)


def _parse_resultants(path) -> Dict[int, list]:
    """Parse a raw s.out dump into per-element averaged shell resultants.

    Each line is "eleTag v1 v2 ..." where the values are groups of 8 per
    integration point, element local frame, order Nxx Nyy Nxy Mxx Myy Mxy
    Vxz Vyz, per unit length. Averaging over integration points matches the
    dormant s2d branch upstream (compas_fea2_opensees/problem/problem.py).
    The group count is inferred rather than assumed to be 4 so triangular
    shells do not corrupt the reshape.

    A line with no columns at all (the trailing blank line every text file
    ends with) is skipped as not-a-row. A line that does have an element tag
    but a short or malformed value count is not skipped: it fails loudly,
    naming the element, rather than silently vanishing from the resultants.
    An element quietly missing from the tension check is exactly the kind
    of incomplete-but-successful-looking result this package exists to
    catch.
    """

    resultants: Dict[int, list] = {}
    for line in Path(path).read_text().split("\n"):
        columns = line.split()
        if not columns:
            continue
        tag = int(columns[0])
        values = [float(v) for v in columns[1:]]
        if not values or len(values) % 8:
            raise ValueError(
                "element {} returned {} stress values, not a positive "
                "multiple of 8; the response layout assumption does not "
                "hold for this element".format(tag, len(values))
            )
        groups = [values[i : i + 8] for i in range(0, len(values), 8)]
        resultants[tag] = [sum(col) / len(groups) for col in zip(*groups)]
    if not resultants:
        raise ValueError("s.out contains no element rows; the solve wrote nothing")
    return resultants


def surface_principal_stresses(resultants, thickness):
    """Principal stresses at both shell surfaces from averaged resultants.

    Plate theory: at z = +/- t/2 the in-plane stresses are
    sigma = N/t +/- 6M/t^2 componentwise, and the principal values follow
    from Mohr's circle. Peak tension over both surfaces is what the
    tension-onset check needs; frame invariance of principal values makes
    the element local frame sufficient, so no rotation to global is done.
    """

    nxx, nyy, nxy, mxx, myy, mxy = resultants[:6]
    outcomes = []
    for sign in (1.0, -1.0):
        sxx = nxx / thickness + sign * 6.0 * mxx / thickness**2
        syy = nyy / thickness + sign * 6.0 * myy / thickness**2
        sxy = nxy / thickness + sign * 6.0 * mxy / thickness**2
        centre = (sxx + syy) / 2.0
        radius = (((sxx - syy) / 2.0) ** 2 + sxy**2) ** 0.5
        outcomes.extend((centre + radius, centre - radius))
    return max(outcomes), min(outcomes)


def deflection_summary(displacement: Mapping[str, Any], span: float) -> Dict[str, Any]:
    """Peak deflection expressed as a span ratio."""

    peak = float(displacement["peak_magnitude"])
    return {
        "peak_magnitude": peak,
        "span": span,
        "span_over_deflection": (span / peak) if peak > 0.0 else None,
    }
