"""
Модуль работы с водой.
"""
from handlers.water.handlers import get_water_handler
from handlers.water.constants import (
    DEFAULT_WATER_ML, WATER_VOLUMES,
    STATE_SELECT_VOLUME, STATE_WATER_INFO,
    CALLBACK_ADD_WATER, CALLBACK_ADD_WATER_DEFAULT, CALLBACK_SHOW_VOLUMES,
    CALLBACK_BACK_TO_DIARY, CALLBACK_WATER_INFO, CALLBACK_WATER_BACK,
)
from handlers.water.utils import (
    get_water_display, format_water_progress, get_water_status_text,
    calculate_water_goal, get_water_info_text,
)
from handlers.water.keyboards import (
    get_water_volume_keyboard, get_water_info_keyboard,
)

__all__ = [
    "get_water_handler",
    "DEFAULT_WATER_ML",
    "WATER_VOLUMES",
    "STATE_SELECT_VOLUME",
    "STATE_WATER_INFO",
    "CALLBACK_ADD_WATER",
    "CALLBACK_ADD_WATER_DEFAULT",
    "CALLBACK_SHOW_VOLUMES",
    "CALLBACK_BACK_TO_DIARY",
    "CALLBACK_WATER_INFO",
    "CALLBACK_WATER_BACK",
    "get_water_display",
    "format_water_progress",
    "get_water_status_text",
    "calculate_water_goal",
    "get_water_info_text",
    "get_water_volume_keyboard",
    "get_water_info_keyboard",
]