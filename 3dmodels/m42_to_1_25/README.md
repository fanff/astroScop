# M42 → 1.25" eyepiece

OpenSCAD adaptor ring: female M42 thread on one end, 1.25" eyepiece socket on the other.

## Features

- **Body** — outer cylinder sized for a comfortable wall around the M42 thread
- **M42 end** — female M42×0.75 (T2) thread to screw onto a male M42 nose
- **Eyepiece end** — bore for a standard 1.25" eyepiece barrel, with a stop lip so the eyepiece cannot fall through
- **Set screw** — optional radial hole to lock the eyepiece

## Mode

Customizer **Mode** → `testing` or `normal` switches overall height, thread length, eyepiece depth, and mesh density.

Thread clearance, eyepiece clearance, and set-screw size are adjustable for print fit.

## Usage

Open `m42_to_1_25.scad` in [OpenSCAD](https://openscad.org/), set **Mode** to `normal` for a final part, adjust clearances if needed, then **Export → STL**.

Print with the axis vertical; check the M42 fit on a known male T2 / M42 nose before relying on it at the telescope.
