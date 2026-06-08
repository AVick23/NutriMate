"""
Состояния FSM и callback-данные для добавления еды.
🎯 Обновлено: добавлены callback для трекинга воды.
"""
# ============ Состояния ConversationHandler ============
(
    STATE_SELECT_METHOD,       # Главное меню (3 кнопки)
    STATE_UNIVERSAL_INPUT,     # 🎯 ЕДИНОЕ состояние для текста, фото и голоса
    STATE_SELECT_PRODUCT,      # Выбор продукта из результатов
    STATE_ENTER_WEIGHT,        # Ввод веса
    STATE_SELECT_MEAL_TYPE,    # Выбор типа приёма пищи
    STATE_CONFIRM_ADD,         # Подтверждение
    STATE_AFTER_ADD,           # Экран после успешного добавления
    # Ручной ввод (остаётся как fallback, если универсальный парсер не справился)
    STATE_MANUAL_NAME,
    STATE_MANUAL_WEIGHT,
    STATE_MANUAL_KCAL,
    STATE_MANUAL_PROTEIN,
    STATE_MANUAL_FAT,
    STATE_MANUAL_CARBS,
    STATE_MANUAL_CONFIRM,
) = range(14)

# ============ Типы приёмов пищи ============
MEAL_TYPES = {
    "breakfast": "🥐 Завтрак",
    "lunch": "🍲 Обед",
    "dinner": "🍽️ Ужин",
    "snack": "🍎 Перекус",
}

# ============ Константы пагинации ============
PAGE_SIZE = 5

# ============ Callback: методы добавления ============
CALLBACK_METHOD_UNIVERSAL = "food_method_universal"  # 🎯 Новая главная кнопка
CALLBACK_METHOD_FAVORITES = "favorites_show"
CALLBACK_METHOD_POPULAR = "food_method_popular"

# ============ Callback: навигация ============
CALLBACK_BACK_TO_DIARY = "food_back_to_diary"
CALLBACK_BACK_TO_RESULTS = "food_back_to_results"
CALLBACK_BACK_TO_WEIGHT = "food_back_to_weight"
CALLBACK_SEARCH_AGAIN = "food_search_again"

# ============ Callback: поиск и выбор ============
CALLBACK_SELECT_PRODUCT = "food_select_product_"
CALLBACK_PAGE_PREV = "food_page_prev"
CALLBACK_PAGE_NEXT = "food_page_next"

# ============ Callback: вес и приёмы пищи ============
CALLBACK_WEIGHT_PREFIX = "food_weight_"
CALLBACK_WEIGHT_CUSTOM = "food_weight_custom"
CALLBACK_MEAL_PREFIX = "food_meal_"

# ============ Callback: подтверждение и избранное ============
CALLBACK_CONFIRM_ADD = "food_confirm_add"
CALLBACK_CHANGE_WEIGHT = "food_change_weight"
CALLBACK_ADD_ANOTHER = "food_add_another"
CALLBACK_SAVE_FAVORITE_YES = "food_save_favorite_yes"
CALLBACK_SAVE_FAVORITE_NO = "food_save_favorite_no"

# ============ Callback: ручной ввод (fallback) ============
CALLBACK_MANUAL_SKIP = "food_manual_skip"
CALLBACK_MANUAL_CONFIRM = "food_manual_confirm"
CALLBACK_MANUAL_EDIT = "food_manual_edit"
CALLBACK_MANUAL_BARCODE = "food_manual_barcode"

# ============ Callback: трекинг воды ============
CALLBACK_TRACK_WATER_YES = "food_track_water_yes"
CALLBACK_TRACK_WATER_NO = "food_track_water_no"

# ============ Callback: служебные ============
CALLBACK_NOOP = "food_noop"
CALLBACK_CANCEL = "food_cancel"