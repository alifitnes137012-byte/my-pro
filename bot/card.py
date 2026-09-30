"""ساخت کارت تصویری نتیجهٔ ذکر شخصی (PNG)."""

import io
import math
from functools import lru_cache
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "fonts"

W, H = 1080, 1350
BG_TOP, BG_BOTTOM = (18, 24, 56), (6, 8, 22)
GOLD, GOLD_SOFT = (232, 196, 110), (170, 140, 80)
PANEL, PANEL_EDGE = (30, 38, 80), (80, 72, 120)
WHITE, MUTED = (245, 242, 235), (175, 178, 205)


@lru_cache(maxsize=None)
def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        str(FONTS / f"Vazirmatn-{weight}.ttf"), size, layout_engine=ImageFont.Layout.BASIC
    )


def _rtl(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill) -> None:
    draw.text((W // 2, y), _rtl(text), font=font, fill=fill, anchor="mm")


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill=None, outline=None, width=2):
    """ستارهٔ هشت‌پر (دو مربع روی هم) به سبک نقوش اسلامی."""
    for rot in (0, math.pi / 4):
        pts = [
            (cx + r * math.cos(rot + k * math.pi / 2), cy + r * math.sin(rot + k * math.pi / 2))
            for k in range(4)
        ]
        draw.polygon(pts, fill=fill, outline=outline, width=width)


def _background() -> Image.Image:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    # ستاره‌های کم‌رنگ پس‌زمینه
    for x in range(0, W + 1, 135):
        for y in range(0, H + 1, 135):
            _star(draw, x, y, 22, outline=(38, 46, 88), width=1)
    return img


def render(title: str, full_name: str, items: list[tuple[str, str, str]]) -> bytes:
    """items: [(عنوان، مقدار اصلی، زیرنویس)] — سه مورد جا می‌شود."""
    img = _background()
    draw = ImageDraw.Draw(img)

    # سربرگ
    _star(draw, W // 2, 120, 46, fill=GOLD)
    _star(draw, W // 2, 120, 22, fill=BG_TOP)
    _center(draw, 225, title, _font("Black", 64), GOLD)
    _center(draw, 305, full_name, _font("Bold", 46), WHITE)
    draw.line([(W // 2 - 220, 360), (W // 2 + 220, 360)], fill=GOLD_SOFT, width=2)

    box_h, gap = 240, 38
    top = 410 + (3 - len(items)) * (box_h + gap) // 2
    for i, (label, value, sub) in enumerate(items):
        y0 = top + i * (box_h + gap)
        draw.rounded_rectangle(
            [(90, y0), (W - 90, y0 + box_h)], radius=36, fill=PANEL, outline=PANEL_EDGE, width=3
        )
        _star(draw, W - 90, y0 + box_h // 2, 30, fill=GOLD)
        _center(draw, y0 + 52, label, _font("Bold", 34), MUTED)
        _center(draw, y0 + 130, value, _font("Black", 76), GOLD)
        _center(draw, y0 + 200, sub, _font("Regular", 26), MUTED)

    _center(draw, H - 70, "مینی اپ علم اعداد", _font("Bold", 30), GOLD_SOFT)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
