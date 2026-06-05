"""
Pydantic-схемы для данных аналитики.
"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


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
    awakenings: Optional[int] = None  # 0,1,2,3+


@dataclass
class EnergyData:
    """Данные об энергии."""
    morning: Optional[int] = None  # 1-10
    evening: Optional[int] = None  # 1-10
    
    @property
    def avg(self) -> Optional[float]:
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
    
    # Модификаторы TDEE
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
    id: Optional[int] = None
    user_id: Optional[int] = None
    pattern_type: str = "correlation"  # correlation, conditional
    metric_x: str = ""
    metric_y: str = ""
    condition_metric: Optional[str] = None
    condition_operator: Optional[str] = None
    condition_value: Optional[float] = None
    correlation_r: Optional[float] = None
    p_value: Optional[float] = None
    lag_days: int = 0
    sample_size: int = 0
    effect_text: str = ""
    effect_direction: str = "neutral"  # positive, negative, neutral
    is_active: bool = True
    first_detected_at: Optional[datetime] = None
    last_confirmed_at: Optional[datetime] = None
    confirmation_count: int = 1


@dataclass
class Insight:
    """Генерируемый инсайт."""
    title: str
    message: str
    emoji: str
    priority: int  # 1-5, где 5 — самый важный
    category: str  # sleep, energy, stress, activity, nutrition, etc.
    action_url: Optional[str] = None


@dataclass
class StateDetection:
    """Обнаруженное состояние."""
    state_type: str  # metabolic_adaptation, body_recomposition, overtraining, stress_plateau, insulin_resistance
    detected: bool
    severity: str  # low, medium, high
    indicators: List[str]
    recommendation: str
    emoji: str