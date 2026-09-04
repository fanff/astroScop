// HQ camera holder body — open CS-mount plate
// No nosepiece: the CS cylinder sticks through so a CS lens can screw on.
// Local bosses keep cover M2.5 taps. All dimensions are in millimetres.

include <hq_camera_holder_lib.scad>

/* [Output] */
part = "assembly"; // [body, assembly]
show_camera_preview = true;

/* [Cover screw bosses] */
// Extra +Z meat at the cover holes; centre stays clear for CS threads.
boss_height = 8.0;

camera_tap_depth = plate_thickness;
cover_tap_depth = min(m25_tap_depth, plate_thickness + boss_height);

assert(
    cover_tap_depth >= 6,
    "Increase boss_height so cover M2.5 taps have enough meat"
);

module body() {
    difference() {
        union() {
            plate_blank();
            cover_screw_bosses(boss_height);
        }
        cs_plate_bore();
        tripod_lug_cutter();
        m25_camera_taps(camera_tap_depth);
        m25_cover_taps(cover_tap_depth);
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
