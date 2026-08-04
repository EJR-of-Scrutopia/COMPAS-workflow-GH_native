from __future__ import annotations

import compas_fea2

from ananke_fea.compat import apply_patches, require_backend


def test_require_backend_registers_opensees():
    assert require_backend() == "compas_fea2_opensees"
    assert compas_fea2.BACKEND is not None


def test_apply_patches_gives_nodes_a_public_loads_mapping():
    require_backend()
    apply_patches()

    from compas_fea2.model import Node

    node = Node(xyz=[0.0, 0.0, 0.0])
    assert node.loads == {}
    assert node.loads is node._loads


def test_apply_patches_is_idempotent():
    require_backend()

    # Node.loads and OpenseesStressFieldResults.jobdata are both class-level
    # patches, so they outlive this test once any other test (or module) has
    # already called apply_patches() in this process. Clear both first so
    # "first call" here means what it says, regardless of what ran before it.
    from compas_fea2.model import Node
    from compas_fea2_opensees.results.fields import OpenseesStressFieldResults

    if "loads" in Node.__dict__:
        del Node.loads
    if getattr(OpenseesStressFieldResults.jobdata, "_ananke_patch", False):
        del OpenseesStressFieldResults.jobdata

    first = apply_patches()
    second = apply_patches()
    assert first == ["Node.loads", "OpenseesStressFieldResults.jobdata"]
    assert second == []
