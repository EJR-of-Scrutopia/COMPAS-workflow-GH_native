"""Normalised equilibrium diagnostics for FD and TNA results."""

from __future__ import annotations

from math import sqrt
from typing import Any
from typing import Mapping

from ._base import AdapterError
from ._base import finite_float
from ._base import friendly
from ._base import get_any
from ._base import make_contract
from ._base import warning


def _norm(vector: Any) -> float:
    return sqrt(sum(float(value) ** 2 for value in vector))


def _diagnostic(
    code: str,
    value: float,
    tolerance: float,
    message: str,
    unit: str = "",
) -> Any:
    severity = "ok" if value <= tolerance else "warning"
    return make_contract(
        "Diagnostic",
        code=code,
        severity=severity,
        message=message,
        value=float(value),
        tolerance=float(tolerance),
        unit=unit,
        context={},
    )


@friendly("Validate")
def validate_result(
    solved_case: Any,
    tolerances: Mapping[str, Any] = None,
    *,
    residual_tolerance: float = 1e-6,
    closure_tolerance: float = 1e-6,
    angle_tolerance: float = 1.0,
    planarity_tolerance: float = 1e-6,
) -> Any:
    """Return a compact tuple of normalised ``Diagnostic`` objects."""

    if solved_case is None:
        raise AdapterError("Connect a SolvedCase.")
    tolerance_values = dict(tolerances or {})
    residual_tolerance = tolerance_values.get(
        "residual",
        tolerance_values.get("residual_tolerance", residual_tolerance),
    )
    closure_tolerance = tolerance_values.get(
        "closure",
        tolerance_values.get("closure_tolerance", closure_tolerance),
    )
    angle_tolerance = tolerance_values.get(
        "angle",
        tolerance_values.get("angle_tolerance", angle_tolerance),
    )
    planarity_tolerance = tolerance_values.get(
        "planarity",
        tolerance_values.get("planarity_tolerance", planarity_tolerance),
    )
    residual_limit = finite_float(
        residual_tolerance,
        "Residual tolerance",
        positive=True,
    )
    closure_limit = finite_float(
        closure_tolerance,
        "Closure tolerance",
        positive=True,
    )
    angle_limit = finite_float(angle_tolerance, "Angle tolerance", positive=True)
    planarity_limit = finite_float(
        planarity_tolerance,
        "Planarity tolerance",
        positive=True,
    )

    diagnostics = []
    metadata = get_any(solved_case, ("metadata",), {})
    raw = metadata.get("raw_diagnostics", {}) if isinstance(metadata, Mapping) else {}
    if not isinstance(raw, Mapping):
        raw = {}

    maximum_free_residual = raw.get("max_free_residual")
    residuals = tuple(get_any(solved_case, ("residuals",), ()))
    if maximum_free_residual is not None or residuals:
        diagnostics.append(
            _diagnostic(
                "equilibrium.residual",
                (
                    abs(float(maximum_free_residual))
                    if maximum_free_residual is not None
                    else max((_norm(value) for value in residuals), default=0.0)
                ),
                residual_limit,
                "Maximum free-node equilibrium residual.",
            )
        )

    closure = raw.get(
        "global_force_error_norm",
        raw.get("closure_error", raw.get("stitch_error")),
    )
    if closure is not None:
        diagnostics.append(
            _diagnostic(
                "equilibrium.closure",
                abs(float(closure)),
                closure_limit,
                "Global external-force closure error.",
            )
        )

    raw_angle = raw.get(
        "max_reciprocal_angle_deviation",
        raw.get("reciprocity_error"),
    )
    if raw_angle is not None:
        angle = abs(float(raw_angle)) % 180.0
        # Form/force edges are unoriented lines.  An upstream 177.9-degree
        # direction difference is therefore a 2.1-degree reciprocity error.
        unoriented = min(angle, 180.0 - angle)
        diagnostics.append(
            _diagnostic(
                "reciprocity.angle",
                unoriented,
                angle_limit,
                "Maximum unoriented form-force angle deviation.",
                "deg",
            )
        )

    planarity = raw.get("max_planarity_error", raw.get("planarity_error"))
    if planarity is not None:
        diagnostics.append(
            _diagnostic(
                "geometry.planarity",
                abs(float(planarity)),
                planarity_limit,
                "Maximum diagram planarity error.",
            )
        )

    if not diagnostics:
        existing = tuple(get_any(solved_case, ("diagnostics",), ()))
        if existing:
            diagnostics.extend(existing)
        else:
            diagnostics.append(
                make_contract(
                    "Diagnostic",
                    code="validation.no_metrics",
                    severity="warning",
                    message="The solver returned no numeric validation metrics.",
                    context={},
                )
            )

    has_warning = any(
        str(getattr(item, "severity", "")).lower() in ("warning", "error")
        for item in diagnostics
    )
    if has_warning:
        return warning(
            tuple(diagnostics),
            "Validation completed with warnings.",
            diagnostic_count=len(diagnostics),
        )
    return tuple(diagnostics)


validate = validate_result
