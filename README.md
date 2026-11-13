# The World on Friday 13 November 2026

Entry for the make.fun bounty **"Sum up 13 November's world news in one
image"** ([news-image-01](https://make.fun/bounty/news-image-01), $250,
ends Sat 14 Nov 2026 03:00 WIB).

## The image

`entry.png` — a 1024×1024 newspaper front page drawn entirely
procedurally, in the style of a clean editorial infographic:

- masthead: **THE WORLD — FRIDAY, 13 NOVEMBER 2026**
- six illustrated panels, each one story of the day with a short bold
  label a picture editor can read at a glance:
  1. **Senate summons Huang & Lutnick** — the US Senate Banking Committee
     summons Nvidia's Jensen Huang and Commerce Secretary Lutnick
  2. **Zelensky meets US envoys, EU joins** — Ukraine talks, with Europe
     brought into the next round
  3. **Drone hits Russian warship** — a Ukrainian drone strike on a
     Russian warship in the Gulf of Finland
  4. **Iran claims strike on US radar in Bahrain**
  5. **FBI: N. Korea $400m crypto hack** — hackers' theft through fake
     video calls
  6. **Kane breaks England caps record**
- a ticker strip with three more stories of the day: the Israeli strike on
  Gaza's Nasser Hospital, the worldwide Microsoft mail/Teams outage, and
  the US record 483,200 deportations in 2026

The stories are the ones first reported on 13 November 2026 (BBC World
and Al Jazeera's reporting of the day). Claims are labelled as claims,
nothing is invented beyond the reporting, and no later day's news is in
the picture.

## The program

`main.py` — Python 3.13, **standard library only** (no install step, no
network, no API key). It contains a tiny software rasteriser (scanline
polygon fill, discs, ellipses, thick lines, gradients, glows), a built-in
5×7 bitmap font for the labels, and a hand-written PNG encoder (zlib,
colour type 2, per-row filter choice), so the whole entry is one
self-contained file that always writes byte-identical output.

Run locally:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
