# handlers/measurements/handlers.py
import logging
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from db.database import Database
from db.models import UserRepository
from .repository import MeasurementsRepository
from .constants import (
    STATE_MAIN_MENU, STATE_CHOOSE_TYPE, STATE_ENTER_VALUE, STATE_HISTORY_TYPE,
    CALLBACK_MEASUREMENTS_MENU, CALLBACK_MEASUREMENTS_ADD, CALLBACK_MEASUREMENTS_HISTORY,
    CALLBACK_MEASUREMENTS_GOALS, CALLBACK_MEASUREMENTS_BACK,
    CALLBACK_TYPE_PREFIX, CALLBACK_VALUE_PREFIX, CALLBACK_VALUE_CUSTOM,
    MEASUREMENT_TYPES,
)
from .keyboards import (
    get_main_menu_keyboard, get_measurement_types_keyboard,
    get_value_keyboard, get_history_types_keyboard,
    get_history_back_keyboard, get_add_more_keyboard,
)
from .utils import (
    get_smart_feedback, format_history_message, format_main_menu_message,
    get_measurement_type_info, calculate_trend, format_waist_risk_message
)

logger = logging.getLogger(__name__)


class MeasurementsHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.measurements_repo = MeasurementsRepository(db)

    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню замеров."""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        # Получаем последние замеры всех типов
        last_measurements = {}
        for type_id in MEASUREMENT_TYPES.keys():
            last = await self.measurements_repo.get_last_measurement(user_id, type_id)
            if last:
                last_measurements[type_id] = last
        
        text = format_main_menu_message(last_measurements, {})
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор в главном меню."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_MEASUREMENTS_BACK:
            await self._back_to_diary(update, context)
            return ConversationHandler.END
        
        elif data == CALLBACK_MEASUREMENTS_ADD:
            return await self._choose_type(update, context)
        
        elif data == CALLBACK_MEASUREMENTS_HISTORY:
            return await self._choose_history_type(update, context)
        
        elif data == CALLBACK_MEASUREMENTS_GOALS:
            await self._goals_menu(update, context)
            return STATE_MAIN_MENU
        
        return STATE_MAIN_MENU

    async def _choose_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает выбор типа замера для добавления."""
        query = update.callback_query
        
        text = "✏️ <b>Какой замер хочешь добавить?</b>"
        
        await query.edit_message_text(
            text,
            reply_markup=get_measurement_types_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CHOOSE_TYPE

    async def handle_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор типа замера."""
        query = update.callback_query
        data = query.data
        
        if data == "measurements_add":
            return await self._choose_type(update, context)
        
        if data == "measurements_menu":
            return await self.show_menu(update, context)
        
        if data.startswith(CALLBACK_TYPE_PREFIX):
            type_id = int(data.replace(CALLBACK_TYPE_PREFIX, ""))
            context.user_data["measurement_type_id"] = type_id
            
            info = get_measurement_type_info(type_id)
            text = f"✏️ <b>Введи значение для {info['display']}</b>\n\nНапример: <code>84.5 {info['unit']}</code>"
            
            await query.edit_message_text(
                text,
                reply_markup=get_value_keyboard(type_id),
                parse_mode="HTML"
            )
            return STATE_ENTER_VALUE
        
        return STATE_CHOOSE_TYPE

    async def handle_value_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает ввод значения (через кнопки или текст)."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data
            
            if data == "measurements_add":
                return await self._choose_type(update, context)
            
            if data == "measurements_menu":
                return await self.show_menu(update, context)
            
            if data.startswith(CALLBACK_VALUE_PREFIX):
                value_str = data.replace(CALLBACK_VALUE_PREFIX, "")
                try:
                    value = float(value_str)
                except ValueError:
                    await query.answer("❌ Ошибка", show_alert=True)
                    return STATE_ENTER_VALUE
                
                return await self._save_measurement(update, context, value, is_callback=True)
            
            if data == CALLBACK_VALUE_CUSTOM:
                await query.edit_message_text(
                    "✏️ <b>Введи значение вручную</b>\n\n"
                    "Например: <code>84.5</code> или <code>85</code>",
                    parse_mode="HTML"
                )
                return STATE_ENTER_VALUE
        
        elif update.message:
            text = update.message.text.strip()
            try:
                value = float(text.replace(',', '.'))
            except ValueError:
                await update.message.reply_text(
                    "❌ Пожалуйста, введи число.\n"
                    "Например: <code>84.5</code>",
                    parse_mode="HTML"
                )
                return STATE_ENTER_VALUE
            
            return await self._save_measurement(update, context, value, is_callback=False)
        
        return STATE_ENTER_VALUE

    async def _save_measurement(self, update: Update, context: ContextTypes.DEFAULT_TYPE, value: float, is_callback: bool = True) -> int:
        """Сохраняет замер в БД и показывает фидбек."""
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        type_id = context.user_data.get("measurement_type_id")
        
        if not type_id:
            return await self._choose_type(update, context)
        
        # Получаем предыдущий замер
        previous = await self.measurements_repo.get_last_measurement(user_id, type_id)
        previous_value = previous["value"] if previous else None
        
        # Сохраняем новый замер
        await self.measurements_repo.add_measurement(user_id, type_id, value)
        
        # Получаем историю для аналитики
        history = await self.measurements_repo.get_measurements_history(user_id, type_id, limit=10)
        
        # Рассчитываем тренд
        trend = calculate_trend(history)
        
        # Генерируем умное сообщение
        info = get_measurement_type_info(type_id)
        feedback = get_smart_feedback(
            type_id,
            info["display"],
            value,
            previous_value,
            trend
        )
        
        # Добавляем оценку риска по талии (согласно рекомендациям ВОЗ)
        if info["name"] == "waist":
            profile = await self.user_repo.get_profile(user_id)
            if profile:
                gender = profile["gender"]
                risk_message = format_waist_risk_message(info["name"], value, gender)
                feedback += risk_message
        
        # Отправляем сообщение в зависимости от типа ввода
        if is_callback and update.callback_query:
            query = update.callback_query
            await query.edit_message_text(
                f"{feedback}\n\nЧто дальше?",
                reply_markup=get_add_more_keyboard(),
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"{feedback}\n\nЧто дальше?",
                reply_markup=get_add_more_keyboard(),
                parse_mode="HTML"
            )
        
        # Очищаем временные данные
        context.user_data.pop("measurement_type_id", None)
        
        return STATE_MAIN_MENU

    async def _choose_history_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает выбор типа для просмотра истории."""
        query = update.callback_query
        
        text = "📈 <b>Историю какого замера показать?</b>"
        
        await query.edit_message_text(
            text,
            reply_markup=get_history_types_keyboard(),
            parse_mode="HTML"
        )
        return STATE_HISTORY_TYPE

    async def handle_history_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор типа для истории."""
        query = update.callback_query
        data = query.data
        
        if data == "measurements_history":
            return await self._choose_history_type(update, context)
        
        if data == "measurements_menu":
            return await self.show_menu(update, context)
        
        if data.startswith("measurements_history_type_"):
            type_id = int(data.replace("measurements_history_type_", ""))
            await self._show_history(update, context, type_id)
            return STATE_HISTORY_TYPE
        
        return STATE_HISTORY_TYPE

    async def _show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE, type_id: int) -> None:
        """Показывает историю замеров выбранного типа."""
        query = update.callback_query
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)
        
        history = await self.measurements_repo.get_measurements_history(user_id, type_id, limit=15)
        info = get_measurement_type_info(type_id)
        
        text = format_history_message(type_id, info["display"], history, info["unit"])
        
        # Добавляем оценку риска по талии для последнего замера
        if info["name"] == "waist" and history:
            profile = await self.user_repo.get_profile(user_id)
            if profile:
                gender = profile["gender"]
                last_value = history[0]["value"]
                risk_message = format_waist_risk_message(info["name"], last_value, gender)
                text += f"\n\n{risk_message}"
        
        await query.edit_message_text(
            text,
            reply_markup=get_history_back_keyboard(),
            parse_mode="HTML"
        )

    async def _goals_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает меню целей (заглушка для MVP)."""
        query = update.callback_query
        
        text = (
            "🎯 <b>Мои цели</b>\n\n"
            "Функция целей находится в разработке.\n"
            "Скоро ты сможешь устанавливать целевой вес и объёмы,\n"
            "а я буду отслеживать прогресс и давать прогнозы! 🚀"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )

    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Возврат в дневник."""
        query = update.callback_query
        from handlers.start.handlers import show_diary
        await show_diary(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена и возврат в главное меню."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
        await self._back_to_diary(update, context)
        return ConversationHandler.END


def get_measurements_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для замеров тела."""
    handlers = MeasurementsHandlers(db)
    
    # Создаём таблицы при инициализации
    import asyncio
    asyncio.create_task(handlers.measurements_repo.init_tables())
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_menu, pattern="^measurements_menu$"),
            CallbackQueryHandler(handlers.show_menu, pattern="^body_measurements$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(handlers.handle_menu, pattern="^measurements_"),
            ],
            STATE_CHOOSE_TYPE: [
                CallbackQueryHandler(handlers.handle_type_selection, pattern="^measurements_"),
            ],
            STATE_ENTER_VALUE: [
                CallbackQueryHandler(handlers.handle_value_input, pattern="^measurements_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_value_input),
            ],
            STATE_HISTORY_TYPE: [
                CallbackQueryHandler(handlers.handle_history_type, pattern="^measurements_"),
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