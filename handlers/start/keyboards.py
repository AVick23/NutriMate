# handlers/start/keyboards.py (опционально, если нужны другие клавиатуры)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_diary_more_keyboard() -> InlineKeyboardMarkup:
    """Меню 'Ещё' — раскрывается по нажатию на кнопку ⋯ в дневнике."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ Тренировка", callback_data="training_add")],
        [InlineKeyboardButton("⚖️ Вес", callback_data="weight_add")],
        [InlineKeyboardButton("📈 Прогресс", callback_data="progress_show")],
        [InlineKeyboardButton("⭐ Избранное", callback_data="favorites_show")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_show")],
        [InlineKeyboardButton("← Назад", callback_data="diary_back")],
    ])


def get_diary_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад в дневник."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📔 ← Вернуться в дневник", callback_data="diary_show")],
    ])