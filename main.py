#!/usr/bin/env python3
"""The World on Friday 13 November 2026 -- one image that sums up the day.

A deterministic generative program for the make.fun bounty
"Sum up 13 November's world news in one image" (news-image-01).

What it draws
------------
A newspaper front page, 1024x1024, entirely procedural with the Python
standard library only:

  * masthead: THE WORLD -- FRIDAY, 13 NOVEMBER 2026
  * six illustrated panels (2 x 3), each one story of the day with a short
    bold label a picture editor can read at a glance:
      1. US Senate summons Nvidia's Huang and Commerce Secretary Lutnick
      2. Zelensky meets US envoys; Europe joins the next talks
      3. Ukrainian drone hits a Russian warship in the Gulf of Finland
      4. Iran claims it struck a US radar site in Bahrain
      5. FBI: North Korean hackers' $400m crypto theft via fake video calls
      6. Harry Kane breaks England's caps record
  * a ticker strip with three more stories of the day: the Israeli strike
    on Gaza's Nasser Hospital, the worldwide Microsoft mail/Teams outage,
    and the US record 483,200 deportations in 2026

The stories are the ones first reported on 13 November 2026 (BBC World and
Al Jazeera's 13 November reporting, as the day's coverage recorded them).
Claims are labelled as claims ("Iran claims...", "FBI: ..."), nothing is
invented beyond the reporting, and no later day's news is included.

There is no network access, no randomness that is not seeded, and no
external asset: the same run always writes the same bytes, so the two
sandbox runs required by the bounty produce identical files.

Output
------
Writes ``entry.png`` into ``$MAKEFUN_OUTPUT_DIR`` (the sandbox's /output),
or into ``/output`` when the variable is not set. The PNG is encoded by
hand with zlib (colour type 2, 8-bit RGB, per-row filter choice), so the
program needs nothing beyond the standard library. Text is drawn with a
small built-in 5x7 bitmap font.

Run locally:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import hashlib
import math
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- canvas ---
W = 1024
H = 1024

canvas = bytearray(W * H * 3)

# --------------------------------------------------------------- palette ---
NAVY = (22, 35, 63)          # masthead / ticker
NAVY_DARK = (13, 22, 42)
PAPER = (247, 243, 234)      # panel paper
PAPER_LINE = (216, 210, 192)
GOLD = (201, 162, 39)
INK = (24, 28, 38)           # label text
WHITE = (250, 250, 246)
SLATE = (107, 122, 144)      # hearing-room wall
WOOD = (107, 74, 47)
WOOD_LIGHT = (138, 98, 56)
SEA = (52, 84, 110)
SEA_DARK = (34, 58, 82)
SKY_DUSK_TOP = (58, 58, 110)
SKY_DUSK_LOW = (232, 150, 96)
SAND = (214, 178, 120)
PITCH = (46, 125, 62)
PITCH_LIGHT = (72, 158, 86)


# ------------------------------------------------------------ primitives ---
def hline(x0, x1, y, color):
    """Fill a horizontal span of pixels (clipped)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    n = x1 - x0 + 1
    i = (y * W + x0) * 3
    canvas[i:i + n * 3] = bytes(color) * n


def rect(x, y, w, h, color):
    """Fill an axis-aligned rectangle (floats allowed)."""
    y0 = max(0, int(math.floor(y)))
    y1 = min(H - 1, int(math.ceil(y + h)) - 1)
    for yy in range(y0, y1 + 1):
        hline(x, x + w - 1, yy, color)


def blend_px(x, y, color, alpha):
    """Alpha-blend one pixel over the canvas."""
    if 0 <= x < W and 0 <= y < H and alpha > 0:
        i = (y * W + x) * 3
        a = alpha
        canvas[i] = int(color[0] * a + canvas[i] * (1 - a) + 0.5)
        canvas[i + 1] = int(color[1] * a + canvas[i + 1] * (1 - a) + 0.5)
        canvas[i + 2] = int(color[2] * a + canvas[i + 2] * (1 - a) + 0.5)


def fill_poly(pts, color):
    """Scanline-fill a polygon given as [(x, y), ...]."""
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x0, ya = pts[i]
            x1, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            lo, hi = (ya, yb) if ya < yb else (yb, ya)
            if lo <= yc < hi:
                t = (yc - ya) / (yb - ya)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(math.ceil(xs[k] - 0.5))
            xb = int(math.floor(xs[k + 1] - 0.5))
            hline(xa, xb, y, color)


def fill_circle(cx, cy, r, color):
    """Fill a disc (float centre/radius allowed)."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_ellipse(cx, cy, rx, ry, color):
    """Fill an axis-aligned ellipse."""
    rx = float(rx)
    ry = float(ry)
    y0 = max(0, int(math.floor(cy - ry)))
    y1 = min(H - 1, int(math.ceil(cy + ry)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / ry
        d2 = 1.0 - dy * dy
        if d2 < 0:
            continue
        dx = rx * math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_circle_alpha(cx, cy, r, color, alpha):
    """Fill a disc with a constant alpha over the canvas."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        for x in range(max(0, int(cx - dx)), min(W - 1, int(cx + dx)) + 1):
            blend_px(x, y, color, alpha)


def soft_disc(cx, cy, r, color, strength):
    """Radial glow: colour fading smoothly to nothing at radius r."""
    r = float(r)
    x0 = max(0, int(cx - r))
    x1 = min(W - 1, int(cx + r))
    y0 = max(0, int(cy - r))
    y1 = min(H - 1, int(cy + r))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / r
        for x in range(x0, x1 + 1):
            dx = (x + 0.5 - cx) / r
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                a = strength * (1.0 - d2) * (1.0 - d2)
                blend_px(x, y, color, a)


def line(x0, y0, x1, y1, w, color, alpha=1.0):
    """Draw a thick line by stamping discs along it."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1.0, w * 0.35)))
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if alpha >= 1.0:
            fill_circle(x, y, w / 2.0, color)
        else:
            fill_circle_alpha(x, y, w / 2.0, color, alpha)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t + 0.5) for i in range(3))


def vgrad(x, y, w, h, top, bottom):
    """Vertical gradient rectangle."""
    for yy in range(int(y), int(y + h)):
        t = (yy - y) / max(1, h - 1)
        rect(x, yy, w, 1, lerp(top, bottom, t))


# ------------------------------------------------------------------ font ---
# A 5x7 bitmap font. Each glyph is 7 rows of 5 bits ('1' = on).
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
}


def text_width(text, scale):
    """Pixel width of one line at the given scale (1 unit spacing)."""
    return len(text) * 6 * scale - scale


def draw_text(text, cx, y, scale, color, align="center"):
    """Draw one line of text; cx is the centre (or left edge if align='left')."""
    if align == "center":
        x = int(cx - text_width(text, scale) / 2)
    else:
        x = int(cx)
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch)
        if glyph is None:
            continue
        gx = x + ci * 6 * scale
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "1":
                    rect(gx + col * scale, y + row * scale, scale, scale, color)


def draw_text_lines(lines, cx, y, scale, color, gap=None):
    """Draw centred lines, one under the next."""
    if gap is None:
        gap = 3 * scale
    for i, ln in enumerate(lines):
        draw_text(ln, cx, y + i * (7 * scale + gap), scale, color)


# ------------------------------------------------------------ the panels ---
# Each illustration draws inside its zone (zx, zy, zw, zh).
# Panels are 490 x 266; the illustration zone is the top ~166 px.

def panel_senate(zx, zy, zw, zh):
    """US Senate hearing room: two empty witness chairs, one with a
    black leather jacket draped over it, microphones, a US flag."""
    vgrad(zx, zy, zw, zh, (122, 134, 156), (88, 100, 124))
    rect(zx, zy + zh - 62, zw, 62, WOOD)                    # desk front
    rect(zx, zy + zh - 62, zw, 6, WOOD_LIGHT)               # desk edge
    # wall seal
    cx = zx + zw // 2
    fill_circle(cx, zy + 26, 17, GOLD)
    fill_circle(cx, zy + 26, 12, NAVY)
    fill_circle(cx, zy + 26, 4, GOLD)
    # US flag on a pole, left
    fx, fy = zx + 26, zy + 18
    line(fx, fy, fx, zy + zh - 62, 3, (60, 52, 40))
    for i in range(7):
        rect(fx + 3, fy + i * 4, 52, 4, (178, 52, 52) if i % 2 == 0 else WHITE)
    rect(fx + 3, fy, 22, 16, (40, 60, 120))
    # two witness chairs
    for cx0, jacket in ((zx + 150, True), (zx + 320, False)):
        rect(cx0 - 34, zy + 52, 68, 58, (38, 48, 70))       # chair back
        fill_circle(cx0, zy + 52, 34, (38, 48, 70))
        rect(cx0 - 40, zy + 104, 80, 12, (30, 40, 58))      # seat
        if jacket:  # black leather jacket draped over the top of the back
            fill_poly([(cx0 - 36, zy + 30), (cx0 + 36, zy + 30),
                       (cx0 + 28, zy + 72), (cx0 - 28, zy + 72)], (18, 18, 20))
            fill_poly([(cx0 - 36, zy + 30), (cx0, zy + 50),
                       (cx0 + 36, zy + 30)], (28, 28, 32))
    # microphones on the desk
    for mx in (zx + 150, zx + 320):
        line(mx - 8, zy + zh - 62, mx + 6, zy + zh - 96, 3, (30, 30, 34))
        fill_circle(mx + 6, zy + zh - 96, 5, (30, 30, 34))
    # nameplate on the desk
    rect(zx + 214, zy + zh - 40, 48, 14, WHITE)
    rect(zx + 214, zy + zh - 40, 48, 3, GOLD)


def _flag(zx, zy, w, h, kind):
    """Small flag on a pole: 'ua' (blue/yellow), 'us' (stripes), 'eu'."""
    line(zx + 2, zy - 26, zx + 2, zy + h, 2, (70, 62, 50))
    if kind == "ua":
        rect(zx + 4, zy, w, h // 2, (0, 91, 172))
        rect(zx + 4, zy + h // 2, w, h - h // 2, (255, 213, 0))
    elif kind == "us":
        for i in range(7):
            rect(zx + 4, zy + i * (h // 7), w, h // 7 + 1,
                 (178, 52, 52) if i % 2 == 0 else WHITE)
        rect(zx + 4, zy, w // 2, h // 2 + 2, (40, 60, 120))
    else:  # eu
        rect(zx + 4, zy, w, h, (0, 51, 153))
        for k in range(8):
            a = k * math.pi / 4
            fill_circle(zx + 4 + w // 2 + int(9 * math.cos(a)),
                        zy + h // 2 + int(6 * math.sin(a)), 2, (255, 204, 0))


def panel_table(zx, zy, zw, zh):
    """A round negotiating table with Ukrainian, US and EU flags behind it."""
    vgrad(zx, zy, zw, zh, (198, 192, 180), (168, 160, 146))
    rect(zx, zy + zh - 34, zw, 34, (120, 110, 96))          # floor
    # chairs behind the table
    for cx0 in (zx + 90, zx + 384):
        rect(cx0 - 30, zy + 46, 60, 52, (52, 58, 74))
        fill_circle(cx0, zy + 46, 30, (52, 58, 74))
    # three flags
    _flag(zx + 118, zy + 66, 44, 28, "ua")
    _flag(zx + 215, zy + 58, 44, 28, "us")
    _flag(zx + 312, zy + 66, 44, 28, "eu")
    # round table
    fill_ellipse(zx + zw // 2, zy + 128, 190, 30, (122, 86, 50))
    fill_ellipse(zx + zw // 2, zy + 122, 190, 30, (150, 110, 66))
    rect(zx + zw // 2 - 14, zy + 122, 28, 34, (90, 62, 36))
    # papers and cups on the table
    rect(zx + 168, zy + 108, 52, 16, WHITE)
    rect(zx + 258, zy + 106, 46, 14, (235, 235, 228))
    rect(zx + 330, zy + 104, 18, 14, WHITE)
    fill_ellipse(zx + 339, zy + 104, 9, 3, (210, 200, 180))
    rect(zx + 128, zy + 106, 16, 12, WHITE)
    fill_ellipse(zx + 136, zy + 106, 8, 3, (210, 200, 180))


def panel_warship(zx, zy, zw, zh):
    """A grey warship on a cold northern sea, smoke rising, fire at the
    hull; a small drone in the sky."""
    vgrad(zx, zy, zw, zh, (150, 165, 182), (112, 128, 148))
    rect(zx, zy + zh - 52, zw, 52, SEA_DARK)                # sea
    for wy in (zy + zh - 44, zy + zh - 30, zy + zh - 16):
        for wx in range(zx + 10, zx + zw - 10, 46):
            hline(wx, wx + 26, wy, (140, 165, 185))
    # hull and superstructure
    fill_poly([(zx + 70, zy + 96), (zx + 420, zy + 96), (zx + 398, zy + 124),
               (zx + 92, zy + 124)], (58, 65, 72))
    rect(zx + 150, zy + 66, 120, 30, (74, 82, 90))
    rect(zx + 280, zy + 74, 46, 22, (74, 82, 90))
    rect(zx + 190, zy + 48, 10, 18, (58, 65, 72))           # funnel
    line(zx + 330, zy + 66, zx + 330, zy + 34, 4, (58, 65, 72))  # mast
    line(zx + 314, zy + 44, zx + 346, zy + 44, 3, (58, 65, 72))
    rect(zx + 150, zy + 66, 120, 4, (96, 104, 112))
    # fire glow at the hull
    soft_disc(zx + 250, zy + 104, 44, (255, 140, 40), 0.85)
    fill_circle(zx + 250, zy + 104, 14, (255, 190, 60))
    fill_circle(zx + 250, zy + 100, 7, (255, 230, 140))
    # smoke rising
    for sx, sy, sr, al in ((zx + 196, zy + 34, 13, 0.55), (zx + 204, zy + 18, 17, 0.45),
                           (zx + 214, zy + 4, 20, 0.35)):
        fill_circle_alpha(sx, sy, sr, (90, 92, 96), al)
    # drone, top right
    dx, dy = zx + 400, zy + 26
    rect(dx - 12, dy - 2, 24, 4, (30, 32, 36))
    fill_circle(dx - 14, dy - 4, 3, (30, 32, 36))
    fill_circle(dx + 14, dy - 4, 3, (30, 32, 36))
    for tx in range(dx - 60, dx - 14, 10):
        fill_circle(tx, dy + 8, 2, (60, 64, 70))


def panel_radar(zx, zy, zw, zh):
    """A radar dome on a desert coast at dusk, a missile streaking in."""
    vgrad(zx, zy, zw, zh, SKY_DUSK_TOP, SKY_DUSK_LOW)
    soft_disc(zx + 400, zy + 60, 60, (255, 220, 160), 0.7)
    fill_circle(zx + 400, zy + 60, 22, (255, 226, 170))
    rect(zx, zy + zh - 44, zw, 44, (40, 62, 112))           # sea
    hline(zx, zx + zw - 1, zy + zh - 44, (150, 170, 210))
    rect(zx, zy + zh - 78, zw, 34, SAND)                    # shore
    hline(zx, zx + zw - 1, zy + zh - 78, (190, 158, 104))
    # radar tower and dome
    tx = zx + 120
    rect(tx - 11, zy + 78, 22, zh - 78 - 44, (150, 152, 156))
    rect(tx - 16, zy + 74, 32, 6, (120, 122, 126))
    fill_circle(tx, zy + 62, 34, (238, 238, 234))
    fill_circle(tx, zy + 62, 34, (238, 238, 234))
    rect(tx - 34, zy + 62, 68, 12, (238, 238, 234))
    line(tx, zy + 62, tx + 26, zy + 26, 3, (200, 200, 196))
    fill_circle(tx + 26, zy + 26, 4, (200, 200, 196))
    # missile streak from upper right
    line(zx + 452, zy + 12, zx + 330, zy + 62, 5, (255, 120, 40))
    line(zx + 452, zy + 12, zx + 330, zy + 62, 2, (255, 240, 200))
    soft_disc(zx + 452, zy + 12, 26, (255, 160, 60), 0.8)
    fill_circle(zx + 452, zy + 12, 9, (255, 210, 120))


def panel_laptop(zx, zy, zw, zh):
    """A laptop showing a fake video call with a masked face, gold coins
    spilling out of the screen."""
    vgrad(zx, zy, zw, zh, (30, 44, 74), (16, 26, 50))
    rect(zx, zy + zh - 26, zw, 26, (18, 24, 40))            # desk
    # laptop screen
    sx, sy, sw, sh = zx + 117, zy + 14, 256, 128
    rect(sx, sy, sw, sh, (8, 12, 22))
    rect(sx + 6, sy + 6, sw - 12, sh - 12, (52, 88, 128))
    # video-call window with a masked figure
    wx, wy, ww, wh = sx + 34, sy + 20, 120, 92
    rect(wx, wy, ww, wh, (24, 34, 52))
    fill_poly([(wx + 28, wy + wh), (wx + 34, wy + 34), (wx + 60, wy + 18),
               (wx + 86, wy + 34), (wx + 92, wy + wh)], (16, 18, 24))  # hood
    fill_circle(wx + 60, wy + 48, 20, (58, 44, 36))          # face
    rect(wx + 42, wy + 44, 36, 12, (235, 235, 230))           # mask
    fill_circle(wx + 52, wy + 42, 3, (10, 10, 12))
    fill_circle(wx + 68, wy + 42, 3, (10, 10, 12))
    # small second window: a contact avatar
    fill_circle(sx + 208, sy + 116, 14, (200, 170, 120))
    fill_circle(sx + 208, sy + 110, 7, (120, 90, 70))
    # red recording dot
    fill_circle(sx + 16, sy + 14, 5, (220, 40, 40))
    # laptop base
    fill_poly([(sx - 16, sy + sh + 14), (sx + sw + 16, sy + sh + 14),
               (sx + sw + 4, sy + sh), (sx - 4, sy + sh)], (154, 160, 168))
    # gold coins spilling out
    for cx0, cy0, r in ((zx + 150, zy + 152, 13), (zx + 178, zy + 158, 11),
                        (zx + 208, zy + 154, 13), (zx + 240, zy + 160, 10),
                        (zx + 268, zy + 156, 12), (zx + 296, zy + 160, 10),
                        (zx + 322, zy + 154, 12)):
        fill_circle(cx0, cy0, r, (212, 160, 40))
        fill_circle(cx0, cy0, r - 4, (240, 196, 80))
        fill_circle(cx0, cy0, 3, (212, 160, 40))


def panel_football(zx, zy, zw, zh):
    """A footballer in white, arms raised, on a green pitch in a stadium."""
    vgrad(zx, zy, zw, zh, (36, 44, 66), (52, 60, 86))
    # crowd dots in the stands
    dots = ((255, 220, 120), (220, 90, 90), (240, 240, 240), (120, 180, 240))
    for i in range(150):
        dx = zx + 8 + (i * 37) % (zw - 16)
        dy = zy + 8 + (i * 23) % 52
        fill_circle(dx, dy, 3, dots[i % 4])
    # pitch with mowing stripes
    rect(zx, zy + 66, zw, zh - 66, PITCH)
    for s in range(4):
        rect(zx, zy + 66 + s * ((zh - 66) // 4), zw, (zh - 66) // 8, PITCH_LIGHT)
    hline(zx, zx + zw - 1, zy + 66, (240, 240, 240))
    # player, arms raised
    cx = zx + zw // 2
    fill_circle(cx, zy + 70, 13, (232, 190, 150))            # head
    fill_poly([(cx - 20, zy + 84), (cx + 20, zy + 84), (cx + 13, zy + 118),
               (cx - 13, zy + 118)], (245, 245, 240))         # shirt
    line(cx - 18, zy + 88, cx - 44, zy + 54, 8, (245, 245, 240))  # left arm
    line(cx + 18, zy + 88, cx + 44, zy + 54, 8, (245, 245, 240))  # right arm
    fill_circle(cx - 46, zy + 52, 5, (232, 190, 150))
    fill_circle(cx + 46, zy + 52, 5, (232, 190, 150))
    rect(cx - 13, zy + 118, 26, 14, (20, 32, 64))            # shorts
    line(cx - 7, zy + 132, cx - 10, zy + 150, 7, (245, 245, 240))
    line(cx + 7, zy + 132, cx + 12, zy + 150, 7, (245, 245, 240))
    fill_circle(cx - 10, zy + 152, 6, (20, 20, 24))
    fill_circle(cx + 12, zy + 152, 6, (20, 20, 24))
    # ball at his feet
    fill_circle(cx + 52, zy + 152, 10, WHITE)
    fill_circle(cx + 52, zy + 152, 4, (20, 20, 24))
    # motion lines
    for my in (zy + 74, zy + 92, zy + 110):
        line(cx - 70, my, cx - 52, my, 3, WHITE, 0.5)


# ---------------------------------------------------------------- layout ---
PANELS = [
    (("SENATE SUMMONS", "HUANG & LUTNICK"), panel_senate),
    (("ZELENSKY MEETS", "US ENVOYS, EU JOINS"), panel_table),
    (("DRONE HITS", "RUSSIAN WARSHIP"), panel_warship),
    (("IRAN CLAIMS STRIKE", "ON US RADAR IN BAHRAIN"), panel_radar),
    (("FBI: N. KOREA", "$400M CRYPTO HACK"), panel_laptop),
    (("KANE BREAKS", "ENGLAND CAPS RECORD"), panel_football),
]


def draw_masthead():
    rect(0, 0, W, 100, NAVY)
    rect(0, 100, W, 4, GOLD)
    draw_text("THE WORLD", W // 2, 14, 6, WHITE)
    draw_text("FRIDAY, 13 NOVEMBER 2026", W // 2, 68, 2, (200, 190, 150))
    fill_circle(48, 50, 5, GOLD)
    fill_circle(W - 48, 50, 5, GOLD)


def draw_panels():
    px = (16, 530)
    py = (112, 390, 668)
    pw, ph = 490, 266
    for i, (lines, fn) in enumerate(PANELS):
        x = px[i % 2]
        y = py[i // 2]
        rect(x, y, pw, ph, PAPER)
        rect(x, y, pw, 2, PAPER_LINE)
        rect(x, y, 2, ph, PAPER_LINE)
        rect(x + pw - 2, y, 2, ph, PAPER_LINE)
        rect(x, y + ph - 2, pw, 2, PAPER_LINE)
        fn(x + 8, y + 8, pw - 16, 166)
        hline(x + 8, x + pw - 9, y + 182, PAPER_LINE)
        draw_text_lines(lines, x + pw // 2, y + 194, 3, INK)


def draw_ticker():
    rect(0, 946, W, 78, NAVY)
    rect(0, 946, W, 3, GOLD)
    draw_text("ALSO: ISRAELI STRIKE ON GAZA HOSPITAL KILLS SIX",
              W // 2, 952, 2, (235, 230, 215))
    draw_text("MICROSOFT MAIL AND TEAMS DOWN WORLDWIDE",
              W // 2, 974, 2, (200, 190, 150))
    draw_text("US RECORD 483,200 DEPORTATIONS IN 2026",
              W // 2, 996, 2, (235, 230, 215))


def draw():
    rect(0, 0, W, H, (232, 228, 216))
    draw_masthead()
    draw_panels()
    draw_ticker()


# -------------------------------------------------------------------- png ---
def png_chunk(kind, data):
    chunk = struct.pack(">I", len(data)) + kind + data
    chunk += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return chunk


def encode_png():
    """Encode the RGB canvas as a PNG (colour type 2, 8-bit).

    Each row gets the smallest of filters None/Sub/Up by the usual
    sum-of-absolute-values heuristic, then one zlib stream at level 9.
    Fully deterministic for a fixed canvas.
    """
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(canvas[y * W * 3:(y + 1) * W * 3])
        cands = []
        cands.append((0, row))
        sub = bytearray(row)
        for i in range(3, len(sub)):
            sub[i] = (sub[i] - row[i - 3]) & 0xFF
        cands.append((1, bytes(sub)))
        up = bytearray(row)
        for i in range(len(up)):
            up[i] = (up[i] - prev[i]) & 0xFF
        cands.append((2, bytes(up)))

        def cost(b):
            return sum(v if v < 128 else 256 - v for v in b)

        ftype, fdata = min(cands, key=lambda c: cost(c[1]))
        raw.append(ftype)
        raw.extend(fdata)
        prev = row
    idat = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", idat)
    png += png_chunk(b"IEND", b"")
    return png


def main():
    draw()
    png = encode_png()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    digest = hashlib.sha256(png).hexdigest()
    print(f"wrote {path} ({len(png)} bytes, {W}x{H}, sha256={digest})")
    if len(png) > 1048576:
        print("WARNING: over the 1 MiB limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
