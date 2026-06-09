"""
Состояния FSM и callback-данные для модуля тренировок.
🎯 Научно обоснованная калистеника с Apple-like UX.
"""

# ============ Состояния ConversationHandler ============
(
    STATE_MAIN_MENU,           # Главное меню тренировок
    STATE_EXERCISES_MENU,      # Меню "Упражнения и советы"
    STATE_MUSCLE_GROUP,        # Список упражнений в группе мышц
    STATE_EXERCISE_CARD,       # Карточка упражнения
    STATE_EXERCISE_DETAIL,     # Детали упражнения (наука/программа/прогрессии)
    STATE_GENERAL_TIPS,       # Общие советы
    STATE_QUICK_WORKOUT,       # Описание быстрой тренировки
    STATE_WORKOUT_SESSION,     # Активная тренировочная сессия
) = range(8)

# ============ Callback: главное меню ============
CALLBACK_MAIN_MENU = "training_main"
CALLBACK_BACK_TO_DIARY = "training_back_to_diary"

# ============ Callback: режимы ============
CALLBACK_EXERCISES_MENU = "training_exercises"
CALLBACK_QUICK_WORKOUT = "training_quick"

# ============ Callback: группы мышц ============
CALLBACK_MUSCLE_PREFIX = "training_muscle_"
CALLBACK_MUSCLE_PUSH = "training_muscle_push"       # Толчок (грудь, трицепс, плечи)
CALLBACK_MUSCLE_PULL = "training_muscle_pull"       # Тяга (спина, бицепс)
CALLBACK_MUSCLE_SQUAT = "training_muscle_squat"     # Приседания (ноги, ягодицы)
CALLBACK_MUSCLE_CORE = "training_muscle_core"       # Кор (пресс, спина)
CALLBACK_MUSCLE_CARDIO = "training_muscle_cardio"   # Кардио
CALLBACK_GENERAL_TIPS = "training_general_tips"     # Общие советы

# ============ Callback: упражнения ============
CALLBACK_EXERCISE_PREFIX = "training_ex_"           # training_ex_{exercise_id}
CALLBACK_EXERCISE_BACK = "training_ex_back"

# ============ Callback: разделы упражнения ============
CALLBACK_DETAIL_TECHNIQUE = "training_detail_tech_"
CALLBACK_DETAIL_SCIENCE = "training_detail_sci_"
CALLBACK_DETAIL_PROGRAM = "training_detail_prog_"
CALLBACK_DETAIL_PROGRESSION = "training_detail_path_"
CALLBACK_DETAIL_CONTRA = "training_detail_contra_"

# ============ Callback: тренировочная сессия ============
CALLBACK_START_QUICK = "training_start_quick"
CALLBACK_WORKOUT_DONE = "training_workout_done"
CALLBACK_WORKOUT_SKIP = "training_workout_skip"
CALLBACK_WORKOUT_CANCEL = "training_workout_cancel"

# ============ Группы мышц (для отображения) ============
MUSCLE_GROUPS = {
    "push": {
        "id": "push",
        "emoji": "💪",
        "name": "Толчок",
        "description": "Грудь, трицепс, плечи",
        "callback": CALLBACK_MUSCLE_PUSH,
    },
    "pull": {
        "id": "pull",
        "emoji": "🦇",
        "name": "Тяга",
        "description": "Спина, бицепс, предплечья",
        "callback": CALLBACK_MUSCLE_PULL,
    },
    "squat": {
        "id": "squat",
        "emoji": "🦵",
        "name": "Приседания",
        "description": "Ноги, ягодицы, икры",
        "callback": CALLBACK_MUSCLE_SQUAT,
    },
    "core": {
        "id": "core",
        "emoji": "🧱",
        "name": "Кор",
        "description": "Пресс, косые, разгибатели спины",
        "callback": CALLBACK_MUSCLE_CORE,
    },
    "cardio": {
        "id": "cardio",
        "emoji": "❤️",
        "name": "Кардио",
        "description": "Выносливость, жиросжигание",
        "callback": CALLBACK_MUSCLE_CARDIO,
    },
}

# ============ Уровни сложности ============
DIFFICULTY_LEVELS = {
    "beginner": {"emoji": "🟢", "name": "Новичок"},
    "intermediate": {"emoji": "🟡", "name": "Средний"},
    "advanced": {"emoji": "🔴", "name": "Продвинутый"},
}

# ============ Цели тренировок ============
TRAINING_GOALS = {
    "strength": {
        "emoji": "💪",
        "name": "Сила",
        "description": "Мало повторений, долгий отдых",
        "sets": "4-5",
        "reps": "5-8",
        "rest": "2-3 мин",
    },
    "hypertrophy": {
        "emoji": "🔥",
        "name": "Мышечная масса",
        "description": "Средние повторения, умеренный отдых",
        "sets": "3-4",
        "reps": "8-15",
        "rest": "60-90 сек",
    },
    "endurance": {
        "emoji": "🏃",
        "name": "Выносливость",
        "description": "Много повторений, короткий отдых",
        "sets": "2-3",
        "reps": "15-25",
        "rest": "30-60 сек",
    },
}

# ============ 🎯 ОБЩИЕ СОВЕТЫ (перенесено из exercises.py) ============
GENERAL_TIPS = {
    "frequency": {
        "emoji": "📅",
        "title": "Частота тренировок",
        "content": (
            "🟢 <b>Новичкам:</b> 2-3 раза в неделю\n"
            "🟡 <b>Средний уровень:</b> 3-4 раза в неделю\n"
            "🔴 <b>Продвинутым:</b> 4-6 раз в неделю\n\n"
            "⚠️ Между тренировками одной группы мышц — "
            "<b>минимум 48 часов</b> для восстановления."
        ),
    },
    "rest": {
        "emoji": "⏱️",
        "title": "Отдых между подходами",
        "content": (
            "💪 <b>Сила:</b> 2-3 минуты\n"
            "🔥 <b>Мышечная масса:</b> 60-90 секунд\n"
            "🏃 <b>Выносливость:</b> 30-60 секунд\n\n"
            "💡 Чем тяжелее упражнение — тем дольше отдых."
        ),
    },
    "progression": {
        "emoji": "📈",
        "title": "Принцип прогрессии",
        "content": (
            "Главный секрет роста — <b>постепенное усложнение</b>.\n\n"
            "5 способов прогрессировать:\n"
            "1. ➕ Больше повторений\n"
            "2. ⏳ Медленнее негативная фаза (3-5 сек)\n"
            "3. 📐 Больше амплитуда\n"
            "4. 🔼 Сложнее вариация упражнения\n"
            "5. ⏱️ Меньше отдых между подходами\n\n"
            "⚠️ Простое увеличение повторений без изменения нагрузки быстро приводит к плато!"
        ),
    },
    "breathing": {
        "emoji": "💨",
        "title": "Правильное дыхание",
        "content": (
            "🌬️ <b>Вдох</b> — на расслаблении (опускание)\n"
            "💨 <b>Выдох</b> — на усилии (подъём)\n\n"
            "Примеры:\n"
            "• Отжимания: вдох вниз, выдох вверх\n"
            "• Приседания: вдох вниз, выдох вверх\n"
            "• Подтягивания: выдох вверх, вдох вниз\n\n"
            "❗ Никогда не задерживай дыхание!"
        ),
    },
    "nutrition": {
        "emoji": "🥗",
        "title": "Питание для результата",
        "content": (
            "🍗 <b>Белок:</b> 1.6-2.0 г на кг веса в день\n"
            "⏰ <b>После тренировки:</b> поесть в течение 1 часа\n"
            "💧 <b>Вода:</b> +500 мл в дни тренировок\n\n"
            "💡 Без правильного питания даже лучшие "
            "тренировки не дадут результата!"
        ),
    },
    "recovery": {
        "emoji": "😴",
        "title": "Восстановление",
        "content": (
            "😴 <b>Сон:</b> 7-9 часов (мышцы растут во сне!)\n"
            "🧘 <b>Стресс:</b> высокий стресс = плохое восстановление\n"
            "🚶 <b>Активность:</b> лёгкие прогулки в дни отдыха\n\n"
            "⚠️ Если чувствуешь сильную усталость — "
            "лучше пропустить тренировку, чем получить травму."
        ),
    },
    "safety": {
        "emoji": "⚠️",
        "title": "Безопасность",
        "content": (
            "❗ <b>Золотое правило:</b> боль = стоп\n\n"
            "Признаки, что нужно остановиться:\n"
            "• Острая боль в суставе\n"
            "• Головокружение\n"
            "• Тошнота\n"
            "• Сильная одышка\n\n"
            "💡 Мышечная усталость — нормально.\n"
            "Боль в суставе — НЕТ!"
        ),
    },
    "warmup": {
        "emoji": "🔥",
        "title": "Разминка и заминка",
        "content": (
            "🔥 <b>Разминка (5 мин):</b>\n"
            "• Суставная гимнастика\n"
            "• Лёгкое кардио (бег на месте)\n"
            "• Динамическая растяжка\n\n"
            "🧊 <b>Заминка (5 мин):</b>\n"
            "• Статическая растяжка\n"
            "• Глубокое дыхание\n"
            "• Лёгкая ходьба\n\n"
            "❗ Никогда не пропускай разминку!"
        ),
    },
}