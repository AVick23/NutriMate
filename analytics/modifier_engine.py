"""
Модуль расчёта модификаторов TDEE.
Корректирует базовый расход калорий на основе ежедневных метрик.
"""
import logging
from datetime import date
from typing import Tuple, Dict, Any, Optional, List

from db import Database, UserRepository
from analytics.models import DailyAggregate

logger = logging.getLogger(__name__)


class ModifierEngine:
    """
    Рассчитывает скорректированный TDEE на основе метрик дня.
    
    Научное обоснование:
    - Sleep: Spiegel et al., Lancet 2004; Leproult et al., Lancet Diabetes Endocrinol 2015
    - Stress: Epel et al., Psychosom Med 2000
    - NEAT: Levine et al., Science 1999
    - Eating window: Sutton et al., Cell Metabolism 2018
    """
    
    # MET значения для разных типов тренировок
    MET_VALUES = {
        "strength": 5.0,
        "cardio": 8.0,
        "yoga": 3.0,
        "walk": 3.5,
        "swim": 7.0,
    }
    
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)

    async def calculate_adjusted_tdee(
        self,
        user_id: int,
        base_tdee: int,
        aggregated: DailyAggregate,
        previous_days: Optional[List[DailyAggregate]] = None
    ) -> Tuple[int, Dict[str, Any], int]:
        """
        Рассчитывает скорректированный TDEE.
        
        Returns:
            (adjusted_tdee, modifiers_dict, confidence_score)
        """
        modifiers = {}
        metrics_used = []
        missing_metrics = []

        # 1. Sleep Modifier (многофакторный)
        sleep_mod, sleep_used, sleep_missing = self._calculate_sleep_modifier(aggregated)
        modifiers["sleep_modifier"] = sleep_mod
        metrics_used.extend(sleep_used)
        missing_metrics.extend(sleep_missing)

        # 2. Energy Modifier (с учётом тренда)
        energy_mod, energy_used, energy_missing = await self._calculate_energy_modifier(
            user_id, aggregated, previous_days
        )
        modifiers["energy_modifier"] = energy_mod
        metrics_used.extend(energy_used)
        missing_metrics.extend(energy_missing)

        # 3. Stress Modifier
        stress_mod, stress_used, stress_missing = self._calculate_stress_modifier(aggregated)
        modifiers["stress_modifier"] = stress_mod
        metrics_used.extend(stress_used)
        missing_metrics.extend(stress_missing)

        # 4. Activity Modifier (NEAT)
        activity_mod, activity_used, activity_missing = self._calculate_activity_modifier(aggregated)
        modifiers["activity_modifier"] = activity_mod
        metrics_used.extend(activity_used)
        missing_metrics.extend(activity_missing)

        # 5. Eating Window Modifier
        window_mod, window_used, window_missing = self._calculate_window_modifier(aggregated)
        modifiers["window_modifier"] = window_mod
        metrics_used.extend(window_used)
        missing_metrics.extend(window_missing)

        # 6. Workout Bonus
        workout_bonus, workout_used, workout_missing = await self._calculate_workout_bonus(
            aggregated, user_id
        )
        modifiers["workout_bonus"] = workout_bonus
        metrics_used.extend(workout_used)
        missing_metrics.extend(workout_missing)

        # Сохраняем модификаторы в объект
        aggregated.sleep_modifier = sleep_mod
        aggregated.energy_modifier = energy_mod
        aggregated.stress_modifier = stress_mod
        aggregated.activity_modifier = activity_mod
        aggregated.window_modifier = window_mod
        aggregated.workout_bonus = workout_bonus

        # Финальный расчёт
        adjusted = base_tdee
        for key in ["sleep_modifier", "energy_modifier", "stress_modifier", 
                    "activity_modifier", "window_modifier"]:
            adjusted = int(adjusted * modifiers.get(key, 1.0))
        adjusted += workout_bonus

        aggregated.adjusted_tdee = adjusted

        # Confidence score
        total_metrics = len(metrics_used) + len(missing_metrics)
        if total_metrics == 0:
            confidence = 100
        else:
            confidence = int((len(metrics_used) / total_metrics) * 100)
        aggregated.confidence_score = confidence

        return adjusted, modifiers, confidence

    def _calculate_sleep_modifier(
        self, aggregated: DailyAggregate
    ) -> Tuple[float, List[str], List[str]]:
        """Рассчитывает модификатор сна."""
        hours = aggregated.sleep.hours
        quality = aggregated.sleep.quality
        awakenings = aggregated.sleep.awakenings

        used = []
        missing = []

        if hours is None:
            missing.append("sleep_hours")
            return 1.0, used, missing

        used.append("sleep_hours")

        # Базовый коэффициент по длительности
        if hours < 5:
            duration_factor = 0.88
        elif hours < 6:
            duration_factor = 0.92
        elif hours < 7:
            duration_factor = 0.97
        elif hours <= 9:
            duration_factor = 1.00
        else:
            duration_factor = 0.98

        # Коэффициент качества
        if quality is not None:
            used.append("sleep_quality")
            if quality <= 2:
                quality_factor = 0.97
            elif quality == 3:
                quality_factor = 1.00
            else:
                quality_factor = 1.02
        else:
            quality_factor = 1.00
            missing.append("sleep_quality")

        # Коэффициент пробуждений
        if awakenings is not None:
            used.append("sleep_awakenings")
            if awakenings <= 1:
                awakenings_factor = 1.00
            elif awakenings == 2:
                awakenings_factor = 0.99
            else:
                awakenings_factor = 0.97
        else:
            awakenings_factor = 1.00
            missing.append("sleep_awakenings")

        modifier = duration_factor * quality_factor * awakenings_factor
        return round(modifier, 3), used, missing

    async def _calculate_energy_modifier(
        self,
        user_id: int,
        aggregated: DailyAggregate,
        previous_days: Optional[List[DailyAggregate]]
    ) -> Tuple[float, List[str], List[str]]:
        """Рассчитывает модификатор энергии (с учётом тренда)."""
        avg_energy = aggregated.derived.avg_energy

        used = []
        missing = []

        if avg_energy is None:
            missing.append("energy")
            return 1.0, used, missing

        used.append("energy")

        # Одиночный день
        if avg_energy >= 8:
            modifier = 1.05
        elif avg_energy >= 6:
            modifier = 1.00
        elif avg_energy >= 4:
            modifier = 0.97
        else:
            modifier = 0.90

        # Учёт длительности дефицита (если есть данные за предыдущие дни)
        if previous_days and len(previous_days) >= 3:
            low_energy_days = 0
            for day in previous_days[:3]:
                if day.derived.avg_energy and day.derived.avg_energy <= 5:
                    low_energy_days += 1
            
            if low_energy_days >= 3:
                modifier *= 0.95  # дополнительное снижение при хронической усталости

        return round(modifier, 3), used, missing

    def _calculate_stress_modifier(
        self, aggregated: DailyAggregate
    ) -> Tuple[float, List[str], List[str]]:
        """Рассчитывает модификатор стресса."""
        stress = aggregated.stress
        
        used = []
        missing = []

        if stress is None:
            missing.append("stress")
            return 1.0, used, missing

        used.append("stress")

        if stress <= 3:
            modifier = 1.00
        elif stress <= 6:
            modifier = 0.98
        elif stress <= 8:
            modifier = 0.95
        else:
            modifier = 0.93

        return round(modifier, 3), used, missing

    def _calculate_activity_modifier(
        self, aggregated: DailyAggregate
    ) -> Tuple[float, List[str], List[str]]:
        """Рассчитывает модификатор активности (NEAT)."""
        steps = aggregated.activity.steps

        used = []
        missing = []

        if steps is None:
            missing.append("steps")
            return 1.0, used, missing

        used.append("steps")

        if steps < 3000:
            modifier = 0.95
        elif steps < 5000:
            modifier = 0.97
        elif steps < 8000:
            modifier = 0.99
        elif steps < 10000:
            modifier = 1.00
        elif steps < 15000:
            modifier = 1.02
        else:
            modifier = 1.05

        return round(modifier, 3), used, missing

    def _calculate_window_modifier(
        self, aggregated: DailyAggregate
    ) -> Tuple[float, List[str], List[str]]:
        """Рассчитывает модификатор окна питания."""
        window_hours = aggregated.derived.eating_window_hours

        used = []
        missing = []

        if window_hours is None:
            missing.append("eating_window")
            return 1.0, used, missing

        used.append("eating_window")

        if window_hours < 8:
            modifier = 1.05
        elif window_hours < 10:
            modifier = 1.03
        elif window_hours < 12:
            modifier = 1.00
        elif window_hours < 14:
            modifier = 0.97
        else:
            modifier = 0.93

        return round(modifier, 3), used, missing

    async def _calculate_workout_bonus(
        self,
        aggregated: DailyAggregate,
        user_id: int
    ) -> Tuple[int, List[str], List[str]]:
        """
        Рассчитывает бонус за тренировку.
        Формула: MET × weight × duration_h × intensity_factor × 0.5
        """
        workout_type = aggregated.workout.type
        duration_min = aggregated.workout.duration_min
        intensity = aggregated.workout.intensity

        used = []
        missing = []

        if not workout_type or workout_type == "none" or not duration_min:
            missing.append("workout")
            return 0, used, missing

        used.append("workout_type")
        used.append("workout_duration")

        # MET значение
        met = self.MET_VALUES.get(workout_type, 5.0)

        # Интенсивность
        if intensity is not None:
            used.append("workout_intensity")
            intensity_factor = intensity / 10.0
        else:
            intensity_factor = 0.7

        # Вес пользователя
        weight = aggregated.measurements.weight_kg
        if not weight:
            # Пытаемся получить из профиля
            profile = await self.user_repo.get_profile(user_id)
            if profile:
                # Берём последний вес из замеров или из профиля
                weight = profile.get("weight_kg", 70)
            else:
                weight = 70

        # Расчёт
        duration_h = duration_min / 60.0
        bonus = int(met * weight * duration_h * intensity_factor * 0.5)

        return bonus, used, missing