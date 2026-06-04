# handlers/start/utils.py
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional


def format_greeting(first_name: Optional[str] = None) -> str:
    """Форматирует приветствие в зависимости от времени суток."""
    now = datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        greeting = "Доброе утро"
    elif 12 <= hour < 18:
        greeting = "Добрый день"
    elif 18 <= hour < 23:
        greeting = "Добрый вечер"
    else:
        greeting = "Доброй ночи"

    name = first_name or "друг"
    
    return f"{greeting}, {name}! 🥑"


def get_weekday_name() -> str:
    """Возвращает название дня недели на русском."""
    weekdays = {
        0: "понедельник",
        1: "вторник", 
        2: "среда",
        3: "четверг",
        4: "пятница",
        5: "суббота",
        6: "воскресенье"
    }
    now = datetime.now()
    return weekdays[now.weekday()]


def get_month_name() -> str:
    """Возвращает название месяца на русском."""
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    now = datetime.now()
    return months[now.month]


def format_progress_bar(current: float, total: float, length: int = 10) -> str:
    """Форматирует прогресс-бар."""
    if total <= 0:
        return "▱" * length
    ratio = min(1.0, current / total)
    filled = int(ratio * length)
    return "▰" * filled + "▱" * (length - filled)


def format_diary_compact(
    daily_kcal: int,
    current_kcal: int,
    protein_goal: int,
    current_protein: float,
    fat_goal: int,
    current_fat: float,
    carbs_goal: int,
    current_carbs: float,
    water_current_ml: int,
    water_goal_ml: int,
) -> str:
    """Компактный формат дневника с водой в миллилитрах."""
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

    kcal_percent = int((current_kcal / daily_kcal) * 100) if daily_kcal > 0 else 0
    kcal_bar = format_progress_bar(current_kcal, daily_kcal)
    
    water_bar = format_progress_bar(water_current_ml, water_goal_ml, length=8)

    return (
        f"📅 <b>{date_str}</b>\n\n"
        f"🔥 <b>{current_kcal} / {daily_kcal} ккал</b>  ·  {kcal_percent}%\n"
        f"{kcal_bar}\n\n"
        f"🍗 {current_protein:.0f}/{protein_goal}г  ·  "
        f"🥑 {current_fat:.0f}/{fat_goal}г  ·  "
        f"🍚 {current_carbs:.0f}/{carbs_goal}г\n\n"
        f"💧 {water_current_ml} / {water_goal_ml} мл\n"
        f"{water_bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )


def get_main_diary_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура дневника."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍽️ Еда", callback_data="food_select_method"),
            InlineKeyboardButton("💧 Вода", callback_data="water_add"),
            InlineKeyboardButton("⋯", callback_data="diary_more"),
        ],
    ])