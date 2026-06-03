# handlers/add_food/utils.py
from typing import Optional, Tuple
import re


def parse_food_text(text: str) -> Tuple[str, Optional[float]]:
    """
    Парсит текст вида "омлет 200г" или "банан".
    Возвращает (название, вес) или (текст, None) если вес не указан.
    """
    text = text.strip()
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:г|g|грамм?)$", text, re.IGNORECASE)
    if weight_match:
        weight = float(weight_match.group(1))
        name = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:г|g|грамм?)$", "", text, flags=re.IGNORECASE).strip()
        return name if name else text, weight
    return text, None


def format_progress_bar(current: float, total: float, length: int = 10) -> str:
    """Форматирует прогресс-бар."""
    if total <= 0:
        return "▱" * length
    ratio = min(1.0, current / total)
    filled = int(ratio * length)
    return "▰" * filled + "▱" * (length - filled)