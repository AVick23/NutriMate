# handlers/measurements/utils.py
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
import statistics
import math


def format_date_ru(dt: datetime) -> str:
    """Форматирует дату на русском: '18 июня' или 'сегодня'."""
    now = datetime.now()
    if dt.date() == now.date():
        return "сегодня"
    elif dt.date() == (now - timedelta(days=1)).date():
        return "вчера"
    
    months = {
        1: "янв", 2: "фев", 3: "мар", 4: "апр",
        5: "мая", 6: "июня", 7: "июля", 8: "авг",
        9: "сен", 10: "окт", 11: "ноя", 12: "дек"
    }
    return f"{dt.day} {months[dt.month]}"


def calculate_trend(measurements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Рассчитывает тренд на основе истории замеров.
    Возвращает: weekly_rate, direction, stability, best_value, worst_value
    """
    if len(measurements) < 2:
        return {
            "weekly_rate": 0.0,
            "direction": "insufficient",
            "stability": "insufficient",
            "best_value": measurements[-1]["value"] if measurements else None,
            "worst_value": measurements[-1]["value"] if measurements else None,
        }
    
    values = [m["value"] for m in measurements]
    dates = [datetime.fromisoformat(m["date"].replace(' ', 'T')) for m in measurements]
    
    # Простая линейная регрессия
    x = [(d - min(dates)).days for d in dates]
    y = values
    n = len(x)
    
    if n > 1 and sum(x) != 0:
        slope = (n * sum(xi*yi for xi, yi in zip(x, y)) - sum(x)*sum(y)) / (n*sum(xi*xi for xi in x) - sum(x)**2 + 1e-9)
        weekly_rate = slope * 7
    else:
        weekly_rate = 0.0
    
    # Направление
    if weekly_rate < -0.1:
        direction = "down"
    elif weekly_rate > 0.1:
        direction = "up"
    else:
        direction = "stable"
    
    # Стабильность
    if len(measurements) >= 4:
        deviation = statistics.stdev(values)
        if deviation < 0.3:
            stability = "high"
        elif deviation < 0.8:
            stability = "medium"
        else:
            stability = "low"
    else:
        stability = "insufficient"
    
    return {
        "weekly_rate": round(weekly_rate, 1),
        "direction": direction,
        "stability": stability,
        "best_value": min(values) if direction == "down" else max(values),
        "worst_value": max(values) if direction == "down" else min(values),
    }


def get_smart_feedback(
    measurement_type_id: int,
    measurement_name: str,
    new_value: float,
    previous_value: Optional[float],
    trend: Dict[str, Any],
    goal_value: Optional[float] = None
) -> str:
    """Генерирует умное сообщение после добавления замера."""
    
    if previous_value is None:
        return f"✅ <b>Первый замер сохранён!</b>\n📏 {measurement_name}: {new_value:.1f} {_get_unit(measurement_type_id)}\nПродолжай отслеживать прогресс!"
    
    change = new_value - previous_value
    abs_change = abs(change)
    
    # Вес
    if measurement_type_id == 1:  # weight
        if change < 0:
            if trend["weekly_rate"] < -1.5:
                return f"⚠️ <b>Быстрая потеря веса</b> ({trend['weekly_rate']:.1f} кг/нед)\nУбедись, что ты получаешь достаточно калорий и белка. Здоровый темп – 0.5-1 кг/нед."
            elif trend["weekly_rate"] < -0.8:
                return f"🔥 <b>Отличный темп!</b> {trend['weekly_rate']:.1f} кг/нед\nТак держать! 💪"
            else:
                return f"✅ <b>-{abs_change:.1f} кг</b>\nСредняя скорость: {trend['weekly_rate']:.1f} кг/нед. Продолжай!"
        elif change > 0:
            return f"📈 <b>+{abs_change:.1f} кг</b>\nЭто может быть задержка воды или набор мышц. Смотри на объёмы и отражение в зеркале."
        else:
            return f"📊 <b>Вес не изменился</b>\nЭто нормально. Иногда прогресс идёт волнами."
    
    # Объёмы (талия, бёдра, грудь, рука, бедро)
    else:
        if change < 0:
            if abs_change >= 2:
                return f"🎉 <b>Отлично!</b> {measurement_name} уменьшилась на {abs_change:.0f} см\nВидимый прогресс! Так держать! 📏"
            else:
                return f"✅ <b>{measurement_name}</b>: {new_value:.1f} см (было {previous_value:.1f})\nНезаметно, но верно. Продолжай!"
        elif change > 0:
            return f"📏 <b>+{abs_change:.0f} см</b> ({measurement_name})\nЭто может быть из-за отёков или роста мышц. Следи за динамикой."
        else:
            return f"📏 <b>{measurement_name}</b> не изменился\nНе переживай, иногда прогресс идёт волнами."


def get_measurement_type_info(type_id: int) -> Dict[str, Any]:
    """Возвращает информацию о типе замера."""
    from .constants import MEASUREMENT_TYPES
    return MEASUREMENT_TYPES.get(type_id, {})


def _get_unit(type_id: int) -> str:
    """Возвращает единицу измерения для типа замера."""
    info = get_measurement_type_info(type_id)
    return info.get("unit", "")


def format_history_message(
    measurement_type_id: int,
    measurement_name: str,
    history: List[Dict[str, Any]],
    unit: str
) -> str:
    """Форматирует сообщение с историей замеров."""
    if not history:
        return f"📋 <b>История замеров: {measurement_name}</b>\n\nНет записей. Добавь первый замер!"
    
    text = f"📋 <b>История замеров: {measurement_name}</b>\n\n"
    
    for i, record in enumerate(history):
        dt = datetime.fromisoformat(record["measured_at"].replace(' ', 'T'))
        date_str = format_date_ru(dt)
        value = record["value"]
        
        # Показываем разницу с предыдущим
        if i < len(history) - 1:
            prev_value = history[i + 1]["value"]
            diff = value - prev_value
            diff_sign = "+" if diff > 0 else ""
            diff_str = f" ({diff_sign}{diff:.1f})"
        else:
            diff_str = ""
        
        text += f"• <b>{date_str}</b> – {value:.1f} {unit}{diff_str}\n"
    
    # Добавляем аналитику, если достаточно данных
    if len(history) >= 2:
        trend = calculate_trend(history)
        if trend["direction"] != "insufficient":
            text += f"\n📊 <b>Аналитика:</b>\n"
            if trend["weekly_rate"] != 0:
                direction_word = "📉 уменьшается" if trend["weekly_rate"] < 0 else "📈 увеличивается"
                text += f"▸ Средняя скорость: {abs(trend['weekly_rate']):.1f} {unit}/нед ({direction_word})\n"
            if trend["best_value"]:
                text += f"▸ Лучший результат: {trend['best_value']:.1f} {unit}\n"
    
    return text


def format_main_menu_message(
    last_measurements: Dict[int, Dict[str, Any]],
    goals: Dict[int, float]
) -> str:
    """Форматирует главное меню замеров с аналитикой."""
    from .constants import MEASUREMENT_TYPES
    
    text = "📏 <b>Замеры тела</b>\n\n"
    
    # Показываем последние замеры
    text += "<b>Последние замеры:</b>\n"
    for type_id, info in MEASUREMENT_TYPES.items():
        if type_id in last_measurements:
            meas = last_measurements[type_id]
            value = meas["value"]
            unit = info["unit"]
            date_str = format_date_ru(datetime.fromisoformat(meas["measured_at"].replace(' ', 'T')))
            text += f"• {info['emoji']} {info['display']}: <b>{value:.1f} {unit}</b> ({date_str})\n"
        else:
            text += f"• {info['emoji']} {info['display']}: <i>нет данных</i>\n"
    
    # Добавляем аналитику по весу (если есть)
    if 1 in last_measurements and len(last_measurements) > 0:
        weight_measurements = last_measurements.get(1, {})
        if "history" in weight_measurements:
            trend = calculate_trend(weight_measurements["history"])
            if trend["weekly_rate"] != 0 and trend["direction"] != "insufficient":
                text += f"\n📊 <b>Аналитика:</b>\n"
                if trend["weekly_rate"] < 0:
                    text += f"▸ Теряешь в среднем {abs(trend['weekly_rate']):.1f} кг/нед\n"
                    if 1 in goals:
                        goal = goals[1]
                        current = weight_measurements.get("value", 0)
                        remaining = current - goal
                        if remaining > 0:
                            weeks = remaining / abs(trend["weekly_rate"]) if trend["weekly_rate"] != 0 else 0
                            text += f"▸ До цели {goal:.1f} кг осталось ~{int(weeks)} недель\n"
                elif trend["weekly_rate"] > 0:
                    text += f"▸ Вес увеличивается на {trend['weekly_rate']:.1f} кг/нед\n"
    
    return text


def get_quick_values_for_type(measurement_type_id: int) -> List[float]:
    """Возвращает список быстрых значений для типа замера."""
    from .constants import QUICK_WEIGHT_VALUES, QUICK_CIRCUMFERENCE_VALUES
    
    if measurement_type_id == 1:  # weight
        return QUICK_WEIGHT_VALUES
    else:
        return QUICK_CIRCUMFERENCE_VALUES