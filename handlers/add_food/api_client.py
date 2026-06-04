import asyncio
import httpx
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """
    Клиент для работы с Open Food Facts API.
    Приоритет для текстового поиска: Search-a-licious → API V1.
    """
    
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"
    
    def __init__(self):
        # ВАЖНО: OFF блокирует запросы без User-Agent!
        headers = {
            "User-Agent": "NutriMateBot/1.0 (+https://t.me/nutrimatebot)",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=10.0, headers=headers)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_max_size = 100
        
        # Быстрый rate limiting (2 запроса в секунду)
        self._last_request_time: float = 0
        self._min_interval = 0.5  # 0.5 секунды между запросами
        
        # Кэш для 503 ошибок (не повторять запросы к недоступным эндпоинтам)
        self._failed_endpoints: Dict[str, float] = {}
        self._endpoint_cooldown = 60  # 60 секунд кулдаун после 503

    async def close(self):
        await self.client.aclose()

    async def _rate_limit(self):
        """Быстрый rate limiting."""
        now = datetime.now().timestamp()
        elapsed = now - self._last_request_time
        
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
            
        self._last_request_time = datetime.now().timestamp()

    def _is_endpoint_available(self, endpoint: str) -> bool:
        """Проверяет, доступен ли эндпоинт (не в кулдауне после 503)."""
        if endpoint in self._failed_endpoints:
            cooldown_end = self._failed_endpoints[endpoint]
            if datetime.now().timestamp() < cooldown_end:
                return False
            else:
                # Кулдаун истек, удаляем из списка
                del self._failed_endpoints[endpoint]
        return True

    def _mark_endpoint_failed(self, endpoint: str):
        """Отмечает эндпоинт как недоступный (503 ошибка)."""
        self._failed_endpoints[endpoint] = datetime.now().timestamp() + self._endpoint_cooldown
        logger.warning(f"Endpoint {endpoint} marked as failed for {self._endpoint_cooldown}s")

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
        retries: int = 1  # Уменьшили с 2 до 1 для скорости
    ) -> List[Dict[str, Any]]:
        """
        Основной метод текстового поиска.
        API V2 здесь не используется, так как он не поддерживает полнотекстовый поиск (search_terms).
        """
        cache_key = f"{query}:{page}:{page_size}"
        
        if cache_key in self._cache:
            logger.debug(f"Cache hit: {query}")
            return self._cache[cache_key]

        # 1. Пробуем Search-a-licious (Современный полнотекстовый поиск)
        if self._is_endpoint_available("SAL"):
            for attempt in range(retries + 1):
                try:
                    await self._rate_limit()
                    products = await self._search_sal(query, page, page_size)
                    if products:
                        logger.info(f"Search-a-licious found {len(products)} products")
                        self._add_to_cache(cache_key, products)
                        return products
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 503:
                        logger.warning("SAL returned 503, marking as failed")
                        self._mark_endpoint_failed("SAL")
                        break  # Не повторяем запросы к недоступному эндпоинту
                    elif e.response.status_code == 429:
                        logger.warning("SAL rate limited, marking as failed")
                        self._mark_endpoint_failed("SAL")
                        break
                except Exception as e:
                    logger.warning(f"Search-a-licious attempt {attempt + 1} failed: {e}")
                    if attempt < retries:
                        await asyncio.sleep(0.3 * (attempt + 1))  # Быстрее: 0.3s, 0.6s

        # 2. Резервный API V1 (Legacy полнотекстовый поиск)
        if self._is_endpoint_available("V1"):
            for attempt in range(retries + 1):
                try:
                    await self._rate_limit()
                    products = await self._search_v1(query, page, page_size)
                    if products:
                        logger.info(f"API V1 found {len(products)} products")
                        self._add_to_cache(cache_key, products)
                        return products
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 503:
                        logger.warning("V1 returned 503, marking as failed")
                        self._mark_endpoint_failed("V1")
                        break
                    elif e.response.status_code == 429:
                        logger.warning("V1 rate limited, marking as failed")
                        self._mark_endpoint_failed("V1")
                        break
                except Exception as e:
                    logger.error(f"API V1 attempt {attempt + 1} failed: {e}")
                    if attempt < retries:
                        await asyncio.sleep(0.3 * (attempt + 1))

        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """Поиск через Search-a-licious."""
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
        }

        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Search-a-licious может вернуть список напрямую или объект с "products"/"hits"
        products = []
        
        if isinstance(data, list):
            # SAL вернул массив напрямую
            for item in data:
                parsed = self._parse_product(item)
                if parsed and parsed.get("kcal_100g"):
                    products.append(parsed)
        elif isinstance(data, dict):
            # SAL вернул объект с ключами
            if "products" in data:
                for item in data.get("products", []):
                    parsed = self._parse_product(item)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
            elif "hits" in data:
                # Elasticsearch формат
                for hit in data.get("hits", {}).get("hits", []):
                    item = hit.get("_source", {})
                    parsed = self._parse_product(item)
                    if parsed and parsed.get("kcal_100g"):
                        products.append(parsed)
        
        return products[:page_size]

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """Поиск через устаревший API V1."""
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
        }

        response = await self.client.get(self.SEARCH_URL_V1, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    async def search_by_filters(
        self,
        categories: Optional[str] = None,
        brands: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Отдельный метод для API V2. Используется для фильтрации, а не для текстового поиска.
        Пример: categories="en:chocolates", brands="nestle"
        """
        if not self._is_endpoint_available("V2"):
            logger.warning("V2 endpoint is in cooldown")
            return []

        params = {
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }
        
        if categories:
            params["categories_tags_en"] = categories
        if brands:
            params["brands_tags_en"] = brands

        try:
            await self._rate_limit()
            response = await self.client.get(self.SEARCH_URL_V2, params=params)
            response.raise_for_status()
            data = response.json()
            return self._parse_products(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [503, 429]:
                self._mark_endpoint_failed("V2")
            logger.error(f"API V2 filter search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"API V2 filter search failed: {e}")
            return []

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Получение продукта по штрихкоду."""
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
        """Универсальный парсер для SAL, V1 и V2."""
        products = []
        # Все три API возвращают массив products
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

    def _parse_default_weight(self, quantity: Optional[Any]) -> float:
        """Извлекает вес из строки формата '500 g'."""
        if not quantity:
            return 100.0
            
        # Приводим к строке на случай, если API вернет число
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