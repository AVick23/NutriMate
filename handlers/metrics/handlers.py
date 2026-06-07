"""
Обработчики для сбора ежедневных метрик и расширенной аналитики.
ИСПРАВЛЕНО: Полный флоу ввода, редактирование, типы данных и регистрация состояний.
"""
import logging
from datetime import date, timedelta
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest

from db import Database, UserRepository
from db.repositories import DailyMetricsRepository
from analytics import DailyAggregator, WeeklyReportGenerator, StateDetector, PatternDetector

from .constants import *
from .keyboards import *
from .utils import get_default_metrics, format_metrics_summary, split_long_message

logger = logging.getLogger(__name__)

class MetricsHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.metrics_repo = DailyMetricsRepository(db)

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================
    def _get_today_metrics(self, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        return context.user_data.get("metrics_data", get_default_metrics())

    def _save_today_metrics(self, context: ContextTypes.DEFAULT_TYPE, metrics: Dict[str, Any]) -> None:
        context.user_data["metrics_data"] = metrics

    def _update_metric(self, context: ContextTypes.DEFAULT_TYPE, key: str, value: Any) -> None:
        metrics = self._get_today_metrics(context)
        metrics[key] = value
        self._save_today_metrics(context, metrics)

    def _clear_metrics(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.pop("metrics_data", None)
        context.user_data.pop("session_mode", None)
        context.user_data.pop("awaiting_custom", None)

    def _set_session_mode(self, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        context.user_data["session_mode"] = mode

    def _is_edit_mode(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        return context.user_data.get("session_mode") == SESSION_EDIT

    async def _safe_edit_message(self, query, text: str, reply_markup=None) -> bool:
        if not query: return False
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
            return True
        except BadRequest as e:
            if "Message is not modified" in str(e): return False
            return False
        except Exception:
            return False

    async def _send_error_message(self, update: Update, text: str) -> None:
        try:
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text, parse_mode="HTML")
        except Exception: pass

    # ============================================================
    # ВХОДНАЯ ТОЧКА
    # ============================================================
    async def show_metrics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        if not user_id:
            text = "❌ Сначала нужно пройти регистрацию. Отправь команду /start"
            if query: await self._safe_edit_message(query, text)
            else: await update.message.reply_text(text, parse_mode="HTML")
            return ConversationHandler.END

        text = "📊 <b>Мои метрики</b>\n\nЗдесь я собираю данные о твоём состоянии:\n• Сон, энергия, стресс\n• Шаги и активность\n• Тренировки\n\nЧем больше данных — тем точнее мои рекомендации! 🧠"
        if query: await self._safe_edit_message(query, text, get_metrics_main_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_metrics_main_keyboard(), parse_mode="HTML")
        return STATE_MAIN_MENU

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = await self.user_repo.get_user_id(update.effective_user.id)

        if data == CALLBACK_METRICS_BACK_TO_DIARY:
            return await self._back_to_diary(update, context)

        if data == CALLBACK_METRICS_TODAY:
            today = date.today()
            try:
                existing = await self.metrics_repo.get_metrics(user_id, today)
                if existing and any(v is not None for v in existing.values()):
                    await query.answer("⚠️ Метрики за сегодня уже заполнены. Используй 'Редактировать'.", show_alert=True)
                    return STATE_MAIN_MENU
            except Exception: pass
            self._clear_metrics(context)
            self._set_session_mode(context, SESSION_FULL)
            return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_EDIT:
            today = date.today()
            try:
                existing = await self.metrics_repo.get_metrics(user_id, today)
            except Exception: existing = None

            if existing and any(v is not None for v in existing.values()):
                self._save_today_metrics(context, dict(existing))
                self._set_session_mode(context, SESSION_EDIT)
                return await self._show_edit_menu(update, context)
            else:
                await query.answer("Нет сохранённых метрик за сегодня", show_alert=True)
                self._set_session_mode(context, SESSION_FULL)
                return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_ANALYTICS:
            return await self._show_analytics_menu(update, context)

        if data == CALLBACK_METRICS_HISTORY:
            await query.answer("🚧 История метрик в разработке", show_alert=True)
            return STATE_MAIN_MENU

        return STATE_MAIN_MENU

    # ============================================================
    # АНАЛИТИКА
    # ============================================================
    async def _show_analytics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        text = "📊 <b>Аналитика</b>\n\nВыбери раздел для детального анализа:"
        if query: await self._safe_edit_message(query, text, get_analytics_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_analytics_keyboard(), parse_mode="HTML")
        return STATE_ANALYTICS

    async def handle_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = await self.user_repo.get_user_id(update.effective_user.id)

        if data == CALLBACK_ANALYTICS_DAILY:
            return await self._show_daily_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_WEEKLY:
            return await self._show_weekly_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_TRENDS:
            return await self._show_trends_analytics(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_PATTERNS:
            return await self._show_patterns(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_FORECAST:
            return await self._show_forecast(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_BEST_DAY:
            return await self._show_best_day(update, context, user_id)
        elif data == CALLBACK_ANALYTICS_STATES:
            return await self._show_states(update, context, user_id)
        elif data == CALLBACK_METRICS_BACK_TO_MENU:
            return await self.show_metrics_menu(update, context)

        return STATE_ANALYTICS

    async def _show_daily_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        query = update.callback_query
        yesterday = date.today() - timedelta(days=1)
        try:
            aggregator = DailyAggregator(self.db)
            aggregated = await aggregator.aggregate(user_id, yesterday)
            text = f"📅 <b>Аналитика за {yesterday.strftime('%d.%m.%Y')}</b>\n\n"
            text += f"😴 Сон: {aggregated.sleep.hours or 'N/A'} ч\n"
            text += f"⚡ Энергия: {aggregated.derived.avg_energy or 'N/A'}/10\n"
            text += f"👣 Шаги: {aggregated.activity.steps or 'N/A'}\n"
            text += f"😰 Стресс: {aggregated.stress or 'N/A'}/10\n"
            await self._safe_edit_message(query, text, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        except Exception as e:
            logger.error(f"Daily analytics error: {e}")
            await self._safe_edit_message(query, "⚠️ Ошибка расчёта аналитики.", get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        return STATE_ANALYTICS

    async def _show_weekly_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        query = update.callback_query
        try:
            profile = await self.user_repo.get_profile(user_id) or {}
            report_gen = WeeklyReportGenerator(self.db)
            # 🛠 ИСПРАВЛЕНО: Ожидаем строку (str), а не ReportResult
            report_text: str = await report_gen.generate_report(user_id, profile)
        except Exception as e:
            logger.error(f"Weekly analytics error: {e}")
            await self._safe_edit_message(query, "⚠️ Ошибка формирования отчёта.", get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
            return STATE_ANALYTICS

        parts = split_long_message(report_text, 4000)
        for i, part in enumerate(parts):
            if i == 0: 
                await self._safe_edit_message(query, part, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
            else: 
                await query.message.reply_text(part, parse_mode="HTML")
        return STATE_ANALYTICS

    async def _show_trends_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        await update.callback_query.answer("🚧 Тренды в разработке", show_alert=True)
        return STATE_ANALYTICS

    async def _show_patterns(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        query = update.callback_query
        try:
            aggregator = DailyAggregator(self.db)
            pattern_detector = PatternDetector(self.db)
            end_date = date.today() - timedelta(days=1)
            aggregates = [await aggregator.aggregate(user_id, end_date - timedelta(days=i)) for i in range(30)]
            patterns = await pattern_detector.detect_patterns(user_id, aggregates)
            
            text = "🔍 <b>Твои уникальные паттерны</b>\n\n"
            if not patterns:
                text += "Пока недостаточно данных (нужно минимум 14 дней)."
            else:
                for p in patterns[:5]:
                    text += f"• {p.effect_text} (уверенность: {int((1-p.p_value)*100)}%)\n"
            
            await self._safe_edit_message(query, text, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        except Exception as e:
            logger.error(f"Patterns error: {e}")
            await self._safe_edit_message(query, "⚠️ Ошибка анализа паттернов.", get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        return STATE_ANALYTICS

    async def _show_forecast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        await update.callback_query.answer("🚧 Прогноз в разработке", show_alert=True)
        return STATE_ANALYTICS

    async def _show_best_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        await update.callback_query.answer("🚧 Лучший день в разработке", show_alert=True)
        return STATE_ANALYTICS

    async def _show_states(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
        query = update.callback_query
        try:
            aggregator = DailyAggregator(self.db)
            state_detector = StateDetector()
            end_date = date.today() - timedelta(days=1)
            aggregates = [await aggregator.aggregate(user_id, end_date - timedelta(days=i)) for i in range(14)]
            profile = await self.user_repo.get_profile(user_id) or {}
            states = state_detector.detect_states(aggregates, profile)
            
            text = "🧬 <b>Физиологические состояния</b>\n\n"
            active = [s for s in states if s.detected]
            if not active:
                text += "✅ Все показатели в норме. Продолжай в том же духе! 💪"
            else:
                for s in active:
                    text += f"{s.emoji} <b>{s.state_type}</b>\n   {s.recommendation}\n\n"
            
            await self._safe_edit_message(query, text, get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        except Exception as e:
            logger.error(f"States error: {e}")
            await self._safe_edit_message(query, "⚠️ Ошибка анализа состояний.", get_back_keyboard(CALLBACK_METRICS_BACK_TO_MENU))
        return STATE_ANALYTICS

    # ============================================================
    # ПОШАГОВЫЙ СБОР МЕТРИК (ИСПРАВЛЕННЫЙ ПОЛНЫЙ ФЛОУ)
    # ============================================================
    async def _start_sleep_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        text = f"{EMOJI_SLEEP} <b>Сколько часов ты спал?</b>\n\nВыбери из вариантов или введи своё значение."
        if query: await self._safe_edit_message(query, text, get_sleep_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_sleep_keyboard(), parse_mode="HTML")
        return STATE_SLEEP_HOURS

    async def process_sleep_hours(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data == "sleep_custom":
                context.user_data["awaiting_custom"] = "sleep_hours"
                await self._safe_edit_message(query, "✏️ Введи количество часов (например: 7.5): ")
                return STATE_SLEEP_HOURS
            if data.startswith("sleep_"):
                try:
                    hours = float(data.replace("sleep_", ""))
                    if 0 <= hours <= 24:
                        self._update_metric(context, "sleep_hours", hours)
                        context.user_data.pop("awaiting_custom", None)
                        return await self._ask_sleep_quality(update, context)
                except ValueError: pass
        elif update.message and context.user_data.get("awaiting_custom") == "sleep_hours":
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if 0 <= hours <= 24:
                    self._update_metric(context, "sleep_hours", hours)
                    context.user_data.pop("awaiting_custom", None)
                    return await self._ask_sleep_quality(update, context)
            except ValueError: pass
            
        await self._send_error_message(update, "❌ Введи число от 0 до 24.")
        return STATE_SLEEP_HOURS

    async def _ask_sleep_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        text = f"{EMOJI_SLEEP} <b>Оцени качество сна</b> (1-5):"
        if query: await self._safe_edit_message(query, text, get_sleep_quality_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_sleep_quality_keyboard(), parse_mode="HTML")
        return STATE_SLEEP_QUALITY

    async def process_sleep_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("quality_"):
            try:
                q = int(query.data.replace("quality_", ""))
                if 1 <= q <= 5:
                    self._update_metric(context, "sleep_quality", q)
                    return await self._ask_sleep_awakenings(update, context)
            except ValueError: pass
        return STATE_SLEEP_QUALITY

    async def _ask_sleep_awakenings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        text = f"{EMOJI_SLEEP} <b>Сколько раз просыпался?</b>"
        if query: await self._safe_edit_message(query, text, get_awakenings_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_awakenings_keyboard(), parse_mode="HTML")
        return STATE_SLEEP_AWAKENINGS

    async def process_sleep_awakenings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("awakenings_"):
            try:
                a = int(query.data.replace("awakenings_", ""))
                self._update_metric(context, "sleep_awakenings", a)
                return await self._ask_energy_morning(update, context)
            except ValueError: pass
        return STATE_SLEEP_AWAKENINGS

    async def _ask_energy_morning(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        prefix = "edit_energy_morning" if self._is_edit_mode(context) else "energy_morning"
        text = f"{EMOJI_ENERGY} <b>Энергия утром</b> (1-10):"
        if query: await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else: await update.message.reply_text(text, reply_markup=get_energy_stress_keyboard(prefix), parse_mode="HTML")
        return STATE_ENERGY_MORNING

    async def process_energy_morning(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data.startswith(("energy_morning_", "edit_energy_morning_")):
                try:
                    v = int(data.split("_")[-1])
                    if 1 <= v <= 10:
                        self._update_metric(context, "energy_morning", v)
                        if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                        return await self._ask_energy_evening(update, context)
                except ValueError: pass
        return STATE_ENERGY_MORNING

    async def _ask_energy_evening(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        prefix = "edit_energy_evening" if self._is_edit_mode(context) else "energy_evening"
        text = f"{EMOJI_ENERGY} <b>Энергия вечером</b> (1-10):"
        if query: await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else: await update.message.reply_text(text, reply_markup=get_energy_stress_keyboard(prefix), parse_mode="HTML")
        return STATE_ENERGY_EVENING

    async def process_energy_evening(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data.startswith(("energy_evening_", "edit_energy_evening_")):
                try:
                    v = int(data.split("_")[-1])
                    if 1 <= v <= 10:
                        self._update_metric(context, "energy_evening", v)
                        if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                        return await self._ask_stress(update, context)
                except ValueError: pass
        return STATE_ENERGY_EVENING

    async def _ask_stress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        prefix = "edit_stress" if self._is_edit_mode(context) else "stress"
        text = f"{EMOJI_STRESS} <b>Уровень стресса</b> (1-10):"
        if query: await self._safe_edit_message(query, text, get_energy_stress_keyboard(prefix))
        else: await update.message.reply_text(text, reply_markup=get_energy_stress_keyboard(prefix), parse_mode="HTML")
        return STATE_STRESS

    async def process_stress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data.startswith(("stress_", "edit_stress_")):
                try:
                    v = int(data.split("_")[-1])
                    if 1 <= v <= 10:
                        self._update_metric(context, "stress_level", v)
                        if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                        return await self._ask_steps(update, context)
                except ValueError: pass
        return STATE_STRESS

    async def _ask_steps(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        text = f"{EMOJI_STEPS} <b>Сколько шагов?</b>"
        if query: await self._safe_edit_message(query, text, get_steps_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_steps_keyboard(), parse_mode="HTML")
        return STATE_STEPS

    async def process_steps(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data == "steps_custom":
                context.user_data["awaiting_custom"] = "steps"
                await self._safe_edit_message(query, "✏️ Введи шаги (например: 8500): ")
                return STATE_STEPS
            if data.startswith("steps_"):
                try:
                    s = int(data.replace("steps_", ""))
                    if 0 <= s <= 100000:
                        self._update_metric(context, "steps", s)
                        context.user_data.pop("awaiting_custom", None)
                        # 🛠 ИСПРАВЛЕНО: Переходим к часам на ногах, а не к подтверждению
                        if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                        return await self._ask_hours_on_feet(update, context)
                except ValueError: pass
        elif update.message and context.user_data.get("awaiting_custom") == "steps":
            try:
                s = int(update.message.text.strip())
                if 0 <= s <= 100000:
                    self._update_metric(context, "steps", s)
                    context.user_data.pop("awaiting_custom", None)
                    if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                    return await self._ask_hours_on_feet(update, context)
            except ValueError: pass
            
        await self._send_error_message(update, "❌ Введи число от 0 до 100000.")
        return STATE_STEPS

    # 🛠 НОВЫЕ МЕТОДЫ ДЛЯ ПОЛНОГО ФЛОУ
    async def _ask_hours_on_feet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        text = f"{EMOJI_STEPS} <b>Сколько часов ты провел на ногах?</b>\n\nЭто важно для точного расчета NEAT."
        if query: await self._safe_edit_message(query, text, get_hours_on_feet_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_hours_on_feet_keyboard(), parse_mode="HTML")
        return STATE_HOURS_ON_FEET

    async def process_hours_on_feet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data == "feet_custom":
                context.user_data["awaiting_custom"] = "hours_on_feet"
                await self._safe_edit_message(query, "✏️ Введи число часов (например: 4.5): ")
                return STATE_HOURS_ON_FEET
            if data.startswith("feet_"):
                val = data.replace("feet_", "")
                mapping = {"1": 1.5, "3": 3.5, "5": 5.5, "7": 7.5, "9": 9.5}
                if val in mapping:
                    self._update_metric(context, "hours_on_feet", mapping[val])
                    context.user_data.pop("awaiting_custom", None)
                    if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                    return await self._ask_workout_type(update, context)
        elif update.message and context.user_data.get("awaiting_custom") == "hours_on_feet":
            try:
                h = float(update.message.text.strip().replace(",", "."))
                if 0 <= h <= 24:
                    self._update_metric(context, "hours_on_feet", h)
                    context.user_data.pop("awaiting_custom", None)
                    if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                    return await self._ask_workout_type(update, context)
            except ValueError: pass
            
        await self._send_error_message(update, "❌ Введи число от 0 до 24.")
        return STATE_HOURS_ON_FEET

    async def _ask_workout_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        text = f"{EMOJI_WORKOUT} <b>Была ли сегодня тренировка?</b>"
        if query: await self._safe_edit_message(query, text, get_workout_type_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_workout_type_keyboard(), parse_mode="HTML")
        return STATE_WORKOUT_TYPE

    async def process_workout_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("workout_type_"):
            w_type = query.data.replace("workout_type_", "")
            self._update_metric(context, "workout_type", w_type)
            if w_type == "none":
                self._update_metric(context, "workout_duration", None)
                self._update_metric(context, "workout_intensity", None)
                if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
                return await self._show_confirm(update, context)
            return await self._ask_workout_duration(update, context)
        return STATE_WORKOUT_TYPE

    async def _ask_workout_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        text = f"{EMOJI_WORKOUT} <b>Сколько минут длилась тренировка?</b>"
        if query: await self._safe_edit_message(query, text, get_workout_duration_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_workout_duration_keyboard(), parse_mode="HTML")
        return STATE_WORKOUT_DURATION

    async def process_workout_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            if data == "duration_custom":
                context.user_data["awaiting_custom"] = "workout_duration"
                await self._safe_edit_message(query, "✏️ Введи длительность в минутах (например: 45): ")
                return STATE_WORKOUT_DURATION
            if data == CALLBACK_BACK_TO_WORKOUT_TYPE:
                return await self._ask_workout_type(update, context)
            if data.startswith("workout_duration_"):
                try:
                    d = int(data.replace("workout_duration_", ""))
                    if 0 < d <= 480:
                        self._update_metric(context, "workout_duration", d)
                        context.user_data.pop("awaiting_custom", None)
                        return await self._ask_workout_intensity(update, context)
                except ValueError: pass
        elif update.message and context.user_data.get("awaiting_custom") == "workout_duration":
            try:
                d = int(update.message.text.strip())
                if 0 < d <= 480:
                    self._update_metric(context, "workout_duration", d)
                    context.user_data.pop("awaiting_custom", None)
                    return await self._ask_workout_intensity(update, context)
            except ValueError: pass
            
        await self._send_error_message(update, "❌ Введи число от 1 до 480.")
        return STATE_WORKOUT_DURATION

    async def _ask_workout_intensity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        text = f"{EMOJI_WORKOUT} <b>Оцени интенсивность тренировки</b> (RPE 1-10):"
        if query: await self._safe_edit_message(query, text, get_workout_intensity_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_workout_intensity_keyboard(), parse_mode="HTML")
        return STATE_WORKOUT_INTENSITY

    async def process_workout_intensity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("intensity_"):
            val = query.data.replace("intensity_", "")
            intensity_map = {"1": 1.5, "3": 3.5, "5": 5.5, "7": 7.5, "9": 9.5}
            self._update_metric(context, "workout_intensity", intensity_map.get(val, 5))
            if self._is_edit_mode(context): return await self._show_edit_menu(update, context)
            return await self._show_confirm(update, context)
        return STATE_WORKOUT_INTENSITY

    # ============================================================
    # РЕДАКТИРОВАНИЕ И ПОДТВЕРЖДЕНИЕ
    # ============================================================
    async def _show_edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        metrics = self._get_today_metrics(context)
        text = f"✏️ <b>Редактирование метрик</b>\n\n{format_metrics_summary(metrics)}\n\nЧто хочешь изменить?"
        if query: await self._safe_edit_message(query, text, get_edit_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_edit_keyboard(), parse_mode="HTML")
        return STATE_EDIT_MENU

    async def _show_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query: await query.answer()
        metrics = self._get_today_metrics(context)
        text = f"📊 <b>Твои метрики за сегодня</b>\n\n{format_metrics_summary(metrics)}\n\nВсё верно?"
        if query: await self._safe_edit_message(query, text, get_confirm_keyboard())
        else: await update.message.reply_text(text, reply_markup=get_confirm_keyboard(), parse_mode="HTML")
        return STATE_CONFIRM

    async def confirm_and_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        user_id = await self.user_repo.get_user_id(update.effective_user.id)
        metrics = self._get_today_metrics(context)

        try:
            await self.metrics_repo.save_metrics(user_id, date.today(), metrics)
            await query.answer("✅ Метрики сохранены!")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            await query.answer("⚠️ Ошибка при сохранении.", show_alert=True)
            return STATE_EDIT_MENU if self._is_edit_mode(context) else STATE_MAIN_MENU

        self._clear_metrics(context)
        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def back_to_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        self._clear_metrics(context)
        return await self.show_metrics_menu(update, context)

    async def back_to_edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self._show_edit_menu(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        self._clear_metrics(context)
        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.cancel(update, context)


# ============================================================
# РЕГИСТРАЦИЯ ConversationHandler (ИСПРАВЛЕННАЯ)
# ============================================================
def get_metrics_conversation_handler(db: Database) -> ConversationHandler:
    h = MetricsHandlers(db)
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(h.show_metrics_menu, pattern=r"^metrics_show$")],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(h.handle_main_menu, pattern=r"^(metrics_today|metrics_edit|metrics_analytics|metrics_history|metrics_back_to_diary)$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_EDIT_MENU: [
                # 🛠 ИСПРАВЛЕНО: Добавлены обработчики для кнопок редактирования
                CallbackQueryHandler(h._start_sleep_input, pattern=r"^edit_sleep$"),
                CallbackQueryHandler(h._ask_energy_morning, pattern=r"^edit_energy_morning$"),
                CallbackQueryHandler(h._ask_energy_evening, pattern=r"^edit_energy_evening$"),
                CallbackQueryHandler(h._ask_stress, pattern=r"^edit_stress$"),
                CallbackQueryHandler(h._ask_steps, pattern=r"^edit_steps$"),
                CallbackQueryHandler(h._ask_workout_type, pattern=r"^edit_workout$"),
                CallbackQueryHandler(h.confirm_and_save, pattern=r"^metrics_confirm_all$"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
            ],
            STATE_ANALYTICS: [
                CallbackQueryHandler(h.handle_analytics, pattern=r"^(analytics_|metrics_back_to_menu|back_to_analytics)"),
            ],
            STATE_SLEEP_HOURS: [
                CallbackQueryHandler(h.process_sleep_hours, pattern=r"^sleep"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                CallbackQueryHandler(h.back_to_main_menu, pattern=r"^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_sleep_hours),
            ],
            STATE_SLEEP_QUALITY: [
                CallbackQueryHandler(h.process_sleep_quality, pattern=r"^quality_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_SLEEP_AWAKENINGS: [
                CallbackQueryHandler(h.process_sleep_awakenings, pattern=r"^awakenings_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_ENERGY_MORNING: [
                CallbackQueryHandler(h.process_energy_morning, pattern=r"^(energy_morning_|edit_energy_morning_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_ENERGY_EVENING: [
                CallbackQueryHandler(h.process_energy_evening, pattern=r"^(energy_evening_|edit_energy_evening_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_STRESS: [
                CallbackQueryHandler(h.process_stress, pattern=r"^(stress_|edit_stress_)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_STEPS: [
                CallbackQueryHandler(h.process_steps, pattern=r"^steps"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_steps),
            ],
            # 🛠 ИСПРАВЛЕНО: Зарегистрированы ранее отсутствующие состояния
            STATE_HOURS_ON_FEET: [
                CallbackQueryHandler(h.process_hours_on_feet, pattern=r"^feet"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_hours_on_feet),
            ],
            STATE_WORKOUT_TYPE: [
                CallbackQueryHandler(h.process_workout_type, pattern=r"^workout_type_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_WORKOUT_DURATION: [
                CallbackQueryHandler(h.process_workout_duration, pattern=r"^(workout_duration_|duration_custom|back_to_workout_type)"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_workout_duration),
            ],
            STATE_WORKOUT_INTENSITY: [
                CallbackQueryHandler(h.process_workout_intensity, pattern=r"^intensity_"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(h.confirm_and_save, pattern=r"^metrics_confirm_all$"),
                CallbackQueryHandler(h._show_edit_menu, pattern=r"^metrics_edit$"),
                CallbackQueryHandler(h.cancel, pattern=r"^(metrics_cancel|metrics_back_to_diary)$"),
                CallbackQueryHandler(h.back_to_edit_menu, pattern=r"^back_to_edit$"),
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