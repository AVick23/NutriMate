"""
Генератор умных недельных отчётов.
"""
import logging
from datetime import date, timedelta
from typing import List, Optional
from db import Database
from .engine import DailyAggregator
from .intelligence import StateDetector, PatternDetector, InsightGenerator
from .core import DailyAggregate, STATE_NAMES, METRIC_NAMES, safe_average, calculate_trend_slope, get_progress_bar

logger = logging.getLogger(__name__)

class WeeklyReportGenerator:
    def __init__(self, db: Database):
        self.db = db
        self.aggregator = DailyAggregator(db)
        self.state_detector = StateDetector()
        self.pattern_detector = PatternDetector(db)
        self.insight_generator = InsightGenerator()

    async def generate_report(self, user_id: int, profile: dict, end_date: Optional[date] = None) -> str:
        if end_date is None:
            end_date = date.today()
        start_date = end_date - timedelta(days=6)  # 7 дней включительно

        # Сбор данных
        aggregates = []
        for i in range(7):
            d = start_date + timedelta(days=i)
            agg = await self.aggregator.aggregate(user_id, d)
            aggregates.append(agg)

        if not aggregates or all(a.nutrition.total_kcal == 0 and not a.measurements.weight_kg for a in aggregates):
            return "📊 Недостаточно данных для отчёта. Заполняй метрики чаще!"

        report = []
        report.append("📊 <b>Недельный отчёт</b>")
        report.append(f"{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}")
        report.append("─────────────────")

        # 1. 🎯 Консистентность
        active_days = sum(1 for a in aggregates if a.nutrition.total_kcal > 0 or a.measurements.weight_kg)
        consistency_pct = int((active_days / 7) * 100)
        report.append(f"\n🎯 <b>Консистентность:</b> {active_days}/7 дней ({consistency_pct}%)")
        if consistency_pct >= 85:
            report.append("🔥 Отличный темп! Регулярность важнее идеальных цифр.")
        elif consistency_pct < 50:
            report.append("💡 Попробуй заполнять дневник хотя бы 4 раза в неделю.")

        # 2. 📈 Средние значения с прогресс-барами
        avg_kcal = safe_average([a.nutrition.total_kcal for a in aggregates])
        avg_protein = safe_average([a.nutrition.total_protein_g for a in aggregates])
        goal_kcal = profile.get("daily_kcal", 2000)
        goal_protein = profile.get("daily_protein_g", 150)

        report.append("\n<b>📈 Средние значения:</b>")
        if avg_kcal:
            report.append(f"🔥 Калории: {avg_kcal:.0f} / {goal_kcal} ккал {get_progress_bar(avg_kcal, goal_kcal)}")
        if avg_protein:
            report.append(f"🍗 Белок: {avg_protein:.0f} / {goal_protein} г {get_progress_bar(avg_protein, goal_protein)}")

        # 3. 📉 Динамика (Линейная регрессия вместо last - first)
        report.append("\n<b>📉 Динамика за неделю:</b>")
        
        weights = [a.measurements.weight_kg for a in aggregates if a.measurements.weight_kg]
        if len(weights) >= 3:
            slope = calculate_trend_slope(weights)
            weekly_change = slope * 7
            direction = "📉" if weekly_change < -0.1 else "📈" if weekly_change > 0.1 else "➡️"
            report.append(f"{direction} Вес: {weekly_change:+.1f} кг (тренд)")
            if abs(weekly_change) < 0.3 and profile.get("goal") == "cutting":
                report.append("   <i>Вес встал, но это нормально. Проверь талию!</i>")

        waists = [a.measurements.waist_cm for a in aggregates if a.measurements.waist_cm]
        if len(waists) >= 3:
            slope = calculate_trend_slope(waists)
            weekly_change = slope * 7
            direction = "📉" if weekly_change < -0.1 else "📈" if weekly_change > 0.1 else "➡️"
            report.append(f"{direction} Талия: {weekly_change:+.1f} см (тренд)")

        # 4. 🔍 Состояния
        states = self.state_detector.detect_states(aggregates, profile)
        if states:
            report.append("\n<b>🔍 Обнаруженные состояния:</b>")
            for s in states:
                report.append(f"{s.emoji} <b>{STATE_NAMES.get(s.state_type, s.state_type)}</b> (уверенность: {s.risk_score}/5)")
                report.append(f"   <i>{s.recommendation[:100]}...</i>")

        # 5. 💡 Персональные инсайты и паттерны
        patterns = await self.pattern_detector.detect_patterns(user_id, aggregates)
        insights = self.insight_generator.generate_insights(aggregates[-1], profile, patterns)
        
        if insights:
            report.append("\n<b>💡 Персональные инсайты:</b>")
            for ins in insights:
                report.append(f"{ins.emoji} <b>{ins.title}</b>")
                report.append(f"   {ins.message}")

        # 6. Футер
        report.append("\n─────────────────")
        report.append("<i>Продолжай в том же духе! Данные работают на тебя.</i>")

        return "\n".join(report)