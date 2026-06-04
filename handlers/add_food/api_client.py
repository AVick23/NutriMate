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
    
    Приоритет поиска (по официальной документации):
    1. Search-a-licious (SAL) - лучший полнотекстовый поиск [[35]]
    2. API V1 (legacy) - резервный полнотекстовый поиск [[88]]
    3. API V2 - только для фильтров, не для полного поиска [[90]]
    """
    
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"
    
    # Лимиты по официальной документации [[71]], [[43]]
    MAX_SEARCH_PER_MIN = 8  # Безопасно меньше чем 10 req/min
    MAX_PRODUCT_PER_MIN = 12  # Безопасно меньше чем 15 req/min
    
    def __init__(self):
        # ОБЯЗАТЕЛЬНО: Правильный формат User-Agent по документации [[98]], [[76]]
        headers = {
            "User-Agent": "NutriMateBot/1.0 (+https://t.me/nutrimatebot)",
            "Accept": "application/json",
            "X-Application": "NutriMate/1.0",
        }
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0)  # Рекомендуемые таймауты [[111]], [[112]]
        )
        self.client.headers.update(headers)
        
        # Кэш без внешних зависимостей
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_max_size = 100
        
        # Rate limiting
        self._last_search_time: float = 0
        self._last_product_time: float = 0
        self._min_search_interval = 60.0 / self.MAX_SEARCH_PER_MIN
        self._min_product_interval = 60.0 / self.MAX_PRODUCT_PER_MIN

    async def close(self):
        await self.client.aclose()

    async def _rate_limit_search(self):
        """Rate limiting для поисковых запросов [[71]]"""
        now = datetime.now().timestamp()
        if now - self._last_search_time < self._min_search_interval:
            delay = self._min_search_interval - (now - self._last_search_time)
            await asyncio.sleep(delay)
        self._last_search_time = datetime.now().timestamp()

    async def _rate_limit_product(self):
        """Rate limiting для запросов продукта по баркоду [[71]]"""
        now = datetime.now().timestamp()
        if now - self._last_product_time < self._min_product_interval:
            delay = self._min_product_interval - (now - self._last_product_time)
            await asyncio.sleep(delay)
        self._last_product_time = datetime.now().timestamp()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
        retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Основной метод поиска с приоритетом: SAL → V1 → V2 [[35]].
        Реализует exponential backoff при ошибках [[107]], [[113]].
        """
        cache_key = f"{query}:{page}:{page_size}"
        
        if cache_key in self._cache:
            logger.debug(f"Cache hit: {query}")
            return self._cache[cache_key]

        sources = [
            ("SAL", self._search_sal, True),  # Предпочтительный источник [[35]]
            ("V1", self._search_v1, True),    # Legacy fallback [[88]]
            ("V2", self._search_v2, False),   # Не поддерживает full-text [[90]]
        ]

        for source_name, search_method, is_text_search in sources:
            for attempt in range(retries + 1):
                try:
                    await self._rate_limit_search()
                    
                    if is_text_search and not source_name == "V2":
                        products = await search_method(query, page, page_size)
                    else:
                        products = await search_method(query, page, page_size)
                    
                    if products:
                        logger.info(f"{source_name} found {len(products)} products")
                        self._add_to_cache(cache_key, products)
                        return products
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 503:
                        # Отложенная обработка 503 ошибки [[77]], [[74]]
                        logger.warning(f"{source_name} returned 503, retrying...")
                        await asyncio.sleep(1 * (attempt + 1))
                    elif e.response.status_code == 429:
                        # Too Many Requests - увеличиваем задержку [[77]]
                        wait_time = min(60, 5 * (attempt + 1))
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise
                        
                except Exception as e:
                    logger.warning(f"{source_name} attempt {attempt + 1} failed: {e}")
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (attempt + 1))

        logger.error("All API sources failed after retries")
        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через Search-a-licious (SAL).
        Возвращает либо список напрямую, либо объект с ключами "hits" или "products" [[35]].
        """
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
            "search_terms": query,  # Дополнительный параметр для релевантности
        }

        await self._rate_limit_search()
        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()

        products = []

        # Обработка разных форматов ответа SAL [[35]], [[86]]
        if isinstance(data, list):
            for item in data:
                parsed = self._parse_product(item)
                if parsed and parsed.get("kcal_100g"):
                    products.append(parsed)
        elif isinstance(data, dict):
            # Пробуем разные ключи в зависимости от формы ответа
            for key in ["products", "hits"]:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        for item in items:
                            # В hits нужен дополнительный парсинг "_source"
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
        """
        Поиск через API V2 с оператором like.
        НЕ подходит для полного текстового поиска [[90]], но полезен как фоллбэк.
        """
        params = {
            "search_terms": query,
            "operator": "like",
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url,serving_size,nutriscore_grade",
        }

        await self._rate_limit_search()
        response = await self.client.get(self.SEARCH_URL_V2, params=params)
        response.raise_for_status()
        data = response.json()
        
        return self._parse_products(data)

    async def _search_v1(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через устаревший API V1 (legacy).
        Использует веб-форму как бэкенд [[88]].
        """
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
            # Пустой фильтр чтобы не ограничивать слишком агрессивно
            "categories_tags_en": "", 
        }

        await self._rate_limit_search()
        response = await self.client.get(self.SEARCH_URL_V1, params=params)
        response.raise_for_status()
        data = response.json()
        
        return self._parse_products(data)

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Получение продукта по штрихкоду."""
        try:
            await self._rate_limit_product()
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
        # V1/V2 обычно возвращают {"products": [...]}
        for product in data.get("products", []):
            parsed = self._parse_product(product)
            if parsed and parsed.get("kcal_100g"):
                products.append(parsed)
        return products

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсит продукт в единый формат."""
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
        """Извлекает вес из строки формата '500 g'."""
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
            oldest = next(iter(list(self._cache.keys())))
            del self._cache[oldest]
        self._cache[key] = products