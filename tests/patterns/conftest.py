"""Shared synthetic fixture for the Armadillo Dual pattern tests.

``dome_result`` builds a coarse hemispherical TNA-shaped Result payload: an
apex, a handful of latitude rings down to an equator, meridian member edges
(force-bearing, radiating from the apex to the equator) and an equator
support ring. It mirrors the ``encode_tna_result`` shape read off
codec.py / gh/export.py: the solved 3D vertices and member forces nest under
"equilibrium", face topology lives in "form_graph", and support node IDs are
named explicitly in ``equilibrium.mappings.resolved_support_ids`` -- nothing
here is inferred from geometry.

This fixture is intentionally reused across the Armadillo Dual task files
(the line field here in Task 1, streamlines and cells in later tasks), so
the geometry helpers it returns alongside the payload (vertex positions,
longitude/latitude lookup, the analytic meridian tangent) are kept generic
rather than tailored to any one task's assertions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple

import pytest


Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class DomeGeometry:
    """Geometry helpers matched index-for-index to a built dome's payload."""

    n_rings: int
    n_segments: int
    radius: float
    apex_index: int
    positions: Tuple[Point3, ...]
    support_vertex_ids: Tuple[int, ...]
    meridian_edges: Tuple[Tuple[int, int], ...]
    apex_faces: Tuple[Tuple[int, int, int], ...]
    quad_faces: Tuple[Tuple[int, int, int, int], ...]

    def ring_vertex(self, ring: int, segment: int) -> int:
        j = segment % self.n_segments
        return 1 + ring * self.n_segments + j

    def lonlat(self, vertex_id: int) -> Optional[Tuple[float, float]]:
        """Return (theta, phi) for a ring vertex, or None for the apex."""

        if vertex_id == self.apex_index:
            return None
        k = vertex_id - 1
        ring = k // self.n_segments
        segment = k % self.n_segments
        phi = (ring + 1) * (math.pi / 2.0) / self.n_rings
        theta = segment * (2.0 * math.pi / self.n_segments)
        return theta, phi

    @staticmethod
    def meridian_tangent(theta: float, phi: float) -> Tuple[float, float, float]:
        """Unit tangent in the direction of increasing phi (pole -> equator)."""

        return (
            math.cos(theta) * math.cos(phi),
            math.sin(theta) * math.cos(phi),
            -math.sin(phi),
        )

    def face_centroid_lonlat(
        self, face: Sequence[int]
    ) -> Optional[Tuple[float, float]]:
        """Average (theta, phi) of a face's ring vertices, skipping the apex.

        theta is a circular mean (atan2 of summed sin/cos), not a plain
        arithmetic mean: faces straddling the theta=0/2*pi seam (the last
        segment wrapping back to the first) would otherwise average to the
        wrong side of the dome entirely.
        """

        angles = [self.lonlat(v) for v in face if v != self.apex_index]
        angles = [a for a in angles if a is not None]
        if not angles:
            return None
        theta = math.atan2(
            sum(math.sin(a[0]) for a in angles),
            sum(math.cos(a[0]) for a in angles),
        )
        phi = sum(a[1] for a in angles) / len(angles)
        return theta, phi


def _canonical(edge: Tuple[int, int]) -> Tuple[int, int]:
    u, v = edge
    return (u, v) if u <= v else (v, u)


def _build_dome_result(
    n_rings: int = 4,
    n_segments: int = 8,
    radius: float = 3.0,
    meridian_force: float = -2.5,
    include_forces: bool = True,
    include_diagrams: bool = False,
    edge_force_overrides: Optional[Mapping[Tuple[int, int], float]] = None,
    extra_edges: Optional[Sequence[Tuple[Tuple[int, int], float]]] = None,
) -> Tuple[Dict[str, Any], DomeGeometry]:
    """Build a synthetic TNA Result payload for a coarse hemisphere dome.

    Returns ``(result, geometry)``. ``result`` is shaped exactly like
    ``encode_tna_result``'s output (see gh/export.py's docstring): 3D
    vertices and member forces nest under "equilibrium", face topology
    lives in "form_graph", and support IDs are named explicitly in
    ``equilibrium.mappings.resolved_support_ids``.
    """

    apex_index = 0
    positions: List[Point3] = [(0.0, 0.0, radius)]
    for ring in range(n_rings):
        phi = (ring + 1) * (math.pi / 2.0) / n_rings
        for segment in range(n_segments):
            theta = segment * (2.0 * math.pi / n_segments)
            positions.append(
                (
                    radius * math.sin(phi) * math.cos(theta),
                    radius * math.sin(phi) * math.sin(theta),
                    radius * math.cos(phi),
                )
            )

    def ring_vertex(ring: int, segment: int) -> int:
        return 1 + ring * n_segments + (segment % n_segments)

    meridian_edges: List[Tuple[int, int]] = []
    for segment in range(n_segments):
        meridian_edges.append((apex_index, ring_vertex(0, segment)))
    for ring in range(n_rings - 1):
        for segment in range(n_segments):
            meridian_edges.append(
                (ring_vertex(ring, segment), ring_vertex(ring + 1, segment))
            )

    overrides = {
        _canonical(edge): float(force)
        for edge, force in (edge_force_overrides or {}).items()
    }
    member_forces: List[float] = [
        overrides.get(_canonical(edge), float(meridian_force))
        for edge in meridian_edges
    ]

    edges: List[Tuple[int, int]] = list(meridian_edges)
    for edge, force in extra_edges or ():
        edges.append(tuple(edge))
        member_forces.append(float(force))

    apex_faces: List[Tuple[int, int, int]] = []
    for segment in range(n_segments):
        apex_faces.append(
            (
                apex_index,
                ring_vertex(0, segment),
                ring_vertex(0, segment + 1),
            )
        )

    quad_faces: List[Tuple[int, int, int, int]] = []
    for ring in range(n_rings - 1):
        for segment in range(n_segments):
            quad_faces.append(
                (
                    ring_vertex(ring, segment),
                    ring_vertex(ring, segment + 1),
                    ring_vertex(ring + 1, segment + 1),
                    ring_vertex(ring + 1, segment),
                )
            )

    faces = [list(face) for face in apex_faces] + [
        list(face) for face in quad_faces
    ]

    support_vertex_ids = tuple(
        ring_vertex(n_rings - 1, segment) for segment in range(n_segments)
    )

    equilibrium: Dict[str, Any] = {
        "vertices": [list(p) for p in positions],
        "edges": [list(e) for e in edges],
        "member_forces": list(member_forces) if include_forces else [],
        "mappings": {
            "resolved_support_ids": list(support_vertex_ids),
        },
    }

    result: Dict[str, Any] = {
        "kind": "Result",
        "solver": "tna",
        "resultSchema": "0.2",
        "equilibrium": equilibrium,
        "form_graph": {
            "vertices": [
                {"id": idx, "key": idx, "point": list(p)}
                for idx, p in enumerate(positions)
            ],
            "edges": [
                {"id": idx, "u": u, "v": v}
                for idx, (u, v) in enumerate(edges)
            ],
            "faces": [
                {"id": idx, "key": idx, "vertices": face}
                for idx, face in enumerate(faces)
            ],
        },
    }

    if include_diagrams:
        force_densities = [
            abs(force) / max(1.0, radius) for force in member_forces
        ]
        equilibrium["force_densities"] = force_densities
        result["force_graph"] = {
            "vertices": [
                {"id": idx, "key": idx, "point": [float(idx), 0.0, 0.0]}
                for idx in range(len(edges))
            ],
            "edges": [
                {"id": idx, "u": idx, "v": (idx + 1) % max(1, len(edges))}
                for idx in range(len(edges))
            ],
            "faces": [],
        }

    geometry = DomeGeometry(
        n_rings=n_rings,
        n_segments=n_segments,
        radius=radius,
        apex_index=apex_index,
        positions=tuple(positions),
        support_vertex_ids=support_vertex_ids,
        meridian_edges=tuple(meridian_edges),
        apex_faces=tuple(apex_faces),
        quad_faces=tuple(quad_faces),
    )

    return result, geometry


@pytest.fixture
def dome_result() -> Callable[..., Tuple[Dict[str, Any], DomeGeometry]]:
    """Factory fixture: call with keyword overrides to build a dome payload.

    Returns ``(result, geometry)`` -- see ``_build_dome_result`` for the
    full parameter list (ring/segment counts, force presence, a diagram
    fallback, per-edge force overrides, and extra injected edges for
    building a deliberately noisy face).
    """

    return _build_dome_result
