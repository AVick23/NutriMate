"""
Базовые модели данных, константы и утилиты для аналитики.
"""
import logging
import math
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ================================================================
# КОНСТАНТЫ
# ================================================================

# Пороги для корреляционного анализа
MIN_CORRELATION = 0.3
MIN_SAMPLE_SIZE = 14
P_VALUE_THRESHOLD = 0.05
LAGS = [0, 1, 3, 5, 7]

# Человекочитаемые названия метрик
METRIC_NAMES = {
    "sleep_hours": "продолжительность сна",
    "sleep_quality": "качество сна",
    "stress_level": "уровень стресса",
    "energy_morning": "утренняя энергия",
    "energy_evening": "вечерняя энергия",
    "steps": "количество шагов",
    "total_kcal": "потребление калорий",
    "total_protein_g": "потребление белка",
    "water_ml": "потребление воды",
    "weight_kg": "вес",
    "waist_cm": "объём талии",
    "hips_cm": "объём бёдер",
}

# Названия состояний
STATE_NAMES = {
    "metabolic_adaptation": "Метаболическая адаптация",
    "body_recomposition": "Рекомпозиция тела ✨",
    "overtraining": "Перетренированность",
    "stress_plateau": "Стрессовое плато",
    "insulin_resistance": "Инсулинорезистентность",
}


# ================================================================
# МОДЕЛИ ДАННЫХ
# ================================================================

@dataclass
class NutritionData:
    """Данные о питании за день."""
    total_kcal: int = 0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0
    meal_count: int = 0
    first_meal_at: Optional[datetime] = None
    last_meal_at: Optional[datetime] = None


@dataclass
class SleepData:
    """Данные о сне."""
    hours: Optional[float] = None
    quality: Optional[int] = None  # 1-5
    awakenings: Optional[int] = None  # 0, 1, 2, 3+


@dataclass
class EnergyData:
    """Данные об энергии."""
    morning: Optional[int] = None  # 1-10
    evening: Optional[int] = None  # 1-10
    
    @property
    def avg(self) -> Optional[float]:
        """Средняя энергия за день."""
        if self.morning is not None and self.evening is not None:
            return (self.morning + self.evening) / 2
        return None


@dataclass
class ActivityData:
    """Данные об активности."""
    steps: Optional[int] = None
    hours_on_feet: Optional[float] = None


@dataclass
class WorkoutData:
    """Данные о тренировке."""
    type: Optional[str] = None  # strength, cardio, yoga, walk, swim
    duration_min: Optional[int] = None
    intensity: Optional[int] = None  # RPE 1-10


@dataclass
class MeasurementsData:
    """Замеры тела."""
    weight_kg: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    arm_cm: Optional[float] = None
    thigh_cm: Optional[float] = None


@dataclass
class DerivedMetrics:
    """Рассчитанные метрики."""
    eating_window_hours: Optional[float] = None
    last_meal_hour: Optional[int] = None
    protein_per_kg: Optional[float] = None
    water_per_kg: Optional[float] = None
    avg_energy: Optional[float] = None


@dataclass
class DailyAggregate:
    """Полные агрегированные данные за день."""
    date: date
    user_id: int
    nutrition: NutritionData = field(default_factory=NutritionData)
    water_ml: int = 0
    measurements: MeasurementsData = field(default_factory=MeasurementsData)
    sleep: SleepData = field(default_factory=SleepData)
    energy: EnergyData = field(default_factory=EnergyData)
    stress: Optional[int] = None
    activity: ActivityData = field(default_factory=ActivityData)
    workout: WorkoutData = field(default_factory=WorkoutData)
    derived: DerivedMetrics = field(default_factory=DerivedMetrics)
    
    # Модификаторы TDEE (заполняются ModifierEngine)
    base_tdee: Optional[int] = None
    sleep_modifier: float = 1.0
    energy_modifier: float = 1.0
    stress_modifier: float = 1.0
    activity_modifier: float = 1.0
    window_modifier: float = 1.0
    workout_bonus: int = 0
    adjusted_tdee: Optional[int] = None
    confidence_score: int = 100


@dataclass
class Pattern:
    """Обнаруженный паттерн."""
    pattern_type: str = "correlation"
    metric_x: str = ""
    metric_y: str = ""
    correlation_r: Optional[float] = None
    p_value: Optional[float] = None
    lag_days: int = 0
    sample_size: int = 0
    effect_text: str = ""
    effect_direction: str = "neutral"  # positive, negative, neutral


@dataclass
class Insight:
    """Генерируемый инсайт."""
    title: str
    message: str
    emoji: str
    priority: int  # 1-5, где 5 — самый важный
    category: str  # sleep, energy, stress, activity, nutrition, workout


@dataclass
class StateDetection:
    """Обнаруженное состояние."""
    state_type: str
    detected: bool
    severity: str  # low, medium, high, positive
    indicators: List[str]
    recommendation: str
    emoji: str


# ================================================================
# УТИЛИТЫ
# ================================================================

def safe_average(values: List[Any]) -> Optional[float]:
    """Безопасное вычисление среднего, игнорируя None."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Рассчитывает коэффициент корреляции Пирсона и p-value.
    
    Args:
        x: список значений первой переменной
        y: список значений второй переменной
        
    Returns:
        (r, p_value) — коэффициент корреляции и статистическая значимость
    """
    n = len(x)
    if n < 3:
        return 0.0, 1.0

    # Расчёт средних
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Расчёт ковариации и стандартных отклонений
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denom_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    denom_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

    if denom_x == 0 or denom_y == 0:
        return 0.0, 1.0

    r = numerator / (denom_x * denom_y)

    # Расчёт p-value через t-распределение
    if abs(r) < 1e-10:
        return r, 1.0

    t_stat = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else 100
    df = n - 2

    # Улучшенная оценка p-value
    if df > 30:
        # Для больших выборок — нормальное приближение
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
    else:
        # Для малых выборок — табличные пороги
        abs_t = abs(t_stat)
        if abs_t > 3.5:
            p_value = 0.001
        elif abs_t > 2.8:
            p_value = 0.01
        elif abs_t > 2.0:
            p_value = 0.05
        elif abs_t > 1.7:
            p_value = 0.1
        else:
            p_value = 0.5

    return r, p_value


def get_lagged_pairs(
    data: Dict[str, List[Optional[float]]],
    metric_x: str,
    metric_y: str,
    lag: int
) -> Tuple[List[float], List[float]]:
    """
    Возвращает пары значений (x_t, y_{t+lag}) для корреляционного анализа.
    
    Args:
        data: словарь с временными рядами метрик
        metric_x: название первой метрики
        metric_y: название второй метрики
        lag: задержка в днях
        
    Returns:
        (x_values, y_values) — пары значений для расчёта корреляции
    """
    x_vals = data.get(metric_x, [])
    y_vals = data.get(metric_y, [])

    if not x_vals or not y_vals:
        return [], []

    if lag == 0:
        # Синхронная корреляция
        pairs = [(x, y) for x, y in zip(x_vals, y_vals)
                 if x is not None and y is not None]
    else:
        # Лаговая корреляция: x в день t, y в день t+lag
        pairs = []
        for i in range(len(x_vals) - lag):
            x = x_vals[i]
            y = y_vals[i + lag]
            if x is not None and y is not None:
                pairs.append((x, y))

    if not pairs:
        return [], []

    return [p[0] for p in pairs], [p[1] for p in pairs]


def aggregates_to_dict(
    aggregates: List[DailyAggregate]
) -> Dict[str, List[Optional[float]]]:
    """Преобразует список DailyAggregate в словарь временных рядов."""
    metrics = [
        "sleep_hours", "sleep_quality", "stress_level",
        "energy_morning", "energy_evening", "steps",
        "total_kcal", "total_protein_g", "water_ml",
        "weight_kg", "waist_cm"
    ]
    result = {metric: [] for metric in metrics}
    result["date"] = []

    for agg in aggregates:
        result["date"].append(agg.date)
        result["sleep_hours"].append(agg.sleep.hours)
        result["sleep_quality"].append(agg.sleep.quality)
        result["stress_level"].append(agg.stress)
        result["energy_morning"].append(agg.energy.morning)
        result["energy_evening"].append(agg.energy.evening)
        result["steps"].append(agg.activity.steps)
        result["total_kcal"].append(agg.nutrition.total_kcal)
        result["total_protein_g"].append(agg.nutrition.total_protein_g)
        result["water_ml"].append(agg.water_ml)
        result["weight_kg"].append(agg.measurements.weight_kg)
        result["waist_cm"].append(agg.measurements.waist_cm)

    return result


def generate_effect_text(
    metric_x: str, metric_y: str, r: float, lag: int
) -> str:
    """Генерирует человекочитаемое описание паттерна."""
    x_name = METRIC_NAMES.get(metric_x, metric_x)
    y_name = METRIC_NAMES.get(metric_y, metric_y)
    direction = "увеличивает" if r > 0 else "уменьшает"
    strength = ("сильно" if abs(r) > 0.7
                else "умеренно" if abs(r) > 0.5
                else "слабо")

    if lag == 0:
        return f"{x_name} {direction} {y_name} (корреляция {strength})"
    elif lag == 1:
        return f"{x_name} сегодня {direction} {y_name} завтра"
    else:
        return f"{x_name} влияет на {y_name} через {lag} дня"