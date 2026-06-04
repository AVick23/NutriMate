# handlers/water/utils.py
from .constants import EMOJI_WATER, EMOJI_WATER_FULL, EMOJI_WATER_EXCESS, DEFAULT_WATER_GOAL


def format_water_progress(current: int, goal: int = DEFAULT_WATER_GOAL, length: int = 8) -> str:
    """
    Форматирует прогресс-бар воды.
    Возвращает строку из ▰ и ▱.
    """
    if goal <= 0:
        return "▱" * length
    
    ratio = min(1.0, current / goal)
    filled = int(ratio * length)
    return "▰" * filled + "▱" * (length - filled)


def get_water_emoji(current: int, goal: int = DEFAULT_WATER_GOAL) -> str:
    """
    Возвращает эмодзи в зависимости от прогресса воды.
    """
    if current >= goal * 1.5:
        return EMOJI_WATER_EXCESS
    elif current >= goal:
        return EMOJI_WATER_FULL
    return EMOJI_WATER


def get_water_status_text(current: int, goal: int = DEFAULT_WATER_GOAL) -> str:
    """
    Возвращает текст статуса воды.
    """
    if current == 0:
        return "Начни день со стакана воды! 💧"
    elif current < goal:
        remaining = goal - current
        word = "стакан" if remaining == 1 else "стакана" if 2 <= remaining <= 4 else "стаканов"
        return f"Осталось {remaining} {word} до цели 💙"
    elif current == goal:
        return "Отлично! Дневная норма выполнена! 🎉💙"
    else:
        excess = current - goal
        word = "стакан" if excess == 1 else "стакана" if 2 <= excess <= 4 else "стаканов"
        return f"Ты выпил на {excess} {word} больше нормы! 💦"


def get_water_display(current: int, goal: int = DEFAULT_WATER_GOAL) -> str:
    """
    Возвращает строку для отображения воды в дневнике.
    """
    emoji = get_water_emoji(current, goal)
    return f"{emoji} {current} / {goal}"