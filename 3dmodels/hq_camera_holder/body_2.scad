// HQ camera holder body — short open 2" nosepiece
// Large bore and short barrel so the sensor sits closer to the focuser.
// All dimensions are in millimetres.

include <hq_camera_holder_lib.scad>

/* [Output] */
part = "assembly"; // [body, assembly]
show_camera_preview = true;

/* [2" nosepiece] */
eyepiece_diameter = 50.8;
outer_clearance = 0.15;
barrel_wall = 1.8;
barrel_length = 12.0;
barrel_chamfer = 1.0;
bore_taper_length = 2.0;

/* [Pyramid] */
// Short join from the 60 mm plate to the ~50.8 mm barrel.
pyramid_height = 3.0;

barrel_od = eyepiece_diameter - outer_clearance;
barrel_id = barrel_od - 2 * barrel_wall;
barrel_z0 = plate_thickness + pyramid_height;
barrel_z1 = barrel_z0 + barrel_length;
join_length = min(4.0, barrel_length);
max_tap_depth = plate_thickness + pyramid_height;
tap_depth = min(m25_tap_depth, max_tap_depth);

assert(barrel_od > barrel_id, "Barrel wall leaves no bore");
assert(barrel_id > cs_bore, "2\" bore should stay open wider than the CS clearance");
assert(
    tap_depth >= 6,
    "Increase pyramid_height or m25_tap_depth so M2.5 taps have enough meat"
);
assert(
    barrel_z1 > cs_bore_height + bore_taper_length,
    "Barrel is shorter than the CS clearance plus flare"
);

module body() {
    difference() {
        nosepiece_body_solid(barrel_z0, barrel_length, barrel_od, join_length);
        nosepiece_optical_path(barrel_id, barrel_z1, bore_taper_length);
        tripod_lug_cutter();
        barrel_chamfers(barrel_z1, barrel_chamfer, barrel_od, barrel_id);
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
