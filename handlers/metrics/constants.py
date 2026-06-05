"""
Состояния FSM и callback-данные для модуля сбора метрик.
"""

# ============ Состояния ConversationHandler ============
(
    STATE_MAIN_MENU,           # Главное меню метрик
    STATE_SLEEP_HOURS,         # Длительность сна
    STATE_SLEEP_QUALITY,       # Качество сна
    STATE_SLEEP_AWAKENINGS,    # Пробуждения
    STATE_ENERGY_MORNING,      # Энергия утром
    STATE_ENERGY_EVENING,      # Энергия вечером
    STATE_STRESS,              # Уровень стресса
    STATE_STEPS,               # Количество шагов
    STATE_HOURS_ON_FEET,       # Часы на ногах
    STATE_WORKOUT_TYPE,        # Тип тренировки
    STATE_WORKOUT_DURATION,    # Длительность тренировки
    STATE_WORKOUT_INTENSITY,   # Интенсивность тренировки
    STATE_HUNGER_BEFORE,       # Голод до еды (опционально)
    STATE_HUNGER_AFTER,        # Голод после еды (опционально)
    STATE_DIGESTION,           # Пищеварение (Бристоль)
    STATE_CYCLE_DAY,           # День цикла (для женщин)
    STATE_CONFIRM,             # Подтверждение всех метрик
    STATE_ANALYTICS,           # Просмотр аналитики
) = range(18)

# ============ Типы сессий ============
SESSION_MORNING = "morning"   # Утренний опрос (сон, энергия утром)
SESSION_EVENING = "evening"   # Вечерний опрос (энергия вечером, стресс, шаги, тренировки)

# ============ Callback для главного меню ============
CALLBACK_METRICS_SHOW = "metrics_show"
CALLBACK_METRICS_TODAY = "metrics_today"
CALLBACK_METRICS_EDIT = "metrics_edit"
CALLBACK_METRICS_HISTORY = "metrics_history"
CALLBACK_METRICS_ANALYTICS = "metrics_analytics"  # НОВЫЙ
CALLBACK_METRICS_BACK_TO_DIARY = "metrics_back_to_diary"
CALLBACK_METRICS_BACK_TO_MENU = "metrics_back_to_menu"

# ============ Callback для выбора действия ============
CALLBACK_SLEEP = "metrics_sleep"
CALLBACK_ENERGY = "metrics_energy"
CALLBACK_STRESS = "metrics_stress"
CALLBACK_STEPS = "metrics_steps"
CALLBACK_WORKOUT = "metrics_workout"
CALLBACK_HUNGER = "metrics_hunger"
CALLBACK_DIGESTION = "metrics_digestion"
CALLBACK_CYCLE = "metrics_cycle"

# ============ Callback для подтверждения ============
CALLBACK_CONFIRM_ALL = "metrics_confirm_all"
CALLBACK_SKIP = "metrics_skip"
CALLBACK_CANCEL = "metrics_cancel"

# ============ Callback для редактирования ============
CALLBACK_EDIT_SLEEP = "edit_sleep"
CALLBACK_EDIT_ENERGY_MORNING = "edit_energy_morning"
CALLBACK_EDIT_ENERGY_EVENING = "edit_energy_evening"
CALLBACK_EDIT_STRESS = "edit_stress"
CALLBACK_EDIT_STEPS = "edit_steps"
CALLBACK_EDIT_WORKOUT = "edit_workout"

# ============ Callback для аналитики ============
CALLBACK_ANALYTICS_DAILY = "analytics_daily"
CALLBACK_ANALYTICS_WEEKLY = "analytics_weekly"
CALLBACK_ANALYTICS_TRENDS = "analytics_trends"

# ============ Быстрые значения ============
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
HUNGER_QUICK = list(range(1, 11))
DIGESTION_TYPES = [
    (1, "🟤 Отдельные комки (запор)"),
    (2, "🟤 Колбасовидный, комковатый"),
    (3, "🟤 Колбасовидный с трещинами"),
    (4, "🟢 Гладкий, мягкий (идеал)"),
    (5, "🟡 Мягкие комочки с чёткими краями"),
    (6, "🟠 Кашицеобразный (диарея)"),
    (7, "🔴 Жидкий (диарея)"),
]

# ============ Эмодзи ============
EMOJI_SLEEP = "😴"
EMOJI_ENERGY = "⚡"
EMOJI_STRESS = "😰"
EMOJI_STEPS = "👣"
EMOJI_WORKOUT = "💪"
EMOJI_HUNGER = "🍽️"
EMOJI_DIGESTION = "🚽"
EMOJI_CYCLE = "🌸"