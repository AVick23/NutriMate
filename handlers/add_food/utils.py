import re
from typing import Optional, Tuple

# Стандартные веса для популярных продуктов (для штуковой упаковки)
DEFAULT_UNITS = {
    "яйцо": 55, "банан": 120, "яблоко": 150, "апельсин": 130,
    "груша": 150, "персик": 130, "слива": 50, "помидор": 120,
    "огурец": 150, "картофель": 180, "хлеб": 30, "булочка": 80,
    "вареник": 50, "пельмень": 40, "котлета": 100, "сосиска": 70,
    "стакан": 200, "чашка": 240, "ложка столовая": 15, "ложка чайная": 5,
}

# Вес популярных фруктов/овощей за штуку
FRUIT_VEGETABLE_DEFAULTS = {
    "яблоко": 150, "банан": 120, "апельсин": 130, "груша": 150,
    "персик": 130, "слива": 50, "абрикос": 40, "вишня": 15,
    "виноград": 5, "клубника": 15, "малина": 5, "смородина": 3,
    "арбуз": 300, "дыня": 250, "кавун": 300, "манго": 200,
    "лимон": 80, "грейпфрут": 300, "айва": 400, "хурма": 150,
    "томат": 120, "огурец": 150, "перец болгарский": 150,
    "капуста": 500, "морковь": 70, "картофель": 180,
    "редис": 20, "лук": 80, "чеснок": 10, "сельдерей": 40,
    "шпинат": 30, "руккола": 20, "зелень": 5,
}


def parse_food_text(text: str) -> Tuple[str, Optional[float], Optional[str]]:
    """
    Парсит текст вида "омлет 200г" или "банан".
    Возвращает: (название, вес в граммах, единица измерения).
    """
    original = text.strip()
    text_lower = text.lower()
    
    # Паттерн 1: число + явная единица измерения
    patterns_explicit = [
        r'(\d+(?:[.,]\d+)?)\s*(г|грамм|граммов?|гр(?:ам)?|gramme?s?|g\b)',
        r'(\d+(?:[.,]\d+)?)\s*(кг|kilogramm?s?|k[g]?g|\bkilo|kg\b)',
        r'(\d+(?:[.,]\d+)?)\s*(мл|мл\.|milliliter?s?|ml\b)',
        r'(\d+(?:[.,]\d+)?)\s*(л|литр|литров?|liters?|l\b)',
        r'(\d+(?:[.,]\d+)?)\s*(стакан|ст\.|чашка)',
        r'(\d+(?:[.,]\d+)?)\s*(ложка|ложками?|чайную ложку|столовую ложку)',
        r'(\d+(?:[.,]\d+)?)\s*(кус|куска|кусок|кусочки|кусочков)',
        r'(\d+(?:[.,]\d+)?)\s*(шт|штуки|штук|piece|pieces)',
    ]
    
    for pattern in patterns_explicit:
        match = re.search(pattern, text_lower)
        if match:
            number_str = match.group(1).replace(',', '.')
            unit_raw = match.group(2) or ""
            rest = text_lower[max(match.start(), 0):match.end()]
            
            try:
                weight = float(number_str)
            except ValueError:
                weight = None
                
            # Определяем нормализованную единицу
            if unit_raw.startswith(('г', 'gram', 'g')):
                unit = 'г'
                if weight is not None:
                    return (text_lower[:match.start()].strip() or original, weight, unit)
            elif unit_raw.startswith(('к', 'kg', 'kilogram')):
                unit = 'г'
                if weight is not None:
                    return (text_lower[:match.start()].strip() or original, weight * 1000, unit)
            elif unit_raw.startswith(('мл', 'ml')):
                unit = 'мл'
                if weight is not None:
                    return (text_lower[:match.start()].strip() or original, weight, unit)
            elif unit_raw.startswith(('л', 'l')):
                unit = 'мл'
                if weight is not None:
                    return (text_lower[:match.start()].strip() or original, weight * 1000, unit)
            elif 'стакан' in unit_raw or 'чашка' in unit_raw:
                unit = 'стакан'
                return (text_lower[:match.start()].strip() or original, weight * 200 if weight else 200, unit)
            elif 'ложка' in unit_raw:
                unit = 'ложка'
                size = 15 if 'столов' in text_lower else 5
                return (text_lower[:match.start()].strip() or original, weight * size if weight else size, unit)
            elif 'кусов' in unit_raw or 'кусок' in unit_raw:
                unit = 'шт'
                return (text_lower[:match.start()].strip() or original, weight if weight else None, unit)
            elif 'шт' in unit_raw:
                unit = 'шт'
                return (text_lower[:match.start()].strip() or original, weight if weight else None, unit)
                
    # Паттерн 2: просто число в конце ("гречка 300")
    pattern_number_only = r'(.+)\s+(\d+(?:[.,]\d+)?)\s*$'
    match = re.search(pattern_number_only, text_lower)
    if match:
        name = match.group(1).strip()
        try:
            weight = float(match.group(2).replace(',', '.'))
        except ValueError:
            weight = None
        return (name or original, weight, 'г')
    
    # Паттерн 3: упоминание "шт" отдельно ("2 яйца")
    pattern_units_only = r'(\d+(?:[.,]\d+)?)\s*(шт|штуки|штук|pcs|piece)'
    match = re.search(pattern_units_only, text_lower)
    if match:
        count = float(match.group(1).replace(',', '.'))
        # Ищем продукт до числа
        before = text_lower[:match.start()].strip()
        
        # Если есть название продукта, используем его стандартный вес
        if before:
            word_before = before.split()[-1] if before.split() else ""
            base_weight = FRUIT_VEGETABLE_DEFAULTS.get(word_before, DEFAULT_UNITS.get(word_before, 100))
            return (before, count * base_weight, 'г')
            
    # Паттерн 4: слитный "200г" без пробела
    pattern_compact = r'(\d+(?:[.,]\d+)?)\s*г$'
    match = re.search(pattern_compact, text_lower)
    if match:
        weight = float(match.group(1).replace(',', '.'))
        name = text_lower[:match.start()].strip()
        return (name or original, weight, 'г')
    
    # По умолчанию — без веса
    return (original, None, None)


def normalize_weight(weight: float) -> int:
    """Нормализует вес до целых значений."""
    return max(10, min(round(weight), 10000))


def format_nutrient(value: float, units: str = "г") -> str:
    """Форматирует значение нутриента для отображения."""
    if value >= 1000:
        return f"{value / 1000:.1f} кг"
    return f"{value:.1f}{units}"


def extract_product_from_suggestion(text: str) -> str:
    """Извлекает название продукта из предложения/вопроса пользователя."""
    patterns = [
        r'(как добавит.*?\s)(.*?)\s',
        r'(сколько калорий в\s+)(.*?)\s',
        r'(калорийность\s+)(.*?)\s',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(2).strip()
            
    return text