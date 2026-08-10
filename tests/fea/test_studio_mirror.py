"""staging.py duplicates ananke_fea's density and gravity constants on
purpose: it must never import the solver stack (see solve_stage.py's module
docstring and tests/studio/test_studio_guard.py). tests/studio/test_staging.py
pins those constants to literal values because the main venv cannot import
ananke_fea at all. This test runs in .venv-fea, where both sides are
importable, and cross-checks the mirror directly: change a preset in
src/ananke_fea/materials.py or GRAVITY in model.py without updating
bench/studio/staging.py to match, and this fails loudly instead of the two
silently drifting apart.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_staging_constants_mirror_the_ananke_fea_presets():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import staging

    from ananke_fea.materials import PRESETS
    from ananke_fea.model import GRAVITY

    assert staging.DENSITIES == {
        "concrete": PRESETS["concrete"].density,
        "concrete-c50": PRESETS["concrete-c50"].density,
        "concrete-sprayed": PRESETS["concrete-sprayed"].density,
        "timber": PRESETS["timber"].density,
    }
    assert staging.GRAVITY == GRAVITY
    assert staging.THICKNESS == 0.2
