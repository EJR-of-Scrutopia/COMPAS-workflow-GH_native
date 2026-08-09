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

    Outer ring: 4 faces centred near radius 5.
    Inner ring: 4 faces centred near radius 1.
    When segmented with rings=2:
      - Outer (radius 5) maps to ring 0 (rim)
      - Inner (radius 1) maps to ring 1 (crown)
    This exercises the rim-to-crown cumulative placement semantic.
    """
    import math

    verts = []
    # Outer ring: 4 square faces at radius ~5
    for i in range(8):
        angle = 2 * math.pi * i / 4
        r = 5.0
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        verts.append({"x": x, "y": y, "z": 0.0})

    # Inner ring: 4 square faces at radius ~1
    for i in range(8):
        angle = 2 * math.pi * i / 4
        r = 1.0
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        verts.append({"x": x, "y": y, "z": 0.0})

    # Outer ring faces (indices 0-3)
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces.append({"id": i, "vertices": [i, j, j + 4, i + 4]})

    # Inner ring faces (indices 4-7)
    for i in range(4):
        j = (i + 1) % 4
        faces.append(
            {"id": i + 4, "vertices": [i + 8, j + 8, j + 12, i + 12]}
        )

    edges = []
    for i in range(4):
        edges.append({"u": i, "v": (i + 1) % 4})
        edges.append({"u": i + 4, "v": ((i + 1) % 4) + 4})
        edges.append({"u": i, "v": i + 4})
        edges.append({"u": i + 8, "v": (i + 1) % 4 + 8})
        edges.append({"u": i + 12, "v": ((i + 1) % 4) + 12})
        edges.append({"u": i + 8, "v": i + 12})

    return {
        "equilibrium": {
            "vertices": verts,
            "edges": edges,
            "loads": [],
            "resolvedSupportNodeIds": [0, 1, 2, 3],
        },
        "formGraph": {"faces": faces},
    }
