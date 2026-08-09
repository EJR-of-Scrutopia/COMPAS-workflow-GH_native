"""Concentric ring and wedge binning, rim to crown. The canonical copy.

binning.js mirrors this function for the instant slider; the numbered rule
in docs/superpowers/plans/2026-08-09-bench-studio.md Task 3 is the shared
contract, and tests/studio/fixtures/ pins it on the real export. Change the
rule in both places or the studio shows a parity warning banner.

floor(x + 0.5) instead of round(): Python rounds half to even, JavaScript
rounds half up, and a wedge count that differs at a .5 boundary would be a
silent parity break.
"""

from __future__ import annotations

import math
from typing import Dict, List

RING_MIN = 4
RING_MAX = 16
RING_DEFAULT = 8
WEDGES_AT_RIM = 12

TWO_PI = 2.0 * math.pi


def _half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def segment_key(ring: int, wedge: int) -> str:
    return "r{}w{}".format(ring, wedge)


def segment_faces(centroids: List[list], rings: int) -> Dict[str, object]:
    """Assign every face centroid to a (ring, wedge) segment cell.

    RING_MIN and RING_MAX bounds (4 to 16) are enforced by the API layer (server-side validator), not here.
    """

    if not centroids:
        raise ValueError("no centroids to segment")
    if rings < 1:
        raise ValueError("rings must be at least 1, got {}".format(rings))

    ax = sum(p[0] for p in centroids) / len(centroids)
    ay = sum(p[1] for p in centroids) / len(centroids)

    rhos = [math.hypot(p[0] - ax, p[1] - ay) for p in centroids]
    lo, hi = min(rhos), max(rhos)
    spread = hi - lo

    def ring_of(rho: float) -> int:
        if spread <= 0.0:
            return 0
        t = (hi - rho) / spread
        return min(rings - 1, int(math.floor(t * rings)))

    def rho_mid(ring: int) -> float:
        return hi - (ring + 0.5) * spread / rings

    rim_mid = rho_mid(0)
    wedge_counts = [
        max(1, _half_up(WEDGES_AT_RIM * rho_mid(r) / rim_mid)) if rim_mid > 0.0 else 1
        for r in range(rings)
    ]

    assignment: List[List[int]] = []
    for point, rho in zip(centroids, rhos):
        ring = ring_of(rho)
        count = wedge_counts[ring]
        theta = math.atan2(point[1] - ay, point[0] - ax) % TWO_PI
        offset = (ring % 2) * math.pi / count
        wedge = int(math.floor(((theta + offset) % TWO_PI) / (TWO_PI / count)))
        assignment.append([ring, min(wedge, count - 1)])

    occupied = {tuple(pair) for pair in assignment}
    order = [
        [ring, wedge]
        for ring in range(rings)
        for wedge in range(wedge_counts[ring])
        if (ring, wedge) in occupied
    ]

    return {
        "axis": [ax, ay],
        "rings": rings,
        "wedge_counts": wedge_counts,
        "assignment": assignment,
        "order": order,
    }
