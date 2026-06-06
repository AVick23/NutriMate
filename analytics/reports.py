"""
Генератор недельных отчётов.
"""
import logging
from datetime import date, timedelta
from typing import List, Optional

from db import Database
from .engine import DailyAggregator
from .intelligence import StateDetector
from .core import DailyAggregate, STATE_NAMES, safe_average

logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """Генерирует недельные отчёты для пользователя."""

    def __init__(self, db: Database):
        self.db = db
        self.state_detector = StateDetector()

    async def generate_report(
        self,
        user_id: int,
        profile: dict,
        end_date: Optional[date] = None
    ) -> str:
        """Генерирует текстовый отчёт за последние 7 дней."""
        if end_date is None:
            end_date = date.today() - timedelta(days=1)

        start_date = end_date - timedelta(days=7)

        # Собираем агрегаты за 8 дней
        aggregator = DailyAggregator(self.db)
        aggregates = []
        for i in range(8):
            d = start_date + timedelta(days=i)
            if d <= end_date:
                aggregates.append(
                    await aggregator.aggregate(user_id, d)
                )

        if not aggregates:
            return (
                "📊 Недостаточно данных для отчёта. "
                "Заполняй метрики чаще!"
            )

        report = []

        # 1. Заголовок
        report.append(f"📊 <b>Недельный отчёт</b>\n")
        report.append(
            f"{start_date.strftime('%d.%m')} — "
            f"{end_date.strftime('%d.%m')}\n"
        )
        report.append("─────────────────")
        report.append("\n<b>📈 Средние значения за неделю:</b>\n")

        avg_kcal = self._safe_avg(
            [a.nutrition.total_kcal for a in aggregates]
        )
        avg_protein = self._safe_avg(
            [a.nutrition.total_protein_g for a in aggregates]
        )
        avg_steps = self._safe_avg(
            [a.activity.steps for a in aggregates if a.activity.steps]
        )
        avg_sleep = self._safe_avg(
            [a.sleep.hours for a in aggregates if a.sleep.hours]
        )

        if avg_kcal:
            report.append(f"🔥 Калории: {avg_kcal:.0f} ккал/день")
        if avg_protein:
            report.append(f"🍗 Белок: {avg_protein:.0f} г/день")
        if avg_steps:
            report.append(f"👣 Шаги: {avg_steps:.0f} шагов/день")
        if avg_sleep:
            report.append(f"😴 Сон: {avg_sleep:.1f} ч/день")

        # 2. Динамика
        report.append("\n<b>📉 Динамика за неделю:</b>\n")

        weights = [
            a.measurements.weight_kg
            for a in aggregates if a.measurements.weight_kg
        ]
        if len(weights) >= 2:
            change = weights[-1] - weights[0]
            direction = (
                "📉" if change < 0
                else "📈" if change > 0
                else "➡️"
            )
            report.append(
                f"{direction} Вес: {abs(change):.1f} кг"
            )

        waists = [
            a.measurements.waist_cm
            for a in aggregates if a.measurements.waist_cm
        ]
        if len(waists) >= 2:
            change = waists[-1] - waists[0]
            direction = (
                "📉" if change < 0
                else "📈" if change > 0
                else "➡️"
            )
            report.append(
                f"{direction} Талия: {abs(change):.1f} см"
            )

        # 3. Состояния
        states = self.state_detector.detect_states(aggregates, profile)
        if states:
            report.append("\n<b>🔍 Обнаруженные состояния:</b>\n")
            for s in states:
                if s.detected:
                    name = self._state_name(s.state_type)
                    report.append(
                        f"{s.emoji} <b>{name}</b>"
                    )
                    report.append(
                        f"   {s.recommendation[:100]}..."
                    )

        # 4. Рекомендации
        report.append(
            "\n<b>💡 Рекомендации на следующую неделю:</b>\n"
        )
        recs = self._generate_recommendations(aggregates, profile)
        for r in recs:
            report.append(f"• {r}")

        # 5. Футер
        report.append("\n─────────────────")
        report.append(
            "\n📝 <i>Заполняй метрики каждый день "
            "для точного анализа!</i>"
        )

        return "\n".join(report)

    def _safe_avg(self, values: List) -> Optional[float]:
        """Безопасное среднее, игнорируя None."""
        filtered = [v for v in values if v is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)

    def _state_name(self, state_type: str) -> str:
        """Человекочитаемое название состояния."""
        return STATE_NAMES.get(state_type, state_type)

    def _generate_recommendations(
        self, aggregates: List[DailyAggregate], profile: dict
    ) -> List[str]:
        """Персонализированные рекомендации."""
        recs = []

        # Сон
        avg_sleep = self._safe_avg(
            [a.sleep.hours for a in aggregates if a.sleep.hours]
        )
        if avg_sleep and avg_sleep < 7:
            recs.append(
                "Старайся спать 7-8 часов — это улучшит "
                "метаболизм на 8-12%"
            )

        # Шаги
        avg_steps = self._safe_avg(
            [a.activity.steps for a in aggregates if a.activity.steps]
        )
        if avg_steps and avg_steps < 8000:
            recs.append(
                "Увеличь NEAT до 8000-10000 шагов в день "
                "для +300-500 ккал"
            )

        # Белок
        avg_protein = self._safe_avg(
            [a.nutrition.total_protein_g for a in aggregates]
        )
        weight = (
            aggregates[-1].measurements.weight_kg
            if aggregates else 70
        )
        if (avg_protein and weight
                and avg_protein < weight * 1.6):
            recs.append(
                f"Увеличь белок до {int(weight * 1.6)} г/день"
            )

        # Если ничего специфичного нет
        if not recs:
            recs.append("Продолжай в том же духе! 💪")

        return recs[:3]