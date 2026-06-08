"""
Клиент для работы с Open Food Facts API.
🎯 Обновлено: page_size увеличен до 50 для лучшей пагинации.
"""
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
    
    Приоритет поиска:
    1. Российские товары на русском языке
    2. Глобальная база (если в России не найдено)
    
    Реальность 2026 года:
    - Search-a-licious (SAL) — единственный стабильный полнотекстовый поиск
    - V1 и V2 для поиска часто возвращают 503 (серверы перегружены/блокируют)
    - V2 для получения по баркоду работает стабильно
    """

    SEARCH_URL_SAL = "https://search.openfoodfacts.org/search"
    PRODUCT_URL_V2 = "https://world.openfoodfacts.org/api/v2/product"

    def __init__(self):
        # ОБЯЗАТЕЛЬНО: OFF блокирует запросы без правильного User-Agent
        headers = {
            "User-Agent": "NutriMateBot/1.0 (+https://t.me/nutrimatebot)",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=10.0, headers=headers)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._barcode_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self._cache_max_size = 200
        self._last_request_time: float = 0
        self._min_interval = 0.3  # 0.3 сек между запросами (безопасно)

    async def close(self):
        await self.client.aclose()

    async def _rate_limit(self):
        """Мягкий rate limiting для защиты от банов."""
        now = datetime.now().timestamp()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_time = datetime.now().timestamp()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,  # 🎯 Увеличено с 5 до 50 для лучшей пагинации
    ) -> List[Dict[str, Any]]:
        """
        Полнотекстовый поиск через Search-a-licious (SAL).
        
        Приоритет:
        1. Российские товары на русском
        2. Глобальная база (если в России не найдено)
        
        🎯 Теперь запрашивает 50 продуктов за раз для полноценной пагинации.
        """
        cache_key = f"{query}:{page}:{page_size}"

        if cache_key in self._cache:
            logger.debug(f"Cache hit: {query}")
            return self._cache[cache_key]

        try:
            await self._rate_limit()
            
            # ЭТАП 1: Ищем только в России
            products = await self._search_sal_russia(query, page, page_size)
            if products:
                logger.info(f"🇷🇺 Found {len(products)} Russian products for '{query}'")
                self._add_to_cache(cache_key, products)
                return products
            
            # ЭТАП 2: Если в России ничего нет — ищем глобально
            logger.info(f"🇷🇺 No Russian products for '{query}', searching globally...")
            await self._rate_limit()
            products = await self._search_sal_global(query, page, page_size)
            if products:
                logger.info(f"🌍 Found {len(products)} global products for '{query}'")
                self._add_to_cache(cache_key, products)
                return products
            
            logger.warning(f"❌ No products found for '{query}'")
        except httpx.HTTPStatusError as e:
            logger.error(f"SAL HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"SAL request failed: {e}")

        return []

    async def _search_sal_russia(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Поиск ТОЛЬКО по российским товарам.
        Использует фильтры SAL:
        - countries_tags_contains=russia (товары из России)
        - langs_contains=russian (с русскими названиями)
        """
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,  # 🎯 Использует переданный page_size (50)
            "countries_tags_contains": "russia",  # Только Россия
            "langs_contains": "russian",  # Только русский язык
        }

        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()

        return self._parse_sal_response(data, page_size)

    async def _search_sal_global(self, query: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        Глобальный поиск (fallback, если в России ничего не найдено).
        """
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,  # 🎯 Использует переданный page_size (50)
        }

        response = await self.client.get(self.SEARCH_URL_SAL, params=params)
        response.raise_for_status()
        data = response.json()

        return self._parse_sal_response(data, page_size)

    def _parse_sal_response(self, data: Dict[str, Any], page_size: int) -> List[Dict[str, Any]]:
        """Парсит ответ от SAL (общий метод для России и глобального поиска)."""
        products = []
        
        # SAL всегда возвращает dict с ключом 'hits' (массив прямых продуктов)
        hits = data.get("hits", [])
        
        if not isinstance(hits, list):
            logger.warning(f"SAL returned unexpected hits type: {type(hits)}")
            return []

        for item in hits:
            parsed = self._parse_sal_product(item)
            if parsed and parsed.get("kcal_100g") and parsed.get("kcal_100g") > 0:
                products.append(parsed)

        return products[:page_size]

    def _parse_sal_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсит продукт из SAL ответа."""
        if not isinstance(product, dict):
            return None

        nutriments = product.get("nutriments", {})
        if not isinstance(nutriments, dict):
            return None

        # В SAL ключ kcal может быть "energy-kcal_100g"
        kcal_100g = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
        if not kcal_100g:
            return None

        try:
            kcal_val = float(kcal_100g)
        except (ValueError, TypeError):
            return None

        protein_100g = nutriments.get("proteins_100g", 0) or 0
        fat_100g = nutriments.get("fat_100g", 0) or 0
        carbs_100g = nutriments.get("carbohydrates_100g", 0) or 0

        # Приоритет: русское название → основное → английское
        name = (product.get("product_name_ru") or 
                product.get("product_name") or 
                product.get("product_name_en") or
                "Неизвестный продукт")

        # brands в SAL может быть списком или строкой
        brands = product.get("brands", "")
        if isinstance(brands, list):
            brands = ", ".join(brands) if brands else ""
        elif not isinstance(brands, str):
            brands = ""

        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)
        
        # 🎯 Определяем, является ли продукт жидкостью
        is_liquid = self._is_liquid_product(product)

        return {
            "code": product.get("code", ""),
            "name": name,
            "brand": brands,
            "quantity": quantity,
            "default_weight": default_weight,
            "kcal_100g": kcal_val,
            "protein_100g": float(protein_100g) if protein_100g else 0.0,
            "fat_100g": float(fat_100g) if fat_100g else 0.0,
            "carbs_100g": float(carbs_100g) if carbs_100g else 0.0,
            "image_url": product.get("image_url") or product.get("image_front_url"),
            "is_russian": True,  # Помечаем как российский товар
            "is_liquid": is_liquid,
        }

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Получение продукта по штрихкоду через API V2.
        Работает стабильно (проверено тестами).
        """
        if barcode in self._barcode_cache:
            return self._barcode_cache[barcode]

        try:
            await self._rate_limit()
            response = await self.client.get(f"{self.PRODUCT_URL_V2}/{barcode}.json")
            response.raise_for_status()
            data = response.json()

            product_data = data.get("product")
            if not product_data:
                self._barcode_cache[barcode] = None
                return None

            parsed = self._parse_v2_product(product_data)
            self._barcode_cache[barcode] = parsed
            return parsed
        except Exception as e:
            logger.error(f"Barcode lookup failed for {barcode}: {e}")
            self._barcode_cache[barcode] = None
            return None

    def _parse_v2_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсит продукт из V2 ответа (barcode lookup)."""
        if not isinstance(product, dict):
            return None

        nutriments = product.get("nutriments", {})
        if not isinstance(nutriments, dict):
            return None

        kcal_100g = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
        if not kcal_100g:
            return None

        try:
            kcal_val = float(kcal_100g)
        except (ValueError, TypeError):
            return None

        protein_100g = nutriments.get("proteins_100g", 0) or 0
        fat_100g = nutriments.get("fat_100g", 0) or 0
        carbs_100g = nutriments.get("carbohydrates_100g", 0) or 0

        # 🎯 ИСПРАВЛЕН БАГ: берём русское название с приоритетом
        name = (product.get("product_name_ru") or 
                product.get("product_name") or 
                product.get("product_name_en") or
                "Неизвестный продукт")

        # 🎯 ИСПРАВЛЕН БАГ: правильная обработка brands (может быть строка с запятыми без пробелов)
        brands = product.get("brands", "")
        if isinstance(brands, list):
            brands = ", ".join(brands)
        elif isinstance(brands, str):
            # Заменяем "Щедрый Год,Чижик" на "Щедрый Год, Чижик"
            brands = brands.replace(",", ", ")
        else:
            brands = ""

        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)

        # Проверяем, из России ли товар
        countries_tags = product.get("countries_tags", [])
        is_russian = "russia" in countries_tags or "ru" in countries_tags
        
        if not is_russian:
            logger.warning(f"⚠️ Product {name} is NOT from Russia (countries: {countries_tags})")
        
        # 🎯 Определяем, является ли продукт жидкостью
        is_liquid = self._is_liquid_product(product)

        return {
            "code": product.get("code", ""),
            "name": name,
            "brand": brands,
            "quantity": quantity,
            "default_weight": default_weight,
            "kcal_100g": kcal_val,
            "protein_100g": float(protein_100g) if protein_100g else 0.0,
            "fat_100g": float(fat_100g) if fat_100g else 0.0,
            "carbs_100g": float(carbs_100g) if carbs_100g else 0.0,
            "image_url": product.get("image_url") or product.get("image_front_url"),
            "is_russian": is_russian,
            "is_liquid": is_liquid,
        }

    def _is_liquid_product(self, product: Dict[str, Any]) -> bool:
        """
        🎯 Определяет, является ли продукт жидкостью для трекинга воды.
        Проверяет категории продукта.
        """
        categories_tags = product.get("categories_tags", [])
        categories_tags_en = product.get("categories_tags_en", [])
        
        # Теги жидкостей
        liquid_tags = {
            "en:beverages", "beverages",
            "en:water", "water",
            "en:teas", "teas",
            "en:coffees", "coffees",
            "en:fruit-juices", "fruit-juices",
            "en:soups", "soups",
            "en:milk", "milk",
            "en:soft-drinks", "soft-drinks",
            "en:energy-drinks", "energy-drinks",
            "en:alcoholic-beverages", "alcoholic-beverages",
        }
        
        # Проверяем оба списка тегов
        for tag in categories_tags + categories_tags_en:
            if tag.lower() in liquid_tags:
                return True
        
        return False

    def _parse_default_weight(self, quantity: Optional[Any]) -> float:
        """Извлекает вес из строки формата '500 g', '400гр.', '1 kg'."""
        if not quantity:
            return 100.0

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(g|гр|грамм|kg|кг|ml|мл|l|л)",
            str(quantity).lower()
        )
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit in ("kg", "кг"):
                return value * 1000
            if unit in ("l", "л"):
                return value * 1000
            if unit in ("ml", "мл"):
                return value  # считаем 1мл = 1г для простоты
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
            "is_liquid": product.get("is_liquid", False),
        }

    def _add_to_cache(self, key: str, products: List[Dict[str, Any]]):
        """LRU-кэш для результатов поиска."""
        if key in self._cache:
            return
        if len(self._cache) >= self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = products