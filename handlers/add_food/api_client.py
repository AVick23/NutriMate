# handlers/add_food/api_client.py
"""
Финальная версия клиента Open Food Facts с поддержкой трёх API.
Корректно обрабатывает все известные форматы ответов.
"""

import asyncio
import httpx
import logging
import re
import time
import random
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._cache_max_size = 100
        self._cache_ttl_seconds = 300  # 5 минут

    async def close(self):
        await self.client.aclose()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
    ) -> List[Dict[str, Any]]:
        cache_key = f"{query}:{page}:{page_size}"
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for: {query}")
                return self._cache[cache_key].get("products", [])
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        # 1. Search-a-licious
        products = await self._search_with_retry(self._search_sal, query, page, page_size, "Search-a-licious")
        if products:
            self._add_to_cache(cache_key, products)
            return products

        # 2. API V2
        products = await self._search_with_retry(self._search_v2, query, page, page_size, "API V2")
        if products:
            self._add_to_cache(cache_key, products)
            return products

        # 3. API V1
        products = await self._search_with_retry(self._search_v1, query, page, page_size, "API V1")
        if products:
            self._add_to_cache(cache_key, products)
            return products

        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {"q": query, "page": page, "page_size": page_size}
        resp = await self.client.get(self.SEARCH_URL_SAL, params=params)
        resp.raise_for_status()
        data = resp.json()

        products = []
        # 🔥 Ключевое исправление: обработка случая, когда data — список
        if isinstance(data, list):
            logger.debug(f"Search-a-licious returned a list of {len(data)} items")
            for item in data:
                if isinstance(item, dict):
                    parsed = self._parse_product(item)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
        elif isinstance(data, dict):
            products_data = data.get("products") or data.get("hits", {}).get("hits", [])
            if products_data:
                for p in products_data:
                    product = p.get("_source", p) if isinstance(p, dict) else p
                    parsed = self._parse_product(product)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
        else:
            logger.warning(f"Unexpected data type from Search-a-licious: {type(data)}")
        return products

    async def _search_v2(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {
            "search_terms": query,
            "operator": "like",
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }
        resp = await self.client.get(self.SEARCH_URL_V2, params=params)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_standard_products(data)

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }
        resp = await self.client.get(self.SEARCH_URL_V1, params=params)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_standard_products(data)

    def _parse_standard_products(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)
        return products

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        cache_key = f"barcode:{barcode}"
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                return self._cache[cache_key].get("product")
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        try:
            resp = await self.client.get(f"{self.PRODUCT_URL}/{barcode}.json")
            resp.raise_for_status()
            data = resp.json()
            product = data.get("product")
            if product and product.get("nutriments"):
                parsed = self._parse_product(product)
                self._add_to_cache(cache_key, {"product": parsed})
                return parsed
            return None
        except Exception as e:
            logger.error(f"Barcode lookup failed for {barcode}: {e}")
            return None

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nutriments = product.get("nutriments", {})
        kcal_100g = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
        if not kcal_100g:
            return None
        protein = nutriments.get("proteins_100g", 0) or 0
        fat = nutriments.get("fat_100g", 0) or 0
        carbs = nutriments.get("carbohydrates_100g", 0) or 0
        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)
        return {
            "code": product.get("code", ""),
            "name": product.get("product_name", "Неизвестный продукт"),
            "brand": product.get("brands", ""),
            "quantity": quantity,
            "default_weight": default_weight,
            "kcal_100g": float(kcal_100g),
            "protein_100g": float(protein),
            "fat_100g": float(fat),
            "carbs_100g": float(carbs),
            "image_url": product.get("image_url"),
        }

    def _parse_default_weight(self, quantity: Optional[str]) -> float:
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

    async def _search_with_retry(self, func, query, page, page_size, api_name, max_retries=3):
        for attempt in range(max_retries):
            try:
                products = await func(query, page, page_size)
                if products:
                    logger.info(f"{api_name} found {len(products)} products for '{query}'")
                    return products
                else:
                    logger.debug(f"{api_name} returned empty for '{query}'")
                    return []
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                retry_after = self._get_retry_after(e.response)
                if self._is_retryable(status):
                    if attempt < max_retries - 1:
                        delay = self._calc_backoff(attempt, retry_after)
                        logger.warning(f"{api_name} attempt {attempt+1} failed with {status}, retrying in {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"{api_name} failed after {max_retries} attempts: {status}")
                        return []
                else:
                    logger.error(f"{api_name} non-retryable error {status}")
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = self._calc_backoff(attempt)
                    logger.warning(f"{api_name} attempt {attempt+1} failed: {e}, retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{api_name} failed after {max_retries} attempts: {e}")
        return []

    def _is_retryable(self, status: int) -> bool:
        return status >= 500 or status == 429

    def _get_retry_after(self, response: httpx.Response) -> Optional[int]:
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                return int(ra)
            except:
                pass
        return None

    def _calc_backoff(self, attempt: int, retry_after: Optional[int] = None) -> float:
        if retry_after:
            return float(retry_after)
        base = 2 ** attempt
        jitter = random.uniform(0.7, 1.3)
        return base * jitter

    def _add_to_cache(self, key: str, products: Union[List, Dict]):
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            del self._cache_ttl[oldest]
        self._cache[key] = {"products": products} if isinstance(products, list) else products
        self._cache_ttl[key] = time.time()