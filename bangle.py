#!/usr/bin/env python3
"""Parametric bangle (Turkish "bilezik"): plain, burma twist, dimple texture or pierced honeycomb; closed or
open cuff with ribbed end caps and/or rose-bud terminals. --target-grams solves the thickness so the piece weighs N grams in the metal.

Axes: wrist along Y, bangle in the XZ plane. Angle a means the +X point rotated by a about +Y. Units: mm.
"""
import argparse, functools, math, sys
import cadquery as cq
from ring import DOME, METALS, V, Y, band, finish

DIMPLE_PITCH, DIMPLE_R, DIMPLE_DEPTH = 1.6, 0.65, 0.3
HEX_HOLE, HEX_WEB, HEX_RIM = 0.9, 0.4, 0.7   # hex hole across flats, wall between holes, solid edge strip (mm)
PETAL = 0.7                                   # petal and sepal wall thickness (mm), a common casting minimum
X = cq.Vector(1, 0, 0)


def shell(pts, span, rot, drop, th=PETAL):
    """One petal or sepal: a thin profile (outer face through pts as (r, y), bud axis = Y) revolved over
    span degrees, centred on rot, with its top edge cut to a point that falls by drop at the sides."""
    inner = [(r - th, y) for r, y in reversed(pts)]
    prof = (cq.Workplane("XY").moveTo(*pts[0]).spline(pts[1:], includeCurrent=True).lineTo(*inner[0])
            .spline(inner[1:], includeCurrent=True).close())
    s = prof.revolve(span, (0, 0, 0), (0, 1, 0)).val().rotate(V(), Y, -span / 2)  # centred on +X
    top, side = pts[-1][1], pts[-1][0] * math.sin(math.radians(min(span / 2, 90)))
    gable = (cq.Workplane("YZ").polyline([(-100, -50), (top - drop * 50 / side, -50), (top, 0),
                                          (top - drop * 50 / side, 50), (-100, 50)]).close().extrude(50, both=True).val())
    return s.intersect(gable).rotate(V(), Y, rot)


@functools.lru_cache   # same bud for every thickness step of --target-grams
def rose(s):
    """Simplified rose bud of scale s (mm), axis +Z, base at the origin: stem, 5 sepals, 3 outer and
    2 inner petals, closed core. ponytail: smooth revolved petals; no curled lips or spiral centre."""
    sc = lambda pts: [(r * s, y * s) for r, y in pts]
    parts = [cq.Solid.makeCylinder(0.3 * s, 0.55 * s, V(0, -0.5, 0), Y)]                    # stem into the band
    parts += [shell(sc([(0.32, 0.0), (0.58, 0.2), (0.8, 0.45), (1.0, 0.62)]), 44, 72 * k + 36, 0.4 * s)
              for k in range(5)]                                                           # pointed sepals, flared out
    parts += [shell(sc([(0.28, 0.12), (0.6, 0.45), (0.76, 0.95), (0.72, 1.35), (0.88, 1.75)]), 150, 120 * k, 0.3 * s)
              for k in range(3)]                                                           # outer petals
    parts += [shell(sc([(0.22, 0.3), (0.45, 0.7), (0.54, 1.1), (0.52, 1.55)]), 230, 60 + 180 * k, 0.2 * s)
              for k in range(2)]                                                           # inner petals
    core = cq.Workplane("XY").moveTo(0, 0.2 * s).spline(sc([(0.3, 0.75), (0.2, 1.3)]), includeCurrent=True)
    parts.append(core.lineTo(0, 1.42 * s).close().revolve(360, (0, 0, 0), (0, 1, 0)).val())
    return parts[0].fuse(*parts[1:]).rotate(V(), X, 90)                                    # bud axis Y -> +Z


def build(inner_d, width, thickness, pattern="plain", gap=0.0, caps=0, roses=False):
    """Returns (metal solid, warnings)."""
    r_in, w, t = inner_d / 2, width, thickness
    span = 360 - math.degrees(gap / r_in)
    tube = pattern == "hex"
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
    elif tube:
        # Round tube, diameter w mid-arc growing to 1.5 w at the open ends, hollow with wall t (solid when
        # t is near w/2). The bore stays at r_in. ponytail: open cuffs are lofted through circles every
        # ~25 deg, so the centre line is a spline that hugs the arc rather than a true arc.
        d = lambda a: w * (1 + 0.5 * abs(2 * a / span - 1) ** 3)
        def loft(a0, a1, wall):
            secs = []
            for a in (a0 + (a1 - a0) * k / 12 for k in range(13)):
                u = V(math.cos(math.radians(a)), 0, -math.sin(math.radians(a)))
                secs.append(cq.Wire.makeCircle(d(a) / 2 - wall, u * (r_in + d(a) / 2), Y.cross(u)))  # normal = tangent
            return cq.Solid.makeLoft(secs)
        ring = lambda r: cq.Workplane("XY").moveTo(r_in + w / 2, 0).circle(r).revolve(360, (0, 0, 0), (0, 1, 0)).val()
        cap = math.degrees(1.0 / r_in)                                   # 1 mm closed end before the void starts
        body = loft(0, span, 0) if gap else ring(w / 2)
        if t < w / 2 - 0.15:
            body = body.cut(loft(cap, span - cap, t) if gap else ring(w / 2 - t))
        W = T = 1.5 * w if gap else w                                     # tube diameter at the open ends
    else:
        body, W, T = band(r_in, w, t, span), w, t

    tools = []
    margin = (caps * 1.5 + 1.0 + 1.5 * bool(roses)) if gap else 0.0     # keep patterns clear of the ends
    if pattern == "hex":
        # Honeycomb on the inner face of the tube: prisms run from inside the bore to the tube centre line,
        # so they pierce the inner wall into the hollow and never reach the smooth outer face. One column
        # is built, then copied round the arc; all copies are cut in one boolean.
        # ponytail: straight radial prisms; where t is near w/2 (solid tube) they become blind pockets.
        pitch = HEX_HOLE + HEX_WEB
        col_pitch, reach = pitch * math.sqrt(3) / 2, 0.3 * w                    # two staggered rows at w = 4
        prism = (cq.Workplane("YZ", origin=(r_in - 1, 0, 0)).polygon(6, HEX_HOLE / math.cos(math.pi / 6))
                 .extrude(1 + w / 2).val().rotate(V(), X, 30))                    # vertices along the arc
        cols = [[prism.translate(V(0, y * pitch, 0)) for y in range(-20, 21) if abs(y * pitch) <= reach],
                [prism.translate(V(0, (y + 0.5) * pitch, 0)) for y in range(-20, 20) if abs((y + 0.5) * pitch) <= reach]]
        rm = r_in
        arc = math.radians(span) * rm - 2 * margin
        n = int(arc / col_pitch) if gap else int(arc / col_pitch / 2) * 2         # closed ring: even, so it tiles
        for k in range(n):
            a = math.degrees((margin + (k + 0.5 * bool(gap)) * arc / n) / rm)
            tools += [p.rotate(V(), Y, a) for p in cols[k % 2]]
    if pattern == "texture":
        # Hex-packed spherical dimples over the outside face (outer arc of the band profile).
        # ponytail: ~1.6 mm pitch keeps it to a few hundred booleans (~5-10 s); finer needs a mesh workflow.
        e = DOME * t
        rho = ((w / 2) ** 2 + e ** 2) / (2 * e)                          # outer arc radius in the profile
        row = DIMPLE_PITCH * 0.866
        rows = int((w - 2 * DIMPLE_R) / row) + 1
        for j in range(rows):
            y = (j - (rows - 1) / 2) * row
            rs = r_in + t - rho + math.sqrt(rho ** 2 - y ** 2)           # outer surface radius at this y
            arc = math.radians(span) * rs - 2 * margin
            m = int(arc / DIMPLE_PITCH)
            for k in range(m):
                s = margin + (k + 0.5 + 0.5 * (j % 2)) * arc / m if gap else (k + 0.5 * (j % 2)) * arc / m
                ball = cq.Solid.makeSphere(DIMPLE_R, V(rs + DIMPLE_R - DIMPLE_DEPTH, y, 0), V(0, 0, 1), -90)
                tools.append(ball.rotate(V(), Y, math.degrees(s / rs)))  # sphere poles along the tangent

    # Collar rings at each open end (--end-caps, and one under each rose): 0.8 mm rings, 1.5 mm apart.
    collars = []
    ring_a, pitch_a = math.degrees(0.8 / r_in), math.degrees(1.5 / r_in)
    if tube:
        ring = cq.Solid.makeTorus(T / 2, 0.45, V(r_in + T / 2, 0, 0), V(0, 0, 1)).rotate(V(), Y, ring_a / 2)
    else:
        ring = band(r_in, W + 0.6, T + 0.3, ring_a)
    for k in range(max(caps, bool(roses)) if gap else 0):
        collars += [ring.rotate(V(), Y, k * pitch_a), ring.rotate(V(), Y, span - k * pitch_a - ring_a)]

    if gap and roses:
        # Rose bud at each open end, turned half the opening angle inward so the two buds face each other.
        bud = rose(1.25 * W).rotate(V(), Y, -(360 - span) / 2).translate(V(r_in + T / 2, 0, 0))
        collars += [bud, bud.rotate(V(), X, 180).rotate(V(), Y, span)]                # mirror to the far end

    metal = body.cut(*tools) if tools else body                      # patterns stay clear of the ends,
    metal = metal.fuse(*collars) if collars else metal               # so cut first, on the simpler body
    # no .clean(): it can break validity
    checks = [
        (t < 0.8, f"{'tube wall' if tube else 'thickness'} {t:.2f} mm is under 0.8 mm"),
        (caps and not gap, "end caps need an open bangle (--open-gap > 0); none made"),
        (roses and not gap, "rose terminals need an open bangle (--open-gap > 0); none made"),
        (not metal.isValid(), "metal solid is invalid (shape.isValid() is False)"),
    ]
    return metal, [msg for bad, msg in checks if bad]


def solve_thickness(target_g, density, lo=0.3, hi=6.0, **kw):
    """Bisection on thickness until the full solid (texture, caps included) weighs target_g within 0.3%.
    ponytail: rebuilds the whole solid every step (~8-10 builds): ~2 s plain, ~2 min textured, ~3 min hex tube + roses."""
    if kw.get("pattern") == "hex":
        hi = min(hi, kw["width"] / 2)  # wall past the tube radius is just a solid tube
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
    ap.add_argument("--width", type=float, default=6.0, help="band width; tube diameter mid-arc for --pattern hex")
    ap.add_argument("--thickness", type=float, default=1.5, help="band thickness; tube wall for --pattern hex. Solved by --target-grams")
    ap.add_argument("--target-grams", type=float, help="solve thickness for this metal weight")
    ap.add_argument("--metal", choices=METALS, default="22k")
    ap.add_argument("--pattern", choices=("plain", "twist", "texture", "hex"), default="plain")
    ap.add_argument("--open-gap", type=float, default=0.0, help="cuff opening in mm (0 = closed)")
    ap.add_argument("--end-caps", type=int, default=0, help="raised rings at each open end")
    ap.add_argument("--roses", action="store_true", help="rose-bud terminals at the open ends")
    ap.add_argument("--out", default="out/bangle")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any manufacturability warning")
    a = ap.parse_args()
    if min(a.inner_diameter, a.width, a.thickness, a.target_grams or 1) <= 0 or a.open_gap < 0 or a.end_caps < 0:
        ap.error("dimensions and weights must be positive")
    if a.open_gap >= math.pi * a.inner_diameter * 0.5:
        ap.error("--open-gap must be under half the inner circumference")
    kw = dict(inner_d=a.inner_diameter, width=a.width, pattern=a.pattern, gap=a.open_gap, caps=a.end_caps, roses=a.roses)
    t = solve_thickness(a.target_grams, METALS[a.metal], **kw) if a.target_grams else a.thickness
    metal, warns = build(thickness=t, **kw)
    vol = metal.Volume()
    report = {"inner_diameter_mm": a.inner_diameter, "thickness_mm": round(t, 3), "metal_volume_mm3": round(vol, 1),
              "metal_weight_g": round(vol / 1000 * METALS[a.metal], 2), "parameters": vars(a)}
    return finish(a.out, report, warns, a.strict, bangle=metal)


if __name__ == "__main__":
    sys.exit(main())
