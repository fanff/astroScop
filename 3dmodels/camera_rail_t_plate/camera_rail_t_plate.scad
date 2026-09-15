// Camera-rail T-plate
// Crossbar: underside bar rails + M4 taps, triangular top rail, sliding camera holder
// Stem: vertical arm, same T outline as the other plates
// All dimensions in millimetres.

/* [Output] */
// plate = T-plate STL; holder = sliding camera rectangle; assembly = preview
part = "plate"; // [plate, holder, assembly]

/* [Mode] */
// testing = thinner plate / shallower cuts for faster iterates
mode = "normal"; // [testing, normal]

/* [Features] */
enable_underside_rails = true;
enable_bar_m4_taps = true;
enable_top_rails = true;
enable_top_rail_m4 = true;
enable_head_groove = true;

/* [T body] */
stem_length = 100.0;
stem_width = 28.0;
crossbar_length = 215.0;
crossbar_width = 68.0;
plate_height = (mode == "normal") ? 10.0 : 3.0;
outer_corner_radius = 12.0;
junction_radius = 12.0;
stem_from_center = 55.0;

/* [Rails — underside of the crossbar] */
rail_length = 122.0;
rail_width = 6.0;
rail_depth = (mode == "normal") ? 8.0 : 2.0;
rail_inner_gap = 28.0;

/* [Crossbar M4 taps] */
m4_tap_spacing = 141.9;
m4_tap_diameter = 3.3;

/* [Top rail — triangle profile on the crossbar] */
top_rail_length = 191.0;
top_rail_height = 8.0;
top_rail_shoulder = 8.0;
top_rail_m4_spacing = 15.0;
top_rail_m4_end_margin = 8.0;

/* [Camera holder] */
slider_length = 40.0;
slider_width = 32.0;
print_clearance = 0.3;
camera_screw_diameter = 6.9;
screw_head_diameter = 16.0;
screw_head_depth = 5.0;

/* [Screw-head groove] */
head_groove_width = 18.0;
head_groove_depth = (mode == "normal") ? 6.0 : 1.5;

/* [Assembly preview] */
assembly_holder_from_center = 0.0;

/* [Quality] */
$fn = 64;
epsilon = 0.1;

crossbar_mid_x = crossbar_width / 2;
crossbar_mid_y = crossbar_length / 2;
stem_y = crossbar_mid_y + stem_from_center;

channel_floor_width = slider_width + 2 * print_clearance;
slider_height = top_rail_height - print_clearance;
top_rail_overhang = top_rail_height;
channel_top_width = channel_floor_width - 2 * top_rail_overhang;
slider_bottom = slider_width;
slider_top = slider_bottom - 2 * slider_height;

left_inner_floor = crossbar_mid_x - channel_floor_width / 2;
right_inner_floor = crossbar_mid_x + channel_floor_width / 2;
left_outer = left_inner_floor - top_rail_shoulder;
right_outer = right_inner_floor + top_rail_shoulder;
left_inner_top = left_inner_floor + top_rail_overhang;
right_inner_top = right_inner_floor - top_rail_overhang;
left_shoulder_x = left_outer + top_rail_shoulder / 2;
right_shoulder_x = right_outer - top_rail_shoulder / 2;

top_rail_y0 = crossbar_mid_y - top_rail_length / 2;
top_rail_usable = top_rail_length - 2 * top_rail_m4_end_margin;
n_top_m4 = (top_rail_usable >= 0)
    ? floor(top_rail_usable / top_rail_m4_spacing) + 1
    : 0;
top_m4_span = (n_top_m4 > 1) ? (n_top_m4 - 1) * top_rail_m4_spacing : 0;
top_m4_first_y = crossbar_mid_y - top_m4_span / 2;

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
    "underside rails must fit across the crossbar");
assert(rail_depth < plate_height,
    "rail_depth must leave a solid floor");
assert(abs(stem_from_center) + stem_width / 2 < crossbar_length / 2,
    "stem_from_center places stem off the crossbar");
assert(top_rail_length <= crossbar_length,
    "top_rail_length must fit on the crossbar");
assert(right_outer - left_outer < crossbar_width,
    "top rails must fit across the crossbar");
assert(left_outer > 0 && right_outer < crossbar_width,
    "top rails overflow the crossbar in X");
assert(channel_top_width > 0,
    "top rail overhang closes the channel; reduce top_rail_height");
assert(slider_top > 0,
    "slider_width too small for 45° sides at slider_height");
assert(print_clearance > 0,
    "print_clearance must be > 0");
assert(head_groove_depth > 0 && head_groove_depth < plate_height,
    "head_groove_depth must be between 0 and plate_height");
assert(head_groove_width < slider_width,
    "head_groove_width must leave sliding lands under the holder");
assert(head_groove_width > screw_head_diameter,
    "head_groove_width must clear the screw head");
assert(slider_height > screw_head_depth,
    "slider_height must exceed screw_head_depth");
assert(top_rail_shoulder > m4_tap_diameter,
    "top_rail_shoulder too narrow for M4 taps");
assert(slider_length < top_rail_length,
    "slider_length must fit in the top rail");
assert(abs(assembly_holder_from_center) + slider_length / 2
        <= top_rail_length / 2,
    "assembly_holder_from_center slides the holder off the rail");
assert(!enable_top_rail_m4 || n_top_m4 >= 1,
    "top rail too short for M4 taps; reduce top_rail_m4_end_margin");

module round_corners_2d(outer_r, inner_r) {
    offset(r = outer_r)
        offset(r = -outer_r)
            offset(r = -inner_r)
                offset(r = inner_r)
                    children();
}

module t_profile() {
    union() {
        square([crossbar_width, crossbar_length], center = false);
        translate([crossbar_width, stem_y - stem_width / 2])
            square([stem_length, stem_width], center = false);
    }
}

module t_plate() {
    linear_extrude(height = plate_height, convexity = 4)
        round_corners_2d(outer_corner_radius, junction_radius)
            t_profile();
}

module left_rail_profile() {
    polygon([
        [left_outer, 0],
        [left_inner_floor, 0],
        [left_inner_top, top_rail_height],
        [left_outer, top_rail_height]
    ]);
}

module right_rail_profile() {
    polygon([
        [right_inner_floor, 0],
        [right_outer, 0],
        [right_outer, top_rail_height],
        [right_inner_top, top_rail_height]
    ]);
}

module top_rails() {
    translate([0, top_rail_y0 + top_rail_length, plate_height])
        rotate([90, 0, 0])
            linear_extrude(height = top_rail_length, convexity = 4)
                union() {
                    left_rail_profile();
                    right_rail_profile();
                }
}

module holder_profile() {
    polygon([
        [-slider_bottom / 2, 0],
        [ slider_bottom / 2, 0],
        [ slider_bottom / 2 - slider_height, slider_height],
        [-slider_bottom / 2 + slider_height, slider_height]
    ]);
}

module holder() {
    difference() {
        translate([0, slider_length / 2, 0])
            rotate([90, 0, 0])
                linear_extrude(height = slider_length, convexity = 4)
                    holder_profile();
        translate([0, 0, -epsilon])
            cylinder(
                h = slider_height + 2 * epsilon,
                d = camera_screw_diameter
            );
        translate([0, 0, -epsilon])
            cylinder(
                h = screw_head_depth + epsilon,
                d = screw_head_diameter
            );
    }
}

module bar_m4_tap_holes() {
    for (dy = [-m4_tap_spacing / 2, m4_tap_spacing / 2])
        translate([crossbar_mid_x, crossbar_mid_y + dy, -epsilon])
            cylinder(h = plate_height + 2 * epsilon, d = m4_tap_diameter);
}

module underside_rails() {
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

module top_rail_m4_holes() {
    for (i = [0 : max(0, n_top_m4 - 1)]) {
        cy = top_m4_first_y + i * top_rail_m4_spacing;
        for (cx = [left_shoulder_x, right_shoulder_x])
            translate([cx, cy, plate_height - epsilon])
                cylinder(
                    h = top_rail_height + 2 * epsilon,
                    d = m4_tap_diameter
                );
    }
}

module head_groove() {
    translate([
        crossbar_mid_x - head_groove_width / 2,
        top_rail_y0 - epsilon,
        plate_height - head_groove_depth
    ])
        cube([
            head_groove_width,
            top_rail_length + 2 * epsilon,
            head_groove_depth + epsilon
        ], center = false);
}

module plate() {
    difference() {
        union() {
            t_plate();
            if (enable_top_rails)
                top_rails();
        }
        if (enable_bar_m4_taps)
            bar_m4_tap_holes();
        if (enable_underside_rails)
            underside_rails();
        if (enable_top_rails && enable_top_rail_m4)
            top_rail_m4_holes();
        if (enable_head_groove)
            head_groove();
    }
}

module assembly() {
    plate();
    %translate([
        crossbar_mid_x,
        crossbar_mid_y + assembly_holder_from_center,
        plate_height
    ])
        holder();
}

if (part == "holder")
    holder();
else if (part == "assembly")
    assembly();
else
    plate();
