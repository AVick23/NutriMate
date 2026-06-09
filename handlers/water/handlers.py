"""
Обработчики для управления водой.
🎯 Обновлено: добавлен экран с информацией о норме воды.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from db.database import Database
from db.repositories import UserRepository, WaterRepository, DailyStatsRepository
from .constants import (
    STATE_SELECT_VOLUME, STATE_WATER_INFO,
    DEFAULT_WATER_ML, CALLBACK_ADD_WATER_DEFAULT, CALLBACK_SHOW_VOLUMES,
    CALLBACK_BACK_TO_DIARY, CALLBACK_WATER_INFO, CALLBACK_WATER_BACK
)
from .utils import get_water_status_text, calculate_water_goal, get_water_info_text
from .keyboards import get_water_volume_keyboard, get_water_info_keyboard

logger = logging.getLogger(__name__)


class WaterHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.water_repo = WaterRepository(db)
        self.stats_repo = DailyStatsRepository(db)

    async def add_water_default(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Добавляет стандартный стакан воды (250 мл) по нажатию на кнопку воды.
        """
        query = update.callback_query
        user = update.effective_user

        user_id = await self.user_repo.get_user_id(user.id)
        if not user_id:
            await query.answer("❌ Ошибка: пользователь не найден", show_alert=True)
            return

        await self.water_repo.add_water(user_id, DEFAULT_WATER_ML)

        # Получаем профиль для расчёта нормы воды
        profile = await self.user_repo.get_profile(user_id)
        if profile:
            weight = profile.get("weight_kg")
            if not weight:
                # Получаем вес из замеров
                from db.repositories import MeasurementsRepository
                meas_repo = MeasurementsRepository(self.db)
                last_weight = await meas_repo.get_last_measurement(user_id, 1)
                weight = last_weight["value"] if last_weight else 70.0
            water_goal = calculate_water_goal(weight, profile["gender"])
        else:
            water_goal = 2000  # запасной вариант

        today_stats = await self.stats_repo.get_today_stats(user_id)
        water_count_ml = today_stats.get("water_ml", 0)
        status_text = get_water_status_text(water_count_ml, water_goal)

        await query.answer(
            f"💧 +{DEFAULT_WATER_ML} мл\n{status_text}",
            show_alert=False
        )

        from handlers.start.handlers import show_diary
        await show_diary(update, context)

    async def show_volume_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает меню выбора объёма воды."""
        query = update.callback_query
        await query.answer()

        text = (
            "💧  <b>Выбери объём воды</b>\n\n"
            "Сколько воды ты выпил?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_water_volume_keyboard(),
            parse_mode="HTML"
        )
        return STATE_SELECT_VOLUME

    # 🎯 НОВОЕ: Показывает информацию о норме воды
    async def show_water_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает информацию о норме воды."""
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        # Получаем норму воды
        profile = await self.user_repo.get_profile(user_id)
        if profile:
            weight = profile.get("weight_kg")
            if not weight:
                from db.repositories import MeasurementsRepository
                meas_repo = MeasurementsRepository(self.db)
                last_weight = await meas_repo.get_last_measurement(user_id, 1)
                weight = last_weight["value"] if last_weight else 70.0
            water_goal = calculate_water_goal(weight, profile["gender"])
        else:
            water_goal = 2000

        text = get_water_info_text(water_goal)

        await query.edit_message_text(
            text,
            reply_markup=get_water_info_keyboard(),
            parse_mode="HTML"
        )
        return STATE_WATER_INFO

    async def add_water_with_volume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Добавляет воду с выбранным объёмом."""
        query = update.callback_query
        user = update.effective_user
        data = query.data

        if data == "water_vol_custom":
            await query.edit_message_text(
                "✏️  <b>Введи объём в миллилитрах</b>\n\n"
                "Например: <code>350</code> или <code>0.5</code>",
                parse_mode="HTML"
            )
            return STATE_SELECT_VOLUME

        try:
            volume = int(data.replace("water_vol_", ""))
        except ValueError:
            await query.answer("❌ Ошибка", show_alert=True)
            return ConversationHandler.END

        user_id = await self.user_repo.get_user_id(user.id)
        if not user_id:
            await query.answer("❌ Пользователь не найден", show_alert=True)
            return ConversationHandler.END

        await self.water_repo.add_water(user_id, volume)

        profile = await self.user_repo.get_profile(user_id)
        if profile:
            weight = profile.get("weight_kg")
            if not weight:
                from db.repositories import MeasurementsRepository
                meas_repo = MeasurementsRepository(self.db)
                last_weight = await meas_repo.get_last_measurement(user_id, 1)
                weight = last_weight["value"] if last_weight else 70.0
            water_goal = calculate_water_goal(weight, profile["gender"])
        else:
            water_goal = 2000

        today_stats = await self.stats_repo.get_today_stats(user_id)
        water_count_ml = today_stats.get("water_ml", 0)
        status_text = get_water_status_text(water_count_ml, water_goal)

        await query.answer(
            f"💧 +{volume} мл\n{status_text}",
            show_alert=False
        )

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def process_custom_volume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает ввод своего объёма воды."""
        user = update.effective_user
        text = update.message.text.strip()

        try:
            if '.' in text or ',' in text:
                volume = float(text.replace(',', '.'))
                if volume < 100:
                    volume = volume * 1000
            else:
                volume = int(text)

            if volume <= 0 or volume > 5000:
                raise ValueError
            volume = int(volume)

        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный объём (1–5000 мл).\n"
                "Например: <code>350</code> или <code>0.5</code> (литра)",
                parse_mode="HTML"
            )
            return STATE_SELECT_VOLUME

        user_id = await self.user_repo.get_user_id(user.id)
        if user_id:
            await self.water_repo.add_water(user_id, volume)

            profile = await self.user_repo.get_profile(user_id)
            if profile:
                weight = profile.get("weight_kg")
                if not weight:
                    from db.repositories import MeasurementsRepository
                    meas_repo = MeasurementsRepository(self.db)
                    last_weight = await meas_repo.get_last_measurement(user_id, 1)
                    weight = last_weight["value"] if last_weight else 70.0
                water_goal = calculate_water_goal(weight, profile["gender"])
            else:
                water_goal = 2000

            today_stats = await self.stats_repo.get_today_stats(user_id)
            water_count_ml = today_stats.get("water_ml", 0)
            status_text = get_water_status_text(water_count_ml, water_goal)

            await update.message.reply_text(
                f"💧  <b>Добавлено {volume} мл</b>\n{status_text}",
                parse_mode="HTML"
            )

        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена выбора объёма."""
        query = update.callback_query
        if query:
            await query.answer()
        from handlers.start.handlers import show_diary
        await show_diary(update, context)
        return ConversationHandler.END


def get_water_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для управления водой."""
    handlers = WaterHandlers(db)
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.add_water_default, pattern=f"^{CALLBACK_ADD_WATER_DEFAULT}$"),
            CallbackQueryHandler(handlers.show_volume_menu, pattern=f"^{CALLBACK_SHOW_VOLUMES}$"),
            CallbackQueryHandler(handlers.show_volume_menu, pattern=f"^{CALLBACK_ADD_WATER}$"),
        ],
        states={
            STATE_SELECT_VOLUME: [
                CallbackQueryHandler(handlers.add_water_with_volume, pattern="^water_vol_"),
                CallbackQueryHandler(handlers.show_water_info, pattern=f"^{CALLBACK_WATER_INFO}$"),  # 🎯 НОВОЕ
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_custom_volume),
                CallbackQueryHandler(handlers.cancel, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            ],
            # 🎯 НОВОЕ: Состояние для информации о воде
            STATE_WATER_INFO: [
                CallbackQueryHandler(handlers.show_volume_menu, pattern=f"^{CALLBACK_ADD_WATER}$"),
                CallbackQueryHandler(handlers.cancel, pattern=f"^{CALLBACK_WATER_BACK}$"),
                CallbackQueryHandler(handlers.cancel, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
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