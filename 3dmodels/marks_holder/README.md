# Marks holder

OpenSCAD **T-shaped** plate that mounts a Pi camera tracking head and a small Maksutov refractor.

## Features

- **Stem (vertical arm)** — Pi camera mount; length is tunable
- **Crossbar (horizontal arm)** — Maksutov mount; length is tunable
- **Rounded corners** — outer tips of the T and inner fillets at the stem/crossbar junction
- **Pi camera mount** — two M3 clearance holes matching the existing tracking mount spacing
- **Maksutov mount** — standard camera tripod screw hole, recessed rectangular pocket in the top face; screw position is offset from the crossbar centre along Y by a tunable parameter
- **Crossbar taps** — two M4 tap-drill holes on the horizontal arm, spaced apart and centred on the bar midpoint
- **Bottom hollows** — two rectangular cavities cut from the underside of the crossbar, centred on Y, with a tunable gap between their inner walls

Arm lengths, widths, plate height, corner radii, mount positions, and clearances are adjustable in the OpenSCAD Customizer.

## Usage

Open `marks_holder.scad` in [OpenSCAD](https://openscad.org/), adjust parameters if needed, then **Export → STL**.
