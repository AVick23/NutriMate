"""
Утилиты для обработки текста еды (fallback-парсер).
Основной парсинг — в food_matcher.py.
"""
import re
from typing import Optional, Tuple


def parse_food_text(text: str) -> Tuple[str, Optional[float]]:
    """
    Простой парсер текста вида "омлет 200г" или "банан".
    Возвращает (название, вес) или (текст, None).
    """
    text = text.strip()

    weight_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:г|g|грамм?)$",
        text, re.IGNORECASE
    )
    if weight_match:
        weight = float(weight_match.group(1))
        name = re.sub(
            r"\s*\d+(?:\.\d+)?\s*(?:г|g|грамм?)$",
            "", text, flags=re.IGNORECASE
        ).strip()
        return name if name else text, weight

    return text, None