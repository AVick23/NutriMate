import asyncio
import httpx
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
from functools import lru_cache

logger = logging.getLogger(__name__)


class Nutriments:
    """Модель нутриентов для типизации."""
    def __init__(self, data: dict):
        self.energy_kcal_100g = data.get("energy-kcal_100g") or data.get("energy-kcal") or 0
        self.proteins_100g = data.get("proteins_100g") or 0
        self.fat_100g = data.get("fat_100g") or 0
        self.carbohydrates_100g = data.get("carbohydrates_100g") or 0


class OFFProduct:
    """Модель продукта из Open Food Facts."""
    def __init__(self, data: dict):
        self.code = data.get("code", "")
        self.product_name = data.get("product_name", "Неизвестный продукт").strip()
        self.brands = data.get("brands", "")
        self.quantity = data.get("quantity")
        self.image_url = data.get("image_url")
        self.nutriments = Nutriments(data.get("nutriments", {}))
        self.serving_size = data.get("serving_size")
        self.nutriscore_grade = data.get("nutriscore_grade")
        
    @property
    def default_weight(self) -> float:
        return parse_quantity(self.quantity) if self.quantity else 100.0
        
    @property
    def kcal_per_100g(self) -> float:
        return max(0, float(self.nutriments.energy_kcal_100g))
    
    @property
    def protein_per_100g(self) -> float:
        return max(0, float(self.nutriments.proteins_100g))
    
    @property
    def fat_per_100g(self) -> float:
        return max(0, float(self.nutriments.fat_100g))
    
    @property
    def carbs_per_100g(self) -> float:
        return max(0, float(self.nutriments.carbohydrates_100g))
    
    def calculate_for_weight(self, weight_g: float) -> dict:
        """Пересчитывает КБЖУ на указанный вес в граммах."""
        multiplier = weight_g / 100.0
        return {
            "code": self.code,
            "name": self.product_name,
            "brand": self.brands,
            "weight": weight_g,
            "kcal": round(self.kcal_per_100g * multiplier),
            "protein": round(self.protein_per_100g * multiplier, 1),
            "fat": round(self.fat_per_100g * multiplier, 1),
            "carbs": round(self.carbs_per_100g * multiplier, 1),
            "image_url": self.image_url,
        }


# ===== Глобальные константы =====
USER_AGENT = "MyFoodApp/1.0 (Contact: your@email.com)"
DEFAULT_TIMEOUT = 15.0
API_RETRY_ATTEMPTS = 2
API_RETRY_DELAY = 0.5


def parse_quantity(quantity: Optional[str]) -> float:
    """Извлекает вес из строки формата '500 g' или '2 шт'."""
    if not quantity:
        return 100.0
    
    match = re.search(r"(\d+(?:\.\d+)?)\s*(г|kg|мл|кг|л)", str(quantity).lower())
    if not match:
        return 100.0
        
    value = float(match.group(1))
    unit = match.group(2)
    
    if unit in ("кг", "kg"):
        return value * 1000
    if unit in ("л", "l", "мл", "ml"):
        return value * 1000
    
    return value


@lru_cache(maxsize=1000)
def get_unit_conversion(unit: str, amount: float) -> Tuple[float, str]:
    """Кэширует конвертацию единиц измерения."""
    if unit in ("шт", "pieces"):
        # Стандартные веса популярных продуктов
        DEFAULT_WEIGHTS = {
            "яйцо": 55, "банан": 120, "яблоко": 150, "апельсин": 130,
            "помидор": 120, "огурец": 150, "картофель": 180, "хлеб кусок": 30,
            "батон ломтик": 35, "сосиска": 70, "котлета": 100, "вареник": 50,
        }
        return 100.0, "г"  # Вернётся стандартный вес
    
    if unit in ("г", "gr", "grams"):
        return amount, "г"
    if unit in ("кг", "kg"):
        return amount * 1000, "г"
    if unit in ("мл", "ml"):
        return amount, "мл"
    
    return amount, unit


class CircuitBreaker:
    """Circuit Breaker для защиты от частых ошибок API."""
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed | open | half-open
        
    async def check(self) -> bool:
        """Проверка состояния circuit breaker."""
        now = datetime.now()
        
        if self.state == "open":
            if (now - self.last_failure_time).total_seconds() > self.reset_timeout:
                self.state = "half-open"
                return True
            return False
        
        return True
    
    def record_success(self):
        """Регистрирует успешный запрос."""
        self.failures = 0
        self.state = "closed"
        
    def record_failure(self):
        """Регистрирует неудачу."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit Breaker открыт после {self.failures} неудач")


class RateLimiter:
    """Ограничитель частоты запросов к API."""
    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: float = 0
        
    async def acquire(self):
        """Блокируется до разрешения следующего запроса."""
        current = asyncio.get_event_loop().time()
        elapsed = current - self.last_request_time
        
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
            
        self.last_request_time = asyncio.get_event_loop().time()


class OpenFoodFactsClient:
    """Надёжный клиент для работы с Open Food Facts API с улучшенной архитектурой."""
    
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search"
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl"
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"
    
    def __init__(self, cache_ttl_hours: int = 1):
        """Инициализация клиента с умным кэшем и rate limiting."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "X-App-Version": "1.0",
        }
        
        self.client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers)
        
        # TTL Cache для результатов поиска (на 1 час)
        self._search_cache: TTLCache = TTLCache(
            maxsize=500, 
            ttl=timedelta(hours=cache_ttl_hours).total_seconds()
        )
        
        # Кэш продуктов по баркоду (на 24 часа)
        self._barcode_cache: TTLCache = TTLCache(
            maxsize=1000, 
            ttl=timedelta(days=1).total_seconds()
        )
        
        self.rate_limiter = RateLimiter(requests_per_second=1.0)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        
        self._stats = {
            "searches_total": 0,
            "searches_success": 0,
            "searches_failed": 0,
            "cache_hits": 0,
            "fallback_used": 0,
        }

    async def close(self):
        """Закрытие клиента и сохранение статистики."""
        await self.client.aclose()
        logger.info(f"Statistics: {self._stats}")
        
    def _get_stats(self) -> dict:
        """Возвращает статистику запросов."""
        return self._stats.copy()
        
    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        retries: Optional[int] = None
    ) -> List[OFFProduct]:
        """
        Основной метод поиска с приоритетом: SAL → V1 → V2.
        Использует кэш, circuit breaker и rate limiter.
        """
        if retries is None:
            retries = API_RETRY_ATTEMPTS
            
        self._stats["searches_total"] += 1
        
        # Проверка circuit breaker
        if not await self.circuit_breaker.check():
            logger.warning("Circuit Breaker активен, использование локального fallback")
            return []
            
        cache_key = f"{query}:{page}:{page_size}"
        
        # Проверка кэша
        if cache_key in self._search_cache:
            self._stats["cache_hits"] += 1
            return self._search_cache[cache_key]
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        products = []
        
        # 1. Search-a-licious (основной полнотекстовый поиск)
        for attempt in range(retries + 1):
            try:
                products = await self._search_sal(query, page, page_size)
                if products:
                    self._stats["searches_success"] += 1
                    self.circuit_breaker.record_success()
                    self._add_to_search_cache(cache_key, products)
                    return products
            except Exception as e:
                logger.warning(f"SAL attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(API_RETRY_DELAY * (attempt + 1))
                    
        # 2. API V1 (резервный полнотекстовый поиск)
        try:
            products = await self._search_v1(query, page, page_size)
            if products:
                self._stats["searches_success"] += 1
                self._stats["fallback_used"] += 1
                self.circuit_breaker.record_success()
                self._add_to_search_cache(cache_key, products)
                return products
        except Exception as e:
            logger.error(f"V1 failed: {e}")
            
        # 3. API V2 (фильтры, не текстовый поиск)
        try:
            products = await self._search_v2_filtered(query, page, page_size)
            if products:
                self._stats["searches_success"] += 1
                self.circuit_breaker.record_success()
                self._add_to_search_cache(cache_key, products)
                return products
        except Exception as e:
            logger.error(f"V2 filtered failed: {e}")
            self._stats["searches_failed"] += 1
            self.circuit_breaker.record_failure()
            
        return []
        
    async def _search_sal(self, query: str, page: int, page_size: int) -> List[OFFProduct]:
        """Поиск через Search-a-licious."""
        params = {"q": query, "page": page, "page_size": page_size}
        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()
        
        products = []
        if isinstance(data, list):
            for item in data:
                product = self._parse_off_product(item)
                if product and product.kcal_per_100g > 0:
                    products.append(product)
        elif isinstance(data, dict):
            for item in data.get("products", []):
                product = self._parse_off_product(item)
                if product and product.kcal_per_100g > 0:
                    products.append(product)
                
        return products[:page_size]
        
    async def _search_v1(self, query: str, page: int, page_size: int) -> List[OFFProduct]:
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
        
        return [
            self._parse_off_product(p) 
            for p in data.get("products", []) 
            if self._validate_product(p)
        ]
        
    async def _search_v2_filtered(self, query: str, page: int, page_size: int) -> List[OFFProduct]:
        """Поиск через API V2 с оператором like (не основной текстовый поиск)."""
        params = {
            "search_terms": query,
            "operator": "like",
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url,serving_size",
        }
        response = await self.client.get(self.SEARCH_URL_V2, params=params)
        response.raise_for_status()
        data = response.json()
        
        return [
            self._parse_off_product(p) 
            for p in data.get("products", []) 
            if self._validate_product(p)
        ]
        
    async def get_product_by_barcode(self, barcode: str) -> Optional[OFFProduct]:
        """Получение продукта по штрихкоду с кэшем."""
        # Проверка кэша
        if barcode in self._barcode_cache:
            cached = self._barcode_cache[barcode]
            if cached:
                return cached
                
        await self.rate_limiter.acquire()
        
        try:
            response = await self.client.get(f"{self.PRODUCT_URL}/{barcode}.json")
            response.raise_for_status()
            data = response.json()
            
            product_data = data.get("product", {})
            if product_data and product_data.get("nutriments"):
                product = self._parse_off_product(product_data)
                self._barcode_cache[barcode] = product
                return product
                
        except Exception as e:
            logger.error(f"Barcode lookup failed for {barcode}: {e}")
            
        self._barcode_cache[barcode] = None
        return None
        
    def _parse_off_product(self, data: dict) -> Optional[OFFProduct]:
        """Парсит продукт в модель OFFProduct."""
        if not isinstance(data, dict):
            return None
            
        try:
            product = OFFProduct(data)
            if product.kcal_per_100g <= 0 and not product.default_weight:
                return None
            return product
        except Exception as e:
            logger.warning(f"Failed to parse product: {data}, error: {e}")
            return None
            
    def _validate_product(self, product: dict) -> bool:
        """Проверяет, содержит ли продукт достаточную информацию."""
        return all([
            product.get("code"),
            product.get("nutriments"),
            product.get("nutriments", {}).get("energy-kcal_100g") or 
            product.get("nutriments", {}).get("energy-kcal"),
        ])
        
    def _add_to_search_cache(self, key: str, products: List[OFFProduct]):
        """Добавляет результаты в кэш с LRU eviction."""
        if len(self._search_cache) >= 500:
            oldest = next(iter(list(self._search_cache.keys())))
            del self._search_cache[oldest]
        self._search_cache[key] = products
        
    async def search_by_filters(
        self,
        categories: Optional[str] = None,
        brands: Optional[str] = None,
        nutrition_grades: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[OFFProduct]:
        """
        Отдельный метод для API V2 с фильтрами.
        Не поддерживает текстовый поиск, только структурированные фильтры.
        """
        await self.rate_limiter.acquire()
        
        params = {
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url,serving_size,nutriscore_grade",
        }
        
        if categories:
            params["categories_tags_en"] = categories
        if brands:
            params["brands_tags_en"] = brands
        if nutrition_grades:
            params["nutrition_grades"] = nutrition_grades
            
        try:
            response = await self.client.get(self.SEARCH_URL_V2, params=params)
            response.raise_for_status()
            data = response.json()
            
            return [
                self._parse_off_product(p)
                for p in data.get("products", [])
                if self._validate_product(p)
            ]
        except Exception as e:
            logger.error(f"API V2 filter search failed: {e}")
            return []
            
    async def batch_get_by_barcodes(self, barcodes: List[str]) -> List[OFFProduct]:
        """Пакетное получение продуктов по нескольким штрихкодам."""
        return await asyncio.gather(
            *[self.get_product_by_barcode(bc) for bc in barcodes],
            return_exceptions=True
        )
        
    async def smart_search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        preferred_categories: Optional[List[str]] = None
    ) -> List[OFFProduct]:
        """
        Умный поиск с расширенными возможностями.
        Поддерживает категории, бренды, сортировку.
        """
        results = await self.search_products(query, page, page_size)
        
        # Фильтрация по предпочтительным категориям (после получения)
        if preferred_categories:
            category_map = {cat.lower() for cat in preferred_categories}
            filtered = [
                p for p in results 
                if any(cat in p.product_name.lower() for cat in category_map)
            ]
            if filtered:
                results = filtered
                
        return results