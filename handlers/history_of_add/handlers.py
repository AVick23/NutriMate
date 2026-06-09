"""
Обработчики для истории питания.
🎯 Обновлено: убран "Завтра", исправлен nav_add_food, добавлены сводки
   за неделю/месяц, "Повторить день", цветовые индикаторы в календаре.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
)
from db.database import Database
from db.repositories import UserRepository, HistoryRepository, MealRepository
from handlers.history_of_add.constants import (
    STATE_MAIN_MENU, STATE_CALENDAR, STATE_PERIOD_SUMMARY,
    CALLBACK_BACK_TO_MENU,
)
from handlers.history_of_add.keyboards import (
    get_main_menu_keyboard, get_navigation_keyboard,
    get_empty_history_keyboard, get_calendar_keyboard,
    get_period_summary_keyboard, get_repeat_confirmation_keyboard,
)
from handlers.history_of_add.utils import (
    format_history_message, format_empty_history_message,
    get_available_dates_set, parse_calendar_date,
    get_period_stats, format_period_summary, get_dates_with_status,
)
from handlers.water.utils import calculate_water_goal

logger = logging.getLogger(__name__)


class HistoryHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.history_repo = HistoryRepository(db)
        self.meal_repo = MealRepository(db)

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ================================================================
    async def _get_user_goals(self, user_id: int) -> dict:
        """🎯 Получает daily_kcal и water_goal пользователя."""
        profile = await self.user_repo.get_profile(user_id)
        if not profile:
            return {"daily_kcal": 2000, "water_goal": 2000}
        
        daily_kcal = profile.get("daily_kcal", 2000)
        
        # Получаем вес для расчёта нормы воды
        from db.repositories import MeasurementsRepository
        meas_repo = MeasurementsRepository(self.db)
        last_weight = await meas_repo.get_last_measurement(user_id, 1)
        weight = last_weight["value"] if last_weight else 70.0
        water_goal = calculate_water_goal(weight, profile.get("gender", "male"))
        
        return {
            "daily_kcal": daily_kcal,
            "water_goal": water_goal,
        }

    # ================================================================
    # ГЛАВНОЕ МЕНЮ
    # ================================================================
    async def show_history_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню выбора даты."""
        query = update.callback_query
        await query.answer()
        
        # Очищаем данные
        context.user_data.pop("history_current_date", None)
        context.user_data.pop("history_calendar_year", None)
        context.user_data.pop("history_calendar_month", None)
        context.user_data.pop("history_period_days", None)
        
        text = (
            "📜  <b>История питания</b>\n\n"
            "Посмотри, что ты ел и пил в любой день.\n\n"
            "Или сразу посмотри сводку за период:"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор из главного меню."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "history_back_to_menu":
            await self._back_to_main_menu(update, context)
            return ConversationHandler.END
        
        elif data == "history_yesterday":
            target_date = date.today() - timedelta(days=1)
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "history_today":
            target_date = date.today()
            return await self._show_history_for_date(update, context, target_date)
        
        # 🎯 УБРАНО: history_tomorrow (бессмыслен для истории)
        
        elif data == "history_week":
            return await self._show_period_summary(update, context, 7, "Сводка за неделю")
        
        elif data == "history_month":
            return await self._show_period_summary(update, context, 30, "Сводка за месяц")
        
        elif data == "history_other_date":
            return await self._show_calendar(update, context)
        
        return STATE_MAIN_MENU

    # ================================================================
    # ПОКАЗ ИСТОРИИ ЗА ДЕНЬ
    # ================================================================
    async def _show_history_for_date(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        target_date: date
    ) -> int:
        """Показывает историю за конкретную дату."""
        query = update.callback_query
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        if not user_id:
            await query.edit_message_text(
                "❌ Пользователь не найден. Напиши /start",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        # Получаем записи за дату
        date_str = target_date.strftime("%Y-%m-%d")
        meals = await self.history_repo.get_meals_for_date(user_id, date_str)
        water_logs = await self.history_repo.get_water_for_date(user_id, date_str)
        
        # Сохраняем текущую дату в контекст (для "Повторить день")
        context.user_data["history_current_date"] = date_str
        
        # 🎯 Получаем цели пользователя для статуса дня
        goals = await self._get_user_goals(user_id)
        
        # Форматируем сообщение
        if meals or water_logs:
            text = format_history_message(
                target_date, meals, water_logs,
                daily_kcal_goal=goals["daily_kcal"],
                water_goal_ml=goals["water_goal"],
            )
            reply_markup = get_navigation_keyboard(target_date, has_entries=bool(meals))
        else:
            text = format_empty_history_message(target_date)
            reply_markup = get_empty_history_keyboard(target_date)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    # ================================================================
    # НАВИГАЦИЯ ПО ДНЯМ
    # ================================================================
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает навигацию (Вчера/Сегодня/Другая дата/Повторить/Добавить еду)."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "nav_today":
            target_date = date.today()
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "nav_other_date":
            return await self._show_calendar(update, context)
        
        # 🎯 ИСПРАВЛЕНО: nav_add_food — завершаем текущий handler,
        # чтобы entry point add_food подхватил callback "food_select_method"
        elif data == "nav_add_food":
            from handlers.add_food.keyboards import get_select_method_keyboard
            text = "🍽️  <b>Добавление еды</b>\n\nВыбери действие:"
            await query.edit_message_text(
                text,
                reply_markup=get_select_method_keyboard(),
                parse_mode="HTML"
            )
            # Возвращаем END, чтобы add_food ConversationHandler активировался
            # через свой entry point (food_select_method)
            return ConversationHandler.END
        
        # 🎯 НОВОЕ: Повторить день (сначала показываем подтверждение)
        elif data == "nav_repeat_day":
            return await self._confirm_repeat_day(update, context)
        
        elif data.startswith("nav_"):
            # Формат: nav_2024-06-18
            try:
                date_str = data.replace("nav_", "")
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return await self._show_history_for_date(update, context, target_date)
            except:
                return STATE_MAIN_MENU
        
        return STATE_MAIN_MENU

    # ================================================================
    # 🎯 НОВОЕ: ПОВТОРИТЬ ДЕНЬ
    # ================================================================
    async def _confirm_repeat_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает подтверждение перед повтором дня."""
        query = update.callback_query
        
        source_date_str = context.user_data.get("history_current_date")
        if not source_date_str:
            await query.answer("❌ Нет данных для повтора", show_alert=True)
            return STATE_MAIN_MENU
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        meals = await self.history_repo.get_meals_for_date(user_id, source_date_str)
        
        if not meals:
            await query.answer("❌ Нет блюд для повтора", show_alert=True)
            return STATE_MAIN_MENU
        
        source_date = datetime.strptime(source_date_str, "%Y-%m-%d").date()
        from .utils import format_date_short_ru
        source_date_text = format_date_short_ru(source_date)
        
        total_kcal = sum(m["kcal"] for m in meals)
        text = (
            f"🔁  <b>Повторить день?</b>\n\n"
            f"📅 {source_date_text}\n"
            f"🍽️ Блюд: <b>{len(meals)}</b>\n"
            f"🔥 Всего: <b>{total_kcal} ккал</b>\n\n"
            f"Все блюда будут скопированы в <b>сегодняшний</b> день."
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_repeat_confirmation_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_repeat_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """🎯 Копирует блюда выбранного дня в сегодняшний."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "repeat_cancel":
            await query.edit_message_text("❌ Повтор отменён.", parse_mode="HTML")
            return await self.show_history_menu(update, context)
        
        # repeat_confirm
        source_date_str = context.user_data.get("history_current_date")
        if not source_date_str:
            await query.edit_message_text("❌ Ошибка: нет данных для повтора", parse_mode="HTML")
            return STATE_MAIN_MENU
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        meals = await self.history_repo.get_meals_for_date(user_id, source_date_str)
        
        if not meals:
            await query.edit_message_text("❌ Нет блюд для повтора", parse_mode="HTML")
            return STATE_MAIN_MENU
        
        # Копируем каждое блюдо в сегодняшний день
        copied = 0
        total_kcal = 0
        for meal in meals:
            await self.meal_repo.add_meal(
                user_id=user_id,
                meal_type=meal["meal_type"],
                food_name=meal["food_name"],
                amount_g=meal["amount_g"],
                kcal=meal["kcal"],
                protein_g=meal["protein_g"],
                fat_g=meal["fat_g"],
                carbs_g=meal["carbs_g"],
                barcode=meal.get("barcode"),
            )
            copied += 1
            total_kcal += meal["kcal"]
        
        # Показываем успех и возвращаем в дневник
        from .utils import format_date_short_ru
        source_date = datetime.strptime(source_date_str, "%Y-%m-%d").date()
        
        text = (
            f"🔁  <b>Повторено!</b>\n\n"
            f"📅 Со дня {format_date_short_ru(source_date)}\n"
            f"🍽️ Скопировано: <b>{copied} блюд</b>\n"
            f"🔥 Всего: <b>{total_kcal} ккал</b>\n\n"
            f"Все блюда добавлены в сегодняшний день. ✨"
        )
        
        await query.edit_message_text(text, parse_mode="HTML")
        
        # Через 2 секунды возвращаем в дневник
        import asyncio
        await asyncio.sleep(2.0)
        
        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    # ================================================================
    # 🎯 НОВОЕ: СВОДКИ ЗА ПЕРИОД
    # ================================================================
    async def _show_period_summary(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        days: int,
        period_name: str,
    ) -> int:
        """Показывает сводку за период (неделя/месяц)."""
        query = update.callback_query
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        if not user_id:
            await query.edit_message_text("❌ Пользователь не найден", parse_mode="HTML")
            return ConversationHandler.END
        
        # Получаем цели пользователя
        goals = await self._get_user_goals(user_id)
        
        # Собираем статистику
        stats = await get_period_stats(
            self.history_repo,
            user_id,
            days,
            daily_kcal_goal=goals["daily_kcal"],
        )
        
        # Форматируем сводку
        text = format_period_summary(stats, period_name, days)
        
        # Сохраняем период в контекст
        context.user_data["history_period_days"] = days
        
        await query.edit_message_text(
            text,
            reply_markup=get_period_summary_keyboard(days),
            parse_mode="HTML"
        )
        return STATE_PERIOD_SUMMARY

    async def handle_period_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает действия в сводке."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "summary_back":
            return await self.show_history_menu(update, context)
        
        elif data == "summary_to_month":
            return await self._show_period_summary(update, context, 30, "Сводка за месяц")
        
        elif data == "history_back_to_menu":
            await self._back_to_main_menu(update, context)
            return ConversationHandler.END
        
        return STATE_PERIOD_SUMMARY

    # ================================================================
    # КАЛЕНДАРЬ
    # ================================================================
    async def _show_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """🎯 Показывает календарь с цветовыми индикаторами."""
        query = update.callback_query
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        # Текущая дата для календаря
        today = date.today()
        current_year = context.user_data.get("history_calendar_year", today.year)
        current_month = context.user_data.get("history_calendar_month", today.month)
        
        # 🎯 Получаем цели пользователя для расчёта статусов
        goals = await self._get_user_goals(user_id)
        
        # Получаем dict {date_str: status} для цветовых индикаторов
        date_status = await get_dates_with_status(
            self.history_repo,
            user_id,
            current_year,
            current_month,
            goals["daily_kcal"],
        )
        
        text = (
            "📅  <b>Выбери день в календаре</b>\n\n"
            "🟢 в норме · 🟡 отклонение · 🔴 сильное отклонение · ⚪ нет записей"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_calendar_keyboard(
                current_year, current_month, date_status, today
            ),
            parse_mode="HTML"
        )
        return STATE_CALENDAR

    async def handle_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает действия в календаре."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "calendar_back":
            context.user_data.pop("history_calendar_year", None)
            context.user_data.pop("history_calendar_month", None)
            return await self.show_history_menu(update, context)
        
        elif data.startswith("calendar_prev_"):
            # Формат: calendar_prev_2024_6
            parts = data.split("_")
            year = int(parts[2])
            month = int(parts[3])
            
            if month == 1:
                prev_year = year - 1
                prev_month = 12
            else:
                prev_year = year
                prev_month = month - 1
            
            context.user_data["history_calendar_year"] = prev_year
            context.user_data["history_calendar_month"] = prev_month
            
            return await self._show_calendar(update, context)
        
        elif data.startswith("calendar_next_"):
            # Формат: calendar_next_2024_6
            parts = data.split("_")
            year = int(parts[2])
            month = int(parts[3])
            
            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1
            
            context.user_data["history_calendar_year"] = next_year
            context.user_data["history_calendar_month"] = next_month
            
            return await self._show_calendar(update, context)
        
        elif data.startswith("calendar_select_"):
            # Формат: calendar_select_2024-06-18
            date_str = data.replace("calendar_select_", "")
            target_date = parse_calendar_date(date_str)
            
            if target_date:
                context.user_data.pop("history_calendar_year", None)
                context.user_data.pop("history_calendar_month", None)
                return await self._show_history_for_date(update, context, target_date)
        
        return STATE_CALENDAR

    # ================================================================
    # ВОЗВРАТЫ И ОТМЕНА
    # ================================================================
    async def _back_to_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Возврат в главное меню бота."""
        from handlers.start.handlers import show_diary
        await show_diary(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена и возврат в главное меню."""
        query = update.callback_query
        if query:
            await query.answer()
        await self._back_to_main_menu(update, context)
        return ConversationHandler.END


def get_history_conversation_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для истории записей."""
    handlers = HistoryHandlers(db)
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_history_menu, pattern="^history_show$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(handlers.handle_main_menu, pattern="^history_"),
                CallbackQueryHandler(handlers.handle_navigation, pattern="^nav_"),
            ],
            STATE_CALENDAR: [
                CallbackQueryHandler(handlers.handle_calendar, pattern="^(calendar_|history_)"),
            ],
            # 🎯 НОВОЕ: состояние для сводок за период
            STATE_PERIOD_SUMMARY: [
                CallbackQueryHandler(handlers.handle_period_summary, pattern="^(summary_|history_)"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel, pattern="^cancel$"),
            # 🎯 НОВОЕ: обработка подтверждения повтора дня
            CallbackQueryHandler(handlers.handle_repeat_day, pattern="^repeat_"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )