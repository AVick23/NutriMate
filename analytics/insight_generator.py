"""
Генератор текстовых инсайтов на основе метрик.
"""
import logging
from datetime import date
from typing import List, Optional

from analytics.models import DailyAggregate, Insight

logger = logging.getLogger(__name__)


class InsightGenerator:
    """Генерирует персональные инсайты на основе данных пользователя."""

    def generate_insights(self, aggregated: DailyAggregate) -> List[Insight]:
        """
        Генерирует список инсайтов на основе агрегированных данных за день.
        """
        insights = []

        # 1. Инсайты о сне
        sleep_insights = self._generate_sleep_insights(aggregated)
        insights.extend(sleep_insights)

        # 2. Инсайты об энергии
        energy_insights = self._generate_energy_insights(aggregated)
        insights.extend(energy_insights)

        # 3. Инсайты о стрессе
        stress_insights = self._generate_stress_insights(aggregated)
        insights.extend(stress_insights)

        # 4. Инсайты о питании
        nutrition_insights = self._generate_nutrition_insights(aggregated)
        insights.extend(nutrition_insights)

        # 5. Инсайты об активности
        activity_insights = self._generate_activity_insights(aggregated)
        insights.extend(activity_insights)

        # 6. Инсайты о тренировках
        workout_insights = self._generate_workout_insights(aggregated)
        insights.extend(workout_insights)

        # Сортируем по приоритету
        insights.sort(key=lambda x: x.priority, reverse=True)
        
        return insights[:5]  # Возвращаем топ-5 инсайтов

    def _generate_sleep_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о сне."""
        insights = []
        
        if agg.sleep.hours is None:
            return insights

        hours = agg.sleep.hours
        
        if hours < 6:
            insights.append(Insight(
                title="Недостаток сна",
                message=f"Ты спал всего {hours}ч. Недосып снижает метаболизм на 8-12% и повышает голод на 28% через грелин.",
                emoji="😴",
                priority=5,
                category="sleep",
            ))
        elif hours < 7:
            insights.append(Insight(
                title="Лёгкий недосып",
                message=f"Ты спал {hours}ч. Даже небольшой недосып снижает чувствительность к инсулину на 20%.",
                emoji="😐",
                priority=3,
                category="sleep",
            ))
        elif hours > 9:
            insights.append(Insight(
                title="Долгий сон",
                message=f"Ты спал {hours}ч. Долгий сон может быть признаком перетренированности или нехватки энергии.",
                emoji="😴",
                priority=2,
                category="sleep",
            ))

        # Качество сна
        if agg.sleep.quality and agg.sleep.quality <= 2:
            insights.append(Insight(
                title="Плохое качество сна",
                message="Плохой сон нарушает выработку гормонов и замедляет восстановление. Попробуй тёплую ванну или медитацию перед сном.",
                emoji="😫",
                priority=4,
                category="sleep",
            ))

        # Пробуждения
        if agg.sleep.awakenings and agg.sleep.awakenings >= 2:
            insights.append(Insight(
                title="Ночные пробуждения",
                message=f"Ты просыпался {agg.sleep.awakenings} раз(а). Это повышает кортизол и снижает эффективность сна.",
                emoji="🔄",
                priority=3,
                category="sleep",
            ))

        return insights

    def _generate_energy_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты об энергии."""
        insights = []
        
        avg_energy = agg.derived.avg_energy
        
        if avg_energy is None:
            return insights

        if avg_energy <= 4:
            insights.append(Insight(
                title="Низкая энергия",
                message="Низкая энергия может быть признаком метаболической адаптации. Возможно, пора сделать диет-брейк на 5-7 дней.",
                emoji="⚡",
                priority=5,
                category="energy",
            ))
        elif avg_energy <= 6:
            insights.append(Insight(
                title="Умеренная энергия",
                message="Твоя энергия чуть ниже нормы. Убедись, что ты высыпаешься и получаешь достаточно белка.",
                emoji="😐",
                priority=2,
                category="energy",
            ))
        elif avg_energy >= 9:
            insights.append(Insight(
                title="Отличная энергия!",
                message="Высокий уровень энергии говорит о хорошем восстановлении. Отличная работа!",
                emoji="💪",
                priority=1,
                category="energy",
            ))

        return insights

    def _generate_stress_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о стрессе."""
        insights = []
        
        if agg.stress is None:
            return insights

        if agg.stress >= 8:
            insights.append(Insight(
                title="Высокий стресс",
                message="Хронический стресс повышает кортизол, который задерживает воду и увеличивает висцеральный жир. Попробуй дыхательные практики или лёгкую прогулку.",
                emoji="😰",
                priority=5,
                category="stress",
            ))
        elif agg.stress >= 6:
            insights.append(Insight(
                title="Повышенный стресс",
                message="Стресс может вызывать тягу к сладкому и снижать качество сна. Выдели 10 минут на расслабление.",
                emoji="😟",
                priority=3,
                category="stress",
            ))

        return insights

    def _generate_nutrition_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о питании."""
        insights = []
        
        # Белок
        protein_per_kg = agg.derived.protein_per_kg
        if protein_per_kg and protein_per_kg < 1.2:
            insights.append(Insight(
                title="Мало белка",
                message=f"Ты съел всего {protein_per_kg}г белка на кг веса. Для сохранения мышц нужно минимум 1.6-2.0г/кг.",
                emoji="🍗",
                priority=4,
                category="nutrition",
            ))
        
        # Окно питания
        window = agg.derived.eating_window_hours
        if window and window > 12:
            insights.append(Insight(
                title="Длинное окно питания",
                message=f"Твой приём пищи растянут на {window:.0f}ч. Узкое окно (8-10ч) улучшает чувствительность к инсулину.",
                emoji="⏰",
                priority=3,
                category="nutrition",
            ))
        elif window and window < 8 and window > 0:
            insights.append(Insight(
                title="Интервальное голодание",
                message=f"Окно питания {window:.0f}ч — отличный режим для метаболического здоровья!",
                emoji="🌟",
                priority=2,
                category="nutrition",
            ))
        
        # Время последнего приёма пищи
        last_meal_hour = agg.derived.last_meal_hour
        if last_meal_hour and last_meal_hour >= 21:
            insights.append(Insight(
                title="Поздний ужин",
                message=f"Последний приём пищи в {last_meal_hour}:00. Поздняя еда снижает окисление жиров на 10% и нарушает циркадные ритмы.",
                emoji="🌙",
                priority=3,
                category="nutrition",
            ))

        return insights

    def _generate_activity_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты об активности."""
        insights = []
        
        steps = agg.activity.steps
        
        if steps is None:
            return insights

        if steps < 5000:
            insights.append(Insight(
                title="Малая активность",
                message=f"Ты прошёл всего {steps:,} шагов. Увеличение NEAT до 8000-10000 шагов в день ускорит метаболизм.",
                emoji="👣",
                priority=4,
                category="activity",
            ))
        elif steps >= 10000:
            insights.append(Insight(
                title="Хорошая активность!",
                message=f"Отлично! {steps:,} шагов — это ~300-500 ккал дополнительного расхода.",
                emoji="🎉",
                priority=1,
                category="activity",
            ))

        return insights

    def _generate_workout_insights(self, agg: DailyAggregate) -> List[Insight]:
        """Генерирует инсайты о тренировках."""
        insights = []
        
        workout_type = agg.workout.type
        duration = agg.workout.duration_min
        
        if not workout_type or workout_type == "none":
            return insights

        if workout_type == "strength":
            insights.append(Insight(
                title="Силовая тренировка",
                message=f"Отличная силовая! Она не только сжигает калории, но и сохраняет мышцы при дефиците.",
                emoji="🏋️",
                priority=2,
                category="workout",
            ))
        elif workout_type == "cardio":
            insights.append(Insight(
                title="Кардио тренировка",
                message=f"{duration} минут кардио. Добавь силовые для лучшего сохранения мышечной массы.",
                emoji="🏃",
                priority=2,
                category="workout",
            ))

        return insights