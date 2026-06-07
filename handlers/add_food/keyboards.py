"""
Клавиатуры для добавления еды.
Обновлено для Универсального ввода (Apple-like UX).
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any
from .constants import (
    MEAL_TYPES, PAGE_SIZE,
    CALLBACK_METHOD_UNIVERSAL, CALLBACK_METHOD_FAVORITES, CALLBACK_METHOD_POPULAR,
    CALLBACK_BACK_TO_DIARY, CALLBACK_BACK_TO_RESULTS, CALLBACK_BACK_TO_WEIGHT,
    CALLBACK_SEARCH_AGAIN, CALLBACK_SELECT_PRODUCT, CALLBACK_PAGE_PREV,
    CALLBACK_PAGE_NEXT, CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX, CALLBACK_CONFIRM_ADD, CALLBACK_CHANGE_WEIGHT,
    CALLBACK_ADD_ANOTHER, CALLBACK_SAVE_FAVORITE_YES, CALLBACK_SAVE_FAVORITE_NO,
    CALLBACK_NOOP, CALLBACK_MANUAL_SKIP, CALLBACK_MANUAL_CONFIRM, CALLBACK_MANUAL_EDIT,
)

def get_select_method_keyboard() -> InlineKeyboardMarkup:
    """🎯 Главное меню: всего 3 кнопки действий + выход."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить еду", callback_data=CALLBACK_METHOD_UNIVERSAL)],
        [InlineKeyboardButton("🔥 Популярные блюда", callback_data=CALLBACK_METHOD_POPULAR)],
        [InlineKeyboardButton("⭐️ Избранное", callback_data=CALLBACK_METHOD_FAVORITES)],
        [InlineKeyboardButton("📔 ← В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])

def get_universal_input_keyboard() -> InlineKeyboardMarkup:
    """Минималистичная клавиатура во время ожидания ввода."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])

def get_product_selection_keyboard(
    products: List[Dict[str, Any]],
    page: int = 0,
    query: str = "",
) -> InlineKeyboardMarkup:
    """Клавиатура выбора продукта с пагинацией."""
    total_pages = max(1, (len(products) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_products = products[start_idx:end_idx]

    buttons = []
    for i, product in enumerate(page_products):
        real_index = start_idx + i
        name = product.get("name", "Без названия")[:32]
        brand = product.get("brand", "")
        kcal = product.get("kcal_100g", 0)

        if brand and str(brand).strip():
            button_text = f"{i + 1}. {name} · {str(brand)[:12]} · {kcal:.0f}ккал"
        else:
            button_text = f"{i + 1}. {name} · {kcal:.0f}ккал/100г"

        buttons.append([
            InlineKeyboardButton(button_text, callback_data=f"{CALLBACK_SELECT_PRODUCT}{real_index}")
        ])

    if total_pages > 1:
        nav_row = []
        nav_row.append(InlineKeyboardButton("◀️", callback_data=CALLBACK_PAGE_PREV) if page > 0 else InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))
        nav_row.append(InlineKeyboardButton(f"· {page + 1} / {total_pages} ·", callback_data=CALLBACK_NOOP))
        nav_row.append(InlineKeyboardButton("▶️", callback_data=CALLBACK_PAGE_NEXT) if page < total_pages - 1 else InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN)])
    buttons.append([InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)])

    return InlineKeyboardMarkup(buttons)

def get_weight_input_keyboard(product_name: str = "") -> InlineKeyboardMarkup:
    """Клавиатура выбора веса."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("50г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}50"),
            InlineKeyboardButton("100г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}100"),
            InlineKeyboardButton("150г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}150"),
        ],
        [
            InlineKeyboardButton("200г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}200"),
            InlineKeyboardButton("250г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}250"),
            InlineKeyboardButton("300г", callback_data=f"{CALLBACK_WEIGHT_PREFIX}300"),
        ],
        [InlineKeyboardButton("✏️ Свой вес", callback_data=CALLBACK_WEIGHT_CUSTOM)],
        [
            InlineKeyboardButton("← К результатам", callback_data=CALLBACK_BACK_TO_RESULTS),
            InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
        ],
    ])

def get_custom_weight_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← К вариантам веса", callback_data=CALLBACK_BACK_TO_WEIGHT)],
        [InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN)],
    ])

def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(label, callback_data=f"{CALLBACK_MEAL_PREFIX}{meal_type}")] for meal_type, label in MEAL_TYPES.items()]
    buttons.append([
        InlineKeyboardButton("✏️ ← Изменить вес", callback_data=CALLBACK_BACK_TO_WEIGHT),
        InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
    ])
    return InlineKeyboardMarkup(buttons)

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data=CALLBACK_CONFIRM_ADD)],
        [
            InlineKeyboardButton("✏️ Изменить вес", callback_data=CALLBACK_CHANGE_WEIGHT),
            InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
        ],
        [InlineKeyboardButton("📔 Отмена (в дневник)", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])

def get_save_favorite_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Да, сохранить", callback_data=CALLBACK_SAVE_FAVORITE_YES),
            InlineKeyboardButton("👌 Нет", callback_data=CALLBACK_SAVE_FAVORITE_NO),
        ],
    ])

def get_after_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽️ Добавить ещё", callback_data=CALLBACK_ADD_ANOTHER)],
        [InlineKeyboardButton("🔍 Поискать другое", callback_data=CALLBACK_SEARCH_AGAIN)],
        [InlineKeyboardButton("📔 Вернуться в дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])

def get_manual_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить", callback_data=CALLBACK_MANUAL_SKIP)],
        [InlineKeyboardButton("🔙 ← Назад", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])

def get_manual_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Всё верно", callback_data=CALLBACK_MANUAL_CONFIRM)],
        [InlineKeyboardButton("✏️ Изменить", callback_data=CALLBACK_MANUAL_EDIT)],
        [InlineKeyboardButton("📔 Отмена", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])