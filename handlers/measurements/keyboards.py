from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any
from datetime import datetime
from .constants import (
    MEASUREMENT_TYPES, 
    CALLBACK_VALUE_PREFIX, CALLBACK_VALUE_CUSTOM, CALLBACK_DELETE_PREFIX, CALLBACK_NOOP
)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню замеров (🎯 убрана заглушка "Мои цели")."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Добавить замер", callback_data="measurements_add")],
        [InlineKeyboardButton("📈 История замеров", callback_data="measurements_history")],
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

def get_value_keyboard(measurement_type_id: int, last_value: float = None) -> InlineKeyboardMarkup:
    """🎯 Клавиатура для ввода значения замера (ДИНАМИЧЕСКАЯ)."""
    unit = "кг" if measurement_type_id == 1 else "см"
    step = 0.5 if measurement_type_id == 1 else 1.0
    
    if last_value:
        # Генерируем динамически: -2 шага, -1 шаг, текущий, +1 шаг, +2 шага
        quick_values = [
            round(last_value - step * 2, 1),
            round(last_value - step, 1),
            round(last_value, 1),
            round(last_value + step, 1),
            round(last_value + step * 2, 1)
        ]
    else:
        # Дефолтные значения, если нет истории
        if measurement_type_id == 1:
            quick_values = [60.0, 70.0, 80.0, 90.0, 100.0]
        else:
            quick_values = [70.0, 80.0, 90.0, 100.0, 110.0]
            
    buttons = []
    row = []
    for val in quick_values:
        if val <= 0:
            val = step 
        row.append(InlineKeyboardButton(f"{val} {unit}", callback_data=f"{CALLBACK_VALUE_PREFIX}{val}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⌨️ Своё значение", callback_data=CALLBACK_VALUE_CUSTOM)])
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

def get_history_list_keyboard(history: List[Dict[str, Any]], type_id: int, unit: str) -> InlineKeyboardMarkup:
    """🎯 НОВАЯ: Список истории с кнопками удаления."""
    from .utils import format_date_ru
    buttons = []
    for record in history:
        date_str_raw = record.get("measured_at")
        if isinstance(date_str_raw, str):
            dt = datetime.fromisoformat(date_str_raw.replace(' ', 'T'))
        else:
            dt = date_str_raw
            
        date_str = format_date_ru(dt)
        val = record["value"]
        
        row = [
            InlineKeyboardButton(f"{date_str}: {val:.1f} {unit}", callback_data=CALLBACK_NOOP),
            InlineKeyboardButton("🗑", callback_data=f"{CALLBACK_DELETE_PREFIX}{record['id']}")
        ]
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("← Назад к типам", callback_data="measurements_history")])
    buttons.append([InlineKeyboardButton("📏 Главное меню", callback_data="measurements_menu")])
    return InlineKeyboardMarkup(buttons)

def get_history_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад к типам", callback_data="measurements_history")],
        [InlineKeyboardButton("📏 Главное меню", callback_data="measurements_menu")],
    ])

def get_add_more_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить ещё замер", callback_data="measurements_add")],
        [InlineKeyboardButton("📈 Посмотреть историю", callback_data="measurements_history")],
        [InlineKeyboardButton("📏 Главное меню", callback_data="measurements_menu")],
    ])