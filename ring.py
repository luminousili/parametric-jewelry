#!/usr/bin/env python3
"""Parametric solitaire engagement ring with pave shoulders -> STEP/STL + weight report.

Axes: finger along Y, band in the XZ plane, centre stone on +Z. Units: mm.
"""
import argparse, json, math, sys
from pathlib import Path
import cadquery as cq

# g/cm3. Gold values are yellow-gold mid-range figures; "platinum" is pure Pt (Pt950 is ~20.1-20.7).
METALS = {"18k": 15.5, "14k": 13.1, "22k": 17.8, "sterling": 10.36, "platinum": 21.45}
COMFORT, DOME = 0.25, 0.15  # inner / outer dome depth of the band profile, as a fraction of thickness
V, Y = cq.Vector, cq.Vector(0, 1, 0)


def us_to_diameter(size):
    return 11.63 + 0.8128 * size  # each US size adds 0.032 in (0.8128 mm) of inner diameter


def band(r_in, w, t, angle=360):
    """Comfort-fit (court) band around the Y axis: domed inside face, gently domed outside face."""
    c, e = COMFORT * t, DOME * t
    return (cq.Workplane("XY").moveTo(r_in + c, -w / 2).lineTo(r_in + t - e, -w / 2)
            .threePointArc((r_in + t, 0), (r_in + t - e, w / 2)).lineTo(r_in + c, w / 2)
            .threePointArc((r_in, 0), (r_in + c, -w / 2)).close()
            .revolve(angle, (0, 0, 0), (0, 1, 0)).val())


def brilliant(d, z=0.0):
    """Round brilliant pointing up +Z, girdle centre at height z. Tolkowsky-like proportions:
    table 57%, crown 16.2%, girdle 3%, pavilion 43.1% of diameter.
    ponytail: 16-sided ruled lofts give facet-like planes, not the real 57-facet brilliant layout."""
    poly = lambda zz, dd, rot=0.0: cq.Workplane("XY").workplane(offset=zz).transformed(rotate=(0, 0, rot)).polygon(16, dd)
    pavilion = poly(-0.431 * d, 0.02 * d).workplane(offset=0.416 * d).polygon(16, d).loft(ruled=True)
    girdle = poly(-0.015 * d, d).extrude(0.03 * d)
    crown = poly(0.015 * d, d).workplane(offset=0.162 * d).transformed(rotate=(0, 0, 11.25)).polygon(16, 0.57 * d).loft(ruled=True)
    return pavilion.union(girdle).union(crown).val().translate(V(0, 0, z))


def wire_rod(pts, r):
    """Round wire of radius r along a polyline, rounded at the bends and the far end, as one solid."""
    pts = [V(*p) for p in pts]
    path = cq.Workplane().polyline(pts)
    rod = cq.Workplane(cq.Plane(pts[0], (pts[1] - pts[0]).cross(V(0, 0, 1)), pts[1] - pts[0])).circle(r)
    return rod.sweep(path, transition="round").val().fuse(ball(pts[-1], r))


def ball(p, r):
    return cq.Solid.makeSphere(r, V(*p), V(0, 0, 1), -90)


def build(inner_d, band_width=2.2, band_thickness=1.7, stone_mm=6.5, prongs=6, setting_height=4.5,
          prong_mm=1.0, pave=8, pave_mm=1.3):
    """Returns (metal solid, stones compound, warnings)."""
    d, pr, p = stone_mm, prong_mm / 2, pave_mm
    r_in = inner_d / 2
    r_out = r_in + band_thickness
    z_g = r_out + setting_height                      # girdle height of the centre stone
    center = brilliant(d, z_g)

    # Prong head: prongs flare from a foot on the band to the girdle, then lean inward over the crown.
    r_foot, z_foot = max(band_width / 2 - pr, 0.3), r_out - 0.4
    seat = (d / 2 + 0.6 * pr, z_g)                    # prong centre just outside the girdle: bites 0.4 r into it
    tip = (d / 2 - 0.2 * pr, z_g + 0.1 * d + 0.5 * pr)
    head = []
    for k in range(prongs):
        a = math.radians(360 * k / prongs + 180 / prongs)
        at = lambda rz: (rz[0] * math.cos(a), rz[0] * math.sin(a), rz[1])
        head.append(wire_rod([at((r_foot, z_foot)), at(seat), at(tip)], pr))
    # Crown collar just under the girdle (stone cut below turns it into the bearing) + a lower gallery rail.
    z_c = z_g - 0.15 - 0.9
    head.append(cq.Solid.makeCylinder(d / 2 + 0.1, 0.9, V(0, 0, z_c)).cut(cq.Solid.makeCylinder(d / 2 - 0.5, 0.9, V(0, 0, z_c))))
    f = 0.45                                          # rail at 45% of the way from foot to seat
    head.append(cq.Solid.makeTorus(r_foot + f * (seat[0] - r_foot), 0.35 * pr, V(0, 0, z_foot + f * (z_g - z_foot)), V(0, 0, 1)))

    # Pave shoulders: stones in drilled seats along the band top, with a pair of beads between each stone.
    pave_stones, seats, beads = [], [], []
    pitch, s0 = p + 0.15, r_foot + pr + 0.3 + p / 2   # arc length from the top to the first pave stone
    z_p = r_out - 0.177 * p - 0.05                    # pave girdle depth: table just under the surface
    for side in (1, -1):
        for i in range(pave):
            ang = side * math.degrees((s0 + i * pitch) / r_out)
            pave_stones.append(brilliant(p, z_p).rotate(V(), Y, ang))
            seats.append(cq.Solid.makeCylinder(p / 2, 1.0, V(0, 0, z_p)).rotate(V(), Y, ang))
        for i in range(pave + 1 if pave else 0):
            ang = side * math.degrees((s0 + (i - 0.5) * pitch) / r_out)
            beads += [ball((0, s * p / 2, r_out - 0.05), 0.25 * p).rotate(V(), Y, ang) for s in (1, -1)]

    metal = band(r_in, band_width, band_thickness).fuse(*head, *beads).cut(center, *pave_stones, *seats)  # no .clean(): it breaks validity here
    stones = cq.Compound.makeCompound([center, *pave_stones])

    lean = math.degrees(math.atan2(seat[0] - r_foot, z_g - z_foot))
    culet_gap = setting_height - 0.431 * d
    under_pave = band_thickness - (r_out - z_p) - 0.431 * p
    checks = [
        (band_thickness < 1.2, f"band thickness {band_thickness} mm is under 1.2 mm"),
        (prong_mm < 0.8, f"prong diameter {prong_mm} mm is under 0.8 mm"),
        # ponytail: 45 deg prong lean is a rule of thumb for "head too wide for this band", not an FEA result
        (lean > 45, f"stone too wide for the band: prongs lean {lean:.0f} deg from the band (over 45)"),
        (culet_gap < 0.3, f"centre-stone culet only {culet_gap:.2f} mm above the band"),
        (pave and p > band_width - 0.4, f"pave stones {p} mm leave under 0.2 mm metal each side on a {band_width} mm band"),
        (pave and under_pave < 0.4, f"only {under_pave:.2f} mm of metal under the pave seats"),
        (not metal.isValid(), "metal solid is invalid (shape.isValid() is False)"),
    ]
    return metal, stones, [msg for bad, msg in checks if bad]


def finish(out, report, warns, strict, **solids):
    """Write <name>.step/.stl for each metal solid (STL only for 'stone') and report.json; return exit code."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, s in solids.items():
        if name != "stone":
            cq.exporters.export(s, str(out / f"{name}.step"))
        cq.exporters.export(s, str(out / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
    report["warnings"] = warns
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    for w in warns:
        print("WARNING:", w, file=sys.stderr)
    return 1 if strict and warns else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    size = ap.add_mutually_exclusive_group()
    size.add_argument("--size-us", type=float, default=6.0, help="US ring size (default 6)")
    size.add_argument("--size-eu", type=float, help="EU size = inner circumference in mm")
    ap.add_argument("--band-width", type=float, default=2.2)
    ap.add_argument("--band-thickness", type=float, default=1.7)
    ap.add_argument("--stone-mm", type=float, default=6.5, help="centre stone diameter (6.5 mm ~ 1 ct)")
    ap.add_argument("--prongs", type=int, choices=(4, 6), default=6)
    ap.add_argument("--setting-height", type=float, default=4.5, help="girdle height above the band top")
    ap.add_argument("--prong-mm", type=float, default=1.0, help="prong diameter")
    ap.add_argument("--pave", type=int, default=8, help="pave stones per shoulder (0 = off)")
    ap.add_argument("--pave-mm", type=float, default=1.3)
    ap.add_argument("--metal", choices=METALS, default="18k")
    ap.add_argument("--out", default="out")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any manufacturability warning")
    a = ap.parse_args()
    nums = [a.size_eu or a.size_us, a.band_width, a.band_thickness, a.stone_mm, a.setting_height, a.prong_mm, a.pave_mm]
    if min(nums) <= 0 or a.pave < 0:
        ap.error("sizes and dimensions must be positive")
    inner_d = a.size_eu / math.pi if a.size_eu else us_to_diameter(a.size_us)
    metal, stones, warns = build(inner_d, a.band_width, a.band_thickness, a.stone_mm, a.prongs,
                                 a.setting_height, a.prong_mm, a.pave, a.pave_mm)
    vol = metal.Volume()
    report = {"inner_diameter_mm": round(inner_d, 2), "metal_volume_mm3": round(vol, 1),
              "metal_weight_g": round(vol / 1000 * METALS[a.metal], 2), "parameters": vars(a)}
    return finish(a.out, report, warns, a.strict, ring=metal, stone=stones)


if __name__ == "__main__":
    sys.exit(main())
