"""
Утилиты для форматирования карточек упражнений и тренировок.
🎯 Научно обоснованный контент в красивом формате.
"""
from typing import Dict, List, Any, Optional
from .constants import MUSCLE_GROUPS, DIFFICULTY_LEVELS, TRAINING_GOALS, GENERAL_TIPS
from .exercises import EXERCISES, READY_WORKOUTS


def format_main_menu() -> str:
    """Главное меню модуля тренировок."""
    return (
        "🏋️  <b>Тренировки с собственным весом</b>\n\n"
        "<i>Научно обоснованная калистеника без оборудования. "
        "Все упражнения с правильной техникой, прогрессиями и "
        "медицинскими рекомендациями.</i>\n\n"
        "Что хочешь сделать?"
    )


def format_exercises_menu() -> str:
    """Меню раздела 'Упражнения и советы'."""
    text = "📚  <b>Упражнения и советы</b>\n\n"
    text += "Выбери группу мышц или изучи общие принципы:\n\n"
    text += "─────────────────\n"
    
    for group in MUSCLE_GROUPS.values():
        count = len([ex for ex in EXERCISES.values() if ex["muscle_group"] == group["id"]])
        text += f"{group['emoji']} <b>{group['name']}</b> — {count} упражнений\n"
        text += f"   <i>{group['description']}</i>\n\n"
    
    text += "─────────────────\n"
    text += f"💡 <b>Общие советы</b> — {len(GENERAL_TIPS)} разделов\n"
    text += "   <i>Частота, отдых, прогрессия, питание и др.</i>"
    
    return text


def format_muscle_group_exercises(muscle_group_id: str) -> str:
    """Форматирует список упражнений в группе мышц."""
    group = MUSCLE_GROUPS.get(muscle_group_id, {})
    exercises = [ex for ex in EXERCISES.values() if ex["muscle_group"] == muscle_group_id]
    
    text = f"{group.get('emoji', '💪')}  <b>{group.get('name', 'Упражнения')}</b>\n"
    text += f"<i>{group.get('description', '')}</i>\n\n"
    text += "─────────────────\n\n"
    
    # Сортируем по уровню сложности
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    exercises_sorted = sorted(exercises, key=lambda x: order.get(x["difficulty"], 1))
    
    for ex in exercises_sorted:
        diff = DIFFICULTY_LEVELS[ex["difficulty"]]
        text += f"{diff['emoji']} <b>{ex['name']}</b>\n"
        text += f"   🎯 {', '.join(ex['primary_muscles'][:2])}\n"
        text += f"   🔥 ~{ex['calories_per_min']} ккал/мин\n\n"
    
    text += "─────────────────\n"
    text += "<b>Легенда сложности:</b>\n"
    text += "🟢 Новичок · 🟡 Средний · 🔴 Продвинутый"
    
    return text


def format_exercise_card(exercise: Dict[str, Any]) -> str:
    """Форматирует карточку упражнения."""
    diff = DIFFICULTY_LEVELS[exercise["difficulty"]]
    group = MUSCLE_GROUPS.get(exercise["muscle_group"], {})
    
    text = f"{group.get('emoji', '💪')}  <b>{exercise['name']}</b>\n\n"
    
    text += f"<b>Уровень:</b> {diff['emoji']} {diff['name']}\n"
    text += f"<b>Основные мышцы:</b> {', '.join(exercise['primary_muscles'])}\n"
    if exercise.get("secondary_muscles"):
        text += f"<b>Вспомогательные:</b> {', '.join(exercise['secondary_muscles'])}\n"
    text += f"<b>Расход:</b> ~{exercise['calories_per_min']} ккал/мин\n\n"
    
    text += "─────────────────\n"
    text += "📖 <b>Техника выполнения:</b>\n"
    for i, step in enumerate(exercise["technique"], 1):
        text += f"{i}. {step}\n"
    
    text += "\n─────────────────\n"
    text += "Выбери раздел для подробной информации:"
    
    return text


def format_exercise_science(exercise: Dict[str, Any]) -> str:
    """Форматирует научное обоснование упражнения."""
    text = f"🔬  <b>Научное обоснование</b>\n"
    text += f"<i>{exercise['name']}</i>\n\n"
    text += "─────────────────\n\n"
    text += f"{exercise['science']}\n\n"
    text += "─────────────────\n"
    text += "<i>💡 Все рекомендации основаны на ЭМГ-исследованиях "
    "и мета-анализах спортивной науки (ACSM, NSCA).</i>"
    
    return text


def format_exercise_programs(exercise: Dict[str, Any]) -> str:
    """Форматирует программы тренировок для разных целей."""
    text = f"💪  <b>Программы тренировок</b>\n"
    text += f"<i>{exercise['name']}</i>\n\n"
    text += "─────────────────\n\n"
    
    for goal_id, program in exercise["programs"].items():
        goal = TRAINING_GOALS[goal_id]
        text += f"{goal['emoji']} <b>{goal['name']}</b>\n"
        text += f"   <i>{goal['description']}</i>\n"
        text += f"   ▸ Подходы: <b>{program['sets']}</b>\n"
        text += f"   ▸ Повторения: <b>{program['reps']}</b>\n"
        text += f"   ▸ Отдых: <b>{program['rest']}</b>\n\n"
    
    text += "─────────────────\n"
    text += "💡 <b>Совет:</b> начинай с 'Выносливости', "
    "затем переходи к 'Массе' и 'Силе'."
    
    return text


def format_exercise_progressions(exercise: Dict[str, Any]) -> str:
    """Форматирует прогрессии упражнения (путь от новичка к профи)."""
    text = f"📈  <b>Путь прогрессии</b>\n"
    text += f"<i>{exercise['name']}</i>\n\n"
    text += "─────────────────\n\n"
    
    for progression, description in exercise["progressions"]:
        text += f"{progression}\n"
        text += f"   <i>{description}</i>\n\n"
    
    text += "─────────────────\n"
    text += "💡 <b>Правило перехода:</b> переходи к следующему уровню "
    "только когда можешь выполнить <b>3 подхода с идеальной техникой</b> "
    "на текущем уровне."
    
    return text


def format_exercise_contraindications(exercise: Dict[str, Any]) -> str:
    """Форматирует противопоказания."""
    text = f"⚠️  <b>Противопоказания</b>\n"
    text += f"<i>{exercise['name']}</i>\n\n"
    text += "─────────────────\n\n"
    
    if exercise["contraindications"]:
        text += "❗ <b>Не выполняй это упражнение при:</b>\n\n"
        for contra in exercise["contraindications"]:
            text += f"▸ {contra}\n"
    else:
        text += "✅ У этого упражнения нет специфических противопоказаний.\n"
    
    text += "\n─────────────────\n"
    text += "💡 <b>Важно:</b> при появлении боли прекрати выполнение "
    "и проконсультируйся с врачом. Помни — <b>мышечная усталость "
    "это нормально, боль в суставе — НЕТ!</b>"
    
    return text


def format_general_tips_menu() -> str:
    """Меню общих советов."""
    text = "💡  <b>Общие советы</b>\n\n"
    text += "<i>Фундаментальные принципы тренировок, "
    "основанные на спортивной науке.</i>\n\n"
    text += "─────────────────\n\n"
    
    for tip_id, tip in GENERAL_TIPS.items():
        text += f"{tip['emoji']} <b>{tip['title']}</b>\n"
    
    text += "\n─────────────────\n"
    text += "Нажми на совет, чтобы узнать подробности."
    
    return text


def format_general_tip(tip_id: str) -> str:
    """Форматирует конкретный общий совет."""
    tip = GENERAL_TIPS.get(tip_id, {})
    
    text = f"{tip.get('emoji', '💡')}  <b>{tip.get('title', 'Совет')}</b>\n\n"
    text += "─────────────────\n\n"
    text += tip.get("content", "")
    
    return text


def format_quick_workout(workout: Dict[str, Any]) -> str:
    """Форматирует описание быстрой тренировки."""
    diff = DIFFICULTY_LEVELS.get(workout["level"], DIFFICULTY_LEVELS["beginner"])
    
    text = f"⚡  <b>{workout['name']}</b>\n\n"
    text += f"<i>{workout['description']}</i>\n\n"
    text += "─────────────────\n\n"
    
    text += f"⏱ <b>Длительность:</b> {workout['duration_min']} минут\n"
    text += f"{diff['emoji']} <b>Уровень:</b> {diff['name']}\n"
    text += f"🔥 <b>Расход:</b> ~{workout['total_calories']} ккал\n"
    text += f"📋 <b>Структура:</b> {workout['structure']}\n"
    text += f"▶️ <b>Работа:</b> {workout['work_time']} сек\n"
    text += f"⏸ <b>Отдых:</b> {workout['rest_time']} сек\n\n"
    
    text += "─────────────────\n\n"
    text += "<b>📋 Упражнения:</b>\n\n"
    
    for i, ex_data in enumerate(workout["exercises"], 1):
        text += f"{i}. <b>{ex_data['name']}</b>\n"
    
    text += "\n─────────────────\n\n"
    text += f"🔥 <b>Разминка:</b> {workout['warmup']}\n"
    text += f"🧊 <b>Заминка:</b> {workout['cooldown']}\n\n"
    text += "Готов начать?"
    
    return text


def format_workout_step(
    workout: Dict[str, Any],
    current_round: int,
    current_exercise: int,
    is_work_phase: bool,
    seconds_left: int
) -> str:
    """Форматирует текущий шаг тренировочной сессии."""
    total_rounds = int(workout["structure"].split()[0])
    ex_data = workout["exercises"][current_exercise]
    
    if is_work_phase:
        phase_text = "▶️ РАБОТА"
        phase_time = workout["work_time"]
    else:
        phase_text = "⏸ ОТДЫХ"
        phase_time = workout["rest_time"]
    
    text = f"🏁  <b>{workout['name']}</b>\n\n"
    text += f"Круг <b>{current_round}/{total_rounds}</b> · "
    text += f"Упражнение <b>{current_exercise + 1}/{len(workout['exercises'])}</b>\n\n"
    text += "─────────────────\n\n"
    text += f"<b>{phase_text}</b>\n"
    text += f"💪 <b>{ex_data['name']}</b>\n\n"
    text += f"⏱ Осталось: <b>{seconds_left} сек</b>\n"
    
    if is_work_phase:
        text += f"\n<i>Делай максимум повторений с правильной техникой!</i>"
    else:
        # Показываем следующее упражнение во время отдыха
        next_ex_idx = (current_exercise + 1) % len(workout["exercises"])
        next_ex = workout["exercises"][next_ex_idx]
        text += f"\n<i>Следующее: {next_ex['name']}</i>"
    
    return text


def format_workout_complete(workout: Dict[str, Any], duration_min: int) -> str:
    """Форматирует сообщение о завершении тренировки."""
    text = "🎉  <b>Тренировка завершена!</b>\n\n"
    text += f"📋 <b>{workout['name']}</b>\n\n"
    text += "─────────────────\n\n"
    text += f"⏱ <b>Длительность:</b> {duration_min} минут\n"
    text += f"🔥 <b>Сожжено:</b> ~{workout['total_calories']} ккал\n"
    text += f"💪 <b>Упражнений:</b> {len(workout['exercises'])}\n\n"
    text += "─────────────────\n\n"
    text += "🧊 Не забудь про заминку и растяжку!\n"
    text += "💧 Выпей 300-500 мл воды.\n"
    text += "🥗 Поешь в течение часа (белок + углеводы)."
    
    return text