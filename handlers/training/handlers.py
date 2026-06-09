"""
Обработчики модуля тренировок.
🎯 Научно обоснованная калистеника с Apple-like UX + поддержка картинок.

📸 КАРТИНКИ:
Положи изображения в папку static/training/ с именами, совпадающими
с ID упражнений из exercises.py:
    - pushup_classic.jpg
    - pullup_classic.jpg  
    - squat_classic.jpg
    - plank.jpg
    - burpee.jpg
    ... и т.д. для всех упражнений.

Формат: JPG или PNG, ~800x600px, до 500KB.
Если файла нет — бот просто покажет текстовую карточку без картинки.
"""
import os
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler,
)
from db.database import Database
from db.repositories import UserRepository
from handlers.start.handlers import show_diary
from .constants import (
    STATE_MAIN_MENU, STATE_EXERCISES_MENU, STATE_MUSCLE_GROUP,
    STATE_EXERCISE_CARD, STATE_EXERCISE_DETAIL, STATE_GENERAL_TIPS,
    STATE_QUICK_WORKOUT, STATE_WORKOUT_SESSION,
    CALLBACK_BACK_TO_DIARY, CALLBACK_MAIN_MENU,
    CALLBACK_EXERCISES_MENU, CALLBACK_QUICK_WORKOUT,
    CALLBACK_MUSCLE_PREFIX, CALLBACK_GENERAL_TIPS,
    CALLBACK_EXERCISE_PREFIX, CALLBACK_EXERCISE_BACK,
    CALLBACK_DETAIL_TECHNIQUE, CALLBACK_DETAIL_SCIENCE,
    CALLBACK_DETAIL_PROGRAM, CALLBACK_DETAIL_PROGRESSION,
    CALLBACK_DETAIL_CONTRA,
    CALLBACK_START_QUICK, CALLBACK_WORKOUT_DONE,
    CALLBACK_WORKOUT_CANCEL,
    MUSCLE_GROUPS,
)
from .keyboards import (
    get_main_training_keyboard, get_exercises_menu_keyboard,
    get_muscle_group_keyboard, get_exercise_card_keyboard,
    get_exercise_detail_keyboard, get_general_tips_keyboard,
    get_general_tip_detail_keyboard, get_quick_workout_keyboard,
    get_workout_session_keyboard, get_workout_complete_keyboard,
)
from .utils import (
    format_main_menu, format_exercises_menu,
    format_muscle_group_exercises, format_exercise_card,
    format_exercise_science, format_exercise_programs,
    format_exercise_progressions, format_exercise_contraindications,
    format_general_tips_menu, format_general_tip,
    format_quick_workout, format_workout_step,
    format_workout_complete,
)
from .exercises import (
    get_exercise_by_id, get_workout_by_id,
)

logger = logging.getLogger(__name__)


class TrainingHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        # 🎯 Определяем путь к папке с картинками упражнений
        # handlers/training/handlers.py -> нужно подняться на 2 уровня вверх к корню проекта
        self._base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self._training_images_dir = os.path.join(self._base_dir, "static", "training")

    # ================================================================
    # 🎯 ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ КАРТИНОК
    # ================================================================
    def _get_exercise_image_path(self, exercise_id: str) -> str:
        """
        🎯 Возвращает путь к картинке упражнения.
        
        Ищет файл static/training/{exercise_id} с расширениями:
        .jpg, .jpeg, .png, .webp
        
        Args:
            exercise_id: ID упражнения (например, 'pushup_classic')
            
        Returns:
            str: Полный путь к файлу картинки (или пустая строка, если нет)
        """
        # Пробуем разные расширения
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            image_path = os.path.join(
                self._training_images_dir,
                f"{exercise_id}{ext}"
            )
            if os.path.exists(image_path):
                return image_path
        
        return ""

    async def _send_exercise_card_with_image(
        self,
        update: Update,
        exercise_id: str,
        text: str,
        keyboard
    ) -> bool:
        """
        🎯 Отправляет карточку упражнения с картинкой (если есть).
        
        Returns:
            bool: True если отправлено с картинкой, False если только текст
        """
        image_path = self._get_exercise_image_path(exercise_id)
        
        if image_path and os.path.exists(image_path):
            try:
                # Если есть callback_query — удаляем старое текстовое сообщение
                if update.callback_query:
                    try:
                        await update.callback_query.message.delete()
                    except Exception as e:
                        logger.debug(f"Не удалось удалить старое сообщение: {e}")
                
                # Отправляем новое сообщение с картинкой
                with open(image_path, "rb") as photo:
                    if update.callback_query:
                        await update.callback_query.message.reply_photo(
                            photo=photo,
                            caption=text,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=text,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                
                logger.debug(f"✅ Отправлена картинка для {exercise_id}")
                return True
                
            except Exception as e:
                logger.error(f"Ошибка отправки картинки для {exercise_id}: {e}")
                return False
        
        return False

    # ================================================================
    # ГЛАВНОЕ МЕНЮ
    # ================================================================
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню тренировок."""
        query = update.callback_query
        if query:
            await query.answer()
        
        # Очищаем данные
        for key in ["training_exercise_id", "training_muscle_group",
                    "training_workout_id", "training_tip_id"]:
            context.user_data.pop(key, None)
        
        text = format_main_menu()
        
        target = query.edit_message_text if query else update.message.reply_text
        await target(
            text,
            reply_markup=get_main_training_keyboard(),
            parse_mode="HTML"
        )
        return STATE_MAIN_MENU

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор из главного меню."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_BACK_TO_DIARY:
            await show_diary(update, context)
            return ConversationHandler.END
        
        if data == CALLBACK_EXERCISES_MENU:
            return await self._show_exercises_menu(update, context)
        
        if data == CALLBACK_QUICK_WORKOUT:
            return await self._show_quick_workout(update, context)
        
        return STATE_MAIN_MENU

    # ================================================================
    # РАЗДЕЛ "УПРАЖНЕНИЯ И СОВЕТЫ"
    # ================================================================
    async def _show_exercises_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает меню упражнений и советов."""
        query = update.callback_query
        
        text = format_exercises_menu()
        
        await query.edit_message_text(
            text,
            reply_markup=get_exercises_menu_keyboard(),
            parse_mode="HTML"
        )
        return STATE_EXERCISES_MENU

    async def handle_exercises_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор в меню упражнений."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        if data == CALLBACK_BACK_TO_DIARY:
            await show_diary(update, context)
            return ConversationHandler.END
        
        if data == CALLBACK_GENERAL_TIPS:
            return await self._show_general_tips(update, context)
        
        # Группа мышц
        if data.startswith(CALLBACK_MUSCLE_PREFIX):
            muscle_id = data.replace(CALLBACK_MUSCLE_PREFIX, "")
            return await self._show_muscle_group(update, context, muscle_id)
        
        return STATE_EXERCISES_MENU

    # ================================================================
    # ГРУППА МЫШЦ
    # ================================================================
    async def _show_muscle_group(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, muscle_id: str
    ) -> int:
        """Показывает список упражнений в группе мышц."""
        query = update.callback_query
        
        context.user_data["training_muscle_group"] = muscle_id
        
        text = format_muscle_group_exercises(muscle_id)
        
        await query.edit_message_text(
            text,
            reply_markup=get_muscle_group_keyboard(muscle_id),
            parse_mode="HTML"
        )
        return STATE_MUSCLE_GROUP

    async def handle_muscle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор в группе мышц."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_EXERCISES_MENU:
            return await self._show_exercises_menu(update, context)
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        if data == CALLBACK_BACK_TO_DIARY:
            await show_diary(update, context)
            return ConversationHandler.END
        
        # Выбор упражнения
        if data.startswith(CALLBACK_EXERCISE_PREFIX):
            exercise_id = data.replace(CALLBACK_EXERCISE_PREFIX, "")
            return await self._show_exercise_card(update, context, exercise_id)
        
        return STATE_MUSCLE_GROUP

    # ================================================================
    # 🎯 КАРТОЧКА УПРАЖНЕНИЯ (С КАРТИНКОЙ!)
    # ================================================================
    async def _show_exercise_card(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, exercise_id: str
    ) -> int:
        """
        🎯 Показывает карточку упражнения с картинкой (если есть).
        
        Логика:
        1. Пытаемся найти картинку в static/training/{exercise_id}.jpg
        2. Если есть — отправляем фото с caption
        3. Если нет — отправляем обычное текстовое сообщение
        """
        query = update.callback_query
        exercise = get_exercise_by_id(exercise_id)
        
        if not exercise:
            await query.answer("❌ Упражнение не найдено", show_alert=True)
            return STATE_MUSCLE_GROUP
        
        context.user_data["training_exercise_id"] = exercise_id
        
        text = format_exercise_card(exercise)
        keyboard = get_exercise_card_keyboard(exercise_id)
        
        # 🎯 Пытаемся отправить с картинкой
        sent_with_image = await self._send_exercise_card_with_image(
            update, exercise_id, text, keyboard
        )
        
        # Если картинка не отправлена — отправляем текст
        if not sent_with_image:
            await query.edit_message_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        return STATE_EXERCISE_CARD

    async def handle_exercise_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает действия с карточкой упражнения."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        exercise_id = context.user_data.get("training_exercise_id")
        muscle_group = context.user_data.get("training_muscle_group", "push")
        
        # Возвраты
        if data == CALLBACK_EXERCISE_BACK or data == f"{CALLBACK_MUSCLE_PREFIX}{muscle_group}":
            return await self._show_muscle_group(update, context, muscle_group)
        
        if data == CALLBACK_EXERCISES_MENU:
            return await self._show_exercises_menu(update, context)
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        # Возврат к той же карточке (из деталей)
        if data.startswith(CALLBACK_EXERCISE_PREFIX) and exercise_id:
            return await self._show_exercise_card(update, context, exercise_id)
        
        # Разделы упражнения
        if not exercise_id:
            return STATE_EXERCISE_CARD
        
        if data.startswith(CALLBACK_DETAIL_SCIENCE):
            return await self._show_exercise_detail(update, context, exercise_id, "science")
        
        if data.startswith(CALLBACK_DETAIL_PROGRAM):
            return await self._show_exercise_detail(update, context, exercise_id, "program")
        
        if data.startswith(CALLBACK_DETAIL_PROGRESSION):
            return await self._show_exercise_detail(update, context, exercise_id, "progression")
        
        if data.startswith(CALLBACK_DETAIL_CONTRA):
            return await self._show_exercise_detail(update, context, exercise_id, "contra")
        
        return STATE_EXERCISE_CARD

    # ================================================================
    # ДЕТАЛИ УПРАЖНЕНИЯ
    # ================================================================
    async def _show_exercise_detail(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
        exercise_id: str, section: str
    ) -> int:
        """Показывает раздел упражнения (наука/программа/прогрессии/противопоказания)."""
        query = update.callback_query
        exercise = get_exercise_by_id(exercise_id)
        
        if not exercise:
            await query.answer("❌ Упражнение не найдено", show_alert=True)
            return STATE_EXERCISE_CARD
        
        formatters = {
            "science": format_exercise_science,
            "program": format_exercise_programs,
            "progression": format_exercise_progressions,
            "contra": format_exercise_contraindications,
        }
        
        formatter = formatters.get(section)
        if not formatter:
            return STATE_EXERCISE_CARD
        
        text = formatter(exercise)
        
        await query.edit_message_text(
            text,
            reply_markup=get_exercise_detail_keyboard(exercise_id, section),
            parse_mode="HTML"
        )
        return STATE_EXERCISE_DETAIL

    async def handle_exercise_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает навигацию в деталях упражнения."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        exercise_id = context.user_data.get("training_exercise_id")
        
        if not exercise_id:
            return await self.show_main_menu(update, context)
        
        # Возврат к карточке
        if data.startswith(CALLBACK_EXERCISE_PREFIX):
            return await self._show_exercise_card(update, context, exercise_id)
        
        # Переход между разделами
        if data.startswith(CALLBACK_DETAIL_SCIENCE):
            return await self._show_exercise_detail(update, context, exercise_id, "science")
        if data.startswith(CALLBACK_DETAIL_PROGRAM):
            return await self._show_exercise_detail(update, context, exercise_id, "program")
        if data.startswith(CALLBACK_DETAIL_PROGRESSION):
            return await self._show_exercise_detail(update, context, exercise_id, "progression")
        if data.startswith(CALLBACK_DETAIL_CONTRA):
            return await self._show_exercise_detail(update, context, exercise_id, "contra")
        
        # Возвраты
        muscle_group = context.user_data.get("training_muscle_group", "push")
        if data == CALLBACK_EXERCISE_BACK or data == f"{CALLBACK_MUSCLE_PREFIX}{muscle_group}":
            return await self._show_muscle_group(update, context, muscle_group)
        
        if data == CALLBACK_EXERCISES_MENU:
            return await self._show_exercises_menu(update, context)
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        return STATE_EXERCISE_DETAIL

    # ================================================================
    # ОБЩИЕ СОВЕТЫ
    # ================================================================
    async def _show_general_tips(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает список общих советов."""
        query = update.callback_query
        
        text = format_general_tips_menu()
        
        await query.edit_message_text(
            text,
            reply_markup=get_general_tips_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GENERAL_TIPS

    async def handle_general_tips(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор совета."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_EXERCISES_MENU:
            return await self._show_exercises_menu(update, context)
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        if data == CALLBACK_BACK_TO_DIARY:
            await show_diary(update, context)
            return ConversationHandler.END
        
        # Конкретный совет
        if data.startswith("training_tip_"):
            tip_id = data.replace("training_tip_", "")
            context.user_data["training_tip_id"] = tip_id
            
            text = format_general_tip(tip_id)
            
            await query.edit_message_text(
                text,
                reply_markup=get_general_tip_detail_keyboard(tip_id),
                parse_mode="HTML"
            )
            return STATE_GENERAL_TIPS
        
        return STATE_GENERAL_TIPS

    # ================================================================
    # БЫСТРАЯ ТРЕНИРОВКА
    # ================================================================
    async def _show_quick_workout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает описание быстрой тренировки."""
        query = update.callback_query
        
        workout = get_workout_by_id("quick_15min")
        if not workout:
            await query.answer("❌ Тренировка не найдена", show_alert=True)
            return await self.show_main_menu(update, context)
        
        context.user_data["training_workout_id"] = "quick_15min"
        
        text = format_quick_workout(workout)
        
        await query.edit_message_text(
            text,
            reply_markup=get_quick_workout_keyboard(),
            parse_mode="HTML"
        )
        return STATE_QUICK_WORKOUT

    async def handle_quick_workout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает действия с быстрой тренировкой."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_MAIN_MENU:
            return await self.show_main_menu(update, context)
        
        if data == CALLBACK_BACK_TO_DIARY:
            await show_diary(update, context)
            return ConversationHandler.END
        
        if data == CALLBACK_START_QUICK:
            return await self._start_workout_session(update, context)
        
        return STATE_QUICK_WORKOUT

    # ================================================================
    # ТРЕНИРОВОЧНАЯ СЕССИЯ
    # ================================================================
    async def _start_workout_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Запускает тренировочную сессию."""
        query = update.callback_query
        
        workout_id = context.user_data.get("training_workout_id", "quick_15min")
        workout = get_workout_by_id(workout_id)
        
        if not workout:
            await query.answer("❌ Тренировка не найдена", show_alert=True)
            return await self.show_main_menu(update, context)
        
        # Инициализация сессии
        context.user_data["workout_start_time"] = datetime.now()
        context.user_data["workout_state"] = {
            "round": 1,
            "exercise": 0,
            "is_work": True,
            "seconds_left": workout["work_time"],
        }
        
        total_rounds = int(workout["structure"].split()[0])
        
        # Сообщение о старте
        text = (
            f"🏁  <b>Тренировка началась!</b>\n\n"
            f"📋 {workout['name']}\n"
            f"🔥 Разминка: {workout['warmup']}\n\n"
            f"Всего <b>{total_rounds} круга</b> по <b>{len(workout['exercises'])} упражнений</b>.\n\n"
            f"▶️ Работа: {workout['work_time']} сек\n"
            f"⏸ Отдых: {workout['rest_time']} сек\n\n"
            f"Удачи! 💪"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_workout_session_keyboard(),
            parse_mode="HTML"
        )
        
        # Запускаем фоновый таймер
        asyncio.create_task(self._workout_timer(context, update))
        
        return STATE_WORKOUT_SESSION

    async def _workout_timer(self, context: ContextTypes.DEFAULT_TYPE, update: Update):
        """Фоновый таймер для тренировки."""
        try:
            while True:
                await asyncio.sleep(1)
                
                state = context.user_data.get("workout_state")
                if not state:
                    break
                
                workout_id = context.user_data.get("training_workout_id", "quick_15min")
                workout = get_workout_by_id(workout_id)
                if not workout:
                    break
                
                state["seconds_left"] -= 1
                
                if state["seconds_left"] <= 0:
                    # Переключение фазы
                    total_rounds = int(workout["structure"].split()[0])
                    total_exercises = len(workout["exercises"])
                    
                    if state["is_work"]:
                        # Работа → Отдых
                        state["is_work"] = False
                        state["seconds_left"] = workout["rest_time"]
                        
                        # Переход к следующему упражнению
                        state["exercise"] += 1
                        if state["exercise"] >= total_exercises:
                            state["exercise"] = 0
                            state["round"] += 1
                            
                            if state["round"] > total_rounds:
                                # Тренировка завершена
                                await self._finish_workout(update, context)
                                return
                    else:
                        # Отдых → Работа
                        state["is_work"] = True
                        state["seconds_left"] = workout["work_time"]
                
                # Обновляем сообщение каждые 5 секунд или при смене фазы
                if state["seconds_left"] % 5 == 0 or state["seconds_left"] <= 3:
                    try:
                        text = format_workout_step(
                            workout,
                            state["round"],
                            state["exercise"],
                            state["is_work"],
                            state["seconds_left"]
                        )
                        await context.bot.edit_message_text(
                            text,
                            chat_id=update.effective_chat.id,
                            message_id=update.callback_query.message.message_id,
                            reply_markup=get_workout_session_keyboard(),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.debug(f"Timer update error: {e}")
        
        except Exception as e:
            logger.error(f"Workout timer error: {e}")

    async def _finish_workout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершает тренировку."""
        start_time = context.user_data.get("workout_start_time")
        workout_id = context.user_data.get("training_workout_id", "quick_15min")
        workout = get_workout_by_id(workout_id)
        
        if not start_time or not workout:
            return await self.show_main_menu(update, context)
        
        duration = datetime.now() - start_time
        duration_min = max(1, int(duration.total_seconds() / 60))
        
        text = format_workout_complete(workout, duration_min)
        
        # Очищаем состояние
        context.user_data.pop("workout_state", None)
        context.user_data.pop("workout_start_time", None)
        context.user_data.pop("training_workout_id", None)
        
        try:
            await context.bot.edit_message_text(
                text,
                chat_id=update.effective_chat.id,
                message_id=update.callback_query.message.message_id,
                reply_markup=get_workout_complete_keyboard(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Finish workout error: {e}")

    async def handle_workout_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает действия во время тренировки."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == CALLBACK_WORKOUT_DONE:
            await self._finish_workout(update, context)
            return STATE_MAIN_MENU
        
        if data == CALLBACK_WORKOUT_CANCEL:
            # Отмена тренировки
            context.user_data.pop("workout_state", None)
            context.user_data.pop("workout_start_time", None)
            context.user_data.pop("training_workout_id", None)
            
            await query.edit_message_text(
                "❌ <b>Тренировка отменена.</b>\n\nНичего страшного — "
                "можно начать в любое время!",
                reply_markup=get_main_training_keyboard(),
                parse_mode="HTML"
            )
            return STATE_MAIN_MENU
        
        return STATE_WORKOUT_SESSION

    # ================================================================
    # ОТМЕНА
    # ================================================================
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена и возврат в дневник."""
        if update.callback_query:
            await update.callback_query.answer()
        await show_diary(update, context)
        return ConversationHandler.END


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================
def get_training_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для тренировок."""
    handlers = TrainingHandlers(db)
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_main_menu, pattern="^training_add$"),
            CallbackQueryHandler(handlers.show_main_menu, pattern="^training_menu$"),
        ],
        states={
            STATE_MAIN_MENU: [
                CallbackQueryHandler(
                    handlers.handle_main_menu,
                    pattern=f"^({CALLBACK_BACK_TO_DIARY}|{CALLBACK_EXERCISES_MENU}|{CALLBACK_QUICK_WORKOUT})$"
                ),
            ],
            STATE_EXERCISES_MENU: [
                CallbackQueryHandler(handlers.handle_exercises_menu, pattern="^(training_|noop)"),
            ],
            STATE_MUSCLE_GROUP: [
                CallbackQueryHandler(handlers.handle_muscle_group, pattern="^(training_|noop)"),
            ],
            STATE_EXERCISE_CARD: [
                CallbackQueryHandler(handlers.handle_exercise_card, pattern="^(training_|noop)"),
            ],
            STATE_EXERCISE_DETAIL: [
                CallbackQueryHandler(handlers.handle_exercise_detail, pattern="^(training_|noop)"),
            ],
            STATE_GENERAL_TIPS: [
                CallbackQueryHandler(handlers.handle_general_tips, pattern="^(training_|noop)"),
            ],
            STATE_QUICK_WORKOUT: [
                CallbackQueryHandler(handlers.handle_quick_workout, pattern="^(training_|noop)"),
            ],
            STATE_WORKOUT_SESSION: [
                CallbackQueryHandler(
                    handlers.handle_workout_session,
                    pattern=f"^({CALLBACK_WORKOUT_DONE}|{CALLBACK_WORKOUT_CANCEL})$"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel, pattern=f"^{CALLBACK_BACK_TO_DIARY}$"),
            CallbackQueryHandler(handlers.cancel, pattern="^cancel$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )