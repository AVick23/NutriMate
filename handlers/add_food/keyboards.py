# handlers/add_food/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any
from handlers.add_food.constants import MEAL_TYPES


def get_select_method_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора способа добавления еды."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Сфотографировать тарелку", callback_data="food_method_photo")],
        [InlineKeyboardButton("📷 Сканировать штрихкод", callback_data="food_method_barcode")],
        [InlineKeyboardButton("✍️ Написать текстом", callback_data="food_method_text")],
        [InlineKeyboardButton("⭐️ Выбрать из избранного", callback_data="food_method_favorites")],
        [InlineKeyboardButton("🔙 ← Назад в дневник", callback_data="food_back_to_diary")],
    ])


def get_back_keyboard(callback_data: str = "food_back") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← Назад", callback_data=callback_data)]
    ])


def get_barcode_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Назад для режима сканирования штрихкода."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← Назад в меню", callback_data="food_back_to_method")]
    ])


def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа приёма пищи."""
    buttons = []
    for meal_type, label in MEAL_TYPES.items():
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"food_meal_{meal_type}")
        ])
    buttons.append([InlineKeyboardButton("🔙 ← Назад", callback_data="food_back_to_method")])
    return InlineKeyboardMarkup(buttons)


def get_product_selection_keyboard(
    products: List[Dict[str, Any]],
    page: int = 0,
    total_pages: int = 1
) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора продукта из результатов поиска.
    Показывает до 5 продуктов.
    """
    buttons = []

    for i, product in enumerate(products[:5]):
        name = product["name"][:30]
        if product.get("brand"):
            name = f"{product['brand']} - {name}"

        kcal = product.get("kcal_100g", 0)

        button_text = f"{i + 1}️⃣ {name} (~{kcal} ккал/100г)"
        buttons.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"food_product_{i}"
            )
        ])

    # Навигация по страницам (если нужно)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"food_page_{page - 1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"food_page_{page + 1}")
        )
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 ← Новый поиск", callback_data="food_new_search")])
    buttons.append([InlineKeyboardButton("🔙 ← Назад в меню", callback_data="food_back_to_method")])

    return InlineKeyboardMarkup(buttons)


def get_weight_input_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода веса."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("50 г", callback_data="food_weight_50"),
            InlineKeyboardButton("100 г", callback_data="food_weight_100"),
            InlineKeyboardButton("150 г", callback_data="food_weight_150"),
        ],
        [
            InlineKeyboardButton("200 г", callback_data="food_weight_200"),
            InlineKeyboardButton("250 г", callback_data="food_weight_250"),
            InlineKeyboardButton("300 г", callback_data="food_weight_300"),
        ],
        [InlineKeyboardButton("✏️ Ввести свой вес", callback_data="food_weight_custom")],
        [InlineKeyboardButton("🔙 ← Назад к выбору продукта", callback_data="food_back_to_products")],
    ])


def get_confirm_keyboard(product_name: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="food_confirm_add")],
        [InlineKeyboardButton("✏️ Изменить вес", callback_data="food_change_weight")],
        [InlineKeyboardButton("🔙 ← Назад к выбору веса", callback_data="food_back_to_weight")],
    ])


def get_after_add_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📔 Вернуться в дневник", callback_data="food_back_to_diary")],
        [InlineKeyboardButton("🍽️ Добавить ещё блюдо", callback_data="food_add_another")],
    ])


def get_save_favorite_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура сохранения в избранное."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐️ Да, сохранить", callback_data="food_save_favorite_yes"),
            InlineKeyboardButton("👌 Нет, спасибо", callback_data="food_save_favorite_no"),
        ]
    ])


def get_favorites_keyboard(favorites: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура со списком избранных продуктов."""
    buttons = []

    for i, fav in enumerate(favorites[:10]):
        name = fav["food_name"][:35]
        kcal = fav["kcal"]
        weight = fav["amount_g"]

        buttons.append([
            InlineKeyboardButton(
                f"{name} ({weight}г, {kcal} ккал)",
                callback_data=f"food_fav_{i}"
            )
        ])

    if not buttons:
        buttons.append([
            InlineKeyboardButton("😕 Пока ничего нет", callback_data="food_noop")
        ])

    buttons.append([InlineKeyboardButton("🔙 ← Назад", callback_data="food_back_to_method")])

    return InlineKeyboardMarkup(buttons)


def get_custom_weight_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ручного ввода веса."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← Назад к выбору веса", callback_data="food_back_to_weight")],
    ])