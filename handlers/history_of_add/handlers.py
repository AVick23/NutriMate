# handlers/history_of_add/handlers.py
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
)

from db.database import Database
from db.models import UserRepository, HistoryRepository
from handlers.history_of_add.constants import (
    STATE_MAIN_MENU, STATE_CALENDAR,
    CALLBACK_BACK_TO_MENU,
)
from handlers.history_of_add.keyboards import (
    get_main_menu_keyboard, get_navigation_keyboard,
    get_empty_history_keyboard, get_calendar_keyboard,
)
from handlers.history_of_add.utils import (
    format_history_message, format_empty_history_message,
    get_available_dates_set, parse_calendar_date
)

logger = logging.getLogger(__name__)


class HistoryHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.history_repo = HistoryRepository(db)

    async def show_history_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню выбора даты."""
        query = update.callback_query
        await query.answer()
        
        # Очищаем данные
        context.user_data.pop("history_current_date", None)
        context.user_data.pop("history_calendar_year", None)
        context.user_data.pop("history_calendar_month", None)
        
        text = (
            "📜 <b>История питания и воды</b>\n\n"
            "Тут ты можешь посмотреть, что ты ел и сколько воды пил в любой день.\n\n"
            "Выбери день:"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор даты из главного меню."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "history_back_to_menu":
            # Возврат в главное меню бота
            await self._back_to_main_menu(update, context)
            return ConversationHandler.END
        
        elif data == "history_yesterday":
            target_date = date.today() - timedelta(days=1)
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "history_today":
            target_date = date.today()
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "history_tomorrow":
            target_date = date.today() + timedelta(days=1)
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "history_other_date":
            return await self._show_calendar(update, context)
        
        return STATE_MAIN_MENU

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
        
        # Сохраняем текущую дату в контекст
        context.user_data["history_current_date"] = date_str
        
        # Форматируем сообщение
        if meals or water_logs:
            text = format_history_message(target_date, meals, water_logs)
            reply_markup = get_navigation_keyboard(target_date)
        else:
            text = format_empty_history_message(target_date)
            reply_markup = get_empty_history_keyboard(target_date)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает навигацию (Вчера/Сегодня/Завтра/Другая дата)."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "nav_today":
            target_date = date.today()
            return await self._show_history_for_date(update, context, target_date)
        
        elif data == "nav_other_date":
            return await self._show_calendar(update, context)
        
        elif data == "nav_add_food":
            # Переход к добавлению еды
            await query.edit_message_text(
                "🍽️ Перенаправление в меню добавления еды...",
                parse_mode="HTML"
            )
            # Вызываем обработчик добавления еды
            from handlers.add_food.handlers import AddFoodHandlers
            add_food_handler = AddFoodHandlers(self.db)
            return await add_food_handler.show_add_food_menu(update, context)
        
        elif data.startswith("nav_"):
            # Формат: nav_2024-06-18
            try:
                date_str = data.replace("nav_", "")
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return await self._show_history_for_date(update, context, target_date)
            except:
                return STATE_MAIN_MENU
        
        return STATE_MAIN_MENU

    async def _show_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает календарь для выбора даты."""
        query = update.callback_query
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        # Получаем даты с записями
        dates_with_entries = await self.history_repo.get_dates_with_entries(user_id)
        available_dates = get_available_dates_set(dates_with_entries)
        
        # Текущая дата для календаря
        today = date.today()
        current_year = context.user_data.get("history_calendar_year", today.year)
        current_month = context.user_data.get("history_calendar_month", today.month)
        
        text = "📅 <b>Выбери день в календаре</b>\n\n"
        text += "✓ — дни с записями"
        
        await query.edit_message_text(
            text,
            reply_markup=get_calendar_keyboard(
                current_year, current_month, available_dates, today
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
            # Очищаем данные календаря
            context.user_data.pop("history_calendar_year", None)
            context.user_data.pop("history_calendar_month", None)
            return await self.show_history_menu(update, context)
        
        elif data.startswith("calendar_prev_"):
            # Формат: calendar_prev_2024_6
            parts = data.split("_")
            year = int(parts[2])
            month = int(parts[3])
            
            # Переход к предыдущему месяцу
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
            
            # Переход к следующему месяцу
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
                # Очищаем данные календаря
                context.user_data.pop("history_calendar_year", None)
                context.user_data.pop("history_calendar_month", None)
                return await self._show_history_for_date(update, context, target_date)
        
        return STATE_CALENDAR

    async def _back_to_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Возврат в главное меню бота."""
        query = update.callback_query
        
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
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel, pattern="^cancel$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )