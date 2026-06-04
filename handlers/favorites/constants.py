"""
Состояния FSM и callback-данные для модуля избранного.
"""

# ============ Состояния ConversationHandler ============
(
    STATE_MAIN_MENU,          # Главное меню избранного
    STATE_ENTER_WEIGHT,       # Выбор веса перед добавлением
    STATE_SELECT_MEAL_TYPE,   # Выбор типа приёма пищи
    STATE_CONFIRM_ADD,        # 🎯 НОВОЕ: Подтверждение добавления
    STATE_AFTER_ADD,          # 🎯 НОВОЕ: Экран после успешного добавления
    STATE_CONFIRM_DELETE,     # Подтверждение удаления одного блюда
    STATE_CONFIRM_CLEAR,      # Подтверждение очистки всего избранного
) = range(7)

# ============ Callback: навигация ============
CALLBACK_FAVORITES_SHOW = "favorites_show"
CALLBACK_FAVORITES_MENU = "fav_menu"
CALLBACK_BACK_TO_DIARY = "fav_back_to_diary"

# ============ Callback: выбор блюда ============
CALLBACK_FAVORITE_SELECT = "fav_select_"
CALLBACK_FAVORITE_DELETE = "fav_delete_"
CALLBACK_FAVORITE_CONFIRM_DELETE = "fav_confirm_del_"
CALLBACK_FAVORITE_CLEAR_ALL = "fav_clear_all"
CALLBACK_FAVORITE_CONFIRM_CLEAR = "fav_confirm_clear"
CALLBACK_FAVORITE_CANCEL = "fav_cancel"

# ============ Callback: вес ============
CALLBACK_WEIGHT_PREFIX = "fav_weight_"
CALLBACK_WEIGHT_CUSTOM = "fav_weight_custom"

# ============ Callback: тип приёма пищи ============
CALLBACK_MEAL_PREFIX = "fav_meal_"

# ============ Callback: подтверждение добавления (НОВОЕ) ============
CALLBACK_CONFIRM_ADD = "fav_confirm_add"
CALLBACK_CHANGE_WEIGHT = "fav_change_weight"

# ============ Callback: после добавления (НОВОЕ) ============
CALLBACK_ADD_ANOTHER = "fav_add_another"
CALLBACK_SEARCH_AGAIN = "fav_search_again"

# ============ Callback: пагинация ============
CALLBACK_PAGE_PREV = "fav_page_prev"
CALLBACK_PAGE_NEXT = "fav_page_next"
CALLBACK_NOOP = "fav_noop"

# ============ Константы ============
PAGE_SIZE = 5

MEAL_TYPES = {
    "breakfast": "🥐 Завтрак",
    "lunch": "🍲 Обед",
    "dinner": "🍽️ Ужин",
    "snack": "🍎 Перекус",
}