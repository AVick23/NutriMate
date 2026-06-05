"""
Клавиатуры для модуля сбора метрик.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Tuple, Optional
from .constants import (
    CALLBACK_METRICS_TODAY, CALLBACK_METRICS_EDIT, CALLBACK_METRICS_HISTORY,
    CALLBACK_METRICS_ANALYTICS, CALLBACK_METRICS_BACK_TO_DIARY, CALLBACK_METRICS_BACK_TO_MENU,
    CALLBACK_SLEEP, CALLBACK_ENERGY, CALLBACK_STRESS, CALLBACK_STEPS,
    CALLBACK_WORKOUT, CALLBACK_HUNGER, CALLBACK_DIGESTION, CALLBACK_CYCLE,
    CALLBACK_CONFIRM_ALL, CALLBACK_SKIP, CALLBACK_CANCEL,
    CALLBACK_EDIT_SLEEP, CALLBACK_EDIT_ENERGY_MORNING, CALLBACK_EDIT_ENERGY_EVENING,
    CALLBACK_EDIT_STRESS, CALLBACK_EDIT_STEPS, CALLBACK_EDIT_WORKOUT,
    CALLBACK_ANALYTICS_DAILY, CALLBACK_ANALYTICS_WEEKLY, CALLBACK_ANALYTICS_TRENDS,
    SLEEP_HOURS_QUICK, ENERGY_STRESS_QUICK, STEPS_QUICK,
    WORKOUT_TYPES, WORKOUT_DURATIONS_QUICK, HUNGER_QUICK, DIGESTION_TYPES,
)


def get_metrics_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню метрик."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Заполнить за сегодня", callback_data=CALLBACK_METRICS_TODAY)],
        [InlineKeyboardButton("✏️ Редактировать метрики", callback_data=CALLBACK_METRICS_EDIT)],
        [InlineKeyboardButton("📊 Аналитика", callback_data=CALLBACK_METRICS_ANALYTICS)],  # НОВАЯ КНОПКА
        [InlineKeyboardButton("📜 История метрик", callback_data=CALLBACK_METRICS_HISTORY)],
        [InlineKeyboardButton("← Назад в дневник", callback_data=CALLBACK_METRICS_BACK_TO_DIARY)],
    ])


def get_analytics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа аналитики."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Дневная аналитика", callback_data=CALLBACK_ANALYTICS_DAILY)],
        [InlineKeyboardButton("📊 Недельная аналитика", callback_data=CALLBACK_ANALYTICS_WEEKLY)],
        [InlineKeyboardButton("📈 Тренды и прогресс", callback_data=CALLBACK_ANALYTICS_TRENDS)],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_METRICS_BACK_TO_MENU)],
    ])


def get_metrics_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора метрики для заполнения/редактирования."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMOJI_SLEEP} Сон", callback_data=CALLBACK_SLEEP)],
        [InlineKeyboardButton(f"{EMOJI_ENERGY} Энергия", callback_data=CALLBACK_ENERGY)],
        [InlineKeyboardButton(f"{EMOJI_STRESS} Стресс", callback_data=CALLBACK_STRESS)],
        [InlineKeyboardButton(f"{EMOJI_STEPS} Шаги", callback_data=CALLBACK_STEPS)],
        [InlineKeyboardButton(f"{EMOJI_WORKOUT} Тренировка", callback_data=CALLBACK_WORKOUT)],
        [InlineKeyboardButton(f"{EMOJI_HUNGER} Голод", callback_data=CALLBACK_HUNGER)],
        [InlineKeyboardButton(f"{EMOJI_DIGESTION} Пищеварение", callback_data=CALLBACK_DIGESTION)],
        [InlineKeyboardButton(f"{EMOJI_CYCLE} Женский цикл", callback_data=CALLBACK_CYCLE)],
        [InlineKeyboardButton("✅ Завершить", callback_data=CALLBACK_CONFIRM_ALL)],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_METRICS_BACK_TO_MENU)],
    ])


def get_sleep_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода длительности сна."""
    buttons = []
    row = []
    for hours in SLEEP_HOURS_QUICK:
        row.append(InlineKeyboardButton(f"{hours}ч", callback_data=f"sleep_{hours}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="sleep_custom")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_sleep_quality_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки качества сна."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 — Очень плохо", callback_data="quality_1")],
        [InlineKeyboardButton("⭐⭐ 2 — Плохо", callback_data="quality_2")],
        [InlineKeyboardButton("⭐⭐⭐ 3 — Нормально", callback_data="quality_3")],
        [InlineKeyboardButton("⭐⭐⭐⭐ 4 — Хорошо", callback_data="quality_4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ 5 — Отлично", callback_data="quality_5")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_edit")],
    ])


def get_awakenings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора количества пробуждений."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("0 раз", callback_data="awakenings_0")],
        [InlineKeyboardButton("1 раз", callback_data="awakenings_1")],
        [InlineKeyboardButton("2 раза", callback_data="awakenings_2")],
        [InlineKeyboardButton("3+ раза", callback_data="awakenings_3")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_edit")],
    ])


def get_energy_stress_keyboard(metric_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для оценки энергии или стресса."""
    buttons = []
    row = []
    for value in ENERGY_STRESS_QUICK:
        row.append(InlineKeyboardButton(str(value), callback_data=f"{metric_type}_{value}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_steps_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора количества шагов."""
    buttons = []
    row = []
    for steps in STEPS_QUICK:
        row.append(InlineKeyboardButton(f"{steps}", callback_data=f"steps_{steps}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="steps_custom")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_hours_on_feet_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора часов на ногах."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1-2 часа", callback_data="feet_1")],
        [InlineKeyboardButton("3-4 часа", callback_data="feet_3")],
        [InlineKeyboardButton("5-6 часов", callback_data="feet_5")],
        [InlineKeyboardButton("7-8 часов", callback_data="feet_7")],
        [InlineKeyboardButton("9+ часов", callback_data="feet_9")],
        [InlineKeyboardButton("✏️ Свой вариант", callback_data="feet_custom")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_edit")],
    ])


def get_workout_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа тренировки."""
    buttons = []
    for value, label in WORKOUT_TYPES:
        buttons.append([InlineKeyboardButton(label, callback_data=f"workout_type_{value}")])
    buttons.append([InlineKeyboardButton("🚫 Нет тренировки", callback_data="workout_type_none")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_workout_duration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора длительности тренировки."""
    buttons = []
    row = []
    for duration in WORKOUT_DURATIONS_QUICK:
        row.append(InlineKeyboardButton(f"{duration}мин", callback_data=f"workout_duration_{duration}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="duration_custom")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_workout_intensity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки интенсивности тренировки (RPE)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1-2 — Очень легко", callback_data="intensity_1")],
        [InlineKeyboardButton("3-4 — Легко", callback_data="intensity_3")],
        [InlineKeyboardButton("5-6 — Умеренно", callback_data="intensity_5")],
        [InlineKeyboardButton("7-8 — Тяжело", callback_data="intensity_7")],
        [InlineKeyboardButton("9-10 — Очень тяжело", callback_data="intensity_9")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_edit")],
    ])


def get_hunger_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки голода."""
    buttons = []
    row = []
    for value in HUNGER_QUICK:
        row.append(InlineKeyboardButton(str(value), callback_data=f"hunger_{value}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_digestion_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа стула по Бристольской шкале."""
    buttons = []
    for value, label in DIGESTION_TYPES:
        buttons.append([InlineKeyboardButton(label, callback_data=f"digestion_{value}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_cycle_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода дня цикла."""
    buttons = []
    row = []
    for day in [1, 5, 10, 14, 21, 28, 35]:
        row.append(InlineKeyboardButton(str(day), callback_data=f"cycle_{day}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой день", callback_data="cycle_custom")])
    buttons.append([InlineKeyboardButton("🚫 Не в цикле / не заполнять", callback_data="cycle_none")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_edit")])
    return InlineKeyboardMarkup(buttons)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения всех метрик."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Сохранить всё", callback_data=CALLBACK_CONFIRM_ALL)],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=CALLBACK_METRICS_EDIT)],
        [InlineKeyboardButton("← Отмена", callback_data=CALLBACK_METRICS_BACK_TO_DIARY)],
    ])


def get_edit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора метрики для редактирования."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😴 Сон", callback_data=CALLBACK_EDIT_SLEEP)],
        [InlineKeyboardButton("⚡ Энергия (утро)", callback_data=CALLBACK_EDIT_ENERGY_MORNING)],
        [InlineKeyboardButton("⚡ Энергия (вечер)", callback_data=CALLBACK_EDIT_ENERGY_EVENING)],
        [InlineKeyboardButton("😰 Стресс", callback_data=CALLBACK_EDIT_STRESS)],
        [InlineKeyboardButton("👣 Шаги", callback_data=CALLBACK_EDIT_STEPS)],
        [InlineKeyboardButton("💪 Тренировка", callback_data=CALLBACK_EDIT_WORKOUT)],
        [InlineKeyboardButton("✅ Завершить редактирование", callback_data=CALLBACK_CONFIRM_ALL)],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_METRICS_BACK_TO_MENU)],
    ])


def get_back_keyboard(callback_data: str = CALLBACK_METRICS_BACK_TO_MENU) -> InlineKeyboardMarkup:
    """Универсальная кнопка Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад", callback_data=callback_data)]
    ])


# Эмодзи для констант (чтобы были доступны)
EMOJI_SLEEP = "😴"
EMOJI_ENERGY = "⚡"
EMOJI_STRESS = "😰"
EMOJI_STEPS = "👣"
EMOJI_WORKOUT = "💪"
EMOJI_HUNGER = "🍽️"
EMOJI_DIGESTION = "🚽"
EMOJI_CYCLE = "🌸"