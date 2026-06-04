import asyncio
import httpx
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """Клиент для работы с Open Food Facts API."""

    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

    def __init__(self):
        headers = {
            "User-Agent": "NutriMateBot/1.0 (+https://t.me/nutrimatebot)",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=15.0, headers=headers)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_max_size = 100
        self._last_request_time = 0

    async def close(self):
        await self.client.aclose()

    async def _rate_limit(self):
        """Минимальная задержка между запросами."""
        now = datetime.now().timestamp()
        if now - self._last_request_time < 0.5:
            delay = 0.5 - (now - self._last_request_time)
            await asyncio.sleep(delay)
        self._last_request_time = datetime.now().timestamp()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
        retries: int = 2
    ) -> List[Dict[str, Any]]:
        """Основной метод поиска."""
        cache_key = f"{query}:{page}:{page_size}"

        if cache_key in self._cache:
            logger.debug(f"Cache hit: {query}")
            return self._cache[cache_key]

        for attempt in range(retries + 1):
            try:
                await self._rate_limit()
                products = await self._search_sal(query, page, page_size)
                if products:
                    logger.info(f"Search-a-licious found {len(products)} products")
                    self._add_to_cache(cache_key, products)
                    return products
            except Exception as e:
                logger.warning(f"SAL attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        try:
            await self._rate_limit()
            products = await self._search_v2(query, page, page_size)
            if products:
                logger.info(f"API V2 found {len(products)} products")
                self._add_to_cache(cache_key, products)
                return products
        except Exception as e:
            logger.warning(f"API V2 failed: {e}")

        try:
            await self._rate_limit()
            products = await self._search_v1(query, page, page_size)
            if products:
                logger.info(f"API V1 found {len(products)} products")
                self._add_to_cache(cache_key, products)
                return products
        except Exception as e:
            logger.error(f"API V1 also failed: {e}")

        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {"q": query, "page": page, "page_size": page_size}

        await self._rate_limit()
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
            for key in ["products", "hits"]:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        for item in items:
                            if key == "hits":
                                product = item.get("_source", {})
                            else:
                                product = item
                            parsed = self._parse_product(product)
                            if parsed and parsed.get("kcal_100g"):
                                products.append(parsed)
                    break

        return products[:page_size]

    async def _search_v2(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {
            "search_terms": query,
            "operator": "like",
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url,serving_size",
        }

        await self._rate_limit()
        response = await self.client.get(self.SEARCH_URL_V2, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
        }

        await self._rate_limit()
        response = await self.client.get(self.SEARCH_URL_V1, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        try:
            await self._rate_limit()
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
        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)
        return products

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nutriments = product.get("nutriments", {})

        kcal_100g = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
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

    def _parse_default_weight(self, quantity: Optional[Any]) -> float:
        if not quantity:
            return 100.0

        match = re.search(r"(\d+(?:\.\d+)?)\s*(g|kg|ml|l|мл|кг|г)", str(quantity).lower())
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
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = products