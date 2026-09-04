// HQ camera holder body — 1.25" nosepiece
// Same barrel / pyramid as the original combined model.
// All dimensions are in millimetres.

include <hq_camera_holder_lib.scad>

/* [Output] */
part = "assembly"; // [body, assembly]
show_camera_preview = true;

/* [1.25" nosepiece] */
eyepiece_diameter = 31.75;
outer_clearance = 0.15;
barrel_wall = 1.8;
barrel_length = 24.0;
barrel_chamfer = 1.0;
safety_groove_enable = true;
safety_groove_from_end = 6.5;
safety_groove_width = 4.5;
safety_groove_depth = 0.8;
bore_taper_length = 4.0;

/* [Pyramid] */
// Z height of the rounded pyramid from the plate to the 1.25" barrel.
// Keep this short: extra height here pushes the sensor out of focus.
pyramid_height = 8.0;

barrel_od = eyepiece_diameter - outer_clearance;
barrel_id = barrel_od - 2 * barrel_wall;
barrel_z0 = plate_thickness + pyramid_height;
barrel_z1 = barrel_z0 + barrel_length;
join_length = min(8.0, barrel_length);
max_tap_depth = plate_thickness + pyramid_height;
tap_depth = min(m25_tap_depth, max_tap_depth);

assert(barrel_od > barrel_id, "Barrel wall leaves no bore");
assert(barrel_id > 0, "Barrel inner diameter must be positive");
assert(pyramid_height >= bore_taper_length,
    "pyramid_height must cover the optical taper");
assert(
    tap_depth >= 6,
    "Increase pyramid_height or m25_tap_depth so M2.5 taps have enough meat"
);

module body() {
    difference() {
        nosepiece_body_solid(barrel_z0, barrel_length, barrel_od, join_length);
        nosepiece_optical_path(barrel_id, barrel_z1, bore_taper_length);
        tripod_lug_cutter();
        barrel_chamfers(barrel_z1, barrel_chamfer, barrel_od, barrel_id);
        if (safety_groove_enable)
            safety_groove_cut(
                barrel_z1,
                safety_groove_from_end,
                safety_groove_width,
                safety_groove_depth,
                barrel_od
            );
        m25_camera_taps(tap_depth);
        m25_cover_taps(tap_depth);
    }
}

module assembly() {
    body();
    cover_in_assembly();
    if (show_camera_preview)
        %camera_preview();
}

if (part == "body") {
    body();
    if (show_camera_preview)
        %camera_preview();
} else if (part == "assembly") {
    assembly();
} else {
    assert(false, "Unknown part selection");
}
