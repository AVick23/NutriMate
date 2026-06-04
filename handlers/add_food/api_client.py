# handlers/add_food/api_client.py
"""
Клиент для работы с Open Food Facts API.
Основан на исследовании официальной документации и реальных тестах.

Правильное использование:
- search_products() — для текстового поиска (Search-a-licious → API V1)
- search_by_filters() — для фильтрации по категориям/брендам (API V2)
- get_product_by_barcode() — для штрихкодов
"""

import asyncio
import httpx
import logging
import re
import time
import random
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """Клиент с правильным использованием всех трёх API Open Food Facts."""

    # API эндпоинты
    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"      # Search-a-licious (основной поиск)
    SEARCH_URL_V2 = "https://world.openfoodfacts.org/api/v2/search" # API V2 (только фильтры)
    SEARCH_URL_V1 = "https://world.openfoodfacts.org/cgi/search.pl" # API V1 (резервный)
    PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"  # Штрихкоды

    def __init__(self):
        # ✅ КРИТИЧЕСКИ ВАЖНО: User-Agent обязателен, иначе блокировка
        headers = {
            "User-Agent": "NutriMateBot - Python - Version 2.0 - https://t.me/NutriMateBot",
            "Accept": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=15.0, headers=headers)
        
        # Кэш с TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._cache_max_size = 100
        self._cache_ttl_seconds = 300  # 5 минут

    async def close(self):
        await self.client.aclose()

    # ========== ТЕКСТОВЫЙ ПОИСК (Search-a-licious → API V1) ==========

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Основной метод для текстового поиска.
        Приоритет: Search-a-licious → API V1.
        API V2 НЕ ИСПОЛЬЗУЕТСЯ, так как он не поддерживает текстовый поиск.
        """
        cache_key = f"search:{query}:{page}:{page_size}"
        
        # Проверка кэша
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for: {query}")
                return self._cache[cache_key].get("products", [])
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        # 1. Search-a-licious (основной, современный полнотекстовый поиск)
        products = await self._search_with_retry(
            self._search_sal, query, page, page_size, "Search-a-licious"
        )
        if products:
            self._add_to_cache(cache_key, products)
            return products

        # 2. API V1 (резервный, устаревший но стабильный)
        products = await self._search_with_retry(
            self._search_v1, query, page, page_size, "API V1"
        )
        if products:
            self._add_to_cache(cache_key, products)
            return products

        return []

    async def _search_sal(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск через Search-a-licious.
        ✅ Возвращает стандартную структуру {"products": [...]}
        """
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
        }
        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Search-a-licious возвращает стандартный JSON с ключом "products"
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
        }
        response = await self.client.get(self.SEARCH_URL_V1, params=params)
        response.raise_for_status()
        data = response.json()
        return self._parse_products(data)

    # ========== СТРУКТУРИРОВАННЫЙ ПОИСК (API V2 для фильтров) ==========

    async def search_by_filters(
        self,
        categories: Optional[str] = None,
        brands: Optional[str] = None,
        nutrition_grades: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Поиск через API V2 по фильтрам (НЕ для текстового поиска!).
        
        Примеры:
        - categories="en:chocolates" — все шоколадки
        - brands="nestle" — все продукты Nestle
        - nutrition_grades="a" — только продукты с классом A
        """
        params = {
            "page": page,
            "page_size": page_size,
            "fields": "product_name,brands,quantity,nutriments,code,image_url",
        }
        if categories:
            params["categories_tags_en"] = categories
        if brands:
            params["brands_tags_en"] = brands
        if nutrition_grades:
            params["nutrition_grades"] = nutrition_grades

        cache_key = f"filters:{categories}:{brands}:{page}:{page_size}"
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < self._cache_ttl_seconds:
                return self._cache[cache_key].get("products", [])
            else:
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        try:
            response = await self.client.get(self.SEARCH_URL_V2, params=params)
            response.raise_for_status()
            data = response.json()
            products = self._parse_products(data)
            self._add_to_cache(cache_key, products)
            return products
        except Exception as e:
            logger.error(f"API V2 filter search failed: {e}")
            return []

    # ========== ПОИСК ПО ШТРИХКОДУ ==========

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Получение продукта по штрихкоду (стабильный эндпоинт).
        """
        cache_key = f"barcode:{barcode}"
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

    def _parse_products(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Универсальный парсер для всех API (SAL, V1, V2).
        Все они возвращают одинаковую структуру с ключом "products".
        """
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

    # ========== RETRY-МЕХАНИЗМ ==========

    async def _search_with_retry(
        self,
        search_func,
        query: str,
        page: int,
        page_size: int,
        api_name: str,
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """Универсальный метод с экспоненциальной задержкой."""
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
                status = e.response.status_code
                if self._is_retryable(status):
                    if attempt < max_retries - 1:
                        delay = self._calc_backoff(attempt)
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
        """Проверяет, стоит ли повторять запрос."""
        return status >= 500 or status == 429

    def _calc_backoff(self, attempt: int) -> float:
        """Экспоненциальная задержка с джиттером."""
        base = 2 ** attempt
        jitter = random.uniform(0.7, 1.3)
        return base * jitter

    def _add_to_cache(self, key: str, data: Any):
        """Добавляет результат в кэш."""
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            del self._cache_ttl[oldest]
        self._cache[key] = data if isinstance(data, dict) else {"products": data}
        self._cache_ttl[key] = time.time()