"""
Утилиты для истории питания.
🎯 Обновлено: правильный подсчёт воды, статусы дней, сводки за период, тренды.
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional
from calendar import monthcalendar, month_name
from db.repositories import HistoryRepository, DailyStatsRepository


# ================================================================
# ФОРМАТИРОВАНИЕ ДАТ И ВРЕМЕНИ
# ================================================================
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


def format_date_short_ru(date_obj: date) -> str:
    """Короткий формат: '18 июня'"""
    months = {
        1: "янв", 2: "фев", 3: "мар", 4: "апр",
        5: "мая", 6: "июн", 7: "июл", 8: "авг",
        9: "сен", 10: "окт", 11: "ноя", 12: "дек"
    }
    return f"{date_obj.day} {months[date_obj.month]}"


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


# ================================================================
# 🎯 НОВОЕ: СТАТУСЫ ДНЯ (для цветовых индикаторов)
# ================================================================
def get_daily_status(total_kcal: int, daily_goal: int) -> str:
    """
    🎯 Определяет статус дня по КБЖУ.
    
    Возвращает:
    - 'good' (🟢): в пределах ±10% от нормы
    - 'warning' (🟡): отклонение 10-25%
    - 'bad' (🔴): отклонение >25%
    """
    from .constants import STATUS_GOOD, STATUS_WARNING, STATUS_BAD
    
    if daily_goal <= 0:
        return STATUS_GOOD
    
    deviation = abs(total_kcal - daily_goal) / daily_goal
    
    if deviation <= 0.10:
        return STATUS_GOOD
    elif deviation <= 0.25:
        return STATUS_WARNING
    else:
        return STATUS_BAD


def get_status_emoji(status: str) -> str:
    """Возвращает эмодзи для статуса."""
    from .constants import STATUS_GOOD, STATUS_WARNING, STATUS_BAD
    
    return {
        STATUS_GOOD: "🟢",
        STATUS_WARNING: "🟡",
        STATUS_BAD: "🔴",
    }.get(status, "⚪")


def get_status_text(total_kcal: int, daily_goal: int) -> str:
    """
    🎯 Возвращает человеко-понятный текст статуса.
    """
    from .constants import STATUS_GOOD, STATUS_WARNING, STATUS_BAD
    
    status = get_daily_status(total_kcal, daily_goal)
    percent = int((total_kcal / daily_goal) * 100) if daily_goal > 0 else 0
    
    if status == STATUS_GOOD:
        if total_kcal >= daily_goal:
            return f"✅ В норме ({percent}%)"
        else:
            return f"✅ В норме ({percent}%)"
    elif status == STATUS_WARNING:
        if total_kcal > daily_goal:
            excess = total_kcal - daily_goal
            return f"🟡 Небольшой перебор (+{excess} ккал, {percent}%)"
        else:
            deficit = daily_goal - total_kcal
            return f"🟡 Небольшой недобор (-{deficit} ккал, {percent}%)"
    else:
        if total_kcal > daily_goal:
            excess = total_kcal - daily_goal
            return f"🔴 Сильный перебор (+{excess} ккал, {percent}%)"
        else:
            deficit = daily_goal - total_kcal
            return f"🔴 Сильный недобор (-{deficit} ккал, {percent}%)"


# ================================================================
# ФОРМАТИРОВАНИЕ ИСТОРИИ ЗА ДЕНЬ
# ================================================================
def format_history_message(
    target_date: date,
    meals: List[Dict[str, Any]],
    water_logs: List[Dict[str, Any]],
    daily_kcal_goal: int = 0,
    water_goal_ml: int = 0,
) -> str:
    """
    Форматирует историю за день.
    🎯 Обновлено: правильный подсчёт воды + статус дня + статус воды.
    """
    date_str = format_date_ru(target_date)
    total_kcal = 0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    # 🎯 ПРАВИЛЬНО: суммируем реальный объём воды, а не предполагаем 250мл
    total_water = sum(log.get('amount_ml', 250) for log in water_logs)

    text = f"📅  <b>{date_str}</b>\n\n"

    # ===== ЕДА =====
    if meals:
        text += "🍽️  <b>Еда</b>\n"
        for meal in meals:
            icon = get_meal_icon(meal["meal_type"])
            time_str = format_time(meal["eaten_at"])
            text += f"▸ {time_str} {icon} <b>{meal['food_name']}</b>\n"
            text += f"   {meal['amount_g']:.0f} г — {meal['kcal']} ккал"
            if meal.get('protein_g') or meal.get('fat_g') or meal.get('carbs_g'):
                text += f" (🥑{meal.get('fat_g', 0):.0f} 🍗{meal.get('protein_g', 0):.0f} 🍚{meal.get('carbs_g', 0):.0f})"
            text += "\n"
            
            total_kcal += meal["kcal"]
            total_protein += meal.get("protein_g", 0)
            total_fat += meal.get("fat_g", 0)
            total_carbs += meal.get("carbs_g", 0)
        text += "\n"
    else:
        text += "🍽️  <b>Еда</b>\n"
        text += "▸ Нет записей о еде\n\n"

    # ===== ВОДА =====
    if water_logs:
        text += "💧  <b>Вода</b>\n"
        for log in water_logs:
            time_str = format_time(log["logged_at"])
            amount = log.get("amount_ml", 250)
            text += f"▸ {time_str} +{amount} мл\n"
        text += "\n"
    else:
        text += "💧  <b>Вода</b>\n"
        text += "▸ Нет записей о воде\n\n"

    # ===== ИТОГИ С СТАТУСОМ =====
    text += "─────────────────\n"
    text += f"<b>Итого:</b> {int(total_kcal)} ккал"
    if total_protein or total_fat or total_carbs:
        text += f" · 🍗{total_protein:.0f} 🥑{total_fat:.0f} 🍚{total_carbs:.0f}"
    text += "\n"
    
    # 🎯 НОВОЕ: статус дня по КБЖУ
    if daily_kcal_goal > 0 and total_kcal > 0:
        status_text = get_status_text(int(total_kcal), daily_kcal_goal)
        text += f"<b>Статус дня:</b> {status_text}\n"
    
    # 🎯 НОВОЕ: статус воды
    if water_goal_ml > 0:
        water_percent = int((total_water / water_goal_ml) * 100)
        if total_water >= water_goal_ml:
            water_status = f"✅ Выполнено ({water_percent}%)"
        elif water_percent >= 70:
            water_status = f"💙 Почти ({water_percent}%)"
        else:
            water_status = f"💧 {water_percent}%"
        text += f"<b>Вода:</b> {total_water} мл / {water_goal_ml} мл — {water_status}\n"
    else:
        text += f"<b>Вода:</b> {total_water} мл ({len(water_logs)} стаканов)\n"

    return text


def format_empty_history_message(target_date: date) -> str:
    """Форматирует сообщение для дня без записей."""
    date_str = format_date_ru(target_date)
    return (
        f"📅  <b>{date_str}</b>\n\n"
        f"😕 За этот день нет записей.\n\n"
        f"Хочешь добавить что-то?"
    )


# ================================================================
# 🎯 НОВОЕ: СБОР СТАТИСТИКИ ЗА ПЕРИОД
# ================================================================
async def get_period_stats(
    history_repo: HistoryRepository,
    user_id: int,
    days: int,
    daily_kcal_goal: int = 0,
) -> Dict[str, Any]:
    """
    Собирает статистику за период (7 или 30 дней).
    Возвращает dict с общими калориями, средним, лучшим/худшим днём и т.д.
    """
    today = date.today()
    total_kcal = 0
    days_with_entries = 0
    daily_totals = []
    weekday_kcal = {i: [] for i in range(7)}  # для инсайтов по дням недели
    
    for i in range(days):
        current_date = today - timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        meals = await history_repo.get_meals_for_date(user_id, date_str)
        day_kcal = sum(m["kcal"] for m in meals)
        
        if meals:
            days_with_entries += 1
            daily_totals.append((current_date, day_kcal))
            weekday_kcal[current_date.weekday()].append(day_kcal)
        
        total_kcal += day_kcal
    
    avg_kcal = total_kcal / days_with_entries if days_with_entries > 0 else 0
    
    # Лучший и худший дни (по близости к норме, если она есть)
    if daily_totals and daily_kcal_goal > 0:
        # Лучший = ближе всего к норме
        best_day = min(daily_totals, key=lambda x: abs(x[1] - daily_kcal_goal))
        # Худший = дальше всего от нормы
        worst_day = max(daily_totals, key=lambda x: abs(x[1] - daily_kcal_goal))
    elif daily_totals:
        best_day = max(daily_totals, key=lambda x: x[1])  # самый сытый
        worst_day = min(daily_totals, key=lambda x: x[1])  # самый голодный
    else:
        best_day = worst_day = None
    
    # 🎯 Инсайт: самый калорийный день недели
    top_weekday = None
    top_weekday_avg = 0
    weekday_names = {
        0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
        4: "Пятница", 5: "Суббота", 6: "Воскресенье"
    }
    for wd, kcals in weekday_kcal.items():
        if kcals:
            wd_avg = sum(kcals) / len(kcals)
            if wd_avg > top_weekday_avg:
                top_weekday_avg = wd_avg
                top_weekday = weekday_names[wd]
    
    return {
        "total_kcal": int(total_kcal),
        "avg_kcal": int(avg_kcal),
        "days_with_entries": days_with_entries,
        "total_days": days,
        "best_day": best_day,
        "worst_day": worst_day,
        "top_weekday": top_weekday,
        "top_weekday_avg": int(top_weekday_avg),
        "daily_goal": daily_kcal_goal,
    }


def format_period_summary(
    stats: Dict[str, Any],
    period_name: str,
    period_days: int,
) -> str:
    """
    🎯 Форматирует красивую сводку за период в стиле Apple.
    """
    start_date = date.today() - timedelta(days=period_days - 1)
    end_date = date.today()
    period_range = f"{format_date_short_ru(start_date)} — {format_date_short_ru(end_date)}"
    
    period_emoji = "📊" if period_days == 7 else "📅"
    
    text = f"{period_emoji}  <b>{period_name}</b>\n\n"
    text += f"🗓 <i>{period_range}</i>\n\n"
    text += "─────────────────\n"
    
    text += f"🔥 <b>{stats['total_kcal']:,} ккал</b> всего\n".replace(",", " ")
    text += f"📊 <b>{stats['avg_kcal']:,} ккал</b> в среднем\n".replace(",", " ")
    text += f"📅 <b>{stats['days_with_entries']}</b> из {stats['total_days']} дней с записями\n"
    
    if stats['best_day']:
        best_date, best_kcal = stats['best_day']
        worst_date, worst_kcal = stats['worst_day']
        text += f"\n🏆 Лучший день: {format_date_short_ru(best_date)} ({best_kcal} ккал)\n"
        text += f"📉 Скромный день: {format_date_short_ru(worst_date)} ({worst_kcal} ккал)\n"
    
    text += "─────────────────\n\n"
    
    # 💡 Инсайт
    if stats['daily_goal'] > 0 and stats['avg_kcal'] > 0:
        deviation = ((stats['avg_kcal'] - stats['daily_goal']) / stats['daily_goal']) * 100
        if abs(deviation) <= 10:
            text += "💡 <i>Ты идеально попадаешь в свою норму! 🎯</i>\n"
        elif deviation > 10:
            text += f"💡 <i>В среднем ты ешь на {deviation:.0f}% больше нормы. Обрати внимание.</i>\n"
        else:
            text += f"💡 <i>В среднем ты ешь на {abs(deviation):.0f}% меньше нормы.</i>\n"
    
    if stats['top_weekday'] and stats['top_weekday_avg'] > 0:
        text += f"🔥 <i>{stats['top_weekday']} — твой самый сытый день ({stats['top_weekday_avg']} ккал)</i>\n"
    
    return text


# ================================================================
# КАЛЕНДАРЬ
# ================================================================
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


async def get_dates_with_status(
    history_repo: HistoryRepository,
    user_id: int,
    year: int,
    month: int,
    daily_kcal_goal: int,
) -> Dict[str, str]:
    """
    🎯 Возвращает dict {date_str: status} для месяца.
    Используется для цветовых индикаторов в календаре.
    """
    from .constants import STATUS_GOOD, STATUS_WARNING, STATUS_BAD, STATUS_EMPTY
    from calendar import monthrange
    
    result = {}
    _, last_day = monthrange(year, month)
    today = date.today()
    
    for day in range(1, last_day + 1):
        current_date = date(year, month, day)
        # Не показываем будущие дни
        if current_date > today:
            continue
        
        date_str = current_date.strftime("%Y-%m-%d")
        meals = await history_repo.get_meals_for_date(user_id, date_str)
        
        if not meals:
            result[date_str] = STATUS_EMPTY
        else:
            total_kcal = sum(m["kcal"] for m in meals)
            if daily_kcal_goal > 0:
                result[date_str] = get_daily_status(int(total_kcal), daily_kcal_goal)
            else:
                result[date_str] = STATUS_GOOD
    
    return result


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