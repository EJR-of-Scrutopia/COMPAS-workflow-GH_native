# CRA Engineering Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CRA verdict actually land on real vault geometry, by making contact detection exact instead of tolerance-dependent, using the solver that finishes, and sizing the rigid-block model to what the solver can afford.

**Architecture:** Three changes, each backed by measurements in `.superpowers/sdd/2026-08-10-studio-cra-feasibility/cra-diagnostics.md`. Wall quads become triangle pairs split on a shared-edge diagonal, so both blocks of a joint present coincident coplanar faces and detection works at a tight fixed tolerance. `cra_solve` gives way to `cra_penalty_solve`. Staging coarsens the CRA-only block model to a measured block budget and records the coarsening so the UI can say what the verdict describes.

**Tech Stack:** compas_cra 0.4.0 with IPOPT in `.venv-cra`, stdlib Python server modules, pytest, node (parity, skips without it).

**Worktree:** branch `feature/studio-cra` in `COMPAS-Workflow-bench`. Paths contain spaces: always quote. Studio suite `./.venv/Scripts/python.exe -m pytest tests/studio -q`; fea suite `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`. `.venv-cra` has no pip and no pytest: never install into it, always shell into it with `python -c` drivers.

## Measurements this plan is built on

From the diagnostic pass, on the real Trial 2 export at rings=2 (13 blocks, 17 detectable joints):

- Warped wall quads at tmax 1e-6 detect **1** interface, leaving 5 of 7 free blocks isolated. Triangulated walls detect **17 of 17** at that same tight tolerance.
- `assembly_interfaces_numpy` deliberately skips pairs where both blocks are supports, so the detectable denominator (17) is below the geometric one (20). Any coverage assertion must use the detectable count.
- Solver at 8 blocks: `cra_solve` 21.2 s, `cra_penalty_solve` 1.2 s, both infeasible. At 4 to 6 blocks `cra_solve` only reaches maxIterations (no verdict) where the penalty form returns a clean verdict in about a second.
- Both solvers exceed a 300 s cap at 10 blocks and above, with clean detection. 8 blocks is the affordable ceiling.

## Global Constraints

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- Never add Co-Authored-By or any AI attribution to commits.
- The server imports no solver stack outside `solve_stage.py` and `solve_cra.py`; `blocks.py` and `staging.py` stay stdlib.
- Honest verdicts: stands true, false, or null with a message. A coarsened model must be labelled as one, never presented as the drawn segmentation.
- Verdict dict shape stays `{stands, status, message, blocks, interfaces, mu}` across `solve_cra._result`, `staging._cra_subprocess_runner`'s failure dict, and every test stub.
- Commit after every task; never push.

---

### Task 1: Triangulated wall faces

**Files:**
- Modify: `bench/studio/blocks.py` (wall construction in `segment_blocks`)
- Test: `tests/studio/test_blocks.py`

**Interfaces:**
- Consumes: `segment_boundary_edges(faces, face_indices)` returning boundary edges as `(a, b)` analysis vertex id pairs, and the existing `top_of` / `bottom_of` welded index maps.
- Produces: block dicts unchanged in shape, but `faces` now carries two triangles per boundary edge instead of one quad. Task 2 relies on every wall face being exactly planar.

The diagonal rule is the whole point: the wall between two adjacent segments is built twice, once by each block, over the same four points. Both copies must be split along the same diagonal or the two sides present non-matching faces. Deriving the diagonal from the shared edge's analysis vertex ids (which both blocks see identically, just traversed in opposite directions) guarantees agreement.

- [ ] **Step 1: Write the failing tests**

In `tests/studio/test_blocks.py`, update `test_each_segment_becomes_a_closed_prism`: a single quad segment now has 1 top face, 1 bottom face and 4 walls of 2 triangles each, so `len(first["faces"]) == 10`, and the vertex count stays 8. Keep the existing directed-edge orientation assertions exactly as they are. Then append:

```python
def wall_triangles(block):
    """The block's wall faces as frozensets of (analysis vertex, surface)."""

    out = []
    for face in block["faces"]:
        labels = [tuple(block["sources"][i]) for i in face]
        surfaces = {label[1] for label in labels}
        if len(face) == 3 and len(surfaces) == 2:
            out.append(frozenset(labels))
    return out


def test_wall_faces_are_planar_triangles():
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    for block in result:
        for face in block["faces"]:
            labels = [tuple(block["sources"][i]) for i in face]
            if len({label[1] for label in labels}) == 2:
                assert len(face) == 3, "wall faces must be triangles, not quads"


def test_adjacent_blocks_split_the_shared_wall_the_same_way():
    # The wall on a shared edge is built by both blocks. Detection only
    # works if both present the SAME triangles, so the diagonal must come
    # from the shared edge's analysis vertex ids, not from build order.
    blocks = studio()
    result = blocks.segment_blocks(
        TILTED_VERTICES, FACES, ASSIGNMENT, ORDER, thickness=0.2, support_ids=[])
    first = set(wall_triangles(result[0], None))
    second = set(wall_triangles(result[1], None))
    shared = first & second
    assert len(shared) == 2, (
        "the shared edge 1-4 must yield exactly two identically split "
        "triangles present in both blocks, got {}".format(len(shared))
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_blocks.py -q`
Expected: FAIL (walls are still quads; the shared-split test finds 0 shared triangles).

- [ ] **Step 3: Implement**

In `bench/studio/blocks.py`, replace the wall loop at the end of `segment_blocks` (the block that appends `[top_of[b], top_of[a], bottom_of[a], bottom_of[b]]`) with:

```python
        # Walls are triangle pairs, not quads. Each vertex is offset along
        # its own normal, so a wall quad on curved geometry is not planar,
        # and compas_cra's interface detector rejects candidate faces that
        # sit off the base face's plane: warped walls cost 16 of 17 joints
        # on the real export. Triangles are planar by construction.
        #
        # The wall on a shared edge is built twice, once by each adjoining
        # block, over the same four points. Both copies must be cut along
        # the same diagonal or the two sides present faces that do not
        # match. The cut is chosen from the shared edge's analysis vertex
        # ids, which both blocks see identically (they traverse the edge in
        # opposite directions, so the a < b test picks opposite branches
        # and lands on the same diagonal). Walls still wind outward, as the
        # quads did.
        for a, b in segment_boundary_edges(faces, face_indices):
            ta, tb = top_of[a], top_of[b]
            ba, bb = bottom_of[a], bottom_of[b]
            if a < b:
                block_faces.append([tb, ta, ba])
                block_faces.append([tb, ba, bb])
            else:
                block_faces.append([ta, ba, bb])
                block_faces.append([ta, bb, tb])
```

- [ ] **Step 4: Run the studio suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q`
Expected: PASS. The node parity test compares positions looked up by (analysis vertex, surface) through `sources`, which triangulation does not change, so it must still pass; if it fails, report that rather than weakening it.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/blocks.py tests/studio/test_blocks.py
git commit -m "fix(studio): planar triangle walls so contact detection finds every joint"
```

---

### Task 2: Fixed tight tolerance and the penalty solver

**Files:**
- Modify: `bench/studio/solve_cra.py` (drop `_face_warp` and `_max_face_warp`, fixed tmax, penalty solver)
- Test: `tests/studio/test_solve_cra.py`

**Interfaces:**
- Consumes: planar triangle walls from Task 1.
- Produces: unchanged verdict dict shape. `solve()` keeps its `solver_available` seam.

- [ ] **Step 1: Write the failing tests**

In `tests/studio/test_solve_cra.py`, the existing warp/tmax regression test (built from the tilted toy mesh through `blocks.segment_blocks`) stays and must keep passing. Add:

```python
def test_the_module_uses_the_penalty_formulation_at_a_fixed_tolerance():
    # Source pins: the adaptive tmax workaround existed only because warped
    # wall quads needed it. With planar triangle walls, detection works at
    # the tight tolerance, and the penalty solver is the one that finishes
    # (cra_solve reaches maxIterations without a verdict at 4 to 6 blocks
    # and blows a 300 s cap where the penalty form answers in about a
    # second): see .superpowers/sdd/2026-08-10-studio-cra-feasibility/
    # cra-diagnostics.md.
    source = (REPO / "bench" / "studio" / "solve_cra.py").read_text(encoding="utf-8")
    assert "cra_penalty_solve" in source
    assert "tmax=1e-6" in source
    assert "_max_face_warp" not in source, "the adaptive tmax workaround is gone"
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cra.py -q`
Expected: FAIL on the new pin.

- [ ] **Step 3: Implement**

In `bench/studio/solve_cra.py`:

1. Delete `_face_warp` and `_max_face_warp` entirely.
2. Change the solver import from `from compas_cra.equilibrium import cra_solve` to `from compas_cra.equilibrium import cra_penalty_solve`.
3. Replace the tmax comment block and the `tmax = max(...)` line plus the detection call with:

```python
    # amin's default (0.1 m2) exceeds a thin joint wall's area; 1e-4 keeps
    # every genuine joint while still rejecting point contacts.
    #
    # tmax bounds how far a candidate face may sit off the base face's
    # plane before compas_cra rejects the interface. blocks.py builds walls
    # as planar triangles precisely so this can stay tight: on the real
    # export a tight 1e-6 recovers every detectable joint (17 of 17), where
    # the earlier warped quads found one. A loose tolerance would start
    # matching faces that are not really in contact.
    assembly_interfaces_numpy(assembly, nmax=10, tmax=1e-6, amin=1e-4)
```

4. Replace the `cra_solve(assembly, mu=mu, density=request["density"])` call with `cra_penalty_solve(assembly, mu=mu, density=request["density"])`, and extend the comment above the `except ValueError` branch to note that the penalty formulation raises the same termination ValueError, so the infeasible-versus-other classification is unchanged.
5. Update the module docstring's mention of `cra_solve` to name the penalty formulation and why (it finishes and is decisive where the plain form stalls).

- [ ] **Step 4: Run the tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_solve_cra.py -q`
Expected: PASS, none skipped. The real-solver tests exercise the penalty path now; if any changes verdict (for instance a fixture that previously reached maxIterations now returning a clean result), report the change rather than adjusting the fixture to hide it.

- [ ] **Step 5: Commit**

```bash
git add bench/studio/solve_cra.py tests/studio/test_solve_cra.py
git commit -m "fix(studio): tight fixed contact tolerance and the penalty solver"
```

---

### Task 3: Coarsen the CRA model to an affordable budget, and say so

**Files:**
- Modify: `bench/studio/staging.py` (budget constant, `cra_binning`, `run_staging`)
- Modify: `bench/studio/static/studio.js` (Data panel line)
- Modify: `docs/superpowers/specs/2026-08-10-studio-cra-feasibility-design.md` (record the pass)
- Test: `tests/studio/test_staging.py`, `tests/studio/test_static.py`

**Interfaces:**
- Consumes: `blocks.segment_blocks(vertices, faces, assignment, order, thickness, support_ids)`; `binned` from `segmentation.segment_faces`.
- Produces: `staging.CRA_BLOCK_BUDGET = 8`; `staging.cra_binning(assignment, order, budget)` returning `{"assignment", "order", "wedge_factor"}`; the staging document gains `"cra_wedge_factor"`; the UI reads `state.bundle.staging.cra_wedge_factor`.

Why coarsen: both solvers blow a 300 s cap at 10 blocks and finish comfortably at 8, and the cost is driven by contact polygons, so merging neighbouring wedges into one larger block cuts both the block count and the joint count. The verdict then describes a coarser assembly than the one drawn, which is a real modelling choice and must be labelled wherever it is reported.

- [ ] **Step 1: Write the failing tests**

Append to `tests/studio/test_staging.py`:

```python
def test_cra_binning_merges_wedges_until_the_block_budget_is_met():
    _, _, staging = studio()
    assignment = [[0, w] for w in range(12)]
    order = [[0, w] for w in range(12)]
    coarse = staging.cra_binning(assignment, order, budget=8)
    assert coarse["wedge_factor"] == 2
    assert len(coarse["order"]) == 6
    assert coarse["assignment"][0] == [0, 0]
    assert coarse["assignment"][3] == [0, 1]
    # Order stays the drop order, deduplicated, no cell repeated.
    assert len(coarse["order"]) == len({tuple(pair) for pair in coarse["order"]})


def test_cra_binning_leaves_a_small_model_alone():
    _, _, staging = studio()
    assignment = [[0, 0], [0, 1], [1, 0]]
    order = [[0, 0], [0, 1], [1, 0]]
    coarse = staging.cra_binning(assignment, order, budget=8)
    assert coarse["wedge_factor"] == 1
    assert coarse["order"] == order
    assert coarse["assignment"] == assignment


def test_run_staging_records_the_cra_wedge_factor(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        cra_runner=lambda request: {
            "stands": True, "status": "optimal", "message": "",
            "blocks": len(request["blocks"]), "interfaces": 1,
            "mu": request["mu"]},
    )
    assert document["cra_wedge_factor"] >= 1
    for stage in document["stages"]:
        assert stage["cra"]["blocks"] <= staging.CRA_BLOCK_BUDGET


def test_include_cra_false_leaves_the_wedge_factor_null(tmp_path):
    g, seg, staging = studio()
    contract_path = tmp_path / "Two-radius-contract.json"
    contract_path.write_text(json.dumps(two_radius_contract()), encoding="utf-8")
    geometry_path = tmp_path / "Two-radius-compas.json"
    geometry_path.write_text("{}", encoding="utf-8")
    document = staging.run_staging(
        {"contract": contract_path, "geometry": geometry_path},
        material="concrete", rings=2, out_path=tmp_path / "o.json",
        runner=lambda request: {"converged": True, "message": ""},
        include_cra=False,
    )
    assert document["cra_wedge_factor"] is None
```

Append to `tests/studio/test_static.py`:

```python
def test_the_data_panel_labels_a_coarsened_cra_model():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "cra_wedge_factor" in body
    assert "coarser" in body or "coarsened" in body
```

- [ ] **Step 2: Run to verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio/test_staging.py tests/studio/test_static.py -q`
Expected: FAIL (no `cra_binning`, no `CRA_BLOCK_BUDGET`, no panel line).

- [ ] **Step 3: Implement the staging coarsening**

In `bench/studio/staging.py`, after `CRA_TIMEOUT_SECONDS`:

```python
CRA_BLOCK_BUDGET = 8
# Measured on the real export: with clean contact detection both compas_cra
# solvers finish 8 blocks (about a second in the penalty form, 21 s in the
# plain one) and blow a 300 s cap at 10. Cost tracks contact polygons, so
# merging neighbouring wedges into one larger block cuts blocks and joints
# together. See .superpowers/sdd/2026-08-10-studio-cra-feasibility/
# cra-diagnostics.md.
CRA_WEDGE_FACTORS = (1, 2, 3, 4, 6, 12)
```

And the binning helper, beside `stage_plan`:

```python
def cra_binning(assignment: List[list], order: List[list], budget: int) -> Dict:
    """Merge neighbouring wedges until the block model fits the budget.

    The display segmentation is what gets drawn and built; the CRA model is
    a coarser view of the same rings, because the rigid-block solve cannot
    afford one block per drawn cell. Merging is by wedge only: rings stay
    intact, so a stage still places whole rings and a coarse block never
    straddles two stages. Returns the merged assignment and drop order plus
    the factor used, which the document records so the UI can say the
    verdict describes a coarser assembly than the picture.
    """

    for factor in CRA_WEDGE_FACTORS:
        cells = {(pair[0], pair[1] // factor) for pair in order}
        if len(cells) <= budget:
            break
    coarse_assignment = [[pair[0], pair[1] // factor] for pair in assignment]
    coarse_order: List[list] = []
    seen = set()
    for pair in order:
        cell = (pair[0], pair[1] // factor)
        if cell not in seen:
            seen.add(cell)
            coarse_order.append([cell[0], cell[1]])
    return {
        "assignment": coarse_assignment,
        "order": coarse_order,
        "wedge_factor": factor,
    }
```

In `run_staging`, replace the `all_blocks` construction with:

```python
    all_blocks: List[dict] = []
    wedge_factor = None
    if include_cra:
        coarse = cra_binning(binned["assignment"], binned["order"], CRA_BLOCK_BUDGET)
        wedge_factor = coarse["wedge_factor"]
        all_blocks = blocks.segment_blocks(
            arrays["vertices"], arrays["faces"], coarse["assignment"],
            coarse["order"], thickness, set(geometry.support_ids(contract)),
        )
```

The per-stage selection can no longer match display segment keys, because the coarse cells have their own wedge numbers. Rings are placed whole, so select by ring instead. Replace the `placed = set(entry["segments"])` selection block with:

```python
        if include_cra:
            # Coarse cells merge wedges only, never rings, so a stage that
            # has placed rings 0..k-1 has placed exactly the coarse blocks
            # in those rings.
            stage_blocks = [
                b for b in all_blocks if b["ring"] < entry["rings_placed"]
            ]
            stage_entry["cra"] = cra_runner({
                "blocks": stage_blocks,
                "density": DENSITIES[material],
                "mu": FRICTION[material],
            })
```

And the document gains, beside `cra_mu`:

```python
        "cra_wedge_factor": wedge_factor,
```

- [ ] **Step 4: Implement the Data panel label**

In `bench/studio/static/studio.js`, inside `renderDataPanel`'s CRA section, after the block and interface counts paragraph, add:

```js
    const factor = state.bundle.staging && state.bundle.staging.cra_wedge_factor;
    if (factor && factor > 1) {
      const coarse = document.createElement("p");
      coarse.textContent = "verdict computed on a coarser model than the "
        + "drawing: neighbouring wedges merged in groups of " + factor
        + " to keep the rigid-block solve affordable";
      content.appendChild(coarse);
    }
```

- [ ] **Step 5: Record the pass in the spec**

In `docs/superpowers/specs/2026-08-10-studio-cra-feasibility-design.md`, append a section:

```markdown
## Engineering pass, 2026-08-10

The first real staged run showed the wave was honest but inert: warped wall
quads cost 16 of 17 joints, and the solve did not finish. Measured fixes,
recorded in .superpowers/sdd/2026-08-10-studio-cra-feasibility/cra-diagnostics.md:

- Wall faces are planar triangle pairs split on a shared-edge diagonal, so
  both blocks of a joint present matching coplanar faces. Detection then
  recovers every detectable joint at a tight fixed tmax of 1e-6. Note that
  compas_cra skips pairs where both blocks are supports, so the detectable
  joint count sits below the geometric one.
- The solver is cra_penalty_solve, not cra_solve: about a second against
  21 s at 8 blocks, and decisive where the plain form only reaches
  maxIterations. Upstream makes the same switch for its larger examples.
- The CRA model is coarsened by merging neighbouring wedges until it fits
  CRA_BLOCK_BUDGET (8 blocks), because both solvers blow a 300 s cap at 10.
  Rings are never merged, so stages stay whole. The document records
  cra_wedge_factor and the Data panel says when the verdict describes a
  coarser assembly than the drawing. A coarser model is optimistic: fewer
  joints means fewer ways to hinge, which is exactly why it is labelled
  rather than quietly substituted.
```

- [ ] **Step 6: Run the suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/studio -q` and `./.venv-fea/Scripts/python.exe -m pytest tests/fea -q -m "not slow"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bench/studio/staging.py bench/studio/static/studio.js docs/superpowers/specs/2026-08-10-studio-cra-feasibility-design.md tests/studio/test_staging.py tests/studio/test_static.py
git commit -m "feat(studio): size the CRA model to an affordable block budget"
```
