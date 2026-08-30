// Marks holder — T-shaped plate
// Stem (vertical): Pi camera tracking mount (2× M4)
// Crossbar (horizontal): small Maksutov (1/4"-20 camera screw)

/* [Mode] */
// testing = smaller / faster iterate; normal = final sizes
mode = "normal"; // [testing, normal]

/* [T shape] */
t_stem_length = 100.0;        // vertical arm (Pi), along +X
t_stem_width = 28.0;
t_horizontal_length = 215.0;  // crossbar (Maksutov), along Y
t_horizontal_width = 68.0;
plate_height = (mode == "normal") ? 10.0 : 3.0;  // small for testing, should be 10
outer_corner_radius = 12.0;    // tips / extremes of the T
junction_radius = 12.0;        // inner corners where stem meets crossbar
// Stem centre offset from crossbar midpoint along Y (+ toward Y+ / Maksutov)
stem_from_center = 55.0;

/* [Maksutov mount — camera screw] */
// Offset of screw centre from the crossbar midpoint along Y (+ toward Y+)
maks_from_center = 88.0;
camera_screw_diameter = 6.9; // 1/4"-20 clearance
// Footprint (long side along the crossbar / Y)
maks_pocket_along = 63;    // along Y
maks_pocket_across = 46;   // along X
maks_pocket_depth = 1.0;     // recess into top face

/* [Pi camera mount — M4] */
// Distance from the free end of the stem to the midpoint between the two M4 holes
pi_centre_from_end = 20.0;
pi_hole_spacing = 9.0;       // centre-to-centre
pi_hole_diameter = 4.5;      // M4 clearance (~4.3) + small extra
// true = holes spaced along the stem (X); false = across the stem (Y)
pi_holes_along_stem = true;

/* [Crossbar M4 taps] */
m4_tap_spacing = 141.9;      // centre-to-centre along Y, centred on bar
m4_tap_diameter = 3.3;       // tap drill for M4×0.7

/* [Bottom hollows] */
hollow_length_y = 122.0;     // along Y
hollow_width_x = 6.0;        // along X
hollow_depth = (mode == "normal") ? 8.0 : 8.0;  // small for testing, should be 8
// Gap between the two inner walls (± half from crossbar centre X)
hollow_inner_gap = 28.0;

/* [Strap deck] */
// Plain plate in the open T corner; joined to the T then rounded together
strap_deck_height = (mode == "normal") ? 3.0 : 1.0;   // small for testing, should be 3
strap_deck_y_min = 12.0;      // start a bit above Y=0
strap_deck_x_max = (mode == "normal") ? 168.0 : 80.0; // small for testing, should be 168
strap_slot_width = 3.0;      // along X
strap_slot_length = 7.0;     // along Y
strap_slot_spacing = 15.0;   // centre-to-centre grid

/* [Quality] */
$fn = 64;

assert(t_horizontal_width >= maks_pocket_across, "t_horizontal_width must cover the Maksutov pocket");
assert(plate_height > maks_pocket_depth, "plate_height must exceed pocket depth");
assert(abs(maks_from_center) < t_horizontal_length / 2, "maks_from_center must lie on the crossbar");
assert(t_stem_length > pi_centre_from_end, "t_stem_length too short for Pi mount");
assert(outer_corner_radius >= 0 && junction_radius >= 0, "corner radii must be >= 0");
assert(2 * outer_corner_radius <= t_stem_width, "outer_corner_radius too large for stem width");
assert(2 * outer_corner_radius <= min(t_horizontal_width, t_stem_length), "outer_corner_radius too large for T tips");
assert(m4_tap_spacing < t_horizontal_length, "m4_tap_spacing must fit on the crossbar");
assert(hollow_length_y < t_horizontal_length, "hollow_length_y must fit on the crossbar");
assert(hollow_inner_gap + 2 * hollow_width_x < t_horizontal_width, "hollows must fit across the crossbar");
assert(strap_deck_height > 0 && strap_deck_height < plate_height, "strap_deck_height must be between 0 and plate_height");
assert(abs(stem_from_center) + t_stem_width / 2 < t_horizontal_length / 2, "stem_from_center places stem off the crossbar");
assert(strap_deck_y_min >= 0, "strap_deck_y_min must be >= 0");
assert(strap_deck_x_max > t_horizontal_width, "strap_deck_x_max must extend past the crossbar");

// Crossbar: X in [0, t_horizontal_width], Y in [0, t_horizontal_length]
// Stem:    X in [t_horizontal_width, …], Y offset by stem_from_center
maks_x = t_horizontal_width / 2;
crossbar_mid_y = t_horizontal_length / 2;
maks_y = crossbar_mid_y + maks_from_center;
stem_y = crossbar_mid_y + stem_from_center;
pi_x = t_horizontal_width + t_stem_length - pi_centre_from_end;
pi_y = stem_y;

// Y- face of the stem (border reached from Y≈0)
stem_y_minus = stem_y - t_stem_width / 2;
deck_x0 = t_horizontal_width;
deck_x1 = min(t_horizontal_width + t_stem_length, strap_deck_x_max);
deck_y0 = strap_deck_y_min;
deck_y1 = stem_y_minus;
deck_size_x = deck_x1 - deck_x0;
deck_size_y = deck_y1 - deck_y0;
has_strap_deck = deck_size_x > 0 && deck_size_y > 0;

module t_profile() {
    union() {
        square([t_horizontal_width, t_horizontal_length], center = false);
        translate([t_horizontal_width, stem_y - t_stem_width / 2])
            square([t_stem_length, t_stem_width], center = false);
    }
}

module strap_deck_profile() {
    if (has_strap_deck)
        translate([deck_x0, deck_y0])
            square([deck_size_x, deck_size_y], center = false);
}

// T + deck as one outline (before rounding)
module body_profile() {
    union() {
        t_profile();
        strap_deck_profile();
    }
}

// Round convex (outer) and concave (junction) corners of a 2D outline
module round_corners_2d(outer_r, inner_r) {
    offset(r = outer_r)
        offset(r = -outer_r)
            offset(r = -inner_r)
                offset(r = inner_r)
                    children();
}

module t_plate() {
    union() {
        // Joined T + deck, rounded together, at deck height
        linear_extrude(height = strap_deck_height, convexity = 4)
            round_corners_2d(outer_corner_radius, junction_radius)
                body_profile();

        // Full-height core (stem + crossbar only), same rounding
        linear_extrude(height = plate_height, convexity = 4)
            round_corners_2d(outer_corner_radius, junction_radius)
                t_profile();
    }
}

module maks_pocket() {
    translate([
        maks_x - maks_pocket_across / 2,
        maks_y - maks_pocket_along / 2,
        plate_height - maks_pocket_depth
    ])
        cube([maks_pocket_across, maks_pocket_along, maks_pocket_depth + 0.1], center = false);
}

module camera_screw_hole() {
    translate([maks_x, maks_y, -0.1])
        cylinder(h = plate_height + 0.2, d = camera_screw_diameter);
}

module pi_m4_holes() {
    offsets = pi_holes_along_stem
        ? [[-pi_hole_spacing / 2, 0], [pi_hole_spacing / 2, 0]]
        : [[0, -pi_hole_spacing / 2], [0, pi_hole_spacing / 2]];

    for (o = offsets)
        translate([pi_x + o[0], pi_y + o[1], -0.1])
            cylinder(h = plate_height + 0.2, d = pi_hole_diameter);
}

module m4_tap_holes() {
    for (dy = [-m4_tap_spacing / 2, m4_tap_spacing / 2])
        translate([maks_x, crossbar_mid_y + dy, -0.1])
            cylinder(h = plate_height + 0.2, d = m4_tap_diameter);
}

module bottom_hollows() {
    for (side = [-1, 1]) {
        inner_x = maks_x + side * hollow_inner_gap / 2;
        x0 = (side < 0) ? inner_x - hollow_width_x : inner_x;
        translate([x0, crossbar_mid_y - hollow_length_y / 2, -0.1])
            cube([hollow_width_x, hollow_length_y, hollow_depth + 0.1], center = false);
    }
}

module strap_slots() {
    if (has_strap_deck) {
        nx = floor((deck_x1 - deck_x0) / strap_slot_spacing);
        ny = floor((deck_y1 - deck_y0) / strap_slot_spacing);
        for (ix = [0 : nx])
            for (iy = [0 : ny]) {
                cx = deck_x0 + strap_slot_spacing * (ix + 0.5);
                cy = deck_y0 + strap_slot_spacing * (iy + 0.5);
                if (cx - strap_slot_width / 2 >= deck_x0
                    && cx + strap_slot_width / 2 <= deck_x1
                    && cy - strap_slot_length / 2 >= deck_y0
                    && cy + strap_slot_length / 2 <= deck_y1)
                    translate([
                        cx - strap_slot_width / 2,
                        cy - strap_slot_length / 2,
                        -0.1
                    ])
                        cube([
                            strap_slot_width,
                            strap_slot_length,
                            strap_deck_height + 0.2
                        ], center = false);
            }
    }
}

difference() {
    t_plate();
    maks_pocket();
    camera_screw_hole();
    pi_m4_holes();
    m4_tap_holes();
    bottom_hollows();
    strap_slots();
}
