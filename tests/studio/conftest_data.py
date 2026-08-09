"""A four-quad synthetic contract, small enough to reason about by hand.

Layout, plan view (z lifts the centre vertex 4):

    6 -- 7 -- 8
    |    |    |          faces: (0,1,4,3) (1,2,5,4) (3,4,7,6) (4,5,8,7)
    3 -- 4 -- 5          supports: the four corners 0, 2, 6, 8
    |    |    |          loads: 1 kN down on the centre vertex 4
    0 -- 1 -- 2

The shape mirrors the real export: equilibrium.vertices carry 3D points,
formGraph.faces index into them, loads are kilonewtons.
"""


def tiny_contract():
    verts = []
    for j in range(3):
        for i in range(3):
            z = 1.0 if (i, j) == (1, 1) else 0.0
            verts.append({"x": float(i), "y": float(j), "z": z})
    faces = [
        {"id": 0, "vertices": [0, 1, 4, 3]},
        {"id": 1, "vertices": [1, 2, 5, 4]},
        {"id": 2, "vertices": [3, 4, 7, 6]},
        {"id": 3, "vertices": [4, 5, 8, 7]},
    ]
    edges = [
        {"u": 0, "v": 1}, {"u": 1, "v": 2}, {"u": 3, "v": 4}, {"u": 4, "v": 5},
        {"u": 6, "v": 7}, {"u": 7, "v": 8}, {"u": 0, "v": 3}, {"u": 3, "v": 6},
        {"u": 1, "v": 4}, {"u": 4, "v": 7}, {"u": 2, "v": 5}, {"u": 5, "v": 8},
    ]
    return {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [{"nodeId": 4, "vector": {"x": 0.0, "y": 0.0, "z": -1.0}}],
            "resolvedSupportNodeIds": [0, 2, 6, 8],
        },
        "formGraph": {"faces": faces},
    }


def two_radius_contract():
    """Contract with two distinct radii: outer ring and inner ring.

    8 faces total (no vertex sharing):
      - Faces 0-3: outer ring, centred at radius 5, angles 0/90/180/270 degrees
      - Faces 4-7: inner ring, centred at radius 1, angles 0/90/180/270 degrees
    Each face is a small square (0.4 x 0.4) centred at its position with corners
    offset by ±0.2 around the centre. Each face has area ~0.16 m^2.

    When segmented with rings=2:
      - Outer (radius 5) maps to ring 0 (rim), placed in stage 1
      - Inner (radius 1) maps to ring 1 (crown), added in stage 2
    This exercises the rim-to-crown cumulative placement semantic.
    """
    import math

    verts = []
    faces = []
    edges = []
    vert_idx = 0

    # Build 8 faces: 4 outer (radius 5) + 4 inner (radius 1)
    for ring_idx, (radius, start_face_id) in enumerate([(5.0, 0), (1.0, 4)]):
        for i in range(4):
            angle = 2 * math.pi * i / 4
            cx = radius * math.cos(angle)
            cy = radius * math.sin(angle)

            # 4 corners of a 0.4x0.4 square around (cx, cy)
            corners = [
                {"x": cx - 0.2, "y": cy - 0.2, "z": 0.0},
                {"x": cx + 0.2, "y": cy - 0.2, "z": 0.0},
                {"x": cx + 0.2, "y": cy + 0.2, "z": 0.0},
                {"x": cx - 0.2, "y": cy + 0.2, "z": 0.0},
            ]
            corner_indices = list(range(vert_idx, vert_idx + 4))
            verts.extend(corners)

            # One quad face for this square
            faces.append({
                "id": start_face_id + i,
                "vertices": corner_indices,
            })

            # Edges for the square
            for j in range(4):
                edges.append({"u": corner_indices[j], "v": corner_indices[(j + 1) % 4]})

            vert_idx += 4

    return {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }
