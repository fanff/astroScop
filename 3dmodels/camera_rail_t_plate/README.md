# Camera-rail T-plate

OpenSCAD **T-shaped** plate for a camera on a bar. Same bar interface as
`scope_t_plate` and `marks_holder`, with a triangular top rail on the
crossbar and a sliding rectangle that carries a 1/4"-20 camera screw.

## Files

| File | Print / tweak |
|------|----------------|
| `camera_rail_t_plate.scad` | Plate, holder, or assembly preview |

Customizer **Output** → `part`: `plate`, `holder`, or `assembly`. Export
`plate` and `holder` as separate STLs. `assembly` is a preview of the holder
in the rail (ghost); it is not a print.

## Features

Each block is a Customizer group. Booleans under **Features** turn cuts on or
off without changing the T outline.

- **T body** — horizontal crossbar plus vertical stem. `stem_length` is how
  far the stem extends past the bar; `stem_from_center` slides the stem along Y
- **Underside rails** — two rectangular channels on the underside of the
  crossbar (`rail_length`, `rail_width`, `rail_depth`, `rail_inner_gap`)
- **Crossbar M4 taps** — two Ø3.3 mm tap-drill holes on the bar, spaced by
  `m4_tap_spacing` and centred on the bar midpoint
- **Top rail** — two 45° triangular rails on top of the crossbar, lips
  inward, open at both Y ends so the holder inserts from either end
  (`top_rail_length`, `top_rail_height`, `top_rail_shoulder`)
- **Top-rail M4 taps** — Ø3.3 mm tap-drill holes along each rail shoulder,
  spaced by `top_rail_m4_spacing`
- **Screw-head groove** — slot in the plate under the channel so a 1/4"-20
  screw head can sit and travel (`head_groove_width`, `head_groove_depth`)
- **Camera holder** — small trapezoid-sided rectangle that slides in the
  rails; Ø6.9 mm 1/4"-20 through-hole with a counterbore on the bottom for
  the screw head. Slide along Y to balance the camera

## Mode

Customizer **Mode** → `testing` or `normal`.

Switched sizes (testing → normal): plate height, underside rail depth, and
head-groove depth. Other dimensions stay shared.

## Usage

Open `camera_rail_t_plate.scad` in [OpenSCAD](https://openscad.org/). Set
**Output** → `part` to `plate`, render (F6), **Export → STL**. Repeat with
`part` = `holder`.

Print the plate flat on its underside. Print the holder on its bottom face
(counterbore up). Tap the Ø3.3 mm holes M4. Seat the holder from either end
of the top rail, put a 1/4"-20 camera screw up through the holder into the
camera, and slide to balance.
