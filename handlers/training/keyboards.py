"""
Клавиатуры для модуля тренировок.
🎯 Минималистичный Apple-like UX.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Dict, List, Any
from .constants import (
    MUSCLE_GROUPS, DIFFICULTY_LEVELS, GENERAL_TIPS,
    CALLBACK_BACK_TO_DIARY, CALLBACK_MAIN_MENU,
    CALLBACK_EXERCISES_MENU, CALLBACK_QUICK_WORKOUT,
    CALLBACK_MUSCLE_PREFIX, CALLBACK_GENERAL_TIPS,
    CALLBACK_EXERCISE_PREFIX, CALLBACK_EXERCISE_BACK,
    CALLBACK_DETAIL_TECHNIQUE, CALLBACK_DETAIL_SCIENCE,
    CALLBACK_DETAIL_PROGRAM, CALLBACK_DETAIL_PROGRESSION,
    CALLBACK_DETAIL_CONTRA,
    CALLBACK_START_QUICK, CALLBACK_WORKOUT_DONE,
    CALLBACK_WORKOUT_SKIP, CALLBACK_WORKOUT_CANCEL,
)
from .exercises import EXERCISES, get_exercises_by_group


def get_main_training_keyboard() -> InlineKeyboardMarkup:
    """Главное меню модуля тренировок."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Упражнения и советы", callback_data=CALLBACK_EXERCISES_MENU)],
        [InlineKeyboardButton("⚡ Быстрая тренировка", callback_data=CALLBACK_QUICK_WORKOUT)],
        [InlineKeyboardButton("📔 ← В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])


def get_exercises_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела 'Упражнения и советы'."""
    buttons = []
    
    # Группы мышц (по 2 в ряд)
    muscle_list = list(MUSCLE_GROUPS.values())
    for i in range(0, len(muscle_list), 2):
        row = []
        for group in muscle_list[i:i+2]:
            row.append(InlineKeyboardButton(
                f"{group['emoji']} {group['name']}",
                callback_data=group["callback"]
            ))
        buttons.append(row)
    
    # Общие советы
    buttons.append([InlineKeyboardButton(" ", callback_data="noop")])
    buttons.append([InlineKeyboardButton(
        "💡 Общие советы",
        callback_data=CALLBACK_GENERAL_TIPS
    )])
    
    # Назад
    buttons.append([InlineKeyboardButton(" ", callback_data="noop")])
    buttons.append([InlineKeyboardButton("← В главное меню", callback_data=CALLBACK_MAIN_MENU)])
    
    return InlineKeyboardMarkup(buttons)


def get_muscle_group_keyboard(muscle_group_id: str) -> InlineKeyboardMarkup:
    """Список упражнений в группе мышц."""
    exercises = get_exercises_by_group(muscle_group_id)
    buttons = []
    
    # Сортируем по сложности
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    exercises_sorted = sorted(exercises, key=lambda x: order.get(x["difficulty"], 1))
    
    for ex in exercises_sorted:
        diff = DIFFICULTY_LEVELS[ex["difficulty"]]
        button_text = f"{diff['emoji']} {ex['name']}"
        buttons.append([
            InlineKeyboardButton(button_text, callback_data=f"{CALLBACK_EXERCISE_PREFIX}{ex['id']}")
        ])
    
    buttons.append([InlineKeyboardButton(" ", callback_data="noop")])
    buttons.append([InlineKeyboardButton("← К группам мышц", callback_data=CALLBACK_EXERCISES_MENU)])
    
    return InlineKeyboardMarkup(buttons)


def get_exercise_card_keyboard(exercise_id: str) -> InlineKeyboardMarkup:
    """Карточка упражнения с навигацией по разделам."""
    buttons = [
        [InlineKeyboardButton("💪 Программа тренировок", callback_data=f"{CALLBACK_DETAIL_PROGRAM}{exercise_id}")],
        [InlineKeyboardButton("📈 Путь прогрессии", callback_data=f"{CALLBACK_DETAIL_PROGRESSION}{exercise_id}")],
        [InlineKeyboardButton("🔬 Научное обоснование", callback_data=f"{CALLBACK_DETAIL_SCIENCE}{exercise_id}")],
        [InlineKeyboardButton("⚠️ Противопоказания", callback_data=f"{CALLBACK_DETAIL_CONTRA}{exercise_id}")],
        [InlineKeyboardButton(" ", callback_data="noop")],
        [InlineKeyboardButton("← К списку упражнений", callback_data=CALLBACK_EXERCISE_BACK)],
    ]
    return InlineKeyboardMarkup(buttons)


def get_exercise_detail_keyboard(exercise_id: str, section: str) -> InlineKeyboardMarkup:
    """Навигация между разделами упражнения."""
    exercise = EXERCISES.get(exercise_id, {})
    muscle_group = exercise.get("muscle_group", "push")
    back_callback = f"{CALLBACK_MUSCLE_PREFIX}{muscle_group}"
    
    # Определяем навигацию в зависимости от текущего раздела
    buttons = []
    
    if section == "technique":
        buttons.append([InlineKeyboardButton("💪 Программа →", callback_data=f"{CALLBACK_DETAIL_PROGRAM}{exercise_id}")])
    elif section == "program":
        buttons.append([InlineKeyboardButton("← Техника", callback_data=f"{CALLBACK_EXERCISE_PREFIX}{exercise_id}")])
        buttons.append([InlineKeyboardButton("📈 Прогрессии →", callback_data=f"{CALLBACK_DETAIL_PROGRESSION}{exercise_id}")])
    elif section == "progression":
        buttons.append([InlineKeyboardButton("← Программа", callback_data=f"{CALLBACK_DETAIL_PROGRAM}{exercise_id}")])
        buttons.append([InlineKeyboardButton("🔬 Наука →", callback_data=f"{CALLBACK_DETAIL_SCIENCE}{exercise_id}")])
    elif section == "science":
        buttons.append([InlineKeyboardButton("← Прогрессии", callback_data=f"{CALLBACK_DETAIL_PROGRESSION}{exercise_id}")])
        buttons.append([InlineKeyboardButton("⚠️ Противопоказания →", callback_data=f"{CALLBACK_DETAIL_CONTRA}{exercise_id}")])
    elif section == "contra":
        buttons.append([InlineKeyboardButton("← Наука", callback_data=f"{CALLBACK_DETAIL_SCIENCE}{exercise_id}")])
    
    buttons.append([InlineKeyboardButton(" ", callback_data="noop")])
    buttons.append([InlineKeyboardButton("↩️ К карточке", callback_data=f"{CALLBACK_EXERCISE_PREFIX}{exercise_id}")])
    buttons.append([InlineKeyboardButton("← К списку", callback_data=back_callback)])
    
    return InlineKeyboardMarkup(buttons)


def get_general_tips_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура со списком общих советов."""
    buttons = []
    
    for tip_id, tip in GENERAL_TIPS.items():
        buttons.append([
            InlineKeyboardButton(
                f"{tip['emoji']} {tip['title']}",
                callback_data=f"training_tip_{tip_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(" ", callback_data="noop")])
    buttons.append([InlineKeyboardButton("← К упражнениям", callback_data=CALLBACK_EXERCISES_MENU)])
    buttons.append([InlineKeyboardButton("← В главное меню", callback_data=CALLBACK_MAIN_MENU)])
    
    return InlineKeyboardMarkup(buttons)


def get_general_tip_detail_keyboard(tip_id: str) -> InlineKeyboardMarkup:
    """Навигация внутри совета."""
    # Находим предыдущий и следующий совет
    tip_ids = list(GENERAL_TIPS.keys())
    current_idx = tip_ids.index(tip_id) if tip_id in tip_ids else 0
    
    buttons = []
    nav_row = []
    
    if current_idx > 0:
        prev_id = tip_ids[current_idx - 1]
        nav_row.append(InlineKeyboardButton("← Пред.", callback_data=f"training_tip_{prev_id}"))
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data="noop"))
    
    nav_row.append(InlineKeyboardButton(f"· {current_idx + 1}/{len(tip_ids)} ·", callback_data="noop"))
    
    if current_idx < len(tip_ids) - 1:
        next_id = tip_ids[current_idx + 1]
        nav_row.append(InlineKeyboardButton("След. →", callback_data=f"training_tip_{next_id}"))
    else:
        nav_row.append(InlineKeyboardButton("·", callback_data="noop"))
    
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("← К списку советов", callback_data=CALLBACK_GENERAL_TIPS)])
    buttons.append([InlineKeyboardButton("← В главное меню", callback_data=CALLBACK_MAIN_MENU)])
    
    return InlineKeyboardMarkup(buttons)


def get_quick_workout_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура перед началом быстрой тренировки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Начать тренировку", callback_data=CALLBACK_START_QUICK)],
        [InlineKeyboardButton(" ", callback_data="noop")],
        [InlineKeyboardButton("← В главное меню", callback_data=CALLBACK_MAIN_MENU)],
    ])


def get_workout_session_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура во время активной тренировки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Завершить тренировку", callback_data=CALLBACK_WORKOUT_DONE)],
        [InlineKeyboardButton("❌ Отменить", callback_data=CALLBACK_WORKOUT_CANCEL)],
    ])


def get_workout_complete_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после завершения тренировки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ Ещё тренировку", callback_data=CALLBACK_QUICK_WORKOUT)],
        [InlineKeyboardButton("📚 Упражнения", callback_data=CALLBACK_EXERCISES_MENU)],
        [InlineKeyboardButton("📔 В дневник", callback_data=CALLBACK_BACK_TO_DIARY)],
    ])