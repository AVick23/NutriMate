"""
Базовые модели данных, константы и утилиты для аналитики.
"""
import logging
import math
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ==============================================================================
# КОНСТАНТЫ
# ==============================================================================
MIN_CORRELATION = 0.4  # Порог для значимой корреляции
MIN_SAMPLE_SIZE = 10   # Минимум дней для анализа
P_VALUE_THRESHOLD = 0.05
LAGS = [0, 1, 3, 7]    # Лаги в днях для поиска отложенных эффектов

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

STATE_NAMES = {
    "metabolic_adaptation": "Метаболическая адаптация",
    "body_recomposition": "Рекомпозиция тела ✨",
    "overtraining": "Перетренированность",
    "stress_plateau": "Стрессовое плато",
    "insulin_resistance": "Инсулинорезистентность",
}

# ==============================================================================
# МОДЕЛИ ДАННЫХ
# ==============================================================================
@dataclass
class NutritionData:
    total_kcal: int = 0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0
    meal_count: int = 0
    first_meal_at: Optional[datetime] = None
    last_meal_at: Optional[datetime] = None

@dataclass
class SleepData:
    hours: Optional[float] = None
    quality: Optional[int] = None
    awakenings: Optional[int] = None

@dataclass
class EnergyData:
    morning: Optional[int] = None
    evening: Optional[int] = None
    @property
    def avg(self) -> Optional[float]:
        if self.morning is not None and self.evening is not None:
            return (self.morning + self.evening) / 2.0
        return self.morning or self.evening

@dataclass
class ActivityData:
    steps: Optional[int] = None
    hours_on_feet: Optional[float] = None

@dataclass
class WorkoutData:
    type: Optional[str] = None
    duration_min: Optional[int] = None
    intensity: Optional[int] = None

@dataclass
class MeasurementsData:
    weight_kg: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    arm_cm: Optional[float] = None
    thigh_cm: Optional[float] = None

@dataclass
class DerivedMetrics:
    eating_window_hours: Optional[float] = None
    last_meal_hour: Optional[int] = None
    protein_per_kg: Optional[float] = None
    water_per_kg: Optional[float] = None
    avg_energy: Optional[float] = None

@dataclass
class DailyAggregate:
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
    pattern_type: str = "correlation"
    metric_x: str = ""
    metric_y: str = ""
    correlation_r: Optional[float] = None
    p_value: Optional[float] = None
    lag_days: int = 0
    sample_size: int = 0
    effect_text: str = ""
    effect_direction: str = "neutral"
    confidence_score: int = 0  # 0-100, на основе размера выборки и силы связи

@dataclass
class Insight:
    title: str
    message: str
    emoji: str
    priority: int
    category: str

@dataclass
class StateDetection:
    state_type: str
    detected: bool
    severity: str
    risk_score: int = 0  # Балльная оценка (чем выше, тем увереннее детекция)
    indicators: List[str] = field(default_factory=list)
    recommendation: str = ""
    emoji: str = ""

# ==============================================================================
# УТИЛИТЫ
# ==============================================================================
def safe_average(values: List[Any]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    return sum(filtered) / len(filtered) if filtered else None

def calculate_trend_slope(values: List[float]) -> float:
    """Рассчитывает наклон тренда (линейная регрессия). Возвращает изменение в день."""
    n = len(values)
    if n < 3:
        return 0.0
    x = list(range(n))
    mean_x = sum(x) / n
    mean_y = sum(values) / n
    
    num = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))
    
    return num / den if den != 0 else 0.0

def calculate_z_score(value: float, mean: float, std_dev: float) -> float:
    """Оценка того, насколько значение выбивается из нормы (для детекции аномалий)."""
    if std_dev == 0:
        return 0.0
    return (value - mean) / std_dev

def spearman_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Ранговая корреляция Спирмена. Находит монотонные (в т.ч. нелинейные) связи."""
    n = len(x)
    if n < MIN_SAMPLE_SIZE:
        return 0.0, 1.0

    def rank(data):
        sorted_idx = sorted(range(len(data)), key=lambda k: data[k])
        ranks = [0] * len(data)
        for rank_val, original_idx in enumerate(sorted_idx, 1):
            ranks[original_idx] = rank_val
        return ranks

    rx, ry = rank(x), rank(y)
    d_squared_sum = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    rho = 1 - (6 * d_squared_sum) / (n * (n**2 - 1))
    
    if n > 10:
        t_stat = rho * math.sqrt((n - 2) / (1 - rho**2 + 1e-10))
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
    else:
        p_value = 0.1 if abs(rho) > 0.6 else 0.5
        
    return round(rho, 3), round(p_value, 3)

def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    mean_x, mean_y = sum(x) / n, sum(y) / n
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denom_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    denom_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))
    if denom_x == 0 or denom_y == 0:
        return 0.0, 1.0
    r = num / (denom_x * denom_y)
    if abs(r) < 1e-10:
        return r, 1.0
    t_stat = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else 100
    df = n - 2
    if df > 30:
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
    else:
        abs_t = abs(t_stat)
        p_value = 0.001 if abs_t > 3.5 else 0.01 if abs_t > 2.8 else 0.05 if abs_t > 2.0 else 0.1 if abs_t > 1.7 else 0.5
    return r, p_value

def get_lagged_pairs(data: Dict[str, List[Optional[float]]], metric_x: str, metric_y: str, lag: int) -> Tuple[List[float], List[float]]:
    x_vals, y_vals = data.get(metric_x, []), data.get(metric_y, [])
    if not x_vals or not y_vals:
        return [], []
    if lag == 0:
        pairs = [(x, y) for x, y in zip(x_vals, y_vals) if x is not None and y is not None]
    else:
        pairs = [(x_vals[i], y_vals[i + lag]) for i in range(len(x_vals) - lag) if x_vals[i] is not None and y_vals[i + lag] is not None]
    return [p[0] for p in pairs], [p[1] for p in pairs]

def aggregates_to_dict(aggregates: List[DailyAggregate]) -> Dict[str, List[Optional[float]]]:
    metrics = ["sleep_hours", "sleep_quality", "stress_level", "energy_morning", "energy_evening", "steps", "total_kcal", "total_protein_g", "water_ml", "weight_kg", "waist_cm"]
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

def generate_effect_text(metric_x: str, metric_y: str, r: float, lag: int) -> str:
    x_name = METRIC_NAMES.get(metric_x, metric_x)
    y_name = METRIC_NAMES.get(metric_y, metric_y)
    direction = "увеличивает" if r > 0 else "уменьшает"
    strength = "сильно" if abs(r) > 0.7 else "умеренно" if abs(r) > 0.5 else "слабо"
    if lag == 0:
        return f"{x_name} {direction} {y_name} (корреляция {strength})"
    elif lag == 1:
        return f"{x_name} сегодня {direction} {y_name} завтра"
    else:
        return f"{x_name} влияет на {y_name} через {lag} дня"

def get_progress_bar(current: float, goal: float, width: int = 10) -> str:
    if goal <= 0: return ""
    pct = min(1.0, max(0.0, current / goal))
    filled = int(width * pct)
    return f"[{'█' * filled}{'░' * (width - filled)}] {int(pct * 100)}%"