"""Draw the Cinder Ward backdrop for the console's battlefield view.

Run from the repo root:  python scripts/gen_scene_backdrop.py
The picture is seeded, so the same code writes the same file. A change to the art shows up as a
diff in src/linkfall/web/assets/scene-cinder-ward.svg.
"""

import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src/linkfall/web/assets/scene-cinder-ward.svg"
SEED = 4217
WIDTH, HEIGHT, GROUND = 2400, 320, 250  # GROUND is the y of the ground line

DEFS = (
    "<defs>"
    '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#060819"/>'
    '<stop offset=".5" stop-color="#121752"/><stop offset=".78" stop-color="#2B2C78"/>'
    '<stop offset="1" stop-color="#4A3170"/></linearGradient>'
    '<radialGradient id="ember" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" '
    'gradientTransform="translate(1750 255) scale(820 230)">'
    '<stop offset="0" stop-color="#FF7A3D" stop-opacity=".62"/>'
    '<stop offset=".45" stop-color="#FF7A3D" stop-opacity=".2"/>'
    '<stop offset="1" stop-color="#FF7A3D" stop-opacity="0"/></radialGradient>'
    '<radialGradient id="cool" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" '
    'gradientTransform="translate(420 255) scale(620 190)">'
    '<stop offset="0" stop-color="#37D6F5" stop-opacity=".22"/>'
    '<stop offset="1" stop-color="#37D6F5" stop-opacity="0"/></radialGradient>'
    '<linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#5A5FC0" stop-opacity="0"/>'
    '<stop offset="1" stop-color="#5A5FC0" stop-opacity=".38"/></linearGradient>'
    '<linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#141842"/>'
    '<stop offset=".35" stop-color="#0A0C28"/><stop offset="1" stop-color="#04051A"/>'
    "</linearGradient>"
    '<radialGradient id="moon" cx=".35" cy=".35" r=".8"><stop offset="0" stop-color="#F4F1FF"/>'
    '<stop offset="1" stop-color="#9AA4E6"/></radialGradient>'
    '<mask id="crescent"><rect width="2400" height="320" fill="#000"/>'
    '<circle cx="470" cy="74" r="40" fill="#fff"/><circle cx="488" cy="64" r="38" fill="#000"/>'
    "</mask>"
    '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%">'
    '<feGaussianBlur stdDeviation="14"/></filter>'
    '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
    '<feGaussianBlur stdDeviation="6"/></filter>'
    "</defs>"
)
SMOKE_AT = (1320, 1610, 1905, 2210, 760)
FIRES_AT = (1320, 1610, 1905, 2210)


def stars(r: random.Random) -> list[str]:
    out = []
    for _ in range(230):
        x, y = r.uniform(0, WIDTH), r.uniform(0, 185)
        radius = r.choice([0.5, 0.6, 0.7, 0.8, 1, 1.3])
        opacity = round(r.uniform(0.25, 0.95) * (1 - y / 260), 2)
        out.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{radius}" fill="#FFF4E6" opacity="{opacity}"/>'
        )
    return out


def ridge(r: random.Random, base: float, amp: float, step: float, fill: str, opacity: float) -> str:
    points, x, y = [f"0,{GROUND}"], 0.0, base
    while x <= WIDTH:
        points.append(f"{x:.0f},{y:.0f}")
        x += r.uniform(step * 0.5, step * 1.5)
        y = max(base - amp, min(base + amp * 0.4, y + r.uniform(-amp * 0.45, amp * 0.45)))
    points += [f"{WIDTH},{y:.0f}", f"{WIDTH},{GROUND}"]
    return f'<polygon points="{" ".join(points)}" fill="{fill}" opacity="{opacity}"/>'


def smoke(r: random.Random) -> list[str]:
    out = []
    for cx in SMOKE_AT:
        top, lean, w = r.uniform(40, 90), r.uniform(-150, -70), r.uniform(12, 20)
        out.append(
            f'<path d="M{cx - w:.0f} {GROUND} '
            f"C{cx - w + lean * 0.2:.0f} {GROUND - 70:.0f} {cx + lean * 0.5 - w * 2:.0f} "
            f"{top + 60:.0f} {cx + lean - w * 3:.0f} {top:.0f} "
            f"L{cx + lean + w * 3:.0f} {top - 12:.0f} "
            f"C{cx + lean * 0.5 + w * 2:.0f} {top + 70:.0f} {cx + w + lean * 0.2:.0f} "
            f'{GROUND - 60:.0f} {cx + w:.0f} {GROUND} Z" '
            'fill="#23265E" opacity=".6" filter="url(#soft)"/>'
        )
    return out


def fires(r: random.Random) -> list[str]:
    out = []
    for cx in FIRES_AT:
        rx, ry = r.uniform(40, 70), r.uniform(14, 24)
        out.append(
            f'<ellipse cx="{cx}" cy="{GROUND - 6}" rx="{rx:.0f}" ry="{ry:.0f}" '
            'fill="#FF7A3D" opacity=".55" filter="url(#glow)"/>'
        )
        out.append(
            f'<ellipse cx="{cx}" cy="{GROUND - 4}" rx="16" ry="7" '
            'fill="#FFB07A" opacity=".8" filter="url(#glow)"/>'
        )
    return out


def building(r: random.Random, x: float, w: float, h: float, fill: str, ruin: float) -> list[str]:
    top = GROUND - h
    if r.random() < ruin:  # a broken top: jagged bites out of the roof
        n = r.randint(3, 5)
        points = [f"{x:.0f},{GROUND}", f"{x:.0f},{top + r.uniform(0, h * 0.3):.0f}"]
        points += [f"{x + w * i / n:.0f},{top + r.uniform(-4, h * 0.45):.0f}" for i in range(1, n)]
        points += [f"{x + w:.0f},{top + r.uniform(0, h * 0.5):.0f}", f"{x + w:.0f},{GROUND}"]
        return [f'<polygon points="{" ".join(points)}" fill="{fill}"/>']
    out = [f'<rect x="{x:.0f}" y="{top:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{fill}"/>']
    if r.random() < 0.3:  # a mast
        mast_top = top - r.uniform(10, 26)
        out.append(
            f'<rect x="{x + w * 0.45:.0f}" y="{mast_top:.0f}" width="2" height="26" fill="{fill}"/>'
        )
    return out


def skyline(
    r: random.Random,
    fill: str,
    heights: tuple[float, float],
    widths: tuple[float, float],
    gap: float,
    lit: int,
    ruin: float,
) -> list[str]:
    out, x = [], -20.0
    while x < WIDTH:
        w = r.uniform(*widths)
        h = r.uniform(*heights) * (1.35 if x > 1100 else 1.0)  # taller on the enemy side
        out += building(r, x, w, h, fill, ruin)
        for _ in range(lit):
            if r.random() < 0.5 and h > 30:
                wx = x + r.uniform(4, w - 6)
                wy = GROUND - h + r.uniform(h * 0.35, h - 8)
                color = "#FFB07A" if x > 1000 else "#8AEAFF"
                out.append(
                    f'<rect x="{wx:.0f}" y="{wy:.0f}" width="3" height="4" fill="{color}" '
                    f'opacity="{r.uniform(0.35, 0.85):.2f}"/>'
                )
        x += w + r.uniform(0, gap)
    return out


def ground(r: random.Random) -> list[str]:
    out = [
        f'<rect y="{GROUND}" width="{WIDTH}" height="{HEIGHT - GROUND}" fill="url(#ground)"/>',
        f'<rect y="{GROUND}" width="{WIDTH}" height="1.5" fill="#96AAFF" opacity=".28"/>',
        f'<ellipse cx="1750" cy="{GROUND + 6}" rx="700" ry="16" fill="#FF7A3D" opacity=".16" '
        'filter="url(#glow)"/>',
    ]
    for _ in range(26):  # craters, flatter toward the horizon
        y = r.uniform(GROUND + 8, HEIGHT - 8)
        depth = (y - GROUND) / (HEIGHT - GROUND)
        x = r.uniform(0, WIDTH)
        rx = 18 + 60 * depth * r.uniform(0.6, 1.2)
        out.append(
            f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rx:.0f}" ry="{rx * 0.16:.1f}" '
            'fill="#030414" opacity=".55"/>'
        )
        out.append(
            f'<path d="M{x - rx:.0f} {y:.0f} A{rx:.0f} {rx * 0.16:.1f} 0 0 1 {x + rx:.0f} {y:.0f}" '
            'stroke="#96AAFF" stroke-opacity=".16" fill="none"/>'
        )
    x, points = 0.0, [f"0,{HEIGHT}"]
    while x <= WIDTH:  # rubble along the bottom edge
        points.append(f"{x:.0f},{HEIGHT - r.uniform(2, 16):.0f}")
        x += r.uniform(14, 60)
    points.append(f"{WIDTH},{HEIGHT}")
    out.append(f'<polygon points="{" ".join(points)}" fill="#02030F"/>')
    return out


def backdrop() -> str:
    r = random.Random(SEED)  # noqa: S311 - picture layout, not a secret
    full = f'width="{WIDTH}" height="{HEIGHT}"'
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" {full}>',
        DEFS,
        f'<rect {full} fill="url(#sky)"/>',
        *stars(r),
        '<circle cx="470" cy="74" r="62" fill="#9AA4E6" opacity=".12" filter="url(#glow)"/>',
        '<rect width="2400" height="320" fill="url(#moon)" mask="url(#crescent)"/>',
        f'<rect {full} fill="url(#ember)"/><rect {full} fill="url(#cool)"/>',
        ridge(r, 178, 34, 70, "#1C2166", 0.75),
        ridge(r, 200, 22, 46, "#161A56", 0.9),
        *smoke(r),
        *fires(r),
        *skyline(r, "#111546", (40, 118), (26, 64), 18, 2, 0.4),
        f'<rect y="{GROUND - 60}" width="{WIDTH}" height="60" fill="url(#haze)"/>',
        *skyline(r, "#090B2A", (16, 62), (36, 96), 50, 2, 0.6),
        *ground(r),
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    OUT.write_text(backdrop(), encoding="utf-8")
