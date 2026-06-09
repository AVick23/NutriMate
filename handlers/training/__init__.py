"""
Модуль тренировок с собственным весом.
🎯 Научно обоснованная калистеника с Apple-like UX.
"""
from handlers.training.handlers import get_training_handler
from handlers.training.exercises import (
    EXERCISES, READY_WORKOUTS, GENERAL_TIPS,
    get_exercises_by_group, get_exercise_by_id,
    get_workout_by_id, get_tip_by_id,
)

__all__ = [
    "get_training_handler",
    "EXERCISES",
    "READY_WORKOUTS",
    "GENERAL_TIPS",
    "get_exercises_by_group",
    "get_exercise_by_id",
    "get_workout_by_id",
    "get_tip_by_id",
]