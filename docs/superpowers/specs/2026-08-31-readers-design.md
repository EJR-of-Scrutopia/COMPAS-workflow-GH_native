# Readers rework: Monitor becomes Forces, Fit and Supports; Frame completes; Deconstruct slims

Date: 2026-08-31. Status: approved design, awaiting Param's spec review.
Follows the surface rework (docs/superpowers/specs/2026-08-30-surface-design.md), whose rules
this spec inherits wholesale: RES at input 0 and, where a RES output exists, at output 0;
port trees aligned so branch {i} of one output pairs with branch {i} of its partner; the
load-protection warning that compares archived port NAMES as well as counts; readers'
geometry outputs hidden; the ForceUnit trap (a Result's forces are kN unless it says
otherwise, and every conversion goes through MonitorMath.ToNewtons).

## 1. Purpose

Monitor is one component with six inputs and twenty-one outputs. It answers three
questions that are asked at different times: what the net's members carry, whether the
machine's frame reaches the solved state, and what the ground interfaces (anchors and
columns) must resist. This rework splits it into three components, one per question, with
the maths moved unchanged. In the same wave Frame gains the one output missing from
Param's essential list, Anchor Lines, and Deconstruct drops the four geometry outputs
Frame already carries, leaving it the statics and diagram reader.

Nothing in this spec changes a number. Every output of the three children is computed by
the same code path that computed it on Monitor, against the same fixtures.

## 2. The three children

All three live in panel 04 Read, take a RES at input 0, and emit a RES at output 0. The
RES passes through with that child's own diagnostics replaced (section 5). Port names,
nicknames, descriptions, defaults, optionality and tree structures are carried from
Monitor verbatim; the slot numbers below are the only thing that changes. Each child sets
the Message line the way Monitor did for the measures it now owns.

### 2.1 Forces

What the net's members carry, and what to cut. Name "Forces", GUID
6ca7992e-0d9c-46ed-85af-47448276d09d.

Inputs: Result RES (0); EA (1, optional, default 0); Cable Capacity CC (2, optional,
default 0).

Outputs: Result RES (0); Member Force F (1); Force Density q (2); Horizontal Force H (3);
Slack SL (4); Spool Length SP (5); Unstrained Length UL (6); Residuals E (7); Cable
Utilisation CU (8).

### 2.2 Fit

Whether the machine reaches the solved state. Name "Fit", GUID
9878783a-048d-4c95-bbc0-31351131a6a6.

Inputs: Result RES (0); EI (1, optional, default 0); Tolerance Tol (2, optional,
default 5).

Outputs: Result RES (0); Deviation DV (1); Deviation Stats DS (2); Reachable RC (3);
Unreachable UN (4); Bar Sag BS (5).

### 2.3 Supports

What the ground sees: anchors and columns. Name "Supports", GUID
3d99b855-4c2e-4d03-94ec-f695f21f86cc.

Inputs: Result RES (0); Column Capacity CO (1, optional, default 0).

Outputs: Result RES (0); Anchor Along AA (1); Anchor Across AX (2); Tip Reaction TR (3);
Column Force CF (4); Thrust TH (5); Lean LN (6); Column Utilisation CLU (7).

That accounts for all twenty of Monitor's data outputs: eight to Forces, five to Fit,
seven to Supports; none duplicated, none dropped.

## 3. Monitor retires

The Monitor component class is deleted and its GUID is not reused. A saved definition
that holds a Monitor loads it as an orphaned object, which is the honest outcome: its
twenty-one wires cannot be split mechanically across three components, and the author
places the one or two children they actually need, which is the point of the split.
MonitorMath stays where it is and is called by all three children; any private helpers on
the Monitor class that the children need are moved with them, not copied.

## 4. Frame gains Anchor Lines

Frame's outputs today end at Phase PH (slot 8). One output is APPENDED at slot 9 so no
existing wire moves, the same append rule Deconstruct's Force Lines used: Anchor Lines
AL, a Line tree branched EXACTLY as Anchor Nodes AN, one branch per connected support
strip, line i joining node i to node i+1 of that strip, so each branch holds one line
fewer than its AN partner. A strip of a single node contributes an empty branch, keeping
the branch count aligned. Like every Frame geometry output it is hidden by default and
follows the frame positions when the Result carries Mould.Frame. Frame is then Param's
complete essential reader: Mesh, Cables, Principal Lines, Principal Nodes, Anchor Nodes,
Anchor Lines, Perimeter Nodes, Perimeter Lines, Columns, Phase.

## 5. Diagnostics ownership

Monitor writes twenty entries under the monitor.* prefix into the RES it emits. Each
entry moves to the child whose outputs its numbers come from, re-keyed under that child's
own prefix with the suffix unchanged, the content and severity rules untouched:

- forces.*: counts, cable_tension, slack_cables, bar_force, spool, and the cable half of
  utilisation and demand_only (the halves that read Cable Capacity).
- fit.*: deviation, reachability, bar_sag, bar_sag_absent, bar_sag_shape_only,
  bar_unheld, intermediate_frame.
- supports.*: column_force, thrust_into_ground, no_columns, anchor_horizontal,
  anchor_split, column_frame_absent, and the column half of utilisation and demand_only
  (the halves that read Column Capacity).

A shared entry that today mixes both capacities (utilisation, demand_only) is split into
its two halves, each half saying only what its own child measures. Each child REPLACES
only its own prefix in the RES it emits, so chaining Forces, Fit and Supports in any
order accumulates all three sets, and re-solving one child never clobbers another's
entries. The monitor.* prefix disappears from the plugin.

## 6. Deconstruct slims

Deconstruct drops Thrust Mesh TM (slot 0), Columns CO (10), Heads HD (11) and Feet FT
(12). Erratum: this sentence first claimed Frame carries all four, and it does not.
Thrust Mesh and Columns moved to Frame; Heads and Feet were retired, their content
living on as Frame's Principal Nodes (each head stands on a notch) and the lower ends
of Frame's Columns branches. What remains, in this order: Member Lines M (0), Form
Lines FL (1), Member IDs MID (2), Node IDs NID (3), Support Points SP (4), Load Points LP
(5), Load Vectors LV (6), Reaction Points RP (7), Reaction Vectors RV (8), Force Lines
FCL (9). Ten outputs, the statics and diagram reader: the trees Monitor's children and
the diagram components align against. The component keeps its name; the load warning
covers the reshape by name (section 8).

## 7. Icons, panels, taxonomy

Icon map: the stress_analysis entry (Monitor, MO) is deleted; three entries are added in
04 Read: forces "FO", fit "FI", supports "SP", all with the 04 Read fill. Icons are
regenerated through plugin/icons/generate_icons.py and --check stays byte-green. The
component taxonomy (docs/component-taxonomy.md) replaces Monitor's row with three rows
and updates Deconstruct's and Frame's. The component count moves from twenty to
twenty-two (this sub-project alone; the Skin sub-project then takes it to twenty-one).

## 8. Loading old definitions

Three warnings, all covered by the name-comparing Mismatch rule:

- Monitor: orphaned object; the author deletes it and places the children needed. This is
  the one manual rewire of the wave.
- Deconstruct: output count 14 to 10 with every remaining wire shifting up; the warning
  leads with the removed names so the author checks each reattached wire.
- Frame: output count 9 to 10 by appending; nothing moves; the warning names the append.

## 9. Harness

The smoke harness re-points Monitor's existing value checks at the three children: the
same fixture nets must produce the same F, q, H, SL, SP, UL, E, CU, DV, DS, RC, UN, BS,
AA, AX, TR, CF, TH, LN, CLU values through the new components, port by port. New checks:
each child's port name and order pins; the diagnostics prefixes present on an emitted RES
and the monitor.* prefix absent; chaining two children accumulates both prefixes; Frame's
AL branch count equals AN's with one line fewer per branch; Deconstruct's ten-output pin;
the icon map pins (three new keys, stress_analysis gone); the component count pin at
twenty-two.

## 10. Out of scope

The columns placement redesign (parked for Param's Diagnose readout); the Skin component
(its own spec, docs/superpowers/specs/2026-08-31-skin-design.md); any change to what the
measures compute; the getting-started rewrite.
