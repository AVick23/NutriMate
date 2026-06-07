"""
Модуль аналитики и умной системы метрик NutriMate.
"""
from .engine import DailyAggregator, ModifierEngine, DailyMetricsRepository, ChartGenerator
from .intelligence import PatternDetector, StateDetector, InsightGenerator, PatternsRepository, WeeklyReportGenerator
from .core import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics,
    Pattern, Insight, StateDetection,
    safe_average, pearson_correlation, get_lagged_pairs, aggregates_to_dict, generate_effect_text,
    format_metrics_summary, format_insights, format_insights_compact, format_patterns,
    format_states, format_macro_balance, format_forecast, format_best_day, format_tdee_modifiers,
    state_name_ru, split_long_message
)

__all__ = [
    # Engine
    "DailyAggregator", "ModifierEngine", "DailyMetricsRepository", "ChartGenerator",
    # Intelligence
    "PatternDetector", "StateDetector", "InsightGenerator", "PatternsRepository", "WeeklyReportGenerator",
    # Core models
    "DailyAggregate", "NutritionData", "SleepData", "EnergyData",
    "ActivityData", "WorkoutData", "MeasurementsData", "DerivedMetrics",
    "Pattern", "Insight", "StateDetection",
    # Core utils
    "safe_average", "pearson_correlation", "get_lagged_pairs", "aggregates_to_dict", "generate_effect_text",
    # Formatting
    "format_metrics_summary", "format_insights", "format_insights_compact", "format_patterns",
    "format_states", "format_macro_balance", "format_forecast", "format_best_day", "format_tdee_modifiers",
    "state_name_ru", "split_long_message"
]