"""Demo 6: the COMPAS masonry template gallery.

compas_dem ships parametric masonry typologies. This builds the ones that
are actually implemented, reports their block and interface counts, and
shows them side by side.

Checked against compas_dem 0.5.0: ArchTemplate, BarrelVaultTemplate and
DomeTemplate build. WallTemplate raises, and the BlockModel factories
from_crossvault, from_fanvault, from_pavilionvault, from_nurbssurface,
from_stack and from_wall are all NotImplementedError stubs. This gallery
shows what works and says so about the rest, rather than quietly omitting
them.

As in demo 4: blocks and interfaces are geometry, not stability.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _common import BLOCK, CASE_COLOURS  # noqa: E402
from _common import add, banner, open_viewer, show, step  # noqa: E402

from compas.geometry import Translation  # noqa: E402

TOLERANCE = 1e-3
MINIMUM_AREA = 0.01

# Templates that build in compas_dem 0.5.0, with arguments that produce a
# readable block count rather than the library defaults.
RECIPES = [
    ("Arch", "ArchTemplate", {"rise": 3.0, "span": 8.0, "thickness": 0.35, "depth": 1.2, "n": 24}),
    ("Barrel vault", "BarrelVaultTemplate", {"span": 6.0, "length": 6.0, "thickness": 0.25, "rise": 1.2}),
    ("Dome", "DomeTemplate", {"meridians": 24, "hoops": 10}),
]

# Documented as unavailable rather than silently skipped.
UNAVAILABLE = [
    ("Wall", "WallTemplate raises TypeError in 0.5.0"),
    ("Cross vault", "BlockModel.from_crossvault is a NotImplementedError stub"),
    ("Fan vault", "BlockModel.from_fanvault is a NotImplementedError stub"),
    ("Pavilion vault", "BlockModel.from_pavilionvault is a NotImplementedError stub"),
]


def build(name, template_name, kwargs):
    """Build one template, returning the model and its counts."""

    import compas_dem.templates as templates
    from compas_dem.models import BlockModel

    cls = getattr(templates, template_name)
    model = BlockModel.from_template(cls(**kwargs))
    blocks = len(list(model.elements()))
    try:
        model.compute_contacts(tolerance=TOLERANCE, minimum_area=MINIMUM_AREA)
        contacts = len(list(model.contacts()))
    except Exception as error:
        contacts = 0
        print("   contact detection failed for {}: {}".format(
            name, type(error).__name__))
    return model, blocks, contacts


def extent(model):
    """Return the model's x and y size, for laying the gallery out."""

    xs, ys = [], []
    for element in model.elements():
        geometry = getattr(element, "modelgeometry", None) or getattr(
            element, "geometry", None
        )
        if geometry is None:
            continue
        try:
            points = list(geometry.vertices_attributes("xyz"))
        except Exception:
            continue
        xs.extend(point[0] for point in points)
        ys.extend(point[1] for point in points)
    if not xs:
        return 8.0, 8.0
    return (max(xs) - min(xs)), (max(ys) - min(ys))


def main() -> int:
    banner("1. Build the templates that work")
    built = []
    for name, template_name, kwargs in RECIPES:
        step("{} ({})".format(name, template_name))
        try:
            model, blocks, contacts = build(name, template_name, kwargs)
        except Exception as error:
            print("   FAILED: {}: {}".format(type(error).__name__, str(error)[:90]))
            continue
        print("   blocks {:<6} contacts {}".format(blocks, contacts))
        built.append((name, model, blocks, contacts))

    banner("2. What is not available in compas_dem 0.5.0")
    for name, reason in UNAVAILABLE:
        print("   {:<16} {}".format(name, reason))

    if not built:
        print("")
        print("Nothing built; nothing to show.")
        return 1

    banner("3. The gallery")
    viewer = open_viewer("COMPAS masonry templates")
    offset = 0.0
    for index, (name, model, blocks, contacts) in enumerate(built):
        width, _depth = extent(model)
        shift = Translation.from_vector([offset, 0.0, 0.0])
        colour = CASE_COLOURS[index % len(CASE_COLOURS)]
        count = 0
        for element in model.elements():
            geometry = getattr(element, "modelgeometry", None) or getattr(
                element, "geometry", None
            )
            if geometry is None:
                continue
            piece = geometry.transformed(shift)
            add(
                viewer.scene,
                piece,
                "{} block {}".format(name, count),
                show_faces=True,
                show_lines=True,
                facecolor=colour if index else BLOCK,
            )
            count += 1
        print("   {:<14} {} blocks placed at x offset {:.1f}".format(
            name, count, offset))
        offset += width * 1.4

    print("")
    print("   Every one of these is parametric: change the span, the rise, or")
    print("   the number of voussoirs and rebuild. None of it is stability.")
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
