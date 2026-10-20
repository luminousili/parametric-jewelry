# parametric-ring

Python + CadQuery scripts that generate jewelry from a few numbers. The solitaire ring has a 6-prong crown head with a collar and pavé shoulders. The bangle (Turkish *bilezik*) can be plain, a twist, dimpled or pierced with a honeycomb, closed or an open cuff with rose-bud terminals. Each script writes a manufacturable STEP and STL, an STL of the stones, and a `report.json` with the metal weight and manufacturability warnings.

![Generated ring](docs/ring-hero.png)
![Generated bangle: pierced hex cuff with rose-bud terminals](docs/bangle-hero.png)

| Original Rhino/Matrix Gold render | Generated from code |
|---|---|
| ![reference ring](docs/reference-ring.jpg) | ![generated ring](docs/ring-hero.png) |
| ![reference bangle](docs/reference-bangle.jpg) | ![generated bangle](docs/bangle-hero.png) |

More ring variants: [docs/ring-variants.png](docs/ring-variants.png). The left image is US 6 with 4 prongs and no pavé. The right image is US 7 with an 8 mm stone and 6 × 1.5 mm pavé. More bangle variants (dimpled cuff, plain, twist): [docs/bangles.png](docs/bangles.png).

## Quick start

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python ring.py --size-us 6 --stone-mm 6.5 --prongs 6      # -> out/ring.step, ring.stl, stone.stl, report.json
.venv/bin/python bangle.py --width 5 --pattern hex --open-gap 40 --roses --target-grams 35   # ~80 s
.venv/bin/python test_ring.py                                        # plain asserts, ~2 min
```

Warnings go to stderr. Add `--strict` to make the exit code 1 when any check fails, for example in CI.

## Ring parameters (`ring.py`)

| Flag | Default | Meaning |
|---|---|---|
| `--size-us` / `--size-eu` | US 6 | Ring size. US: d = 11.63 + 0.8128 × size mm. EU: inner circumference in mm |
| `--band-width` | 2.2 | Band width, mm |
| `--band-thickness` | 1.7 | Band thickness, mm (comfort-fit profile) |
| `--stone-mm` | 6.5 | Centre stone diameter (6.5 mm ≈ 1 ct round brilliant) |
| `--prongs` | 6 | 4 or 6 |
| `--setting-height` | 4.5 | Girdle height above the band top, mm |
| `--prong-mm` | 1.0 | Prong wire diameter |
| `--pave` / `--pave-mm` | 8 / 1.3 | Pavé stones per shoulder (0 = off) and their diameter |
| `--metal` | 18k | 18k, 14k, 22k, sterling, platinum |

These checks produce warnings: band thinner than 1.2 mm; prong thinner than 0.8 mm; prongs leaning more than 45° (stone too wide for the band); culet less than 0.3 mm above the band; pavé too wide for the band or too little metal under the seats; and an invalid solid.

Example `out/report.json` (default ring, 18k):

```json
{
  "inner_diameter_mm": 16.51,
  "metal_volume_mm3": 218.5,
  "metal_weight_g": 3.39,
  "parameters": { "size_us": 6.0, "prongs": 6, "stone_mm": 6.5, "pave": 8, "pave_mm": 1.3, "metal": "18k", "...": "..." },
  "warnings": []
}
```

## Bangle (`bangle.py`)

| Flag | Default | Meaning |
|---|---|---|
| `--inner-diameter` | 62 | mm (a medium adult bangle) |
| `--width` / `--thickness` | 6 / 1.5 | mm |
| `--target-grams` | none | Solve the thickness by bisection so the finished piece (including texture and caps) weighs this much |
| `--metal` | 22k | Same metals as the ring |
| `--pattern` | plain | `plain`, `twist` (burma twist), `texture` (hex-packed dimples) or `hex` (honeycomb pierced through the band, solid rims along both edges) |
| `--open-gap` | 0 | Cuff opening in mm (0 = closed) |
| `--end-caps` | 0 | Raised rings at each open end |
| `--roses` | off | Rose-bud terminal at each open end: calyx of 5 pointed sepals, 3 outer and 2 inner petals, a core, and a collar ring |

The solved thickness and weight go into `report.json`. A thickness under 0.8 mm produces a warning. Example: the hero cuff (22k, 5 mm wide, hex piercing, 40 mm opening, roses), targeting 35 g, solves to 1.97 mm and 34.96 g. The holes and the roses are part of the weighed solid. The hex solve takes about 80 seconds and the dimpled one about 2–3 minutes, because every bisection step rebuilds the cuts. A plain solve takes about 2 seconds.

## Regenerating the previews

The previews are rendered with Blender (headless Cycles):

```sh
.venv/bin/python ring.py --out out/ring-hero
.venv/bin/python ring.py --prongs 4 --pave 0 --out out/ring-us6
.venv/bin/python ring.py --size-us 7 --stone-mm 8 --band-width 2.6 --pave 6 --pave-mm 1.5 --out out/ring-us7
.venv/bin/python bangle.py --width 5 --pattern hex --open-gap 40 --roses --target-grams 35 --out out/bangle-rose
.venv/bin/python bangle.py --pattern texture --open-gap 25 --end-caps 3 --target-grams 20 --out out/bangle-cuff
.venv/bin/python bangle.py --target-grams 20 --out out/bangle-plain
.venv/bin/python bangle.py --pattern twist --width 3.5 --thickness 2.5 --out out/bangle-twist
blender -b -P render.py -- docs/ring-hero.png out/ring-hero/ring.stl+out/ring-hero/stone.stl
blender -b -P render.py -- docs/ring-variants.png out/ring-us6/ring.stl+out/ring-us6/stone.stl out/ring-us7/ring.stl+out/ring-us7/stone.stl
blender -b -P render.py -- docs/bangle-hero.png --tilt=40 out/bangle-rose/bangle.stl
blender -b -P render.py -- docs/bangles.png --tilt=30 out/bangle-cuff/bangle.stl out/bangle-plain/bangle.stl out/bangle-twist/bangle.stl
```

## Limitations

- The stones are simplified: 16-sided ruled lofts with Tolkowsky-like proportions, not a real 57-facet brilliant.
- The 45° prong-lean check is a rule of thumb, not a stress analysis.
- The "platinum" density (21.45) is pure platinum. Pt950 is about 20.1–20.7 g/cm³.
- The twist bangle keeps the section diagonal at the inner diameter, so the bore is slightly larger where the flats face inward.
- The rose buds are smooth revolved petals with pointed tips. The curled petal lips and the spiral centre of the reference are not modelled. The reference band is a round tube, while this one keeps the comfort-fit band profile.
- The hex holes are straight radial prisms (0.9 mm across flats, 0.4 mm walls), so the walls are slightly thinner on the inside face. The dimple texture is coarse (1.6 mm pitch).
- `.clean()` is skipped on the final solids because it made them invalid. The STL exports are not guaranteed watertight, but their volume matches the B-rep.

## About

Built by a jewelry CAD designer directing Claude Code (AI coding agent): I defined the jewelry constraints and checks, the agent wrote the code, and I reviewed the output.

License: MIT.
