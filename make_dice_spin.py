#!/usr/bin/env python3

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


OUT_DIR = Path("/Users/hmi/Documents/core3s/uiflow_upload/dice")
FRAME_COUNT = 36
SIZE = 168
HALF = 1.0
DIST = 6.4
SCALE = 200.0
CENTER_X = 84.0
CENTER_Y = 82.0


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(dot(v, v))
    return (v[0] / length, v[1] / length, v[2] / length)


def rotate_x(v: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def rotate_y(v: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def rotate_z(v: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c - y * s, x * s + y * c, z)


def rotate(v: tuple[float, float, float], rx: float, ry: float, rz: float) -> tuple[float, float, float]:
    return rotate_z(rotate_y(rotate_x(v, rx), ry), rz)


def project(v: tuple[float, float, float]) -> tuple[float, float]:
    depth = DIST - v[2]
    scale = SCALE / depth
    return (CENTER_X + v[0] * scale, CENTER_Y - v[1] * scale)


PIPS = {
    1: [(0.5, 0.5)],
    2: [(0.25, 0.25), (0.75, 0.75)],
    3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
    4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
    6: [(0.25, 0.22), (0.75, 0.22), (0.25, 0.5), (0.75, 0.5), (0.25, 0.78), (0.75, 0.78)],
}


FACES = [
    {
        "value": 1,
        "center": (0.0, 1.0, 0.0),
        "u": (1.0, 0.0, 0.0),
        "v": (0.0, 0.0, -1.0),
    },
    {
        "value": 6,
        "center": (0.0, -1.0, 0.0),
        "u": (1.0, 0.0, 0.0),
        "v": (0.0, 0.0, 1.0),
    },
    {
        "value": 2,
        "center": (0.0, 0.0, 1.0),
        "u": (1.0, 0.0, 0.0),
        "v": (0.0, 1.0, 0.0),
    },
    {
        "value": 5,
        "center": (0.0, 0.0, -1.0),
        "u": (-1.0, 0.0, 0.0),
        "v": (0.0, 1.0, 0.0),
    },
    {
        "value": 3,
        "center": (1.0, 0.0, 0.0),
        "u": (0.0, 0.0, -1.0),
        "v": (0.0, 1.0, 0.0),
    },
    {
        "value": 4,
        "center": (-1.0, 0.0, 0.0),
        "u": (0.0, 0.0, 1.0),
        "v": (0.0, 1.0, 0.0),
    },
]


def face_polygon(center: tuple[float, float, float], u: tuple[float, float, float], v: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    return [
        add(center, add(mul(u, -HALF), mul(v, -HALF))),
        add(center, add(mul(u, HALF), mul(v, -HALF))),
        add(center, add(mul(u, HALF), mul(v, HALF))),
        add(center, add(mul(u, -HALF), mul(v, HALF))),
    ]


def face_point(
    center: tuple[float, float, float],
    u: tuple[float, float, float],
    v: tuple[float, float, float],
    px: float,
    py: float,
) -> tuple[float, float, float]:
    return add(center, add(mul(u, (px - 0.5) * 2.0 * HALF), mul(v, (py - 0.5) * 2.0 * HALF)))


def draw_frame(index: int) -> None:
    t = index / FRAME_COUNT
    spin = math.tau * t
    rx = 0.82 + spin * 1.08 + 0.34 * math.sin(spin * 2.0 + 0.20)
    ry = 0.64 + spin * 1.62 + 0.30 * math.sin(spin * 3.0 + 1.10)
    rz = -0.14 + spin * 2.55 + 0.18 * math.cos(spin * 2.0 - 0.45)

    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    draw = ImageDraw.Draw(image)

    shadow_w = 120 + int(12 * math.sin(math.tau * t))
    shadow_h = 32 + int(5 * math.cos(math.tau * t * 2.0))
    shadow_draw.ellipse(
        (
            CENTER_X - shadow_w / 2,
            138 - shadow_h / 2,
            CENTER_X + shadow_w / 2,
            138 + shadow_h / 2,
        ),
        fill=(8, 12, 18, 72),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    image.alpha_composite(shadow)

    light = norm((-0.35, 0.85, 1.0))
    visible = []

    for face in FACES:
        normal = rotate(norm(face["center"]), rx, ry, rz)
        if normal[2] <= 0.0:
            continue

        center = rotate(mul(face["center"], HALF), rx, ry, rz)
        u = rotate(face["u"], rx, ry, rz)
        v = rotate(face["v"], rx, ry, rz)
        polygon_3d = face_polygon(center, u, v)
        polygon_2d = [project(p) for p in polygon_3d]

        brightness = clamp(0.62 + dot(normal, light) * 0.32, 0.45, 1.0)
        base = int(232 * brightness)
        face_fill = (base, base + 5 if base < 250 else 255, min(255, base + 10), 255)
        face_line = (190, 196, 205, 255)
        depth = sum(p[2] for p in polygon_3d) / 4.0
        visible.append((depth, face, center, u, v, polygon_2d, face_fill, face_line))

    visible.sort(key=lambda item: item[0])

    for _depth, face, center, u, v, polygon_2d, face_fill, face_line in visible:
        draw.polygon(polygon_2d, fill=face_fill)
        draw.line(polygon_2d + [polygon_2d[0]], fill=face_line, width=1)

        center_2d = project(center)
        ux = project(add(center, mul(u, 0.34)))
        vx = project(add(center, mul(v, 0.34)))
        rx_pix = max(2, int(abs(ux[0] - center_2d[0]) + abs(vx[0] - center_2d[0])) // 3)
        ry_pix = max(2, int(abs(ux[1] - center_2d[1]) + abs(vx[1] - center_2d[1])) // 3)

        for px, py in PIPS[face["value"]]:
            pip_center = project(face_point(center, u, v, px, py))
            draw.ellipse(
                (
                    pip_center[0] - rx_pix,
                    pip_center[1] - ry_pix,
                    pip_center[0] + rx_pix,
                    pip_center[1] + ry_pix,
                ),
                fill=(18, 22, 28, 255),
            )
            draw.ellipse(
                (
                    pip_center[0] - max(1, rx_pix - 1),
                    pip_center[1] - max(1, ry_pix - 1),
                    pip_center[0] + max(1, rx_pix - 1),
                    pip_center[1] + max(1, ry_pix - 1),
                ),
                fill=(10, 12, 16, 255),
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUT_DIR / f"spin_{index:03d}.png")


def main() -> None:
    for index in range(FRAME_COUNT):
        draw_frame(index)
    print(f"generated {FRAME_COUNT} frames in {OUT_DIR}")


if __name__ == "__main__":
    main()
