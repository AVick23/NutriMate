"""
Обнаружение паттернов, состояний и генерация инсайтов.
"""
import logging
from typing import List, Optional, Dict, Any

from db import Database
from .core import (
    DailyAggregate, Pattern, Insight, StateDetection,
    MIN_CORRELATION, MIN_SAMPLE_SIZE, P_VALUE_THRESHOLD, LAGS,
    STATE_NAMES,
    pearson_correlation, get_lagged_pairs, aggregates_to_dict,
    generate_effect_text,
)

logger = logging.getLogger(__name__)


# ================================================================
# РЕПОЗИТОРИЙ ПАТТЕРНОВ
# ================================================================

class PatternsRepository:
    """Репозиторий для таблицы user_patterns."""

    def __init__(self, db: Database):
        self.db = db

    async def save_pattern(
        self, user_id: int, pattern_data: Dict[str, Any]
    ) -> int:
        """Сохраняет или обновляет паттерн."""
        async with self.db.transaction() as conn:
            # Проверяем существование
            cursor = await conn.execute("""
                SELECT id, confirmation_count FROM user_patterns
                WHERE user_id = ? AND metric_x = ?
                    AND metric_y = ? AND lag_days = ?
            """, (
                user_id,
                pattern_data.get("metric_x"),
                pattern_data.get("metric_y"),
                pattern_data.get("lag_days", 0)
            ))
            existing = await cursor.fetchone()

            if existing:
                await conn.execute("""
                    UPDATE user_patterns
                    SET correlation_r = ?,
                        p_value = ?,
                        sample_size = ?,
                        effect_text = ?,
                        effect_direction = ?,
                        last_confirmed_at = CURRENT_TIMESTAMP,
                        confirmation_count = confirmation_count + 1,
                        is_active = 1
                    WHERE id = ?
                """, (
                    pattern_data.get("correlation_r"),
                    pattern_data.get("p_value"),
                    pattern_data.get("sample_size"),
                    pattern_data.get("effect_text"),
                    pattern_data.get("effect_direction"),
                    existing["id"]
                ))
                return existing["id"]
            else:
                cursor = await conn.execute("""
                    INSERT INTO user_patterns
                    (user_id, pattern_type, metric_x, metric_y,
                     correlation_r, p_value, lag_days, sample_size,
                     effect_text, effect_direction)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    pattern_data.get("pattern_type"),
                    pattern_data.get("metric_x"),
                    pattern_data.get("metric_y"),
                    pattern_data.get("correlation_r"),
                    pattern_data.get("p_value"),
                    pattern_data.get("lag_days", 0),
                    pattern_data.get("sample_size"),
                    pattern_data.get("effect_text"),
                    pattern_data.get("effect_direction")
                ))
                return cursor.lastrowid

    async def get_active_patterns(
        self, user_id: int
    ) -> List[Dict[str, Any]]:
        """Получает активные паттерны пользователя."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM user_patterns
                WHERE user_id = ? AND is_active = 1
                ORDER BY ABS(correlation_r) DESC,
                         confirmation_count DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ================================================================
# ДЕТЕКТОР ПАТТЕРНОВ
# ================================================================

class PatternDetector:
    """
    Обнаруживает корреляции между метриками с разными лагами.
    """

    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(
        self, user_id: int, aggregates: List[DailyAggregate]
    ) -> List[Pattern]:
        """Обнаруживает паттерны на основе агрегированных данных."""
        if len(aggregates) < MIN_SAMPLE_SIZE:
            logger.debug(
                f"Not enough data for user {user_id}: "
                f"{len(aggregates)} days"
            )
            return []

        data = aggregates_to_dict(aggregates)
        detected_patterns = []

        for lag in LAGS:
            patterns = await self._analyze_correlations(
                user_id, data, lag
            )
            detected_patterns.extend(patterns)

        # Сохраняем паттерны в БД
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
        self, user_id: int, data: dict, lag: int
    ) -> List[Pattern]:
        """Анализирует корреляции с заданным лагом."""
        patterns = []
        metrics = [k for k in data.keys() if k != "date"]

        for metric_x in metrics:
            for metric_y in metrics:
                if metric_x == metric_y:
                    continue

                x_vals, y_vals = get_lagged_pairs(
                    data, metric_x, metric_y, lag
                )

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
                        effect_direction=(
                            "positive" if r > 0 else "negative"
                        ),
                        effect_text=generate_effect_text(
                            metric_x, metric_y, r, lag
                        ),
                    )
                    patterns.append(pattern)

        return patterns


# ================================================================
# ДЕТЕКТОР СОСТОЯНИЙ
# ================================================================

class StateDetector:
    """
    Определяет сложные состояния на основе правил.
    
    Обнаруживаемые состояния:
    - Метаболическая адаптация
    - Рекомпозиция тела
    - Перетренированность
    - Стрессовое плато
    - Инсулинорезистентность (косвенная оценка)
    """

    def detect_states(
        self, aggregates: List[DailyAggregate], profile: dict
    ) -> List[StateDetection]:
        """Анализирует агрегаты и возвращает состояния."""
        states = []

        detectors = [
            self._detect_metabolic_adaptation,
            self._detect_body_recomposition,
            self._detect_overtraining,
            self._detect_stress_plateau,
            lambda aggs: self._detect_insulin_resistance(aggs, profile),
        ]

        for detector in detectors:
            state = detector(aggregates)
            if state:
                states.append(state)

        return states

    def _detect_metabolic_adaptation(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """Метаболическая адаптация при длительном дефиците."""
        if len(aggregates) < 14:
            return None

        indicators = []

        # 1. Низкая энергия 5+ дней
        low_energy = sum(
            1 for a in aggregates[:14]
            if a.derived.avg_energy and a.derived.avg_energy < 5
        )
        if low_energy >= 5:
            indicators.append(
                "энергия ниже 5/10 в течение 5+ дней"
            )

        # 2. Плато веса 14+ дней
        weights = [
            a.measurements.weight_kg
            for a in aggregates[:14]
            if a.measurements.weight_kg
        ]
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
                recommendation=(
                    "Рекомендуется диет-брейк на 5-7 дней "
                    "на уровне поддержки. Это восстановит "
                    "метаболизм и гормональный фон."
                ),
                emoji="🔄",
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
        weights = [
            a.measurements.weight_kg
            for a in aggregates[:14]
            if a.measurements.weight_kg
        ]
        if len(weights) >= 2:
            weight_change = abs(weights[0] - weights[-1])
            if weight_change < 0.5:
                indicators.append("вес стабилен (±0.5 кг)")

        # Талия уменьшается
        waists = [
            a.measurements.waist_cm
            for a in aggregates[:14]
            if a.measurements.waist_cm
        ]
        if len(waists) >= 2:
            waist_change = waists[0] - waists[-1]
            if waist_change >= 1:
                indicators.append(
                    f"талия уменьшилась на {waist_change:.0f} см"
                )

        if len(indicators) >= 2:
            return StateDetection(
                state_type="body_recomposition",
                detected=True,
                severity="positive",
                indicators=indicators,
                recommendation=(
                    "Отлично! Это лучший сценарий — мышцы растут, "
                    "жир уходит. НЕ снижай калории, продолжай "
                    "в том же духе!"
                ),
                emoji="🎉",
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
        low_energy = sum(
            1 for a in aggregates[:7]
            if a.derived.avg_energy and a.derived.avg_energy < 4
        )
        if low_energy >= 3:
            indicators.append("низкая энергия 3+ дня подряд")

        # 2. Частые тренировки
        workout_days = sum(
            1 for a in aggregates[:7]
            if a.workout.type and a.workout.type != "none"
        )
        if workout_days >= 4:
            indicators.append(
                f"тренировки {workout_days} раз за неделю"
            )

        # 3. Снижение качества сна
        sleep_quality = [
            a.sleep.quality for a in aggregates[:7]
            if a.sleep.quality
        ]
        if len(sleep_quality) >= 5:
            recent = sum(sleep_quality[:3]) / 3
            prev = (sum(sleep_quality[3:6]) / 3
                    if len(sleep_quality) >= 6
                    else recent)
            if recent < prev - 1:
                indicators.append("качество сна ухудшилось")

        # 4. Снижение шагов
        steps = [
            a.activity.steps for a in aggregates[:7]
            if a.activity.steps
        ]
        if len(steps) >= 5:
            if (sum(steps[:3]) / 3
                    < sum(steps[3:6]) / 3 * 0.9):
                indicators.append("активность снизилась на 10%+")

        if len(indicators) >= 3:
            return StateDetection(
                state_type="overtraining",
                detected=True,
                severity="high" if len(indicators) >= 4 else "medium",
                indicators=indicators,
                recommendation=(
                    "Возможна перетренированность. "
                    "Рекомендуется 2-3 дня полного отдыха "
                    "и снижение интенсивности тренировок."
                ),
                emoji="⚠️",
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
        high_stress = sum(
            1 for a in aggregates[:7]
            if a.stress and a.stress >= 7
        )
        if high_stress >= 5:
            indicators.append("высокий стресс 5+ дней")

        # Стабильный вес
        weights = [
            a.measurements.weight_kg
            for a in aggregates[:14]
            if a.measurements.weight_kg
        ]
        if len(weights) >= 3:
            weight_change = max(weights[-3:]) - min(weights[-3:])
            if abs(weight_change) < 0.5:
                indicators.append("вес стабилен")

        if len(indicators) >= 2:
            return StateDetection(
                state_type="stress_plateau",
                detected=True,
                severity="medium",
                indicators=indicators,
                recommendation=(
                    "Стресс вызывает задержку воды. "
                    "НЕ снижай калории! Лучше сосредоточься "
                    "на управлении стрессом: прогулки, "
                    "дыхательные практики, сон."
                ),
                emoji="😰",
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
        for a in reversed(aggregates):
            if not last_waist and a.measurements.waist_cm:
                last_waist = a.measurements.waist_cm
            if not last_hips and a.measurements.hips_cm:
                last_hips = a.measurements.hips_cm
            if last_waist and last_hips:
                break

        if last_waist and last_hips:
            whr = last_waist / last_hips
            gender = profile.get("gender", "male")
            if ((gender == "male" and whr > 0.90)
                    or (gender == "female" and whr > 0.85)):
                indicators.append(f"WHR {whr:.2f} (выше нормы)")

        # Частые приёмы пищи
        meals = [
            a.nutrition.meal_count
            for a in aggregates[:7]
            if a.nutrition.meal_count
        ]
        if meals and sum(meals) / len(meals) > 5:
            indicators.append("частые приёмы пищи (>5 раз в день)")

        # ИСПРАВЛЕНО: требуется минимум 2 индикатора (было >= 1)
        if len(indicators) >= 2:
            return StateDetection(
                state_type="insulin_resistance",
                detected=True,
                severity="high" if len(indicators) >= 2 else "medium",
                indicators=indicators,
                recommendation=(
                    "Рекомендуется сократить окно питания "
                    "до 8-10 часов, убрать перекусы "
                    "между основными приёмами, "
                    "увеличить потребление белка."
                ),
                emoji="🍬",
            )

        return None


# ================================================================
# ГЕНЕРАТОР ИНСАЙТОВ
# ================================================================

class InsightGenerator:
    """Генерирует персональные инсайты на основе данных пользователя."""

    def generate_insights(
        self, aggregated: DailyAggregate
    ) -> List[Insight]:
        """Генерирует список инсайтов (топ-5 по приоритету)."""
        insights = []

        insights.extend(self._generate_sleep_insights(aggregated))
        insights.extend(self._generate_energy_insights(aggregated))
        insights.extend(self._generate_stress_insights(aggregated))
        insights.extend(self._generate_nutrition_insights(aggregated))
        insights.extend(self._generate_activity_insights(aggregated))
        insights.extend(self._generate_workout_insights(aggregated))

        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:5]

    def _generate_sleep_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты о сне."""
        insights = []

        if agg.sleep.hours is None:
            return insights

        hours = agg.sleep.hours

        if hours < 6:
            insights.append(Insight(
                title="Недостаток сна",
                message=(
                    f"Ты спал всего {hours}ч. "
                    f"Недосып снижает метаболизм на 8-12% "
                    f"и повышает голод на 28% через грелин."
                ),
                emoji="😴",
                priority=5,
                category="sleep",
            ))
        elif hours < 7:
            insights.append(Insight(
                title="Лёгкий недосып",
                message=(
                    f"Ты спал {hours}ч. Даже небольшой недосып "
                    f"снижает чувствительность к инсулину на 20%."
                ),
                emoji="😐",
                priority=3,
                category="sleep",
            ))
        elif hours > 9:
            insights.append(Insight(
                title="Долгий сон",
                message=(
                    f"Ты спал {hours}ч. Долгий сон может быть "
                    f"признаком перетренированности или "
                    f"нехватки энергии."
                ),
                emoji="😴",
                priority=2,
                category="sleep",
            ))

        # Качество сна
        if agg.sleep.quality and agg.sleep.quality <= 2:
            insights.append(Insight(
                title="Плохое качество сна",
                message=(
                    "Плохой сон нарушает выработку гормонов "
                    "и замедляет восстановление. "
                    "Попробуй тёплую ванну или медитацию "
                    "перед сном."
                ),
                emoji="😫",
                priority=4,
                category="sleep",
            ))

        # Пробуждения
        if agg.sleep.awakenings and agg.sleep.awakenings >= 2:
            insights.append(Insight(
                title="Ночные пробуждения",
                message=(
                    f"Ты просыпался {agg.sleep.awakenings} раз(а). "
                    f"Это повышает кортизол и снижает "
                    f"эффективность сна."
                ),
                emoji="🔄",
                priority=3,
                category="sleep",
            ))

        return insights

    def _generate_energy_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты об энергии."""
        insights = []

        avg_energy = agg.derived.avg_energy
        if avg_energy is None:
            return insights

        if avg_energy <= 4:
            insights.append(Insight(
                title="Низкая энергия",
                message=(
                    "Низкая энергия может быть признаком "
                    "метаболической адаптации. Возможно, "
                    "пора сделать диет-брейк на 5-7 дней."
                ),
                emoji="⚡",
                priority=5,
                category="energy",
            ))
        elif avg_energy <= 6:
            insights.append(Insight(
                title="Умеренная энергия",
                message=(
                    "Твоя энергия чуть ниже нормы. Убедись, "
                    "что ты высыпаешься и получаешь "
                    "достаточно белка."
                ),
                emoji="😐",
                priority=2,
                category="energy",
            ))
        elif avg_energy >= 9:
            insights.append(Insight(
                title="Отличная энергия!",
                message=(
                    "Высокий уровень энергии говорит "
                    "о хорошем восстановлении. Отличная работа!"
                ),
                emoji="💪",
                priority=1,
                category="energy",
            ))

        return insights

    def _generate_stress_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты о стрессе."""
        insights = []

        if agg.stress is None:
            return insights

        if agg.stress >= 8:
            insights.append(Insight(
                title="Высокий стресс",
                message=(
                    "Хронический стресс повышает кортизол, "
                    "который задерживает воду и увеличивает "
                    "висцеральный жир. Попробуй дыхательные "
                    "практики или лёгкую прогулку."
                ),
                emoji="😰",
                priority=5,
                category="stress",
            ))
        elif agg.stress >= 6:
            insights.append(Insight(
                title="Повышенный стресс",
                message=(
                    "Стресс может вызывать тягу к сладкому "
                    "и снижать качество сна. "
                    "Выдели 10 минут на расслабление."
                ),
                emoji="😟",
                priority=3,
                category="stress",
            ))

        return insights

    def _generate_nutrition_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты о питании."""
        insights = []

        # Белок
        protein_per_kg = agg.derived.protein_per_kg
        if protein_per_kg and protein_per_kg < 1.2:
            insights.append(Insight(
                title="Мало белка",
                message=(
                    f"Ты съел всего {protein_per_kg}г белка "
                    f"на кг веса. Для сохранения мышц "
                    f"нужно минимум 1.6-2.0г/кг."
                ),
                emoji="🍗",
                priority=4,
                category="nutrition",
            ))

        # Окно питания
        window = agg.derived.eating_window_hours
        if window and window > 12:
            insights.append(Insight(
                title="Длинное окно питания",
                message=(
                    f"Твой приём пищи растянут на {window:.0f}ч. "
                    f"Узкое окно (8-10ч) улучшает "
                    f"чувствительность к инсулину."
                ),
                emoji="⏰",
                priority=3,
                category="nutrition",
            ))
        elif window and 0 < window < 8:
            insights.append(Insight(
                title="Интервальное голодание",
                message=(
                    f"Окно питания {window:.0f}ч — отличный "
                    f"режим для метаболического здоровья!"
                ),
                emoji="🌟",
                priority=2,
                category="nutrition",
            ))

        # Время последнего приёма пищи
        last_meal_hour = agg.derived.last_meal_hour
        if last_meal_hour and last_meal_hour >= 21:
            insights.append(Insight(
                title="Поздний ужин",
                message=(
                    f"Последний приём пищи в {last_meal_hour}:00. "
                    f"Поздняя еда снижает окисление жиров на 10% "
                    f"и нарушает циркадные ритмы."
                ),
                emoji="🌙",
                priority=3,
                category="nutrition",
            ))

        return insights

    def _generate_activity_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты об активности."""
        insights = []

        steps = agg.activity.steps
        if steps is None:
            return insights

        if steps < 5000:
            insights.append(Insight(
                title="Малая активность",
                message=(
                    f"Ты прошёл всего {steps:,} шагов. "
                    f"Увеличение NEAT до 8000-10000 шагов "
                    f"в день ускорит метаболизм."
                ),
                emoji="👣",
                priority=4,
                category="activity",
            ))
        elif steps >= 10000:
            insights.append(Insight(
                title="Хорошая активность!",
                message=(
                    f"Отлично! {steps:,} шагов — это ~300-500 "
                    f"ккал дополнительного расхода."
                ),
                emoji="🎉",
                priority=1,
                category="activity",
            ))

        return insights

    def _generate_workout_insights(
        self, agg: DailyAggregate
    ) -> List[Insight]:
        """Инсайты о тренировках."""
        insights = []

        workout_type = agg.workout.type
        duration = agg.workout.duration_min

        if not workout_type or workout_type == "none":
            return insights

        if workout_type == "strength":
            insights.append(Insight(
                title="Силовая тренировка",
                message=(
                    "Отличная силовая! Она не только сжигает "
                    "калории, но и сохраняет мышцы при дефиците."
                ),
                emoji="🏋️",
                priority=2,
                category="workout",
            ))
        elif workout_type == "cardio":
            insights.append(Insight(
                title="Кардио тренировка",
                message=(
                    f"{duration} минут кардио. Добавь силовые "
                    f"для лучшего сохранения мышечной массы."
                ),
                emoji="🏃",
                priority=2,
                category="workout",
            ))

        return insights