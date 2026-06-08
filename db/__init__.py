"""
Модуль работы с базой данных.
"""
from db.database import Database
from db.repositories import (
    UserRepository,
    MealRepository,
    FavoritesRepository,
    WaterRepository,
    HistoryRepository,
    DailyStatsRepository,
    RegistrationStateRepository,
    DailyMetricsRepository,
    DailyAggregatesRepository,
    PatternsRepository,
    ModifierHistoryRepository,
    AnalyticsSettingsRepository,
    MeasurementsRepository,  # 🎯 Добавлено
)

__all__ = [
    "Database",
    "UserRepository",
    "MealRepository",
    "FavoritesRepository",
    "WaterRepository",
    "HistoryRepository",
    "DailyStatsRepository",
    "RegistrationStateRepository",
    "DailyMetricsRepository",
    "DailyAggregatesRepository",
    "PatternsRepository",
    "ModifierHistoryRepository",
    "AnalyticsSettingsRepository",
    "MeasurementsRepository",  # 🎯 Добавлено
]