"""
Константы для модуля воды.
🎯 Обновлено: добавлены callback для информации о воде.
"""

# Состояния для ConversationHandler
STATE_SELECT_VOLUME = 1
STATE_WATER_INFO = 2  # 🎯 НОВОЕ

# Callback данные
CALLBACK_ADD_WATER = "water_add"
CALLBACK_ADD_WATER_DEFAULT = "water_add_default"
CALLBACK_SHOW_VOLUMES = "water_show_volumes"
CALLBACK_BACK_TO_DIARY = "water_back_to_diary"
CALLBACK_WATER_INFO = "water_info"  # 🎯 НОВОЕ
CALLBACK_WATER_BACK = "water_back"  # 🎯 НОВОЕ

# Объёмы воды (мл)
DEFAULT_WATER_ML = 250
WATER_VOLUMES = [250, 300, 500, 1000]

# Эмодзи для разных состояний
EMOJI_WATER = "💧"
EMOJI_WATER_FULL = "💙"
EMOJI_WATER_EXCESS = "💦"