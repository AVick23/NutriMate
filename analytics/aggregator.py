"""
Агрегатор данных за день.
Собирает информацию из всех таблиц в единую структуру.
"""
import logging
from datetime import date, datetime
from typing import Dict, Any, Optional

from db import Database, UserRepository, DailyMetricsRepository
from analytics.models import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics
)

logger = logging.getLogger(__name__)


class DailyAggregator:
    """Собирает и агрегирует все данные пользователя за указанный день."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.daily_metrics_repo = DailyMetricsRepository(db)

    async def aggregate(self, user_id: int, target_date: date) -> DailyAggregate:
        """
        Собирает все данные за день в единую структуру DailyAggregate.
        """
        result = DailyAggregate(date=target_date, user_id=user_id)

        # 1. Питание (из meals)
        nutrition = await self._aggregate_nutrition(user_id, target_date)
        result.nutrition = nutrition

        # 2. Вода
        result.water_ml = await self._aggregate_water(user_id, target_date)

        # 3. Замеры тела (последние за день)
        measurements = await self._aggregate_measurements(user_id, target_date)
        result.measurements = measurements

        # 4. Метрики из daily_metrics
        metrics = await self.daily_metrics_repo.get_metrics(user_id, target_date)
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

        # 5. Рассчитанные метрики (derived)
        result.derived = self._calculate_derived_metrics(result)

        return result

    async def _aggregate_nutrition(
        self, user_id: int, target_date: date
    ) -> NutritionData:
        """Агрегирует данные о питании за день."""
        date_str = target_date.isoformat()
        
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT 
                    COUNT(*) as meal_count,
                    SUM(kcal) as total_kcal,
                    SUM(protein_g) as total_protein,
                    SUM(fat_g) as total_fat,
                    SUM(carbs_g) as total_carbs,
                    MIN(eaten_at) as first_meal,
                    MAX(eaten_at) as last_meal
                FROM meals 
                WHERE user_id = ? AND DATE(eaten_at) = ?
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
        """Агрегирует данные о воде за день."""
        date_str = target_date.isoformat()
        
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT COALESCE(SUM(amount_ml), 0) as total_ml
                FROM water_logs 
                WHERE user_id = ? AND DATE(logged_at) = ?
            """, (user_id, date_str))
            row = await cursor.fetchone()
            return row["total_ml"] or 0

    async def _aggregate_measurements(
        self, user_id: int, target_date: date
    ) -> MeasurementsData:
        """Получает последние замеры тела за день (или ближайшие предыдущие)."""
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
                if name == "weight":
                    result.weight_kg = value
                elif name == "waist":
                    result.waist_cm = value
                elif name == "hips":
                    result.hips_cm = value
                elif name == "chest":
                    result.chest_cm = value
                elif name == "arm":
                    result.arm_cm = value
                elif name == "thigh":
                    result.thigh_cm = value
            
            return result

    def _calculate_derived_metrics(self, aggregated: DailyAggregate) -> DerivedMetrics:
        """Рассчитывает производные метрики."""
        derived = DerivedMetrics()

        # Окно питания
        if aggregated.nutrition.first_meal_at and aggregated.nutrition.last_meal_at:
            try:
                first = aggregated.nutrition.first_meal_at
                last = aggregated.nutrition.last_meal_at
                if isinstance(first, str):
                    first = datetime.fromisoformat(first.replace(" ", "T"))
                if isinstance(last, str):
                    last = datetime.fromisoformat(last.replace(" ", "T"))
                window = (last - first).total_seconds() / 3600
                derived.eating_window_hours = round(window, 1)
                derived.last_meal_hour = last.hour
            except Exception:
                pass

        # Белок на кг веса
        weight = aggregated.measurements.weight_kg
        protein = aggregated.nutrition.total_protein_g
        if weight and weight > 0 and protein > 0:
            derived.protein_per_kg = round(protein / weight, 1)

        # Вода на кг веса
        water_ml = aggregated.water_ml
        if weight and weight > 0 and water_ml > 0:
            derived.water_per_kg = round(water_ml / weight, 1)

        # Средняя энергия
        if aggregated.energy.morning and aggregated.energy.evening:
            derived.avg_energy = (aggregated.energy.morning + aggregated.energy.evening) / 2

        return derived