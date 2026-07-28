# Source Grasshopper definition

Create `ananke_equilibrium_v01.gh` here in Rhino 8 using the ten entries in
`../components.toml`.

Each Python component should:

1. use the matching file from `../component_scripts/`;
2. use the exact input/output names and item/list access declared in the
   manifest;
3. set useful input descriptions and mark genuinely required inputs;
4. retain its Script component Instance ID after publication.

The `.gh` file is intentionally not fabricated outside Grasshopper because its
Script component Instance IDs become the public component GUIDs in the
published `.gha`.
