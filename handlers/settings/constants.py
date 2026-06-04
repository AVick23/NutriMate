# handlers/settings/constants.py

# Состояния ConversationHandler для редактирования профиля
(
    STATE_EDIT_MENU,
    STATE_EDIT_WEIGHT,
    STATE_EDIT_HEIGHT,
    STATE_EDIT_AGE,
    STATE_EDIT_GENDER,
    STATE_EDIT_ACTIVITY,
    STATE_EDIT_GOAL,
    STATE_CONFIRM_SAVE,
) = range(8)

# Callback данные для меню настроек
CALLBACK_SETTINGS_MENU = "settings_menu"
CALLBACK_EDIT_PROFILE = "settings_edit_profile"
CALLBACK_EDIT_WATER = "settings_edit_water"
CALLBACK_EXPORT_DATA = "settings_export_data"
CALLBACK_DELETE_DATA = "settings_delete_data"
CALLBACK_BACK_TO_DIARY = "settings_back_to_diary"

# Callback для выбора параметра редактирования
CALLBACK_EDIT_WEIGHT = "edit_weight"
CALLBACK_EDIT_HEIGHT = "edit_height"
CALLBACK_EDIT_AGE = "edit_age"
CALLBACK_EDIT_GENDER = "edit_gender"
CALLBACK_EDIT_ACTIVITY = "edit_activity"
CALLBACK_EDIT_GOAL = "edit_goal"
CALLBACK_EDIT_ALL = "edit_all"

# Callback для подтверждения
CALLBACK_SAVE_PROFILE = "save_profile"
CALLBACK_CANCEL = "cancel_edit"