"""
Матчер с предобработкой запроса для улучшения результатов поиска.
Использует pymorphy2 + Levenshtein + API fallback.
"""
import re
import logging
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

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
    """Матчер с предобработкой запроса."""

    STOP_WORDS = {
        'с', 'без', 'в', 'на', 'из', 'от', 'до', 'для',
        'к', 'по', 'при', 'и', 'или', 'а', 'но', 'да'
    }

    NUMBER_WORDS = {
        'один': 1, 'одна': 1, 'одно': 1,
        'два': 2, 'две': 2, 'двух': 2,
        'три': 3, 'четыре': 4, 'пять': 5,
        'шесть': 6, 'семь': 7, 'восемь': 8,
        'девять': 9, 'десять': 10,
        'полтора': 1.5, 'полторы': 1.5,
    }

    def __init__(
        self, food_database: List[Dict[str, Any]], api_client=None
    ):
        self.database = food_database
        self.api_client = api_client

        self.morph = None
        if HAS_PYMORPHY:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                logger.info("pymorphy2 инициализирован")
            except Exception as e:
                logger.warning(f"pymorphy2 не загружен: {e}")

    def preprocess_query(self, query: str) -> str:
        """Предобработка запроса: опечатки → парсинг веса → лемматизация."""
        original = query
        query = query.lower().strip()

        if HAS_LEVENSHTEIN and self.database:
            query = self._fix_typos(query)

        query, weight, unit = self.parse_quantity_from_text(original)
        if weight:
            logger.debug(f"Extracted weight: {weight} {unit}")

        words = query.split()
        filtered_words = [w for w in words if w not in self.STOP_WORDS]
        query = ' '.join(filtered_words) if filtered_words else query

        if self.morph:
            query = self._lemmatize_query(query)

        logger.debug(f"Preprocessed: '{original}' → '{query}'")
        return query

    def _fix_typos(self, query: str) -> str:
        """Исправление опечаток через расстояние Левенштейна."""
        words = query.split()
        corrected = []
        for w in words:
            if len(w) < 3:
                corrected.append(w)
                continue

            best_match = None
            best_dist = 2
            for food in self.database:
                name = food["name"].lower()
                for part in name.split():
                    if len(part) >= 3:
                        dist = Levenshtein.distance(w, part)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = part
            corrected.append(best_match if best_match else w)
        return ' '.join(corrected)

    def _lemmatize_query(self, query: str) -> str:
        """Лемматизация запроса."""
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
                except Exception:
                    lemmatized.append(w)
        return ' '.join(lemmatized)

    def parse_quantity_from_text(
        self, text: str
    ) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Парсит вес из текста.
        Возвращает: (очищенный текст, вес, единица измерения).
        """
        original = text
        text = text.strip().lower()
        multiplier = None
        unit = None

        # Паттерн 1: "300г", "1.5 кг", "200 мл"
        match = re.search(
            r'(\d+(?:[.,]\d+)?)\s*(г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|порц)\b',
            text
        )
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

            text = re.sub(
                r'\d+(?:[.,]\d+)?\s*(?:г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|порц)\b',
                '', text
            ).strip()
            return (text if text else original, multiplier, unit)

        # Паттерн 2: "300" в конце строки
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*$', text)
        if match:
            multiplier = float(match.group(1).replace(',', '.'))
            unit = 'г'
            text = text[:match.start()].strip()
            return (text if text else original, multiplier, unit)

        # Паттерн 3: "два яблока"
        for word, num in self.NUMBER_WORDS.items():
            if word in text:
                multiplier = num
                unit = 'шт'
                text = text.replace(word, '').strip()
                return (text if text else original, multiplier, unit)

        return original, None, None

    async def search_with_api_fallback(
        self, user_input: str
    ) -> List[Dict[str, Any]]:
        """Поиск с fallback: API → локальная база."""
        processed_query = self.preprocess_query(user_input)

        if self.api_client:
            try:
                products = await self.api_client.search_products(processed_query)
                if products:
                    logger.info(f"Found {len(products)} products via API")
                    return products
            except Exception as e:
                logger.warning(f"API search failed: {e}")

        if self.database:
            local_results = self._search_local(processed_query)
            if local_results:
                logger.info(f"Found {len(local_results)} products locally")
                return local_results

        return []

    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Простой локальный поиск по подстроке."""
        if not self.database:
            return []

        query = query.lower()
        results = []
        for food in self.database:
            name = food["name"].lower()
            if query in name or any(q in name for q in query.split()):
                results.append(food)
        return results