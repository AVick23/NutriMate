# handlers/measurements/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List
from .constants import MEASUREMENT_TYPES, QUICK_WEIGHT_VALUES, QUICK_CIRCUMFERENCE_VALUES


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню замеров."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Добавить замер", callback_data="measurements_add")],
        [InlineKeyboardButton("📈 История замеров", callback_data="measurements_history")],
        [InlineKeyboardButton("🎯 Мои цели", callback_data="measurements_goals")],
        [InlineKeyboardButton("← Назад в дневник", callback_data="measurements_back")],
    ])


def get_measurement_types_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа замера."""
    buttons = []
    for type_id, info in MEASUREMENT_TYPES.items():
        buttons.append([
            InlineKeyboardButton(
                f"{info['emoji']} {info['display']}", 
                callback_data=f"measurements_type_{type_id}"
            )
        ])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="measurements_menu")])
    return InlineKeyboardMarkup(buttons)


def get_value_keyboard(measurement_type_id: int, current_value: float = None) -> InlineKeyboardMarkup:
    """Клавиатура для ввода значения замера."""
    if measurement_type_id == 1:  # weight
        quick_values = QUICK_WEIGHT_VALUES
        unit = "кг"
    else:
        quick_values = QUICK_CIRCUMFERENCE_VALUES
        unit = "см"
    
    buttons = []
    row = []
    for val in quick_values:
        row.append(InlineKeyboardButton(f"{val} {unit}", callback_data=f"measurements_value_{val}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("⌨️ Своё значение", callback_data="measurements_value_custom")])
    buttons.append([InlineKeyboardButton("← Назад к типам", callback_data="measurements_add")])
    
    return InlineKeyboardMarkup(buttons)


def get_history_types_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа для истории."""
    buttons = []
    for type_id, info in MEASUREMENT_TYPES.items():
        buttons.append([
            InlineKeyboardButton(
                f"{info['emoji']} {info['display']}", 
                callback_data=f"measurements_history_type_{type_id}"
            )
        ])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="measurements_menu")])
    return InlineKeyboardMarkup(buttons)


def get_history_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата из истории."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад к типам", callback_data="measurements_history")],
        [InlineKeyboardButton("📏 Главное меню", callback_data="measurements_menu")],
    ])


def get_add_more_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после добавления замера."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить ещё замер", callback_data="measurements_add")],
        [InlineKeyboardButton("📈 Посмотреть историю", callback_data="measurements_history")],
        [InlineKeyboardButton("📏 Главное меню", callback_data="measurements_menu")],
    ])


def get_goals_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для целей."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚖️ Установить цель по весу", callback_data="measurements_goal_weight")],
        [InlineKeyboardButton("📏 Установить цель по талии", callback_data="measurements_goal_waist")],
        [InlineKeyboardButton("← Назад", callback_data="measurements_menu")],
    ])