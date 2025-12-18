from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render_card(
    *,
    out_dir: Path,
    title: str,
    recipient_line: str,
    date: dt.date,
    brand_line: str = "Сбер",
) -> Path:
    """Render a simple greeting card image (Pillow) and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), color=(19, 141, 92))  # Sber-like green
    draw = ImageDraw.Draw(img)

    # Fonts: use default (portable). If custom fonts needed later, bundle them.
    try:
        font_title = ImageFont.truetype("arial.ttf", 56)
        font_body = ImageFont.truetype("arial.ttf", 40)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Simple layout
    margin = 70
    draw.text((margin, 90), title, fill=(255, 255, 255), font=font_title)
    draw.text((margin, 200), recipient_line, fill=(255, 255, 255), font=font_body)
    draw.text(
        (margin, h - 120),
        f"{brand_line} • {date.isoformat()}",
        fill=(240, 240, 240),
        font=font_small,
    )

    filename = f"card_{date.isoformat()}_{abs(hash(recipient_line + title)) % 10_000_000}.png"
    path = out_dir / filename
    img.save(path, format="PNG")
    return path
