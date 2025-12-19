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

    # Фон: мягкий градиент в фирменных зелёных тонах
    img = Image.new("RGB", (w, h), color=(0, 82, 63))
    top_color = (0, 82, 63)
    bottom_color = (0, 181, 102)
    for y in range(h):
        ratio = y / h
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        ImageDraw.Draw(img).line([(0, y), (w, y)], fill=(r, g, b))

    # Fonts: use default (portable). If custom fonts needed later, bundle them.
    try:
        font_title = ImageFont.truetype("arial.ttf", 60)
        font_body = ImageFont.truetype("arial.ttf", 42)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Белая полупрозрачная карточка в центре
    card_margin_x = 80
    card_margin_y = 80
    card_radius = 40
    card_color = (255, 255, 255, 235)

    card = Image.new("RGBA", (w - card_margin_x * 2, h - card_margin_y * 2), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [(0, 0), (card.size[0], card.size[1])],
        radius=card_radius,
        fill=card_color,
    )
    img.paste(card, (card_margin_x, card_margin_y), card)

    # Текст внутри карточки
    text_draw = ImageDraw.Draw(img)
    margin_inner_x = card_margin_x + 80
    y = card_margin_y + 70

    # Заголовок (повод)
    text_draw.text(
        (margin_inner_x, y),
        title,
        fill=(5, 88, 55),
        font=font_title,
    )
    y += 120

    # Кому
    text_draw.text(
        (margin_inner_x, y),
        recipient_line,
        fill=(20, 20, 20),
        font=font_body,
    )

    # Нижняя подпись
    footer_text = f"{brand_line} • {date.isoformat()}"
    # Pillow совместимость: используем textbbox вместо textsize
    bbox = text_draw.textbbox((0, 0), footer_text, font=font_small)
    footer_w = bbox[2] - bbox[0]
    footer_x = w - card_margin_x - 80 - footer_w
    footer_y = h - card_margin_y - 60
    text_draw.text(
        (footer_x, footer_y),
        footer_text,
        fill=(60, 60, 60),
        font=font_small,
    )

    filename = f"card_{date.isoformat()}_{abs(hash(recipient_line + title)) % 10_000_000}.png"
    path = out_dir / filename
    img.save(path, format="PNG")
    return path
