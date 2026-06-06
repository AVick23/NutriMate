"""
Обработчики для сбора ежедневных метрик и аналитики.
Полностью переработанная версия с исправлением всех критических багов.
"""
import logging
from datetime import date, timedelta
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from telegram.error import BadRequest
from db import Database, UserRepository, DailyMetricsRepository
from .constants import *
from .keyboards import *
from .utils import format_metrics_summary, get_default_metrics, split_long_message
from .logger import log_metrics_action

logger = logging.getLogger(__name__)


class MetricsHandlers:
    """Обработчики для сбора метрик и аналитики."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.metrics_repo = DailyMetricsRepository(db)

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ================================================================

    def _get_today_metrics(self, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Получает текущие метрики из context.user_data."""
        return context.user_data.get("metrics_data", get_default_metrics())

    def _save_today_metrics(self, context: ContextTypes.DEFAULT_TYPE, metrics: Dict[str, Any]) -> None:
        """Сохраняет метрики в context.user_data."""
        context.user_data["metrics_data"] = metrics

    def _update_metric(self, context: ContextTypes.DEFAULT_TYPE, key: str, value: Any) -> None:
        """Обновляет одну метрику."""
        metrics = self._get_today_metrics(context)
        metrics[key] = value
        self._save_today_metrics(context, metrics)

    def _clear_metrics(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Очищает все метрики и режим сессии."""
        context.user_data.pop("metrics_data", None)
        context.user_data.pop("session_mode", None)
        context.user_data.pop("awaiting_custom_input", None)

    def _set_session_mode(self, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        """Устанавливает режим сессии (full/edit)."""
        context.user_data["session_mode"] = mode

    def _is_edit_mode(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверяет, в режиме ли редактирования."""
        return context.user_data.get("session_mode") == SESSION_EDIT

    async def _safe_edit_message(self, query, text: str, reply_markup=None) -> bool:
        """Безопасно редактирует сообщение."""
        if not query:
            return False
        try:
            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return True
        except BadRequest as e:
            if "Message is not modified" in str(e):
                return False
            logger.warning(f"Edit message failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return False

    async def _send_error_message(self, update: Update, text: str) -> None:
        """Отправляет сообщение об ошибке."""
        try:
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

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

    # ================================================================
    # ВХОДНАЯ ТОЧКА
    # ================================================================

    async def show_metrics_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает главное меню метрик."""
        query = update.callback_query
        if query:
            await query.answer()

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        if not user_id:
            text = "❌ Сначала нужно пройти регистрацию. Отправь команду /start"
            if query:
                await self._safe_edit_message(query, text)
            else:
                await update.message.reply_text(text, parse_mode="HTML")
            return ConversationHandler.END

        text = (
            "📊 <b>Мои метрики</b>\n\n"
            "Здесь я собираю данные о твоём состоянии:\n"
            "• Сон, энергия, стресс\n"
            "• Шаги и активность\n"
            "• Тренировки\n\n"
            "Чем больше данных — тем точнее мои рекомендации! 🧠"
        )

        if query:
            await self._safe_edit_message(query, text, get_metrics_main_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_metrics_main_keyboard(),
                parse_mode="HTML"
            )

        log_metrics_action(user_id, "open_menu")
        return STATE_MAIN_MENU

    async def handle_main_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор из главного меню."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = await self.user_repo.get_user_id(update.effective_user.id)

        if data == CALLBACK_METRICS_BACK_TO_DIARY:
            log_metrics_action(user_id, "back_to_diary_from_menu")
            return await self._back_to_diary(update, context)

        if data == CALLBACK_METRICS_TODAY:
            # Проверка на уже заполненные метрики
            today = date.today()
            try:
                existing = await self.metrics_repo.get_metrics(user_id, today)
                if existing and any(v is not None for v in existing.values()):
                    await query.answer(
                        "⚠️ Метрики за сегодня уже заполнены. Используй 'Редактировать'.",
                        show_alert=True
                    )
                    log_metrics_action(user_id, "metrics_already_filled", status="skipped")
                    return STATE_MAIN_MENU
            except Exception as e:
                logger.warning(f"Error checking existing metrics: {e}")

            self._clear_metrics(context)
            self._set_session_mode(context, SESSION_FULL)
            log_metrics_action(user_id, "start_full_session")
            return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_EDIT:
            today = date.today()
            try:
                existing = await self.metrics_repo.get_metrics(user_id, today)
            except Exception as e:
                logger.warning(f"Error loading metrics for edit: {e}")
                existing = None

            if existing and any(v is not None for v in existing.values()):
                self._save_today_metrics(context, dict(existing))
                self._set_session_mode(context, SESSION_EDIT)
                log_metrics_action(user_id, "start_edit_session", {
                    "metrics_count": sum(1 for v in existing.values() if v is not None)
                })
                return await self._show_edit_menu(update, context)
            else:
                await query.answer("Нет сохранённых метрик за сегодня", show_alert=True)
                self._set_session_mode(context, SESSION_FULL)
                log_metrics_action(user_id, "edit_no_existing", status="skipped")
                return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_ANALYTICS:
            log_metrics_action(user_id, "open_analytics")
            return await self._show_analytics_menu(update, context)

        if data == CALLBACK_METRICS_HISTORY:
            log_metrics_action(user_id, "open_history")
            text = "📊 <b>История метрик</b>\n\nФункция в разработке. Скоро появится! 🚀"
            await self._safe_edit_message(
                query,
                text,
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_MAIN_MENU

        return STATE_MAIN_MENU

    # ================================================================
    # АНАЛИТИКА
    # ================================================================

    async def _show_analytics_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает меню выбора типа аналитики."""
        query = update.callback_query
        if query:
            await query.answer()

        text = (
            "📊 <b>Аналитика</b>\n\n"
            "Выбери, какую аналитику хочешь посмотреть:\n\n"
            "• <b>Дневная</b> — детальный анализ за конкретный день\n"
            "• <b>Недельная</b> — средние значения и тренды за 7 дней\n"
            "• <b>Тренды</b> — динамика изменений за последние 30 дней"
        )

        if query:
            await self._safe_edit_message(query, text, get_analytics_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_analytics_keyboard(),
                parse_mode="HTML"
            )
        return STATE_ANALYTICS

    async def handle_analytics(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор типа аналитики."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        if data == CALLBACK_ANALYTICS_DAILY:
            log_metrics_action(user_id, "view_daily_analytics")
            return await self._show_daily_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_WEEKLY:
            log_metrics_action(user_id, "view_weekly_analytics")
            return await self._show_weekly_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_TRENDS:
            log_metrics_action(user_id, "view_trends_analytics")
            return await self._show_trends_analytics(update, context, user_id)
        elif data == CALLBACK_METRICS_BACK_TO_MENU:
            return await self.show_metrics_menu(update, context)

        return STATE_ANALYTICS

    async def _show_daily_analytics(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
    ) -> int:
        """Показывает дневную аналитику за вчера."""
        query = update.callback_query
        yesterday = date.today() - timedelta(days=1)

        try:
            from analytics import DailyAggregator, ModifierEngine, InsightGenerator

            aggregator = DailyAggregator(self.db)
            modifier_engine = ModifierEngine(self.db)
            insight_gen = InsightGenerator()

            aggregated = await aggregator.aggregate(user_id, yesterday)
            profile = await self.user_repo.get_profile(user_id)
            # ИСПРАВЛЕНО: используем .get() с дефолтным значением
            base_tdee = profile.get("daily_kcal", 2000) if profile else 2000

            adjusted_tdee, modifiers, confidence = await modifier_engine.calculate_adjusted_tdee(
                user_id, base_tdee, aggregated
            )
            insights = insight_gen.generate_insights(aggregated)

        except Exception as e:
            logger.error(f"Analytics error: {e}", exc_info=True)
            log_metrics_action(user_id, "daily_analytics_error", {"error": str(e)}, status="error")
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при расчёте аналитики. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS

        text = f"📅 <b>Аналитика за {yesterday.strftime('%d.%m.%Y')}</b>\n\n"
        text += "─────────────────\n"
        text += "📊 <b>Основные показатели</b>\n"
        text += f"🔥 Калории: {aggregated.nutrition.total_kcal} ккал\n"
        if aggregated.nutrition.total_protein_g:
            text += f"🍗 Белок: {aggregated.nutrition.total_protein_g:.0f} г\n"
        if aggregated.water_ml:
            text += f"💧 Вода: {aggregated.water_ml} мл\n"
        if aggregated.sleep.hours:
            text += f"😴 Сон: {aggregated.sleep.hours:.1f} ч"
            if aggregated.sleep.quality:
                text += f" ({'⭐' * aggregated.sleep.quality})"
            text += "\n"
        if aggregated.stress:
            text += f"😰 Стресс: {aggregated.stress}/10\n"
        if aggregated.activity.steps:
            text += f"👣 Шаги: {aggregated.activity.steps:,}\n"
        if aggregated.derived.eating_window_hours:
            text += f"⏰ Окно питания: {aggregated.derived.eating_window_hours:.0f} ч\n"

        text += "\n─────────────────\n"
        text += "⚡ <b>Метаболизм (TDEE)</b>\n"
        text += f"📊 Базовый: {base_tdee} ккал\n"
        text += f"🎯 Скорректированный: {adjusted_tdee} ккал\n"

        if confidence < 70:
            text += f"\n⚠️ <i>Точность анализа: {confidence}% (заполни больше метрик)</i>\n"

        if insights:
            text += "\n─────────────────\n"
            text += "💡 <b>Персональные инсайты</b>\n"
            for insight in insights[:3]:
                text += f"\n{insight.emoji} <b>{insight.title}</b>\n"
                text += f"   {insight.message[:100]}"
                if len(insight.message) > 100:
                    text += "..."
                text += "\n"

        if aggregated.sleep.hours is None and aggregated.stress is None:
            text += "\n─────────────────\n"
            text += "📝 <i>Заполни больше метрик (сон, стресс, шаги),</i>\n"
            text += "<i>чтобы я мог давать более точные рекомендации!</i>\n"

        text += "\n─────────────────\n"
        text += "📊 #NutriMate"

        # Разбиваем длинное сообщение, если нужно
        parts = split_long_message(text, max_length=4000)
        for i, part in enumerate(parts):
            if i == 0:
                await self._safe_edit_message(
                    query, part,
                    get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
                )
            else:
                await query.message.reply_text(part, parse_mode="HTML")

        return STATE_ANALYTICS

    async def _show_weekly_analytics(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
    ) -> int:
        """Показывает недельную аналитику."""
        query = update.callback_query

        try:
            from analytics import WeeklyReportGenerator

            profile = await self.user_repo.get_profile(user_id)
            report_gen = WeeklyReportGenerator(self.db)
            report = await report_gen.generate_report(user_id, profile)
            report = report.replace("━" * 30, "─────────────────")
            report = report.replace("━" * 25, "─────────────────")
        except Exception as e:
            logger.error(f"Weekly analytics error: {e}", exc_info=True)
            log_metrics_action(user_id, "weekly_analytics_error", {"error": str(e)}, status="error")
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при формировании отчёта. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS

        parts = split_long_message(report, 4000)
        for i, part in enumerate(parts):
            if i == 0:
                await self._safe_edit_message(
                    query, part,
                    get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
                )
            else:
                await query.message.reply_text(part, parse_mode="HTML")

        return STATE_ANALYTICS

    async def _show_trends_analytics(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
    ) -> int:
        """Показывает тренды и прогресс за последние 30 дней."""
        query = update.callback_query

        try:
            from analytics import DailyAggregator, StateDetector

            aggregator = DailyAggregator(self.db)
            state_detector = StateDetector()

            end_date = date.today() - timedelta(days=1)
            start_date = end_date - timedelta(days=30)

            aggregates = []
            for i in range(31):
                current_date = start_date + timedelta(days=i)
                if current_date <= end_date:
                    agg = await aggregator.aggregate(user_id, current_date)
                    aggregates.append(agg)

            profile = await self.user_repo.get_profile(user_id)
            states = state_detector.detect_states(aggregates, profile)

        except Exception as e:
            logger.error(f"Trends analytics error: {e}", exc_info=True)
            log_metrics_action(user_id, "trends_analytics_error", {"error": str(e)}, status="error")
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при расчёте трендов. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS

        text = "📈 <b>Тренды за 30 дней</b>\n\n"
        text += "─────────────────\n"
        text += "📊 <b>Динамика измерений</b>\n"

        weights = [agg.measurements.weight_kg for agg in aggregates if agg.measurements.weight_kg]
        if len(weights) >= 2:
            first_weight = weights[0]
            last_weight = weights[-1]
            change = last_weight - first_weight
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            text += f"⚖️ Вес: {first_weight:.1f} → {last_weight:.1f} кг ({direction} {abs(change):.1f} кг)\n"

        waists = [agg.measurements.waist_cm for agg in aggregates if agg.measurements.waist_cm]
        if len(waists) >= 2:
            first_waist = waists[0]
            last_waist = waists[-1]
            change = last_waist - first_waist
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            text += f"📏 Талия: {first_waist:.1f} → {last_waist:.1f} см ({direction} {abs(change):.1f} см)\n"

        text += "\n─────────────────\n"
        text += "📊 <b>Средние значения</b>\n"

        sleep_hours = [agg.sleep.hours for agg in aggregates if agg.sleep.hours]
        if sleep_hours:
            avg_sleep = sum(sleep_hours) / len(sleep_hours)
            text += f"😴 Сон: {avg_sleep:.1f} ч/день\n"

        steps = [agg.activity.steps for agg in aggregates if agg.activity.steps]
        if steps:
            avg_steps = sum(steps) / len(steps)
            text += f"👣 Шаги: {avg_steps:.0f} шагов/день\n"

        kcals = [agg.nutrition.total_kcal for agg in aggregates if agg.nutrition.total_kcal > 0]
        if kcals:
            avg_kcal = sum(kcals) / len(kcals)
            text += f"🔥 Калории: {avg_kcal:.0f} ккал/день\n"

        active_states = [s for s in states if s.detected]
        if active_states:
            text += "\n─────────────────\n"
            text += "🔍 <b>Обнаруженные состояния</b>\n"
            for state in active_states[:3]:
                text += f"\n{state.emoji} <b>{self._state_name(state.state_type)}</b>\n"
                text += f"   {state.recommendation[:100]}"
                if len(state.recommendation) > 100:
                    text += "..."
                text += "\n"

        if len(aggregates) < 14:
            text += "\n─────────────────\n"
            text += "📝 <i>Заполняй метрики чаще для более точного анализа трендов!</i>\n"

        text += "\n─────────────────\n"
        text += "📊 #NutriMate"

        parts = split_long_message(text, 4000)
        for i, part in enumerate(parts):
            if i == 0:
                await self._safe_edit_message(
                    query, part,
                    get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
                )
            else:
                await query.message.reply_text(part, parse_mode="HTML")

        return STATE_ANALYTICS

    # ================================================================
    # ОБРАБОТКА РЕДАКТИРОВАНИЯ
    # ================================================================

    async def handle_edit_actions(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор параметра для редактирования."""
        query = update.callback_query
        logger.info(f"🔔 handle_edit_actions called with data: {query.data}")
        await query.answer()

        data = query.data

        if data == CALLBACK_EDIT_SLEEP:
            return await self._edit_sleep(update, context)
        elif data == CALLBACK_EDIT_ENERGY_MORNING:
            return await self._edit_energy_morning(update, context)
        elif data == CALLBACK_EDIT_ENERGY_EVENING:
            return await self._edit_energy_evening(update, context)
        elif data == CALLBACK_EDIT_STRESS:
            return await self._edit_stress(update, context)
        elif data == CALLBACK_EDIT_STEPS:
            return await self._edit_steps(update, context)
        elif data == CALLBACK_EDIT_WORKOUT:
            return await self._edit_workout(update, context)
        elif data == CALLBACK_CONFIRM_ALL:
            return await self.confirm_and_save(update, context)
        elif data == CALLBACK_METRICS_BACK_TO_MENU:
            return await self.show_metrics_menu(update, context)

        return STATE_EDIT_MENU

    async def _edit_sleep(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование сна."""
        query = update.callback_query
        text = f"{EMOJI_SLEEP} <b>Редактирование сна</b>\n\nСколько часов ты спал?"
        await self._safe_edit_message(query, text, get_sleep_keyboard())
        return STATE_SLEEP_HOURS

    async def _edit_energy_morning(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование энергии утром."""
        query = update.callback_query
        text = f"{EMOJI_ENERGY} <b>Редактирование энергии утром</b>\n\nОцени энергию от 1 до 10:"
        await self._safe_edit_message(query, text, get_energy_stress_keyboard("edit_energy_morning"))
        return STATE_ENERGY_MORNING

    async def _edit_energy_evening(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование энергии вечером."""
        query = update.callback_query
        text = f"{EMOJI_ENERGY} <b>Редактирование энергии вечером</b>\n\nОцени энергию от 1 до 10:"
        await self._safe_edit_message(query, text, get_energy_stress_keyboard("edit_energy_evening"))
        return STATE_ENERGY_EVENING

    async def _edit_stress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование стресса."""
        query = update.callback_query
        text = f"{EMOJI_STRESS} <b>Редактирование стресса</b>\n\nОцени уровень стресса от 1 до 10:"
        await self._safe_edit_message(query, text, get_energy_stress_keyboard("edit_stress"))
        return STATE_STRESS

    async def _edit_steps(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование шагов."""
        query = update.callback_query
        text = f"{EMOJI_STEPS} <b>Редактирование шагов</b>\n\nСколько шагов ты прошёл?"
        await self._safe_edit_message(query, text, get_steps_keyboard())
        return STATE_STEPS

    async def _edit_workout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование тренировки."""
        query = update.callback_query
        text = f"{EMOJI_WORKOUT} <b>Редактирование тренировки</b>\n\nКакая была тренировка?"
        await self._safe_edit_message(query, text, get_workout_type_keyboard())
        return STATE_WORKOUT_TYPE

    # ================================================================
    # ОБРАБОТКА КНОПОК НАЗАД
    # ================================================================

    async def back_to_main_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат в главное меню метрик."""
        query = update.callback_query
        if query:
            await query.answer()
        return await self.show_metrics_menu(update, context)

    async def back_to_edit_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат в меню редактирования."""
        query = update.callback_query
        if query:
            await query.answer()
        return await self._show_edit_menu(update, context)

    # ================================================================
    # ПОШАГОВЫЙ СБОР МЕТРИК
    # ================================================================

    async def _start_sleep_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает опрос с вопроса о сне."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_SLEEP} <b>Сколько часов ты спал?</b>\n\nВыбери из вариантов или введи своё значение."

        if query:
            await self._safe_edit_message(query, text, get_sleep_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_sleep_keyboard(),
                parse_mode="HTML"
            )
        return STATE_SLEEP_HOURS

    async def process_sleep_hours(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод длительности сна."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            # Кнопка "Свой вариант"
            if data == "sleep_custom":
                context.user_data["awaiting_custom_input"] = "sleep_hours"
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество часов (например: 7.5 или 8):"
                )
                return STATE_SLEEP_HOURS

            # Готовые кнопки (sleep_6, sleep_6.5, sleep_7, ...)
            if data.startswith("sleep_"):
                try:
                    hours = float(data.replace("sleep_", ""))
                    # ВАЛИДАЦИЯ
                    if hours < 0 or hours > 24:
                        raise ValueError

                    self._update_metric(context, "sleep_hours", hours)
                    context.user_data.pop("awaiting_custom_input", None)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "sleep_hours", "value": hours, "input": "button"}
                    )
                    return await self._ask_sleep_quality(update, context)
                except ValueError:
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric_error",
                        {"metric": "sleep_hours", "error": "invalid_value"},
                        status="error"
                    )
                    await self._send_error_message(update, "❌ Ошибка: неверное значение (0-24).")
                    return STATE_SLEEP_HOURS

        elif update.message:
            # Текстовый ввод (для sleep_custom)
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if hours < 0 or hours > 24:
                    raise ValueError

                self._update_metric(context, "sleep_hours", hours)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "sleep_hours", "value": hours, "input": "text"}
                )
                return await self._ask_sleep_quality(update, context)
            except ValueError:
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric_error",
                    {"metric": "sleep_hours", "error": "invalid_text"},
                    status="error"
                )
                await update.message.reply_text(
                    "❌ Введи число от 0 до 24. Например: 7.5",
                    parse_mode="HTML"
                )
                return STATE_SLEEP_HOURS

        return STATE_SLEEP_HOURS

    async def _ask_sleep_quality(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает качество сна."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_SLEEP} <b>Оцени качество сна</b> (1 — очень плохо, 5 — отлично):"

        if query:
            await self._safe_edit_message(query, text, get_sleep_quality_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_sleep_quality_keyboard(),
                parse_mode="HTML"
            )
        return STATE_SLEEP_QUALITY

    async def process_sleep_quality(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает оценку качества сна."""
        query = update.callback_query
        await query.answer()

        data = query.data
        if data.startswith("quality_"):
            try:
                quality = int(data.replace("quality_", ""))
                if quality < 1 or quality > 5:
                    await self._send_error_message(update, "❌ Значение должно быть от 1 до 5.")
                    return STATE_SLEEP_QUALITY

                self._update_metric(context, "sleep_quality", quality)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "sleep_quality", "value": quality}
                )
                return await self._ask_sleep_awakenings(update, context)
            except ValueError:
                await self._send_error_message(update, "❌ Ошибка значения.")
                return STATE_SLEEP_QUALITY

        return STATE_SLEEP_QUALITY

    async def _ask_sleep_awakenings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает количество пробуждений."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_SLEEP} <b>Сколько раз ты просыпался за ночь?</b>"

        if query:
            await self._safe_edit_message(query, text, get_awakenings_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_awakenings_keyboard(),
                parse_mode="HTML"
            )
        return STATE_SLEEP_AWAKENINGS

    async def process_sleep_awakenings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает количество пробуждений."""
        query = update.callback_query
        await query.answer()

        data = query.data
        if data.startswith("awakenings_"):
            try:
                awakenings = int(data.replace("awakenings_", ""))
                self._update_metric(context, "sleep_awakenings", awakenings)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "sleep_awakenings", "value": awakenings}
                )
                return await self._ask_energy_morning(update, context)
            except ValueError:
                await self._send_error_message(update, "❌ Ошибка значения.")
                return STATE_SLEEP_AWAKENINGS

        return STATE_SLEEP_AWAKENINGS

    async def _ask_energy_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает энергию утром."""
        query = update.callback_query
        if query:
            await query.answer()

        prefix = "edit_energy_morning" if self._is_edit_mode(context) else "energy_morning"
        text = f"{EMOJI_ENERGY} <b>Как чувствуешь себя сейчас?</b>\n\nОцени энергию от 1 до 10:"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard(prefix),
                parse_mode="HTML"
            )
        return STATE_ENERGY_MORNING

    async def process_energy_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает оценку энергии утром."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            if data.startswith("energy_morning_"):
                try:
                    value = int(data.replace("energy_morning_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_ENERGY_MORNING

                    self._update_metric(context, "energy_morning", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "energy_morning", "value": value}
                    )

                    if self._is_edit_mode(context):
                        return await self._show_edit_menu(update, context)
                    return await self._ask_energy_evening(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_ENERGY_MORNING

            elif data.startswith("edit_energy_morning_"):
                try:
                    value = int(data.replace("edit_energy_morning_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_ENERGY_MORNING

                    self._update_metric(context, "energy_morning", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "energy_morning", "value": value, "mode": "edit"}
                    )
                    return await self._show_edit_menu(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_ENERGY_MORNING

        return STATE_ENERGY_MORNING

    async def _ask_energy_evening(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает энергию вечером."""
        query = update.callback_query
        if query:
            await query.answer()

        prefix = "edit_energy_evening" if self._is_edit_mode(context) else "energy_evening"
        text = f"{EMOJI_ENERGY} <b>Как чувствуешь себя вечером?</b>\n\nОцени энергию от 1 до 10:"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard(prefix),
                parse_mode="HTML"
            )
        return STATE_ENERGY_EVENING

    async def process_energy_evening(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает оценку энергии вечером."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            if data.startswith("energy_evening_"):
                try:
                    value = int(data.replace("energy_evening_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_ENERGY_EVENING

                    self._update_metric(context, "energy_evening", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "energy_evening", "value": value}
                    )

                    if self._is_edit_mode(context):
                        return await self._show_edit_menu(update, context)
                    return await self._ask_stress(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_ENERGY_EVENING

            elif data.startswith("edit_energy_evening_"):
                try:
                    value = int(data.replace("edit_energy_evening_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_ENERGY_EVENING

                    self._update_metric(context, "energy_evening", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "energy_evening", "value": value, "mode": "edit"}
                    )
                    return await self._show_edit_menu(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_ENERGY_EVENING

        return STATE_ENERGY_EVENING

    async def _ask_stress(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает уровень стресса."""
        query = update.callback_query
        if query:
            await query.answer()

        prefix = "edit_stress" if self._is_edit_mode(context) else "stress"
        text = f"{EMOJI_STRESS} <b>Оцени уровень стресса за сегодня</b> (1 — спокоен, 10 — очень напряжён):"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard(prefix),
                parse_mode="HTML"
            )
        return STATE_STRESS

    async def process_stress(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает оценку стресса."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            if data.startswith("stress_"):
                try:
                    value = int(data.replace("stress_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_STRESS

                    self._update_metric(context, "stress_level", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "stress_level", "value": value}
                    )

                    if self._is_edit_mode(context):
                        return await self._show_edit_menu(update, context)
                    return await self._ask_steps(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_STRESS

            elif data.startswith("edit_stress_"):
                try:
                    value = int(data.replace("edit_stress_", ""))
                    if value < 1 or value > 10:
                        await self._send_error_message(update, "❌ Значение должно быть от 1 до 10.")
                        return STATE_STRESS

                    self._update_metric(context, "stress_level", value)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "stress_level", "value": value, "mode": "edit"}
                    )
                    return await self._show_edit_menu(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка значения.")
                    return STATE_STRESS

        return STATE_STRESS

    async def _ask_steps(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает количество шагов."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_STEPS} <b>Сколько шагов ты прошёл сегодня?</b>"

        if query:
            await self._safe_edit_message(query, text, get_steps_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_steps_keyboard(),
                parse_mode="HTML"
            )
        return STATE_STEPS

    async def process_steps(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод количества шагов."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            if data == "steps_custom":
                context.user_data["awaiting_custom_input"] = "steps"
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество шагов (например: 8500):"
                )
                return STATE_STEPS

            # Кнопки steps_2000, steps_3000, ...
            if data.startswith("steps_"):
                try:
                    steps = int(data.replace("steps_", ""))
                    if steps < 0 or steps > 100000:
                        raise ValueError

                    self._update_metric(context, "steps", steps)
                    context.user_data.pop("awaiting_custom_input", None)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "steps", "value": steps, "input": "button"}
                    )

                    if self._is_edit_mode(context):
                        return await self._show_edit_menu(update, context)
                    return await self._ask_hours_on_feet(update, context)
                except ValueError:
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric_error",
                        {"metric": "steps", "error": "invalid_value"},
                        status="error"
                    )
                    await self._send_error_message(update, "❌ Шаги должны быть от 0 до 100000.")
                    return STATE_STEPS

        elif update.message:
            try:
                steps = int(update.message.text.strip())
                if steps < 0 or steps > 100000:
                    raise ValueError

                self._update_metric(context, "steps", steps)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "steps", "value": steps, "input": "text"}
                )

                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_hours_on_feet(update, context)
            except ValueError:
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric_error",
                    {"metric": "steps", "error": "invalid_text"},
                    status="error"
                )
                await update.message.reply_text(
                    "❌ Введи число от 0 до 100000.",
                    parse_mode="HTML"
                )
                return STATE_STEPS

        return STATE_STEPS

    async def _ask_hours_on_feet(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает количество часов на ногах."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_STEPS} <b>Сколько часов ты провёл на ногах?</b>\n(не считая тренировок)"

        if query:
            await self._safe_edit_message(query, text, get_hours_on_feet_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_hours_on_feet_keyboard(),
                parse_mode="HTML"
            )
        return STATE_HOURS_ON_FEET

    async def process_hours_on_feet(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод часов на ногах."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            if data == "feet_custom":
                context.user_data["awaiting_custom_input"] = "hours_on_feet"
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество часов (например: 4.5):"
                )
                return STATE_HOURS_ON_FEET

            # Кнопки feet_1, feet_3, ...
            if data.startswith("feet_"):
                try:
                    hours = float(data.replace("feet_", ""))
                    if hours < 0 or hours > 24:
                        raise ValueError

                    self._update_metric(context, "hours_on_feet", hours)
                    context.user_data.pop("awaiting_custom_input", None)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "hours_on_feet", "value": hours, "input": "button"}
                    )

                    if self._is_edit_mode(context):
                        return await self._show_edit_menu(update, context)
                    return await self._ask_workout_type(update, context)
                except ValueError:
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric_error",
                        {"metric": "hours_on_feet", "error": "invalid_value"},
                        status="error"
                    )
                    await self._send_error_message(update, "❌ Часы должны быть от 0 до 24.")
                    return STATE_HOURS_ON_FEET

        elif update.message:
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if hours < 0 or hours > 24:
                    raise ValueError

                self._update_metric(context, "hours_on_feet", hours)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "hours_on_feet", "value": hours, "input": "text"}
                )

                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_workout_type(update, context)
            except ValueError:
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric_error",
                    {"metric": "hours_on_feet", "error": "invalid_text"},
                    status="error"
                )
                await update.message.reply_text(
                    "❌ Введи число от 0 до 24.",
                    parse_mode="HTML"
                )
                return STATE_HOURS_ON_FEET

        return STATE_HOURS_ON_FEET

    async def _ask_workout_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает тип тренировки."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_WORKOUT} <b>Была ли у тебя тренировка сегодня?</b>"

        if query:
            await self._safe_edit_message(query, text, get_workout_type_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_workout_type_keyboard(),
                parse_mode="HTML"
            )
        return STATE_WORKOUT_TYPE

    async def process_workout_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор типа тренировки."""
        query = update.callback_query
        await query.answer()

        data = query.data
        if data.startswith("workout_type_"):
            workout_type = data.replace("workout_type_", "")
            self._update_metric(context, "workout_type", workout_type)
            log_metrics_action(
                update.effective_user.id,
                "save_metric",
                {"metric": "workout_type", "value": workout_type}
            )

            if workout_type == "none":
                # Сбрасываем остальные поля тренировки
                self._update_metric(context, "workout_duration", None)
                self._update_metric(context, "workout_intensity", None)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._show_confirm(update, context)
            else:
                return await self._ask_workout_duration(update, context)

        return STATE_WORKOUT_TYPE

    async def _ask_workout_duration(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает длительность тренировки."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_WORKOUT} <b>Сколько минут длилась тренировка?</b>"

        if query:
            await self._safe_edit_message(query, text, get_workout_duration_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_workout_duration_keyboard(),
                parse_mode="HTML"
            )
        return STATE_WORKOUT_DURATION

    async def process_workout_duration(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает ввод длительности тренировки."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            # Кнопка "Свой вариант"
            if data == "duration_custom":
                context.user_data["awaiting_custom_input"] = "workout_duration"
                await self._safe_edit_message(
                    query,
                    "✏️ Введи длительность в минутах (например: 45):"
                )
                return STATE_WORKOUT_DURATION

            # ИСПРАВЛЕНО: обработка кнопки "Назад к типу"
            if data == CALLBACK_BACK_TO_WORKOUT_TYPE or data == "back_to_workout_type":
                return await self._ask_workout_type(update, context)

            # Готовые кнопки длительности
            if data.startswith("workout_duration_"):
                try:
                    duration = int(data.replace("workout_duration_", ""))
                    if duration <= 0 or duration > 480:
                        raise ValueError

                    self._update_metric(context, "workout_duration", duration)
                    context.user_data.pop("awaiting_custom_input", None)
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric",
                        {"metric": "workout_duration", "value": duration, "input": "button"}
                    )
                    return await self._ask_workout_intensity(update, context)
                except ValueError:
                    log_metrics_action(
                        update.effective_user.id,
                        "save_metric_error",
                        {"metric": "workout_duration", "error": "invalid_value"},
                        status="error"
                    )
                    await self._send_error_message(
                        update,
                        "❌ Длительность должна быть от 1 до 480 минут."
                    )
                    return STATE_WORKOUT_DURATION

        elif update.message:
            try:
                duration = int(update.message.text.strip())
                if duration <= 0 or duration > 480:
                    raise ValueError

                self._update_metric(context, "workout_duration", duration)
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric",
                    {"metric": "workout_duration", "value": duration, "input": "text"}
                )
                return await self._ask_workout_intensity(update, context)
            except ValueError:
                log_metrics_action(
                    update.effective_user.id,
                    "save_metric_error",
                    {"metric": "workout_duration", "error": "invalid_text"},
                    status="error"
                )
                await update.message.reply_text(
                    "❌ Введи число от 1 до 480 минут.",
                    parse_mode="HTML"
                )
                return STATE_WORKOUT_DURATION

        return STATE_WORKOUT_DURATION

    async def _ask_workout_intensity(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает интенсивность тренировки."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_WORKOUT} <b>Оцени интенсивность тренировки</b> (RPE 1-10):"

        if query:
            await self._safe_edit_message(query, text, get_workout_intensity_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_workout_intensity_keyboard(),
                parse_mode="HTML"
            )
        return STATE_WORKOUT_INTENSITY

    async def process_workout_intensity(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает оценку интенсивности."""
        query = update.callback_query
        await query.answer()

        data = query.data
        # Маппинг диапазонов в средние значения RPE
        intensity_map = {
            "intensity_1": 2,
            "intensity_3": 4,
            "intensity_5": 6,
            "intensity_7": 8,
            "intensity_9": 10,
        }

        if data in intensity_map:
            intensity = intensity_map[data]
            self._update_metric(context, "workout_intensity", intensity)
            log_metrics_action(
                update.effective_user.id,
                "save_metric",
                {"metric": "workout_intensity", "value": intensity}
            )

            if self._is_edit_mode(context):
                return await self._show_edit_menu(update, context)
            return await self._show_confirm(update, context)

        return STATE_WORKOUT_INTENSITY

    # ================================================================
    # ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
    # ================================================================

    async def _show_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает экран подтверждения."""
        query = update.callback_query
        if query:
            await query.answer()

        metrics = self._get_today_metrics(context)
        text = (
            "📊 <b>Твои метрики за сегодня</b>\n\n"
            f"{format_metrics_summary(metrics)}\n\n"
            "Всё верно?"
        )

        if query:
            await self._safe_edit_message(query, text, get_confirm_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_confirm_keyboard(),
                parse_mode="HTML"
            )
        return STATE_CONFIRM

    async def _show_edit_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает меню для редактирования метрик."""
        query = update.callback_query
        if query:
            await query.answer()

        metrics = self._get_today_metrics(context)
        text = (
            "✏️ <b>Редактирование метрик</b>\n\n"
            f"{format_metrics_summary(metrics)}\n\n"
            "Что хочешь изменить?"
        )

        if query:
            await self._safe_edit_message(query, text, get_edit_keyboard())
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_edit_keyboard(),
                parse_mode="HTML"
            )
        return STATE_EDIT_MENU

    async def confirm_and_save(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет метрики в БД и завершает."""
        query = update.callback_query

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        metrics = self._get_today_metrics(context)

        # Подсчёт заполненных метрик
        filled_metrics = [k for k, v in metrics.items() if v is not None]
        metrics_count = len(filled_metrics)

        try:
            today = date.today()
            # Пробуем использовать save_metrics (оптимальный путь)
            try:
                await self.metrics_repo.save_metrics(user_id, today, metrics)
                await query.answer("✅ Метрики сохранены!")
                logger.info(f"Metrics saved for user {user_id}")
                log_metrics_action(
                    user_id,
                    "save_all_metrics",
                    {"count": metrics_count, "metrics": filled_metrics}
                )
            except AttributeError:
                # Fallback: если save_metrics не существует, сохраняем по одной
                logger.warning("save_metrics not found, using fallback save_metric")
                metric_mapping = {
                    "sleep_hours": ("sleep", "hours"),
                    "sleep_quality": ("sleep", "quality"),
                    "sleep_awakenings": ("sleep", "awakenings"),
                    "energy_morning": ("energy", "morning"),
                    "energy_evening": ("energy", "evening"),
                    "stress_level": ("stress", None),
                    "steps": ("steps", None),
                    "hours_on_feet": ("hours_on_feet", None),
                    "workout_type": ("workout", "type"),
                    "workout_duration": ("workout", "duration"),
                    "workout_intensity": ("workout", "intensity"),
                }
                for key, value in metrics.items():
                    if value is not None:
                        mapping = metric_mapping.get(key)
                        if mapping:
                            mt, st = mapping
                            await self.metrics_repo.save_metric(
                                user_id, mt, value, st, today.isoformat()
                            )
                await query.answer("✅ Метрики сохранены!")
                log_metrics_action(
                    user_id,
                    "save_all_metrics_fallback",
                    {"count": metrics_count, "metrics": filled_metrics}
                )
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}", exc_info=True)
            log_metrics_action(
                user_id,
                "save_all_metrics_error",
                {"error": str(e)},
                status="error"
            )
            await query.answer(
                "⚠️ Ошибка при сохранении метрик. Попробуйте позже.",
                show_alert=True
            )
            if self._is_edit_mode(context):
                return await self._show_edit_menu(update, context)
            return await self._back_to_diary(update, context)

        self._clear_metrics(context)

        from handlers.start.handlers import show_diary
        await show_diary(update, context)

        return ConversationHandler.END

    # ================================================================
    # ОТМЕНА И ВОЗВРАТ
    # ================================================================

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отмена и возврат в дневник."""
        user_id = None
        try:
            user_id = await self.user_repo.get_user_id(update.effective_user.id)
        except Exception:
            pass

        query = update.callback_query
        if query:
            await query.answer()

        self._clear_metrics(context)

        if user_id:
            log_metrics_action(user_id, "cancel_metrics")

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def _back_to_diary(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат в дневник без сохранения."""
        user_id = None
        try:
            user_id = await self.user_repo.get_user_id(update.effective_user.id)
        except Exception:
            pass

        query = update.callback_query
        if query:
            await query.answer()

        self._clear_metrics(context)

        if user_id:
            log_metrics_action(user_id, "back_to_diary")

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================

def get_metrics_conversation_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для сбора метрик."""
    h = MetricsHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(h.show_metrics_menu, pattern=r"^metrics_show$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(
                    h.handle_main_menu,
                    pattern=r"^(metrics_today|metrics_edit|metrics_analytics|metrics_history|metrics_back_to_diary)$"
                ),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_EDIT_MENU: [
                CallbackQueryHandler(
                    h.handle_edit_actions,
                    pattern=r"^(edit_|metrics_back_to_menu|metrics_confirm_all)"
                ),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_ANALYTICS: [
                CallbackQueryHandler(
                    h.handle_analytics,
                    pattern=r"^(analytics_|metrics_back_to_menu)"
                ),
            ],

            # ИСПРАВЛЕНО: pattern без $ для кнопок sleep_6, sleep_7, etc.
            STATE_SLEEP_HOURS: [
                CallbackQueryHandler(h.process_sleep_hours, pattern=r"^sleep"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_sleep_hours),
            ],
            STATE_SLEEP_QUALITY: [
                CallbackQueryHandler(h.process_sleep_quality, pattern=r"^quality_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_SLEEP_AWAKENINGS: [
                CallbackQueryHandler(h.process_sleep_awakenings, pattern=r"^awakenings_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_ENERGY_MORNING: [
                CallbackQueryHandler(
                    h.process_energy_morning,
                    pattern=r"^(energy_morning_|edit_energy_morning_)"
                ),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_ENERGY_EVENING: [
                CallbackQueryHandler(
                    h.process_energy_evening,
                    pattern=r"^(energy_evening_|edit_energy_evening_)"
                ),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_STRESS: [
                CallbackQueryHandler(
                    h.process_stress,
                    pattern=r"^(stress_|edit_stress_)"
                ),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],

            # ИСПРАВЛЕНО: pattern без $ для кнопок steps_2000, etc.
            STATE_STEPS: [
                CallbackQueryHandler(h.process_steps, pattern=r"^steps"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_steps),
            ],

            # ИСПРАВЛЕНО: pattern без $ для кнопок feet_1, etc.
            STATE_HOURS_ON_FEET: [
                CallbackQueryHandler(h.process_hours_on_feet, pattern=r"^feet"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_hours_on_feet),
            ],
            STATE_WORKOUT_TYPE: [
                CallbackQueryHandler(h.process_workout_type, pattern=r"^workout_type_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],

            # ИСПРАВЛЕНО: добавлен MessageHandler + back_to_workout_type
            STATE_WORKOUT_DURATION: [
                CallbackQueryHandler(
                    h.process_workout_duration,
                    pattern=r"^(workout_duration_|duration_custom|back_to_workout_type)"
                ),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_workout_duration),
            ],
            STATE_WORKOUT_INTENSITY: [
                CallbackQueryHandler(h.process_workout_intensity, pattern=r"^intensity_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],

            # ИСПРАВЛЕНО: добавлена явная обработка metrics_cancel
            STATE_CONFIRM: [
                CallbackQueryHandler(h.confirm_and_save, pattern=r"^metrics_confirm_all$"),
                CallbackQueryHandler(h._show_edit_menu, pattern=r"^metrics_edit$"),
                CallbackQueryHandler(h.cancel, pattern=r"^metrics_back_to_diary$"),
                CallbackQueryHandler(h.cancel, pattern=r"^metrics_cancel$"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cancel, pattern=r"^metrics_cancel$"),
            CallbackQueryHandler(h._back_to_diary, pattern=r"^metrics_back_to_diary$"),
            MessageHandler(filters.COMMAND, h.cancel),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )