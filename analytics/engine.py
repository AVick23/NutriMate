"""
Агрегатор данных, расчёт модификаторов TDEE и генерация графиков.
"""
import io
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from db import Database, UserRepository
from .core import DailyAggregate, NutritionData, SleepData, EnergyData, ActivityData, WorkoutData, MeasurementsData, DerivedMetrics

logger = logging.getLogger(__name__)

# Настройка кириллицы для matplotlib
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class DailyMetricsRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save_metrics(self, user_id: int, metric_date: date, metrics: Dict[str, Any]) -> None:
        valid_keys = {'sleep_hours', 'sleep_quality', 'sleep_awakenings', 'energy_morning', 'energy_evening', 'stress_level', 'steps', 'hours_on_feet', 'workout_type', 'workout_duration', 'workout_intensity', 'hunger_before', 'hunger_after', 'digestion_bristol', 'cycle_day', 'notes'}
        filtered = {k: v for k, v in metrics.items() if k in valid_keys and v is not None}
        if not filtered:
            return
        async with self.db.transaction() as conn:
            cursor = await conn.execute("SELECT 1 FROM daily_metrics WHERE user_id = ? AND metric_date = ?", (user_id, metric_date.isoformat()))
            exists = await cursor.fetchone()
            if exists:
                set_clause = ", ".join(f"{k} = ?" for k in filtered)
                values = list(filtered.values()) + [user_id, metric_date.isoformat()]
                await conn.execute(f"UPDATE daily_metrics SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND metric_date = ?", values)
            else:
                columns = ", ".join(filtered.keys()) + ", user_id, metric_date"
                placeholders = ", ".join(["?"] * (len(filtered) + 2))
                values = list(filtered.values()) + [user_id, metric_date.isoformat()]
                await conn.execute(f"INSERT INTO daily_metrics ({columns}) VALUES ({placeholders})", values)

    async def get_metrics(self, user_id: int, metric_date: date) -> Dict[str, Any]:
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT * FROM daily_metrics WHERE user_id = ? AND metric_date = ?", (user_id, metric_date.isoformat()))
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                for key in ('id', 'user_id', 'metric_date', 'created_at', 'updated_at'):
                    result.pop(key, None)
                return result
            return {}

    async def get_metrics_range(self, user_id: int, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT * FROM daily_metrics WHERE user_id = ? AND metric_date BETWEEN ? AND ? ORDER BY metric_date ASC", (user_id, start_date.isoformat(), end_date.isoformat()))
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                for key in ('id', 'user_id', 'created_at', 'updated_at'):
                    d.pop(key, None)
                result.append(d)
            return result

    async def save_metric(self, user_id: int, metric_type: str, value: Any, sub_type: str = None, recorded_for_date: str = None) -> None:
        if recorded_for_date is None:
            recorded_for_date = date.today().isoformat()
        metric_date = date.fromisoformat(recorded_for_date)
        mapping = {("sleep", "hours"): "sleep_hours", ("sleep", "quality"): "sleep_quality", ("sleep", "awakenings"): "sleep_awakenings", ("energy", "morning"): "energy_morning", ("energy", "evening"): "energy_evening", ("stress", None): "stress_level", ("steps", None): "steps", ("hours_on_feet", None): "hours_on_feet", ("workout", "type"): "workout_type", ("workout", "duration"): "workout_duration", ("workout", "intensity"): "workout_intensity"}
        col = mapping.get((metric_type, sub_type))
        if col is None:
            logger.warning(f"Unknown metric mapping: {metric_type}/{sub_type}")
            return
        await self.save_metrics(user_id, metric_date, {col: value})

class DailyAggregator:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.metrics_repo = DailyMetricsRepository(db)

    async def aggregate(self, user_id: int, target_date: date) -> DailyAggregate:
        result = DailyAggregate(date=target_date, user_id=user_id)
        result.nutrition = await self._aggregate_nutrition(user_id, target_date)
        result.water_ml = await self._aggregate_water(user_id, target_date)
        result.measurements = await self._aggregate_measurements(user_id, target_date)
        metrics = await self.metrics_repo.get_metrics(user_id, target_date)
        if metrics:
            result.sleep = SleepData(hours=metrics.get("sleep_hours"), quality=metrics.get("sleep_quality"), awakenings=metrics.get("sleep_awakenings"))
            result.energy = EnergyData(morning=metrics.get("energy_morning"), evening=metrics.get("energy_evening"))
            result.stress = metrics.get("stress_level")
            result.activity = ActivityData(steps=metrics.get("steps"), hours_on_feet=metrics.get("hours_on_feet"))
            result.workout = WorkoutData(type=metrics.get("workout_type"), duration_min=metrics.get("workout_duration"), intensity=metrics.get("workout_intensity"))
        result.derived = self._calculate_derived_metrics(result)
        return result

    async def _aggregate_nutrition(self, user_id: int, target_date: date) -> NutritionData:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) as meal_count, SUM(kcal) as total_kcal, SUM(protein_g) as total_protein, SUM(fat_g) as total_fat, SUM(carbs_g) as total_carbs, MIN(eaten_at) as first_meal, MAX(eaten_at) as last_meal FROM meals WHERE user_id = ? AND DATE(eaten_at) = ?", (user_id, date_str))
            row = await cursor.fetchone()
            return NutritionData(total_kcal=row["total_kcal"] or 0, total_protein_g=row["total_protein"] or 0.0, total_fat_g=row["total_fat"] or 0.0, total_carbs_g=row["total_carbs"] or 0.0, meal_count=row["meal_count"] or 0, first_meal_at=row["first_meal"], last_meal_at=row["last_meal"])

    async def _aggregate_water(self, user_id: int, target_date: date) -> int:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT COALESCE(SUM(amount_ml), 0) as total_ml FROM water_logs WHERE user_id = ? AND DATE(logged_at) = ?", (user_id, date_str))
            row = await cursor.fetchone()
            return row["total_ml"] or 0

    async def _aggregate_measurements(self, user_id: int, target_date: date) -> MeasurementsData:
        date_str = target_date.isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute("SELECT m.measurement_type_id, m.value, mt.name FROM body_measurements m JOIN measurement_types mt ON m.measurement_type_id = mt.id WHERE m.user_id = ? AND DATE(m.measured_at) <= ? GROUP BY m.measurement_type_id HAVING DATE(m.measured_at) = MAX(DATE(m.measured_at))", (user_id, date_str))
            rows = await cursor.fetchall()
            result = MeasurementsData()
            for row in rows:
                name, value = row["name"], row["value"]
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

    def _calculate_derived_metrics(self, agg: DailyAggregate) -> DerivedMetrics:
        derived = DerivedMetrics()
        if agg.nutrition.first_meal_at and agg.nutrition.last_meal_at:
            try:
                first = agg.nutrition.first_meal_at if isinstance(agg.nutrition.first_meal_at, datetime) else datetime.fromisoformat(str(agg.nutrition.first_meal_at).replace(" ", "T"))
                last = agg.nutrition.last_meal_at if isinstance(agg.nutrition.last_meal_at, datetime) else datetime.fromisoformat(str(agg.nutrition.last_meal_at).replace(" ", "T"))
                window = (last - first).total_seconds() / 3600
                derived.eating_window_hours = round(window, 1)
                derived.last_meal_hour = last.hour
            except Exception:
                pass
        weight = agg.measurements.weight_kg
        protein = agg.nutrition.total_protein_g
        if weight and weight > 0 and protein > 0:
            derived.protein_per_kg = round(protein / weight, 1)
        water_ml = agg.water_ml
        if weight and weight > 0 and water_ml > 0:
            derived.water_per_kg = round(water_ml / weight, 1)
        if agg.energy.morning and agg.energy.evening:
            derived.avg_energy = (agg.energy.morning + agg.energy.evening) / 2
        return derived

class ModifierEngine:
    MET_VALUES = {"strength": 5.0, "cardio": 8.0, "yoga": 3.0, "walk": 3.5, "swim": 7.0}

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)

    async def calculate_adjusted_tdee(self, user_id: int, base_tdee: int, aggregated: DailyAggregate, previous_days: Optional[List[DailyAggregate]] = None) -> Tuple[int, Dict[str, Any], int]:
        modifiers = {}
        metrics_used = []
        missing_metrics = []

        sleep_mod, used, missing = self._calculate_sleep_modifier(aggregated)
        modifiers["sleep_modifier"] = sleep_mod
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        energy_mod, used, missing = await self._calculate_energy_modifier(user_id, aggregated, previous_days)
        modifiers["energy_modifier"] = energy_mod
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        stress_mod, used, missing = self._calculate_stress_modifier(aggregated)
        modifiers["stress_modifier"] = stress_mod
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        activity_mod, used, missing = self._calculate_activity_modifier(aggregated)
        modifiers["activity_modifier"] = activity_mod
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        window_mod, used, missing = self._calculate_window_modifier(aggregated)
        modifiers["window_modifier"] = window_mod
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        workout_bonus, used, missing = await self._calculate_workout_bonus(aggregated, user_id)
        modifiers["workout_bonus"] = workout_bonus
        metrics_used.extend(used)
        missing_metrics.extend(missing)

        aggregated.sleep_modifier = sleep_mod
        aggregated.energy_modifier = energy_mod
        aggregated.stress_modifier = stress_mod
        aggregated.activity_modifier = activity_mod
        aggregated.window_modifier = window_mod
        aggregated.workout_bonus = workout_bonus

        adjusted = base_tdee
        for key in ("sleep_modifier", "energy_modifier", "stress_modifier", "activity_modifier", "window_modifier"):
            adjusted = int(adjusted * modifiers.get(key, 1.0))
        adjusted += workout_bonus
        aggregated.adjusted_tdee = adjusted

        total = len(metrics_used) + len(missing_metrics)
        confidence = (100 if total == 0 else int((len(metrics_used) / total) * 100))
        aggregated.confidence_score = confidence

        return adjusted, modifiers, confidence

    def _calculate_sleep_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        hours = agg.sleep.hours
        used, missing = [], []
        if hours is None:
            missing.append("sleep_hours")
            return 1.0, used, missing
        used.append("sleep_hours")

        if hours < 5:
            duration = 0.88
        elif hours < 6:
            duration = 0.92
        elif hours < 7:
            duration = 0.97
        elif hours <= 9:
            duration = 1.00
        else:
            duration = 0.98

        quality = agg.sleep.quality
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

        awakenings = agg.sleep.awakenings
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

        mod = duration * quality_factor * awakenings_factor
        return round(mod, 3), used, missing

    async def _calculate_energy_modifier(self, user_id: int, agg: DailyAggregate, prev: Optional[List[DailyAggregate]]) -> Tuple[float, List[str], List[str]]:
        avg_energy = agg.derived.avg_energy
        used, missing = [], []
        if avg_energy is None:
            missing.append("energy")
            return 1.0, used, missing
        used.append("energy")

        if avg_energy >= 8:
            mod = 1.05
        elif avg_energy >= 6:
            mod = 1.00
        elif avg_energy >= 4:
            mod = 0.97
        else:
            mod = 0.90

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

        if stress <= 3:
            mod = 1.00
        elif stress <= 6:
            mod = 0.98
        elif stress <= 8:
            mod = 0.95
        else:
            mod = 0.93

        return round(mod, 3), used, missing

    def _calculate_activity_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        steps = agg.activity.steps
        used, missing = [], []
        if steps is None:
            missing.append("steps")
            return 1.0, used, missing
        used.append("steps")

        if steps < 3000:
            mod = 0.95
        elif steps < 5000:
            mod = 0.97
        elif steps < 8000:
            mod = 0.99
        elif steps < 10000:
            mod = 1.00
        elif steps < 15000:
            mod = 1.02
        else:
            mod = 1.05

        return round(mod, 3), used, missing

    def _calculate_window_modifier(self, agg: DailyAggregate) -> Tuple[float, List[str], List[str]]:
        window = agg.derived.eating_window_hours
        used, missing = [], []
        if window is None:
            missing.append("eating_window")
            return 1.0, used, missing
        used.append("eating_window")

        if window < 8:
            mod = 1.05
        elif window < 10:
            mod = 1.03
        elif window < 12:
            mod = 1.00
        elif window < 14:
            mod = 0.97
        else:
            mod = 0.93

        return round(mod, 3), used, missing

    async def _calculate_workout_bonus(self, agg: DailyAggregate, user_id: int) -> Tuple[int, List[str], List[str]]:
        wtype = agg.workout.type
        duration = agg.workout.duration_min
        used, missing = [], []
        if not wtype or wtype == "none" or not duration:
            missing.append("workout")
            return 0, used, missing
        used.append("workout_type")
        used.append("workout_duration")

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

# ==============================================================================
# ГЕНЕРАТОР ГРАФИКОВ (из charts.py)
# ==============================================================================
class ChartGenerator:
    @staticmethod
    def generate_weight_trend_chart(aggregates: List[DailyAggregate], target_weight: Optional[float] = None) -> bytes:
        dates = [a.date for a in aggregates if a.measurements.weight_kg]
        weights = [a.measurements.weight_kg for a in aggregates if a.measurements.weight_kg]
        if len(weights) < 3:
            return b""
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        ax.plot(dates, weights, marker='o', linestyle='-', color='#FF6B6B', label='Фактический вес', alpha=0.7)
        if target_weight:
            ax.axhline(y=target_weight, color='#2ECC71', linestyle=':', linewidth=2, label=f'Цель: {target_weight} кг')
        ax.set_title("Динамика веса", fontsize=14, fontweight='bold')
        ax.set_ylabel("Вес (кг)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        return buf.getvalue()

    @staticmethod
    def generate_sleep_energy_chart(aggregates: List[DailyAggregate]) -> bytes:
        dates = [a.date for a in aggregates if a.sleep.hours is not None]
        sleep_hours = [a.sleep.hours for a in aggregates if a.sleep.hours is not None]
        energy = [a.derived.avg_energy for a in aggregates if a.derived.avg_energy is not None]
        if len(dates) < 3:
            return b""
        fig, ax1 = plt.subplots(figsize=(8, 4), dpi=100)
        color1 = '#3498DB'
        ax1.set_xlabel('Дата')
        ax1.set_ylabel('Сон (часы)', color=color1)
        ax1.plot(dates, sleep_hours, marker='o', color=color1, label='Сон')
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.axhspan(7, 9, color='#2ECC71', alpha=0.2)
        ax2 = ax1.twinx()
        color2 = '#F39C12'
        ax2.set_ylabel('Энергия (1-10)', color=color2)
        ax2.plot(dates, energy, marker='^', color=color2, label='Энергия')
        ax2.tick_params(axis='y', labelcolor=color2)
        plt.title("Сон vs Энергия", fontsize=14, fontweight='bold')
        fig.tight_layout()
        plt.xticks(rotation=45)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        return buf.getvalue()