"""
Состояния FSM и callback-данные для истории питания.
🎯 Обновлено: убран "Завтра", добавлены сводки и "Повторить день".
"""

# ============ Состояния ConversationHandler ============
(
    STATE_MAIN_MENU,        # Главное меню выбора даты
    STATE_CALENDAR,         # Режим календаря
    STATE_PERIOD_SUMMARY,   # 🎯 НОВОЕ: сводка за период (неделя/месяц)
) = range(3)

# ============ Callback для главного меню ============
CALLBACK_TODAY = "history_today"
CALLBACK_YESTERDAY = "history_yesterday"
# 🎯 УБРАНО: CALLBACK_TOMORROW (бессмыслен для истории)
CALLBACK_WEEK = "history_week"          # 🎯 НОВОЕ
CALLBACK_MONTH = "history_month"        # 🎯 НОВОЕ
CALLBACK_OTHER_DATE = "history_other_date"
CALLBACK_BACK_TO_MENU = "history_back_to_menu"

# ============ Callback для календаря ============
CALLBACK_CALENDAR_PREV = "calendar_prev"
CALLBACK_CALENDAR_NEXT = "calendar_next"
CALLBACK_CALENDAR_SELECT = "calendar_select"
CALLBACK_CALENDAR_BACK = "calendar_back"

# ============ Callback для навигации ============
CALLBACK_NAV_TODAY = "nav_today"
CALLBACK_NAV_YESTERDAY = "nav_yesterday"
# 🎯 УБРАНО: CALLBACK_NAV_TOMORROW
CALLBACK_NAV_OTHER_DATE = "nav_other_date"
CALLBACK_ADD_FOOD = "nav_add_food"
CALLBACK_REPEAT_DAY = "nav_repeat_day"  # 🎯 НОВОЕ: повторить блюда дня

# ============ Callback для сводок ============
CALLBACK_BACK_FROM_SUMMARY = "summary_back"  # 🎯 НОВОЕ
CALLBACK_SHOW_MONTH_FROM_WEEK = "summary_to_month"  # 🎯 НОВОЕ

# ============ Статусы дня для цветовых индикаторов ============
STATUS_GOOD = "good"          # 🟢 в пределах ±10% от нормы
STATUS_WARNING = "warning"    # 🟡 перебор/недобор 10-25%
STATUS_BAD = "bad"            # 🔴 перебор/недобор >25%
STATUS_EMPTY = "empty"        # ⚪ нет записей

# ============ Лимиты ============
MAX_MEALS_DISPLAY = 15
MAX_WATER_DISPLAY = 10
DAYS_IN_WEEK = 7
DAYS_IN_MONTH = 30