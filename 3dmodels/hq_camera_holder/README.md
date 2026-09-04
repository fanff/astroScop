# HQ camera holder

OpenSCAD enclosure that screws a Raspberry Pi High Quality Camera (CS-mount)
onto a telescope nosepiece, or leaves the CS mount free for a CS lens.

The **cover is frozen**. Already-printed caps still fit every body. Do not
change plate outline, cover walls, or screw spacing in
`hq_camera_holder_lib.scad`.

## Files

| File | Print / tweak |
|------|----------------|
| `cover.scad` | Back cap (unchanged geometry) |
| `body_1_25.scad` | 1.25" nosepiece |
| `body_2.scad` | Short, open 2" nosepiece (near focus) |
| `body_open.scad` | Plate only — CS threads free for a CS lens |
| `hq_camera_holder_lib.scad` | Shared modules; not a part |

Open the file for the part you want in [OpenSCAD](https://openscad.org/),
render (F6), then **Export → STL**.

Body files also have an **assembly** Customizer option: preview of that body
plus the cover. `show_camera_preview` is a ghost overlay in **Preview** (F5)
only; it is not in a full render or STL.

## Features

- **1.25" nosepiece** — barrel for a standard focuser, chamfer, optional
  safety groove, hulled into the camera plate
- **2" nosepiece** — ~12 mm stub, 50.8 mm OD minus print clearance, inner
  bore wider than the CS clearance (no 1.25"-style tunnel)
- **Open CS** — no barrel; CS-mount sticks through the plate; corner bosses
  take the cover screws
- **CS-mount hollow** — clearance for the aluminium CS-mount, tripod-lug
  slot on the −Y side
- **Camera plate** — PCB face at z = 0, four M2.5 tap holes on the 30 mm
  square
- **Back cap** — shallow box with a fat rim on the plate at z = 0; M2.5
  through-holes line up with body taps; ribbon slot on +Y

Camera geometry follows the official HQ CS-mount drawing: 38 mm PCB, Ø2.5
holes on a 30 mm square, CS-mount about Ø36 mm. Barrel ODs use the same
print-clearance convention as the other telescope adaptors in this folder.

## Usage

The body lies on its flat camera face with the nosepiece (if any) pointing
+Z. Print the cover outer-face down, cavity up.

Seat the HQ camera CS-mount through the plate (tripod lug toward −Y), fasten
with four M2.5 screws, route the ribbon out the +Y slot, then close the cap
with M2.5 screws into the plate. Body holes are Ø2.1 mm, ready to tap M2.5.

If a nosepiece is tight or loose in the focuser, change `outer_clearance` in
that body file. If the CS-mount is snug, change `cs_mount_clearance` in the
lib (that affects every body, not the cover).
