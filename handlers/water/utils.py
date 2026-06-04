# handlers/water/utils.py
from .constants import EMOJI_WATER, EMOJI_WATER_FULL, EMOJI_WATER_EXCESS


def format_water_progress(current: int, goal: int, length: int = 8) -> str:
    """
    Форматирует прогресс-бар воды.
    Возвращает строку из ▰ и ▱.
    """
    if goal <= 0:
        return "▱" * length
    
    ratio = min(1.0, current / goal)
    filled = int(ratio * length)
    return "▰" * filled + "▱" * (length - filled)


def get_water_emoji(current: int, goal: int) -> str:
    """
    Возвращает эмодзи в зависимости от прогресса воды.
    """
    if current >= goal * 1.5:
        return EMOJI_WATER_EXCESS
    elif current >= goal:
        return EMOJI_WATER_FULL
    return EMOJI_WATER


def calculate_water_goal(weight_kg: float, gender: str) -> int:
    """
    Рассчитывает норму воды по формуле EFSA (Европейское агентство по безопасности пищевых продуктов).
    Мужчины: 35 мл × вес (кг)
    Женщины: 30 мл × вес (кг)
    Возвращает количество миллилитров.
    """
    if gender == "male":
        return int(weight_kg * 35)
    else:
        return int(weight_kg * 30)


def get_water_status_text(current: int, goal: int) -> str:
    """
    Возвращает текст статуса воды.
    goal — в миллилитрах.
    """
    if current == 0:
        return f"Начни день со стакана воды! 💧 (норма: {goal} мл)"
    elif current < goal:
        remaining_ml = goal - current
        remaining_glasses = remaining_ml // 250
        word = "стакан" if remaining_glasses == 1 else "стакана" if 2 <= remaining_glasses <= 4 else "стаканов"
        return f"Осталось {remaining_ml} мл ({remaining_glasses} {word}) до нормы 💙"
    elif current == goal:
        return f"Отлично! Дневная норма {goal} мл выполнена! 🎉💙"
    else:
        excess = current - goal
        excess_glasses = excess // 250
        word = "стакан" if excess_glasses == 1 else "стакана" if 2 <= excess_glasses <= 4 else "стаканов"
        return f"Ты выпил на {excess} мл ({excess_glasses} {word}) больше нормы! 💦"


def get_water_display(current: int, goal: int) -> str:
    """
    Возвращает строку для отображения воды в дневнике.
    """
    emoji = get_water_emoji(current, goal)
    return f"{emoji} {current} / {goal} мл"