"""Demo 5: a robot placing the vault's blocks, with no ROS anywhere.

The blocks come from the same tessellated pavilion as demo 4, scaled into a
UR5's reach. For each block the script solves closed-form inverse kinematics,
picks the arm posture nearest the current one so the motion stays continuous,
and animates the arm placing them from springing to crown.

What this is: analytical inverse kinematics, which is exact, instant, and
needs no solver, no ROS, and no simulator.

What this is not: it does not check for collisions, it does not plan a
trajectory around obstacles, and it does not know the arm's dynamics. Those
are planning problems, and they are where PyBullet or ROS with MoveIt would
come in. Reaching a frame and moving safely between frames are different
questions, and only the first is answered here.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import BLOCK, COMPRESSION, DEMO, PAVILION, SURFACE  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402
from _robot import RobotDrawing, best_solution, interpolate  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402
from compas.geometry import Frame, Point, Scale, Translation  # noqa: E402

from ananke_equilibrium.cli.results import load_result  # noqa: E402
from ananke_equilibrium.cli.results import thrust_faces  # noqa: E402
from ananke_equilibrium.cli.results import thrust_vertices  # noqa: E402

# UR5 reach is about 0.85 m, so the vault is brought down to bench scale.
TARGET_FOOTPRINT = 0.42
BASE_OFFSET = (0.42, 0.0, 0.0)
MAX_BLOCKS = 28
FRAMES_PER_MOVE = 6


def mini_vault_targets(result):
    """Scale the thrust surface into reach and return block centres."""

    vertices = thrust_vertices(result)
    faces = thrust_faces(result)
    mesh = Mesh.from_vertices_and_faces(vertices, faces)

    xs = [point[0] for point in vertices]
    ys = [point[1] for point in vertices]
    zs = [point[2] for point in vertices]
    footprint = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    factor = TARGET_FOOTPRINT / footprint
    centre = [
        (max(xs) + min(xs)) / 2.0,
        (max(ys) + min(ys)) / 2.0,
        min(zs),
    ]

    mesh.transform(Translation.from_vector([-c for c in centre]))
    mesh.transform(Scale.from_factors([factor, factor, factor]))
    mesh.transform(Translation.from_vector(list(BASE_OFFSET)))

    centres = []
    for face in mesh.faces():
        point = mesh.face_centroid(face)
        centres.append([float(point[0]), float(point[1]), float(point[2])])
    # Build from the springing upward, which is how a vault actually goes up.
    centres.sort(key=lambda p: (round(p[2], 4), math.hypot(p[0] - BASE_OFFSET[0], p[1])))
    return mesh, centres[:MAX_BLOCKS]


def main() -> int:
    result_path = require(
        PAVILION / "results" / "result.json",
        "Run demo/01_solve_pavilion.py first: it produces the result file.",
    )
    result = load_result(result_path)

    banner("1. Load the robot")
    from compas_fab.robots import RobotCellLibrary

    step("UR5 from the compas_fab library, with geometry, offline")
    cell, _state = RobotCellLibrary.ur5(load_geometry=True)
    model = cell.robot_model
    print("   robot           {}".format(model.name))
    print("   joints          {} configurable".format(
        len(model.get_configurable_joints())))

    banner("2. Turn the vault into a placement sequence")
    mesh, centres = mini_vault_targets(result)
    print("   {} block positions, scaled to a {} m footprint".format(
        len(centres), TARGET_FOOTPRINT))

    banner("3. Solve inverse kinematics for every placement")
    from compas_fab.backends.kinematics import UR5Kinematics

    kinematics = UR5Kinematics()
    configurations = []
    placed_points = []
    reference = None
    reachable = 0
    for point in centres:
        # Tool pointing straight down at the block position.
        frame = Frame(point, [1.0, 0.0, 0.0], [0.0, -1.0, 0.0])
        try:
            solutions = kinematics.inverse(frame)
        except Exception:
            solutions = None
        choice = best_solution(solutions, reference)
        if choice is None:
            continue
        reference = choice
        configurations.append(choice)
        placed_points.append(point)
        reachable += 1
    print("   reachable       {} of {} positions".format(reachable, len(centres)))
    if not configurations:
        print("   Nothing was reachable; adjust BASE_OFFSET or TARGET_FOOTPRINT.")
        return 1
    print("   solver          closed form, no ROS, no simulator, no iteration")

    banner("4. Watch it build")
    viewer = open_viewer("UR5 placing the vault")

    add(
        viewer.scene,
        mesh,
        "Target vault",
        show_faces=True,
        show_lines=True,
        opacity=0.15,
        facecolor=SURFACE,
    )

    start = model.zero_configuration()
    robot = RobotDrawing(viewer.scene, model, start, colour=(0.35, 0.38, 0.42))

    markers = []
    for index, point in enumerate(placed_points):
        obj = add(
            viewer.scene,
            Point(*point),
            "Block {}".format(index + 1),
            pointsize=18,
            pointcolor=BLOCK,
        )
        markers.append(obj)
        if obj is not None:
            try:
                obj.show = False
            except Exception:
                pass

    path = []
    current = list(start.joint_values)
    for target in configurations:
        path.extend(interpolate(current, target, FRAMES_PER_MOVE))
        current = target
    reveal_at = {
        (index + 1) * FRAMES_PER_MOVE - 1: index
        for index in range(len(configurations))
    }

    print("   {} placements, {} animation frames".format(
        len(configurations), len(path)))
    print("")
    print("   Analytical inverse kinematics only. No collision checking and")
    print("   no trajectory planning: reaching a frame and moving safely")
    print("   between frames are different questions.")

    state = {"frame": 0}
    configuration = start.copy()

    @viewer.on(interval=90, frames=len(path))
    def build(frame):
        index = state["frame"]
        if index >= len(path):
            return
        configuration.joint_values = path[index]
        robot.move(configuration)
        if index in reveal_at:
            marker = markers[reveal_at[index]]
            if marker is not None:
                try:
                    marker.show = True
                    marker.update()
                except Exception:
                    pass
        state["frame"] = index + 1

    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
