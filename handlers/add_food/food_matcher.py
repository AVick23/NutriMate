import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)


# Стандартные веса продуктов (для штук, порций)
UNIT_CONVERSION_MAP = {
    "яйцо": 55,       # г
    "банан": 120,     # г
    "яблоко": 150,    # г
    "апельсин": 130,  # г
    "груша": 150,     # г
    "персик": 130,    # г
    "слива": 50,      # г
    "помидор": 120,   # г
    "огурец": 150,    # г
    "картофель": 180, # г
    "хлеб кусок": 30, # г
    "булочка": 80,    # г
    "вареник": 50,    # г
    "пельмень": 40,   # г
    "котлета": 100,   # г
    "сосиска": 70,    # г
    "сосиски (2 шт)": 140,
    "колбаса кусок": 30,
    "сыр кусок": 30,
    "шоколадка": 90,  # средняя плитка
    "пачка чая": 1.5, # г пакетика
    "столовая ложка": 15,  # мл масла/сахара
    "чайная ложка": 5,     # мл/г
    "чашка": 240,        # мл воды
    "стакан": 200,       # мл жидкости
}

# Числа словами
NUMBER_WORDS = {
    'один': 1, 'одна': 1, 'одно': 1, 'одного': 1,
    'два': 2, 'две': 2, 'двух': 2,
    'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8,
    'девять': 9, 'десять': 10,
    'полтора': 1.5, 'полторы': 1.5,
    'двадцать': 20, 'тридцать': 30,
}

# Стоп-слова для очистки запроса
STOP_WORDS = {
    'с', 'без', 'в', 'на', 'из', 'от', 'до', 'для', 'к', 'по', 'при',
    'и', 'или', 'а', 'но', 'да', 'еще', 'там', 'здесь', 'этот', 'эта',
    'это', 'эти', 'мой', 'моя', 'мое', 'мои', 'ваш', 'ваша', 'ваше', 'ваши',
}


class SmartFoodMatcher:
    """
    Умный матчер с предобработкой запроса, поддержкой составных блюд
    и кэшированием популярных паттернов.
    """
    
    def __init__(self, local_database: Optional[List[Dict[str, Any]]] = None):
        """Инициализация матчера с локальной базой."""
        self.local_database = local_database or []
        self._query_cache: Dict[str, str] = {}  # Запрос -> обработанный
        self._conversion_cache: Dict[Tuple[str, str], float] = {}  # (продукт, ед.) -> вес
        
    def preprocess_query(self, query: str) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Предобработка запроса: извлечение веса, очистка, лемматизация.
        Возвращает: (запрос без веса, вес в граммах, единица измерения).
        """
        original = query
        
        # Кэширование для быстрых повторных запросов
        if query in self._query_cache:
            processed, weight, unit = self._query_cache[query]
            return processed, weight, unit
            
        # 1. Извлечение веса из текста
        extracted = self._extract_weight_from_text(query)
        
        # 2. Очистка стоп-слов
        cleaned = self._remove_stop_words(extracted[0])
        
        # 3. Лемматизация (упрощенная)
        normalized = self._normalize_text(cleaned)
        
        result = (normalized, extracted[1], extracted[2])
        self._query_cache[original] = result
        
        # Ограничение размера кэша
        if len(self._query_cache) > 1000:
            oldest_keys = list(self._query_cache.keys())[:100]
            for k in oldest_keys:
                del self._query_cache[k]
                
        return result
        
    def _extract_weight_from_text(self, text: str) -> Tuple[str, Optional[float], Optional[str]]:
        """Извлекает вес и количество из текста."""
        original = text.strip()
        text = text.lower()
        
        # Паттерн 1: число + явная единица (например, "300г", "2 шт", "500мл")
        pattern_explicit = r'(\d+(?:[.,]\d+)?)\s*(г|гр|грамм|gramm|g|kg|грамм|кг|грамм\.)?(\s*(?:мл|ml|л|l|стакан|чашка|ложка|чайная|столовая|кус|кусков|шт|штуки|штук))?(\s*(.+))?$'
        match = re.search(pattern_explicit, text)
        
        if match:
            number_str = match.group(1).replace(',', '.')
            weight_char = match.group(2) or ""
            unit_part = match.group(3) or ""
            rest_text = match.group(4) or ""
            
            try:
                multiplier = float(number_str)
            except ValueError:
                multiplier = None
                
            # Определение единицы измерения
            unit = None
            if weight_char:
                if weight_char.startswith('г') or weight_char.startswith('g'):
                    unit = 'г'
                    final_weight = multiplier
                elif weight_char.startswith('кг'):
                    unit = 'г'
                    final_weight = multiplier * 1000
                elif weight_char.startswith('к'):  # кг или кило
                    unit = 'г'
                    final_weight = multiplier * 1000
                else:
                    final_weight = multiplier
            elif unit_part:
                unit_part_clean = unit_part.strip().split()[0]
                if 'мл' in unit_part_clean or 'ml' in unit_part_clean:
                    unit = 'мл'
                    final_weight = multiplier
                elif 'л' in unit_part_clean or 'l' in unit_part_clean:
                    unit = 'мл'
                    final_weight = multiplier * 1000
                elif 'стакан' in unit_part_clean or 'чашка' in unit_part_clean:
                    unit = 'стакан'
                    final_weight = UNIT_CONVERSION_MAP.get("чашка", 240)
                elif 'ложка' in unit_part_clean:
                    unit = 'ложка'
                    final_weight = 15 if 'столовая' in text else 5
                elif 'шт' in unit_part_clean or 'штук' in unit_part_clean or 'шт.' in unit_part_clean:
                    unit = 'шт'
                    final_weight = multiplier * UNIT_CONVERSION_MAP.get(rest_text.split()[0], 100)
                else:
                    unit = None
                    final_weight = multiplier
            else:
                final_weight = multiplier
            
            # Убираем вес и количество из названия
            name = re.sub(pattern_explicit, '', text).strip()
            return (name if name else original, final_weight, unit)
        
        # Паттерн 2: просто число в конце ("гречка 300")
        pattern_number_end = r'(.+)\s+(\d+(?:[.,]\d+)?)\s*$'
        match = re.search(pattern_number_end, text)
        
        if match:
            name = match.group(1).strip()
            try:
                weight = float(match.group(2).replace(',', '.'))
            except ValueError:
                weight = None
            return (name if name else original, weight, 'г')
        
        # Паттерн 3: словесное число ("два яйца", "полтора банана")
        for word, num in NUMBER_WORDS.items():
            if word in text:
                # Пытаемся найти продукт после слова
                after_word = text.replace(word, '').strip()
                first_word = after_word.split()[0] if after_word.split() else "продукт"
                
                weight = num * UNIT_CONVERSION_MAP.get(first_word, 100)
                return (after_word if after_word else original, weight, 'шт')
        
        # По умолчанию — без веса
        return (original, None, None)
        
    def _remove_stop_words(self, text: str) -> str:
        """Удаляет стоп-слова из текста."""
        words = text.split()
        filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        return ' '.join(filtered)
        
    def _normalize_text(self, text: str) -> str:
        """Нормализация текста (приведение к общему виду)."""
        # Приводим к нижнему регистру
        normalized = text.lower()
        
        # Убираем лишние пробелы
        normalized = ' '.join(normalized.split())
        
        # Заменяем распространенные варианты написания
        replacements = {
            'овсянка': 'овсяная каша',
            'каша': 'каша',
            'пюре': 'пюре',
            'котлету': 'котлета',
            'мясо': 'мясо',
            'птицу': 'птица',
            'курицу': 'курица',
            'рыбку': 'рыба',
            'рисик': 'рис',
            'гречку': 'гречка',
            'макарон': 'макароны',
            'супчик': 'суп',
            'салатик': 'салат',
            'творожок': 'творог',
            'йогурт': 'йогурт',
            'кефирчик': 'кефир',
            'молоко': 'молоко',
            'хлебик': 'хлеб',
            'булочку': 'булочка',
            'пиццу': 'пицца',
            'бургер': 'бургер',
            'гамбургер': 'бургер',
        }
        
        for orig, replacement in replacements.items():
            normalized = normalized.replace(orig, replacement)
            
        return normalized
        
    def split_compound_query(self, query: str) -> List[str]:
        """
        Разбивает составной запрос на компоненты.
        Пример: "гречка с котлетой" → ["гречка", "котлета"]
        """
        separator_patterns = [
            r'\s+с\s+',
            r'\s+и\s+',
            r'\s+на\s+',
            r'\s+в\s+',
            r'\s+без\s+',
        ]
        
        parts = [query]
        for pattern in separator_patterns:
            new_parts = []
            for part in parts:
                splits = re.split(pattern, part)
                new_parts.extend([p.strip() for p in splits if p.strip()])
            parts = new_parts
            
        # Фильтруем слишком короткие части
        return [p for p in parts if len(p) > 2]
        
    async def search_with_api_fallback(
        self,
        user_input: str,
        api_client=None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Основной метод поиска: предобработка → API → локальный fallback.
        """
        # Предобработка
        processed_query, _, _ = self.preprocess_query(user_input)
        
        # Попытка через API
        if api_client:
            try:
                products = await api_client.search_products(processed_query)
                if products:
                    logger.info(f"API found {len(products)} products via '{processed_query}'")
                    # Возвращаем первые limit результатов
                    return [
                        {
                            "code": p.code,
                            "name": p.product_name,
                            "brand": p.brands,
                            "default_weight": p.default_weight,
                            "kcal_100g": p.kcal_per_100g,
                            "protein_100g": p.protein_per_100g,
                            "fat_100g": p.fat_per_100g,
                            "carbs_100g": p.carbs_per_100g,
                            "image_url": p.image_url,
                        }
                        for p in products[:limit]
                    ]
            except Exception as e:
                logger.warning(f"API search failed for '{processed_query}': {e}")
                
        # Fallback на локальный поиск
        if self.local_database:
            local_results = self._search_local(processed_query)
            if local_results:
                logger.info(f"Local DB found {len(local_results)} products for '{processed_query}'")
                return local_results
                
        return []
        
    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Локальный поиск по названию блюда."""
        if not self.local_database:
            return []
            
        query = query.lower()
        results = []
        
        for food in self.local_database:
            name = food.get("name", "").lower()
            
            # Прямое совпадение подстроки
            if query in name:
                results.append(food)
                continue
                
            # Совпадение по отдельным словам
            query_words = query.split()
            matching_words = sum(1 for qw in query_words if any(qw in name.lower() for name_word in name.split()))
            if matching_words >= len(query_words):
                results.append(food)
                
        return results[:10]
        
    def suggest_alternatives(self, query: str, max_suggestions: int = 5) -> List[str]:
        """Генерирует альтернативные формулировки для запроса."""
        suggestions = set()
        suggestions.add(query)
        
        # Варианты с разными артикулами и предлогаами
        base = query.strip()
        variations = [
            base,
            f"{base} отварной",
            f"{base} жареная",
            f"{base} запечённая",
            f"{base} тушёная",
            f"{base} домашний",
            f"{base} магазинный",
            f"{base} натуральный",
            f"{base} диетический",
        ]
        
        for var in variations:
            suggestions.add(var.lower())
            
        return list(suggestions)[:max_suggestions]