"""
Утилиты для обработки текста еды
"""
import re
from typing import Optional, Tuple


def parse_food_text(text: str) -> Tuple[str, Optional[float]]:
    """
    Парсит текст вида "омлет 200г" или "банан".
    Возвращает (название, вес) или (текст, None) если вес не указан.
    """
    text = text.strip()
    # Ищем вес в конце строки
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:г|g|грамм?)$", text, re.IGNORECASE)
    if weight_match:
        weight = float(weight_match.group(1))
        # Убираем вес из названия
        name = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:г|g|грамм?)$", "", text, flags=re.IGNORECASE).strip()
        return name if name else text, weight
    
    return text, None