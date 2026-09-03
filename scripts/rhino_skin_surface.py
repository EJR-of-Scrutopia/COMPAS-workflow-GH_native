"""Prove the Brep route section 5 is built on (check 12.5(a)).

Run inside Rhino 8. It builds one loft from two known polylines and reports
whether a valid single-face Brep comes back, then repeats the deterministic
fan of rule 5.2.3(d) for a cap-shaped loop. Nothing here touches the plugin:
it proves the API, which is the only part of section 5 this repository has
never exercised.
"""

import Rhino
import Rhino.Geometry as rg


def polyline(points):
    return rg.PolylineCurve([rg.Point3d(*point) for point in points])


def loft_two_runs():
    lower = polyline([(0, 0, 0), (1, 0, 0.1), (2, 0, 0.15)])
    upper = polyline([(0, 1, 0.4), (1, 1, 0.5), (2, 1, 0.55)])
    breps = rg.Brep.CreateFromLoft(
        [lower, upper],
        rg.Point3d.Unset,
        rg.Point3d.Unset,
        rg.LoftType.Straight,
        False,
    )
    if not breps or len(breps) != 1:
        return "FAIL: CreateFromLoft returned %r" % (breps,)
    brep = breps[0]
    if not brep.IsValid:
        return "FAIL: the loft came back invalid"
    if brep.Faces.Count != 1:
        return "FAIL: %d faces, and rule 5.2.3(a) promises one" % (
            brep.Faces.Count,
        )
    return "PASS: a two-section loft is one valid single-face Brep"


def fan_a_cap():
    loop = [
        (0.5, 0.0, 1.0), (0.35, 0.35, 1.0), (0.0, 0.5, 1.0),
        (-0.35, 0.35, 1.0), (-0.5, 0.0, 1.0), (-0.35, -0.35, 1.0),
        (0.0, -0.5, 1.0), (0.35, -0.35, 1.0),
    ]
    apex = rg.Point3d(0.0, 0.0, 1.2)
    faces = []
    for at in range(len(loop)):
        a = rg.Point3d(*loop[at])
        b = rg.Point3d(*loop[(at + 1) % len(loop)])
        faces.append(rg.Brep.CreateFromCornerPoints(a, b, apex, 1e-9))
    joined = rg.Brep.JoinBreps(faces, 1e-9)
    if not joined or len(joined) != 1:
        return "FAIL: the fan did not join into one Brep"
    return "PASS: a cap fans into one joined Brep of %d faces" % (
        joined[0].Faces.Count,
    )


print(loft_two_runs())
print(fan_a_cap())
