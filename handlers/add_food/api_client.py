# handlers/add_food/api_client.py
import httpx
from typing import Optional, List, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


class OpenFoodFactsClient:
    """Клиент для работы с Open Food Facts API."""

    BASE_URL = "https://world.openfoodfacts.org"
    SEARCH_URL = f"{BASE_URL}/cgi/search.pl"
    PRODUCT_URL = f"{BASE_URL}/api/v2/product"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск продуктов по текстовому запросу.
        Возвращает список продуктов с КБЖУ.
        """
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
            "fields": (
                "product_name,brands,quantity,"
                "nutriments,code,image_url"
            ),
        }

        try:
            response = await self.client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            products = []
            for product in data.get("products", []):
                parsed = self._parse_product(product)
                if parsed and parsed.get("kcal_100g"):  # Только с калориями
                    products.append(parsed)

            return products

        except Exception as e:
            logger.error(f"Ошибка поиска продуктов: {e}")
            return []

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Получение продукта по штрихкоду.
        """
        try:
            response = await self.client.get(f"{self.PRODUCT_URL}/{barcode}")
            response.raise_for_status()
            data = response.json()

            product = data.get("product", {})
            if product:
                return self._parse_product(product)

            return None

        except Exception as e:
            logger.error(f"Ошибка получения продукта по штрихкоду {barcode}: {e}")
            return None

    def _parse_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсит продукт из ответа API в унифицированный формат.
        """
        nutriments = product.get("nutriments", {})

        # Получаем калории (на 100г)
        kcal_100g = nutriments.get("energy-kcal_100g")
        if not kcal_100g:
            kcal_100g = nutriments.get("energy-kcal")

        # Если нет калорий, пробуем получить из других полей
        if not kcal_100g:
            return None

        # Получаем макросы (на 100г)
        protein_100g = nutriments.get("proteins_100g", 0)
        fat_100g = nutriments.get("fat_100g", 0)
        carbs_100g = nutriments.get("carbohydrates_100g", 0)

        # Определяем вес порции
        quantity = product.get("quantity")
        default_weight = self._parse_default_weight(quantity)

        return {
            "code": product.get("code", ""),  # Пустая строка если нет штрихкода
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
        """
        Пытается извлечь вес из строки quantity.
        Например: "500 g", "1 kg", "330 ml" -> 500, 1000, 330
        """
        if not quantity:
            return 100.0  # По умолчанию 100г

        # Ищем число и единицу измерения
        match = re.search(r"(\d+(?:\.\d+)?)\s*(g|kg|ml|l)", quantity.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)

            if unit == "kg":
                value *= 1000
            elif unit == "l":
                value *= 1000
            elif unit == "ml":
                value = value  # мл примерно равны граммам для жидкостей

            return value

        return 100.0

    def calculate_for_weight(
        self,
        product: Dict[str, Any],
        weight: float
    ) -> Dict[str, Any]:
        """
        Рассчитывает КБЖУ для указанного веса.
        Безопасно обрабатывает отсутствие поля 'code'.
        """
        multiplier = weight / 100.0

        return {
            "code": product.get("code", ""),  # Безопасно получаем code
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "weight": weight,
            "kcal": round(product.get("kcal_100g", 0) * multiplier),
            "protein": round(product.get("protein_100g", 0) * multiplier, 1),
            "fat": round(product.get("fat_100g", 0) * multiplier, 1),
            "carbs": round(product.get("carbs_100g", 0) * multiplier, 1),
            "image_url": product.get("image_url"),
        }