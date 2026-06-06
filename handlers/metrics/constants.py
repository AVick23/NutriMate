"""
Состояния FSM и callback-данные для модуля сбора метрик.
Расширенная версия с поддержкой продвинутой аналитики.
"""

# ============================================================
# Состояния ConversationHandler
# ============================================================
(
    STATE_MAIN_MENU,           # 0: Главное меню метрик
    STATE_EDIT_MENU,           # 1: Меню редактирования метрик
    STATE_SLEEP_HOURS,         # 2: Длительность сна
    STATE_SLEEP_QUALITY,       # 3: Качество сна
    STATE_SLEEP_AWAKENINGS,    # 4: Пробуждения
    STATE_ENERGY_MORNING,      # 5: Энергия утром
    STATE_ENERGY_EVENING,      # 6: Энергия вечером
    STATE_STRESS,              # 7: Уровень стресса
    STATE_STEPS,               # 8: Количество шагов
    STATE_HOURS_ON_FEET,       # 9: Часы на ногах
    STATE_WORKOUT_TYPE,        # 10: Тип тренировки
    STATE_WORKOUT_DURATION,    # 11: Длительность тренировки
    STATE_WORKOUT_INTENSITY,   # 12: Интенсивность тренировки
    STATE_CONFIRM,             # 13: Подтверждение всех метрик
    STATE_ANALYTICS,           # 14: Меню аналитики
    STATE_PATTERNS,            # 15: Просмотр паттернов
    STATE_FORECAST,            # 16: Прогноз прогресса
    STATE_BEST_DAY,            # 17: Лучший день
    STATE_STATES,              # 18: Физиологические состояния
) = range(19)

# ============================================================
# Типы сессий
# ============================================================
SESSION_MORNING = "morning"
SESSION_EVENING = "evening"
SESSION_FULL = "full"
SESSION_EDIT = "edit"

# ============================================================
# Callback для главного меню
# ============================================================
CALLBACK_METRICS_SHOW = "metrics_show"
CALLBACK_METRICS_TODAY = "metrics_today"
CALLBACK_METRICS_EDIT = "metrics_edit"
CALLBACK_METRICS_HISTORY = "metrics_history"
CALLBACK_METRICS_ANALYTICS = "metrics_analytics"
CALLBACK_METRICS_BACK_TO_DIARY = "metrics_back_to_diary"
CALLBACK_METRICS_BACK_TO_MENU = "metrics_back_to_menu"

# ============================================================
# Callback для навигации
# ============================================================
CALLBACK_BACK_TO_EDIT = "back_to_edit"
CALLBACK_BACK_TO_MAIN = "back_to_main"
CALLBACK_BACK_TO_WORKOUT_TYPE = "back_to_workout_type"
CALLBACK_BACK_TO_ANALYTICS = "back_to_analytics"

# ============================================================
# Callback для редактирования
# ============================================================
CALLBACK_EDIT_SLEEP = "edit_sleep"
CALLBACK_EDIT_ENERGY_MORNING = "edit_energy_morning"
CALLBACK_EDIT_ENERGY_EVENING = "edit_energy_evening"
CALLBACK_EDIT_STRESS = "edit_stress"
CALLBACK_EDIT_STEPS = "edit_steps"
CALLBACK_EDIT_WORKOUT = "edit_workout"

# ============================================================
# Callback для аналитики (РАСШИРЕНО)
# ============================================================
CALLBACK_ANALYTICS_DAILY = "analytics_daily"
CALLBACK_ANALYTICS_WEEKLY = "analytics_weekly"
CALLBACK_ANALYTICS_TRENDS = "analytics_trends"
CALLBACK_ANALYTICS_PATTERNS = "analytics_patterns"
CALLBACK_ANALYTICS_FORECAST = "analytics_forecast"
CALLBACK_ANALYTICS_BEST_DAY = "analytics_best_day"
CALLBACK_ANALYTICS_STATES = "analytics_states"

# ============================================================
# Callback для подтверждения
# ============================================================
CALLBACK_CONFIRM_ALL = "metrics_confirm_all"
CALLBACK_CANCEL = "metrics_cancel"

# ============================================================
# Быстрые значения
# ============================================================
SLEEP_HOURS_QUICK = [6, 6.5, 7, 7.5, 8, 8.5, 9]
ENERGY_STRESS_QUICK = list(range(1, 11))
STEPS_QUICK = [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 12000, 15000]
WORKOUT_TYPES = [
    ("strength", "🏋️ Силовая"),
    ("cardio", "🏃 Кардио"),
    ("yoga", "🧘 Йога/растяжка"),
    ("walk", "🚶 Прогулка"),
    ("swim", "🏊 Плавание"),
]
WORKOUT_DURATIONS_QUICK = [15, 20, 25, 30, 40, 45, 50, 60, 75, 90]

# ============================================================
# Эмодзи
# ============================================================
EMOJI_SLEEP = "😴"
EMOJI_ENERGY = "⚡"
EMOJI_STRESS = "😰"
EMOJI_STEPS = "👣"
EMOJI_WORKOUT = "💪"