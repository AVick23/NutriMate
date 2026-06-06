"""
Аналитика: сбор данных (aggregator) и расчёт модификаторов TDEE (modifier_engine).
"""
import logging
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from db import Database, UserRepository
from .core import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics
)

logger = logging.getLogger(__name__)


class DailyMetricsRepository:
    """
    Репозиторий для таблицы daily_metrics.
    """
    def __init__(self, db: Database):
        self.db = db

    async def save_metric(self, user_id: int, metric_type: str, value: Any,
                          sub_type: str = None, recorded_for_date: str = None) -> None:
        if recorded_for_date is None:
            recorded_for_date = date.today().isoformat()
        async with self.db.transaction() as conn:
            await conn.execute("""
                INSERT INTO daily_metrics (user_id, metric_type, value, sub_type, recorded_for_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, metric_type, sub_type, recorded_for_date) DO UPDATE SET
                value = excluded.value, recorded_at = CURRENT_TIMESTAMP
            """, (user_id, metric_type, value, sub_type, recorded_for_date))

    async def get_metrics(self, user_id: int, target_date: date) -> Dict[str, Any]:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT metric_type, value, sub_type FROM daily_metrics WHERE user_id = ? AND recorded_for_date = ?",
                (user_id, date_str)
            )
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                mt = row["metric_type"]
                st = row["sub_type"]
                val = row["value"]
                if mt == "sleep_hours":
                    result["sleep_hours"] = val
                elif mt == "sleep_quality":
                    result["sleep_quality"] = int(val)
                elif mt == "sleep_awakenings":
                    result["sleep_awakenings"] = int(val)
                elif mt == "energy":
                    if st == "morning":
                        result["energy_morning"] = int(val)
                    elif st == "evening":
                        result["energy_evening"] = int(val)
                elif mt == "stress":
                    result["stress_level"] = int(val)
                elif mt == "steps":
                    result["steps"] = int(val)
                elif mt == "hours_on_feet":
                    result["hours_on_feet"] = val
                elif mt == "workout_type":
                    result["workout_type"] = val
                elif mt == "workout_duration":
                    result["workout_duration"] = int(val)
                elif mt == "workout_intensity":
                    result["workout_intensity"] = int(val)
            return result

    async def save_metrics(self, user_id: int, target_date: date, metrics: Dict[str, Any]) -> None:
        """
        Сохраняет все метрики за день, переданные в виде словаря.
        Преобразует ключи словаря в соответствующие metric_type и sub_type.
        """
        # Маппинг: ключ в metrics -> (metric_type, sub_type)
        mapping = {
            "sleep_hours": ("sleep_hours", None),
            "sleep_quality": ("sleep_quality", None),
            "sleep_awakenings": ("sleep_awakenings", None),
            "energy_morning": ("energy", "morning"),
            "energy_evening": ("energy", "evening"),
            "stress_level": ("stress", None),
            "steps": ("steps", None),
            "hours_on_feet": ("hours_on_feet", None),
            "workout_type": ("workout_type", None),
            "workout_duration": ("workout_duration", None),
            "workout_intensity": ("workout_intensity", None),
        }
        for key, value in metrics.items():
            if value is None:
                continue
            if key in mapping:
                metric_type, sub_type = mapping[key]
                await self.save_metric(user_id, metric_type, value, sub_type, target_date.isoformat())
            else:
                logger.warning(f"Unknown metric key: {key}")


class DailyAggregator:
    """Собирает и агрегирует все данные пользователя за указанный день."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.metrics_repo = DailyMetricsRepository(db)

    async def aggregate(self, user_id: int, target_date: date) -> DailyAggregate:
        result = DailyAggregate(date=target_date, user_id=user_id)

        # Питание
        nutrition = await self._aggregate_nutrition(user_id, target_date)
        result.nutrition = nutrition

        # Вода
        result.water_ml = await self._aggregate_water(user_id, target_date)

        # Замеры тела
        measurements = await self._aggregate_measurements(user_id, target_date)
        result.measurements = measurements

        # Метрики из daily_metrics
        metrics = await self.metrics_repo.get_metrics(user_id, target_date)
        if metrics:
            result.sleep = SleepData(
                hours=metrics.get("sleep_hours"),
                quality=metrics.get("sleep_quality"),
                awakenings=metrics.get("sleep_awakenings"),
            )
            result.energy = EnergyData(
                morning=metrics.get("energy_morning"),
                evening=metrics.get("energy_evening"),
            )
            result.stress = metrics.get("stress_level")
            result.activity = ActivityData(
                steps=metrics.get("steps"),
                hours_on_feet=metrics.get("hours_on_feet"),
            )
            result.workout = WorkoutData(
                type=metrics.get("workout_type"),
                duration_min=metrics.get("workout_duration"),
                intensity=metrics.get("workout_intensity"),
            )

        # Производные метрики
        result.derived = self._calculate_derived_metrics(result)

        return result

    async def _aggregate_nutrition(self, user_id: int, target_date: date) -> NutritionData:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT COUNT(*) as meal_count,
                       SUM(kcal) as total_kcal,
                       SUM(protein_g) as total_protein,
                       SUM(fat_g) as total_fat,
                       SUM(carbs_g) as total_carbs,
                       MIN(eaten_at) as first_meal,
                       MAX(eaten_at) as last_meal
                FROM meals WHERE user_id = ? AND DATE(eaten_at) = ?
            """, (user_id, date_str))
            row = await cursor.fetchone()
            return NutritionData(
                total_kcal=row["total_kcal"] or 0,
                total_protein_g=row["total_protein"] or 0.0,
                total_fat_g=row["total_fat"] or 0.0,
                total_carbs_g=row["total_carbs"] or 0.0,
                meal_count=row["meal_count"] or 0,
                first_meal_at=row["first_meal"],
                last_meal_at=row["last_meal"],
            )

    async def _aggregate_water(self, user_id: int, target_date: date) -> int:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(amount_ml), 0) as total_ml FROM water_logs WHERE user_id = ? AND DATE(logged_at) = ?",
                (user_id, date_str)
            )
            row = await cursor.fetchone()
            return row["total_ml"] or 0

    async def _aggregate_measurements(self, user_id: int, target_date: date) -> MeasurementsData:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT m.measurement_type_id, m.value, mt.name
                FROM body_measurements m
                JOIN measurement_types mt ON m.measurement_type_id = mt.id
                WHERE m.user_id = ? AND DATE(m.measured_at) <= ?
                GROUP BY m.measurement_type_id
                HAVING DATE(m.measured_at) = MAX(DATE(m.measured_at))
            """, (user_id, date_str))
            rows = await cursor.fetchall()
            result = MeasurementsData()
            for row in rows:
                name = row["name"]
                value = row["value"]
                if name == "weight": result.weight_kg = value
                elif name == "waist": result.waist_cm = value
                elif name == "hips": result.hips_cm = value
                elif name == "chest": result.chest_cm = value
                elif name == "arm": result.arm_cm = value
                elif name == "thigh": result.thigh_cm = value
            return result

    def _calculate_derived_metrics(self, agg: DailyAggregate) -> DerivedMetrics:
        derived = DerivedMetrics()
        # Окно питания
        if agg.nutrition.first_meal_at and agg.nutrition.last_meal_at:
            try:
                first = agg.nutrition.first_meal_at
                last = agg.nutrition.last_meal_at
                if isinstance(first, str): first = datetime.fromisoformat(first.replace(" ", "T"))
                if isinstance(last, str): last = datetime.fromisoformat(last.replace(" ", "T"))
                window = (last - first).total_seconds() / 3600
                derived.eating_window_hours = round(window, 1)
                derived.last_meal_hour = last.hour
            except Exception:
                pass
        # Белок на кг
        weight = agg.measurements.weight_kg
        protein = agg.nutrition.total_protein_g
        if weight and weight > 0 and protein > 0:
            derived.protein_per_kg = round(protein / weight, 1)
        # Вода на кг
        water_ml = agg.water_ml
        if weight and weight > 0 and water_ml > 0:
            derived.water_per_kg = round(water_ml / weight, 1)
        # Средняя энергия
        if agg.energy.morning and agg.energy.evening:
            derived.avg_energy = (agg.energy.morning + agg.energy.evening) / 2
        return derived


class ModifierEngine:
    """
    Рассчитывает скорректированный TDEE на основе метрик дня.
    """
    MET_VALUES = {"strength": 5.0, "cardio": 8.0, "yoga": 3.0, "walk": 3.5, "swim": 7.0}

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)

    async def calculate_adjusted_tdee(
        self, user_id: int, base_tdee: int, aggregated: DailyAggregate,
        previous_days: Optional[List[DailyAggregate]] = None
    ) -> Tuple[int, Dict[str, Any], int]:
        modifiers = {}
        metrics_used, missing_metrics = [], []

        # 1. Сон
        sleep_mod, used, missing = self._calculate_sleep_modifier(aggregated)
        modifiers["sleep_modifier"] = sleep_mod
        metrics_used.extend(used); missing_metrics.extend(missing)

        # 2. Энергия
        energy_mod, used, missing = await self._calculate_energy_modifier(user_id, aggregated, previous_days)
        modifiers["energy_modifier"] = energy_mod
        metrics_used.extend(used); missing_metrics.extend(missing)

        # 3. Стресс
        stress_mod, used, missing = self._calculate_stress_modifier(aggregated)
        modifiers["stress_modifier"] = stress_mod
        metrics_used.extend(used); missing_metrics.extend(missing)

        # 4. Активность (NEAT)
        activity_mod, used, missing = self._calculate_activity_modifier(aggregated)
        modifiers["activity_modifier"] = activity_mod
        metrics_used.extend(used); missing_metrics.extend(missing)

        # 5. Окно питания
        window_mod, used, missing = self._calculate_window_modifier(aggregated)
        modifiers["window_modifier"] = window_mod
        metrics_used.extend(used); missing_metrics.extend(missing)

        # 6. Тренировка
        workout_bonus, used, missing = await self._calculate_workout_bonus(aggregated, user_id)
        modifiers["workout_bonus"] = workout_bonus
        metrics_used.extend(used); missing_metrics.extend(missing)

        # Сохраняем в объект агрегата
        aggregated.sleep_modifier = sleep_mod
        aggregated.energy_modifier = energy_mod
        aggregated.stress_modifier = stress_mod
        aggregated.activity_modifier = activity_mod
        aggregated.window_modifier = window_mod
        aggregated.workout_bonus = workout_bonus

        # Финальный расчёт
        adjusted = base_tdee
        for key in ("sleep_modifier", "energy_modifier", "stress_modifier",
                    "activity_modifier", "window_modifier"):
            adjusted = int(adjusted * modifiers.get(key, 1.0))
        adjusted += workout_bonus
        aggregated.adjusted_tdee = adjusted

        # Confidence
        total = len(metrics_used) + len(missing_metrics)
        confidence = 100 if total == 0 else int((len(metrics_used) / total) * 100)
        aggregated.confidence_score = confidence

        return adjusted, modifiers, confidence

    def _calculate_sleep_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        hours = agg.sleep.hours
        used, missing = [], []
        if hours is None:
            missing.append("sleep_hours")
            return 1.0, used, missing
        used.append("sleep_hours")
        if hours < 5: duration = 0.88
        elif hours < 6: duration = 0.92
        elif hours < 7: duration = 0.97
        elif hours <= 9: duration = 1.00
        else: duration = 0.98
        quality = agg.sleep.quality
        if quality is not None:
            used.append("sleep_quality")
            quality_factor = 0.97 if quality <= 2 else 1.00 if quality == 3 else 1.02
        else:
            quality_factor = 1.00
            missing.append("sleep_quality")
        awakenings = agg.sleep.awakenings
        if awakenings is not None:
            used.append("sleep_awakenings")
            awakenings_factor = 1.00 if awakenings <= 1 else 0.99 if awakenings == 2 else 0.97
        else:
            awakenings_factor = 1.00
            missing.append("sleep_awakenings")
        mod = duration * quality_factor * awakenings_factor
        return round(mod, 3), used, missing

    async def _calculate_energy_modifier(self, user_id: int, agg: DailyAggregate,
                                         prev: Optional[List[DailyAggregate]]) -> Tuple[float, List[str], List[str]]:
        avg_energy = agg.derived.avg_energy
        used, missing = [], []
        if avg_energy is None:
            missing.append("energy")
            return 1.0, used, missing
        used.append("energy")
        if avg_energy >= 8: mod = 1.05
        elif avg_energy >= 6: mod = 1.00
        elif avg_energy >= 4: mod = 0.97
        else: mod = 0.90
        if prev and len(prev) >= 3:
            low = sum(1 for d in prev[:3] if d.derived.avg_energy and d.derived.avg_energy <= 5)
            if low >= 3:
                mod *= 0.95
        return round(mod, 3), used, missing

    def _calculate_stress_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        stress = agg.stress
        used, missing = [], []
        if stress is None:
            missing.append("stress")
            return 1.0, used, missing
        used.append("stress")
        if stress <= 3: mod = 1.00
        elif stress <= 6: mod = 0.98
        elif stress <= 8: mod = 0.95
        else: mod = 0.93
        return round(mod, 3), used, missing

    def _calculate_activity_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        steps = agg.activity.steps
        used, missing = [], []
        if steps is None:
            missing.append("steps")
            return 1.0, used, missing
        used.append("steps")
        if steps < 3000: mod = 0.95
        elif steps < 5000: mod = 0.97
        elif steps < 8000: mod = 0.99
        elif steps < 10000: mod = 1.00
        elif steps < 15000: mod = 1.02
        else: mod = 1.05
        return round(mod, 3), used, missing

    def _calculate_window_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        window = agg.derived.eating_window_hours
        used, missing = [], []
        if window is None:
            missing.append("eating_window")
            return 1.0, used, missing
        used.append("eating_window")
        if window < 8: mod = 1.05
        elif window < 10: mod = 1.03
        elif window < 12: mod = 1.00
        elif window < 14: mod = 0.97
        else: mod = 0.93
        return round(mod, 3), used, missing

    async def _calculate_workout_bonus(self, agg: DailyAggregate, user_id: int) -> Tuple[int, List[str], List[str]]:
        wtype = agg.workout.type
        duration = agg.workout.duration_min
        used, missing = [], []
        if not wtype or wtype == "none" or not duration:
            missing.append("workout")
            return 0, used, missing
        used.append("workout_type"); used.append("workout_duration")
        met = self.MET_VALUES.get(wtype, 5.0)
        intensity = agg.workout.intensity
        if intensity is not None:
            used.append("workout_intensity")
            intensity_factor = intensity / 10.0
        else:
            intensity_factor = 0.7
        weight = agg.measurements.weight_kg
        if not weight:
            profile = await self.user_repo.get_profile(user_id)
            weight = profile.get("weight_kg", 70) if profile else 70
        duration_h = duration / 60.0
        bonus = int(met * weight * duration_h * intensity_factor * 0.5)
        return bonus, used, missing