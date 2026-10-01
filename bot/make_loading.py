"""ساخت انیمیشن «در حال محاسبه» (assets/loading.gif).

فقط وقتی طرح عوض شود اجرا می‌شود:  python -m bot.make_loading
"""

import math

from PIL import Image, ImageDraw, ImageFilter

from .card import ASSETS, BG_BOTTOM, BG_TOP, GOLD, GOLD_SOFT, _font, _logo, _rtl, _star

S = 480
FRAMES = 36
DIGITS = "۱۲۳۴۵۶۷۸۹"


def _base() -> Image.Image:
    img = Image.new("RGB", (S, S), BG_BOTTOM)
    glow = Image.new("RGB", (S, S), BG_BOTTOM)
    d = ImageDraw.Draw(glow)
    for r in range(S // 2, 0, -4):
        t = r / (S / 2)
        color = tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        d.ellipse([(S / 2 - r, S / 2 - 30 - r), (S / 2 + r, S / 2 - 30 + r)], fill=color)
    img.paste(glow)
    return img


def frame(i: int, base: Image.Image) -> Image.Image:
    t = i / FRAMES
    img = base.copy()
    cx, cy = S // 2, S // 2 - 30

    # هالهٔ طلایی تپنده پشت لوگو
    halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t)
    r = 96 + 10 * pulse
    ImageDraw.Draw(halo).ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*GOLD, int(70 + 60 * pulse)))
    img.paste(halo.filter(ImageFilter.GaussianBlur(18)), (0, 0), halo.filter(ImageFilter.GaussianBlur(18)))

    draw = ImageDraw.Draw(img)
    # دو حلقهٔ کمانی که خلاف هم می‌چرخند
    for radius, speed, width in ((118, 1, 4), (132, -1, 2)):
        start = 360 * t * speed
        for k in range(3):
            a = start + k * 120
            draw.arc([(cx - radius, cy - radius), (cx + radius, cy + radius)], a, a + 70, fill=GOLD, width=width)

    # اعداد ۱ تا ۹ در مدار
    font = _font("Bold", 24)
    for k, ch in enumerate(DIGITS):
        ang = 2 * math.pi * (k / 9 + t / 3)
        x, y = cx + 170 * math.cos(ang), cy + 170 * math.sin(ang)
        bright = 0.5 + 0.5 * math.sin(2 * math.pi * (t * 2 + k / 9))
        color = tuple(int(g * (0.45 + 0.55 * bright)) for g in GOLD)
        draw.text((x, y), ch, font=font, fill=color, anchor="mm")

    # ستاره‌های چشمک‌زن
    for k in range(7):
        ang = 2 * math.pi * k / 7 + 0.4
        x, y = cx + 205 * math.cos(ang) * 0.95, cy + 150 * math.sin(ang)
        s = 3 + 7 * max(0.0, math.sin(2 * math.pi * (t + k / 7)))
        _star(draw, x, y, s, fill=GOLD_SOFT)

    logo = _logo(170)
    img.paste(logo, (cx - 85, cy - 85), logo)

    dots = "." * (1 + (i // 6) % 3)
    draw.text((S // 2, S - 48), _rtl("در حال محاسبه") + dots, font=_font("Bold", 30), fill=GOLD, anchor="mm")
    return img


def main() -> None:
    base = _base()
    frames = [frame(i, base).quantize(colors=128, method=Image.Quantize.MEDIANCUT) for i in range(FRAMES)]
    frames[0].save(
        ASSETS / "loading.gif", save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True
    )


if __name__ == "__main__":
    main()
