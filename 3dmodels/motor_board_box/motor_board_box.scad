// Motor board enclosure
// Two printable parts: a board-holding bottom box and a screw-fastened cover.
// All dimensions are in millimetres and intentionally live in this file.
// The 12V adapter shape lives in barrel_adapter.scad (`use` imports modules only).
use <barrel_adapter.scad>

/* [Output] */
part = "assembly"; // [bottom, cover, assembly]
show_board_preview = true;
show_adapter_preview = true;

/* [Feature switches] */
board_grooves_enable = true;
flat_wire_notches_enable = true;
usb_notch_enable = true;
adapter_pocket_enable = true;
adapter_holder_enable = true;
strap_loops_enable = true;
screw_mounts_enable = true;
cover_lip_enable = true;
cover_vents_enable = true;
xminus_vents_enable = true;

/* [Board and clearances] */
board_length = 70.0;
board_width = 50.0;
board_thickness = 1.6;
clearance_below_board = 10.0;
clearance_above_board = 27.0;
board_end_margin_x_minus = 10.0;
board_end_margin_x_plus = 40.0;
board_side_gap = 1.2;
board_vertical_fit = 0.25;

/* [Box] */
wall_thickness = 1.6;
floor_thickness = 2.4;
box_corner_radius = 4.0;

/* [Board edge grooves] */
groove_support_depth = 1.0;
groove_tab_depth = 1.0;
groove_tab_height = 5.0;
groove_tab_length = 9.0;
groove_tab_positions = [0.50]; // fractions along board length

/* [Cover] */
cover_thickness = 2.4;
cover_lip_depth = 3.0;
cover_lip_thickness = 1.2;
cover_fit_clearance = 0.25;
cover_lip_wire_clearance = 0.6;

/* [Cover airflow rays] */
cover_vent_count = 12;
cover_vent_width = 2.2;
cover_vent_inner_radius = 6.0;
cover_vent_outer_margin = 3.0;

/* [M3 cover screws] */
m3_clearance_diameter = 3.4;
m3_tap_diameter = 2.5;
screw_post_diameter = 7.0;
screw_post_edge_offset = screw_post_diameter / 2;
screw_tap_depth = 20.0;

/* [Flat wire notches] */
flat_notch_width = 6.0;
flat_notch_depth = 1.3;
flat_notch_board_fractions = [0.35, 0.65];

/* [USB wire notch] */
usb_notch_diameter = 3.0;
usb_notch_from_x_plus = 12.0;

/* [12V adapter placement] */
// Reference plane: inside face of the X+ end wall. The barrel extends outward.
adapter_from_y_plus = 6.0;
adapter_x_shift = -5.0;
adapter_floor_lift = 0.0;
adapter_fit_clearance = 0.25;

/* [12V adapter holder] */
adapter_holder_side_margin = 2.0;
adapter_holder_end_margin = -2.0;
adapter_holder_height_fraction = 0.70;

/* [Strap loops] */
strap_width = 12.0;
strap_thickness = 1.2;
strap_fit_clearance = 0.5;
strap_loop_x_fractions = [0.22, 0.50, 0.78];
strap_loop_side_width = 2.0;
strap_loop_bridge_thickness = 2.0;
strap_loop_bridge_height = 5.0;
strap_loop_z_fraction = 0.62;
strap_loop_ramp_extra = 4.0;

/* [X- wall vents] */
xminus_vent_count = 5;
xminus_vent_width = 2.0;
xminus_vent_height = 20.0;
xminus_vent_bottom_z = 8.0;
xminus_vent_y_margin = 10.0;

/* [Quality] */
$fn = $preview ? 32 : 96;

epsilon = 0.05;

inner_length =
    board_end_margin_x_minus + board_length + board_end_margin_x_plus;
inner_width = board_width + 2 * board_side_gap;
inner_height = clearance_below_board + board_thickness + clearance_above_board;

box_length = inner_length + 2 * wall_thickness;
box_width = inner_width + 2 * wall_thickness;
box_height = floor_thickness + inner_height;

board_x = wall_thickness + board_end_margin_x_minus;
board_y = wall_thickness + board_side_gap;
board_bottom_z = floor_thickness + clearance_below_board;
board_top_z = board_bottom_z + board_thickness;

adapter_wall_x = box_length - wall_thickness + adapter_x_shift;
adapter_center_y =
    box_width - wall_thickness -
    adapter_from_y_plus -
    adapter_pyramid_inner_width() / 2;
adapter_center_z =
    floor_thickness +
    adapter_floor_lift +
    adapter_pyramid_inner_height() / 2;
adapter_inner_end_x =
    adapter_wall_x -
    (
        adapter_pyramid_length() -
        adapter_terminal_overlap() +
        adapter_terminal_length() +
        adapter_fit_clearance
    );
adapter_body_height =
    adapter_pyramid_inner_height() + adapter_terminal_z_offset();
adapter_holder_top_z =
    floor_thickness +
    adapter_floor_lift +
    adapter_holder_height_fraction * adapter_body_height;

assert(
    board_length > 0 && board_width > 0 && board_thickness > 0,
    "Board dimensions must be positive"
);
assert(
    clearance_below_board > 0,
    "Bottom clearance must be positive"
);
assert(
    clearance_above_board > cover_lip_depth,
    "Top clearance must exceed the cover lip depth"
);
assert(
    wall_thickness > 0 && floor_thickness > 0,
    "Wall and floor thicknesses must be positive"
);
assert(
    box_corner_radius >= wall_thickness &&
    2 * box_corner_radius < min(box_length, box_width),
    "Box corner radius is invalid"
);
assert(
    groove_support_depth > 0 && groove_support_depth <= board_width / 2,
    "Board groove support depth is invalid"
);
assert(
    groove_tab_depth > 0 &&
    groove_tab_height > 0 &&
    groove_tab_length > 0,
    "Board retaining-tab dimensions must be positive"
);
assert(
    cover_fit_clearance >= 0 &&
    cover_lip_thickness > 0 &&
    cover_lip_depth > 0,
    "Cover lip dimensions are invalid"
);
assert(
    cover_vent_count == floor(cover_vent_count) &&
    cover_vent_count >= 2 &&
    cover_vent_width > 0 &&
    cover_vent_inner_radius >= 0 &&
    cover_vent_outer_margin >= 0,
    "Cover vent parameters are invalid"
);
assert(
    m3_tap_diameter < screw_post_diameter - 2,
    "M3 tapping hole leaves too little material in the post"
);
assert(
    screw_tap_depth > 0 && screw_tap_depth < box_height - floor_thickness,
    "Screw tap depth must remain above the box floor"
);
assert(
    board_x > screw_post_edge_offset + screw_post_diameter / 2,
    "Increase board_end_margin_x_minus to clear the X- screw posts"
);
assert(
    board_x + board_length <
        box_length - screw_post_edge_offset - screw_post_diameter / 2,
    "Increase board_end_margin_x_plus to clear the X+ screw posts"
);
assert(
    adapter_center_y - adapter_pyramid_inner_width() / 2 > wall_thickness &&
    adapter_center_y + adapter_pyramid_inner_width() / 2 <
        box_width - wall_thickness,
    "12V adapter does not fit along the X+ wall"
);
assert(
    adapter_center_z - adapter_pyramid_inner_height() / 2 >= floor_thickness &&
    adapter_holder_height_fraction > 0 &&
    adapter_holder_height_fraction < 1 &&
    adapter_holder_top_z < box_height,
    "12V adapter does not fit vertically in the box"
);
assert(
    adapter_terminal_overlap() >= 0 &&
    adapter_terminal_overlap() < adapter_terminal_length(),
    "12V terminal overlap must be smaller than its length"
);
assert(
    adapter_inner_end_x > board_x + board_length,
    "Increase board_end_margin_x_plus to clear the 12V adapter body"
);
assert(
    usb_notch_from_x_plus > usb_notch_diameter / 2 &&
    usb_notch_from_x_plus <
        board_end_margin_x_plus - usb_notch_diameter / 2,
    "USB notch must remain inside the X+ clearance area"
);

strap_loop_protrusion =
    strap_thickness + strap_fit_clearance + strap_loop_bridge_thickness;
strap_loop_total_width = strap_width + 2 * strap_loop_side_width;
strap_loop_z0 =
    box_height * strap_loop_z_fraction - strap_loop_bridge_height / 2;
strap_loop_ramp_z =
    strap_loop_z0 - strap_loop_protrusion - strap_loop_ramp_extra;

assert(
    strap_loop_z0 > 0 &&
    strap_loop_z0 + strap_loop_bridge_height < box_height,
    "Strap loops must stay within the box height"
);
assert(
    strap_loop_ramp_z > 0,
    "Strap loop ramps would go below the box floor"
);

for (position = strap_loop_x_fractions) {
    strap_center_x = box_length * position;

    assert(
        position > 0 && position < 1 &&
        strap_center_x - strap_loop_total_width / 2 > 0 &&
        strap_center_x + strap_loop_total_width / 2 < box_length,
        "A strap loop lies outside the long wall"
    );
}

assert(
    xminus_vent_count == floor(xminus_vent_count) &&
    xminus_vent_count >= 1 &&
    xminus_vent_width > 0 &&
    xminus_vent_height > 0 &&
    xminus_vent_bottom_z > 0 &&
    xminus_vent_bottom_z + xminus_vent_height < box_height &&
    xminus_vent_y_margin > 0 &&
    2 * xminus_vent_y_margin + xminus_vent_count * xminus_vent_width <
        box_width,
    "X- wall vents do not fit"
);

module rounded_rect_prism(length, width, height, radius) {
    assert(radius > 0, "Rounded rectangle radius must be positive");
    hull() {
        for (x = [radius, length - radius])
            for (y = [radius, width - radius])
                translate([x, y, 0])
                    cylinder(h = height, r = radius);
    }
}

module empty_box_shell() {
    inner_radius = max(epsilon, box_corner_radius - wall_thickness);

    difference() {
        rounded_rect_prism(
            box_length,
            box_width,
            box_height,
            box_corner_radius
        );

        translate([wall_thickness, wall_thickness, floor_thickness])
            rounded_rect_prism(
                inner_length,
                inner_width,
                inner_height + epsilon,
                inner_radius
            );
    }
}

module board_edge_grooves() {
    tab_z = board_top_z + board_vertical_fit;

    // Full-length supports: wide under the board, tapering toward -Z to the floor.
    translate([board_x, 0, 0])
        triangular_prism_x(
            board_length,
            wall_thickness - epsilon,
            0,
            wall_thickness - epsilon,
            board_bottom_z,
            board_y + groove_support_depth,
            board_bottom_z
        );

    translate([board_x, 0, 0])
        triangular_prism_x(
            board_length,
            box_width - wall_thickness + epsilon,
            0,
            box_width - wall_thickness + epsilon,
            board_bottom_z,
            board_y + board_width - groove_support_depth,
            board_bottom_z
        );

    // One triangular wedge per edge flexes during insertion and retains the board.
    for (position = groove_tab_positions) {
        tab_x = board_x + position * board_length - groove_tab_length / 2;

        translate([tab_x, 0, 0])
            triangular_prism_x(
                groove_tab_length,
                wall_thickness - epsilon,
                tab_z,
                board_y + groove_tab_depth,
                tab_z,
                wall_thickness - epsilon,
                tab_z + groove_tab_height
            );

        translate([tab_x, 0, 0])
            triangular_prism_x(
                groove_tab_length,
                box_width - wall_thickness + epsilon,
                tab_z,
                board_y + board_width - groove_tab_depth,
                tab_z,
                box_width - wall_thickness + epsilon,
                tab_z + groove_tab_height
            );
    }
}

// Triangular prism extruded along +X.
module triangular_prism_x(length, y0, z0, y1, z1, y2, z2) {
    polyhedron(
        points = [
            [0,      y0, z0],
            [0,      y1, z1],
            [0,      y2, z2],
            [length, y0, z0],
            [length, y1, z1],
            [length, y2, z2]
        ],
        faces = [
            [0, 2, 1],
            [3, 4, 5],
            [0, 1, 4, 3],
            [1, 2, 5, 4],
            [2, 0, 3, 5]
        ],
        convexity = 2
    );
}

module at_screw_positions() {
    for (x = [screw_post_edge_offset, box_length - screw_post_edge_offset])
        for (y = [screw_post_edge_offset, box_width - screw_post_edge_offset])
            translate([x, y, 0])
                children();
}

module screw_posts() {
    intersection() {
        union() {
            at_screw_positions()
                cylinder(
                    h = box_height,
                    d = screw_post_diameter
                );
        }

        // Keep the posts inside the outer rounded profile.
        rounded_rect_prism(
            box_length,
            box_width,
            box_height,
            box_corner_radius
        );
    }
}

module screw_tap_cutters() {
    at_screw_positions()
        translate([0, 0, box_height - screw_tap_depth])
            cylinder(
                h = screw_tap_depth + epsilon,
                d = m3_tap_diameter
            );
}

module flat_wire_notch_cutters() {
    for (position = flat_notch_board_fractions)
        translate([
            board_x + board_length * position - flat_notch_width / 2,
            box_width - wall_thickness - epsilon,
            box_height - flat_notch_depth
        ])
            cube([
                flat_notch_width,
                wall_thickness + 2 * epsilon,
                flat_notch_depth + epsilon
            ]);
}

module usb_notch_cutter() {
    center_x = box_length - wall_thickness - usb_notch_from_x_plus;
    center_z = box_height - usb_notch_diameter / 2;

    translate([
        center_x,
        box_width + epsilon,
        center_z
    ])
        rotate([90, 0, 0])
            cylinder(
                h = wall_thickness + 2 * epsilon,
                d = usb_notch_diameter
            );

    // Open the circular passage through the top rim.
    translate([
        center_x - usb_notch_diameter / 2,
        box_width - wall_thickness - epsilon,
        center_z
    ])
        cube([
            usb_notch_diameter,
            wall_thickness + 2 * epsilon,
            usb_notch_diameter
        ]);
}

module placed_adapter(clearance = 0) {
    translate([
        adapter_wall_x,
        adapter_center_y,
        adapter_center_z
    ])
        rotate([0, 0, 90])
            adapter_component(clearance);
}

module adapter_holder() {
    holder_width =
        adapter_pyramid_inner_width() + 2 * adapter_holder_side_margin;
    holder_y = adapter_center_y - holder_width / 2;
    holder_x = adapter_inner_end_x - adapter_holder_end_margin;
    holder_length = box_length - holder_x;

    translate([
        holder_x,
        max(wall_thickness, holder_y),
        0
    ])
        cube([
            holder_length,
            min(holder_width, inner_width),
            adapter_holder_top_z
        ]);
}

module strap_loop(side = "near", center_x = box_length / 2) {
    x0 = center_x - strap_loop_total_width / 2;
    x_sides = [x0, x0 + strap_loop_total_width - strap_loop_side_width];

    if (side == "near") {
        for (x = x_sides) {
            translate([x, -strap_loop_protrusion, strap_loop_z0])
                cube([
                    strap_loop_side_width,
                    strap_loop_protrusion + epsilon,
                    strap_loop_bridge_height
                ]);

            // Ramp from the wall up to the hanging side post.
            translate([x, 0, 0])
                triangular_prism_x(
                    strap_loop_side_width,
                    epsilon,
                    strap_loop_ramp_z,
                    epsilon,
                    strap_loop_z0,
                    -strap_loop_protrusion,
                    strap_loop_z0
                );
        }

        translate([x0, -strap_loop_protrusion, strap_loop_z0])
            cube([
                strap_loop_total_width,
                strap_loop_bridge_thickness,
                strap_loop_bridge_height
            ]);
    } else {
        for (x = x_sides) {
            translate([x, box_width - epsilon, strap_loop_z0])
                cube([
                    strap_loop_side_width,
                    strap_loop_protrusion + epsilon,
                    strap_loop_bridge_height
                ]);

            translate([x, 0, 0])
                triangular_prism_x(
                    strap_loop_side_width,
                    box_width - epsilon,
                    strap_loop_ramp_z,
                    box_width - epsilon,
                    strap_loop_z0,
                    box_width + strap_loop_protrusion,
                    strap_loop_z0
                );
        }

        translate([
            x0,
            box_width + strap_loop_protrusion - strap_loop_bridge_thickness,
            strap_loop_z0
        ])
            cube([
                strap_loop_total_width,
                strap_loop_bridge_thickness,
                strap_loop_bridge_height
            ]);
    }
}

module strap_loops() {
    for (position = strap_loop_x_fractions) {
        center_x = box_length * position;
        strap_loop("near", center_x);
        strap_loop("far", center_x);
    }
}

module xminus_vent_cutters() {
    usable_y = box_width - 2 * xminus_vent_y_margin;
    step = usable_y / (xminus_vent_count + 1);

    for (i = [1 : xminus_vent_count]) {
        y0 = xminus_vent_y_margin + i * step - xminus_vent_width / 2;
        translate([
            -epsilon,
            y0,
            xminus_vent_bottom_z
        ])
            cube([
                wall_thickness + 2 * epsilon,
                xminus_vent_width,
                xminus_vent_height
            ]);
    }
}

module bottom_box() {
    difference() {
        union() {
            empty_box_shell();

            if (board_grooves_enable)
                board_edge_grooves();

            if (screw_mounts_enable)
                screw_posts();

            if (strap_loops_enable)
                strap_loops();

            if (adapter_holder_enable)
                adapter_holder();
        }

        if (screw_mounts_enable)
            screw_tap_cutters();

        if (flat_wire_notches_enable)
            flat_wire_notch_cutters();

        if (usb_notch_enable)
            usb_notch_cutter();

        if (adapter_pocket_enable)
            placed_adapter(adapter_fit_clearance);

        if (xminus_vents_enable)
            xminus_vent_cutters();
    }
}

module cover_lip() {
    lip_outer_length = inner_length - 2 * cover_fit_clearance;
    lip_outer_width = inner_width - 2 * cover_fit_clearance;
    lip_outer_radius = max(
        epsilon,
        box_corner_radius - wall_thickness - cover_fit_clearance
    );
    lip_inner_length = lip_outer_length - 2 * cover_lip_thickness;
    lip_inner_width = lip_outer_width - 2 * cover_lip_thickness;
    lip_inner_radius = max(epsilon, lip_outer_radius - cover_lip_thickness);
    lip_x = wall_thickness + cover_fit_clearance;
    lip_y = wall_thickness + cover_fit_clearance;

    difference() {
        translate([lip_x, lip_y, cover_thickness - epsilon])
            difference() {
                rounded_rect_prism(
                    lip_outer_length,
                    lip_outer_width,
                    cover_lip_depth + epsilon,
                    lip_outer_radius
                );

                translate([
                    cover_lip_thickness,
                    cover_lip_thickness,
                    -epsilon
                ])
                    rounded_rect_prism(
                        lip_inner_length,
                        lip_inner_width,
                        cover_lip_depth + 3 * epsilon,
                        lip_inner_radius
                    );
            }

        // Keep the locating lip clear of the four corner posts.
        at_screw_positions()
            translate([0, 0, cover_thickness - epsilon])
                cylinder(
                    h = cover_lip_depth + 2 * epsilon,
                    d = screw_post_diameter + 2 * cover_fit_clearance
                );

        // Assembly flips the cover, so this near-Y lip sits on the notched Y+ wall.
        cover_lip_wire_cutters(lip_y);
    }
}

module cover_lip_wire_gap(center_x, gap_width, lip_y) {
    translate([
        center_x - gap_width / 2,
        lip_y - epsilon,
        cover_thickness - epsilon
    ])
        cube([
            gap_width,
            cover_lip_thickness + 2 * epsilon,
            cover_lip_depth + 2 * epsilon
        ]);
}

module cover_lip_wire_cutters(lip_y) {
    if (flat_wire_notches_enable)
        for (position = flat_notch_board_fractions)
            cover_lip_wire_gap(
                board_x + board_length * position,
                flat_notch_width + 2 * cover_lip_wire_clearance,
                lip_y
            );

    if (usb_notch_enable)
        cover_lip_wire_gap(
            box_length - wall_thickness - usb_notch_from_x_plus,
            usb_notch_diameter + 2 * cover_lip_wire_clearance,
            lip_y
        );
}

module cover_vent_cutters() {
    outer_radius = min(
        inner_length / 2 - cover_lip_thickness - cover_vent_outer_margin,
        inner_width / 2 - cover_lip_thickness - cover_vent_outer_margin
    );
    slot_length = outer_radius - cover_vent_inner_radius;
    cutter_h = cover_thickness + cover_lip_depth + 2 * epsilon;

    assert(
        slot_length > cover_vent_width,
        "Cover vents do not fit inside the lip"
    );

    translate([box_length / 2, box_width / 2, -epsilon])
        for (i = [0 : cover_vent_count - 1])
            rotate([0, 0, i * 360 / cover_vent_count])
                hull() {
                    translate([cover_vent_inner_radius, 0, 0])
                        cylinder(h = cutter_h, d = cover_vent_width);
                    translate([outer_radius, 0, 0])
                        cylinder(h = cutter_h, d = cover_vent_width);
                }
}

// Printable orientation: broad cover plate on the build surface, lip upward.
module cover() {
    difference() {
        union() {
            rounded_rect_prism(
                box_length,
                box_width,
                cover_thickness,
                box_corner_radius
            );

            if (cover_lip_enable)
                cover_lip();
        }

        if (screw_mounts_enable)
            at_screw_positions()
                translate([0, 0, -epsilon])
                    cylinder(
                        h = cover_thickness + cover_lip_depth + 2 * epsilon,
                        d = m3_clearance_diameter
                    );

        if (cover_vents_enable)
            cover_vent_cutters();
    }
}

module board_preview() {
    translate([board_x, board_y, board_bottom_z])
        cube([board_length, board_width, board_thickness]);
}

module assembly() {
    bottom_box();

    // Turn the print-oriented cover over and seat its lip inside the box.
    translate([0, box_width, box_height + cover_thickness])
        rotate([180, 0, 0])
            cover();

    preview_inserts();
}

module preview_inserts() {
    if (show_board_preview)
        %color("ForestGreen", 0.75)
            board_preview();

    if (show_adapter_preview)
        %color("DarkSlateGray", 0.75)
            placed_adapter();
}

if (part == "bottom") {
    bottom_box();
    preview_inserts();
} else if (part == "cover") {
    cover();
} else if (part == "assembly") {
    assembly();
} else {
    assert(false, "Unknown part selection");
}
