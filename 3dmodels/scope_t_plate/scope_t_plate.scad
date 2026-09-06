// Scope T-plate
// Crossbar: rails + M4 tap holes for bar mounting
// Stem: extendable vertical arm + deck in the open T corner
// All dimensions in millimetres.

/* [Mode] */
// testing = thinner / shorter deck for faster iterates
mode = "normal"; // [testing, normal]

/* [Features] */
enable_rails = true;
enable_m4_taps = true;
enable_deck = true;
enable_scope_mount = true;
enable_pi_mount = true;

/* [T body] */
// Vertical arm length past the crossbar (extension)
stem_length = 100.0;
stem_width = 28.0;
// Horizontal bar along Y
crossbar_length = 215.0;
crossbar_width = 68.0;
plate_height = (mode == "normal") ? 10.0 : 3.0;
outer_corner_radius = 12.0;
junction_radius = 12.0;
// Stem centre offset from crossbar midpoint along Y (+ toward Y+)
stem_from_center = 55.0;

/* [Rails — underside of the crossbar] */
rail_length = 122.0;       // along Y
rail_width = 6.0;          // along X
rail_depth = 8.0;
// Gap between the two inner walls, centred on the bar
rail_inner_gap = 28.0;

/* [Crossbar M4 taps] */
m4_tap_spacing = 141.9;    // centre-to-centre along Y, centred on the bar
m4_tap_diameter = 3.3;     // tap drill for M4×0.7

/* [Deck — filling plate in the open T corner] */
deck_height = (mode == "normal") ? 3.0 : 1.0;
deck_y_min = 12.0;
deck_x_max = (mode == "normal") ? 168.0 : 80.0;
deck_hole_spacing = 10.0;  // 10×10 mm grid
m3_tap_diameter = 2.5;     // tap drill for M3×0.5

/* [Scope mount — 1/4"-20] */
// Distance of each screw from the plate / crossbar centre along Y
scope_screw_from_center = 88.0;
camera_screw_diameter = 6.9;

/* [Pi camera mount — M3 through on the stem] */
pi_centre_from_end = 20.0;
pi_hole_spacing = 10.0;
m3_clearance_diameter = 3.2;  // M3 pass-through
// true = holes spaced along the stem (X); false = across the stem (Y)
pi_holes_along_stem = true;
// Round hole is the pivot; the other cut is an arc around it
pi_arc_angle = 20.0;          // total sweep, degrees

/* [Quality] */
$fn = 64;
epsilon = 0.1;

assert(abs(scope_screw_from_center) < crossbar_length / 2,
    "scope_screw_from_center must lie on the crossbar");
assert(stem_length > pi_centre_from_end,
    "stem_length too short for Pi mount");
assert(outer_corner_radius >= 0 && junction_radius >= 0,
    "corner radii must be >= 0");
assert(2 * outer_corner_radius <= stem_width,
    "outer_corner_radius too large for stem width");
assert(2 * outer_corner_radius <= min(crossbar_width, stem_length),
    "outer_corner_radius too large for T tips");
assert(m4_tap_spacing < crossbar_length,
    "m4_tap_spacing must fit on the crossbar");
assert(rail_length < crossbar_length,
    "rail_length must fit on the crossbar");
assert(rail_inner_gap + 2 * rail_width < crossbar_width,
    "rails must fit across the crossbar");
assert(deck_height > 0 && deck_height < plate_height,
    "deck_height must be between 0 and plate_height");
assert(abs(stem_from_center) + stem_width / 2 < crossbar_length / 2,
    "stem_from_center places stem off the crossbar");
assert(deck_y_min >= 0, "deck_y_min must be >= 0");
assert(deck_x_max > crossbar_width,
    "deck_x_max must extend past the crossbar");
assert(rail_depth < plate_height, "rail_depth must leave a solid floor");
assert(deck_hole_spacing > m3_tap_diameter,
    "deck_hole_spacing must leave wall between M3 taps");
assert(pi_arc_angle > 0 && pi_arc_angle < 180,
    "pi_arc_angle must be between 0 and 180");
assert(
    2 * (pi_hole_spacing * sin(pi_arc_angle / 2) + m3_clearance_diameter / 2)
        < (pi_holes_along_stem ? stem_width : stem_length),
    "Pi arc slot does not fit on the stem; reduce pi_arc_angle"
);

// Crossbar: X in [0, crossbar_width], Y in [0, crossbar_length]
// Stem:    X in [crossbar_width, …], Y offset by stem_from_center
crossbar_mid_x = crossbar_width / 2;
crossbar_mid_y = crossbar_length / 2;
stem_y = crossbar_mid_y + stem_from_center;
pi_x = crossbar_width + stem_length - pi_centre_from_end;
pi_y = stem_y;

stem_y_minus = stem_y - stem_width / 2;
deck_x0 = crossbar_width;
deck_x1 = min(crossbar_width + stem_length, deck_x_max);
deck_y0 = deck_y_min;
deck_y1 = stem_y_minus;
deck_size_x = deck_x1 - deck_x0;
deck_size_y = deck_y1 - deck_y0;
has_deck = enable_deck && deck_size_x > 0 && deck_size_y > 0;

module round_corners_2d(outer_r, inner_r) {
    offset(r = outer_r)
        offset(r = -outer_r)
            offset(r = -inner_r)
                offset(r = inner_r)
                    children();
}

module crossbar_profile() {
    square([crossbar_width, crossbar_length], center = false);
}

module stem_profile() {
    translate([crossbar_width, stem_y - stem_width / 2])
        square([stem_length, stem_width], center = false);
}

module t_profile() {
    union() {
        crossbar_profile();
        stem_profile();
    }
}

module deck_profile() {
    if (has_deck)
        translate([deck_x0, deck_y0])
            square([deck_size_x, deck_size_y], center = false);
}

module body_profile() {
    union() {
        t_profile();
        deck_profile();
    }
}

module t_plate() {
    union() {
        if (has_deck)
            linear_extrude(height = deck_height, convexity = 4)
                round_corners_2d(outer_corner_radius, junction_radius)
                    body_profile();

        linear_extrude(height = plate_height, convexity = 4)
            round_corners_2d(outer_corner_radius, junction_radius)
                t_profile();
    }
}

module camera_screw_holes() {
    for (dy = [-scope_screw_from_center, scope_screw_from_center])
        translate([crossbar_mid_x, crossbar_mid_y + dy, -epsilon])
            cylinder(h = plate_height + 2 * epsilon, d = camera_screw_diameter);
}

module pi_mount_holes() {
    // Pivot is the round hole (toward the crossbar / −Y).
    // The arc is centred on that hole at radius pi_hole_spacing.
    pivot = pi_holes_along_stem
        ? [pi_x - pi_hole_spacing / 2, pi_y]
        : [pi_x, pi_y - pi_hole_spacing / 2];
    heading = pi_holes_along_stem ? 0 : 90;

    translate([pivot[0], pivot[1], -epsilon])
        cylinder(h = plate_height + 2 * epsilon, d = m3_clearance_diameter);

    translate([pivot[0], pivot[1], 0])
        rotate([0, 0, heading - pi_arc_angle / 2])
            rotate_extrude(angle = pi_arc_angle, convexity = 4)
                translate([
                    pi_hole_spacing - m3_clearance_diameter / 2,
                    -epsilon
                ])
                    square([
                        m3_clearance_diameter,
                        plate_height + 2 * epsilon
                    ]);

    for (a = [heading - pi_arc_angle / 2, heading + pi_arc_angle / 2])
        translate([
            pivot[0] + pi_hole_spacing * cos(a),
            pivot[1] + pi_hole_spacing * sin(a),
            -epsilon
        ])
            cylinder(h = plate_height + 2 * epsilon, d = m3_clearance_diameter);
}

module m4_tap_holes() {
    for (dy = [-m4_tap_spacing / 2, m4_tap_spacing / 2])
        translate([crossbar_mid_x, crossbar_mid_y + dy, -epsilon])
            cylinder(h = plate_height + 2 * epsilon, d = m4_tap_diameter);
}

module rails() {
    for (side = [-1, 1]) {
        inner_x = crossbar_mid_x + side * rail_inner_gap / 2;
        x0 = (side < 0) ? inner_x - rail_width : inner_x;
        translate([
            x0,
            crossbar_mid_y - rail_length / 2,
            -epsilon
        ])
            cube([rail_width, rail_length, rail_depth + epsilon], center = false);
    }
}

module deck_m3_holes() {
    if (has_deck) {
        nx = floor(deck_size_x / deck_hole_spacing);
        ny = floor(deck_size_y / deck_hole_spacing);
        r = m3_tap_diameter / 2;
        for (ix = [0 : nx])
            for (iy = [0 : ny]) {
                cx = deck_x0 + deck_hole_spacing * (ix + 0.5);
                cy = deck_y0 + deck_hole_spacing * (iy + 0.5);
                if (cx - r >= deck_x0
                    && cx + r <= deck_x1
                    && cy - r >= deck_y0
                    && cy + r <= deck_y1)
                    translate([cx, cy, -epsilon])
                        cylinder(
                            h = deck_height + 2 * epsilon,
                            d = m3_tap_diameter
                        );
            }
    }
}

difference() {
    t_plate();
    if (enable_scope_mount)
        camera_screw_holes();
    if (enable_pi_mount)
        pi_mount_holes();
    if (enable_m4_taps)
        m4_tap_holes();
    if (enable_rails)
        rails();
    deck_m3_holes();
}
