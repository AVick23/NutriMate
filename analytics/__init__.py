"""
Модуль аналитики и умной системы метрик.

Содержит:
- DailyAggregator — сбор и агрегация данных за день
- ModifierEngine — расчёт модификаторов TDEE (сон, стресс, активность и т.д.)
- InsightGenerator — генерация текстовых инсайтов
- PatternDetector — обнаружение корреляций между метриками
- StateDetector — детекция состояний (адаптация, рекомпозиция и т.д.)
- WeeklyReportGenerator — формирование недельных отчётов
"""
from analytics.aggregator import DailyAggregator
from analytics.modifier_engine import ModifierEngine
from analytics.insight_generator import InsightGenerator
from analytics.pattern_detector import PatternDetector
from analytics.state_detector import StateDetector
from analytics.weekly_report import WeeklyReportGenerator

__all__ = [
    "DailyAggregator",
    "ModifierEngine",
    "InsightGenerator",
    "PatternDetector",
    "StateDetector",
    "WeeklyReportGenerator",
]