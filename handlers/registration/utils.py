# handlers/registration/utils.py
from enum import Enum
from typing import Optional

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"

class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"

class Goal(str, Enum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"

class Pace(str, Enum):
    SLOW = "slow"
    STEADY = "steady"
    FAST = "fast"

# Множители активности
ACTIVITY_MULTIPLIERS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

# Корректировки калорий в зависимости от цели и темпа
GOAL_ADJUSTMENTS = {
    Goal.LOSE: {
        Pace.SLOW: -0.12,
        Pace.STEADY: -0.20,
        Pace.FAST: -0.28,
    },
    Goal.MAINTAIN: 0.0,
    Goal.GAIN: {
        Pace.SLOW: 0.10,
        Pace.STEADY: 0.15,
        Pace.FAST: 0.20,
    },
}

# Названия для отображения
ACTIVITY_NAMES = {
    ActivityLevel.SEDENTARY: "Сидячая работа",
    ActivityLevel.LIGHT: "Хожу пешком / работа на ногах",
    ActivityLevel.MODERATE: "Тренируюсь 3-5 раз в неделю",
    ActivityLevel.ACTIVE: "Физический труд / спорт каждый день",
    ActivityLevel.VERY_ACTIVE: "Профессиональный спорт",
}

GOAL_NAMES = {
    Goal.LOSE: "Похудеть",
    Goal.MAINTAIN: "Сохранить вес",
    Goal.GAIN: "Набрать мышечную массу",
}

PACE_NAMES = {
    Pace.SLOW: "Мягко (-0.3 кг/нед)",
    Pace.STEADY: "Уверенно (-0.5 кг/нед)",
    Pace.FAST: "Быстро (-0.8 кг/нед)",
}

PACE_NAMES_GAIN = {
    Pace.SLOW: "Медленно (+0.3 кг/мес)",
    Pace.STEADY: "Уверенно (+0.5 кг/мес)",
    Pace.FAST: "Быстро (+0.8 кг/мес)",
}

GENDER_NAMES = {
    Gender.MALE: "Мужской",
    Gender.FEMALE: "Женский",
}


def calculate_bmr(weight_kg: float, height_cm: int, age: int, gender: Gender) -> int:
    """Формула Миффлина-Сан Жеора для расчёта базового метаболизма."""
    if gender == Gender.MALE:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    return int(bmr)


def calculate_tdee(bmr: int, activity: ActivityLevel) -> int:
    """Расчёт общего расхода энергии с учётом активности."""
    return int(bmr * ACTIVITY_MULTIPLIERS[activity])


def calculate_target_kcal(tdee: int, goal: Goal, pace: Optional[Pace] = None) -> int:
    """Расчёт целевых калорий."""
    if goal == Goal.MAINTAIN:
        return tdee

    adjustment = GOAL_ADJUSTMENTS[goal][pace]
    return int(tdee * (1 + adjustment))


def calculate_macros(target_kcal: int, weight_kg: float, goal: Goal) -> dict:
    """Расчёт БЖУ в граммах."""
    if goal == Goal.LOSE:
        protein_per_kg = 2.0
    elif goal == Goal.GAIN:
        protein_per_kg = 1.8
    else:
        protein_per_kg = 1.6

    protein_g = int(weight_kg * protein_per_kg)
    protein_kcal = protein_g * 4

    fat_kcal = target_kcal * 0.28
    fat_g = int(fat_kcal / 9)

    carbs_kcal = target_kcal - protein_kcal - fat_kcal
    carbs_g = int(carbs_kcal / 4)

    return {
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
    }


def parse_physical_data(text: str) -> Optional[tuple[int, int, float]]:
    """Парсит строку вида '30 180 85' в (возраст, рост, вес)."""
    parts = text.strip().split()
    if len(parts) != 3:
        return None

    try:
        age = int(parts[0])
        height = int(parts[1])
        weight = float(parts[2])
        return age, height, weight
    except ValueError:
        return None


# Состояния ConversationHandler
(
    STATE_AGE_HEIGHT_WEIGHT,
    STATE_ACTIVITY,
    STATE_GOAL,
    STATE_PACE,
    STATE_GENDER,
) = range(5)