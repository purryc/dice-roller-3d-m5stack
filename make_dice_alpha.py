#!/usr/bin/env python3
"""
Remove checkerboard background from dice sprite frames by
flood-filling border-connected gray pixels.

Usage:
  python3 make_dice_alpha.py \
    --input /path/to/spin36_128 \
    --output /path/to/spin36_128_alpha
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from pathlib import Path

from PIL import Image


def detect_bg_tones(samples: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    quantized = [tuple((c // 8) * 8 for c in s) for s in samples]
    common = [k for k, _ in Counter(quantized).most_common(8)]
    tones = [k for k in common if max(k) - min(k) <= 16]
    return tones if tones else common[:2]


def remove_bg_one(in_path: Path, out_path: Path, threshold: int) -> None:
    im = Image.open(in_path).convert("RGBA")
    pix = im.load()
    w, h = im.size

    border_samples: list[tuple[int, int, int]] = []
    for x in range(w):
        border_samples.append(pix[x, 0][:3])
        border_samples.append(pix[x, h - 1][:3])
    for y in range(h):
        border_samples.append(pix[0, y][:3])
        border_samples.append(pix[w - 1, y][:3])

    tones = detect_bg_tones(border_samples)

    def is_bg(rgb: tuple[int, int, int]) -> bool:
        r, g, b = rgb
        if max(rgb) - min(rgb) > 24:
            return False
        for t in tones:
            if abs(r - t[0]) + abs(g - t[1]) + abs(b - t[2]) <= threshold:
                return True
        return False

    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    for x in range(w):
        for y in (0, h - 1):
            if not visited[y][x] and is_bg(pix[x, y][:3]):
                visited[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not visited[y][x] and is_bg(pix[x, y][:3]):
                visited[y][x] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                if is_bg(pix[nx, ny][:3]):
                    visited[ny][nx] = True
                    q.append((nx, ny))

    out = im.copy()
    out_pix = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _a = out_pix[x, y]
            out_pix[x, y] = (r, g, b, 0 if visited[y][x] else 255)

    out.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input folder containing spin_XXX.png")
    parser.add_argument("--output", required=True, help="Output folder for transparent PNGs")
    parser.add_argument("--threshold", type=int, default=26, help="Background distance threshold")
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("spin_*.png"))
    if not files:
        raise SystemExit(f"No spin_*.png in {in_dir}")

    for p in files:
        remove_bg_one(p, out_dir / p.name, args.threshold)

    print(f"done: {len(files)} files -> {out_dir}")


if __name__ == "__main__":
    main()

