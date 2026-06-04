"""
Состояния FSM и callback-данные для модуля избранного.
"""

# ============ Состояния ConversationHandler ============
(
    STATE_MAIN_MENU,          # Главное меню избранного
    STATE_ENTER_WEIGHT,       # Выбор веса перед добавлением
    STATE_SELECT_MEAL_TYPE,   # Выбор типа приёма пищи
    STATE_CONFIRM_DELETE,     # Подтверждение удаления одного блюда
    STATE_CONFIRM_CLEAR,      # Подтверждение очистки всего избранного
) = range(5)

# ============ Callback: навигация ============
CALLBACK_FAVORITES_SHOW = "favorites_show"           # entry point из дневника
CALLBACK_FAVORITES_MENU = "fav_menu"                 # возврат в главное меню
CALLBACK_BACK_TO_DIARY = "fav_back_to_diary"

# ============ Callback: выбор блюда ============
CALLBACK_FAVORITE_SELECT = "fav_select_"             # + id
CALLBACK_FAVORITE_DELETE = "fav_delete_"             # + id (запрос подтверждения)
CALLBACK_FAVORITE_CONFIRM_DELETE = "fav_confirm_del_"  # + id (подтвердить удаление)
CALLBACK_FAVORITE_CLEAR_ALL = "fav_clear_all"        # запрос очистки
CALLBACK_FAVORITE_CONFIRM_CLEAR = "fav_confirm_clear"  # подтвердить очистку
CALLBACK_FAVORITE_CANCEL = "fav_cancel"              # отмена удаления/очистки

# ============ Callback: вес ============
CALLBACK_WEIGHT_PREFIX = "fav_weight_"               # fav_weight_100
CALLBACK_WEIGHT_CUSTOM = "fav_weight_custom"

# ============ Callback: тип приёма пищи ============
CALLBACK_MEAL_PREFIX = "fav_meal_"                   # fav_meal_breakfast

# ============ Callback: пагинация ============
CALLBACK_PAGE_PREV = "fav_page_prev"
CALLBACK_PAGE_NEXT = "fav_page_next"
CALLBACK_NOOP = "fav_noop"

# ============ Константы ============
PAGE_SIZE = 5  # Блюд на странице

# Типы приёмов пищи (дублируем из add_food для независимости модуля)
MEAL_TYPES = {
    "breakfast": "🥐 Завтрак",
    "lunch": "🍲 Обед",
    "dinner": "🍽️ Ужин",
    "snack": "🍎 Перекус",
}