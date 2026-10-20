#!/usr/bin/env python3
"""Parametric bangle (Turkish "bilezik"): plain, burma twist or dimple texture; closed or open cuff
with ribbed end caps. --target-grams solves the thickness so the piece weighs N grams in the metal.

Axes: wrist along Y, bangle in the XZ plane. Angle a means the +X point rotated by a about +Y. Units: mm.
"""
import argparse, math, sys
import cadquery as cq
from ring import DOME, METALS, V, Y, band, finish

DIMPLE_PITCH, DIMPLE_R, DIMPLE_DEPTH = 1.6, 0.65, 0.3


def build(inner_d, width, thickness, pattern="plain", gap=0.0, caps=0):
    """Returns (metal solid, warnings)."""
    r_in, w, t = inner_d / 2, width, thickness
    span = 360 - math.degrees(gap / r_in)
    if pattern == "twist":
        # Burma twist: rounded-rectangle section swept round the circle while rotating, steered by an
        # auxiliary spine wound around the path. ponytail: inner diameter is kept at the section's
        # diagonal (worst case), so the bore is slightly larger where the flats face inward.
        h = math.hypot(w, t) / 2
        R, W, T = r_in + h, 2 * h, 2 * h
        turns = max(1, round(math.radians(span) * r_in / (3 * w)))     # one full turn per ~3 widths
        path = cq.Wire.assembleEdges([cq.Edge.makeCircle(R, V(), Y, 0, span).rotate(V(), Y, 90)])  # start at +X
        n = 16 * turns
        aux = []
        for k in range(n + (gap > 0)):
            a = math.radians(span) * k / n
            ph = 2 * math.pi * turns * k / n
            radial = V(math.cos(a), 0, -math.sin(a))
            aux.append(radial * R + (radial * math.cos(ph) + Y * math.sin(ph)) * h)
        aux = cq.Wire.assembleEdges([cq.Edge.makeSpline(aux, periodic=gap == 0)])
        section = cq.Workplane("XY", origin=(R, 0, 0)).sketch().rect(t, w).vertices().fillet(min(w, t) / 4).finalize()
        body = section.sweep(cq.Workplane().add(path), auxSpine=cq.Workplane().add(aux)).val()
    else:
        body, W, T = band(r_in, w, t, span), w, t

    tools = []
    if pattern == "texture":
        # Hex-packed spherical dimples over the outside face (outer arc of the band profile).
        # ponytail: ~1.6 mm pitch keeps it to a few hundred booleans (~5-10 s); finer needs a mesh workflow.
        e = DOME * t
        rho = ((w / 2) ** 2 + e ** 2) / (2 * e)                          # outer arc radius in the profile
        row = DIMPLE_PITCH * 0.866
        rows = int((w - 2 * DIMPLE_R) / row) + 1
        margin = (caps * 1.5 + 1.0) if gap else 0.0                       # keep clear of the end caps
        for j in range(rows):
            y = (j - (rows - 1) / 2) * row
            rs = r_in + t - rho + math.sqrt(rho ** 2 - y ** 2)           # outer surface radius at this y
            arc = math.radians(span) * rs - 2 * margin
            m = int(arc / DIMPLE_PITCH)
            for k in range(m):
                s = margin + (k + 0.5 + 0.5 * (j % 2)) * arc / m if gap else (k + 0.5 * (j % 2)) * arc / m
                ball = cq.Solid.makeSphere(DIMPLE_R, V(rs + DIMPLE_R - DIMPLE_DEPTH, y, 0), V(0, 0, 1), -90)
                tools.append(ball.rotate(V(), Y, math.degrees(s / rs)))  # sphere poles along the tangent

    collars = []
    if gap and caps:
        ring_a, pitch_a = math.degrees(0.8 / r_in), math.degrees(1.5 / r_in)  # 0.8 mm rings, 1.5 mm apart
        for k in range(caps):
            for start in (k * pitch_a, span - k * pitch_a - ring_a):
                collars.append(band(r_in, W + 0.6, T + 0.3, ring_a).rotate(V(), Y, start))

    metal = body.fuse(*collars) if collars else body
    metal = metal.cut(*tools) if tools else metal                    # no .clean(): it can break validity
    checks = [
        (t < 0.8, f"thickness {t:.2f} mm is under 0.8 mm"),
        (caps and not gap, "end caps need an open bangle (--open-gap > 0); none made"),
        (not metal.isValid(), "metal solid is invalid (shape.isValid() is False)"),
    ]
    return metal, [msg for bad, msg in checks if bad]


def solve_thickness(target_g, density, lo=0.3, hi=6.0, **kw):
    """Bisection on thickness until the full solid (texture, caps included) weighs target_g within 0.3%.
    ponytail: rebuilds the whole solid every step (~8-10 builds): ~2 s plain, ~2 min textured."""
    for _ in range(40):
        mid = (lo + hi) / 2
        grams = build(thickness=mid, **kw)[0].Volume() / 1000 * density
        if abs(grams - target_g) <= 0.003 * target_g:
            return mid
        lo, hi = (mid, hi) if grams < target_g else (lo, mid)
    raise SystemExit(f"{target_g} g is not reachable with thickness {lo:.1f}-{hi:.1f} mm at this width")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inner-diameter", type=float, default=62.0, help="mm (62 = medium adult bangle)")
    ap.add_argument("--width", type=float, default=6.0)
    ap.add_argument("--thickness", type=float, default=1.5, help="ignored when --target-grams is set")
    ap.add_argument("--target-grams", type=float, help="solve thickness for this metal weight")
    ap.add_argument("--metal", choices=METALS, default="22k")
    ap.add_argument("--pattern", choices=("plain", "twist", "texture"), default="plain")
    ap.add_argument("--open-gap", type=float, default=0.0, help="cuff opening in mm (0 = closed)")
    ap.add_argument("--end-caps", type=int, default=0, help="raised rings at each open end")
    ap.add_argument("--out", default="out/bangle")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any manufacturability warning")
    a = ap.parse_args()
    if min(a.inner_diameter, a.width, a.thickness, a.target_grams or 1) <= 0 or a.open_gap < 0 or a.end_caps < 0:
        ap.error("dimensions and weights must be positive")
    if a.open_gap >= math.pi * a.inner_diameter * 0.5:
        ap.error("--open-gap must be under half the inner circumference")
    kw = dict(inner_d=a.inner_diameter, width=a.width, pattern=a.pattern, gap=a.open_gap, caps=a.end_caps)
    t = solve_thickness(a.target_grams, METALS[a.metal], **kw) if a.target_grams else a.thickness
    metal, warns = build(thickness=t, **kw)
    vol = metal.Volume()
    report = {"inner_diameter_mm": a.inner_diameter, "thickness_mm": round(t, 3), "metal_volume_mm3": round(vol, 1),
              "metal_weight_g": round(vol / 1000 * METALS[a.metal], 2), "parameters": vars(a)}
    return finish(a.out, report, warns, a.strict, bangle=metal)


if __name__ == "__main__":
    sys.exit(main())
