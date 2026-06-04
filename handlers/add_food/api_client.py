# handlers/add_food/api_client.py
import asyncio
import httpx
import logging
import re
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """Клиент для работы с Open Food Facts API V3."""

    # API V3 на Elasticsearch (поддерживает нечёткий поиск)
    BASE_URL = "https://search.openfoodfacts.org/api/v2/search"
    
    # Резервный URL на случай недоступности V3
    FALLBACK_URL = "https://world.openfoodfacts.org/cgi/search.pl"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_max_size = 100

    async def close(self):
        await self.client.aclose()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
        retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Поиск продуктов с использованием API V3 (нечёткий поиск).
        При ошибке пробует V1, затем retry.
        """
        # Проверяем кэш
        cache_key = f"{query}:{page}:{page_size}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit for: {query}")
            return self._cache[cache_key]

        # Сначала пробуем API V3 (рекомендуется)
        for attempt in range(retries + 1):
            try:
                products = await self._search_v3(query, page, page_size)
                if products:
                    self._add_to_cache(cache_key, products)
                    return products
            except Exception as e:
                logger.warning(f"API V3 attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # Пробуем API V1 (старый, но надёжный)
        try:
            products = await self._search_v1(query, page, page_size)
            if products:
                self._add_to_cache(cache_key, products)
                return products
        except Exception as e:
            logger.error(f"API V1 also failed: {e}")

        return []

    async def _search_v3(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через API V3 (Elasticsearch) с нечётким сопоставлением.
        """
        params = {
            "search_terms": query,
            "operator": "like",          # включает нечёткий поиск
            "sort_by": "popularity",     # сортировка по популярности
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }

        response = await self.client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)

        logger.info(f"API V3 found {len(products)} products for '{query}'")
        return products

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Резервный поиск через старый API V1.
        """
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }

        response = await self.client.get(self.FALLBACK_URL, params=params)
        response.raise_for_status()
        data = response.json()

        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)

        logger.info(f"API V1 found {len(products)} products for '{query}'")
        return products

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсит продукт из ответа API в унифицированный формат."""
        nutriments = product.get("nutriments", {})

        # Калории на 100 г
        kcal_100g = nutriments.get("energy-kcal_100g")
        if not kcal_100g:
            kcal_100g = nutriments.get("energy-kcal")
        if not kcal_100g:
            return None

        protein_100g = nutriments.get("proteins_100g", 0)
        fat_100g = nutriments.get("fat_100g", 0)
        carbs_100g = nutriments.get("carbohydrates_100g", 0)

        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)

        return {
            "code": product.get("code", ""),
            "name": product.get("product_name", "Неизвестный продукт"),
            "brand": product.get("brands", ""),
            "quantity": quantity,
            "default_weight": default_weight,
            "kcal_100g": float(kcal_100g),
            "protein_100g": float(protein_100g) if protein_100g else 0,
            "fat_100g": float(fat_100g) if fat_100g else 0,
            "carbs_100g": float(carbs_100g) if carbs_100g else 0,
            "image_url": product.get("image_url"),
        }

    def _parse_default_weight(self, quantity: Optional[str]) -> float:
        """Извлекает вес из строки quantity."""
        if not quantity:
            return 100.0

        match = re.search(r"(\d+(?:\.\d+)?)\s*(g|kg|ml|l)", quantity.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit == "kg":
                value *= 1000
            elif unit == "l":
                value *= 1000
            return value
        return 100.0

    def calculate_for_weight(self, product: Dict[str, Any], weight: float) -> Dict[str, Any]:
        """Рассчитывает КБЖУ для указанного веса."""
        multiplier = weight / 100.0
        return {
            "code": product.get("code", ""),
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "weight": weight,
            "kcal": round(product.get("kcal_100g", 0) * multiplier),
            "protein": round(product.get("protein_100g", 0) * multiplier, 1),
            "fat": round(product.get("fat_100g", 0) * multiplier, 1),
            "carbs": round(product.get("carbs_100g", 0) * multiplier, 1),
            "image_url": product.get("image_url"),
        }

    def _add_to_cache(self, key: str, products: List[Dict[str, Any]]):
        """Добавляет результат в LRU-кэш."""
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            # Удаляем самый старый элемент
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = products

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Получение продукта по штрихкоду (через API V3)."""
        # Для штрихкода используем точный поиск
        return await self._search_v3(barcode, 1, 1).__anext__() if self._search_v3(barcode, 1, 1) else None