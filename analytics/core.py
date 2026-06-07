"""
Базовые модели данных, константы и утилиты для аналитики.
"""
import logging
import math
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ==============================================================================
# КОНСТАНТЫ
# ==============================================================================
MIN_CORRELATION = 0.3
MIN_SAMPLE_SIZE = 14
P_VALUE_THRESHOLD = 0.05
LAGS = [0, 1, 3, 5, 7]

METRIC_NAMES = {
    "sleep_hours": "продолжительность сна",
    "sleep_quality": "качество сна",
    "stress_level": "уровень стресса",
    "energy_morning": "утренняя энергия",
    "energy_evening": "вечерняя энергия",
    "steps": "количество шагов",
    "total_kcal": "потребление калорий",
    "total_protein_g": "потребление белка",
    "water_ml": "потребление воды",
    "weight_kg": "вес",
    "waist_cm": "объём талии",
    "hips_cm": "объём бёдер",
}

STATE_NAMES = {
    "metabolic_adaptation": "Метаболическая адаптация",
    "body_recomposition": "Рекомпозиция тела ✨",
    "overtraining": "Перетренированность",
    "stress_plateau": "Стрессовое плато",
    "insulin_resistance": "Инсулинорезистентность",
}

# ==============================================================================
# МОДЕЛИ ДАННЫХ
# ==============================================================================
@dataclass
class NutritionData:
    total_kcal: int = 0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0
    meal_count: int = 0
    first_meal_at: Optional[datetime] = None
    last_meal_at: Optional[datetime] = None

@dataclass
class SleepData:
    hours: Optional[float] = None
    quality: Optional[int] = None
    awakenings: Optional[int] = None

@dataclass
class EnergyData:
    morning: Optional[int] = None
    evening: Optional[int] = None
    @property
    def avg(self) -> Optional[float]:
        if self.morning is not None and self.evening is not None:
            return (self.morning + self.evening) / 2
        return None

@dataclass
class ActivityData:
    steps: Optional[int] = None
    hours_on_feet: Optional[float] = None

@dataclass
class WorkoutData:
    type: Optional[str] = None
    duration_min: Optional[int] = None
    intensity: Optional[int] = None

@dataclass
class MeasurementsData:
    weight_kg: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    arm_cm: Optional[float] = None
    thigh_cm: Optional[float] = None

@dataclass
class DerivedMetrics:
    eating_window_hours: Optional[float] = None
    last_meal_hour: Optional[int] = None
    protein_per_kg: Optional[float] = None
    water_per_kg: Optional[float] = None
    avg_energy: Optional[float] = None

@dataclass
class DailyAggregate:
    date: date
    user_id: int
    nutrition: NutritionData = field(default_factory=NutritionData)
    water_ml: int = 0
    measurements: MeasurementsData = field(default_factory=MeasurementsData)
    sleep: SleepData = field(default_factory=SleepData)
    energy: EnergyData = field(default_factory=EnergyData)
    stress: Optional[int] = None
    activity: ActivityData = field(default_factory=ActivityData)
    workout: WorkoutData = field(default_factory=WorkoutData)
    derived: DerivedMetrics = field(default_factory=DerivedMetrics)
    base_tdee: Optional[int] = None
    sleep_modifier: float = 1.0
    energy_modifier: float = 1.0
    stress_modifier: float = 1.0
    activity_modifier: float = 1.0
    window_modifier: float = 1.0
    workout_bonus: int = 0
    adjusted_tdee: Optional[int] = None
    confidence_score: int = 100

@dataclass
class Pattern:
    pattern_type: str = "correlation"
    metric_x: str = ""
    metric_y: str = ""
    correlation_r: Optional[float] = None
    p_value: Optional[float] = None
    lag_days: int = 0
    sample_size: int = 0
    effect_text: str = ""
    effect_direction: str = "neutral"

@dataclass
class Insight:
    title: str
    message: str
    emoji: str
    priority: int
    category: str

@dataclass
class StateDetection:
    state_type: str
    detected: bool
    severity: str
    indicators: List[str]
    recommendation: str
    emoji: str

# ==============================================================================
# УТИЛИТЫ
# ==============================================================================
def safe_average(values: List[Any]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    return sum(filtered) / len(filtered) if filtered else None

def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denom_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    denom_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))
    if denom_x == 0 or denom_y == 0:
        return 0.0, 1.0
    r = numerator / (denom_x * denom_y)
    if abs(r) < 1e-10:
        return r, 1.0
    t_stat = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else 100
    df = n - 2
    if df > 30:
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
    else:
        abs_t = abs(t_stat)
        if abs_t > 3.5:
            p_value = 0.001
        elif abs_t > 2.8:
            p_value = 0.01
        elif abs_t > 2.0:
            p_value = 0.05
        elif abs_t > 1.7:
            p_value = 0.1
        else:
            p_value = 0.5
    return r, p_value

def get_lagged_pairs(data: Dict[str, List[Optional[float]]], metric_x: str, metric_y: str, lag: int) -> Tuple[List[float], List[float]]:
    x_vals = data.get(metric_x, [])
    y_vals = data.get(metric_y, [])
    if not x_vals or not y_vals:
        return [], []
    if lag == 0:
        pairs = [(x, y) for x, y in zip(x_vals, y_vals) if x is not None and y is not None]
    else:
        pairs = []
        for i in range(len(x_vals) - lag):
            x = x_vals[i]
            y = y_vals[i + lag]
            if x is not None and y is not None:
                pairs.append((x, y))
    if not pairs:
        return [], []
    return [p[0] for p in pairs], [p[1] for p in pairs]

def aggregates_to_dict(aggregates: List[DailyAggregate]) -> Dict[str, List[Optional[float]]]:
    metrics = ["sleep_hours", "sleep_quality", "stress_level", "energy_morning", "energy_evening", "steps", "total_kcal", "total_protein_g", "water_ml", "weight_kg", "waist_cm"]
    result = {metric: [] for metric in metrics}
    result["date"] = []
    for agg in aggregates:
        result["date"].append(agg.date)
        result["sleep_hours"].append(agg.sleep.hours)
        result["sleep_quality"].append(agg.sleep.quality)
        result["stress_level"].append(agg.stress)
        result["energy_morning"].append(agg.energy.morning)
        result["energy_evening"].append(agg.energy.evening)
        result["steps"].append(agg.activity.steps)
        result["total_kcal"].append(agg.nutrition.total_kcal)
        result["total_protein_g"].append(agg.nutrition.total_protein_g)
        result["water_ml"].append(agg.water_ml)
        result["weight_kg"].append(agg.measurements.weight_kg)
        result["waist_cm"].append(agg.measurements.waist_cm)
    return result

def generate_effect_text(metric_x: str, metric_y: str, r: float, lag: int) -> str:
    x_name = METRIC_NAMES.get(metric_x, metric_x)
    y_name = METRIC_NAMES.get(metric_y, metric_y)
    direction = "увеличивает" if r > 0 else "уменьшает"
    strength = "сильно" if abs(r) > 0.7 else "умеренно" if abs(r) > 0.5 else "слабо"
    if lag == 0:
        return f"{x_name} {direction} {y_name} (корреляция {strength})"
    elif lag == 1:
        return f"{x_name} сегодня {direction} {y_name} завтра"
    else:
        return f"{x_name} влияет на {y_name} через {lag} дня"

# ==============================================================================
# ФОРМАТИРОВАНИЕ (из utils.py)
# ==============================================================================
def format_metrics_summary(metrics: Dict[str, Any]) -> str:
    lines = []
    sleep_hours = metrics.get("sleep_hours")
    sleep_quality = metrics.get("sleep_quality")
    sleep_awakenings = metrics.get("sleep_awakenings")
    if sleep_hours is not None:
        quality_stars = "⭐" * sleep_quality if sleep_quality else ""
        awakenings_text = {0: "нет", 1: "1 раз", 2: "2 раза", 3: "3+ раз"}.get(sleep_awakenings, "")
        lines.append(f"😴 Сон: {sleep_hours}ч {quality_stars} {awakenings_text}")
    else:
        lines.append("😴 Сон:  не заполнено")
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
    stress = metrics.get("stress_level")
    if stress is not None:
        lines.append(f"😰 Стресс: {stress}/10")
    else:
        lines.append("😰 Стресс: ❌ не заполнено")
    steps = metrics.get("steps")
    hours_on_feet = metrics.get("hours_on_feet")
    if steps is not None:
        lines.append(f"👣 Шаги: {steps:,}")
    if hours_on_feet is not None:
        lines.append(f"👣 Часы на ногах: {hours_on_feet}ч")
    if steps is None and hours_on_feet is None:
        lines.append("👣 Активность: ❌ не заполнено")
    workout_type = metrics.get("workout_type")
    workout_duration = metrics.get("workout_duration")
    workout_intensity = metrics.get("workout_intensity")
    if workout_type and workout_type != "none":
        type_names = {"strength": "силовая", "cardio": "кардио", "yoga": "йога", "walk": "прогулка", "swim": "плавание"}
        type_text = type_names.get(workout_type, workout_type)
        intensity_text = f" ({workout_intensity}/10)" if workout_intensity else ""
        duration_text = f", {workout_duration}мин" if workout_duration else ""
        lines.append(f"💪 Тренировка: {type_text}{duration_text}{intensity_text}")
    else:
        lines.append("💪 Тренировка: ❌ не было или не заполнено")
    return "\n".join(lines)

def format_insights(insights: List[Any], max_count: int = 5) -> str:
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
    if not insights:
        return ""
    lines = []
    for insight in insights[:max_count]:
        msg = insight.message[:120] + "..." if len(insight.message) > 120 else insight.message
        lines.append(f"{insight.emoji} <b>{insight.title}</b>\n   {msg}")
    return "\n\n".join(lines)

def format_patterns(patterns: List[Any], max_count: int = 5) -> str:
    if not patterns:
        return "🔍 <b>Паттерны ещё не обнаружены</b>\n\nДля анализа паттернов нужно минимум <b>14 дней</b> данных.\nЗаполняй метрики каждый день, и я найду уникальные закономерности!"
    lines = [f"🔍 <b>Обнаружено паттернов: {len(patterns)}</b>\n"]
    for i, pattern in enumerate(patterns[:max_count], 1):
        emoji = "📈" if pattern.effect_direction == "positive" else "📉"
        r_abs = abs(pattern.correlation_r) if pattern.correlation_r else 0
        if r_abs > 0.7:
            strength = "💪 сильная"
        elif r_abs > 0.5:
            strength = "🔹 умеренная"
        else:
            strength = "◇ слабая"
        lag_text = ""
        if pattern.lag_days == 1:
            lag_text = " (на следующий день)"
        elif pattern.lag_days > 1:
            lag_text = f" (через {pattern.lag_days} дн.)"
        lines.append(f"{i}. {emoji} <b>{pattern.effect_text}</b>{lag_text}\n   Связь {strength} (r={pattern.correlation_r:.2f}, подтверждений: {pattern.sample_size})")
        if i < len(patterns[:max_count]):
            lines.append("")
    return "\n".join(lines)

def format_states(states: List[Any]) -> str:
    active_states = [s for s in states if s.detected]
    if not active_states:
        return "✅ <b>Состояний не обнаружено</b>\n\nВсе показатели в норме. Продолжай в том же духе! 💪"
    lines = [f"🧬 <b>Обнаружено состояний: {len(active_states)}</b>\n"]
    for state in active_states:
        severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "positive": "✨"}.get(state.severity, "⚪")
        lines.append(f"{state.emoji} <b>{state_name_ru(state.state_type)}</b> {severity_emoji}")
        if state.indicators:
            lines.append("    <i>Признаки:</i>")
            for indicator in state.indicators[:3]:
                lines.append(f"   • {indicator}")
        lines.append(f"\n   💡 {state.recommendation}")
        lines.append("")
    return "\n".join(lines)

def state_name_ru(state_type: str) -> str:
    names = {"metabolic_adaptation": "Метаболическая адаптация", "body_recomposition": "Рекомпозиция тела", "overtraining": "Перетренированность", "stress_plateau": "Стрессовое плато", "insulin_resistance": "Инсулинорезистентность"}
    return names.get(state_type, state_type)

def format_macro_balance(agg: Any) -> str:
    total_kcal = agg.nutrition.total_kcal
    if not total_kcal or total_kcal <= 0:
        return "<i>Нет данных о питании</i>"
    protein_kcal = agg.nutrition.total_protein_g * 4
    fat_kcal = agg.nutrition.total_fat_g * 9
    carbs_kcal = agg.nutrition.total_carbs_g * 4
    protein_pct = (protein_kcal / total_kcal) * 100
    fat_pct = (fat_kcal / total_kcal) * 100
    carbs_pct = (carbs_kcal / total_kcal) * 100
    def bar(pct: float, length: int = 10) -> str:
        filled = int(pct / 100 * length)
        return "▰" * filled + "▱" * (length - filled)
    lines = ["<b>⚖️ Баланс БЖУ:</b>", f"🍗 Белки: {bar(protein_pct)} {protein_pct:.0f}% ({agg.nutrition.total_protein_g:.0f}г)", f"🥑 Жиры: {bar(fat_pct)} {fat_pct:.0f}% ({agg.nutrition.total_fat_g:.0f}г)", f"🍚 Углеводы: {bar(carbs_pct)} {carbs_pct:.0f}% ({agg.nutrition.total_carbs_g:.0f}г)"]
    return "\n".join(lines)

def format_forecast(aggregates: List[Any], profile: Dict[str, Any]) -> str:
    if len(aggregates) < 7:
        return "🔮 <b>Прогноз</b>\n\n<i>Недостаточно данных. Нужно минимум 7 дней для прогноза.</i>"
    weights = [a.measurements.weight_kg for a in aggregates if a.measurements.weight_kg]
    if len(weights) < 3:
        return "🔮 <b>Прогноз</b>\n\n<i>Недостаточно данных о весе для прогноза.</i>"
    current_weight = weights[-1]
    target_weight = profile.get("target_weight")
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
                target_date = date.today() + __import__('datetime').timedelta(days=days_to_goal)
                lines.append(f"\n📅 При текущем темпе ({weekly_rate:+.2f} кг/нед):")
                lines.append(f"   Цель будет достигнута через <b>{days_to_goal} дней</b>")
                lines.append(f"   Примерная дата: <b>{target_date.strftime('%d.%m.%Y')}</b>")
            else:
                lines.append("\n✨ <b>Цель уже достигнута!</b>")
        else:
            lines.append("\n⏸️ <i>Темп изменений слишком мал для прогноза</i>")
    else:
        lines.append("\n⚙️ <i>Целевой вес не установлен в профиле</i>")
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

def format_best_day(aggregates: List[Any]) -> str:
    if len(aggregates) < 3:
        return "🏆 <b>Лучший день</b>\n\n<i>Недостаточно данных. Заполняй метрики минимум 3 дня.</i>"
    scored_days = []
    for agg in aggregates:
        score = 0
        details = []
        if agg.derived.avg_energy:
            energy_score = agg.derived.avg_energy
            score += energy_score
            details.append(f"⚡ Энергия: {energy_score:.1f}/10")
        if agg.activity.steps:
            steps_score = min(agg.activity.steps / 1000, 10)
            score += steps_score
            details.append(f"👣 Шаги: {agg.activity.steps:,}")
        if agg.sleep.hours:
            sleep_score = min(agg.sleep.hours, 10)
            score += sleep_score
            details.append(f"😴 Сон: {agg.sleep.hours:.1f}ч")
        if agg.sleep.quality:
            score += agg.sleep.quality
        if agg.stress:
            score -= (agg.stress - 5)
        if agg.derived.protein_per_kg and agg.derived.protein_per_kg >= 1.6:
            score += 3
            details.append(f"🍗 Белок: {agg.derived.protein_per_kg:.1f}г/кг")
        scored_days.append((score, agg, details))
    scored_days.sort(key=lambda x: x[0], reverse=True)
    best_score, best_agg, best_details = scored_days[0]
    avg_score = sum(s[0] for s in scored_days) / len(scored_days)
    lines = ["🏆 <b>Твой лучший день</b>\n"]
    lines.append(f"📅 <b>{best_agg.date.strftime('%d.%m.%Y')}</b>")
    lines.append(f"⭐ Скор: <b>{best_score:.1f}</b> (среднее: {avg_score:.1f})\n")
    lines.append("<b>Формула успеха:</b>")
    for detail in best_details:
        lines.append(f"• {detail}")
    lines.append("\n💡 <i>Попробуй повторить эту формулу! Это твой персональный рецепт хорошего дня.</i>")
    return "\n".join(lines)

def format_tdee_modifiers(agg: Any, base_tdee: int) -> str:
    lines = ["<b>⚡ Как рассчитан TDEE:</b>\n"]
    lines.append(f"📊 Базовый TDEE: <b>{base_tdee}</b> ккал\n")
    modifiers = [("😴 Сон", agg.sleep_modifier), ("⚡ Энергия", agg.energy_modifier), ("😰 Стресс", agg.stress_modifier), ("👣 Активность", agg.activity_modifier), ("⏰ Окно питания", agg.window_modifier)]
    for name, mod in modifiers:
        if mod != 1.0:
            change_pct = (mod - 1.0) * 100
            emoji = "📈" if change_pct > 0 else "📉"
            lines.append(f"{emoji} {name}: ×{mod:.3f} ({change_pct:+.1f}%)")
    if agg.workout_bonus > 0:
        lines.append(f"💪 Тренировка: +{agg.workout_bonus} ккал")
    lines.append(f"\n🎯 <b>Итог: {agg.adjusted_tdee}</b> ккал")
    if agg.confidence_score < 100:
        lines.append(f"\n📊 Точность: <b>{agg.confidence_score}%</b> (заполни больше метрик для точности)")
    return "\n".join(lines)

def get_default_metrics() -> Dict[str, Any]:
    return {"sleep_hours": None, "sleep_quality": None, "sleep_awakenings": None, "energy_morning": None, "energy_evening": None, "stress_level": None, "steps": None, "hours_on_feet": None, "workout_type": None, "workout_duration": None, "workout_intensity": None, "hunger_before": None, "hunger_after": None, "digestion_bristol": None, "cycle_day": None, "notes": None}

def get_session_type_by_hour() -> Optional[str]:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 18 <= hour < 23:
        return "evening"
    return None

def split_long_message(text: str, max_length: int = 4000) -> list:
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