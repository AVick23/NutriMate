"""
Модуль работы с базой данных.

Содержит:
- Database — ядро работы с SQLite
- Все репозитории для доступа к данным в одном файле repositories.py
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
]