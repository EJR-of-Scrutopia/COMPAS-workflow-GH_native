# What the real exports say, and what it corrects

Written 7 October 2026, after reading the owner's actual Grasshopper exports for
the first time. Everything in the two cable net specs before this was built
against a data shape I invented and validated against fixtures of the same
invention. This records what the real files contain and which of my assumptions
they overturn.

## Where the files are

The studio's `bench/studio/settings.json` has carried the answer all along:

```
upload_folder    C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports
```

Two mechanism documents sit in its `Mechanisms` subfolder, both exported on
15 September 2026, both 31 MB: `5 sided form-mechanism.json` and
`Complex geometry-mechanism.json`. I had been looking in
`bench/demo/upload from grasshopper/`, which holds older four-file studies with
no mechanism document at all, and concluding from their absence that none had
ever been exported.

## The Grasshopper plugin needed no change

`plugin/native_v02/Components/ExportPayloads.cs` already writes `net_vertex` on
every wire, validates it against the vertex count, and refuses to write a
mechanism document at all when a wire cannot be resolved to a vertex. The
repeated claim in earlier notes that the plugin had to be updated before
anything could run was wrong.

## Five corrections to the specs

**1. The wires ARE the supports.** This is the important one. All 105 wires in
`5 sided form` attach to nodes listed in `equilibrium.resolvedSupportNodeIds`,
all at z = 0. The machine does not pull the net up at the crown, which is the
model both specs assume. It holds the net at its base, and those nodes are not
fixed by the ground: they are fixed by the wires.

`wires_from_mechanism` refused a wire on a support node, saying "commanding a
fixed node moves nothing". That rule was exactly backwards and would have
refused all 105 wires. It is inverted: a wire on a support node is expected, and
what is fixed is the machine end of each wire. `build_problem` now frees the
support nodes and fixes only the drum ends.

**2. 105 wires, not seven.** Fifteen instances of the seven-spool machine, seven
wires each. Every performance figure quoted from seven is wrong by a factor of
fifteen: the correction solve is 106 per stage, not 8, which is roughly two
minutes a stage rather than eight seconds.

**3. The reeving is 4, and it is in the document.** Every wire carries
`reeveFactor: 4` with `reeveFactorSource: "machine"`. The chooser offers one
fall or two and ignores the exported value. At four falls the ceiling is 1190 N
bound by the sheave, worse than the 1214 N reported for two.

**4. The wire shape is not what the adapter expected.** `wires` is at the top
level, not under `mechanism`; the name key is `id`; and there is no
`frame_point`. A wire carries `route`, about 1002 frames of
`{origin, xAxis, yAxis, zAxis, owner, ownerReel}` in the machine's LOCAL space,
meaning the cable centreline. `route[0]` is the net end and `route[-1]` the
machine end.

**5. Instances place the routes.** `instances[].frame` is the transform, with
`placement` being only a kind marker. World position is
`origin + x*xAxis + y*yAxis + z*zAxis`. Verified decisively: mapped that way,
`route[0]` lands on its own `net_vertex` to 1e-5 m for all 105 wires, while the
transposed reading misses by 14 m.

## Still unverified

Whether the real 1101-node problem settles at all. With the correction above it
has no ground fixity whatever, only the 105 drum ends, which is a different
problem from anything the engine has solved.

## The lesson worth keeping

The adapter was written to a guess, and every green test and live run
demonstrated only that the guess was self-consistent. One real file, read at the
start, would have caught all five corrections above. The information needed to
find it was in `settings.json` from the first day.
