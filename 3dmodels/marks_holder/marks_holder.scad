// Marks holder — T-shaped plate
// Stem (vertical): Pi camera tracking mount (2× M3)
// Crossbar (horizontal): small Maksutov (1/4"-20 camera screw)

/* [T shape] */
t_stem_length = 100.0;        // vertical arm (Pi), along +X
t_stem_width = 28.0;
t_horizontal_length = 220.0;  // crossbar (Maksutov), along Y
t_horizontal_width = 68.0;
plate_height = 10.0;
outer_corner_radius = 12.0;    // tips / extremes of the T
junction_radius = 12.0;        // inner corners where stem meets crossbar

/* [Maksutov mount — camera screw] */
// Offset of screw centre from the crossbar midpoint along Y (+ toward Y+)
maks_from_center = 88.0;
camera_screw_diameter = 6.5; // 1/4"-20 clearance
// Footprint (long side along the crossbar / Y)
maks_pocket_along = 61.9;    // along Y
maks_pocket_across = 44.9;   // along X
maks_pocket_depth = 1.0;     // recess into top face

/* [Pi camera mount — M3] */
// Distance from the free end of the stem to the midpoint between the two M3 holes
pi_centre_from_end = 20.0;
m3_hole_spacing = 9.0;       // centre-to-centre
m3_hole_diameter = 3.2;      // clearance for M3
// true = holes spaced along the stem (X); false = across the stem (Y)
pi_holes_along_stem = true;

/* [Crossbar M4 taps] */
m4_tap_spacing = 141.9;      // centre-to-centre along Y, centred on bar
m4_tap_diameter = 3.3;       // tap drill for M4×0.7

/* [Bottom hollows] */
hollow_length_y = 122.0;     // along Y
hollow_width_x = 6.0;        // along X
hollow_depth = 8.0;          // cut up from the bottom face
// Gap between the two inner walls (± half from crossbar centre X)
hollow_inner_gap = 30.0;

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
assert(hollow_depth < plate_height, "hollow_depth must leave material above");
assert(hollow_length_y < t_horizontal_length, "hollow_length_y must fit on the crossbar");
assert(hollow_inner_gap + 2 * hollow_width_x < t_horizontal_width, "hollows must fit across the crossbar");

// Crossbar: X in [0, t_horizontal_width], Y in [0, t_horizontal_length]
// Stem:    X in [t_horizontal_width, t_horizontal_width + t_stem_length], Y centred
maks_x = t_horizontal_width / 2;
maks_y = t_horizontal_length / 2 + maks_from_center;
pi_x = t_horizontal_width + t_stem_length - pi_centre_from_end;
pi_y = t_horizontal_length / 2;
crossbar_mid_y = t_horizontal_length / 2;

module t_profile() {
    union() {
        square([t_horizontal_width, t_horizontal_length], center = false);
        translate([t_horizontal_width, (t_horizontal_length - t_stem_width) / 2])
            square([t_stem_length, t_stem_width], center = false);
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
    linear_extrude(height = plate_height, convexity = 4)
        round_corners_2d(outer_corner_radius, junction_radius)
            t_profile();
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

module pi_m3_holes() {
    offsets = pi_holes_along_stem
        ? [[-m3_hole_spacing / 2, 0], [m3_hole_spacing / 2, 0]]
        : [[0, -m3_hole_spacing / 2], [0, m3_hole_spacing / 2]];

    for (o = offsets)
        translate([pi_x + o[0], pi_y + o[1], -0.1])
            cylinder(h = plate_height + 0.2, d = m3_hole_diameter);
}

module m4_tap_holes() {
    for (dy = [-m4_tap_spacing / 2, m4_tap_spacing / 2])
        translate([maks_x, crossbar_mid_y + dy, -0.1])
            cylinder(h = plate_height + 0.2, d = m4_tap_diameter);
}

module bottom_hollows() {
    // Inner walls at maks_x ± hollow_inner_gap/2; pockets extend outward in X
    for (side = [-1, 1]) {
        inner_x = maks_x + side * hollow_inner_gap / 2;
        // side -1: pocket is to the left of its inner wall; side +1: to the right
        x0 = (side < 0) ? inner_x - hollow_width_x : inner_x;
        translate([x0, crossbar_mid_y - hollow_length_y / 2, -0.1])
            cube([hollow_width_x, hollow_length_y, hollow_depth + 0.1], center = false);
    }
}

difference() {
    t_plate();
    maks_pocket();
    camera_screw_hole();
    pi_m3_holes();
    m4_tap_holes();
    bottom_hollows();
}
