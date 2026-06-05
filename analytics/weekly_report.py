"""
Генератор недельных отчётов.
"""
import logging
from datetime import date, timedelta
from typing import List, Dict, Any

from db import Database
from analytics.models import DailyAggregate
from analytics.aggregator import DailyAggregator
from analytics.pattern_detector import PatternDetector
from analytics.state_detector import StateDetector

logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """Генерирует недельные отчёты для пользователя."""
    
    def __init__(self, db: Database):
        self.db = db
        self.aggregator = DailyAggregator(db)
        self.pattern_detector = PatternDetector(db)
        self.state_detector = StateDetector()

    async def generate_report(
        self, user_id: int, profile: dict, end_date: date = None
    ) -> str:
        """
        Генерирует текстовый отчёт за последние 7 дней.
        """
        if end_date is None:
            end_date = date.today() - timedelta(days=1)  # вчера
        
        start_date = end_date - timedelta(days=7)
        
        # Собираем агрегаты за 7 дней
        aggregates = []
        for i in range(8):
            current_date = start_date + timedelta(days=i)
            if current_date <= end_date:
                agg = await self.aggregator.aggregate(user_id, current_date)
                aggregates.append(agg)
        
        if not aggregates:
            return "📊 Недостаточно данных для формирования отчёта. Заполняй метрики чаще!"
        
        # Формируем отчёт
        report = []
        
        # 1. Заголовок
        report.append(f"📊 <b>Недельный отчёт</b>\n")
        report.append(f"{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}\n")
        
        # 2. Средние значения
        report.append("━" * 30)
        report.append("\n<b>📈 Средние значения за неделю:</b>\n")
        
        avg_kcal = self._average([agg.nutrition.total_kcal for agg in aggregates])
        avg_protein = self._average([agg.nutrition.total_protein_g for agg in aggregates])
        avg_steps = self._average([agg.activity.steps for agg in aggregates if agg.activity.steps])
        avg_sleep = self._average([agg.sleep.hours for agg in aggregates if agg.sleep.hours])
        
        report.append(f"🔥 Калории: {avg_kcal:.0f} ккал/день")
        report.append(f"🍗 Белок: {avg_protein:.0f} г/день")
        report.append(f"👣 Шаги: {avg_steps:.0f} шагов/день")
        if avg_sleep:
            report.append(f"😴 Сон: {avg_sleep:.1f} ч/день")
        
        # 3. Прогресс за неделю
        report.append("\n<b>📉 Динамика за неделю:</b>\n")
        
        # Вес
        weights = [agg.measurements.weight_kg for agg in aggregates if agg.measurements.weight_kg]
        if len(weights) >= 2:
            weight_change = weights[-1] - weights[0]
            direction = "📉" if weight_change < 0 else "📈" if weight_change > 0 else "➡️"
            report.append(f"{direction} Вес: {abs(weight_change):.1f} кг")
        
        # Талия
        waists = [agg.measurements.waist_cm for agg in aggregates if agg.measurements.waist_cm]
        if len(waists) >= 2:
            waist_change = waists[-1] - waists[0]
            direction = "📉" if waist_change < 0 else "📈" if waist_change > 0 else "➡️"
            report.append(f"{direction} Талия: {abs(waist_change):.1f} см")
        
        # 4. Детекция состояний
        states = self.state_detector.detect_states(aggregates, profile)
        if states:
            report.append("\n<b>🔍 Состояния:</b>\n")
            for state in states:
                if state.detected:
                    report.append(f"{state.emoji} <b>{self._state_name(state.state_type)}</b>")
                    report.append(f"   {state.recommendation[:100]}...")
        
        # 5. Топ-3 дня
        report.append("\n<b>🏆 Лучшие дни:</b>\n")
        
        # Сортируем дни по композитному скору (энергия + шаги + сон)
        scored_days = []
        for agg in aggregates:
            score = 0
            if agg.derived.avg_energy:
                score += agg.derived.avg_energy
            if agg.activity.steps:
                score += min(agg.activity.steps / 1000, 10)
            if agg.sleep.hours:
                score += min(agg.sleep.hours, 10)
            scored_days.append((score, agg.date))
        
        scored_days.sort(reverse=True)
        for i, (score, day) in enumerate(scored_days[:3]):
            emoji = ["🥇", "🥈", "🥉"][i]
            report.append(f"{emoji} {day.strftime('%d.%m')} — {score:.0f} баллов")
        
        # 6. Рекомендации на следующую неделю
        report.append("\n<b>💡 Рекомендации на следующую неделю:</b>\n")
        
        recommendations = self._generate_recommendations(aggregates, profile)
        for rec in recommendations:
            report.append(f"• {rec}")
        
        # 7. Футер
        report.append("\n" + "━" * 30)
        report.append("\n📝 <i>Чтобы улучшить точность анализа, заполняй метрики каждый день!</i>")
        
        return "\n".join(report)

    def _average(self, values: List) -> float:
        """Возвращает среднее значение, игнорируя None."""
        filtered = [v for v in values if v is not None]
        if not filtered:
            return 0
        return sum(filtered) / len(filtered)

    def _state_name(self, state_type: str) -> str:
        """Возвращает человекочитаемое название состояния."""
        names = {
            "metabolic_adaptation": "Метаболическая адаптация",
            "body_recomposition": "Рекомпозиция тела ✨",
            "overtraining": "Перетренированность",
            "stress_plateau": "Стрессовое плато",
            "insulin_resistance": "Признаки инсулинорезистентности",
        }
        return names.get(state_type, state_type)

    def _generate_recommendations(
        self, aggregates: List[DailyAggregate], profile: dict
    ) -> List[str]:
        """Генерирует персонализированные рекомендации."""
        recommendations = []
        
        # Сон
        avg_sleep = self._average([agg.sleep.hours for agg in aggregates if agg.sleep.hours])
        if avg_sleep < 7:
            recommendations.append("Старайся спать 7-8 часов — это улучшит метаболизм на 8-12%")
        
        # Шаги
        avg_steps = self._average([agg.activity.steps for agg in aggregates if agg.activity.steps])
        if avg_steps < 8000:
            recommendations.append("Увеличь NEAT до 8000-10000 шагов в день для дополнительного расхода 300-500 ккал")
        
        # Белок
        avg_protein = self._average([agg.nutrition.total_protein_g for agg in aggregates])
        weight = aggregates[-1].measurements.weight_kg if aggregates else 70
        if avg_protein < weight * 1.6:
            recommendations.append(f"Увеличь потребление белка до {int(weight * 1.6)} г/день для сохранения мышц")
        
        # Стресс
        avg_stress = self._average([agg.stress for agg in aggregates if agg.stress])
        if avg_stress > 6:
            recommendations.append("Практикуй дыхательные упражнения или медитацию для снижения кортизола")
        
        # Добавляем общую рекомендацию, если нет специфичных
        if not recommendations:
            recommendations.append("Продолжай в том же духе! Ты на правильном пути 💪")
            recommendations.append("Заполняй метрики каждый день для более точных рекомендаций")
        
        return recommendations[:3]