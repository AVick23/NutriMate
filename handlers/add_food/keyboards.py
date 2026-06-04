"""
Клавиатуры для добавления еды с пагинацией и умной навигацией.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any
from .constants import (
    MEAL_TYPES, PAGE_SIZE,
    CALLBACK_METHOD_TEXT, CALLBACK_METHOD_BARCODE, CALLBACK_METHOD_FAVORITES,
    CALLBACK_METHOD_POPULAR, CALLBACK_METHOD_VOICE,
    CALLBACK_BACK_TO_DIARY, CALLBACK_BACK_TO_METHOD, CALLBACK_BACK_TO_TEXT,
    CALLBACK_BACK_TO_RESULTS, CALLBACK_BACK_TO_WEIGHT,
    CALLBACK_SEARCH_AGAIN, CALLBACK_SELECT_PRODUCT,
    CALLBACK_PAGE_PREV, CALLBACK_PAGE_NEXT,
    CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX, CALLBACK_CONFIRM_ADD, CALLBACK_CHANGE_WEIGHT,
    CALLBACK_ADD_ANOTHER, CALLBACK_SAVE_FAVORITE_YES, CALLBACK_SAVE_FAVORITE_NO,
    CALLBACK_FAVORITE_PREFIX, CALLBACK_FAV_PAGE_PREV, CALLBACK_FAV_PAGE_NEXT,
    CALLBACK_NOOP,
)


def get_select_method_keyboard() -> InlineKeyboardMarkup:
    """Главное меню выбора способа добавления еды."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎤 Голосом (просто скажи)", callback_data=CALLBACK_METHOD_VOICE)],
        [InlineKeyboardButton("✍️ Написать текстом", callback_data=CALLBACK_METHOD_TEXT)],
        [InlineKeyboardButton("📷 Сканировать штрихкод", callback_data=CALLBACK_METHOD_BARCODE)],
        [InlineKeyboardButton("⭐️ Избранное", callback_data=CALLBACK_METHOD_FAVORITES)],
        [InlineKeyboardButton("🔥 Популярные блюда", callback_data=CALLBACK_METHOD_POPULAR)],
        [InlineKeyboardButton("📔 ← В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_text_input_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для экрана текстового ввода."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← К выбору способа", callback_data=CALLBACK_BACK_TO_METHOD)],
        [InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_product_selection_keyboard(
    products: List[Dict[str, Any]],
    page: int = 0,
    query: str = "",
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора продукта с пагинацией.
    Показывает PAGE_SIZE продуктов на странице с навигацией ◀️ 1/N ▶️
    """
    total_pages = max(1, (len(products) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_products = products[start_idx:end_idx]

    buttons = []

    # Список продуктов
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
            InlineKeyboardButton(
                button_text,
                callback_data=f"{CALLBACK_SELECT_PRODUCT}{real_index}"
            )
        ])

    # Пагинация (только если больше одной страницы)
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=CALLBACK_PAGE_PREV))
        else:
            nav_row.append(InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))

        nav_row.append(
            InlineKeyboardButton(
                f"· {page + 1} / {total_pages} ·",
                callback_data=CALLBACK_NOOP
            )
        )

        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=CALLBACK_PAGE_NEXT))
        else:
            nav_row.append(InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))

        buttons.append(nav_row)

    # Действия
    buttons.append([
        InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN)
    ])
    buttons.append([
        InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)
    ])

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
    """Клавиатура для ручного ввода веса."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← К вариантам веса", callback_data=CALLBACK_BACK_TO_WEIGHT)],
        [InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN)],
    ])


def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа приёма пищи."""
    buttons = []
    for meal_type, label in MEAL_TYPES.items():
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"{CALLBACK_MEAL_PREFIX}{meal_type}")
        ])

    buttons.append([
        InlineKeyboardButton("✏️ ← Изменить вес", callback_data=CALLBACK_BACK_TO_WEIGHT),
        InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
    ])

    return InlineKeyboardMarkup(buttons)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data=CALLBACK_CONFIRM_ADD)],
        [
            InlineKeyboardButton("✏️ Изменить вес", callback_data=CALLBACK_CHANGE_WEIGHT),
            InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
        ],
        [InlineKeyboardButton("📔 Отмена (в дневник)", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_save_favorite_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура предложения сохранить в избранное."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Да, сохранить", callback_data=CALLBACK_SAVE_FAVORITE_YES),
            InlineKeyboardButton("👌 Нет", callback_data=CALLBACK_SAVE_FAVORITE_NO),
        ],
    ])


def get_after_add_keyboard() -> InlineKeyboardMarkup:
    """Экран после успешного добавления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽️ Добавить ещё одно блюдо", callback_data=CALLBACK_ADD_ANOTHER)],
        [InlineKeyboardButton("🔍 Поискать что-то другое", callback_data=CALLBACK_SEARCH_AGAIN)],
        [InlineKeyboardButton("📔 Вернуться в дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_favorites_keyboard(
    favorites: List[Dict[str, Any]],
    page: int = 0
) -> InlineKeyboardMarkup:
    """Клавиатура избранного с пагинацией."""
    total_pages = max(1, (len(favorites) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_favs = favorites[start_idx:end_idx]

    buttons = []

    if not favorites:
        buttons.append([
            InlineKeyboardButton("😕 Пока ничего нет", callback_data=CALLBACK_NOOP)
        ])
    else:
        for i, fav in enumerate(page_favs):
            # 🎯 ВАЖНО: используем fav["id"], а не real_index
            fav_id = fav["id"]
            name = fav["food_name"][:28]
            kcal = fav.get("kcal", 0)
            weight = fav.get("amount_g", 0)
            times_used = fav.get("times_used", 1)
            
            buttons.append([
                InlineKeyboardButton(
                    f"⭐ {name} · {weight:.0f}г · {kcal}ккал (×{times_used})",
                    callback_data=f"{CALLBACK_FAVORITE_PREFIX}{fav_id}"  # 🎯 ID, не индекс
                )
            ])

        # Пагинация
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("◀️", callback_data=CALLBACK_FAV_PAGE_PREV))
            else:
                nav_row.append(InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))
            nav_row.append(
                InlineKeyboardButton(f"· {page + 1}/{total_pages} ·", callback_data=CALLBACK_NOOP)
            )
            if page < total_pages - 1:
                nav_row.append(InlineKeyboardButton("▶️", callback_data=CALLBACK_FAV_PAGE_NEXT))
            else:
                nav_row.append(InlineKeyboardButton("·", callback_data=CALLBACK_NOOP))
            buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("🔍 Новый поиск", callback_data=CALLBACK_SEARCH_AGAIN),
        InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY),
    ])

    return InlineKeyboardMarkup(buttons)


def get_barcode_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для режима сканирования штрихкода."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Ввести цифры вручную", callback_data=CALLBACK_BACK_TO_TEXT)],
        [InlineKeyboardButton("🔙 ← К выбору способа", callback_data=CALLBACK_BACK_TO_METHOD)],
        [InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_voice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для режима голосового ввода."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← К выбору способа", callback_data=CALLBACK_BACK_TO_METHOD)],
        [InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_back_keyboard(callback_data: str = CALLBACK_BACK_TO_DIARY) -> InlineKeyboardMarkup:
    """Универсальная кнопка Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ← Назад", callback_data=callback_data)]
    ])