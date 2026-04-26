# handlers/registration/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.registration.utils import (
    ActivityLevel, Goal, Pace, Gender,
    ACTIVITY_NAMES, GOAL_NAMES, PACE_NAMES, PACE_NAMES_GAIN, GENDER_NAMES
)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="reg_cancel")]
    ])


def get_confirm_retry_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения с возможностью исправить."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, всё верно", callback_data="reg_confirm"),
            InlineKeyboardButton("✏️ Исправить", callback_data="reg_retry"),
        ]
    ])


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора уровня активности."""
    buttons = []
    for level in ActivityLevel:
        buttons.append([
            InlineKeyboardButton(
                ACTIVITY_NAMES[level],
                callback_data=f"reg_activity_{level.value}"
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="reg_cancel")])
    return InlineKeyboardMarkup(buttons)


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора цели."""
    buttons = []
    for goal in Goal:
        buttons.append([
            InlineKeyboardButton(
                GOAL_NAMES[goal],
                callback_data=f"reg_goal_{goal.value}"
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="reg_cancel")])
    return InlineKeyboardMarkup(buttons)


def get_pace_keyboard(goal: Goal) -> InlineKeyboardMarkup:
    """Клавиатура выбора темпа в зависимости от цели."""
    buttons = []
    names = PACE_NAMES_GAIN if goal == Goal.GAIN else PACE_NAMES

    for pace in Pace:
        buttons.append([
            InlineKeyboardButton(
                names[pace],
                callback_data=f"reg_pace_{pace.value}"
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="reg_cancel")])
    return InlineKeyboardMarkup(buttons)


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пола."""
    buttons = []
    for gender in Gender:
        buttons.append([
            InlineKeyboardButton(
                GENDER_NAMES[gender],
                callback_data=f"reg_gender_{gender.value}"
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="reg_cancel")])
    return InlineKeyboardMarkup(buttons)


def get_start_registration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для начала регистрации."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Начать знакомство", callback_data="reg_start")]
    ])


def get_complete_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после завершения регистрации."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📔 Открыть дневник", callback_data="diary_show")]
    ])