# Marks holder

OpenSCAD **T-shaped** plate that mounts a Pi camera tracking head and a small Maksutov refractor.

## Features

- **Stem (vertical arm)** — Pi camera mount; length and Y offset toward the Maksutov are tunable
- **Crossbar (horizontal arm)** — Maksutov mount; length is tunable
- **Rounded corners** — outer tips of the T and inner fillets at the stem/crossbar junction
- **Strap deck** — lower plain plate in the open corner of the T; united with the stem and crossbar before corner rounding, with a grid of rectangular slots for straps / rubber bands
- **Pi camera mount** — two M4 clearance holes matching the existing tracking mount spacing
- **Maksutov mount** — standard camera tripod screw hole, recessed rectangular pocket in the top face; screw position is offset from the crossbar centre along Y by a tunable parameter
- **Crossbar taps** — two M4 tap-drill holes on the horizontal arm, spaced apart and centred on the bar midpoint
- **Bottom hollows** — two rectangular cavities cut from the underside of the crossbar, centred on Y, with a tunable gap between their inner walls

## Mode

Customizer **Mode** → `testing` or `normal`.

Switched sizes (testing → normal): plate height, hollow depth, strap-deck height, and strap-deck max X. Other dimensions stay shared.

## Usage

Open `marks_holder.scad` in [OpenSCAD](https://openscad.org/), adjust parameters if needed, then **Export → STL**.
