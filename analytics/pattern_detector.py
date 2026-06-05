"""
Детектор паттернов и корреляций между метриками.
"""
import logging
import math
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

from db import Database, PatternsRepository
from analytics.models import DailyAggregate, Pattern

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Обнаруживает корреляции между метриками с разными лагами.
    
    Алгоритм:
    1. Собирает данные за последние N дней
    2. Рассчитывает корреляцию Пирсона для всех пар метрик
    3. Сохраняет только статистически значимые паттерны (p < 0.05, |r| > 0.3)
    """
    
    # Метрики для анализа
    METRICS = [
        "sleep_hours",
        "sleep_quality",
        "stress_level",
        "energy_morning",
        "energy_evening",
        "steps",
        "total_kcal",
        "total_protein_g",
        "water_ml",
        "weight_kg",
        "waist_cm",
    ]
    
    # Лаги для анализа (дни)
    LAGS = [0, 1, 3, 5, 7]
    
    # Пороги
    MIN_CORRELATION = 0.3
    MIN_SAMPLE_SIZE = 14
    P_VALUE_THRESHOLD = 0.05
    
    def __init__(self, db: Database):
        self.db = db
        self.patterns_repo = PatternsRepository(db)

    async def detect_patterns(
        self,
        user_id: int,
        aggregates: List[DailyAggregate]
    ) -> List[Pattern]:
        """
        Обнаруживает паттерны на основе агрегированных данных.
        
        Args:
            user_id: ID пользователя
            aggregates: Список DailyAggregate за последние N дней
            
        Returns:
            Список обнаруженных паттернов
        """
        if len(aggregates) < self.MIN_SAMPLE_SIZE:
            logger.info(f"Not enough data for user {user_id}: {len(aggregates)} days")
            return []
        
        # Преобразуем агрегаты в словарь для удобного доступа
        data = self._aggregates_to_dict(aggregates)
        
        detected_patterns = []
        
        # Анализируем корреляции
        for lag in self.LAGS:
            patterns = await self._analyze_correlations(user_id, data, lag)
            detected_patterns.extend(patterns)
        
        # Сохраняем новые паттерны в БД
        for pattern in detected_patterns:
            await self.patterns_repo.save_pattern(user_id, {
                "pattern_type": pattern.pattern_type,
                "metric_x": pattern.metric_x,
                "metric_y": pattern.metric_y,
                "correlation_r": pattern.correlation_r,
                "p_value": pattern.p_value,
                "lag_days": pattern.lag_days,
                "sample_size": pattern.sample_size,
                "effect_text": pattern.effect_text,
                "effect_direction": pattern.effect_direction,
            })
        
        return detected_patterns

    def _aggregates_to_dict(
        self, aggregates: List[DailyAggregate]
    ) -> Dict[str, List[Optional[float]]]:
        """
        Преобразует список агрегатов в словарь {метрика: [значения]}.
        """
        result = {metric: [] for metric in self.METRICS}
        result["date"] = []
        
        for agg in aggregates:
            result["date"].append(agg.date)
            
            # Сон
            result["sleep_hours"].append(agg.sleep.hours)
            result["sleep_quality"].append(agg.sleep.quality)
            
            # Стресс
            result["stress_level"].append(agg.stress)
            
            # Энергия
            result["energy_morning"].append(agg.energy.morning)
            result["energy_evening"].append(agg.energy.evening)
            
            # Активность
            result["steps"].append(agg.activity.steps)
            
            # Питание
            result["total_kcal"].append(agg.nutrition.total_kcal)
            result["total_protein_g"].append(agg.nutrition.total_protein_g)
            
            # Вода
            result["water_ml"].append(agg.water_ml)
            
            # Замеры
            result["weight_kg"].append(agg.measurements.weight_kg)
            result["waist_cm"].append(agg.measurements.waist_cm)
        
        return result

    async def _analyze_correlations(
        self,
        user_id: int,
        data: Dict[str, List[Optional[float]]],
        lag: int
    ) -> List[Pattern]:
        """
        Анализирует корреляции между метриками с заданным лагом.
        """
        patterns = []
        
        for metric_x in self.METRICS:
            for metric_y in self.METRICS:
                if metric_x == metric_y:
                    continue
                
                # Получаем пары значений с учётом лага
                x_vals, y_vals = self._get_lagged_pairs(data, metric_x, metric_y, lag)
                
                if len(x_vals) < self.MIN_SAMPLE_SIZE:
                    continue
                
                # Рассчитываем корреляцию
                r, p_value = self._pearson_correlation(x_vals, y_vals)
                
                if abs(r) >= self.MIN_CORRELATION and p_value < self.P_VALUE_THRESHOLD:
                    pattern = Pattern(
                        pattern_type="correlation",
                        metric_x=metric_x,
                        metric_y=metric_y,
                        correlation_r=r,
                        p_value=p_value,
                        lag_days=lag,
                        sample_size=len(x_vals),
                        effect_direction="positive" if r > 0 else "negative",
                        effect_text=self._generate_effect_text(metric_x, metric_y, r, lag),
                    )
                    patterns.append(pattern)
        
        return patterns

    def _get_lagged_pairs(
        self,
        data: Dict[str, List[Optional[float]]],
        metric_x: str,
        metric_y: str,
        lag: int
    ) -> Tuple[List[float], List[float]]:
        """
        Возвращает пары значений (x_t, y_{t+lag}) для корреляционного анализа.
        """
        x_vals = data[metric_x]
        y_vals = data[metric_y]
        
        if lag == 0:
            # Синхронная корреляция
            pairs = [(x, y) for x, y in zip(x_vals, y_vals) if x is not None and y is not None]
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

    def _pearson_correlation(
        self, x: List[float], y: List[float]
    ) -> Tuple[float, float]:
        """
        Рассчитывает коэффициент корреляции Пирсона и p-value.
        """
        n = len(x)
        if n < 3:
            return 0.0, 1.0
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
        denominator_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))
        
        if denominator_x == 0 or denominator_y == 0:
            return 0.0, 1.0
        
        r = numerator / (denominator_x * denominator_y)
        
        # Приблизительный p-value (t-тест)
        if n > 2:
            t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else 100
            # Упрощённая оценка p-value
            p_value = 0.05 if abs(t) > 2 else 0.1 if abs(t) > 1.5 else 0.5
        else:
            p_value = 1.0
        
        return r, p_value

    def _generate_effect_text(
        self, metric_x: str, metric_y: str, r: float, lag: int
    ) -> str:
        """
        Генерирует человекочитаемое описание паттерна.
        """
        # Человекочитаемые названия метрик
        names = {
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
        }
        
        x_name = names.get(metric_x, metric_x)
        y_name = names.get(metric_y, metric_y)
        
        direction = "увеличивает" if r > 0 else "уменьшает"
        strength = "сильно" if abs(r) > 0.7 else "умеренно" if abs(r) > 0.5 else "слабо"
        
        if lag == 0:
            return f"{x_name} {direction} {y_name} (корреляция {strength})"
        elif lag == 1:
            return f"{x_name} сегодня {direction} {y_name} завтра (предсказание)"
        else:
            return f"{x_name} влияет на {y_name} через {lag} дней"