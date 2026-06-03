# handlers/history_of_add/utils.py
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional
from calendar import monthcalendar, month_name


def format_date_ru(date_obj: date) -> str:
    """Форматирует дату на русском: '18 июня 2024, вторник'"""
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    weekdays = {
        0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
        4: "пятница", 5: "суббота", 6: "воскресенье"
    }
    
    return f"{date_obj.day} {months[date_obj.month]} {date_obj.year}, {weekdays[date_obj.weekday()]}"


def format_time(timestamp: str) -> str:
    """Извлекает время из timestamp: '2024-06-18 09:30:00' -> '09:30'"""
    try:
        dt = datetime.fromisoformat(timestamp.replace(' ', 'T'))
        return dt.strftime("%H:%M")
    except:
        return ""


def get_meal_icon(meal_type: str) -> str:
    """Возвращает иконку для типа приёма пищи."""
    icons = {
        "breakfast": "🥐",
        "lunch": "🍲",
        "dinner": "🍽️",
        "snack": "🍎"
    }
    return icons.get(meal_type, "🍽️")


def format_history_message(
    target_date: date,
    meals: List[Dict[str, Any]],
    water_logs: List[Dict[str, Any]]
) -> str:
    """
    Форматирует историю за день.
    """
    date_str = format_date_ru(target_date)
    
    total_kcal = 0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    total_water = len(water_logs) * 250  # по умолчанию 250 мл за запись
    
    text = f"📅 <b>{date_str}</b>\n\n"
    
    # Еда
    if meals:
        text += "🍽️ <b>Еда</b>\n"
        for meal in meals:
            icon = get_meal_icon(meal["meal_type"])
            time_str = format_time(meal["eaten_at"])
            text += f"▸ {time_str} {icon} <b>{meal['food_name']}</b>\n"
            text += f"   {meal['amount_g']} г — {meal['kcal']} ккал"
            if meal.get('protein_g') or meal.get('fat_g') or meal.get('carbs_g'):
                text += f" (🥑{meal.get('fat_g', 0):.0f} 🍗{meal.get('protein_g', 0):.0f} 🍚{meal.get('carbs_g', 0):.0f})"
            text += "\n"
            
            total_kcal += meal["kcal"]
            total_protein += meal.get("protein_g", 0)
            total_fat += meal.get("fat_g", 0)
            total_carbs += meal.get("carbs_g", 0)
        
        text += "\n"
    else:
        text += "🍽️ <b>Еда</b>\n"
        text += "▸ Нет записей о еде\n\n"
    
    # Вода
    if water_logs:
        text += "💧 <b>Вода</b>\n"
        for log in water_logs:
            time_str = format_time(log["logged_at"])
            amount = log.get("amount_ml", 250)
            text += f"▸ {time_str} +{amount} мл\n"
        text += "\n"
    else:
        text += "💧 <b>Вода</b>\n"
        text += "▸ Нет записей о воде\n\n"
    
    # Итоги
    text += "─────────────────\n"
    text += f"<b>Итого:</b> {total_kcal} ккал"
    if total_protein or total_fat or total_carbs:
        text += f" · 🍗{total_protein:.0f} 🥑{total_fat:.0f} 🍚{total_carbs:.0f}"
    text += f"\n<b>Вода:</b> {total_water} мл ({len(water_logs)} стаканов)\n"
    
    return text


def format_empty_history_message(target_date: date) -> str:
    """Форматирует сообщение для дня без записей."""
    date_str = format_date_ru(target_date)
    return (
        f"📅 <b>{date_str}</b>\n\n"
        f"😕 За этот день нет записей.\n\n"
        f"Хочешь добавить что-то?"
    )


def generate_calendar(year: int, month: int, available_dates: set) -> Tuple[List[List[Optional[int]]], int, int]:
    """
    Генерирует календарь на месяц.
    Возвращает: (матрица дней, количество недель, первый день недели)
    """
    cal = monthcalendar(year, month)
    return cal, len(cal), cal[0].index(1) if 1 in cal[0] else 0


def get_available_dates_set(available_dates: List[str]) -> set:
    """Преобразует список доступных дат в множество для быстрого поиска."""
    return set(available_dates)


def parse_calendar_date(date_str: str) -> Optional[date]:
    """Парсит дату из строки формата 'YYYY-MM-DD'."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return None


def get_date_range_for_period(days: int = 30) -> Tuple[date, date]:
    """Возвращает диапазон дат для ограничения истории."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date