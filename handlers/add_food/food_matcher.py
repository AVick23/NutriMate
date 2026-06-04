# handlers/add_food/food_matcher.py
"""
Упрощённый матчер с предобработкой запроса и приоритетом API.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)

# Внешние зависимости
try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False

try:
    import pymorphy2
    HAS_PYMORPHY = True
except ImportError:
    HAS_PYMORPHY = False


class OptimizedFoodMatcher:
    """
    Матчер с предобработкой запроса для улучшения результатов API.
    Локальная база используется только как резерв.
    """

    # Стоп-слова для удаления из запроса
    STOP_WORDS = {'с', 'без', 'в', 'на', 'из', 'от', 'до', 'для', 'к', 'по', 'при', 'и', 'или', 'а', 'но', 'да'}

    # Числа словами для парсинга количества
    NUMBER_WORDS = {
        'один': 1, 'одна': 1, 'одно': 1,
        'два': 2, 'две': 2, 'двух': 2,
        'три': 3, 'четыре': 4, 'пять': 5,
        'шесть': 6, 'семь': 7, 'восемь': 8,
        'девять': 9, 'десять': 10,
        'полтора': 1.5, 'полторы': 1.5,
    }

    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        self.database = food_database
        self.api_client = api_client

        # Инициализация pymorphy2 (опционально)
        self.morph = None
        if HAS_PYMORPHY:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                logger.info("pymorphy2 инициализирован")
            except Exception as e:
                logger.warning(f"pymorphy2 не загружен: {e}")

    def preprocess_query(self, query: str) -> str:
        """
        Предобработка запроса перед отправкой в API:
        - исправление опечаток
        - удаление стоп-слов
        - лемматизация (опционально)
        """
        original = query
        query = query.lower().strip()

        # 1. Исправление опечаток (если есть библиотека и локальная база)
        if HAS_LEVENSHTEIN and self.database:
            query = self._fix_typos(query)

        # 2. Удаление веса/количества из запроса (отделяем для последующего использования)
        query, weight, unit = self.parse_quantity_from_text(original)
        if weight:
            logger.debug(f"Extracted weight: {weight} {unit}")

        # 3. Удаление стоп-слов
        words = query.split()
        filtered_words = [w for w in words if w not in self.STOP_WORDS]
        query = ' '.join(filtered_words) if filtered_words else query

        # 4. Лемматизация (если есть pymorphy2)
        if self.morph:
            query = self._lemmatize_query(query)

        logger.debug(f"Preprocessed: '{original}' → '{query}'")
        return query

    def _fix_typos(self, query: str) -> str:
        """Исправляет опечатки через расстояние Левенштейна."""
        words = query.split()
        corrected = []
        for w in words:
            if len(w) < 3:
                corrected.append(w)
                continue
            # Ищем наиболее похожее слово среди названий продуктов
            best_match = None
            best_dist = 2
            for food in self.database:
                name = food["name"].lower()
                # Проверяем по словам
                for part in name.split():
                    if len(part) >= 3:
                        dist = Levenshtein.distance(w, part)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = part
            corrected.append(best_match if best_match else w)
        return ' '.join(corrected)

    def _lemmatize_query(self, query: str) -> str:
        """Лемматизация слов запроса."""
        if not self.morph:
            return query
        words = query.split()
        lemmatized = []
        for w in words:
            if len(w) <= 2:
                lemmatized.append(w)
            else:
                try:
                    parsed = self.morph.parse(w)
                    if parsed:
                        lemmatized.append(parsed[0].normal_form)
                    else:
                        lemmatized.append(w)
                except:
                    lemmatized.append(w)
        return ' '.join(lemmatized)

    def parse_quantity_from_text(self, text: str) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Извлекает количество из текста.
        Возвращает (название_блюда, множитель, единица_измерения)
        """
        original = text
        text = text.strip().lower()
        multiplier = None
        unit = None

        # Паттерн 1: число + явная единица ("300г", "2 шт", "500мл")
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|порц)\b', text)
        if match:
            multiplier = float(match.group(1).replace(',', '.'))
            raw = match.group(2)
            if raw in ('г', 'гр', 'g', 'gr'):
                unit = 'г'
            elif raw in ('кг', 'kg'):
                unit = 'г'
                multiplier *= 1000
            elif raw in ('мл', 'ml'):
                unit = 'мл'
            elif raw in ('л', 'l'):
                unit = 'мл'
                multiplier *= 1000
            else:
                unit = 'шт'
            text = re.sub(r'\d+(?:[.,]\d+)?\s*(?:г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|порц)\b', '', text).strip()
            return (text if text else original, multiplier, unit)

        # Паттерн 2: просто число в конце ("гречка 300")
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*$', text)
        if match:
            multiplier = float(match.group(1).replace(',', '.'))
            unit = 'г'
            text = text[:match.start()].strip()
            return (text if text else original, multiplier, unit)

        # Паттерн 3: словесное число ("два яйца", "полтора банана")
        for word, num in self.NUMBER_WORDS.items():
            if word in text:
                multiplier = num
                unit = 'шт'
                text = text.replace(word, '').strip()
                return (text if text else original, multiplier, unit)

        return original, None, None

    async def search_with_api_fallback(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Основной метод: предобработка → API → при ошибке локальный поиск.
        """
        # Предобработка запроса
        processed_query = self.preprocess_query(user_input)

        # Поиск через API
        if self.api_client:
            try:
                products = await self.api_client.search_products(processed_query)
                if products:
                    logger.info(f"Found {len(products)} products via API")
                    return products
            except Exception as e:
                logger.warning(f"API search failed: {e}")

        # Fallback на локальный поиск
        if self.database:
            local_results = self._search_local(processed_query)
            if local_results:
                logger.info(f"Found {len(local_results)} products locally")
                return local_results

        return []

    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Простой локальный поиск по ключевым словам."""
        if not self.database:
            return []
        query = query.lower()
        results = []
        for food in self.database:
            name = food["name"].lower()
            # Простое совпадение подстроки
            if query in name or any(q in name for q in query.split()):
                results.append(food)
        return results[:5]

    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Синхронная заглушка (не используется)."""
        return None


class SyncFoodMatcher:
    """Синхронная обёртка для совместимости."""
    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        self._matcher = OptimizedFoodMatcher(food_database, api_client)

    def search(self, user_input: str) -> List[Dict[str, Any]]:
        return []

    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        return None

    def parse_quantity_from_text(self, text: str) -> Tuple[str, Optional[float], Optional[str]]:
        return self._matcher.parse_quantity_from_text(text)