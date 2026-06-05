"""
Детектор состояний организма на основе совокупности метрик.
"""
import logging
from typing import List, Tuple, Optional

from analytics.models import DailyAggregate, StateDetection

logger = logging.getLogger(__name__)


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
        self,
        aggregates: List[DailyAggregate],
        profile: dict
    ) -> List[StateDetection]:
        """
        Анализирует агрегированные данные и возвращает обнаруженные состояния.
        """
        states = []
        
        # Метаболическая адаптация
        metabolic = self._detect_metabolic_adaptation(aggregates)
        if metabolic:
            states.append(metabolic)
        
        # Рекомпозиция тела
        recomposition = self._detect_body_recomposition(aggregates)
        if recomposition:
            states.append(recomposition)
        
        # Перетренированность
        overtraining = self._detect_overtraining(aggregates)
        if overtraining:
            states.append(overtraining)
        
        # Стрессовое плато
        stress_plateau = self._detect_stress_plateau(aggregates)
        if stress_plateau:
            states.append(stress_plateau)
        
        # Инсулинорезистентность
        insulin_resistance = self._detect_insulin_resistance(aggregates, profile)
        if insulin_resistance:
            states.append(insulin_resistance)
        
        return states

    def _detect_metabolic_adaptation(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """
        Метаболическая адаптация: снижение BMR при длительном дефиците.
        
        Признаки (достаточно 2 из 4):
        - Энергия <5 в течение 5+ дней
        - Плато веса >14 дней при соблюдении КБЖУ
        - Снижение пульса покоя (заглушка)
        """
        if len(aggregates) < 14:
            return None
        
        indicators = []
        
        # 1. Низкая энергия 5+ дней
        low_energy_days = 0
        for agg in aggregates[:14]:
            if agg.derived.avg_energy and agg.derived.avg_energy < 5:
                low_energy_days += 1
        
        if low_energy_days >= 5:
            indicators.append("энергия ниже 5/10 в течение 5+ дней")
        
        # 2. Плато веса 14+ дней
        weights = [agg.measurements.weight_kg for agg in aggregates[:14] if agg.measurements.weight_kg]
        if len(weights) >= 7:
            weight_change = max(weights) - min(weights) if weights else 0
            if abs(weight_change) < 0.5:
                indicators.append("вес стабилен 2+ недели")
        
        if len(indicators) >= 2:
            return StateDetection(
                state_type="metabolic_adaptation",
                detected=True,
                severity="high" if len(indicators) >= 3 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется диет-брейк на 5-7 дней на уровне поддержки. Это восстановит метаболизм и гормональный фон.",
                emoji="🔄",
            )
        
        return None

    def _detect_body_recomposition(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """
        Рекомпозиция тела: вес стабилен, но объёмы уменьшаются.
        
        Признаки:
        - Вес стабилен (±0.5 кг за 2 недели)
        - Талия уменьшается на 1+ см за 2 недели
        """
        if len(aggregates) < 14:
            return None
        
        indicators = []
        
        # Вес стабилен
        weights = [agg.measurements.weight_kg for agg in aggregates[:14] if agg.measurements.weight_kg]
        if len(weights) >= 2:
            weight_change = abs(weights[0] - weights[-1]) if weights else 0
            if weight_change < 0.5:
                indicators.append("вес стабилен (±0.5 кг)")
        
        # Талия уменьшается
        waists = [agg.measurements.waist_cm for agg in aggregates[:14] if agg.measurements.waist_cm]
        if len(waists) >= 2:
            waist_change = waists[0] - waists[-1] if waists else 0
            if waist_change >= 1:
                indicators.append(f"талия уменьшилась на {waist_change:.0f} см")
        
        if len(indicators) >= 2:
            return StateDetection(
                state_type="body_recomposition",
                detected=True,
                severity="positive",
                indicators=indicators,
                recommendation="Отлично! Это лучший сценарий — мышцы растут, жир уходит. НЕ снижай калории, продолжай в том же духе!",
                emoji="🎉",
            )
        
        return None

    def _detect_overtraining(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """
        Перетренированность.
        
        Признаки (3+ из 5):
        - Энергия <4 в течение 3+ дней
        - Частые тренировки (4+ в неделю)
        - Качество сна снизилось
        - Шаги уменьшились
        """
        if len(aggregates) < 14:
            return None
        
        indicators = []
        
        # 1. Низкая энергия
        low_energy_days = 0
        for agg in aggregates[:7]:
            if agg.derived.avg_energy and agg.derived.avg_energy < 4:
                low_energy_days += 1
        
        if low_energy_days >= 3:
            indicators.append("низкая энергия 3+ дня подряд")
        
        # 2. Частые тренировки
        workout_days = sum(1 for agg in aggregates[:7] if agg.workout.type and agg.workout.type != "none")
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
                emoji="⚠️",
            )
        
        return None

    def _detect_stress_plateau(
        self, aggregates: List[DailyAggregate]
    ) -> Optional[StateDetection]:
        """
        Стрессовое плато: высокий стресс + стабильный вес.
        """
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
            weight_change = max(weights[-3:]) - min(weights[-3:]) if weights else 0
            if weight_change < 0.5:
                indicators.append("вес стабилен")
        
        if len(indicators) >= 2:
            return StateDetection(
                state_type="stress_plateau",
                detected=True,
                severity="medium",
                indicators=indicators,
                recommendation="Стресс вызывает задержку воды. НЕ снижай калории! Лучше сосредоточься на управлении стрессом: прогулки, дыхательные практики, сон.",
                emoji="😰",
            )
        
        return None

    def _detect_insulin_resistance(
        self, aggregates: List[DailyAggregate], profile: dict
    ) -> Optional[StateDetection]:
        """
        Косвенная оценка инсулинорезистентности.
        
        Признаки:
        - WHR > 0.90 (М) / > 0.85 (Ж)
        - Частые перекусы (>5 в день)
        """
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
        
        # Частые перекусы (между основными приёмами)
        # Упрощённо: количество приёмов пищи >5
        meal_counts = [agg.nutrition.meal_count for agg in aggregates[:7] if agg.nutrition.meal_count]
        if meal_counts and sum(meal_counts) / len(meal_counts) > 5:
            indicators.append("частые приёмы пищи (>5 раз в день)")
        
        if len(indicators) >= 1:
            return StateDetection(
                state_type="insulin_resistance",
                detected=True,
                severity="high" if len(indicators) >= 2 else "medium",
                indicators=indicators,
                recommendation="Рекомендуется сократить окно питания до 8-10 часов, убрать перекусы между основными приёмами, увеличить потребление белка.",
                emoji="🍬",
            )
        
        return None