# handlers/measurements/constants.py

# Состояния ConversationHandler
(
    STATE_MAIN_MENU,
    STATE_CHOOSE_TYPE,
    STATE_ENTER_VALUE,
    STATE_HISTORY_TYPE,
) = range(4)

# Callback данные для главного меню
CALLBACK_MEASUREMENTS_MENU = "measurements_menu"
CALLBACK_MEASUREMENTS_ADD = "measurements_add"
CALLBACK_MEASUREMENTS_HISTORY = "measurements_history"
CALLBACK_MEASUREMENTS_GOALS = "measurements_goals"
CALLBACK_MEASUREMENTS_BACK = "measurements_back"

# Callback для выбора типа замера
CALLBACK_TYPE_PREFIX = "measurements_type_"

# Callback для быстрого ввода значения
CALLBACK_VALUE_PREFIX = "measurements_value_"
CALLBACK_VALUE_CUSTOM = "measurements_value_custom"

# Типы замеров
MEASUREMENT_TYPES = {
    1: {"id": 1, "name": "weight", "display": "⚖️ Вес", "unit": "кг", "emoji": "⚖️", "sort": 1},
    2: {"id": 2, "name": "waist", "display": "📏 Талия", "unit": "см", "emoji": "📏", "sort": 2},
    3: {"id": 3, "name": "hips", "display": "🍑 Бёдра", "unit": "см", "emoji": "🍑", "sort": 3},
    4: {"id": 4, "name": "chest", "display": "💪 Грудь", "unit": "см", "emoji": "💪", "sort": 4},
    5: {"id": 5, "name": "arm", "display": "💪 Рука (бицепс)", "unit": "см", "emoji": "💪", "sort": 5},
    6: {"id": 6, "name": "thigh", "display": "🦵 Бедро", "unit": "см", "emoji": "🦵", "sort": 6},
}

# Быстрые значения для веса (кг)
QUICK_WEIGHT_VALUES = [84.0, 84.5, 85.0, 85.5, 86.0]

# Быстрые значения для объёмов (см)
QUICK_CIRCUMFERENCE_VALUES = [80, 82, 84, 86, 88, 90]

# Максимальное количество записей для истории
MAX_HISTORY_ENTRIES = 15