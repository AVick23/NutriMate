"""
Модуль аналитики и умной системы метрик NutriMate.
"""
from .engine import DailyAggregator, ModifierEngine, DailyMetricsRepository
from .intelligence import PatternDetector, StateDetector, InsightGenerator, PatternsRepository
from .reports import WeeklyReportGenerator
from .core import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics,
    Pattern, Insight, StateDetection,
    calculate_trend_slope, calculate_z_score, spearman_correlation, get_progress_bar
)

__all__ = [
    "DailyAggregator", "ModifierEngine", "DailyMetricsRepository",
    "PatternDetector", "StateDetector", "InsightGenerator", "PatternsRepository",
    "WeeklyReportGenerator",
    "DailyAggregate", "NutritionData", "SleepData", "EnergyData",
    "ActivityData", "WorkoutData", "MeasurementsData", "DerivedMetrics",
    "Pattern", "Insight", "StateDetection",
    "calculate_trend_slope", "calculate_z_score", "spearman_correlation", "get_progress_bar"
]