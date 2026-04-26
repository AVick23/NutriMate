# handlers/add_food/constants.py

# Состояния ConversationHandler для добавления еды
(
    # Выбор способа добавления
    STATE_SELECT_METHOD,
    # Текстовый поиск
    STATE_WAIT_FOR_TEXT,
    STATE_SELECT_PRODUCT,
    STATE_SELECT_MEAL_TYPE,
    STATE_ENTER_WEIGHT,
    STATE_CONFIRM_ADD,
    # Штрихкод
    STATE_WAIT_FOR_BARCODE,
    # Избранное
    STATE_SELECT_FAVORITE,
) = range(8)  # <-- Исправлено с 9 на 8

# Типы приёмов пищи
MEAL_TYPES = {
    "breakfast": "🥐 Завтрак",
    "lunch": "🍲 Обед",
    "dinner": "🍽️ Ужин",
    "snack": "🍎 Перекус",
}

# Callback данные
CALLBACK_SELECT_METHOD = "food_select_method"
CALLBACK_TEXT_INPUT = "food_text_input"
CALLBACK_BARCODE_SCAN = "food_barcode_scan"
CALLBACK_FAVORITES = "food_favorites"
CALLBACK_BACK_TO_DIARY = "food_back_to_diary"

CALLBACK_SELECT_MEAL = "food_select_meal"
CALLBACK_SELECT_PRODUCT = "food_select_product"
CALLBACK_CONFIRM_ADD = "food_confirm_add"
CALLBACK_ADD_ANOTHER = "food_add_another"
CALLBACK_SAVE_FAVORITE = "food_save_favorite"
CALLBACK_CHANGE_WEIGHT = "food_change_weight"
CALLBACK_CANCEL = "food_cancel"