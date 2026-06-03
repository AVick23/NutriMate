# handlers/history_of_add/constants.py

# Состояния ConversationHandler
(
    STATE_MAIN_MENU,      # главное меню выбора даты
    STATE_CALENDAR,       # режим календаря
) = range(2)

# Callback данные для главного меню
CALLBACK_TODAY = "history_today"
CALLBACK_YESTERDAY = "history_yesterday"
CALLBACK_TOMORROW = "history_tomorrow"
CALLBACK_OTHER_DATE = "history_other_date"
CALLBACK_BACK_TO_MENU = "history_back_to_menu"

# Callback данные для календаря
CALLBACK_CALENDAR_PREV = "calendar_prev"
CALLBACK_CALENDAR_NEXT = "calendar_next"
CALLBACK_CALENDAR_SELECT = "calendar_select"
CALLBACK_CALENDAR_BACK = "calendar_back"

# Callback данные для навигации после показа истории
CALLBACK_NAV_TODAY = "nav_today"
CALLBACK_NAV_YESTERDAY = "nav_yesterday"
CALLBACK_NAV_TOMORROW = "nav_tomorrow"
CALLBACK_NAV_OTHER_DATE = "nav_other_date"
CALLBACK_ADD_FOOD = "nav_add_food"

# Максимальное количество записей для показа
MAX_MEALS_DISPLAY = 15
MAX_WATER_DISPLAY = 10