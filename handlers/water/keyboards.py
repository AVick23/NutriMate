"""
Клавиатуры для управления водой.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .constants import WATER_VOLUMES, CALLBACK_BACK_TO_DIARY


def get_water_volume_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора объёма воды."""
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
    # 🎯 Используем константу из constants.py
    buttons.append([InlineKeyboardButton("🔙 ← Назад в дневник", callback_data=CALLBACK_BACK_TO_DIARY)])

    return InlineKeyboardMarkup(buttons)