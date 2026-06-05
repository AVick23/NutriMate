"""
Обработчики для сбора ежедневных метрик.
"""
import logging
from datetime import date
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from db import Database, UserRepository, DailyMetricsRepository
from .constants import *
from .keyboards import *
from .utils import format_metrics_summary, get_default_metrics, get_session_type_by_hour

logger = logging.getLogger(__name__)


class MetricsHandlers:
    """Обработчики для сбора метрик."""

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
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
            return False

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
            "• Тренировки\n"
            "• Голод, пищеварение, цикл\n\n"
            "Чем больше данных — тем точнее мои рекомендации по питанию и образу жизни! 🧠"
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
            # Начинаем заполнение за сегодня
            self._clear_metrics(context)
            return await self._start_sleep_input(update, context)

        if data == CALLBACK_METRICS_EDIT:
            # Показываем уже сохранённые метрики для редактирования
            today = date.today()
            user_id = await self.user_repo.get_user_id(update.effective_user.id)
            existing = await self.metrics_repo.get_metrics(user_id, today)
            if existing:
                self._save_today_metrics(context, dict(existing))
                return await self._show_edit_menu(update, context)
            else:
                await query.answer("Нет сохранённых метрик за сегодня", show_alert=True)
                return await self._start_sleep_input(update, context)

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
    # ПОШАГОВЫЙ СБОР МЕТРИК
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
                hours = float(data.replace("sleep_", ""))
                self._update_metric(context, "sleep_hours", hours)
                return await self._ask_sleep_quality(update, context)

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

        text = f"{EMOJI_ENERGY} <b>Как чувствуешь себя сейчас?</b>\n\nОцени энергию от 1 до 10:"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard("energy_morning"))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard("energy_morning"),
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
                value = int(data.replace("energy_morning_", ""))
                self._update_metric(context, "energy_morning", value)

                # Если вечерняя сессия — спрашиваем стресс, иначе — завершаем
                session_type = get_session_type_by_hour()
                if session_type == "evening":
                    return await self._ask_stress(update, context)
                else:
                    return await self._show_confirm(update, context)

        return STATE_ENERGY_MORNING

    async def _ask_energy_evening(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Спрашивает энергию вечером."""
        query = update.callback_query
        if query:
            await query.answer()

        text = f"{EMOJI_ENERGY} <b>Как чувствуешь себя сейчас?</b>\n\nОцени энергию от 1 до 10:"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard("energy_evening"))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard("energy_evening"),
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

        text = f"{EMOJI_STRESS} <b>Оцени уровень стресса за сегодня</b> (1 — спокоен, 10 — очень напряжён):"

        if query:
            await self._safe_edit_message(query, text, get_energy_stress_keyboard("stress"))
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_energy_stress_keyboard("stress"),
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
                return await self._ask_hours_on_feet(update, context)

        elif update.message:
            try:
                steps = int(update.message.text.strip())
                if steps < 0 or steps > 50000:
                    raise ValueError
                self._update_metric(context, "steps", steps)
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
                return await self._ask_workout_type(update, context)

        elif update.message:
            try:
                hours = float(update.message.text.strip().replace(",", "."))
                if hours < 0 or hours > 24:
                    raise ValueError
                self._update_metric(context, "hours_on_feet", hours)
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
                # Нет тренировки — переходим к подтверждению
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

        # Сохраняем в БД
        today = date.today()
        await self.metrics_repo.save_metrics(user_id, today, metrics)

        # Очищаем временные данные
        self._clear_metrics(context)

        # Показываем дневник
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
            CallbackQueryHandler(h.show_metrics_menu, pattern="^metrics_show$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(h.handle_main_menu, pattern="^metrics_"),
                CallbackQueryHandler(h._show_edit_menu, pattern="^edit_"),
                CallbackQueryHandler(h.confirm_and_save, pattern=f"^{CALLBACK_CONFIRM_ALL}$"),
            ],
            STATE_SLEEP_HOURS: [
                CallbackQueryHandler(h.process_sleep_hours, pattern="^(sleep_|sleep_custom)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_sleep_hours),
            ],
            STATE_SLEEP_QUALITY: [
                CallbackQueryHandler(h.process_sleep_quality, pattern="^quality_"),
            ],
            STATE_SLEEP_AWAKENINGS: [
                CallbackQueryHandler(h.process_sleep_awakenings, pattern="^awakenings_"),
            ],
            STATE_ENERGY_MORNING: [
                CallbackQueryHandler(h.process_energy_morning, pattern="^energy_morning_"),
            ],
            STATE_ENERGY_EVENING: [
                CallbackQueryHandler(h.process_energy_evening, pattern="^energy_evening_"),
            ],
            STATE_STRESS: [
                CallbackQueryHandler(h.process_stress, pattern="^stress_"),
            ],
            STATE_STEPS: [
                CallbackQueryHandler(h.process_steps, pattern="^(steps_|steps_custom)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_steps),
            ],
            STATE_HOURS_ON_FEET: [
                CallbackQueryHandler(h.process_hours_on_feet, pattern="^(feet_|feet_custom)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_hours_on_feet),
            ],
            STATE_WORKOUT_TYPE: [
                CallbackQueryHandler(h.process_workout_type, pattern="^workout_type_"),
            ],
            STATE_WORKOUT_DURATION: [
                CallbackQueryHandler(h.process_workout_duration, pattern="^(workout_duration_|duration_custom)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.process_workout_duration),
            ],
            STATE_WORKOUT_INTENSITY: [
                CallbackQueryHandler(h.process_workout_intensity, pattern="^intensity_"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(h.confirm_and_save, pattern=f"^{CALLBACK_CONFIRM_ALL}$"),
                CallbackQueryHandler(h._show_edit_menu, pattern=f"^{CALLBACK_METRICS_EDIT}$"),
                CallbackQueryHandler(h.cancel, pattern=f"^{CALLBACK_METRICS_BACK_TO_DIARY}$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cancel, pattern=f"^{CALLBACK_CANCEL}$"),
            CallbackQueryHandler(h._back_to_diary, pattern=f"^{CALLBACK_METRICS_BACK_TO_DIARY}$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )