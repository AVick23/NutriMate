"""
Обработчики для сбора ежедневных метрик и аналитики.
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
        """Очищает все метрики."""
        context.user_data.pop("metrics_data", None)
        context.user_data.pop("session_mode", None)

    def _set_session_mode(self, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        """Устанавливает режим сессии (full/edit)."""
        context.user_data["session_mode"] = mode

    def _is_edit_mode(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверяет, в режиме ли редактирования."""
        return context.user_data.get("session_mode") == SESSION_EDIT

    async def _safe_edit_message(self, query, text: str, reply_markup=None) -> bool:
        """Безопасно редактирует сообщение, игнорируя ошибку 'Message is not modified'."""
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
            raise e
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

        # Проверяем, зарегистрирован ли пользователь
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
        return STATE_MAIN_MENU

    async def handle_main_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор из главного меню."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == CALLBACK_METRICS_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        if data == CALLBACK_METRICS_TODAY:
            self._clear_metrics(context)
            self._set_session_mode(context, SESSION_FULL)
            return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_EDIT:
            today = date.today()
            user_id = await self.user_repo.get_user_id(update.effective_user.id)
            existing = await self.metrics_repo.get_metrics(user_id, today)
            if existing:
                self._save_today_metrics(context, dict(existing))
                self._set_session_mode(context, SESSION_EDIT)
                return await self._show_edit_menu(update, context)
            else:
                await query.answer("Нет сохранённых метрик за сегодня", show_alert=True)
                return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_ANALYTICS:
            return await self._show_analytics_menu(update, context)

        if data == CALLBACK_METRICS_HISTORY:
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
            return await self._show_daily_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_WEEKLY:
            return await self._show_weekly_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_TRENDS:
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
            
            # Агрегируем данные
            aggregated = await aggregator.aggregate(user_id, yesterday)
            
            # Получаем профиль пользователя для расчёта TDEE
            profile = await self.user_repo.get_profile(user_id)
            base_tdee = profile["daily_kcal"] if profile else 2000
            
            # Рассчитываем скорректированный TDEE
            adjusted_tdee, modifiers, confidence = await modifier_engine.calculate_adjusted_tdee(
                user_id, base_tdee, aggregated
            )
            
            # Получаем инсайты
            insights = insight_gen.generate_insights(aggregated)
            
        except Exception as e:
            logger.error(f"Analytics error: {e}", exc_info=True)
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при расчёте аналитики. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS
        
        # Формируем текст аналитики
        text = f"📅 <b>Аналитика за {yesterday.strftime('%d.%m.%Y')}</b>\n\n"
        
        # Основные показатели
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
        
        # Метаболизм
        if aggregated.derived.eating_window_hours:
            text += f"⏰ Окно питания: {aggregated.derived.eating_window_hours:.0f} ч\n"
        
        text += "\n─────────────────\n"
        text += "⚡ <b>Метаболизм (TDEE)</b>\n"
        text += f"📊 Базовый: {base_tdee} ккал\n"
        text += f"🎯 Скорректированный: {adjusted_tdee} ккал\n"
        
        if confidence < 70:
            text += f"\n⚠️ <i>Точность анализа: {confidence}% (заполни больше метрик)</i>\n"
        
        # Инсайты
        if insights:
            text += "\n─────────────────\n"
            text += "💡 <b>Персональные инсайты</b>\n"
            for insight in insights[:3]:
                text += f"\n{insight.emoji} <b>{insight.title}</b>\n"
                text += f"   {insight.message[:100]}"
                if len(insight.message) > 100:
                    text += "..."
                text += "\n"
        
        # Если мало данных
        if aggregated.sleep.hours is None and aggregated.stress is None:
            text += "\n─────────────────\n"
            text += "📝 <i>Заполни больше метрик (сон, стресс, шаги),</i>\n"
            text += "<i>чтобы я мог давать более точные рекомендации!</i>\n"
        
        text += "\n─────────────────\n"
        text += "📊 <a href='https://t.me/nutrimate'>#NutriMate</a>"
        
        await self._safe_edit_message(query, text, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
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
            
        except Exception as e:
            logger.error(f"Weekly analytics error: {e}", exc_info=True)
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при формировании отчёта. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS
        
        # Заменяем длинные линии на короткие
        report = report.replace("━" * 30, "─────────────────")
        report = report.replace("━" * 25, "─────────────────")
        
        await self._safe_edit_message(query, report, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
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
            await self._safe_edit_message(
                query,
                "⚠️ Произошла ошибка при расчёте трендов. Попробуйте позже.",
                get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU)
            )
            return STATE_ANALYTICS
        
        # Формируем текст
        text = "📈 <b>Тренды за 30 дней</b>\n\n"
        
        text += "─────────────────\n"
        text += "📊 <b>Динамика измерений</b>\n"
        
        # Вес
        weights = [agg.measurements.weight_kg for agg in aggregates if agg.measurements.weight_kg]
        if len(weights) >= 2:
            first_weight = weights[0]
            last_weight = weights[-1]
            change = last_weight - first_weight
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            text += f"⚖️ Вес: {first_weight:.1f} → {last_weight:.1f} кг ({direction} {abs(change):.1f} кг)\n"
        
        # Талия
        waists = [agg.measurements.waist_cm for agg in aggregates if agg.measurements.waist_cm]
        if len(waists) >= 2:
            first_waist = waists[0]
            last_waist = waists[-1]
            change = last_waist - first_waist
            direction = "📉" if change < 0 else "📈" if change > 0 else "➡️"
            text += f"📏 Талия: {first_waist:.1f} → {last_waist:.1f} см ({direction} {abs(change):.1f} см)\n"
        
        # Средние значения
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
        
        # Обнаруженные состояния
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
        text += "📊 <a href='https://t.me/nutrimate'>#NutriMate</a>"
        
        await self._safe_edit_message(query, text, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        return STATE_ANALYTICS

    # ================================================================
    # ОБРАБОТКА РЕДАКТИРОВАНИЯ
    # ================================================================

    async def handle_edit_actions(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор параметра для редактирования."""
        query = update.callback_query
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

        return STATE_MAIN_MENU

    async def _edit_sleep(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Редактирование сна."""
        query = update.callback_query
        text = (
            f"{EMOJI_SLEEP} <b>Редактирование сна</b>\n\n"
            "Сколько часов ты спал?"
        )
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
    # ПОШАГОВЫЙ СБОР МЕТРИК (ПОЛНЫЙ)
    # ================================================================

    async def _start_sleep_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает опрос с вопроса о сне."""
        query = update.callback_query
        if query:
            await query.answer()

        text = (
            f"{EMOJI_SLEEP} <b>Сколько часов ты спал?</b>\n\n"
            "Выбери из вариантов или введи своё значение."
        )

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

            if data == "sleep_custom":
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество часов (например: 7.5 или 8):"
                )
                return STATE_SLEEP_HOURS

            if data.startswith("sleep_"):
                try:
                    hours = float(data.replace("sleep_", ""))
                    self._update_metric(context, "sleep_hours", hours)
                    return await self._ask_sleep_quality(update, context)
                except ValueError:
                    await self._send_error_message(update, "❌ Ошибка: неверное значение.")
                    return STATE_SLEEP_HOURS

        elif update.message:
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if hours < 0 or hours > 24:
                    raise ValueError
                self._update_metric(context, "sleep_hours", hours)
                return await self._ask_sleep_quality(update, context)
            except ValueError:
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
            quality = int(data.replace("quality_", ""))
            self._update_metric(context, "sleep_quality", quality)
            return await self._ask_sleep_awakenings(update, context)

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
            awakenings = int(data.replace("awakenings_", ""))
            self._update_metric(context, "sleep_awakenings", awakenings)
            return await self._ask_energy_morning(update, context)

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

            if data.startswith("edit_energy_morning_"):
                value = int(data.replace("edit_energy_morning_", ""))
                self._update_metric(context, "energy_morning", value)
                # Режим редактирования — возвращаемся в меню
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_energy_evening(update, context)

            elif data.startswith("energy_morning_"):
                value = int(data.replace("energy_morning_", ""))
                self._update_metric(context, "energy_morning", value)
                return await self._ask_energy_evening(update, context)

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

            if data.startswith("edit_energy_evening_"):
                value = int(data.replace("edit_energy_evening_", ""))
                self._update_metric(context, "energy_evening", value)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_stress(update, context)

            elif data.startswith("energy_evening_"):
                value = int(data.replace("energy_evening_", ""))
                self._update_metric(context, "energy_evening", value)
                return await self._ask_stress(update, context)

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

            if data.startswith("edit_stress_"):
                value = int(data.replace("edit_stress_", ""))
                self._update_metric(context, "stress_level", value)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_steps(update, context)

            elif data.startswith("stress_"):
                value = int(data.replace("stress_", ""))
                self._update_metric(context, "stress_level", value)
                return await self._ask_steps(update, context)

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
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество шагов (например: 8500):"
                )
                return STATE_STEPS

            if data.startswith("steps_"):
                steps = int(data.replace("steps_", ""))
                self._update_metric(context, "steps", steps)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_hours_on_feet(update, context)

        elif update.message:
            try:
                steps = int(update.message.text.strip())
                if steps < 0 or steps > 50000:
                    raise ValueError
                self._update_metric(context, "steps", steps)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_hours_on_feet(update, context)
            except ValueError:
                await update.message.reply_text(
                    "❌ Введи число от 0 до 50000.",
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
                await self._safe_edit_message(
                    query,
                    "✏️ Введи количество часов (например: 4.5):"
                )
                return STATE_HOURS_ON_FEET

            if data.startswith("feet_"):
                hours = float(data.replace("feet_", ""))
                self._update_metric(context, "hours_on_feet", hours)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_workout_type(update, context)

        elif update.message:
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if hours < 0 or hours > 24:
                    raise ValueError
                self._update_metric(context, "hours_on_feet", hours)
                if self._is_edit_mode(context):
                    return await self._show_edit_menu(update, context)
                return await self._ask_workout_type(update, context)
            except ValueError:
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

            if workout_type == "none":
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

            if data == "duration_custom":
                await self._safe_edit_message(
                    query,
                    "✏️ Введи длительность в минутах (например: 45):"
                )
                return STATE_WORKOUT_DURATION

            if data.startswith("workout_duration_"):
                duration = int(data.replace("workout_duration_", ""))
                self._update_metric(context, "workout_duration", duration)
                return await self._ask_workout_intensity(update, context)

        elif update.message:
            try:
                duration = int(update.message.text.strip())
                if duration <= 0 or duration > 480:
                    raise ValueError
                self._update_metric(context, "workout_duration", duration)
                return await self._ask_workout_intensity(update, context)
            except ValueError:
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
        if data.startswith("intensity_"):
            intensity = int(data.replace("intensity_", ""))
            self._update_metric(context, "workout_intensity", intensity)
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
        return STATE_MAIN_MENU

    async def confirm_and_save(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет метрики в БД и завершает."""
        query = update.callback_query
        await query.answer("✅ Метрики сохранены!")

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        metrics = self._get_today_metrics(context)

        try:
            today = date.today()
            await self.metrics_repo.save_metrics(user_id, today, metrics)
            logger.info(f"Metrics saved for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}", exc_info=True)
            await self._send_error_message(update, "⚠️ Ошибка при сохранении метрик. Попробуйте позже.")
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
        query = update.callback_query
        if query:
            await query.answer()
        self._clear_metrics(context)

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def _back_to_diary(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возврат в дневник без сохранения."""
        query = update.callback_query
        if query:
            await query.answer()
        self._clear_metrics(context)

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
            CallbackQueryHandler(h.show_metrics_menu, pattern=f"^{CALLBACK_METRICS_SHOW}$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(h.handle_main_menu, pattern=f"^({CALLBACK_METRICS_TODAY}|{CALLBACK_METRICS_EDIT}|{CALLBACK_METRICS_ANALYTICS}|{CALLBACK_METRICS_HISTORY}|{CALLBACK_METRICS_BACK_TO_DIARY})$"),
                CallbackQueryHandler(h.handle_edit_actions, pattern=f"^(edit_|{CALLBACK_METRICS_BACK_TO_MENU}|{CALLBACK_CONFIRM_ALL})$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_ANALYTICS: [
                CallbackQueryHandler(h.handle_analytics, pattern=f"^({CALLBACK_ANALYTICS_DAILY}|{CALLBACK_ANALYTICS_WEEKLY}|{CALLBACK_ANALYTICS_TRENDS}|{CALLBACK_METRICS_BACK_TO_MENU})$"),
            ],
            STATE_SLEEP_HOURS: [
                CallbackQueryHandler(h.process_sleep_hours, pattern="^(sleep_|sleep_custom)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_sleep_hours),
            ],
            STATE_SLEEP_QUALITY: [
                CallbackQueryHandler(h.process_sleep_quality, pattern="^quality_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_SLEEP_AWAKENINGS: [
                CallbackQueryHandler(h.process_sleep_awakenings, pattern="^awakenings_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_ENERGY_MORNING: [
                CallbackQueryHandler(h.process_energy_morning, pattern="^(energy_morning_|edit_energy_morning_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_ENERGY_EVENING: [
                CallbackQueryHandler(h.process_energy_evening, pattern="^(energy_evening_|edit_energy_evening_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_STRESS: [
                CallbackQueryHandler(h.process_stress, pattern="^(stress_|edit_stress_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_STEPS: [
                CallbackQueryHandler(h.process_steps, pattern="^(steps_|steps_custom)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_steps),
            ],
            STATE_HOURS_ON_FEET: [
                CallbackQueryHandler(h.process_hours_on_feet, pattern="^(feet_|feet_custom)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_hours_on_feet),
            ],
            STATE_WORKOUT_TYPE: [
                CallbackQueryHandler(h.process_workout_type, pattern="^workout_type_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_WORKOUT_DURATION: [
                CallbackQueryHandler(h.process_workout_duration, pattern="^(workout_duration_|duration_custom)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_workout_duration),
            ],
            STATE_WORKOUT_INTENSITY: [
                CallbackQueryHandler(h.process_workout_intensity, pattern="^intensity_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(h.confirm_and_save, pattern=f"^{CALLBACK_CONFIRM_ALL}$"),
                CallbackQueryHandler(h._show_edit_menu, pattern=f"^{CALLBACK_METRICS_EDIT}$"),
                CallbackQueryHandler(h.cancel, pattern=f"^{CALLBACK_METRICS_BACK_TO_DIARY}$"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=f"^{CALLBACK_BACK_TO_EDIT}$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=f"^{CALLBACK_BACK_TO_MAIN}$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cancel, pattern=f"^{CALLBACK_CANCEL}$"),
            CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_METRICS_BACK_TO_DIARY}$"),
            MessageHandler(filters.COMMAND, h.cancel),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )