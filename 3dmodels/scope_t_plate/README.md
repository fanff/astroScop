# Scope T-plate

OpenSCAD **T-shaped** mounting plate for a scope on a bar. Same geometry
family as `marks_holder`, with each feature named and switchable.

## Features

Each block is a Customizer group. Booleans under **Features** turn cuts on or
off without changing the T outline.

- **T body** — horizontal crossbar plus vertical stem. `stem_length` is how
  far the stem extends past the bar; `stem_from_center` slides the stem along Y
- **Rails** — two rectangular channels on the underside of the crossbar
  (`rail_length`, `rail_width`, `rail_depth`, `rail_inner_gap`)
- **Crossbar M4 taps** — two Ø3.3 mm tap-drill holes on the bar, spaced by
  `m4_tap_spacing` and centred on the bar midpoint
- **Deck** — thinner filling plate in the open T corner, united with the T
  before corner rounding, with a 10×10 mm grid of Ø2.5 mm M3 tap holes
  (`deck_hole_spacing`, `m3_tap_diameter`)
- **Scope mount** (optional) — two 1/4"-20 clearance holes on the crossbar,
  mirrored about the plate centre along Y; `scope_screw_from_center` is the
  offset of each hole from that centre
- **Pi camera mount** (optional) — M3 through-hole on the stem plus an M3-wide
  arc slot centred on that hole so the camera can pivot; `pi_arc_angle` is the
  total sweep, `m3_clearance_diameter` is the pass-through size

## Mode

Customizer **Mode** → `testing` or `normal`.

Switched sizes (testing → normal): plate height, deck height, and
deck max X. Other dimensions stay shared.

## Usage

Open `scope_t_plate.scad` in [OpenSCAD](https://openscad.org/), adjust
parameters if needed, then **Export → STL**.
