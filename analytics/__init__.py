"""
Модуль аналитики и умной системы метрик NutriMate.

Содержит:
- DailyAggregator — сбор и агрегация данных за день
- ModifierEngine — расчёт модификаторов TDEE (сон, стресс, активность и т.д.)
- InsightGenerator — генерация текстовых инсайтов
- PatternDetector — обнаружение корреляций между метриками
- StateDetector — детекция состояний (адаптация, рекомпозиция и т.д.)
- WeeklyReportGenerator — формирование недельных отчётов
"""

from .engine import DailyAggregator, ModifierEngine, DailyMetricsRepository
from .intelligence import (
    PatternDetector, StateDetector, InsightGenerator,
    PatternsRepository
)
from .reports import WeeklyReportGenerator
from .core import (
    DailyAggregate, NutritionData, SleepData, EnergyData,
    ActivityData, WorkoutData, MeasurementsData, DerivedMetrics,
    Pattern, Insight, StateDetection
)

__all__ = [
    # Классы движка
    "DailyAggregator",
    "ModifierEngine",
    "DailyMetricsRepository",
    
    # Классы аналитики
    "PatternDetector",
    "StateDetector",
    "InsightGenerator",
    "PatternsRepository",
    "WeeklyReportGenerator",
    
    # Модели данных
    "DailyAggregate",
    "NutritionData",
    "SleepData",
    "EnergyData",
    "ActivityData",
    "WorkoutData",
    "MeasurementsData",
    "DerivedMetrics",
    "Pattern",
    "Insight",
    "StateDetection",
]