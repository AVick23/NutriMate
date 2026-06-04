"""
Состояния FSM и callback-данные для добавления еды.
"""

# ============ Состояния ConversationHandler ============
(
    STATE_SELECT_METHOD,       # Выбор способа добавления
    STATE_WAIT_FOR_TEXT,       # Ожидание текстового ввода
    STATE_SELECT_PRODUCT,      # Выбор продукта из результатов (с пагинацией)
    STATE_ENTER_WEIGHT,        # Ввод веса
    STATE_SELECT_MEAL_TYPE,    # Выбор типа приёма пищи
    STATE_CONFIRM_ADD,         # Подтверждение
    STATE_WAIT_FOR_BARCODE,    # Ожидание штрихкода
    STATE_SELECT_FAVORITE,     # Выбор из избранного
    STATE_AFTER_ADD,           # Экран после успешного добавления
    STATE_WAIT_FOR_VOICE,      # Ожидание голосового сообщения
) = range(10)

# ============ Типы приёмов пищи ============
MEAL_TYPES = {
    "breakfast": "🥐 Завтрак",
    "lunch": "🍲 Обед",
    "dinner": "🍽️ Ужин",
    "snack": "🍎 Перекус",
}

# ============ Константы пагинации ============
PAGE_SIZE = 5  # Продуктов на странице

# ============ Callback: методы добавления ============
CALLBACK_METHOD_TEXT = "food_method_text"
CALLBACK_METHOD_BARCODE = "food_method_barcode"
CALLBACK_METHOD_FAVORITES = "food_method_favorites"
CALLBACK_METHOD_POPULAR = "food_method_popular"
CALLBACK_METHOD_VOICE = "food_method_voice"

# ============ Callback: навигация ============
CALLBACK_BACK_TO_DIARY = "food_back_to_diary"
CALLBACK_BACK_TO_METHOD = "food_back_to_method"
CALLBACK_BACK_TO_TEXT = "food_back_to_text"
CALLBACK_BACK_TO_RESULTS = "food_back_to_results"
CALLBACK_BACK_TO_WEIGHT = "food_back_to_weight"
CALLBACK_BACK_TO_PRODUCTS = "food_back_to_products"

# ============ Callback: поиск ============
CALLBACK_SEARCH_AGAIN = "food_search_again"
CALLBACK_SELECT_PRODUCT = "food_select_product_"  # + index

# ============ Callback: пагинация ============
CALLBACK_PAGE_PREV = "food_page_prev"
CALLBACK_PAGE_NEXT = "food_page_next"

# ============ Callback: вес ============
CALLBACK_WEIGHT_PREFIX = "food_weight_"
CALLBACK_WEIGHT_CUSTOM = "food_weight_custom"

# ============ Callback: тип приёма пищи ============
CALLBACK_MEAL_PREFIX = "food_meal_"

# ============ Callback: подтверждение ============
CALLBACK_CONFIRM_ADD = "food_confirm_add"
CALLBACK_CHANGE_WEIGHT = "food_change_weight"

# ============ Callback: после добавления ============
CALLBACK_ADD_ANOTHER = "food_add_another"
CALLBACK_SAVE_FAVORITE_YES = "food_save_favorite_yes"
CALLBACK_SAVE_FAVORITE_NO = "food_save_favorite_no"

# ============ Callback: избранное ============
CALLBACK_FAVORITE_PREFIX = "food_fav_"
CALLBACK_FAV_PAGE_PREV = "fav_page_prev"
CALLBACK_FAV_PAGE_NEXT = "fav_page_next"

# ============ Callback: служебные ============
CALLBACK_NOOP = "food_noop"
CALLBACK_CANCEL = "food_cancel"