// Isolated 12V barrel-to-screw-terminal adapter
// Outside -> inside along +Y. The wall interface is the Y=0 plane.
// Negative Y is the barrel (outside the box). Positive Y is inside the box.
// All dimensions are in millimetres and live in this file.

/* [Adapter preview] */
adapter_show_sections = true;

/* [Barrel — outside] */
adapter_barrel_diameter = 10.0;
adapter_barrel_length = 9.0;

/* [Truncated pyramid — body] */
// Face against the barrel / wall (outside)
adapter_pyramid_outer_width = 11.0;
adapter_pyramid_outer_height = 11.0;
// Face toward the screw terminal (inside)
adapter_pyramid_inner_width = 14.2;
adapter_pyramid_inner_height = 12.0;
adapter_pyramid_length = 21.4;

/* [Screw terminal — inside] */
// Longer side is aligned with the pyramid inner-face width.
adapter_terminal_width = 10.3;
adapter_terminal_height = 10.1;
adapter_terminal_length = 8.0;
// How far the terminal sits back into the pyramid inner face.
adapter_terminal_overlap = 2.0;
// Shift the terminal along +Z (up) from the pyramid centreline.
adapter_terminal_z_offset = 1.0;

/* [Quality] */
adapter_fn = $preview ? 32 : 96;

function adapter_pyramid_inner_width() = adapter_pyramid_inner_width;
function adapter_pyramid_inner_height() = adapter_pyramid_inner_height;
function adapter_pyramid_length() = adapter_pyramid_length;
function adapter_terminal_overlap() = adapter_terminal_overlap;
function adapter_terminal_length() = adapter_terminal_length;
function adapter_terminal_z_offset() = adapter_terminal_z_offset;

module rectangular_frustum_y(length, outer_width, outer_height, inner_width, inner_height) {
    polyhedron(
        points = [
            [-outer_width / 2, 0, -outer_height / 2],
            [ outer_width / 2, 0, -outer_height / 2],
            [ outer_width / 2, 0,  outer_height / 2],
            [-outer_width / 2, 0,  outer_height / 2],
            [-inner_width / 2, length, -inner_height / 2],
            [ inner_width / 2, length, -inner_height / 2],
            [ inner_width / 2, length,  inner_height / 2],
            [-inner_width / 2, length,  inner_height / 2]
        ],
        faces = [
            [0, 3, 2, 1],
            [4, 5, 6, 7],
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7]
        ],
        convexity = 4
    );
}

module adapter_barrel(clearance = 0) {
    translate([0, -adapter_barrel_length - clearance, 0])
        rotate([-90, 0, 0])
            cylinder(
                h = adapter_barrel_length + 2 * clearance,
                d = adapter_barrel_diameter + 2 * clearance,
                $fn = adapter_fn
            );
}

module adapter_pyramid(clearance = 0) {
    translate([0, -clearance, 0])
        rectangular_frustum_y(
            adapter_pyramid_length + 2 * clearance,
            adapter_pyramid_outer_width + 2 * clearance,
            adapter_pyramid_outer_height + 2 * clearance,
            adapter_pyramid_inner_width + 2 * clearance,
            adapter_pyramid_inner_height + 2 * clearance
        );
}

module adapter_terminal(clearance = 0) {
    translate([
        -adapter_terminal_width / 2 - clearance,
        adapter_pyramid_length - adapter_terminal_overlap,
        -adapter_terminal_height / 2 - clearance + adapter_terminal_z_offset
    ])
        cube([
            adapter_terminal_width + 2 * clearance,
            adapter_terminal_length + 2 * clearance,
            adapter_terminal_height + 2 * clearance
        ]);
}

// Full physical adapter. clearance grows every face for use as a box cutter.
module adapter_component(clearance = 0) {
    if (adapter_show_sections && clearance == 0) {
        color("Silver")
            adapter_barrel();
        color("DimGray")
            adapter_pyramid();
        color("ForestGreen")
            adapter_terminal();
    } else {
        union() {
            adapter_barrel(clearance);
            adapter_pyramid(clearance);
            adapter_terminal(clearance);
        }
    }
}

adapter_component();
