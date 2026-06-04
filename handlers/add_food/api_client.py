# handlers/add_food/api_client.py
import asyncio
import httpx
import logging
import re
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """
    Клиент для работы с Open Food Facts API.
    Надёжный выбор: Search-a-licious → API V2 → API V1.
    """

    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

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
        Основной метод поиска с приоритетом: Search-a-licious → API V2 → API V1.
        """
        cache_key = f"{query}:{page}:{page_size}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit: {query}")
            return self._cache[cache_key]

        # 1. Пробуем Search-a-licious (экспериментальный, но самый современный)
        for attempt in range(retries + 1):
            try:
                products = await self._search_sal(query, page, page_size)
                if products:
                    logger.info(f"Search-a-licious found {len(products)} products")
                    self._add_to_cache(cache_key, products)
                    return products
            except Exception as e:
                logger.warning(f"Search-a-licious attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # 2. Пробуем API V2 (стабильный, современный)
        try:
            products = await self._search_v2(query, page, page_size)
            if products:
                logger.info(f"API V2 found {len(products)} products")
                self._add_to_cache(cache_key, products)
                return products
        except Exception as e:
            logger.warning(f"API V2 failed: {e}")

        # 3. Резервный API V1 (устаревший, но надёжный)
        try:
            products = await self._search_v1(query, page, page_size)
            if products:
                logger.info(f"API V1 found {len(products)} products")
                self._add_to_cache(cache_key, products)
                return products
        except Exception as e:
            logger.error(f"API V1 also failed: {e}")

        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через Search-a-licious с улучшенной обработкой ответов.
        """
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
        }

        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()
        products = []

        if isinstance(data, list):
            for product in data:
                parsed = self._parse_product(product)
                if parsed and parsed.get("kcal_100g"):
                    products.append(parsed)
        elif isinstance(data, dict):
            if "products" in data:
                for product in data.get("products", []):
                    parsed = self._parse_product(product)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
            elif "hits" in data:
                for hit in data.get("hits", {}).get("hits", []):
                    product = hit.get("_source", {})
                    parsed = self._parse_product(product)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)

        return products

    async def _search_v2(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через API V2 с оператором like для нечёткого поиска.
        """
        params = {
            "search_terms": query,
            "operator": "like",
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }

        response = await self.client.get(self.SEARCH_URL_V2, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через устаревший API V1.
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

        response = await self.client.get(self.SEARCH_URL_V1, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Получение продукта по штрихкоду.
        """
        try:
            response = await self.client.get(f"{self.PRODUCT_URL}/{barcode}.json")
            response.raise_for_status()
            data = response.json()
            product = data.get("product")
            if product and product.get("nutriments"):
                return self._parse_product(product)
            return None
        except Exception as e:
            logger.error(f"Barcode lookup failed for {barcode}: {e}")
            return None

    def _parse_products(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлекает и парсит продукты из ответа API V1/V2."""
        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)
        return products

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсит продукт в единый формат."""
        nutriments = product.get("nutriments", {})
        
        kcal_100g = nutriments.get("energy-kcal_100g")
        if not kcal_100g:
            kcal_100g = nutriments.get("energy-kcal")
        if not kcal_100g:
            return None

        protein_100g = nutriments.get("proteins_100g", 0) or 0
        fat_100g = nutriments.get("fat_100g", 0) or 0
        carbs_100g = nutriments.get("carbohydrates_100g", 0) or 0

        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)

        return {
            "code": product.get("code", ""),
            "name": product.get("product_name", "Неизвестный продукт"),
            "brand": product.get("brands", ""),
            "quantity": quantity,
            "default_weight": default_weight,
            "kcal_100g": float(kcal_100g),
            "protein_100g": float(protein_100g),
            "fat_100g": float(fat_100g),
            "carbs_100g": float(carbs_100g),
            "image_url": product.get("image_url"),
        }

    def _parse_default_weight(self, quantity: Optional[str]) -> float:
        """Извлекает вес из строки формата '500 g'."""
        if not quantity:
            return 100.0
            
        match = re.search(r"(\d+(?:\.\d+)?)\s*(g|kg|ml|l|мл|кг|г)", quantity.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit in ("kg", "кг"):
                return value * 1000
            if unit in ("l", "л"):
                return value * 1000
            return value
        return 100.0

    def calculate_for_weight(self, product: Dict[str, Any], weight: float) -> Dict[str, Any]:
        """Пересчитывает КБЖУ на указанный вес в граммах."""
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
        """LRU-кэш для результатов поиска."""
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = products