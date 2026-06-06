"""
Утилиты для модуля сбора метрик и аналитики.
Расширенная версия с форматированием инсайтов, паттернов, прогнозов.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ============================================================
# ФОРМАТИРОВАНИЕ МЕТРИК
# ============================================================

def format_metrics_summary(metrics: Dict[str, Any]) -> str:
    """Форматирует текущие сохранённые метрики для отображения."""
    lines = []
    
    # Сон
    sleep_hours = metrics.get("sleep_hours")
    sleep_quality = metrics.get("sleep_quality")
    sleep_awakenings = metrics.get("sleep_awakenings")
    
    if sleep_hours is not None:
        quality_stars = "⭐" * sleep_quality if sleep_quality else ""
        awakenings_text = {0: "нет", 1: "1 раз", 2: "2 раза", 3: "3+ раз"}.get(
            sleep_awakenings, ""
        )
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
        duration_text = f", {workout_duration}мин" if workout_duration else ""
        lines.append(f"💪 Тренировка: {type_text}{duration_text}{intensity_text}")
    else:
        lines.append("💪 Тренировка: ❌ не было или не заполнено")
    
    return "\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ ИНСАЙТОВ (НОВОЕ)
# ============================================================

def format_insights(insights: List[Any], max_count: int = 5) -> str:
    """
    Форматирует список инсайтов в читаемый текст.
    
    Args:
        insights: список объектов Insight
        max_count: максимальное количество инсайтов
    
    Returns:
        HTML-форматированная строка
    """
    if not insights:
        return "<i>Нет инсайтов для отображения</i>"
    
    lines = []
    for i, insight in enumerate(insights[:max_count], 1):
        lines.append(f"{insight.emoji} <b>{insight.title}</b>")
        lines.append(f"   {insight.message}")
        if i < len(insights[:max_count]):
            lines.append("")
    
    return "\n".join(lines)


def format_insights_compact(insights: List[Any], max_count: int = 3) -> str:
    """Компактное форматирование инсайтов для дневной аналитики."""
    if not insights:
        return ""
    
    lines = []
    for insight in insights[:max_count]:
        msg = insight.message[:120] + "..." if len(insight.message) > 120 else insight.message
        lines.append(f"{insight.emoji} <b>{insight.title}</b>\n   {msg}")
    
    return "\n\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ ПАТТЕРНОВ (НОВОЕ)
# ============================================================

def format_patterns(patterns: List[Any], max_count: int = 5) -> str:
    """
    Форматирует список обнаруженных паттернов.
    
    Args:
        patterns: список объектов Pattern
        max_count: максимальное количество
    
    Returns:
        HTML-форматированная строка
    """
    if not patterns:
        return (
            "🔍 <b>Паттерны ещё не обнаружены</b>\n\n"
            "Для анализа паттернов нужно минимум <b>14 дней</b> данных.\n"
            "Заполняй метрики каждый день, и я найду уникальные закономерности!"
        )
    
    lines = [f"🔍 <b>Обнаружено паттернов: {len(patterns)}</b>\n"]
    
    for i, pattern in enumerate(patterns[:max_count], 1):
        # Эмодзи направления
        emoji = "📈" if pattern.effect_direction == "positive" else "📉"
        
        # Сила корреляции
        r_abs = abs(pattern.correlation_r) if pattern.correlation_r else 0
        if r_abs > 0.7:
            strength = "💪 сильная"
        elif r_abs > 0.5:
            strength = "🔹 умеренная"
        else:
            strength = "◇ слабая"
        
        # Лаг
        lag_text = ""
        if pattern.lag_days == 1:
            lag_text = " (на следующий день)"
        elif pattern.lag_days > 1:
            lag_text = f" (через {pattern.lag_days} дн.)"
        
        lines.append(
            f"{i}. {emoji} <b>{pattern.effect_text}</b>{lag_text}\n"
            f"   Связь {strength} (r={pattern.correlation_r:.2f}, "
            f"подтверждений: {pattern.sample_size})"
        )
        if i < len(patterns[:max_count]):
            lines.append("")
    
    return "\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ СОСТОЯНИЙ (НОВОЕ)
# ============================================================

def format_states(states: List[Any]) -> str:
    """
    Форматирует список обнаруженных состояний.
    
    Args:
        states: список объектов StateDetection
    
    Returns:
        HTML-форматированная строка
    """
    active_states = [s for s in states if s.detected]
    
    if not active_states:
        return (
            "✅ <b>Состояний не обнаружено</b>\n\n"
            "Все показатели в норме. Продолжай в том же духе! 💪"
        )
    
    lines = [f"🧬 <b>Обнаружено состояний: {len(active_states)}</b>\n"]
    
    for state in active_states:
        # Цветовая индикация severity
        severity_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
            "positive": "✨",
        }.get(state.severity, "⚪")
        
        lines.append(f"{state.emoji} <b>{state_name_ru(state.state_type)}</b> {severity_emoji}")
        
        # Индикаторы
        if state.indicators:
            lines.append("   <i>Признаки:</i>")
            for indicator in state.indicators[:3]:
                lines.append(f"   • {indicator}")
        
        # Рекомендация
        lines.append(f"\n   💡 {state.recommendation}")
        lines.append("")
    
    return "\n".join(lines)


def state_name_ru(state_type: str) -> str:
    """Возвращает русское название состояния."""
    names = {
        "metabolic_adaptation": "Метаболическая адаптация",
        "body_recomposition": "Рекомпозиция тела",
        "overtraining": "Перетренированность",
        "stress_plateau": "Стрессовое плато",
        "insulin_resistance": "Инсулинорезистентность",
    }
    return names.get(state_type, state_type)


# ============================================================
# ФОРМАТИРОВАНИЕ БЖУ БАЛАНСА (НОВОЕ)
# ============================================================

def format_macro_balance(agg: Any) -> str:
    """
    Форматирует баланс БЖУ с визуализацией.
    
    Args:
        agg: объект DailyAggregate
    
    Returns:
        HTML-форматированная строка
    """
    total_kcal = agg.nutrition.total_kcal
    if not total_kcal or total_kcal <= 0:
        return "<i>Нет данных о питании</i>"
    
    protein_kcal = agg.nutrition.total_protein_g * 4
    fat_kcal = agg.nutrition.total_fat_g * 9
    carbs_kcal = agg.nutrition.total_carbs_g * 4
    
    protein_pct = (protein_kcal / total_kcal) * 100
    fat_pct = (fat_kcal / total_kcal) * 100
    carbs_pct = (carbs_kcal / total_kcal) * 100
    
    # Визуализация барами
    def bar(pct: float, length: int = 10) -> str:
        filled = int(pct / 100 * length)
        return "▰" * filled + "▱" * (length - filled)
    
    lines = [
        "<b>⚖️ Баланс БЖУ:</b>",
        f"🍗 Белки: {bar(protein_pct)} {protein_pct:.0f}% ({agg.nutrition.total_protein_g:.0f}г)",
        f"🥑 Жиры: {bar(fat_pct)} {fat_pct:.0f}% ({agg.nutrition.total_fat_g:.0f}г)",
        f"🍚 Углеводы: {bar(carbs_pct)} {carbs_pct:.0f}% ({agg.nutrition.total_carbs_g:.0f}г)",
    ]
    
    return "\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ ПРОГНОЗА (НОВОЕ)
# ============================================================

def format_forecast(aggregates: List[Any], profile: Dict[str, Any]) -> str:
    """
    Форматирует прогноз достижения цели.
    
    Args:
        aggregates: список DailyAggregate за последние дни
        profile: профиль пользователя
    
    Returns:
        HTML-форматированная строка
    """
    if len(aggregates) < 7:
        return (
            "🔮 <b>Прогноз</b>\n\n"
            "<i>Недостаточно данных. Нужно минимум 7 дней для прогноза.</i>"
        )
    
    # Получаем веса
    weights = [a.measurements.weight_kg for a in aggregates if a.measurements.weight_kg]
    if len(weights) < 3:
        return (
            "🔮 <b>Прогноз</b>\n\n"
            "<i>Недостаточно данных о весе для прогноза.</i>"
        )
    
    current_weight = weights[-1]
    target_weight = profile.get("target_weight")
    
    # Рассчитываем средний темп (кг/неделю)
    week_change = weights[-1] - weights[0]
    weeks_span = len(weights) / 7
    weekly_rate = week_change / weeks_span if weeks_span > 0 else 0
    
    lines = ["🔮 <b>Прогноз прогресса</b>\n"]
    lines.append(f"⚖️ Текущий вес: <b>{current_weight:.1f} кг</b>")
    
    if target_weight:
        lines.append(f"🎯 Целевой вес: <b>{target_weight:.1f} кг</b>")
        remaining = target_weight - current_weight
        
        if weekly_rate != 0 and remaining != 0:
            weeks_to_goal = remaining / weekly_rate
            days_to_goal = int(weeks_to_goal * 7)
            
            if days_to_goal > 0:
                # Дата достижения
                target_date = date.today() + __import__('datetime').timedelta(days=days_to_goal)
                lines.append(
                    f"\n📅 При текущем темпе ({weekly_rate:+.2f} кг/нед):"
                )
                lines.append(
                    f"   Цель будет достигнута через <b>{days_to_goal} дней</b>"
                )
                lines.append(
                    f"   Примерная дата: <b>{target_date.strftime('%d.%m.%Y')}</b>"
                )
            else:
                lines.append("\n✨ <b>Цель уже достигнута!</b>")
        else:
            lines.append("\n⏸️ <i>Темп изменений слишком мал для прогноза</i>")
    else:
        lines.append("\n⚙️ <i>Целевой вес не установлен в профиле</i>")
    
    # Рекомендация по темпу
    if weekly_rate < -1:
        lines.append("\n⚠️ <b>Внимание:</b> слишком быстрая потеря веса!")
        lines.append("Рекомендуется темп 0.5-1 кг/нед для сохранения мышц.")
    elif -1 <= weekly_rate <= -0.3:
        lines.append("\n✅ Темп потери веса в норме")
    elif -0.3 < weekly_rate < 0.3:
        lines.append("\n⏸️ Вес стабилен (плато)")
    elif weekly_rate >= 0.3:
        lines.append("\n📈 Набор веса")
    
    return "\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ ЛУЧШЕГО ДНЯ (НОВОЕ)
# ============================================================

def format_best_day(aggregates: List[Any]) -> str:
    """
    Форматирует информацию о лучшем дне пользователя.
    
    Args:
        aggregates: список DailyAggregate
    
    Returns:
        HTML-форматированная строка
    """
    if len(aggregates) < 3:
        return (
            "🏆 <b>Лучший день</b>\n\n"
            "<i>Недостаточно данных. Заполняй метрики минимум 3 дня.</i>"
        )
    
    # Рассчитываем композитный скор для каждого дня
    scored_days = []
    for agg in aggregates:
        score = 0
        details = []
        
        # Энергия (до 10 баллов)
        if agg.derived.avg_energy:
            energy_score = agg.derived.avg_energy
            score += energy_score
            details.append(f"⚡ Энергия: {energy_score:.1f}/10")
        
        # Шаги (до 10 баллов)
        if agg.activity.steps:
            steps_score = min(agg.activity.steps / 1000, 10)
            score += steps_score
            details.append(f"👣 Шаги: {agg.activity.steps:,}")
        
        # Сон (до 10 баллов)
        if agg.sleep.hours:
            sleep_score = min(agg.sleep.hours, 10)
            score += sleep_score
            details.append(f"😴 Сон: {agg.sleep.hours:.1f}ч")
        
        # Качество сна (бонус до 5 баллов)
        if agg.sleep.quality:
            score += agg.sleep.quality
        
        # Стресс (штраф)
        if agg.stress:
            score -= (agg.stress - 5)  # стресс > 5 снижает скор
        
        # Белок (бонус)
        if agg.derived.protein_per_kg and agg.derived.protein_per_kg >= 1.6:
            score += 3
            details.append(f"🍗 Белок: {agg.derived.protein_per_kg:.1f}г/кг")
        
        scored_days.append((score, agg, details))
    
    # Сортируем по скору
    scored_days.sort(key=lambda x: x[0], reverse=True)
    
    best_score, best_agg, best_details = scored_days[0]
    avg_score = sum(s[0] for s in scored_days) / len(scored_days)
    
    lines = ["🏆 <b>Твой лучший день</b>\n"]
    lines.append(f"📅 <b>{best_agg.date.strftime('%d.%m.%Y')}</b>")
    lines.append(f"⭐ Скор: <b>{best_score:.1f}</b> (среднее: {avg_score:.1f})\n")
    
    lines.append("<b>Формула успеха:</b>")
    for detail in best_details:
        lines.append(f"• {detail}")
    
    # Рекомендация
    lines.append(
        "\n💡 <i>Попробуй повторить эту формулу! "
        "Это твой персональный рецепт хорошего дня.</i>"
    )
    
    return "\n".join(lines)


# ============================================================
# ФОРМАТИРОВАНИЕ МОДИФИКАТОРОВ TDEE (НОВОЕ)
# ============================================================

def format_tdee_modifiers(agg: Any, base_tdee: int) -> str:
    """
    Форматирует breakdown модификаторов TDEE.
    
    Args:
        agg: объект DailyAggregate
        base_tdee: базовый TDEE
    
    Returns:
        HTML-форматированная строка
    """
    lines = ["<b>⚡ Как рассчитан TDEE:</b>\n"]
    
    lines.append(f"📊 Базовый TDEE: <b>{base_tdee}</b> ккал\n")
    
    modifiers = [
        ("😴 Сон", agg.sleep_modifier),
        ("⚡ Энергия", agg.energy_modifier),
        ("😰 Стресс", agg.stress_modifier),
        ("👣 Активность", agg.activity_modifier),
        ("⏰ Окно питания", agg.window_modifier),
    ]
    
    for name, mod in modifiers:
        if mod != 1.0:
            change_pct = (mod - 1.0) * 100
            emoji = "📈" if change_pct > 0 else "📉"
            lines.append(f"{emoji} {name}: ×{mod:.3f} ({change_pct:+.1f}%)")
    
    if agg.workout_bonus > 0:
        lines.append(f"💪 Тренировка: +{agg.workout_bonus} ккал")
    
    lines.append(f"\n🎯 <b>Итог: {agg.adjusted_tdee}</b> ккал")
    
    if agg.confidence_score < 100:
        lines.append(
            f"\n📊 Точность: <b>{agg.confidence_score}%</b> "
            f"(заполни больше метрик для точности)"
        )
    
    return "\n".join(lines)


# ============================================================
# БАЗОВЫЕ УТИЛИТЫ
# ============================================================

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


def get_session_type_by_hour() -> Optional[str]:
    """Определяет, утренняя или вечерняя сейчас сессия."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 18 <= hour < 23:
        return "evening"
    return None


def split_long_message(text: str, max_length: int = 4000) -> list:
    """Разбивает длинное сообщение на части для отправки."""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    for line in text.split("\n"):
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            if current_part:
                current_part += "\n" + line
            else:
                current_part = line
    
    if current_part:
        parts.append(current_part)
    
    return parts


def format_waist_risk_message(measurement_name: str, value: float, gender: str) -> str:
    """Форматирует сообщение с риском по талии (ВОЗ)."""
    if measurement_name != "waist":
        return ""
    
    risk = get_waist_risk_category(value, gender)
    return f"\n\n{risk['color']} <b>Оценка риска ВОЗ:</b> {risk['category']}\n{risk['message']}"


def get_waist_risk_category(waist_cm: float, gender: str) -> dict:
    """Оценивает риск для здоровья по окружности талии (ВОЗ)."""
    if gender == "male":
        if waist_cm < 94:
            return {
                "category": "Норма",
                "risk": "Низкий",
                "color": "🟢",
                "message": "Твоя талия в пределах нормы. Отличный результат!"
            }
        elif waist_cm < 102:
            return {
                "category": "Повышенная",
                "risk": "Средний",
                "color": "🟡",
                "message": "Талия превышает норму. Повышенный риск ССЗ."
            }
        else:
            return {
                "category": "Высокая",
                "risk": "Высокий",
                "color": "🔴",
                "message": "Талия значительно превышает норму! Консультация врача."
            }
    else:
        if waist_cm < 80:
            return {
                "category": "Норма",
                "risk": "Низкий",
                "color": "🟢",
                "message": "Твоя талия в пределах нормы. Отличный результат!"
            }
        elif waist_cm < 88:
            return {
                "category": "Повышенная",
                "risk": "Средний",
                "color": "🟡",
                "message": "Талия превышает норму. Повышенный риск ССЗ."
            }
        else:
            return {
                "category": "Высокая",
                "risk": "Высокий",
                "color": "🔴",
                "message": "Талия значительно превышает норму! Консультация врача."
            }