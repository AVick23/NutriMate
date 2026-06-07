"""
Обнаружение паттернов, состояний и генерация инсайтов.
"""
import logging
from typing import List, Optional, Dict, Any
from db import Database
from .core import (
    DailyAggregate, Pattern, Insight, StateDetection,
    MIN_CORRELATION, MIN_SAMPLE_SIZE, P_VALUE_THRESHOLD, LAGS,
    STATE_NAMES, METRIC_NAMES, spearman_correlation, aggregates_to_dict, generate_effect_text
)

logger = logging.getLogger(__name__)

# ==============================================================================
# РЕПОЗИТОРИЙ ПАТТЕРНОВ
# ==============================================================================
class PatternsRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save_pattern(self, user_id: int, pattern_data: Dict[str, Any]) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute("""
                SELECT id, confirmation_count FROM user_patterns
                WHERE user_id = ? AND metric_x = ? AND metric_y = ? AND lag_days = ?
            """, (user_id, pattern_data.get("metric_x"), pattern_data.get("metric_y"), pattern_data.get("lag_days", 0)))
            existing = await cursor.fetchone()

            if existing:
                await conn.execute("""
                    UPDATE user_patterns SET correlation_r = ?, p_value = ?, sample_size = ?, effect_text = ?,
                    effect_direction = ?, last_confirmed_at = CURRENT_TIMESTAMP, confirmation_count = confirmation_count + 1, is_active = 1
                    WHERE id = ?
                """, (pattern_data.get("correlation_r"), pattern_data.get("p_value"), pattern_data.get("sample_size"),
                      pattern_data.get("effect_text"), pattern_data.get("effect_direction"), existing["id"]))
                return existing["id"]
            else:
                cursor = await conn.execute("""
                    INSERT INTO user_patterns (user_id, pattern_type, metric_x, metric_y, correlation_r, p_value, lag_days, sample_size, effect_text, effect_direction)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, pattern_data.get("pattern_type"), pattern_data.get("metric_x"), pattern_data.get("metric_y"),
                      pattern_data.get("correlation_r"), pattern_data.get("p_value"), pattern_data.get("lag_days", 0),
                      pattern_data.get("sample_size"), pattern_data.get("effect_text"), pattern_data.get("effect_direction")))
                return cursor.lastrowid

    async def get_active_patterns(self, user_id: int) -> List[Dict[str, Any]]:
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM user_patterns WHERE user_id = ? AND is_active = 1
                ORDER BY ABS(correlation_r) DESC, confirmation_count DESC
            """, (user_id,))
            return [dict(row) for row in await cursor.fetchall()]


# ==============================================================================
# ДЕТЕКТОР ПАТТЕРНОВ
# ==============================================================================
class PatternDetector:
    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(self, user_id: int, aggregates: List[DailyAggregate]) -> List[Pattern]:
        if len(aggregates) < MIN_SAMPLE_SIZE:
            return []

        data = aggregates_to_dict(aggregates)
        detected_patterns = []

        for lag in LAGS:
            patterns = await self._analyze_correlations(user_id, data, lag)
            detected_patterns.extend(patterns)

        for pattern in detected_patterns:
            await self.patterns_repo.save_pattern(user_id, {
                "pattern_type": pattern.pattern_type, "metric_x": pattern.metric_x, "metric_y": pattern.metric_y,
                "correlation_r": pattern.correlation_r, "p_value": pattern.p_value, "lag_days": pattern.lag_days,
                "sample_size": pattern.sample_size, "effect_text": pattern.effect_text, "effect_direction": pattern.effect_direction,
            })
        return detected_patterns

    async def _analyze_correlations(self, user_id: int, data: dict, lag: int) -> List[Pattern]:
        patterns = []
        metrics = [k for k in data.keys() if k != "date"]

        for metric_x in metrics:
            for metric_y in metrics:
                if metric_x == metric_y:
                    continue

                x_vals, y_vals = self._get_lagged_pairs(data, metric_x, metric_y, lag)
                if len(x_vals) < MIN_SAMPLE_SIZE:
                    continue

                # 🎯 Используем Спирмена вместо Пирсона для нелинейных связей
                r, p_value = spearman_correlation(x_vals, y_vals)

                if abs(r) >= MIN_CORRELATION and p_value < P_VALUE_THRESHOLD:
                    # 🎯 Расчет Confidence Score (0-100) на основе силы связи и размера выборки
                    confidence = min(100, int((abs(r) * 0.7 + (len(x_vals) / 30.0) * 0.3) * 100))
                    
                    patterns.append(Pattern(
                        pattern_type="spearman_correlation", metric_x=metric_x, metric_y=metric_y,
                        correlation_r=r, p_value=p_value, lag_days=lag, sample_size=len(x_vals),
                        effect_direction="positive" if r > 0 else "negative",
                        effect_text=generate_effect_text(metric_x, metric_y, r, lag),
                        confidence_score=confidence
                    ))
        return patterns

    def _get_lagged_pairs(self, data: dict, metric_x: str, metric_y: str, lag: int):
        x_vals, y_vals = data.get(metric_x, []), data.get(metric_y, [])
        if not x_vals or not y_vals: return [], []
        if lag == 0:
            pairs = [(x, y) for x, y in zip(x_vals, y_vals) if x is not None and y is not None]
        else:
            pairs = [(x_vals[i], y_vals[i + lag]) for i in range(len(x_vals) - lag) if x_vals[i] is not None and y_vals[i + lag] is not None]
        return [p[0] for p in pairs], [p[1] for p in pairs]


# ==============================================================================
# ДЕТЕКТОР СОСТОЯНИЙ (Балльная система)
# ==============================================================================
class StateDetector:
    def detect_states(self, aggregates: List[DailyAggregate], profile: dict) -> List[StateDetection]:
        states = []
        detectors = [
            self._detect_metabolic_adaptation, self._detect_body_recomposition,
            self._detect_overtraining, self._detect_stress_plateau,
            lambda aggs: self._detect_insulin_resistance(aggs, profile),
        ]
        for detector in detectors:
            state = detector(aggregates)
            if state: states.append(state)
        return states

    def _detect_metabolic_adaptation(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14: return None
        risk_score, indicators = 0, []

        low_energy = sum(1 for a in aggregates[:14] if a.derived.avg_energy and a.derived.avg_energy < 5)
        if low_energy >= 5: risk_score += 3; indicators.append("энергия ниже 5/10 в течение 5+ дней")
        elif low_energy >= 3: risk_score += 1

        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 7 and (max(weights) - min(weights)) < 0.5:
            risk_score += 2; indicators.append("вес стабилен 2+ недели")

        if risk_score >= 4:
            return StateDetection(state_type="metabolic_adaptation", detected=True, severity="high" if risk_score >= 5 else "medium",
                                  risk_score=risk_score, indicators=indicators,
                                  recommendation="Рекомендуется диет-брейк на 5-7 дней на уровне поддержки для восстановления метаболизма.", emoji="🔄")
        return None

    def _detect_body_recomposition(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14: return None
        risk_score, indicators = 0, []

        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 2 and abs(weights[0] - weights[-1]) < 0.5:
            risk_score += 2; indicators.append("вес стабилен (±0.5 кг)")

        waists = [a.measurements.waist_cm for a in aggregates[:14] if a.measurements.waist_cm]
        if len(waists) >= 2 and (waists[0] - waists[-1]) >= 1.0:
            risk_score += 3; indicators.append(f"талия уменьшилась на {waists[0] - waists[-1]:.1f} см")

        if risk_score >= 4:
            return StateDetection(state_type="body_recomposition", detected=True, severity="positive", risk_score=risk_score,
                                  indicators=indicators, recommendation="Отличный сценарий! Жир уходит, мышцы сохраняются. НЕ снижай калории, держи темп.", emoji="🎉")
        return None

    def _detect_overtraining(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14: return None
        risk_score, indicators = 0, []

        low_energy = sum(1 for a in aggregates[:7] if a.derived.avg_energy and a.derived.avg_energy < 4)
        if low_energy >= 3: risk_score += 3; indicators.append("низкая энергия 3+ дня подряд")
        elif low_energy >= 1: risk_score += 1

        workout_days = sum(1 for a in aggregates[:7] if a.workout.type and a.workout.type != "none")
        if workout_days >= 5: risk_score += 3; indicators.append(f"тренировки {workout_days} раз за неделю")
        elif workout_days >= 4: risk_score += 2; indicators.append(f"тренировки {workout_days} раз за неделю")

        sleep_quality = [a.sleep.quality for a in aggregates[:7] if a.sleep.quality]
        if len(sleep_quality) >= 5:
            recent = sum(sleep_quality[:3]) / 3
            prev = sum(sleep_quality[3:6]) / 3 if len(sleep_quality) >= 6 else recent
            if recent < prev - 1: risk_score += 2; indicators.append("качество сна ухудшилось")

        if risk_score >= 5:
            return StateDetection(state_type="overtraining", detected=True, severity="high" if risk_score >= 7 else "medium",
                                  risk_score=risk_score, indicators=indicators,
                                  recommendation="Возможна перетренированность. Рекомендуется 2-3 дня полного отдыха и снижение интенсивности.", emoji="⚠️")
        return None

    def _detect_stress_plateau(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 7: return None
        risk_score, indicators = 0, []

        high_stress = sum(1 for a in aggregates[:7] if a.stress and a.stress >= 7)
        if high_stress >= 5: risk_score += 3; indicators.append("высокий стресс 5+ дней")

        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 3 and (max(weights[-3:]) - min(weights[-3:])) < 0.5:
            risk_score += 2; indicators.append("вес стабилен")

        if risk_score >= 4:
            return StateDetection(state_type="stress_plateau", detected=True, severity="medium", risk_score=risk_score,
                                  indicators=indicators, recommendation="Стресс вызывает задержку воды. НЕ снижай калории! Сосредоточься на управлении стрессом.", emoji="😰")
        return None

    def _detect_insulin_resistance(self, aggregates: List[DailyAggregate], profile: dict) -> Optional[StateDetection]:
        if len(aggregates) < 7: return None
        risk_score, indicators = 0, []

        last_waist, last_hips = None, None
        for a in reversed(aggregates):
            if not last_waist and a.measurements.waist_cm: last_waist = a.measurements.waist_cm
            if not last_hips and a.measurements.hips_cm: last_hips = a.measurements.hips_cm
            if last_waist and last_hips: break

        if last_waist and last_hips:
            whr = last_waist / last_hips
            gender = profile.get("gender", "male")
            if (gender == "male" and whr > 0.90) or (gender == "female" and whr > 0.85):
                risk_score += 3; indicators.append(f"WHR {whr:.2f} (выше нормы)")

        meals = [a.nutrition.meal_count for a in aggregates[:7] if a.nutrition.meal_count]
        if meals and (sum(meals) / len(meals)) > 5:
            risk_score += 2; indicators.append("частые приёмы пищи (>5 раз в день)")

        if risk_score >= 4:
            return StateDetection(state_type="insulin_resistance", detected=True, severity="high" if risk_score >= 5 else "medium",
                                  risk_score=risk_score, indicators=indicators,
                                  recommendation="Рекомендуется сократить окно питания до 8-10 часов, убрать перекусы и увеличить белок.", emoji="🍬")
        return None


# ==============================================================================
# ГЕНЕРАТОР ИНСАЙТОВ
# ==============================================================================
class InsightGenerator:
    def generate_insights(self, aggregated: DailyAggregate, profile: dict, patterns: List[Pattern]) -> List[Insight]:
        insights = []
        goal = profile.get("goal", "maintenance")

        # 🎯 Инсайт на основе паттерна (Микро-привычка)
        high_conf_patterns = [p for p in patterns if getattr(p, 'confidence_score', 0) > 70]
        if high_conf_patterns:
            p = high_conf_patterns[0]
            insights.append(Insight(
                title="🧠 Я заметил закономерность",
                message=f"Когда {METRIC_NAMES.get(p.metric_x, p.metric_x)} в норме, {METRIC_NAMES.get(p.metric_y, p.metric_y)} улучшается. Попробуй сделать на этом фокус сегодня.",
                emoji="💡", priority=5, category="pattern"
            ))

        insights.extend(self._generate_sleep_insights(aggregated))
        insights.extend(self._generate_energy_insights(aggregated))
        insights.extend(self._generate_stress_insights(aggregated))
        insights.extend(self._generate_nutrition_insights(aggregated, goal))
        insights.extend(self._generate_activity_insights(aggregated))
        insights.extend(self._generate_workout_insights(aggregated))

        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:3]

    def _generate_sleep_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        if agg.sleep.hours is not None:
            if agg.sleep.hours < 6:
                insights.append(Insight(title="Недостаток сна", message=f"Ты спал всего {agg.sleep.hours}ч. Недосып снижает метаболизм на 8-12% и повышает голод.", emoji="😴", priority=5, category="sleep"))
            elif agg.sleep.hours > 9:
                insights.append(Insight(title="Долгий сон", message=f"Ты спал {agg.sleep.hours}ч. Это может быть признаком перетренированности или нехватки энергии.", emoji="😴", priority=2, category="sleep"))
        if agg.sleep.quality and agg.sleep.quality <= 2:
            insights.append(Insight(title="Плохое качество сна", message="Плохой сон нарушает выработку гормонов. Попробуй тёплую ванну или медитацию перед сном.", emoji="😫", priority=4, category="sleep"))
        return insights

    def _generate_energy_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        avg_energy = agg.derived.avg_energy
        if avg_energy is not None:
            if avg_energy <= 4:
                insights.append(Insight(title="Низкая энергия", message="Низкая энергия может быть признаком метаболической адаптации. Возможно, пора сделать диет-брейк.", emoji="⚡", priority=5, category="energy"))
            elif avg_energy >= 9:
                insights.append(Insight(title="Отличная энергия!", message="Высокий уровень энергии говорит о хорошем восстановлении. Отличная работа!", emoji="💪", priority=1, category="energy"))
        return insights

    def _generate_stress_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        if agg.stress is not None:
            if agg.stress >= 8:
                insights.append(Insight(title="Высокий стресс", message="Хронический стресс повышает кортизол, который задерживает воду. Попробуй дыхательные практики.", emoji="😰", priority=5, category="stress"))
        return insights

    def _generate_nutrition_insights(self, agg: DailyAggregate, goal: str) -> List[Insight]:
        insights = []
        prot_per_kg = agg.derived.protein_per_kg
        if prot_per_kg is not None:
            target = 1.8 if goal == "cutting" else 1.6
            if prot_per_kg < target:
                insights.append(Insight(title="Мало белка", message=f"Сейчас {prot_per_kg:.1f}г/кг. На {goal} нужно минимум {target}г/кг, чтобы не терять мышцы.", emoji="🍗", priority=4, category="nutrition"))

        window = agg.derived.eating_window_hours
        if window and window > 12:
            insights.append(Insight(title="Длинное окно питания", message=f"Приём пищи растянут на {window:.0f}ч. Узкое окно (8-10ч) улучшает чувствительность к инсулину.", emoji="⏰", priority=3, category="nutrition"))

        last_meal = agg.derived.last_meal_hour
        if last_meal and last_meal >= 21:
            insights.append(Insight(title="Поздний ужин", message=f"Последний приём пищи в {last_meal}:00. Поздняя еда снижает окисление жиров и нарушает циркадные ритмы.", emoji="🌙", priority=3, category="nutrition"))
        return insights

    def _generate_activity_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        steps = agg.activity.steps
        if steps is not None:
            if steps < 5000:
                insights.append(Insight(title="Малая активность", message=f"Ты прошёл всего {steps:,} шагов. Увеличение NEAT до 8000-10000 шагов ускорит метаболизм.", emoji="👣", priority=4, category="activity"))
            elif steps >= 10000:
                insights.append(Insight(title="Хорошая активность!", message=f"Отлично! {steps:,} шагов — это ~300-500 ккал дополнительного расхода.", emoji="🎉", priority=1, category="activity"))
        return insights

    def _generate_workout_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        if agg.workout.type and agg.workout.type != "none":
            if agg.workout.type == "strength":
                insights.append(Insight(title="Силовая тренировка", message="Отличная силовая! Она не только сжигает калории, но и сохраняет мышцы при дефиците.", emoji="🏋️", priority=2, category="workout"))
            elif agg.workout.type == "cardio":
                insights.append(Insight(title="Кардио тренировка", message=f"{agg.workout.duration_min} минут кардио. Добавь силовые для лучшего сохранения мышечной массы.", emoji="🏃", priority=2, category="workout"))
        return insights