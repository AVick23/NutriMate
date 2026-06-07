"""
Обнаружение паттернов, состояний, генерация инсайтов и отчётов.
"""
import logging
from datetime import date, timedelta
from typing import List, Optional, Dict, Any

from db import Database
from .core import DailyAggregate, Pattern, Insight, StateDetection, MIN_CORRELATION, MIN_SAMPLE_SIZE, P_VALUE_THRESHOLD, LAGS, STATE_NAMES, METRIC_NAMES, pearson_correlation, get_lagged_pairs, aggregates_to_dict, generate_effect_text, safe_average, format_metrics_summary, format_insights, format_insights_compact, format_patterns, format_states, format_macro_balance, format_forecast, format_best_day, format_tdee_modifiers, state_name_ru, split_long_message
from .engine import DailyAggregator, ChartGenerator

logger = logging.getLogger(__name__)

class PatternsRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save_pattern(self, user_id: int, pattern_data: Dict[str, Any]) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute("SELECT id, confirmation_count FROM user_patterns WHERE user_id = ? AND metric_x = ? AND metric_y = ? AND lag_days = ?", (user_id, pattern_data.get("metric_x"), pattern_data.get("metric_y"), pattern_data.get("lag_days", 0)))
            existing = await cursor.fetchone()
            if existing:
                await conn.execute("UPDATE user_patterns SET correlation_r = ?, p_value = ?, sample_size = ?, effect_text = ?, effect_direction = ?, last_confirmed_at = CURRENT_TIMESTAMP, confirmation_count = confirmation_count + 1, is_active = 1 WHERE id = ?", (pattern_data.get("correlation_r"), pattern_data.get("p_value"), pattern_data.get("sample_size"), pattern_data.get("effect_text"), pattern_data.get("effect_direction"), existing["id"]))
                return existing["id"]
            else:
                cursor = await conn.execute("INSERT INTO user_patterns (user_id, pattern_type, metric_x, metric_y, correlation_r, p_value, lag_days, sample_size, effect_text, effect_direction) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, pattern_data.get("pattern_type"), pattern_data.get("metric_x"), pattern_data.get("metric_y"), pattern_data.get("correlation_r"), pattern_data.get("p_value"), pattern_data.get("lag_days", 0), pattern_data.get("sample_size"), pattern_data.get("effect_text"), pattern_data.get("effect_direction")))
                return cursor.lastrowid

    async def get_active_patterns(self, user_id: int) -> List[Dict[str, Any]]:
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT * FROM user_patterns WHERE user_id = ? AND is_active = 1 ORDER BY ABS(correlation_r) DESC, confirmation_count DESC", (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

class PatternDetector:
    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(self, user_id: int, aggregates: List[DailyAggregate]) -> List[Pattern]:
        if len(aggregates) < MIN_SAMPLE_SIZE:
            logger.debug(f"Not enough data for user {user_id}: {len(aggregates)} days")
            return []
        data = aggregates_to_dict(aggregates)
        detected_patterns = []
        for lag in LAGS:
            patterns = await self._analyze_correlations(user_id, data, lag)
            detected_patterns.extend(patterns)
        for pattern in detected_patterns:
            await self.patterns_repo.save_pattern(user_id, {"pattern_type": pattern.pattern_type, "metric_x": pattern.metric_x, "metric_y": pattern.metric_y, "correlation_r": pattern.correlation_r, "p_value": pattern.p_value, "lag_days": pattern.lag_days, "sample_size": pattern.sample_size, "effect_text": pattern.effect_text, "effect_direction": pattern.effect_direction})
        return detected_patterns

    async def _analyze_correlations(self, user_id: int, data: dict, lag: int) -> List[Pattern]:
        patterns = []
        metrics = [k for k in data.keys() if k != "date"]
        for metric_x in metrics:
            for metric_y in metrics:
                if metric_x == metric_y:
                    continue
                x_vals, y_vals = get_lagged_pairs(data, metric_x, metric_y, lag)
                if len(x_vals) < MIN_SAMPLE_SIZE:
                    continue
                r, p_value = pearson_correlation(x_vals, y_vals)
                if abs(r) >= MIN_CORRELATION and p_value < P_VALUE_THRESHOLD:
                    pattern = Pattern(pattern_type="correlation", metric_x=metric_x, metric_y=metric_y, correlation_r=r, p_value=p_value, lag_days=lag, sample_size=len(x_vals), effect_direction="positive" if r > 0 else "negative", effect_text=generate_effect_text(metric_x, metric_y, r, lag))
                    patterns.append(pattern)
        return patterns

class StateDetector:
    def detect_states(self, aggregates: List[DailyAggregate], profile: dict) -> List[StateDetection]:
        states = []
        detectors = [self._detect_metabolic_adaptation, self._detect_body_recomposition, self._detect_overtraining, self._detect_stress_plateau, lambda aggs: self._detect_insulin_resistance(aggs, profile)]
        for detector in detectors:
            state = detector(aggregates)
            if state:
                states.append(state)
        return states

    def _detect_metabolic_adaptation(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14:
            return None
        indicators = []
        low_energy = sum(1 for a in aggregates[:14] if a.derived.avg_energy and a.derived.avg_energy < 5)
        if low_energy >= 5:
            indicators.append("энергия ниже 5/10 в течение 5+ дней")
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 7:
            weight_change = max(weights) - min(weights)
            if abs(weight_change) < 0.5:
                indicators.append("вес стабилен 2+ недели")
        if len(indicators) >= 2:
            return StateDetection(state_type="metabolic_adaptation", detected=True, severity="high" if len(indicators) >= 3 else "medium", indicators=indicators, recommendation="Рекомендуется диет-брейк на 5-7 дней на уровне поддержки. Это восстановит метаболизм и гормональный фон.", emoji="🔄")
        return None

    def _detect_body_recomposition(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 14:
            return None
        indicators = []
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 2:
            weight_change = abs(weights[0] - weights[-1])
            if weight_change < 0.5:
                indicators.append("вес стабилен (±0.5 кг)")
        waists = [a.measurements.waist_cm for a in aggregates[:14] if a.measurements.waist_cm]
        if len(waists) >= 2:
            waist_change = waists[0] - waists[-1]
            if waist_change >= 1:
                indicators.append(f"талия уменьшилась на {waist_change:.0f} см")
        if len(indicators) >= 2:
            return StateDetection(state_type="body_recomposition", detected=True, severity="positive", indicators=indicators, recommendation="Отлично! Это лучший сценарий — мышцы растут, жир уходит. НЕ снижай калории, продолжай в том же духе!", emoji="🎉")
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
        sleep_quality = [a.sleep.quality for a in aggregates[:7] if a.sleep.quality]
        if len(sleep_quality) >= 5:
            recent = sum(sleep_quality[:3]) / 3
            prev = (sum(sleep_quality[3:6]) / 3 if len(sleep_quality) >= 6 else recent)
            if recent < prev - 1:
                indicators.append("качество сна ухудшилось")
        steps = [a.activity.steps for a in aggregates[:7] if a.activity.steps]
        if len(steps) >= 5:
            if (sum(steps[:3]) / 3) < sum(steps[3:6]) / 3 * 0.9:
                indicators.append("активность снизилась на 10%+")
        if len(indicators) >= 3:
            return StateDetection(state_type="overtraining", detected=True, severity="high" if len(indicators) >= 4 else "medium", indicators=indicators, recommendation="Возможна перетренированность. Рекомендуется 2-3 дня полного отдыха и снижение интенсивности тренировок.", emoji="⚠️")
        return None

    def _detect_stress_plateau(self, aggregates: List[DailyAggregate]) -> Optional[StateDetection]:
        if len(aggregates) < 7:
            return None
        indicators = []
        high_stress = sum(1 for a in aggregates[:7] if a.stress and a.stress >= 7)
        if high_stress >= 5:
            indicators.append("высокий стресс 5+ дней")
        weights = [a.measurements.weight_kg for a in aggregates[:14] if a.measurements.weight_kg]
        if len(weights) >= 3:
            weight_change = max(weights[-3:]) - min(weights[-3:])
            if abs(weight_change) < 0.5:
                indicators.append("вес стабилен")
        if len(indicators) >= 2:
            return StateDetection(state_type="stress_plateau", detected=True, severity="medium", indicators=indicators, recommendation="Стресс вызывает задержку воды. НЕ снижай калории! Лучше сосредоточься на управлении стрессом: прогулки, дыхательные практики, сон.", emoji="😰")
        return None

    def _detect_insulin_resistance(self, aggregates: List[DailyAggregate], profile: dict) -> Optional[StateDetection]:
        if len(aggregates) < 7:
            return None
        indicators = []
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
            if ((gender == "male" and whr > 0.90) or (gender == "female" and whr > 0.85)):
                indicators.append(f"WHR {whr:.2f} (выше нормы)")
        meals = [a.nutrition.meal_count for a in aggregates[:7] if a.nutrition.meal_count]
        if meals and sum(meals) / len(meals) > 5:
            indicators.append("частые приёмы пищи (>5 раз в день)")
        if len(indicators) >= 2:
            return StateDetection(state_type="insulin_resistance", detected=True, severity="high" if len(indicators) >= 2 else "medium", indicators=indicators, recommendation="Рекомендуется сократить окно питания до 8-10 часов, убрать перекусы между основными приёмами, увеличить потребление белка.", emoji="🍬")
        return None

class InsightGenerator:
    def generate_insights(self, aggregated: DailyAggregate) -> List[Insight]:
        insights = []
        insights.extend(self._generate_sleep_insights(aggregated))
        insights.extend(self._generate_energy_insights(aggregated))
        insights.extend(self._generate_stress_insights(aggregated))
        insights.extend(self._generate_nutrition_insights(aggregated))
        insights.extend(self._generate_activity_insights(aggregated))
        insights.extend(self._generate_workout_insights(aggregated))
        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:5]

    def _generate_sleep_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        if agg.sleep.hours is None:
            return insights
        hours = agg.sleep.hours
        if hours < 6:
            insights.append(Insight(title="Недостаток сна", message=f"Ты спал всего {hours}ч. Недосып снижает метаболизм на 8-12% и повышает голод на 28% через грелин.", emoji="😴", priority=5, category="sleep"))
        elif hours < 7:
            insights.append(Insight(title="Лёгкий недосып", message=f"Ты спал {hours}ч. Даже небольшой недосып снижает чувствительность к инсулину на 20%.", emoji="😐", priority=3, category="sleep"))
        elif hours > 9:
            insights.append(Insight(title="Долгий сон", message=f"Ты спал {hours}ч. Долгий сон может быть признаком перетренированности или нехватки энергии.", emoji="😴", priority=2, category="sleep"))
        if agg.sleep.quality and agg.sleep.quality <= 2:
            insights.append(Insight(title="Плохое качество сна", message="Плохой сон нарушает выработку гормонов и замедляет восстановление. Попробуй тёплую ванну или медитацию перед сном.", emoji="😫", priority=4, category="sleep"))
        if agg.sleep.awakenings and agg.sleep.awakenings >= 2:
            insights.append(Insight(title="Ночные пробуждения", message=f"Ты просыпался {agg.sleep.awakenings} раз(а). Это повышает кортизол и снижает эффективность сна.", emoji="🔄", priority=3, category="sleep"))
        return insights

    def _generate_energy_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        avg_energy = agg.derived.avg_energy
        if avg_energy is None:
            return insights
        if avg_energy <= 4:
            insights.append(Insight(title="Низкая энергия", message="Низкая энергия может быть признаком метаболической адаптации. Возможно, пора сделать диет-брейк на 5-7 дней.", emoji="⚡", priority=5, category="energy"))
        elif avg_energy <= 6:
            insights.append(Insight(title="Умеренная энергия", message="Твоя энергия чуть ниже нормы. Убедись, что ты высыпаешься и получаешь достаточно белка.", emoji="😐", priority=2, category="energy"))
        elif avg_energy >= 9:
            insights.append(Insight(title="Отличная энергия!", message="Высокий уровень энергии говорит о хорошем восстановлении. Отличная работа!", emoji="💪", priority=1, category="energy"))
        return insights

    def _generate_stress_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        if agg.stress is None:
            return insights
        if agg.stress >= 8:
            insights.append(Insight(title="Высокий стресс", message="Хронический стресс повышает кортизол, который задерживает воду и увеличивает висцеральный жир. Попробуй дыхательные практики или лёгкую прогулку.", emoji="😰", priority=5, category="stress"))
        elif agg.stress >= 6:
            insights.append(Insight(title="Повышенный стресс", message="Стресс может вызывать тягу к сладкому и снижать качество сна. Выдели 10 минут на расслабление.", emoji="😟", priority=3, category="stress"))
        return insights

    def _generate_nutrition_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        protein_per_kg = agg.derived.protein_per_kg
        if protein_per_kg and protein_per_kg < 1.2:
            insights.append(Insight(title="Мало белка", message=f"Ты съел всего {protein_per_kg}г белка на кг веса. Для сохранения мышц нужно минимум 1.6-2.0г/кг.", emoji="🍗", priority=4, category="nutrition"))
        window = agg.derived.eating_window_hours
        if window and window > 12:
            insights.append(Insight(title="Длинное окно питания", message=f"Твой приём пищи растянут на {window:.0f}ч. Узкое окно (8-10ч) улучшает чувствительность к инсулину.", emoji="⏰", priority=3, category="nutrition"))
        elif window and 0 < window < 8:
            insights.append(Insight(title="Интервальное голодание", message=f"Окно питания {window:.0f}ч — отличный режим для метаболического здоровья!", emoji="🌟", priority=2, category="nutrition"))
        last_meal_hour = agg.derived.last_meal_hour
        if last_meal_hour and last_meal_hour >= 21:
            insights.append(Insight(title="Поздний ужин", message=f"Последний приём пищи в {last_meal_hour}:00. Поздняя еда снижает окисление жиров на 10% и нарушает циркадные ритмы.", emoji="🌙", priority=3, category="nutrition"))
        return insights

    def _generate_activity_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        steps = agg.activity.steps
        if steps is None:
            return insights
        if steps < 5000:
            insights.append(Insight(title="Малая активность", message=f"Ты прошёл всего {steps:,} шагов. Увеличение NEAT до 8000-10000 шагов в день ускорит метаболизм.", emoji="👣", priority=4, category="activity"))
        elif steps >= 10000:
            insights.append(Insight(title="Хорошая активность!", message=f"Отлично! {steps:,} шагов — это ~300-500 ккал дополнительного расхода.", emoji="🎉", priority=1, category="activity"))
        return insights

    def _generate_workout_insights(self, agg: DailyAggregate) -> List[Insight]:
        insights = []
        workout_type = agg.workout.type
        duration = agg.workout.duration_min
        if not workout_type or workout_type == "none":
            return insights
        if workout_type == "strength":
            insights.append(Insight(title="Силовая тренировка", message="Отличная силовая! Она не только сжигает калории, но и сохраняет мышцы при дефиците.", emoji="🏋️", priority=2, category="workout"))
        elif workout_type == "cardio":
            insights.append(Insight(title="Кардио тренировка", message=f"{duration} минут кардио. Добавь силовые для лучшего сохранения мышечной массы.", emoji="🏃", priority=2, category="workout"))
        return insights

class WeeklyReportGenerator:
    def __init__(self, db: Database):
        self.db = db
        self.aggregator = DailyAggregator(db)
        self.state_detector = StateDetector()
        self.pattern_detector = PatternDetector(db)
        self.insight_generator = InsightGenerator()
        self.chart_gen = ChartGenerator()

    async def generate_report(self, user_id: int, profile: dict, end_date: Optional[date] = None) -> str:
        if end_date is None:
            end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)
        aggregates = []
        for i in range(8):
            d = start_date + timedelta(days=i)
            if d <= end_date:
                aggregates.append(await self.aggregator.aggregate(user_id, d))
        if not aggregates:
            return "📊 Недостаточно данных для отчёта. Заполняй метрики чаще!"
        report = []
        report.append(f"📊 <b>Недельный отчёт</b>\n")
        report.append(f"{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}\n")
        report.append("─────────────────")
        report.append("\n<b>📈 Средние значения за неделю:</b>\n")
        avg_kcal = safe_average([a.nutrition.total_kcal for a in aggregates])
        avg_protein = safe_average([a.nutrition.total_protein_g for a in aggregates])
        avg_steps = safe_average([a.activity.steps for a in aggregates if a.activity.steps])
        avg_sleep = safe_average([a.sleep.hours for a in aggregates if a.sleep.hours])
        if avg_kcal:
            report.append(f"🔥 Калории: {avg_kcal:.0f} ккал/день")
        if avg_protein:
            report.append(f"🍗 Белок: {avg_protein:.0f} г/день")
        if avg_steps:
            report.append(f"👣 Шаги: {avg_steps:.0f} шагов/день")
        if avg_sleep:
            report.append(f"😴 Сон: {avg_sleep:.1f} ч/день")
        report.append("\n<b>📉 Динамика за неделю:</b>\n")
        weights = [a.measurements.weight_kg for a in aggregates if a.measurements.weight_kg]
        if len(weights) >= 2:
            change = weights[-1] - weights[0]
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            report.append(f"{direction} Вес: {abs(change):.1f} кг")
        waists = [a.measurements.waist_cm for a in aggregates if a.measurements.waist_cm]
        if len(waists) >= 2:
            change = waists[-1] - waists[0]
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            report.append(f"{direction} Талия: {abs(change):.1f} см")
        states = self.state_detector.detect_states(aggregates, profile)
        if states:
            report.append("\n<b>🔍 Обнаруженные состояния:</b>\n")
            for s in states:
                if s.detected:
                    name = state_name_ru(s.state_type)
                    report.append(f"{s.emoji} <b>{name}</b>")
                    report.append(f"   {s.recommendation[:100]}...")
        report.append("\n<b>💡 Рекомендации на следующую неделю:</b>\n")
        recs = self._generate_recommendations(aggregates, profile)
        for r in recs:
            report.append(f"• {r}")
        report.append("\n─────────────────")
        report.append("\n📝 <i>Заполняй метрики каждый день для точного анализа!</i>")
        return "\n".join(report)

    def _generate_recommendations(self, aggregates: List[DailyAggregate], profile: dict) -> List[str]:
        recs = []
        avg_sleep = safe_average([a.sleep.hours for a in aggregates if a.sleep.hours])
        if avg_sleep and avg_sleep < 7:
            recs.append("Старайся спать 7-8 часов — это улучшит метаболизм на 8-12%")
        avg_steps = safe_average([a.activity.steps for a in aggregates if a.activity.steps])
        if avg_steps and avg_steps < 8000:
            recs.append("Увеличь NEAT до 8000-10000 шагов в день для +300-500 ккал")
        avg_protein = safe_average([a.nutrition.total_protein_g for a in aggregates])
        weight = aggregates[-1].measurements.weight_kg if aggregates else 70
        if avg_protein and weight and avg_protein < weight * 1.6:
            recs.append(f"Увеличь белок до {int(weight * 1.6)} г/день")
        if not recs:
            recs.append("Продолжай в том же духе! 💪")
        return recs[:3]