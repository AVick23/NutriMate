"""
Обнаружение паттернов, состояний и генерация инсайтов.
"""
import logging
from typing import List, Optional
from db import Database, PatternsRepository
from .core import (
    DailyAggregate, Pattern, Insight, StateDetection,
    MIN_CORRELATION, MIN_SAMPLE_SIZE, P_VALUE_THRESHOLD, LAGS,
    STATE_NAMES, METRIC_NAMES,
    pearson_correlation, get_lagged_pairs, aggregates_to_dict, generate_effect_text
)

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Обнаруживает корреляции между метриками с разными лагами.
    """

    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(
        self,
        user_id: int,
        aggregates: List[DailyAggregate]
    ) -> List[Pattern]:
        """
        Обнаруживает паттерны на основе агрегированных данных.
        """
        if len(aggregates) < MIN_SAMPLE_SIZE:
            logger.debug(f"Not enough data for user {user_id}: {len(aggregates)} days")
            return []

        data = aggregates_to_dict(aggregates)
        detected_patterns = []

        for lag in LAGS:
            patterns = await self._analyze_correlations(user_id, data, lag)
            detected_patterns.extend(patterns)

        for pattern in detected_patterns:
            await self.patterns_repo.save_pattern(user_id, {
                "pattern_type": pattern.pattern_type,
                "metric_x": pattern.metric_x,
                "metric_y": pattern.metric_y,
                "correlation_r": pattern.correlation_r,
                "p_value": pattern.p_value,
                "lag_days": pattern.lag_days,
                "sample_size": pattern.sample_size,
                "effect_text": pattern.effect_text,
                "effect_direction": pattern.effect_direction,
            })

        return detected_patterns

    async def _analyze_correlations(
        self,
        user_id: int,
        data: dict,
        lag: int
    ) -> List[Pattern]:
        """Анализирует корреляции между метриками с заданным лагом."""
        patterns = []
        metrics = list(data.keys())
        if "date" in metrics:
            metrics.remove("date")

        for metric_x in metrics:
            for metric_y in metrics:
                if metric_x == metric_y:
                    continue

                x_vals, y_vals = get_lagged_pairs(data, metric_x, metric_y, lag)

                if len(x_vals) < MIN_SAMPLE_SIZE:
                    continue

                r, p_value = pearson_correlation(x_vals, y_vals)

                if abs(r) >= MIN_CORRELATION and p_value < P_VALUE_THRESHOLD:
                    pattern = Pattern(
                        pattern_type="correlation",
                        metric_x=metric_x,
                        metric_y=metric_y,
                        correlation_r=r,
                        p_value=p_value,
                        lag_days=lag,
                        sample_size=len(x_vals),
                        effect_direction="positive" if r > 0 else "negative",
                        effect_text=generate_effect_text(metric_x, metric_y, r, lag),
                    )
                    patterns.append(pattern)

        return patterns


class StateDetector:
    """
    Определяет сложные состояния на основе правил.
    """

    def detect_states(
        self,
        aggregates: List[DailyAggregate],
        profile: dict
    ) -> List[StateDetection]:
        """Анализирует агрегированные данные и возвращает обнаруженные состояния."""
        states = []

        detectors = [
            self._detect_metabolic_adaptation,
            self._detect_body_recomposition,
            self._detect_overtraining,
            self._detect_stress_plateau,
            lambda aggs: self._detect_insulin_resistance(aggs, profile)
        ]

        for detector in detectors:
            state = detector(aggregates)
            if state:
                states.append(state)

        return states

    def _detect_metabolic_adaptation(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """Метаболическая адаптация: снижение BMR при длительном дефиците."""
        if len(aggregates) < 14:
            return None

        indicators = []

        # 1. Низкая энергия 5+ дней
        low_energy_days = sum(
            1 for agg in aggregates[:14]
            if agg.derived.avg_energy and agg.derived.avg_energy < 5
        )
        if low_energy_days >= 5:
            indicators.append("энергия ниже 5/10 в течение 5+ дней")

        # 2. Плато веса 14+ дней
        weights = [agg.measurements.weight_kg for agg in aggregates[:14] if agg.measurements.weight_kg]
        if len(weights) >= 7:
            weight_change = max(weights) - min(weights)
            if abs(weight_change) < 0.5:
                indicators.append("вес стабилен 2+ недели")

        if len(indicators) >= 2:
            return StateDetection(
                state_type="metabolic_adaptation",
                detected=True,
                severity="high" if len(indicators) >= 3 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется диет-брейк на 5-7 дней на уровне поддержки. Это восстановит метаболизм и гормональный фон.",
                emoji="🔄"
            )

        return None

    def _detect_body_recomposition(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """Рекомпозиция тела: вес стабилен, но объёмы уменьшаются."""
        if len(aggregates) < 14:
            return None

        indicators = []

        # Вес стабилен
        weights = [agg.measurements.weight_kg for agg in aggregates[:14] if agg.measurements.weight_kg]
        if len(weights) >= 2:
            weight_change = abs(weights[0] - weights[-1])
            if weight_change < 0.5:
                indicators.append("вес стабилен (±0.5 кг)")

        # Талия уменьшается
        waists = [agg.measurements.waist_cm for agg in aggregates[:14] if agg.measurements.waist_cm]
        if len(waists) >= 2:
            waist_change = waists[0] - waists[-1]
            if waist_change >= 1:
                indicators.append(f"талия уменьшилась на {waist_change:.0f} см")

        if len(indicators) >= 2:
            return StateDetection(
                state_type="body_recomposition",
                detected=True,
                severity="positive",
                indicators=indicators,
                recommendation="Отлично! Это лучший сценарий — мышцы растут, жир уходит. НЕ снижай калории, продолжай в том же духе!",
                emoji="🎉"
            )

        return None

    def _detect_overtraining(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """Перетренированность."""
        if len(aggregates) < 14:
            return None

        indicators = []

        # 1. Низкая энергия
        low_energy_days = sum(
            1 for agg in aggregates[:7]
            if agg.derived.avg_energy and agg.derived.avg_energy < 4
        )
        if low_energy_days >= 3:
            indicators.append("низкая энергия 3+ дня подряд")

        # 2. Частые тренировки
        workout_days = sum(
            1 for agg in aggregates[:7]
            if agg.workout.type and agg.workout.type != "none"
        )
        if workout_days >= 4:
            indicators.append(f"тренировки {workout_days} раз за неделю")

        # 3. Снижение качества сна
        sleep_quality = [agg.sleep.quality for agg in aggregates[:7] if agg.sleep.quality]
        if len(sleep_quality) >= 5:
            avg_recent = sum(sleep_quality[:3]) / 3
            avg_previous = sum(sleep_quality[3:6]) / 3 if len(sleep_quality) >= 6 else avg_recent
            if avg_recent < avg_previous - 1:
                indicators.append("качество сна ухудшилось")

        # 4. Снижение шагов
        steps = [agg.activity.steps for agg in aggregates[:7] if agg.activity.steps]
        if len(steps) >= 5:
            steps_recent = steps[:3]
            steps_previous = steps[3:6]
            if steps_previous and sum(steps_recent) / 3 < sum(steps_previous) / 3 * 0.9:
                indicators.append("активность снизилась на 10%+")

        if len(indicators) >= 3:
            return StateDetection(
                state_type="overtraining",
                detected=True,
                severity="high" if len(indicators) >= 4 else "medium",
                indicators=indicators,
                recommendation="Возможна перетренированность. Рекомендуется 2-3 дня полного отдыха и снижение интенсивности тренировок.",
                emoji="⚠️"
            )

        return None

    def _detect_stress_plateau(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """Стрессовое плато: высокий стресс + стабильный вес."""
        if len(aggregates) < 7:
            return None

        indicators = []

        # Высокий стресс
        high_stress_days = sum(1 for agg in aggregates[:7] if agg.stress and agg.stress >= 7)
        if high_stress_days >= 5:
            indicators.append("высокий стресс 5+ дней")

        # Стабильный вес
        weights = [agg.measurements.weight_kg for agg in aggregates[:14] if agg.measurements.weight_kg]
        if len(weights) >= 3:
            weight_change = max(weights[-3:]) - min(weights[-3:])
            if weight_change < 0.5:
                indicators.append("вес стабилен")

        if len(indicators) >= 2:
            return StateDetection(
                state_type="stress_plateau",
                detected=True,
                severity="medium",
                indicators=indicators,
                recommendation="Стресс вызывает задержку воды. НЕ снижай калории! Лучше сосредоточься на управлении стрессом: прогулки, дыхательные практики, сон.",
                emoji="😰"
            )

        return None

    def _detect_insulin_resistance(
        self, aggregates: List[DailyAggregate], profile: dict
    ) -> Optional[StateDetection]:
        """Косвенная оценка инсулинорезистентности."""
        if len(aggregates) < 7:
            return None

        indicators = []

        # WHR (талия/бёдра)
        last_waist = None
        last_hips = None
        for agg in reversed(aggregates):
            if not last_waist and agg.measurements.waist_cm:
                last_waist = agg.measurements.waist_cm
            if not last_hips and agg.measurements.hips_cm:
                last_hips = agg.measurements.hips_cm
            if last_waist and last_hips:
                break

        if last_waist and last_hips:
            whr = last_waist / last_hips
            gender = profile.get("gender", "male")
            if (gender == "male" and whr > 0.90) or (gender == "female" and whr > 0.85):
                indicators.append(f"WHR {whr:.2f} (выше нормы)")

        # Частые приёмы пищи
        meal_counts = [agg.nutrition.meal_count for agg in aggregates[:7] if agg.nutrition.meal_count]
        if meal_counts and sum(meal_counts) / len(meal_counts) > 5:
            indicators.append("частые приёмы пищи (>5 раз в день)")

        # ИСПРАВЛЕНО: требуется минимум 2 индикатора (было >= 1)
        if len(indicators) >= 2:
            return StateDetection(
                state_type="insulin_resistance",
                detected=True,
                severity="high" if len(indicators) >= 2 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется сократить окно питания до 8-10 часов, убрать перекусы между основными приёмами, увеличить потребление белка.",
                emoji="🍬"
            )

        return None


class InsightGenerator:
    """Генерирует персональные инсайты на основе данных пользователя."""

    def generate_insights(self, aggregated: DailyAggregate) -> List[Insight]:
        """Генерирует список инсайтов на основе агрегированных данных за день."""
        insights = []

        # Сон
        sleep_insights = self._generate_sleep_insights(aggregated)
        insights.extend(sleep_insights)

        # Энергия
        energy_insights = self._generate_energy_insights(aggregated)
        insights.extend(energy_insights)

        # Стресс
        stress_insights = self._generate_stress_insights(aggregated)
        insights.extend(stress_insights)

        # Питание
        nutrition_insights = self._generate_nutrition_insights(aggregated)
        insights.extend(nutrition_insights)

        # Активность
        activity_insights = self._generate_activity_insights(aggregated)
        insights.extend(activity_insights)

        # Тренировки
        workout_insights = self._generate_workout_insights(aggregated)
        insights.extend(workout_insights)

        # Сортируем по приоритету и возвращаем топ-5
        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:5]

    def _generate_sleep_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о сне."""
        insights = []

        if agg.sleep.hours is None:
            return insights

        hours = agg.sleep.hours

        if hours < 6:
            insights.append(Insight(
                title="Недостаток сна",
                message=f"Ты спал всего {hours}ч. Недосып снижает метаболизм на 8-12%.",
                emoji="😴",
                priority=5,
                category="sleep"
            ))
        elif hours < 7:
            insights.append(Insight(
                title="Лёгкий недосып",
                message=f"Ты спал {hours}ч. Даже небольшой недосып снижает чувствительность к инсулину.",
                emoji="😐",
                priority=3,
                category="sleep"
            ))

        if agg.sleep.quality and agg.sleep.quality <= 2:
            insights.append(Insight(
                title="Плохое качество сна",
                message="Плохой сон нарушает выработку гормонов.",
                emoji="😫",
                priority=4,
                category="sleep"
            ))

        return insights

    def _generate_energy_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты об энергии."""
        insights = []

        avg_energy = agg.derived.avg_energy
        if avg_energy is None:
            return insights

        if avg_energy <= 4:
            insights.append(Insight(
                title="Низкая энергия",
                message="Возможно, пора сделать диет-брейк на 5-7 дней.",
                emoji="⚡",
                priority=5,
                category="energy"
            ))
        elif avg_energy >= 9:
            insights.append(Insight(
                title="Отличная энергия!",
                message="Высокий уровень энергии говорит о хорошем восстановлении.",
                emoji="💪",
                priority=1,
                category="energy"
            ))

        return insights

    def _generate_stress_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о стрессе."""
        insights = []

        if agg.stress and agg.stress >= 8:
            insights.append(Insight(
                title="Высокий стресс",
                message="Хронический стресс повышает кортизол. Попробуй дыхательные практики.",
                emoji="😰",
                priority=5,
                category="stress"
            ))

        return insights

    def _generate_nutrition_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о питании."""
        insights = []

        # Белок
        protein_per_kg = agg.derived.protein_per_kg
        if protein_per_kg and protein_per_kg < 1.2:
            insights.append(Insight(
                title="Мало белка",
                message=f"Ты съел {protein_per_kg:.1f}г белка на кг. Нужно 1.6-2.0г/кг.",
                emoji="🍗",
                priority=4,
                category="nutrition"
            ))

        # Окно питания
        window = agg.derived.eating_window_hours
        if window and window > 12:
            insights.append(Insight(
                title="Длинное окно питания",
                message=f"Окно питания {window:.0f}ч. Узкое окно (8-10ч) улучшает метаболизм.",
                emoji="⏰",
                priority=3,
                category="nutrition"
            ))

        return insights

    def _generate_activity_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты об активности."""
        insights = []

        steps = agg.activity.steps
        if steps is None:
            return insights

        if steps < 5000:
            insights.append(Insight(
                title="Малая активность",
                message=f"Ты прошёл {steps:,} шагов. Увеличь до 8000-10000.",
                emoji="👣",
                priority=4,
                category="activity"
            ))
        elif steps >= 10000:
            insights.append(Insight(
                title="Хорошая активность!",
                message=f"{steps:,} шагов — это ~300-500 ккал.",
                emoji="🎉",
                priority=1,
                category="activity"
            ))

        return insights

    def _generate_workout_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о тренировках."""
        insights = []

        if agg.workout.type and agg.workout.type != "none":
            if agg.workout.type == "strength":
                insights.append(Insight(
                    title="Силовая тренировка",
                    message="Отличная силовая! Она сохраняет мышцы при дефиците.",
                    emoji="🏋️",
                    priority=2,
                    category="workout"
                ))

        return insights