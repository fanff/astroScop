// Shared HQ camera holder geometry.
// Cover / plate / screw numbers are frozen so existing printed covers still fit.
// All dimensions are in millimetres.
// This file has no top-level part; include it from cover.scad or a body file.

/* [HQ camera] */
pcb_size = 38.0;
pcb_thickness = 1.5;
pcb_corner_radius = 3.0;
// M2.5 holes on a square, centred on the optical axis
hole_spacing = 30.0;
// Aluminium CS-mount cylinder on the sensor side of the PCB
cs_mount_diameter = 36.0;
cs_mount_clearance = 0.8;
// From PCB face to CS-mount front (official CS drawing ~10.16)
cs_mount_height = 10.2;

/* [Tripod lug on the CS mount] */
tripod_lug_enable = true;
tripod_lug_width = 12.0;
tripod_lug_extra_radius = 6.0;

/* [Plate — XY frozen to match printed covers] */
plate_thickness = 4.0;
box_size = 60.0;
box_corner_radius = 8.0;

/* [Cover — frozen; do not change] */
cover_thickness = 2.4;
cover_wall = 10.0;
cover_inner_height = 8.0;
cover_boss_diameter = 9.0;

/* [Screws — all M2.5 tap] */
screw_mounts_enable = true;
m25_tap_diameter = 2.1;
m25_clearance_diameter = 2.8;
m25_tap_depth = 12.0;

/* [Cover side M3 taps] */
side_taps_enable = true;
side_taps_count = 5;
side_taps_spacing = 10.0;
m3_tap_diameter = 2.5;
m3_tap_depth = 20.0;

/* [Ribbon slot] */
ribbon_slot_enable = true;
ribbon_slot_width = 18.0;
ribbon_slot_height = 2.2;

/* [Quality] */
$fn = $preview ? 48 : 96;

epsilon = 0.05;

// Ribbon leaves at +Y; CS-mount tripod lug is cut on the opposite side (-Y).
ribbon_angle = 0;
tripod_lug_angle = 180;

cs_bore = cs_mount_diameter + cs_mount_clearance;
cs_bore_height = cs_mount_height + 0.8;

inner_size = box_size - 2 * cover_wall;
// Through-holes sit in the middle of the cover lip, same XY as the body taps.
cover_hole_spacing = inner_size + cover_wall;

assert(cs_bore < hole_spacing * sqrt(2) - m25_tap_diameter - 2,
    "CS bore collides with the M2.5 holes; reduce cs_mount_clearance");
assert(cs_bore < box_size - 4, "CS bore does not fit inside the plate");
assert(
    box_corner_radius > 0 &&
    2 * box_corner_radius < box_size,
    "Box corner radius is invalid"
);
assert(
    cover_wall >= cover_boss_diameter,
    "Cover lip must be at least as fat as the screw bosses"
);
assert(
    inner_size > pcb_size + 1.5,
    "Cover cavity does not fit the PCB; increase box_size or reduce cover_wall"
);
assert(
    cover_hole_spacing / 2 - cover_boss_diameter / 2 > pcb_size / 2,
    "Cover bosses would hit the PCB"
);
assert(
    cover_hole_spacing / 2 + m25_clearance_diameter / 2 < box_size / 2 - 0.8,
    "Cover screw holes fall outside the plate"
);
assert(
    ribbon_slot_width > 0 &&
    ribbon_slot_width < inner_size &&
    ribbon_slot_height > 0 &&
    ribbon_slot_height < cover_inner_height + cover_thickness,
    "Ribbon slot does not fit in the cover"
);
assert(
    !side_taps_enable || (
        side_taps_count >= 1 &&
        side_taps_spacing > m3_tap_diameter &&
        m3_tap_depth > 0
    ),
    "Cover side M3 taps are invalid"
);
assert(
    !side_taps_enable ||
        cover_thickness + cover_inner_height > m3_tap_diameter + 2,
    "Cover is too shallow for side M3 taps"
);
assert(
    !side_taps_enable ||
        (side_taps_count - 1) * side_taps_spacing + m3_tap_diameter
            < box_size - 2 * box_corner_radius,
    "Side M3 taps do not fit on the cover face"
);

module rounded_rect_prism(size_x, size_y, height, radius) {
    assert(radius > 0, "Rounded rectangle radius must be positive");
    hull() {
        for (sx = [-1, 1], sy = [-1, 1])
            translate([
                sx * (size_x / 2 - radius),
                sy * (size_y / 2 - radius),
                0
            ])
                cylinder(h = height, r = radius);
    }
}

module at_camera_holes() {
    for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * hole_spacing / 2, sy * hole_spacing / 2, 0])
            children();
}

module at_cover_screws() {
    for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * cover_hole_spacing / 2, sy * cover_hole_spacing / 2, 0])
            children();
}

module plate_blank() {
    rounded_rect_prism(
        box_size,
        box_size,
        plate_thickness,
        box_corner_radius
    );
}

module barrel_blank(z0, length, od) {
    translate([0, 0, z0])
        cylinder(h = length, d = od);
}

// Hull the plate into the barrel so they are one solid.
module plate_barrel_join(z0, join_length, od) {
    hull() {
        plate_blank();

        translate([0, 0, z0])
            cylinder(h = join_length, d = od);
    }
}

module nosepiece_body_solid(z0, length, od, join_length) {
    union() {
        plate_blank();
        plate_barrel_join(z0, join_length, od);
        barrel_blank(z0, length, od);
    }
}

module nosepiece_optical_path(barrel_id, barrel_z1, taper_length) {
    // CS-mount clearance only as far as the metal actually goes.
    translate([0, 0, -epsilon])
        cylinder(h = cs_bore_height + epsilon, d = cs_bore);

    translate([0, 0, cs_bore_height - epsilon])
        cylinder(
            h = taper_length + 2 * epsilon,
            d1 = cs_bore,
            d2 = barrel_id
        );

    translate([0, 0, cs_bore_height + taper_length - epsilon])
        cylinder(
            h = barrel_z1 - (cs_bore_height + taper_length) + 2 * epsilon,
            d = barrel_id
        );
}

module cs_plate_bore() {
    translate([0, 0, -epsilon])
        cylinder(h = plate_thickness + 2 * epsilon, d = cs_bore);
}

module tripod_lug_cutter() {
    if (tripod_lug_enable) {
        lug_r = cs_bore / 2 + tripod_lug_extra_radius;

        rotate([0, 0, tripod_lug_angle])
            translate([-tripod_lug_width / 2, 0, -epsilon])
                cube([
                    tripod_lug_width,
                    lug_r,
                    cs_bore_height + 2 * epsilon
                ]);
    }
}

module barrel_chamfers(z1, chamfer, od, id) {
    translate([0, 0, z1 - chamfer])
        cylinder(
            h = chamfer + epsilon,
            d1 = id,
            d2 = id + 2 * chamfer
        );

    translate([0, 0, z1 - chamfer])
        difference() {
            cylinder(
                h = chamfer + epsilon,
                d = od + 2
            );
            cylinder(
                h = chamfer + 2 * epsilon,
                d1 = od + 2 * epsilon,
                d2 = od - 2 * chamfer
            );
        }
}

module safety_groove_cut(z1, from_end, width, depth, od) {
    translate([0, 0, z1 - from_end - width])
        rotate_extrude(convexity = 4)
            translate([od / 2 - depth, 0, 0])
                square(
                    [depth + 1, width],
                    center = false
                );
}

module cover_screw_bosses(height) {
    if (screw_mounts_enable)
        intersection() {
            at_cover_screws()
                cylinder(h = height, d = cover_boss_diameter);
            rounded_rect_prism(
                box_size,
                box_size,
                height,
                box_corner_radius
            );
        }
}

module m25_camera_taps(depth) {
    at_camera_holes()
        translate([0, 0, -epsilon])
            cylinder(h = depth + epsilon, d = m25_tap_diameter);
}

module m25_cover_taps(depth) {
    if (screw_mounts_enable)
        at_cover_screws()
            translate([0, 0, -epsilon])
                cylinder(h = depth + epsilon, d = m25_tap_diameter);
}

module ribbon_slot_cutter(from_z, height) {
    if (ribbon_slot_enable)
        rotate([0, 0, ribbon_angle])
            translate([
                -ribbon_slot_width / 2,
                inner_size / 2 - epsilon,
                from_z
            ])
                cube([
                    ribbon_slot_width,
                    cover_wall + 2 * epsilon,
                    height
                ]);
}

module at_cover_side_taps() {
    for (i = [0 : side_taps_count - 1]) {
        x = (i - (side_taps_count - 1) / 2) * side_taps_spacing;
        translate([x, 0, 0])
            children();
    }
}

module cover_side_tap_holes() {
    if (side_taps_enable) {
        hole_z = (cover_thickness + cover_inner_height) / 2;

        for (a = [0, 90, 180, 270])
            rotate([0, 0, a])
                at_cover_side_taps()
                    translate([
                        0,
                        box_size / 2 + epsilon,
                        hole_z
                    ])
                        rotate([90, 0, 0])
                            cylinder(
                                h = m3_tap_depth + 2 * epsilon,
                                d = m3_tap_diameter
                            );
    }
}

module cover_screw_lips() {
    if (screw_mounts_enable)
        intersection() {
            union() {
                at_cover_screws()
                    cylinder(
                        h = cover_thickness + cover_inner_height,
                        d = cover_boss_diameter
                    );
            }

            rounded_rect_prism(
                box_size,
                box_size,
                cover_thickness + cover_inner_height,
                box_corner_radius
            );
        }
}

// Printable orientation: outer face on the bed, cavity upward.
// Fat lips stand up to z = 0 in assembly and carry the M2.5 through-holes.
module cover() {
    difference() {
        union() {
            rounded_rect_prism(
                box_size,
                box_size,
                cover_thickness,
                box_corner_radius
            );

            translate([0, 0, cover_thickness - epsilon])
                difference() {
                    rounded_rect_prism(
                        box_size,
                        box_size,
                        cover_inner_height + epsilon,
                        box_corner_radius
                    );

                    translate([0, 0, -epsilon])
                        rounded_rect_prism(
                            inner_size,
                            inner_size,
                            cover_inner_height + 3 * epsilon,
                            max(epsilon, box_corner_radius - cover_wall)
                        );
                }

            cover_screw_lips();
        }

        cover_side_tap_holes();

        if (screw_mounts_enable)
            at_cover_screws()
                translate([0, 0, -epsilon])
                    cylinder(
                        h = cover_thickness + cover_inner_height + 2 * epsilon,
                        d = m25_clearance_diameter
                    );

        ribbon_slot_cutter(
            cover_thickness + cover_inner_height - ribbon_slot_height,
            ribbon_slot_height + epsilon
        );
    }
}

module camera_preview() {
    color("ForestGreen", 0.8)
        translate([0, 0, -pcb_thickness])
            rounded_rect_prism(
                pcb_size,
                pcb_size,
                pcb_thickness,
                pcb_corner_radius
            );

    color("Silver", 0.7)
        cylinder(h = cs_mount_height, d = cs_mount_diameter);

    if (ribbon_slot_enable)
        color("Gold", 0.85)
            rotate([0, 0, ribbon_angle])
                translate([
                    -ribbon_slot_width / 2,
                    pcb_size / 2 - 1,
                    -pcb_thickness - 0.3
                ])
                    cube([ribbon_slot_width, 12, 0.3]);
}

module cover_in_assembly() {
    translate([0, 0, -cover_thickness - cover_inner_height])
        cover();
}
