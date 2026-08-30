# Motor board box

Parametric OpenSCAD enclosure for the Raspberry Pi motor-control board and its
power and motor wiring.

## Features

- **Bottom box** — rounded enclosure with configurable walls, floor, and internal clearances
- **Board grooves** — full-length triangular ribs under both long edges, tapering toward the floor, plus short snap-fit tabs above the board
- **Cable exits** — separate features for the two flat motor wires and the USB wire
- **Power adaptor pocket** — floor block hollowed by the isolated adaptor in `barrel_adapter.scad`, opening through the end wall
- **Strap loops** — three C-shaped loops on each long wall, with ramps from the wall so they print without hanging
- **End-wall vents** — vertical slots through the short wall opposite the power adaptor
- **Screw posts** — corner posts intended to be tapped for the cover screws
- **Cover** — separate printable plate with clearance holes, a locating lip, and radial airflow slots

Box dimensions live in `motor_board_box.scad`. Adaptor shape dimensions live
only in `barrel_adapter.scad`.

## Part selection

Use the OpenSCAD Customizer **Output** section:

- `bottom` — render the enclosure body for export
- `cover` — render the cover in its print orientation
- `assembly` — preview the closed enclosure

Open `barrel_adapter.scad` on its own to iterate the 12V adaptor. The box
imports only its modules (`use`) and hollows that shape through the end wall.

`show_board_preview` and `show_adapter_preview` are ghost overlays in
**Preview** (F5) on `bottom` and `assembly`. They do not appear in a full
**Render** (F6) and are not part of an exported STL.

Individual feature switches can hide the grooves, cable exits, adaptor pocket,
strap loops, screw mounts, cover lip, cover vents, or end-wall vents during
development.

## Usage

Open `motor_board_box.scad` in [OpenSCAD](https://openscad.org/), select the
required part, render it, then use **Export → STL**. Export `bottom` and `cover`
separately.

Adaptor shape parameters live only in `barrel_adapter.scad`. Placement of that
pocket on the box lives in `motor_board_box.scad`.
