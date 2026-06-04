# handlers/settings/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.registration.utils import ActivityLevel, Goal, Gender, ACTIVITY_NAMES, GOAL_NAMES, GENDER_NAMES


def get_settings_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню настроек."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Редактировать профиль", callback_data="settings_edit_profile")],
        [InlineKeyboardButton("💧 Настройки воды", callback_data="settings_edit_water")],
        [InlineKeyboardButton("📥 Экспорт данных", callback_data="settings_export_data")],
        [InlineKeyboardButton("🗑 Удалить мои данные", callback_data="settings_delete_data")],
        [InlineKeyboardButton("← Назад в меню", callback_data="settings_back_to_diary")],
    ])


def get_profile_edit_keyboard(profile: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора параметра для редактирования.
    profile содержит текущие значения.
    """
    buttons = [
        [InlineKeyboardButton(f"⚖️ Вес: {profile['weight_kg']} кг", callback_data="edit_weight")],
        [InlineKeyboardButton(f"📏 Рост: {profile['height_cm']} см", callback_data="edit_height")],
        [InlineKeyboardButton(f"🎂 Возраст: {profile['age']} лет", callback_data="edit_age")],
        [InlineKeyboardButton(f"👤 Пол: {GENDER_NAMES[Gender(profile['gender'])]}", callback_data="edit_gender")],
        [InlineKeyboardButton(f"🏃 Активность: {ACTIVITY_NAMES[ActivityLevel(profile['activity_level'])]}", callback_data="edit_activity")],
        [InlineKeyboardButton(f"🎯 Цель: {GOAL_NAMES[Goal(profile['goal'])]}", callback_data="edit_goal")],
        [InlineKeyboardButton("✅ Сохранить и пересчитать", callback_data="save_profile")],
        [InlineKeyboardButton("← Отмена", callback_data="cancel_edit")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_confirm_save_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение сохранения профиля."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, пересчитать", callback_data="save_profile_confirm")],
        [InlineKeyboardButton("✏️ Продолжить редактирование", callback_data="save_profile_continue")],
        [InlineKeyboardButton("← Отмена", callback_data="cancel_edit")],
    ])


def get_back_keyboard(callback_data: str = "settings_menu") -> InlineKeyboardMarkup:
    """Универсальная кнопка Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад", callback_data=callback_data)]
    ])


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пола (аналогична регистрации)."""
    buttons = []
    for gender in Gender:
        buttons.append([InlineKeyboardButton(GENDER_NAMES[gender], callback_data=f"set_gender_{gender.value}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="cancel_edit")])
    return InlineKeyboardMarkup(buttons)


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора активности."""
    buttons = []
    for level in ActivityLevel:
        buttons.append([InlineKeyboardButton(ACTIVITY_NAMES[level], callback_data=f"set_activity_{level.value}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="cancel_edit")])
    return InlineKeyboardMarkup(buttons)


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора цели."""
    buttons = []
    for goal in Goal:
        buttons.append([InlineKeyboardButton(GOAL_NAMES[goal], callback_data=f"set_goal_{goal.value}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="cancel_edit")])
    return InlineKeyboardMarkup(buttons)