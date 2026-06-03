# handlers/add_food/utils.py
from typing import Optional, Tuple
from handlers.start.utils import parse_food_text  # просто импортируем из start

# Для обратной совместимости
def parse_food_text(text: str) -> Tuple[str, Optional[float]]:
    return parse_food_text(text)