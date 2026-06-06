"""
Модуль аналитики и умной системы метрик.

Содержит:
- DailyAggregator — сбор и агрегация данных за день
- ModifierEngine — расчёт модификаторов TDEE
- InsightGenerator — генерация текстовых инсайтов
- PatternDetector — обнаружение корреляций между метриками
- StateDetector — детекция состояний (адаптация, рекомпозиция и т.д.)
- WeeklyReportGenerator — формирование недельных отчётов
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
    # Классы
    "DailyAggregator",
    "ModifierEngine",
    "PatternDetector",
    "StateDetector",
    "InsightGenerator",
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