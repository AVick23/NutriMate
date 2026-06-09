"""
Клавиатуры для управления водой.
🎯 Обновлено: добавлена информационная кнопка о норме воды.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .constants import WATER_VOLUMES, CALLBACK_WATER_INFO, CALLBACK_WATER_BACK


def get_water_volume_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора объёма воды.
    """
    buttons = []
    row = []
    for i, volume in enumerate(WATER_VOLUMES):
        row.append(InlineKeyboardButton(f"{volume} мл", callback_data=f"water_vol_{volume}"))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("✏️ Свой объём", callback_data="water_vol_custom")])
    buttons.append([InlineKeyboardButton("ℹ️ О норме воды", callback_data=CALLBACK_WATER_INFO)])  # 🎯 НОВОЕ
    buttons.append([InlineKeyboardButton("🔙 ← Назад в дневник", callback_data=CALLBACK_WATER_BACK)])

    return InlineKeyboardMarkup(buttons)


def get_water_info_keyboard() -> InlineKeyboardMarkup:
    """
    🎯 НОВОЕ: Клавиатура для экрана с информацией о воде.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💧 Добавить воду", callback_data="water_add")],
        [InlineKeyboardButton("🔙 ← Назад", callback_data=CALLBACK_WATER_BACK)],
    ])