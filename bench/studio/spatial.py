"""A uniform bucket grid over the plan, so the cut is not quadratic.

Every pass in the engine is "which of these thousands of things are near
this box": which welded points lie on this edge, which cells contain this
centroid, which render face is under this point. Without an index each of
those is a full scan and the whole build goes from a second to minutes.

Stdlib only: the bundle path imports this.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple


class Grid:
    def __init__(self, cell: float):
        self.cell = max(float(cell), 1e-9)
        self.buckets: Dict[Tuple[int, int], List[int]] = {}

    def _keys(self, x0: float, y0: float, x1: float, y1: float):
        i0 = int(math.floor(x0 / self.cell))
        i1 = int(math.floor(x1 / self.cell))
        j0 = int(math.floor(y0 / self.cell))
        j1 = int(math.floor(y1 / self.cell))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield (i, j)

    def insert(self, index: int, x0: float, y0: float, x1: float, y1: float) -> None:
        for key in self._keys(x0, y0, x1, y1):
            self.buckets.setdefault(key, []).append(index)

    def query(self, x0: float, y0: float, x1: float, y1: float) -> List[int]:
        found: List[int] = []
        seen = set()
        for key in self._keys(x0, y0, x1, y1):
            for index in self.buckets.get(key, ()):
                if index not in seen:
                    seen.add(index)
                    found.append(index)
        return found
