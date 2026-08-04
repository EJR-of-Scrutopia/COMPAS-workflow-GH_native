# Removed component GUIDs

Deleted 2026-08-03 by decision in the component-surface redesign spec.
Saved definitions referencing these GUIDs lose those components on open.

| Component | GUID |
| --- | --- |
| Network | a9f470fc-e1a8-46c4-ba4c-d7fbe515b161 |
| Support Set | 73b719d9-9b24-4086-a023-a06313f4dd17 |
| Load Case | 1ba4e155-b5e5-4043-89b3-e062a8e72fb5 |
| Equilibrium Problem | 24868635-057b-4926-92d9-ec9a76bcf451 |
| FD Settings | 9de76173-8146-4b52-98d0-a0cc1c3d120a |
| FD Solve (v0.2) | cfcade39-f94d-4367-b9a8-9defedeff537 |
| TNA Control (v0.2) | 678439fc-d4d9-4734-9567-3f266d3e978b |
| TNA Solve (one-shot) | 8913cdd7-f563-4930-a310-fd62b3a31831 |
| TNA Pattern | 2fb2617f-d952-4f22-b7d5-0383c8cc203b |
| TNA Supports | fd767b85-9dc2-48a2-afdb-504f9db33640 |
| TNA Relax + Boundaries | 2f8fddfa-1e46-4546-afa7-c114db411b09 |
| TNA Equilibrium | 8dc94461-dcd8-4556-8ace-d201d2e1c6c3 |
| TNA Reciprocal | 30aa4b56-6d9e-47dd-8b15-94a56a046cf6 |
| Graphic Diagram Display | 0c17dc94-a6f0-48b0-98fa-ab6766c64912 |
| Equilibrium Preview | 471c5479-6c2c-479c-9372-3dc1fd31e85e |
| TNA Geometry | 3943da0e-bb1e-4375-9fa9-8b6e3019aacb |
| TNA Members | f543cb90-bef4-46ea-8510-7aa075c57279 |
| TNA Actions | 0ed716a8-744c-45dc-bc47-98b9e41d2f65 |
| Result Breakdown | c80b2201-c11b-4364-895e-5600ff6bcf01 |

Deleted 2026-08-04 in the canvas-feedback round: TNA Solve absorbed the
iteration control as one optional input with an auto-converging default,
so a settings-bundle component no longer earns its canvas space.

| Component | GUID |
| --- | --- |
| Control | a6d19e73-5f2b-4c8e-b0a4-9c3e7d1f5b28 |
