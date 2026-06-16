"""Generate scroll-stopping experiment visuals with Pillow — no image API needed."""
from __future__ import annotations

import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import CFG

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media" / "posts"
SIZE = (1080, 1080)
BG = (8, 10, 18)
ACCENT = (99, 102, 241)       # indigo
ACCENT2 = (34, 211, 238)      # cyan
TEXT = (248, 250, 252)
MUTED = (148, 163, 184)
CARD = (18, 22, 32)
GLOW = (99, 102, 241, 40)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def render_card(spec: dict) -> Path:
    """Render a stat-card PNG from a visual spec dict."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)

    # Subtle gradient header glow
    for i in range(120):
        alpha = int(30 * (1 - i / 120))
        draw.line([(0, i), (SIZE[0], i)], fill=(ACCENT[0], ACCENT[1], ACCENT[2]))

    title_font = _font(48, bold=True)
    stat_font = _font(76, bold=True)
    label_font = _font(28)
    body_font = _font(32)
    small_font = _font(22)
    brand_font = _font(36, bold=True)

    draw.text((48, 40), "CENTURION", font=brand_font, fill=ACCENT2)
    draw.text((48, 82), spec.get("subtitle", "autonomous field notes"), font=small_font, fill=MUTED)

    y = 160
    headline = spec.get("headline", "Day 0")
    for line in _wrap(draw, headline, title_font, SIZE[0] - 96):
        draw.text((48, y), line, font=title_font, fill=TEXT)
        y += 58

    y += 20
    stats = spec.get("stats", [])
    for i, stat in enumerate(stats[:3]):
        box_y = y + i * 145
        draw.rounded_rectangle((48, box_y, SIZE[0] - 48, box_y + 115), radius=16, fill=CARD)
        draw.rectangle((48, box_y, 54, box_y + 115), fill=ACCENT if i == 0 else ACCENT2)
        draw.text((72, box_y + 14), stat.get("label", ""), font=label_font, fill=MUTED)
        draw.text((72, box_y + 48), str(stat.get("value", "")), font=stat_font, fill=TEXT)

    insight = spec.get("insight", "")
    if insight:
        iy = SIZE[1] - 210
        draw.rounded_rectangle((48, iy, SIZE[0] - 48, SIZE[1] - 48), radius=16, fill=CARD)
        draw.text((72, iy + 20), "NOTE", font=label_font, fill=ACCENT2)
        for j, line in enumerate(_wrap(draw, insight, body_font, SIZE[0] - 140)):
            draw.text((72, iy + 56 + j * 40), line, font=body_font, fill=TEXT)

    out = MEDIA_DIR / f"{int(time.time())}.png"
    img.save(out, "PNG", optimize=True)
    print(f"[visual] rendered {out.name} ({out.stat().st_size // 1024}KB)")
    return out


def render_tip_card(spec: dict) -> Path:
    """Bold single-tip card — high contrast for 0-follower feeds."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)

    tag_font = _font(28, bold=True)
    tip_font = _font(56, bold=True)
    sub_font = _font(30)

    draw.rectangle((0, 0, SIZE[0], 6), fill=ACCENT)
    draw.text((48, 44), spec.get("tag", "FIELD NOTE"), font=tag_font, fill=ACCENT2)

    y = 190
    for line in _wrap(draw, spec.get("tip", ""), tip_font, SIZE[0] - 96):
        draw.text((48, y), line, font=tip_font, fill=TEXT)
        y += 68

    footer = spec.get("footer", "— Centurion, posting without a supervisor")
    for j, line in enumerate(_wrap(draw, footer, sub_font, SIZE[0] - 96)):
        draw.text((48, SIZE[1] - 120 + j * 38), line, font=sub_font, fill=MUTED)

    out = MEDIA_DIR / f"tip_{int(time.time())}.png"
    img.save(out, "PNG", optimize=True)
    print(f"[visual] rendered tip {out.name}")
    return out
