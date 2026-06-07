"""
Клавиатуры для модуля сбора метрик.
"""
from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .constants import (
    CALLBACK_METRICS_TODAY, CALLBACK_METRICS_EDIT, CALLBACK_METRICS_HISTORY,
    CALLBACK_METRICS_ANALYTICS, CALLBACK_METRICS_BACK_TO_DIARY, CALLBACK_METRICS_BACK_TO_MENU,
    CALLBACK_CONFIRM_ALL, CALLBACK_CANCEL,
    CALLBACK_EDIT_SLEEP, CALLBACK_EDIT_ENERGY_MORNING, CALLBACK_EDIT_ENERGY_EVENING,
    CALLBACK_EDIT_STRESS, CALLBACK_EDIT_STEPS, CALLBACK_EDIT_WORKOUT,
    CALLBACK_ANALYTICS_DAILY, CALLBACK_ANALYTICS_WEEKLY, CALLBACK_ANALYTICS_TRENDS,
    CALLBACK_ANALYTICS_PATTERNS, CALLBACK_ANALYTICS_FORECAST,
    CALLBACK_ANALYTICS_BEST_DAY, CALLBACK_ANALYTICS_STATES,
    CALLBACK_BACK_TO_EDIT, CALLBACK_BACK_TO_MAIN, CALLBACK_BACK_TO_WORKOUT_TYPE,
    SLEEP_HOURS_QUICK, ENERGY_STRESS_QUICK, STEPS_QUICK,
    WORKOUT_TYPES, WORKOUT_DURATIONS_QUICK,
)

def get_metrics_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Заполнить за сегодня", callback_data=CALLBACK_METRICS_TODAY)],
        [InlineKeyboardButton("✏️ Редактировать метрики", callback_data=CALLBACK_METRICS_EDIT)],
        [InlineKeyboardButton("📊 Аналитика", callback_data=CALLBACK_METRICS_ANALYTICS)],
        [InlineKeyboardButton("📜 История метрик", callback_data=CALLBACK_METRICS_HISTORY)],
        [InlineKeyboardButton("← Назад в дневник", callback_data=CALLBACK_METRICS_BACK_TO_DIARY)],
    ])

def get_analytics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 За день", callback_data=CALLBACK_ANALYTICS_DAILY),
         InlineKeyboardButton("📊 За неделю", callback_data=CALLBACK_ANALYTICS_WEEKLY)],
        [InlineKeyboardButton("📈 Тренды", callback_data=CALLBACK_ANALYTICS_TRENDS),
         InlineKeyboardButton("🔍 Паттерны", callback_data=CALLBACK_ANALYTICS_PATTERNS)],
        [InlineKeyboardButton("🔮 Прогноз", callback_data=CALLBACK_ANALYTICS_FORECAST),
         InlineKeyboardButton("🏆 Лучший день", callback_data=CALLBACK_ANALYTICS_BEST_DAY)],
        [InlineKeyboardButton("🧬 Состояния", callback_data=CALLBACK_ANALYTICS_STATES)],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_METRICS_BACK_TO_MENU)],
    ])

def get_history_keyboard(dates: list) -> InlineKeyboardMarkup:
    buttons = []
    for d in dates[:15]:  # Показываем максимум 15 последних дней
        buttons.append([InlineKeyboardButton(
            f"📅 {d.strftime('%d.%m.%Y')}", 
            callback_data=f"history_date_{d.isoformat()}"
        )])
    buttons.append([InlineKeyboardButton("← Назад", callback_data=CALLBACK_METRICS_BACK_TO_MENU)])
    return InlineKeyboardMarkup(buttons)

def get_sleep_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for hours in SLEEP_HOURS_QUICK:
        row.append(InlineKeyboardButton(f"{hours}ч", callback_data=f"sleep_{hours}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="sleep_custom")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)])
    return InlineKeyboardMarkup(buttons)

def get_sleep_quality_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 — Очень плохо", callback_data="quality_1")],
        [InlineKeyboardButton("⭐⭐ 2 — Плохо", callback_data="quality_2")],
        [InlineKeyboardButton("⭐⭐⭐ 3 — Нормально", callback_data="quality_3")],
        [InlineKeyboardButton("⭐⭐⭐⭐ 4 — Хорошо", callback_data="quality_4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ 5 — Отлично", callback_data="quality_5")],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)],
    ])

def get_awakenings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("0 раз", callback_data="awakenings_0")],
        [InlineKeyboardButton("1 раз", callback_data="awakenings_1")],
        [InlineKeyboardButton("2 раза", callback_data="awakenings_2")],
        [InlineKeyboardButton("3+ раза", callback_data="awakenings_3")],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)],
    ])

def get_energy_stress_keyboard(prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for value in ENERGY_STRESS_QUICK:
        row.append(InlineKeyboardButton(str(value), callback_data=f"{prefix}_{value}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)])
    return InlineKeyboardMarkup(buttons)

def get_steps_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for steps in STEPS_QUICK:
        row.append(InlineKeyboardButton(str(steps), callback_data=f"steps_{steps}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="steps_custom")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)])
    return InlineKeyboardMarkup(buttons)

def get_hours_on_feet_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1-2 часа", callback_data="feet_1.5"), InlineKeyboardButton("3-4 часа", callback_data="feet_3.5")],
        [InlineKeyboardButton("5-6 часов", callback_data="feet_5.5"), InlineKeyboardButton("7-8 часов", callback_data="feet_7.5")],
        [InlineKeyboardButton("9+ часов", callback_data="feet_9"), InlineKeyboardButton("✏️ Свой", callback_data="feet_custom")],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)],
    ])

def get_workout_type_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for value, label in WORKOUT_TYPES:
        buttons.append([InlineKeyboardButton(label, callback_data=f"workout_type_{value}")])
    buttons.append([InlineKeyboardButton("🚫 Нет тренировки", callback_data="workout_type_none")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)])
    return InlineKeyboardMarkup(buttons)

def get_workout_duration_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for duration in WORKOUT_DURATIONS_QUICK:
        row.append(InlineKeyboardButton(f"{duration}мин", callback_data=f"workout_duration_{duration}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой вариант", callback_data="duration_custom")])
    buttons.append([InlineKeyboardButton("← Назад к типу", callback_data=CALLBACK_BACK_TO_WORKOUT_TYPE)])
    return InlineKeyboardMarkup(buttons)

def get_workout_intensity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1-2 (очень легко)", callback_data="intensity_1"), InlineKeyboardButton("3-4 (легко)", callback_data="intensity_3")],
        [InlineKeyboardButton("5-6 (умеренно)", callback_data="intensity_5"), InlineKeyboardButton("7-8 (тяжело)", callback_data="intensity_7")],
        [InlineKeyboardButton("9-10 (очень тяжело)", callback_data="intensity_9")],
        [InlineKeyboardButton("← Назад", callback_data=CALLBACK_BACK_TO_EDIT)],
    ])

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Сохранить всё", callback_data=CALLBACK_CONFIRM_ALL)],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=CALLBACK_METRICS_EDIT)],
        [InlineKeyboardButton("❌ Отмена", callback_data=CALLBACK_CANCEL)],
    ])

def get_edit_keyboard() -> InlineKeyboardMarkup:
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
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data=callback_data)]])