"""Server-side rendering of image questions. Answers are only recoverable by looking at the pixels."""

from __future__ import annotations

import io
import random
from typing import Any

from PIL import Image, ImageDraw, ImageFont

COLORS = {"red": (220, 50, 47), "blue": (38, 110, 210), "green": (46, 160, 67)}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def render(spec: dict[str, Any]) -> bytes:
    if spec["kind"] == "bar_chart":
        img = _bar_chart(spec)
    elif spec["kind"] == "shapes":
        img = _shapes(spec)
    else:
        raise ValueError(f"unknown image kind {spec['kind']}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _bar_chart(spec: dict[str, Any]) -> Image.Image:
    w, h, left, bottom, top = 720, 420, 70, 60, 50
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    f, fs = _font(16), _font(13)
    d.text((w // 2 - 90, 14), spec["title"], fill="black", font=_font(18))
    plot_h = h - bottom - top
    vmax = 100
    for v in range(0, vmax + 1, 10):
        y = h - bottom - plot_h * v / vmax
        d.line([(left, y), (w - 20, y)], fill=(225, 225, 225))
        d.text((left - 34, y - 8), str(v), fill=(90, 90, 90), font=fs)
    d.line([(left, top - 5), (left, h - bottom)], fill="black", width=2)
    d.line([(left, h - bottom), (w - 20, h - bottom)], fill="black", width=2)
    n = len(spec["labels"])
    slot = (w - 20 - left) / n
    for i, (label, value) in enumerate(zip(spec["labels"], spec["values"], strict=True)):
        x0 = left + i * slot + slot * 0.2
        x1 = left + (i + 1) * slot - slot * 0.2
        y0 = h - bottom - plot_h * value / vmax
        d.rectangle([x0, y0, x1, h - bottom], fill=(66, 133, 244), outline=(30, 80, 170))
        d.text(((x0 + x1) / 2 - 10, y0 - 20), str(value), fill="black", font=f)
        d.text(((x0 + x1) / 2 - len(label) * 4, h - bottom + 10), label, fill="black", font=f)
    return img


def _shapes(spec: dict[str, Any]) -> Image.Image:
    rng = random.Random(spec["seed"])
    w, h, cell = 720, 420, 90
    img = Image.new("RGB", (w, h), (250, 250, 247))
    d = ImageDraw.Draw(img)
    cells = [(cx, cy) for cx in range(w // cell) for cy in range(h // cell)]
    rng.shuffle(cells)
    for s, (cx, cy) in zip(spec["shapes"], cells, strict=False):
        r = rng.randint(22, 34)
        x = cx * cell + cell // 2 + rng.randint(-8, 8)
        y = cy * cell + cell // 2 + rng.randint(-8, 8)
        col = COLORS[s["color"]]
        if s["shape"] == "circle":
            d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline="black")
        elif s["shape"] == "square":
            d.rectangle([x - r, y - r, x + r, y + r], fill=col, outline="black")
        else:
            d.polygon([(x, y - r), (x - r, y + r), (x + r, y + r)], fill=col, outline="black")
    return img
