"""
Аналитика: обнаружение паттернов, состояний и генерация инсайтов.
"""
import logging
import math
from typing import List, Tuple, Optional, Dict, Any
from datetime import timedelta

from db import Database, PatternsRepository
from .core import DailyAggregate, Pattern, Insight, StateDetection

logger = logging.getLogger(__name__)

# ===== КОНСТАНТЫ =====
MIN_CORRELATION = 0.3
MIN_SAMPLE_SIZE = 14
P_VALUE_THRESHOLD = 0.05
LAGS = [0, 1, 3, 5, 7]

METRIC_NAMES = {
    "sleep_hours": "продолжительность сна", "sleep_quality": "качество сна",
    "stress_level": "уровень стресса", "energy_morning": "утренняя энергия",
    "energy_evening": "вечерняя энергия", "steps": "шаги",
    "total_kcal": "калории", "total_protein_g": "белок",
    "water_ml": "вода", "weight_kg": "вес", "waist_cm": "талия"
}
STATE_NAMES = {
    "metabolic_adaptation": "Метаболическая адаптация",
    "body_recomposition": "Рекомпозиция тела ✨",
    "overtraining": "Перетренированность",
    "stress_plateau": "Стрессовое плато",
    "insulin_resistance": "Инсулинорезистентность",
}

# ===== УТИЛИТЫ =====
def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0.0, 1.0
    r = num / (den_x * den_y)
    if abs(r) < 1e-10:
        return r, 1.0
    t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else 100
    abs_t = abs(t)
    # Улучшенная оценка p-value (таблица t-распределения)
    if abs_t > 3.5: p = 0.001
    elif abs_t > 2.8: p = 0.01
    elif abs_t > 2.0: p = 0.05
    elif abs_t > 1.7: p = 0.1
    else: p = 0.5
    return r, p

def aggregates_to_dict(aggregates: List[DailyAggregate]) -> Dict[str, List[Optional[float]]]:
    metrics = ["sleep_hours", "sleep_quality", "stress_level", "energy_morning",
               "energy_evening", "steps", "total_kcal", "total_protein_g",
               "water_ml", "weight_kg", "waist_cm"]
    res = {m: [] for m in metrics}
    res["date"] = []
    for agg in aggregates:
        res["date"].append(agg.date)
        res["sleep_hours"].append(agg.sleep.hours)
        res["sleep_quality"].append(agg.sleep.quality)
        res["stress_level"].append(agg.stress)
        res["energy_morning"].append(agg.energy.morning)
        res["energy_evening"].append(agg.energy.evening)
        res["steps"].append(agg.activity.steps)
        res["total_kcal"].append(agg.nutrition.total_kcal)
        res["total_protein_g"].append(agg.nutrition.total_protein_g)
        res["water_ml"].append(agg.water_ml)
        res["weight_kg"].append(agg.measurements.weight_kg)
        res["waist_cm"].append(agg.measurements.waist_cm)
    return res

def get_lagged_pairs(data: Dict[str, List[Optional[float]]], metric_x: str, metric_y: str, lag: int):
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

# ===== PATTERN DETECTOR =====
class PatternDetector:
    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(self, user_id: int, aggregates: List[DailyAggregate]) -> List[Pattern]:
        if len(aggregates) < MIN_SAMPLE_SIZE:
            return []
        data = aggregates_to_dict(aggregates)
        detected = []
        for lag in LAGS:
            patterns = await self._analyze_correlations(user_id, data, lag)
            detected.extend(patterns)
        for p in detected:
            await self.patterns_repo.save_pattern(user_id, {
                "pattern_type": p.pattern_type, "metric_x": p.metric_x, "metric_y": p.metric_y,
                "correlation_r": p.correlation_r, "p_value": p.p_value, "lag_days": p.lag_days,
                "sample_size": p.sample_size, "effect_text": p.effect_text,
                "effect_direction": p.effect_direction,
            })
        return detected

    async def _analyze_correlations(self, user_id: int, data: dict, lag: int) -> List[Pattern]:
        patterns = []
        metrics = [k for k in data.keys() if k != "date"]
        for mx in metrics:
            for my in metrics:
                if mx == my:
                    continue
                xv, yv = get_lagged_pairs(data, mx, my, lag)
                if len(xv) < MIN_SAMPLE_SIZE:
                    continue
                r, p = pearson_correlation(xv, yv)
                if abs(r) >= MIN_CORRELATION and p < P_VALUE_THRESHOLD:
                    patterns.append(Pattern(
                        pattern_type="correlation",
                        metric_x=mx, metric_y=my,
                        correlation_r=r, p_value=p, lag_days=lag,
                        sample_size=len(xv),
                        effect_direction="positive" if r > 0 else "negative",
                        effect_text=generate_effect_text(mx, my, r, lag)
                    ))
        return patterns

# ===== STATE DETECTOR =====
class StateDetector:
    def detect_states(self, aggregates: List[DailyAggregate], profile: dict) -> List[StateDetection]:
        states = []
        for detector in [self._detect_metabolic_adaptation, self._detect_body_recomposition,
                         self._detect_overtraining, self._detect_stress_plateau,
                         lambda aggs: self._detect_insulin_resistance(aggs, profile)]:
            s = detector(aggregates)
            if s:
                states.append(s)
        return states

    def _detect_metabolic_adaptation(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14:
            return None
        indicators = []
        low_energy = sum(1 for a in aggregates[:14] if a.derived.avg_energy and a.derived.avg_energy < 5)
        if low_energy >= 5:
            indicators.append("энергия ниже 5/10 в течение 5+ дней")
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 7 and (max(weights) - min(weights)) < 0.5:
            indicators.append("вес стабилен 2+ недели")
        if len(indicators) >= 2:
            return StateDetection(
                state_type="metabolic_adaptation", detected=True,
                severity="high" if len(indicators) >= 3 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется диет-брейк на 5-7 дней на уровне поддержки.",
                emoji="🔄"
            )
        return None

    def _detect_body_recomposition(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14:
            return None
        indicators = []
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 2 and abs(weights[0] - weights[-1]) < 0.5:
            indicators.append("вес стабилен (±0.5 кг)")
        waists = [a.measurements.waist_cm for a in aggregates[:14] if a.measurements.waist_cm]
        if len(waists) >= 2 and (waists[0] - waists[-1]) >= 1:
            indicators.append(f"талия уменьшилась на {waists[0] - waists[-1]:.0f} см")
        if len(indicators) >= 2:
            return StateDetection(
                state_type="body_recomposition", detected=True, severity="positive",
                indicators=indicators,
                recommendation="Отлично! Это лучший сценарий — мышцы растут, жир уходит. НЕ снижай калории!",
                emoji="🎉"
            )
        return None

    def _detect_overtraining(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14:
            return None
        indicators = []
        low_energy = sum(1 for a in aggregates[:7] if a.derived.avg_energy and a.derived.avg_energy < 4)
        if low_energy >= 3:
            indicators.append("низкая энергия 3+ дня подряд")
        workout_days = sum(1 for a in aggregates[:7] if a.workout.type and a.workout.type != "none")
        if workout_days >= 4:
            indicators.append(f"тренировки {workout_days} раз за неделю")
        sq = [a.sleep.quality for a in aggregates[:7] if a.sleep.quality]
        if len(sq) >= 5:
            recent = sum(sq[:3])/3
            prev = sum(sq[3:6])/3 if len(sq) >= 6 else recent
            if recent < prev - 1:
                indicators.append("качество сна ухудшилось")
        steps = [a.activity.steps for a in aggregates[:7] if a.activity.steps]
        if len(steps) >= 5:
            if sum(steps[:3])/3 < sum(steps[3:6])/3 * 0.9:
                indicators.append("активность снизилась на 10%+")
        if len(indicators) >= 3:
            return StateDetection(
                state_type="overtraining", detected=True,
                severity="high" if len(indicators) >= 4 else "medium",
                indicators=indicators,
                recommendation="Возможна перетренированность. Рекомендуется 2-3 дня полного отдыха.",
                emoji="⚠️"
            )
        return None

    def _detect_stress_plateau(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 7:
            return None
        indicators = []
        high_stress = sum(1 for a in aggregates[:7] if a.stress and a.stress >= 7)
        if high_stress >= 5:
            indicators.append("высокий стресс 5+ дней")
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 3 and (max(weights[-3:]) - min(weights[-3:])) < 0.5:
            indicators.append("вес стабилен")
        if len(indicators) >= 2:
            return StateDetection(
                state_type="stress_plateau", detected=True, severity="medium",
                indicators=indicators,
                recommendation="Стресс вызывает задержку воды. НЕ снижай калории! Сосредоточься на управлении стрессом.",
                emoji="😰"
            )
        return None

    def _detect_insulin_resistance(self, aggregates: List[DailyAggregate], profile: dict) -> Optional[StateDetection]:
        if len(aggregates) < 7:
            return None
        indicators = []
        # WHR
        last_waist = last_hips = None
        for a in reversed(aggregates):
            if not last_waist and a.measurements.waist_cm: last_waist = a.measurements.waist_cm
            if not last_hips and a.measurements.hips_cm: last_hips = a.measurements.hips_cm
            if last_waist and last_hips: break
        if last_waist and last_hips:
            whr = last_waist / last_hips
            gender = profile.get("gender", "male")
            if (gender == "male" and whr > 0.90) or (gender == "female" and whr > 0.85):
                indicators.append(f"WHR {whr:.2f} (выше нормы)")
        # Частые приёмы пищи
        meals = [a.nutrition.meal_count for a in aggregates[:7] if a.nutrition.meal_count]
        if meals and sum(meals)/len(meals) > 5:
            indicators.append("частые приёмы пищи (>5 раз в день)")
        # Требуется минимум 2 индикатора (исправлено)
        if len(indicators) >= 2:
            return StateDetection(
                state_type="insulin_resistance", detected=True,
                severity="high" if len(indicators) >= 2 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется сократить окно питания до 8-10 часов, убрать перекусы.",
                emoji="🍬"
            )
        return None

# ===== INSIGHT GENERATOR =====
class InsightGenerator:
    def generate_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        # Сон
        if agg.sleep.hours:
            h = agg.sleep.hours
            if h < 6:
                insights.append(Insight("Недостаток сна", f"Ты спал всего {h}ч. Недосып снижает метаболизм на 8-12%.", "😴", 5, "sleep"))
            elif h < 7:
                insights.append(Insight("Лёгкий недосып", f"Ты спал {h}ч. Даже небольшой недосып снижает чувствительность к инсулину.", "😐", 3, "sleep"))
            if agg.sleep.quality and agg.sleep.quality <= 2:
                insights.append(Insight("Плохое качество сна", "Плохой сон нарушает выработку гормонов.", "😫", 4, "sleep"))
        # Энергия
        avg_e = agg.derived.avg_energy
        if avg_e:
            if avg_e <= 4:
                insights.append(Insight("Низкая энергия", "Возможно, пора сделать диет-брейк на 5-7 дней.", "⚡", 5, "energy"))
            elif avg_e >= 9:
                insights.append(Insight("Отличная энергия!", "Высокий уровень энергии говорит о хорошем восстановлении.", "💪", 1, "energy"))
        # Стресс
        if agg.stress and agg.stress >= 8:
            insights.append(Insight("Высокий стресс", "Хронический стресс повышает кортизол. Попробуй дыхательные практики.", "😰", 5, "stress"))
        # Белок
        if agg.derived.protein_per_kg and agg.derived.protein_per_kg < 1.2:
            insights.append(Insight("Мало белка", f"Ты съел {agg.derived.protein_per_kg:.1f}г белка на кг. Нужно 1.6-2.0г/кг.", "🍗", 4, "nutrition"))
        # Окно питания
        if agg.derived.eating_window_hours and agg.derived.eating_window_hours > 12:
            insights.append(Insight("Длинное окно питания", f"Окно питания {agg.derived.eating_window_hours:.0f}ч. Узкое окно (8-10ч) улучшает метаболизм.", "⏰", 3, "nutrition"))
        # Шаги
        if agg.activity.steps:
            steps = agg.activity.steps
            if steps < 5000:
                insights.append(Insight("Малая активность", f"Ты прошёл {steps:,} шагов. Увеличь до 8000-10000.", "👣", 4, "activity"))
            elif steps >= 10000:
                insights.append(Insight("Хорошая активность!", f"{steps:,} шагов — это ~300-500 ккал.", "🎉", 1, "activity"))
        # Тренировка
        if agg.workout.type and agg.workout.type != "none":
            if agg.workout.type == "strength":
                insights.append(Insight("Силовая тренировка", "Отличная силовая! Она сохраняет мышцы при дефиците.", "🏋️", 2, "workout"))
        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:5]