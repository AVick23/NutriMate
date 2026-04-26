# handlers/add_food/utils.py
from typing import Optional, Tuple
from telegram import InlineKeyboardMarkup


def parse_food_text(text: str) -> Tuple[str, Optional[float]]:
    """
    Парсит текст вида "омлет 200г" или "банан".
    Возвращает (название, вес) или (текст, None) если вес не указан.
    """
    import re

    text = text.strip()

    # Ищем вес в конце строки
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:г|g|грамм?)$", text, re.IGNORECASE)
    if weight_match:
        weight = float(weight_match.group(1))
        # Убираем вес из названия
        name = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:г|g|грамм?)$", "", text, flags=re.IGNORECASE).strip()
        return name, weight

    return text, None


def format_progress_bar(current: float, total: float, length: int = 10) -> str:
    """
    Форматирует прогресс-бар из эмодзи.
    """
    if total == 0:
        return "▱" * length

    ratio = current / total
    filled = int(ratio * length)
    filled = min(filled, length)

    return "▰" * filled + "▱" * (length - filled)


def format_diary_message(
    daily_kcal: int,
    current_kcal: int,
    protein_goal: int,
    current_protein: float,
    fat_goal: int,
    current_fat: float,
    carbs_goal: int,
    current_carbs: float,
    water_current: int,
    water_goal: int = 8
) -> str:
    """
    Форматирует сообщение дневника с HTML-разметкой.
    """
    from datetime import datetime

    # Русские названия месяцев и дней недели
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    weekdays = {
        0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
        4: "пятница", 5: "суббота", 6: "воскресенье"
    }

    now = datetime.now()
    date_str = f"{weekdays[now.weekday()]}, {now.day} {months[now.month]}"

    kcal_bar = format_progress_bar(current_kcal, daily_kcal)
    kcal_percent = int((current_kcal / daily_kcal) * 100) if daily_kcal > 0 else 0

    protein_bar = format_progress_bar(current_protein, protein_goal)
    protein_percent = int((current_protein / protein_goal) * 100) if protein_goal > 0 else 0

    fat_bar = format_progress_bar(current_fat, fat_goal)
    fat_percent = int((current_fat / fat_goal) * 100) if fat_goal > 0 else 0

    carbs_bar = format_progress_bar(current_carbs, carbs_goal)
    carbs_percent = int((current_carbs / carbs_goal) * 100) if carbs_goal > 0 else 0

    water_bar = format_progress_bar(water_current, water_goal, length=8)
    water_percent = int((water_current / water_goal) * 100) if water_goal > 0 else 0

    text = f"""📅 <b>{date_str}</b>

─────────────────
🔥 <b>Калории</b>
<b>{current_kcal} / {daily_kcal} ккал</b>
{kcal_bar} <b>{kcal_percent}%</b>

🍗 <b>Белки</b>
<b>{current_protein:.0f} / {protein_goal} г</b>
{protein_bar} <b>{protein_percent}%</b>

🥑 <b>Жиры</b>
<b>{current_fat:.0f} / {fat_goal} г</b>
{fat_bar} <b>{fat_percent}%</b>

🍚 <b>Углеводы</b>
<b>{current_carbs:.0f} / {carbs_goal} г</b>
{carbs_bar} <b>{carbs_percent}%</b>

💧 <b>Вода</b>
<b>{water_current} / {water_goal} стаканов</b>
{water_bar} <b>{water_percent}%</b>
─────────────────"""

    return text


def get_main_diary_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура дневника."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽️ Добавить еду", callback_data="food_select_method")],  # <-- Изменить здесь
        [InlineKeyboardButton("🏋️ Записать тренировку", callback_data="training_add")],
        [
            InlineKeyboardButton("⚖️ Записать вес", callback_data="weight_add"),
            InlineKeyboardButton("💧 + Стакан воды", callback_data="water_add")
        ],
        [
            InlineKeyboardButton("📊 Прогресс", callback_data="progress_show"),
            InlineKeyboardButton("⭐️ Избранное", callback_data="favorites_show")
        ],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_show")],
    ])