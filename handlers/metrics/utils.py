"""
Утилиты для модуля сбора метрик.
"""
from typing import Dict, Any, Optional
from datetime import datetime, date


def format_metrics_summary(metrics: Dict[str, Any]) -> str:
    """
    Форматирует текущие сохранённые метрики для отображения.
    """
    lines = []
    
    # Сон
    sleep_hours = metrics.get("sleep_hours")
    sleep_quality = metrics.get("sleep_quality")
    sleep_awakenings = metrics.get("sleep_awakenings")
    
    if sleep_hours is not None:
        quality_stars = "⭐" * sleep_quality if sleep_quality else ""
        awakenings_text = {0: "нет", 1: "1 раз", 2: "2 раза", 3: "3+ раз"}.get(sleep_awakenings, "")
        lines.append(f"😴 Сон: {sleep_hours}ч {quality_stars} {awakenings_text}")
    else:
        lines.append("😴 Сон: ❌ не заполнено")
    
    # Энергия
    energy_morning = metrics.get("energy_morning")
    energy_evening = metrics.get("energy_evening")
    if energy_morning is not None:
        lines.append(f"⚡ Энергия утром: {energy_morning}/10")
    else:
        lines.append("⚡ Энергия утром: ❌ не заполнено")
    
    if energy_evening is not None:
        lines.append(f"⚡ Энергия вечером: {energy_evening}/10")
    else:
        lines.append("⚡ Энергия вечером: ❌ не заполнено")
    
    # Стресс
    stress = metrics.get("stress_level")
    if stress is not None:
        lines.append(f"😰 Стресс: {stress}/10")
    else:
        lines.append("😰 Стресс: ❌ не заполнено")
    
    # Шаги
    steps = metrics.get("steps")
    hours_on_feet = metrics.get("hours_on_feet")
    if steps is not None:
        lines.append(f"👣 Шаги: {steps:,}")
    if hours_on_feet is not None:
        lines.append(f"👣 Часы на ногах: {hours_on_feet}ч")
    
    if steps is None and hours_on_feet is None:
        lines.append("👣 Активность: ❌ не заполнено")
    
    # Тренировка
    workout_type = metrics.get("workout_type")
    workout_duration = metrics.get("workout_duration")
    workout_intensity = metrics.get("workout_intensity")
    
    if workout_type and workout_type != "none":
        type_names = {
            "strength": "силовая",
            "cardio": "кардио",
            "yoga": "йога",
            "walk": "прогулка",
            "swim": "плавание",
        }
        type_text = type_names.get(workout_type, workout_type)
        intensity_text = f" ({workout_intensity}/10)" if workout_intensity else ""
        lines.append(f"💪 Тренировка: {type_text}, {workout_duration}мин{intensity_text}")
    else:
        lines.append("💪 Тренировка: ❌ не было или не заполнено")
    
    # Голод (опционально)
    hunger_before = metrics.get("hunger_before")
    hunger_after = metrics.get("hunger_after")
    if hunger_before is not None or hunger_after is not None:
        lines.append(f"🍽️ Голод: до={hunger_before}/10, после={hunger_after}/10")
    
    # Пищеварение
    digestion = metrics.get("digestion_bristol")
    if digestion is not None:
        digestion_names = {
            1: "запор", 2: "запор", 3: "норма", 4: "идеал",
            5: "мягкий", 6: "диарея", 7: "диарея"
        }
        lines.append(f"🚽 Пищеварение: тип {digestion} ({digestion_names.get(digestion, '')})")
    
    # Цикл
    cycle_day = metrics.get("cycle_day")
    if cycle_day is not None and cycle_day > 0:
        lines.append(f"🌸 День цикла: {cycle_day}")
    
    return "\n".join(lines)


def get_default_metrics() -> Dict[str, Any]:
    """Возвращает словарь с метриками по умолчанию (все None)."""
    return {
        "sleep_hours": None,
        "sleep_quality": None,
        "sleep_awakenings": None,
        "energy_morning": None,
        "energy_evening": None,
        "stress_level": None,
        "steps": None,
        "hours_on_feet": None,
        "workout_type": None,
        "workout_duration": None,
        "workout_intensity": None,
        "hunger_before": None,
        "hunger_after": None,
        "digestion_bristol": None,
        "cycle_day": None,
        "notes": None,
    }


def get_session_type_by_hour() -> str:
    """
    Определяет, утренняя или вечерняя сейчас сессия.
    Утро: 5:00 - 12:00
    Вечер: 18:00 - 23:00
    В остальное время возвращает None.
    """
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 18 <= hour < 23:
        return "evening"
    return None


def get_session_prompt(session_type: str) -> str:
    """Возвращает приветственное сообщение для сессии."""
    if session_type == "morning":
        return (
            "☀️ <b>Доброе утро!</b>\n\n"
            "Давай оценим, как ты спал и как себя чувствуешь.\n"
            "Это поможет мне лучше понимать твой метаболизм и давать точные советы.\n\n"
            "Начнём?"
        )
    else:
        return (
            "🌙 <b>Добрый вечер!</b>\n\n"
            "Давай подведём итоги дня — это займёт всего минуту.\n"
            "Расскажи, как прошёл день, и я дам персональные рекомендации.\n\n"
            "Начнём?"
        )