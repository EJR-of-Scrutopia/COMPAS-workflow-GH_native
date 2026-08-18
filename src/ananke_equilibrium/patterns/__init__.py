"""Plugin-side pattern generators that ride on a solved Result payload.

Modules under this package are held to a stricter dependency diet than the
rest of ``ananke_equilibrium``: the live Rhino site-env (catenary-compas-2026)
carries numpy and compas but no scipy, so nothing here may import scipy.
Individual modules document their own exact budget; see
``armadillo_dual.py`` for the current one (numpy and the standard library
only, no compas).
"""

from __future__ import annotations

__all__: list = []
