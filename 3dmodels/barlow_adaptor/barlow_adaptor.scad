// Barlow length adaptor ring
// Outer: 2" telescope focuser/mount barrel
// Inner: 46 mm bore
// Height: 40 mm

/* [Dimensions] */
outer_diameter = 50.8; // 2" standard eyepiece barrel (ISO 14134)
inner_diameter = 49.4;
height = 40.0;

/* [Fit / print] */
// Reduce OD slightly so a printed part slides into a metal 2" focuser
outer_clearance = 0.1;
// Extra ID for print shrinkage / easy fit of the inner piece
inner_clearance = 0.1;

/* [Quality] */
$fn = 200;

od = outer_diameter - outer_clearance;
id = inner_diameter + inner_clearance;

assert(od > id, "Outer diameter must be larger than inner diameter");

difference() {
    cylinder(h = height, d = od, center = false);
    translate([0, 0, -0.1])
        cylinder(h = height + 0.2, d = id, center = false);
}
