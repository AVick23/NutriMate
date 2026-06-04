"""
Клавиатуры для модуля избранного.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any
from .constants import (
    MEAL_TYPES, PAGE_SIZE,
    CALLBACK_NOOP,
    CALLBACK_FAVORITE_SELECT, CALLBACK_FAVORITE_DELETE,
    CALLBACK_FAVORITE_CONFIRM_DELETE, CALLBACK_FAVORITE_CONFIRM_CLEAR,
    CALLBACK_FAVORITE_CLEAR_ALL, CALLBACK_FAVORITE_CANCEL,
    CALLBACK_FAVORITES_MENU, CALLBACK_BACK_TO_DIARY,
    CALLBACK_PAGE_PREV, CALLBACK_PAGE_NEXT,
    CALLBACK_WEIGHT_PREFIX, CALLBACK_WEIGHT_CUSTOM,
    CALLBACK_MEAL_PREFIX,
)


def get_favorites_list_keyboard(
    favorites: List[Dict[str, Any]],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """
    Главная клавиатура избранного с пагинацией.
    Для каждого блюда 2 кнопки: «⭐ Выбрать» и «🗑 Удалить».
    """
    total_pages = max(1, (len(favorites) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_favs = favorites[start_idx:end_idx]

    buttons = []

    if not favorites:
        buttons.append([
            InlineKeyboardButton("😕 Избранное пусто", callback_data=CALLBACK_NOOP)
        ])
    else:
        for fav in page_favs:
            fav_id = fav["id"]
            name = fav["food_name"][:25]
            weight = fav.get("amount_g", 0)
            kcal = fav.get("kcal", 0)
            times_used = fav.get("times_used", 1)

            # Кнопка выбора
            buttons.append([
                InlineKeyboardButton(
                    f"⭐ {name} · {weight:.0f}г · {kcal}ккал (×{times_used})",
                    callback_data=f"{CALLBACK_FAVORITE_SELECT}{fav_id}"
                )
            ])

            # Кнопка удаления (чуть меньше, с отступом)
            buttons.append([
                InlineKeyboardButton(
                    f"    🗑 Удалить «{name[:20]}»",
                    callback_data=f"{CALLBACK_FAVORITE_DELETE}{fav_id}"
                )
            ])

        # Пагинация
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

    # Общие действия
    buttons.append([
        InlineKeyboardButton("🍽️ Добавить новую еду", callback_data="food_select_method"),
    ])

    if favorites:
        buttons.append([
            InlineKeyboardButton(
                "🗑 Очистить всё избранное",
                callback_data=CALLBACK_FAVORITE_CLEAR_ALL
            )
        ])

    buttons.append([
        InlineKeyboardButton("📔 ← В дневник", callback_data=CALLBACK_BACK_TO_DIARY)
    ])

    return InlineKeyboardMarkup(buttons)


def get_weight_keyboard(default_weight: float = 100) -> InlineKeyboardMarkup:
    """Клавиатура выбора веса с учётом последнего использованного."""
    # Умные быстрые значения вокруг default_weight
    base = int(round(default_weight / 50.0)) * 50
    if base < 50:
        base = 50
    quick_values = [base - 50, base, base + 50, base + 100, base + 150]
    quick_values = [v for v in quick_values if 10 <= v <= 1000]
    # Убираем дубликаты и сортируем
    quick_values = sorted(set(quick_values))[:6]

    buttons = []
    row = []
    for val in quick_values:
        row.append(InlineKeyboardButton(
            f"{val}г",
            callback_data=f"{CALLBACK_WEIGHT_PREFIX}{val}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("✏️ Свой вес", callback_data=CALLBACK_WEIGHT_CUSTOM)
    ])

    buttons.append([
        InlineKeyboardButton("🔙 ← Назад к избранному", callback_data=CALLBACK_FAVORITES_MENU)
    ])

    return InlineKeyboardMarkup(buttons)


def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа приёма пищи."""
    buttons = []
    for meal_type, label in MEAL_TYPES.items():
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"{CALLBACK_MEAL_PREFIX}{meal_type}")
        ])

    buttons.append([
        InlineKeyboardButton("🔙 ← Назад к избранному", callback_data=CALLBACK_FAVORITES_MENU)
    ])

    return InlineKeyboardMarkup(buttons)


def get_confirm_delete_keyboard(fav_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления одного блюда."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Да, удалить",
                callback_data=f"{CALLBACK_FAVORITE_CONFIRM_DELETE}{fav_id}"
            ),
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data=CALLBACK_FAVORITES_MENU
            ),
        ],
    ])


def get_confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение очистки всего избранного."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Да, очистить всё",
                callback_data=CALLBACK_FAVORITE_CONFIRM_CLEAR
            ),
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data=CALLBACK_FAVORITES_MENU
            ),
        ],
    ])