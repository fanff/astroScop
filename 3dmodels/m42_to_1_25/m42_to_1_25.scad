// M42 (female) → 1.25" eyepiece adaptor ring
// One end: female M42×0.75 (T2) thread
// Other end: socket for a 1.25" eyepiece barrel

/* [Body] */
outer_diameter = 48.0;

/* [M42 female thread] */
m42_major = 42.0;
m42_pitch = 0.75;            // T2 / astronomy M42
thread_length = 4.0;
// Extra clearance on the male cutter (print fit for female thread)
thread_clearance = 0.25;

/* [1.25" eyepiece socket] */
eyepiece_diameter = 31.75;   // standard 1.25" barrel OD
eyepiece_clearance = 0.2;
eyepiece_depth = 22.0;

/* [Transition] */
// Length of conical transition from M42 thread to eyepiece socket
transition_length = 8.0;

/* [Set screw (optional)] */
set_screw_enable = true;
set_screw_diameter = 3.2;    // clearance / tap drill for M3
// Distance from the eyepiece-end face down to the screw axis
set_screw_from_eyepiece_end = 8.0;

/* [Quality] */
$fn = 200;
thread_steps_per_turn = 180;

height = transition_length + eyepiece_depth;

assert(outer_diameter > m42_major + 2, "outer_diameter too small for M42 wall");
assert(set_screw_from_eyepiece_end < eyepiece_depth, "set screw must sit within the eyepiece socket");

eyepiece_id = eyepiece_diameter + eyepiece_clearance;
m42_id = m42_major + thread_clearance;
// Eyepiece socket at +Z end; M42 thread at Z=0
// Eyepiece bore runs from Z=0 all the way up; transition cone sits inside
transition_z0 = thread_length;

// --- Metric thread (simplified ISO triangular profile) ---
// Solid male thread used as a cutter for the female bore.
module male_metric_thread(d_major, pitch, length, clearance = 0) {
    d = d_major + clearance;
    h = (sqrt(3) / 2) * pitch;       // sharp-V height
    tooth_h = (5 / 8) * h;           // engaged flank height
    r_maj = d / 2;
    r_root = r_maj - tooth_h;
    turns = length / pitch;
    steps = max(8, ceil(turns * thread_steps_per_turn));

    // Core
    cylinder(h = length, r = r_root, $fn = $fn);

    // Helical tooth
    for (i = [0 : steps - 1]) {
        z0 = i / steps * length;
        z1 = (i + 1) / steps * length;
        a0 = i / steps * turns * 360;
        a1 = (i + 1) / steps * turns * 360;
        hull() {
            rotate([0, 0, a0])
                translate([0, 0, z0])
                    thread_tooth_slice(r_root, r_maj, pitch);
            rotate([0, 0, a1])
                translate([0, 0, z1])
                    thread_tooth_slice(r_root, r_maj, pitch);
        }
    }
}

module thread_tooth_slice(r_root, r_maj, pitch) {
    w = pitch / 2;
    rotate([90, 0, 0])
        linear_extrude(height = 0.05, center = true)
            polygon([
                [r_root, -w],
                [r_maj, 0],
                [r_root, w]
            ]);
}

module body() {
    cylinder(h = height, d = outer_diameter);
}

module m42_female() {
    // Thread cutter
    translate([0, 0, -0.05])
        male_metric_thread(
            m42_major,
            m42_pitch,
            thread_length + 0.1,
            clearance = thread_clearance
        );
    // Smooth bore through threaded section (at thread root diameter)
    d = m42_major + thread_clearance;
    h = (sqrt(3) / 2) * m42_pitch;
    tooth_h = (5 / 8) * h;
    r_root = d / 2 - tooth_h;
    translate([0, 0, -0.05])
        cylinder(h = thread_length + 0.1, r = r_root);
}

module eyepiece_socket() {
    // Full-depth 1.25" bore from Z=0 to top
    translate([0, 0, -0.05])
        cylinder(h = height + 0.1, d = eyepiece_id);
}

module transition_bore() {
    // Conical transition from M42 thread diameter to eyepiece socket
    translate([0, 0, transition_z0])
        cylinder(
            h = transition_length,
            d1 = m42_id,
            d2 = eyepiece_id
        );
}

module set_screw_hole() {
    if (set_screw_enable) {
        z = height - set_screw_from_eyepiece_end;
        translate([0, 0, z])
            rotate([0, 90, 0])
                cylinder(h = outer_diameter / 2 + 1, d = set_screw_diameter);
    }
}

difference() {
    body();
    m42_female();
    transition_bore();
    eyepiece_socket();
    set_screw_hole();
}
