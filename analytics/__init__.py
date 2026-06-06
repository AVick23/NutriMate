"""
Модуль аналитики и умной системы метрик.
"""
from .engine import DailyAggregator, ModifierEngine
from .intelligence import PatternDetector, StateDetector, InsightGenerator
from .reports import WeeklyReportGenerator
from .core import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics,
    Pattern, Insight, StateDetection
)

__all__ = [
    "DailyAggregator", "ModifierEngine",
    "PatternDetector", "StateDetector", "InsightGenerator",
    "WeeklyReportGenerator",
    "DailyAggregate", "NutritionData", "SleepData", "EnergyData",
    "ActivityData", "WorkoutData", "MeasurementsData", "DerivedMetrics",
    "Pattern", "Insight", "StateDetection",
]