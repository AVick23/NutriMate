"""
Утилиты для обработки текста еды (fallback-парсер).
Основной парсинг — в food_matcher.py.
"""
import re
from typing import Optional, Tuple, Dict, Any


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


def parse_manual_template(text: str) -> Optional[Dict[str, Any]]:
    """
    🎯 Умный парсер ручного ввода.
    
    Понимает форматы:
    
    Формат 1 (многострочный):
        Гречка с котлетой
        350г
        578 ккал
        Б: 33.3г
        Ж: 28.7г
        У: 49.0г
    
    Формат 2 (одна строка):
        Гречка с котлетой 350г 578ккал Б33.3 Ж28.7 У49
    
    Формат 3 (минимальный):
        Гречка с котлетой 578ккал
        (вес и макросы опциональны)
    
    Возвращает dict с полями:
    - name (обязательно)
    - weight (опционально, дефолт 100)
    - kcal (обязательно)
    - protein (опционально)
    - fat (опционально)
    - carbs (опционально)
    """
    text = text.strip()
    if not text:
        return None
    
    result = {
        "name": None,
        "weight": 100.0,
        "kcal": None,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
    }
    
    # Попытка 1: Парсим вес (число + г/гр/gram)
    weight_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:г|гр|g|gram|грамм)\b', text, re.IGNORECASE)
    if weight_match:
        result["weight"] = float(weight_match.group(1).replace(',', '.'))
        text = text[:weight_match.start()] + text[weight_match.end():]
    
    # Попытка 2: Парсим калории (число + ккал/kcal)
    kcal_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:ккал|kcal|калорий)\b', text, re.IGNORECASE)
    if kcal_match:
        result["kcal"] = int(float(kcal_match.group(1).replace(',', '.')))
        text = text[:kcal_match.start()] + text[kcal_match.end():]
    
    # Попытка 3: Парсим белки (Б: число / белки: число / protein: число)
    protein_match = re.search(r'(?:Б|белки?|protein)[:\s]*(\d+(?:[.,]\d+)?)\s*(?:г|g)?', text, re.IGNORECASE)
    if protein_match:
        result["protein"] = float(protein_match.group(1).replace(',', '.'))
        text = text[:protein_match.start()] + text[protein_match.end():]
    
    # Попытка 4: Парсим жиры (Ж: число / жиры: число / fat: число)
    fat_match = re.search(r'(?:Ж|жиры?|fat)[:\s]*(\d+(?:[.,]\d+)?)\s*(?:г|g)?', text, re.IGNORECASE)
    if fat_match:
        result["fat"] = float(fat_match.group(1).replace(',', '.'))
        text = text[:fat_match.start()] + text[fat_match.end():]
    
    # Попытка 5: Парсим углеводы (У: число / углеводы: число / carbs: число)
    carbs_match = re.search(r'(?:У|углеводы?|carbs|carbohydrates)[:\s]*(\d+(?:[.,]\d+)?)\s*(?:г|g)?', text, re.IGNORECASE)
    if carbs_match:
        result["carbs"] = float(carbs_match.group(1).replace(',', '.'))
        text = text[:carbs_match.start()] + text[carbs_match.end():]
    
    # Остаток текста — это название
    result["name"] = text.strip()
    
    # Валидация
    if not result["name"]:
        return None
    if result["kcal"] is None or result["kcal"] <= 0:
        return None
    
    return result


def format_manual_product_for_confirmation(product: Dict[str, Any]) -> str:
    """
    Форматирует продукт для экрана подтверждения.
    """
    text = f"🍳 <b>{product['name']}</b>\n"
    text += f"⚖️ {product['weight']:.0f}г\n\n"
    text += f"🔥 {product['kcal']} ккал\n"
    
    if product.get("protein") or product.get("fat") or product.get("carbs"):
        text += f"🍗 {product.get('protein', 0):.1f}г · "
        text += f"🥑 {product.get('fat', 0):.1f}г · "
        text += f"🍚 {product.get('carbs', 0):.1f}г"
    
    return text