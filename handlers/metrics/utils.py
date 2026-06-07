"""
Утилиты для модуля сбора метрик и аналитики.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def get_default_metrics() -> Dict[str, Any]:
    # ВАЖНО: Ключи без пробелов, иначе analytics их не прочитает!
    return {
        "sleep_hours": None, "sleep_quality": None, "sleep_awakenings": None,
        "energy_morning": None, "energy_evening": None, "stress_level": None,
        "steps": None, "hours_on_feet": None, "workout_type": None,
        "workout_duration": None, "workout_intensity": None,
        "hunger_before": None, "hunger_after": None, "digestion_bristol": None,
        "cycle_day": None, "notes": None
    }

def format_metrics_summary(metrics: Dict[str, Any]) -> str:
    lines = []
    sleep_hours = metrics.get("sleep_hours")
    if sleep_hours is not None:
        q = metrics.get("sleep_quality")
        stars = "⭐" * q if q else ""
        lines.append(f"😴 Сон: {sleep_hours}ч {stars}")
    else:
        lines.append("😴 Сон: ❌ не заполнено")

    if metrics.get("energy_morning") is not None:
        lines.append(f"⚡ Энергия утром: {metrics['energy_morning']}/10")
    if metrics.get("energy_evening") is not None:
        lines.append(f"⚡ Энергия вечером: {metrics['energy_evening']}/10")
        
    if metrics.get("stress_level") is not None:
        lines.append(f"😰 Стресс: {metrics['stress_level']}/10")
        
    if metrics.get("steps") is not None:
        lines.append(f"👣 Шаги: {metrics['steps']:,}")
    if metrics.get("hours_on_feet") is not None:
        lines.append(f"👣 Часы на ногах: {metrics['hours_on_feet']}ч")
        
    w_type = metrics.get("workout_type")
    if w_type and w_type != "none":
        names = {"strength": "Силовая", "cardio": "Кардио", "yoga": "Йога", "walk": "Прогулка", "swim": "Плавание"}
        dur = f", {metrics.get('workout_duration')}мин" if metrics.get('workout_duration') else ""
        intensity = f" ({metrics.get('workout_intensity')}/10)" if metrics.get('workout_intensity') else ""
        lines.append(f"💪 Тренировка: {names.get(w_type, w_type)}{dur}{intensity}")
    else:
        lines.append("💪 Тренировка: ❌ не было")

    return "\n".join(lines)

def split_long_message(text: str, max_length: int = 1000) -> list:
    # Telegram ограничивает подпись к фото (caption) 1024 символами.
    # Поэтому для графиков разбиваем текст на части по 1000 символов.
    if len(text) <= max_length:
        return [text]
    parts, current_part = [], ""
    for line in text.split("\n"):
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            current_part += ("\n" + line) if current_part else line
    if current_part:
        parts.append(current_part)
    return parts