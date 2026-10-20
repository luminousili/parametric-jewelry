"""Plain-assert checks. Run: .venv/bin/python test_ring.py"""
import subprocess, sys, tempfile
import bangle, ring

# US size -> inner diameter, against a published chart (US 6 = 16.5 mm, US 9 = 18.9 mm)
assert abs(ring.us_to_diameter(6) - 16.5) < 0.05
assert abs(ring.us_to_diameter(9) - 18.9) < 0.05

metal, stones, warns = ring.build(ring.us_to_diameter(6), prongs=4, pave=0)
assert metal.isValid() and stones.isValid() and warns == [], warns
assert len(metal.Solids()) == 1  # head, prongs and band are one piece of metal

narrow = ring.build(16.5, band_width=2.0, pave=0)[0].Volume()
wide = ring.build(16.5, band_width=3.0, pave=0)[0].Volume()
assert wide > narrow, (narrow, wide)

with tempfile.TemporaryDirectory() as out:
    cmd = [sys.executable, "ring.py", "--prong-mm", "0.6", "--pave", "0", "--strict", "--out", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 1 and "prong diameter 0.6" in p.stderr, p.stderr

# Bangle: --target-grams lands within 1% of the target, and the solid is valid
kw = dict(inner_d=62, width=6, pattern="plain", gap=20, caps=3)
t = bangle.solve_thickness(15.0, ring.METALS["22k"], **kw)
b, warns = bangle.build(thickness=t, **kw)
grams = b.Volume() / 1000 * ring.METALS["22k"]
assert abs(grams - 15.0) / 15.0 < 0.01, grams
assert b.isValid() and warns == [], warns
assert bangle.build(62, 3.5, 2.5, "twist")[0].isValid()

print("all tests passed")
