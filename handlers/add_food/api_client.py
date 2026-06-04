# handlers/add_food/api_client.py
"""
Клиент для работы с Open Food Facts API.
Поддерживает три API с умным fallback:
1. Search-a-licious (Elasticsearch, нечёткий поиск)
2. API V2 (стабильный, оператор like)
3. API V1 (устаревший, резервный)
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
    """Клиент с автоматическим выбором API и обработкой ошибок."""

    # URL API
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

    # Лимиты (для соблюдения)
    RATE_LIMIT_SEARCH = 10      # запросов в минуту
    RATE_LIMIT_PRODUCT = 100    # запросов в минуту

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._cache_max_size = 100
        self._cache_ttl_seconds = 300  # 5 минут

    async def close(self):
        await self.client.aclose()

    # ========== ОСНОВНОЙ МЕТОД ПОИСКА ==========

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Основной метод поиска с умным fallback.
        Порядок: Search-a-licious → API V2 → API V1
        """
        cache_key = f"{query}:{page}:{page_size}"
        
        # Проверка кэша с TTL
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for: {query}")
                return self._cache[cache_key].get("products", [])
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        # 1. Search-a-licious (самый современный)
        products = await self._search_with_retry(
            self._search_sal, query, page, page_size,
            api_name="Search-a-licious"
        )
        if products:
            self._add_to_cache(cache_key, products)
            return products

        # 2. API V2 (стабильный)
        products = await self._search_with_retry(
            self._search_v2, query, page, page_size,
            api_name="API V2"
        )
        if products:
            self._add_to_cache(cache_key, products)
            return products

        # 3. API V1 (резервный)
        products = await self._search_with_retry(
            self._search_v1, query, page, page_size,
            api_name="API V1"
        )
        if products:
            self._add_to_cache(cache_key, products)
            return products

        return []

    # ========== МЕТОДЫ ПОИСКА ПО ОТДЕЛЬНЫМ API ==========

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Search-a-licious — новая поисковая система на Elasticsearch.
        Поддерживает разные форматы ответов (list, dict с products, dict с hits).
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
        
        # Универсальный парсинг для разных форматов ответа
        if isinstance(data, list):
            # Прямой список продуктов
            for product in data:
                parsed = self._parse_product(product)
                if parsed and parsed.get("kcal_100g"):
                    products.append(parsed)
        elif isinstance(data, dict):
            # Формат {"products": [...]}
            if "products" in data:
                for product in data.get("products", []):
                    parsed = self._parse_product(product)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
            # Формат Elasticsearch {"hits": {"hits": [...]}}
            elif "hits" in data:
                for hit in data.get("hits", {}).get("hits", []):
                    product = hit.get("_source", {})
                    parsed = self._parse_product(product)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)

        return products

    async def _search_v2(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        API V2 с оператором like для нечёткого поиска.
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
        return self._parse_products_v2(data)

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        API V1 (устаревший, но надёжный резерв).
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
        return self._parse_products_v1(data)

    # ========== ПОИСК ПО ШТРИХКОДУ ==========

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Получение продукта по штрихкоду (отдельный стабильный эндпоинт).
        """
        cache_key = f"barcode:{barcode}"
        
        # Проверка кэша
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                return self._cache[cache_key].get("product")
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        try:
            response = await self.client.get(f"{self.PRODUCT_URL}/{barcode}.json")
            response.raise_for_status()
            data = response.json()
            
            product = data.get("product")
            if product and product.get("nutriments"):
                parsed = self._parse_product(product)
                self._add_to_cache(cache_key, {"product": parsed})
                return parsed
            return None
        except Exception as e:
            logger.error(f"Barcode lookup failed for {barcode}: {e}")
            return None

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    async def _search_with_retry(
        self,
        search_func,
        query: str,
        page: int,
        page_size: int,
        api_name: str,
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Универсальный метод с экспоненциальной задержкой и джиттером.
        """
        for attempt in range(max_retries):
            try:
                products = await search_func(query, page, page_size)
                if products:
                    logger.info(f"{api_name} found {len(products)} products for '{query}'")
                    return products
                else:
                    logger.debug(f"{api_name} returned empty for '{query}'")
                    return []
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                retry_after = self._get_retry_after(e.response)
                
                if self._is_retryable_error(status_code):
                    if attempt < max_retries - 1:
                        delay = self._calculate_backoff(attempt, retry_after)
                        logger.warning(f"{api_name} attempt {attempt + 1} failed with {status_code}, retrying in {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"{api_name} failed after {max_retries} attempts: {status_code}")
                else:
                    # Не retryable ошибка (4xx кроме 429)
                    logger.error(f"{api_name} non-retryable error: {status_code} for '{query}'")
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(f"{api_name} attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{api_name} failed after {max_retries} attempts: {e}")
        return []

    def _is_retryable_error(self, status_code: int) -> bool:
        """Проверяет, стоит ли повторять запрос."""
        # 5xx (серверные ошибки) и 429 (Too Many Requests) — повторяем
        return status_code >= 500 or status_code == 429

    def _get_retry_after(self, response: httpx.Response) -> Optional[int]:
        """Извлекает значение Retry-After из заголовка."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                # Может быть HTTP-дата, но для простоты игнорируем
                pass
        return None

    def _calculate_backoff(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        Рассчитывает задержку с экспоненциальным ростом и джиттером.
        """
        if retry_after:
            return float(retry_after)
        
        # Экспоненциальная задержка: 2^attempt секунд
        base_delay = 2 ** attempt
        # Добавляем джиттер (±30%)
        jitter = random.uniform(0.7, 1.3)
        return base_delay * jitter

    def _parse_products_v2(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсит ответ API V2."""
        products = []
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)
        return products

    def _parse_products_v1(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсит ответ API V1."""
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

    def _add_to_cache(self, key: str, products: Union[List, Dict]):
        """Добавляет результат в LRU-кэш с TTL."""
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            del self._cache_ttl[oldest]
        self._cache[key] = {"products": products} if isinstance(products, list) else products
        self._cache_ttl[key] = time.time()