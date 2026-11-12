#!/usr/bin/env python3
"""Cutest picture entry: a chubby baby axolotl in soft pastel water.

Pure Python 3 standard library only — no image files, no network, no
third-party packages. The picture is rasterised procedurally into a
1024x1024 RGB buffer and written as a deterministic PNG (pure-Python
encoder, zlib) to $MAKEFUN_OUTPUT_DIR/entry.png (default ./entry.png).
Every run produces byte-identical output.
"""

import math
import os
import struct
import zlib

SIZE = 1024

# ------------------------------------------------------------------ palette
AQUA_LIGHT = (190, 233, 224)   # pale mint water, top
AQUA_MID = (168, 217, 229)     # soft aqua, middle
AQUA_DEEP = (138, 195, 219)    # deeper aqua, bottom
SUN_GLOW = (255, 243, 220)     # warm halo behind the axolotl
SAND = (246, 226, 196)         # sandy floor
PINK_TOP = (255, 215, 227)     # axolotl head, pale pink
PINK_BOT = (255, 182, 200)     # axolotl belly-side, deeper pink
CREAM = (255, 239, 244)        # cream belly and paws
FROND = (255, 143, 171)        # coral-pink gill fronds
FROND_DEEP = (255, 106, 156)   # darker frond
FROND_SOFT = (255, 179, 199)   # light frond fluff
INK = (44, 44, 60)             # eyes, smile
BOW_RED = (255, 92, 143)       # bow
BOW_DEEP = (228, 60, 116)      # bow knot / shading
BLUSH = (255, 148, 176)        # cheeks and nose
GOLD = (255, 191, 92)          # fish friend
GOLD_DEEP = (238, 148, 58)     # fish tail and fin
SNOW = (255, 255, 255)


class Canvas:
    """A plain RGB framebuffer with small filled-shape helpers."""

    def __init__(self, size):
        self.size = size
        self.px = bytearray(size * size * 3)

    def _off(self, x, y):
        return (y * self.size + x) * 3

    def blend(self, x, y, color, alpha):
        if 0 <= x < self.size and 0 <= y < self.size and 0.0 < alpha:
            i = self._off(x, y)
            inv = 1.0 - alpha
            self.px[i] = int(color[0] * alpha + self.px[i] * inv + 0.5)
            self.px[i + 1] = int(color[1] * alpha + self.px[i + 1] * inv + 0.5)
            self.px[i + 2] = int(color[2] * alpha + self.px[i + 2] * inv + 0.5)

    def hline(self, y, x0, x1, color):
        """Solid horizontal run, clipped to the canvas."""
        if y < 0 or y >= self.size:
            return
        x0 = max(0, x0)
        x1 = min(self.size - 1, x1)
        if x1 < x0:
            return
        i = self._off(x0, y)
        self.px[i:i + (x1 - x0 + 1) * 3] = bytes(color) * (x1 - x0 + 1)

    def disc(self, cx, cy, rx, ry, color, alpha=1.0):
        """Filled ellipse with a soft 1 px edge."""
        top = max(0, int(math.floor(cy - ry)))
        bot = min(self.size - 1, int(math.ceil(cy + ry)))
        for y in range(top, bot + 1):
            t = (y - cy) / ry
            if abs(t) >= 1.0:
                continue
            dx = rx * math.sqrt(1.0 - t * t)
            left, right = cx - dx, cx + dx
            if alpha >= 1.0:
                self.hline(y, int(math.ceil(left)), int(math.floor(right)), color)
                edge = int(math.floor(left))
                self.blend(edge, y, color, edge + 1 - left)
                edge = int(math.floor(right))
                if edge != int(math.floor(left)):
                    self.blend(edge, y, color, right - edge)
            else:
                for x in range(int(math.ceil(left)), int(math.floor(right)) + 1):
                    self.blend(x, y, color, alpha)

    def tilted(self, cx, cy, rx, ry, angle_deg, color, alpha=1.0):
        """Filled ellipse rotated angle_deg clockwise."""
        th = math.radians(angle_deg)
        c, s = math.cos(th), math.sin(th)
        ix, iy = 1.0 / (rx * rx), 1.0 / (ry * ry)
        # quadratic coefficient for the scanline solve
        qa = c * c * ix + s * s * iy
        ex = math.sqrt((rx * c) ** 2 + (ry * s) ** 2)
        ey = math.sqrt((rx * s) ** 2 + (ry * c) ** 2)
        top = max(0, int(math.floor(cy - ey)))
        bot = min(self.size - 1, int(math.ceil(cy + ey)))
        for y in range(top, bot + 1):
            dy = y - cy
            qb = 2.0 * c * s * dy * (ix - iy)
            qc = dy * dy * (s * s * ix + c * c * iy) - 1.0
            det = qb * qb - 4.0 * qa * qc
            if det < 0:
                continue
            root = math.sqrt(det)
            left = cx + (-qb - root) / (2.0 * qa)
            right = cx + (-qb + root) / (2.0 * qa)
            if alpha >= 1.0:
                self.hline(y, int(math.ceil(left)), int(math.floor(right)), color)
            else:
                for x in range(int(math.ceil(left)), int(math.floor(right)) + 1):
                    self.blend(x, y, color, alpha)

    def poly(self, pts, color, alpha=1.0):
        """Scanline fill of a simple polygon."""
        top = max(0, int(math.ceil(min(p[1] for p in pts))))
        bot = min(self.size - 1, int(math.floor(max(p[1] for p in pts))))
        n = len(pts)
        for y in range(top, bot + 1):
            hits = []
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    hits.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            hits.sort()
            for k in range(0, len(hits) - 1, 2):
                if alpha >= 1.0:
                    self.hline(y, int(math.ceil(hits[k])), int(math.floor(hits[k + 1])), color)
                else:
                    for x in range(int(math.ceil(hits[k])), int(math.floor(hits[k + 1])) + 1):
                        self.blend(x, y, color, alpha)

    def star(self, cx, cy, r, color, alpha=1.0):
        """Four-point sparkle."""
        k = 0.24
        self.poly([(cx, cy - r), (cx + r * k, cy - r * k), (cx + r, cy),
                   (cx + r * k, cy + r * k), (cx, cy + r),
                   (cx - r * k, cy + r * k), (cx - r, cy),
                   (cx - r * k, cy - r * k)], color, alpha)

    def ring(self, cx, cy, r, color, alpha, width=3):
        steps = max(32, int(2 * math.pi * r))
        for i in range(steps):
            a = 2 * math.pi * i / steps
            for w in range(-width // 2, width // 2 + 1):
                self.blend(int(cx + (r + w) * math.cos(a)),
                           int(cy + (r + w) * math.sin(a)), color, alpha)


def mix(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t + 0.5),
            int(c1[1] + (c2[1] - c1[1]) * t + 0.5),
            int(c1[2] + (c2[2] - c1[2]) * t + 0.5))


# ------------------------------------------------------------------ scenery
def paint_water(cv):
    for y in range(SIZE):
        t = y / (SIZE - 1)
        if t < 0.55:
            col = mix(AQUA_LIGHT, AQUA_MID, t / 0.55)
        else:
            col = mix(AQUA_MID, AQUA_DEEP, (t - 0.55) / 0.45)
        i = y * SIZE * 3
        cv.px[i:i + SIZE * 3] = bytes(col) * SIZE
    # slanted sun rays from the surface
    for cx, wd, a in ((170, 95, 0.10), (430, 135, 0.08), (760, 105, 0.10), (950, 70, 0.07)):
        cv.tilted(cx, 290, wd, 570, 8, (255, 255, 240), a)
    # warm halo behind the subject, built from faint concentric discs
    for k in range(28, 0, -1):
        t = k / 28.0
        cv.disc(512, 545, 435 * t, 405 * t, SUN_GLOW, 0.30 / 28.0)
    # sandy floor at the bottom
    cv.disc(512, 1130, 720, 155, SAND, 0.35)


def bubble(cv, cx, cy, r):
    cv.disc(cx, cy, r, r, SNOW, 0.18)
    cv.ring(cx, cy, r, SNOW, 0.55, 3)
    cv.disc(cx - r * 0.35, cy - r * 0.38, r * 0.28, r * 0.20, SNOW, 0.85)


# ------------------------------------------------------------------ axolotl
def gill(cv, bx, by, angle, length, color):
    """One feathery external gill: three petals fanning from the base."""
    th = math.radians(angle)
    dx, dy = math.cos(th), math.sin(th)
    for off, ln, wd in ((-20, length * 0.92, 33), (0, length, 37), (20, length * 0.92, 33)):
        cv.tilted(bx + dx * ln * 0.42, by + dy * ln * 0.42,
                  wd, ln * 0.5, angle + off * 0.35, color)
    for off, ln, wd in ((-10, length * 0.60, 15), (10, length * 0.60, 15)):
        cv.tilted(bx + dx * ln * 0.40, by + dy * ln * 0.40,
                  wd, ln * 0.48, angle + off * 0.4, FROND_SOFT)


def eye(cv, ex, ey):
    cv.disc(ex, ey, 62, 70, INK)                       # big dark eye
    cv.disc(ex, ey, 32, 40, (72, 72, 96), 0.9)        # iris depth
    cv.disc(ex - 21, ey - 27, 21, 25, SNOW)           # main sparkle
    cv.disc(ex + 19, ey + 21, 9, 10, SNOW, 0.9)       # small sparkle
    cv.star(ex - 38, ey - 44, 15, SNOW, 0.95)         # twinkle
    # three little lashes above the eye
    for dx, tilt in ((-34, -32), (0, 0), (34, 32)):
        cv.tilted(ex + dx, ey - 76, 4, 15, tilt, INK)


def bow(cv, bx, by):
    """Little pink bow on the head, tilted playfully."""
    cv.tilted(bx - 52, by - 8, 52, 30, -28, BOW_RED)
    cv.tilted(bx + 52, by - 8, 52, 30, 28, BOW_RED)
    cv.tilted(bx - 52, by - 8, 30, 16, -28, BOW_DEEP, 0.45)
    cv.tilted(bx + 52, by - 8, 30, 16, 28, BOW_DEEP, 0.45)
    cv.disc(bx, by - 6, 22, 20, BOW_DEEP)


def draw_axolotl(cv):
    cx, cy = 512, 545
    # gills behind the head, fanning out on both sides; bases tucked
    # into the head so the fronds read as attached, not floating
    for side in (-1, 1):
        for i, ang in enumerate((215, 180, 145)):
            a = ang if side < 0 else (180 - ang) % 360
            col = FROND if i != 1 else FROND_DEEP
            gill(cv, cx + side * 246, cy - 170 + i * 62, a,
                 150 - abs(i - 1) * 12, col)
    # chubby round body with a vertical pink gradient
    for y in range(cy - 265, cy + 266):
        t = (y - cy) / 265.0
        if abs(t) >= 1.0:
            continue
        dx = 300 * math.sqrt(1.0 - t * t)
        cv.hline(y, int(math.ceil(cx - dx)), int(math.floor(cx + dx)),
                 mix(PINK_TOP, PINK_BOT, (t + 1) / 2))
    # cream belly
    cv.disc(cx, cy + 130, 195, 130, CREAM, 0.85)
    # tiny arms with cream paws
    for side in (-1, 1):
        cv.tilted(cx + side * 265, cy + 150, 42, 26, side * 35, PINK_BOT)
        cv.disc(cx + side * 282, cy + 178, 26, 18, CREAM)
    # little feet peeking out at the bottom
    for side in (-1, 1):
        cv.disc(cx + side * 150, cy + 258, 46, 24, PINK_BOT)
        cv.disc(cx + side * 150, cy + 262, 30, 14, CREAM, 0.9)
    # blush cheeks
    for side in (-1, 1):
        cv.disc(cx + side * 185, cy + 55, 52, 30, BLUSH, 0.55)
    # huge sparkling eyes
    for side in (-1, 1):
        eye(cv, cx + side * 126, cy - 55)
    # tiny nose and a crescent smile
    cv.disc(cx, cy + 38, 26, 20, BLUSH, 0.9)
    cv.disc(cx, cy + 66, 36, 32, INK)
    cv.disc(cx, cy + 51, 38, 32, PINK_BOT)
    # the bow, sitting on the head rather than floating above it
    bow(cv, cx + 150, cy - 222)


def fish(cv, cx, cy, scale=1.0, flip=False):
    """Tiny gold fish friend. flip=True makes it swim the other way."""
    s = scale
    d = -1 if flip else 1
    cv.poly([(cx + d * 44 * s, cy), (cx + d * 76 * s, cy - 26 * s),
             (cx + d * 76 * s, cy + 26 * s)], GOLD_DEEP)          # tail
    cv.disc(cx, cy, 48 * s, 32 * s, GOLD)                          # body
    cv.disc(cx - d * 5 * s, cy + 5 * s, 38 * s, 23 * s, (255, 211, 132), 0.8)
    cv.tilted(cx - d * 2 * s, cy - 25 * s, 22 * s, 10 * s, -20 * d, GOLD_DEEP)
    cv.disc(cx - d * 25 * s, cy - 7 * s, 9 * s, 10 * s, INK)       # eye
    cv.disc(cx - d * 28 * s, cy - 10 * s, 3 * s, 4 * s, SNOW)
    cv.disc(cx - d * 35 * s, cy + 10 * s, 8 * s, 7 * s, INK)       # smile dot
    cv.disc(cx - d * 35 * s, cy + 7 * s, 9 * s, 7 * s, GOLD)


def draw_scene(cv):
    paint_water(cv)
    for cx, cy, r in ((140, 220, 26), (210, 420, 16), (880, 260, 22),
                      (920, 480, 14), (120, 700, 20), (700, 130, 15),
                      (330, 120, 12), (790, 880, 18), (250, 880, 13),
                      (950, 760, 11)):
        bubble(cv, cx, cy, r)
    draw_axolotl(cv)
    fish(cv, 862, 625, 1.0)          # main fish friend, right side
    fish(cv, 150, 815, 0.55, flip=True)  # tiny second fish, bottom left
    # sparkles and a little heart floating near the fish friend
    cv.star(795, 500, 13, SNOW, 0.9)
    cv.star(905, 720, 11, SNOW, 0.85)
    cv.disc(905, 545, 9, 8, BOW_RED)
    cv.disc(921, 545, 9, 8, BOW_RED)
    cv.poly([(897, 549), (929, 549), (913, 570)], BOW_RED)
    for cx, cy, r in ((300, 330, 12), (730, 360, 10), (660, 880, 14)):
        bubble(cv, cx, cy, r)


# ------------------------------------------------------------------ PNG out
def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(cv):
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)  # filter: none
        raw += cv.px[y * SIZE * 3:(y + 1) * SIZE * 3]
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "./entry.png")
    # MAKEFUN_OUTPUT_DIR is a directory; tolerate being given a file path.
    if out_dir.endswith(".png"):
        path = out_dir
        out_dir = os.path.dirname(path) or "."
    else:
        path = os.path.join(out_dir, "entry.png")
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas(SIZE)
    draw_scene(cv)
    data = encode_png(cv)
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
