# Legacy solver core

These modules are the tested, Rhino-independent solver core migrated from the
original `tools/tree_forest_compas` prototype on 2026-07-28.

They remain under the `tree_forest_compas` import path so existing Grasshopper
definitions can continue to resolve their imports while the public plugin API
moves to `ananke_equilibrium`.

The modules intentionally import optional COMPAS packages lazily where
possible. The new adapters in `ananke_equilibrium.gh` are responsible for
turning bundled plugin inputs into calls to this core.
