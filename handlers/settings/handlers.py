"""
Обработчики для меню настроек пользователя.
🎯 Обновлено: исправлен баг с Pace, добавлено редактирование темпа,
   MeasurementsRepository импортируется из db.repositories.
"""
import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from db.database import Database
from db.repositories import UserRepository, MeasurementsRepository
from handlers.registration.utils import (
    Gender, ActivityLevel, Goal, Pace,
    calculate_bmr, calculate_tdee, calculate_target_kcal, calculate_macros,
    ACTIVITY_NAMES, GOAL_NAMES, GENDER_NAMES,
    PACE_NAMES, PACE_NAMES_GAIN,
)
from .constants import (
    STATE_EDIT_MENU, STATE_EDIT_WEIGHT, STATE_EDIT_HEIGHT, STATE_EDIT_AGE,
    STATE_EDIT_GENDER, STATE_EDIT_ACTIVITY, STATE_EDIT_GOAL, STATE_EDIT_PACE,
    STATE_CONFIRM_SAVE,
    CALLBACK_SETTINGS_MENU, CALLBACK_EDIT_PROFILE, CALLBACK_EDIT_WATER,
    CALLBACK_EXPORT_DATA, CALLBACK_DELETE_DATA, CALLBACK_BACK_TO_DIARY,
    CALLBACK_EDIT_WEIGHT, CALLBACK_EDIT_HEIGHT, CALLBACK_EDIT_AGE,
    CALLBACK_EDIT_GENDER, CALLBACK_EDIT_ACTIVITY, CALLBACK_EDIT_GOAL,
    CALLBACK_EDIT_PACE, CALLBACK_EDIT_ALL,
    CALLBACK_SAVE_PROFILE, CALLBACK_CANCEL,
)
from .keyboards import (
    get_settings_main_keyboard, get_profile_edit_keyboard,
    get_confirm_save_keyboard, get_back_keyboard,
    get_gender_keyboard, get_activity_keyboard, get_goal_keyboard,
    get_pace_keyboard,
)

logger = logging.getLogger(__name__)


class SettingsHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.measurements_repo = MeasurementsRepository(db)  # 🎯 из db.repositories

    # ================================================================
    # ГЛАВНОЕ МЕНЮ НАСТРОЕК
    # ================================================================
    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню настроек и возвращает состояние."""
        query = update.callback_query
        await query.answer()

        text = "⚙️  <b>Настройки</b>\n\nЗдесь ты можешь изменить свои данные и предпочтения."
        await query.edit_message_text(
            text,
            reply_markup=get_settings_main_keyboard(),
            parse_mode="HTML"
        )
        return STATE_EDIT_MENU

    async def handle_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор из главного меню настроек."""
        query = update.callback_query
        data = query.data

        if data == CALLBACK_BACK_TO_DIARY:
            await self._back_to_diary(update, context)
            return ConversationHandler.END

        if data == CALLBACK_EDIT_PROFILE:
            return await self._start_edit_profile(update, context)

        if data == CALLBACK_EDIT_WATER:
            await query.edit_message_text(
                "💧 Настройка воды будет добавлена в следующей версии.",
                reply_markup=get_back_keyboard("settings_menu"),
                parse_mode="HTML"
            )
            return STATE_EDIT_MENU

        if data == CALLBACK_EXPORT_DATA:
            await query.edit_message_text(
                "📥 Экспорт данных будет доступен в ближайшее время.",
                reply_markup=get_back_keyboard("settings_menu"),
                parse_mode="HTML"
            )
            return STATE_EDIT_MENU

        if data == CALLBACK_DELETE_DATA:
            await query.edit_message_text(
                "🗑 Удаление данных — это необратимое действие.\n"
                "Функция временно отключена для безопасности.",
                reply_markup=get_back_keyboard("settings_menu"),
                parse_mode="HTML"
            )
            return STATE_EDIT_MENU

        return STATE_EDIT_MENU

    # ================================================================
    # РЕДАКТИРОВАНИЕ ПРОФИЛЯ
    # ================================================================
    async def _start_edit_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает редактирование профиля."""
        query = update.callback_query
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        profile = await self.user_repo.get_profile(user_id)
        if not profile:
            await query.edit_message_text("❌ Профиль не найден. Начни с /start")
            return ConversationHandler.END

        # Получаем последний вес из замеров
        last_weight = await self.measurements_repo.get_last_measurement(user_id, 1)
        current_weight = last_weight["value"] if last_weight else 70.0

        # 🎯 Загружаем pace из БД (если есть)
        saved_pace = profile.get("pace")

        context.user_data["edit_profile"] = {
            "weight_kg": current_weight,
            "height_cm": profile["height_cm"],
            "age": profile["age"],
            "gender": profile["gender"],
            "activity_level": profile["activity_level"],
            "goal": profile["goal"],
            "pace": saved_pace,  # 🎯 сохраняем pace
        }
        context.user_data["edit_profile_original"] = context.user_data["edit_profile"].copy()

        text = "👤  <b>Редактирование профиля</b>\n\nВыбери, что хочешь изменить:"
        await query.edit_message_text(
            text,
            reply_markup=get_profile_edit_keyboard(context.user_data["edit_profile"]),
            parse_mode="HTML"
        )
        return STATE_EDIT_MENU

    async def handle_edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает выбор параметра для редактирования."""
        query = update.callback_query
        data = query.data

        if data == CALLBACK_CANCEL:
            await self._back_to_diary(update, context)
            return ConversationHandler.END

        if data == CALLBACK_SAVE_PROFILE:
            return await self._confirm_save(update, context)

        if data == CALLBACK_EDIT_WEIGHT:
            await query.edit_message_text(
                "✏️  <b>Введи свой текущий вес</b>\n\nНапример: <code>84.2</code>",
                parse_mode="HTML"
            )
            return STATE_EDIT_WEIGHT

        if data == CALLBACK_EDIT_HEIGHT:
            await query.edit_message_text(
                "✏️  <b>Введи свой рост</b> (в см)\n\nНапример: <code>180</code>",
                parse_mode="HTML"
            )
            return STATE_EDIT_HEIGHT

        if data == CALLBACK_EDIT_AGE:
            await query.edit_message_text(
                "✏️  <b>Введи свой возраст</b> (лет)\n\nНапример: <code>30</code>",
                parse_mode="HTML"
            )
            return STATE_EDIT_AGE

        if data == CALLBACK_EDIT_GENDER:
            await query.edit_message_text(
                "👤  <b>Выбери пол</b>",
                reply_markup=get_gender_keyboard(),
                parse_mode="HTML"
            )
            return STATE_EDIT_GENDER

        if data == CALLBACK_EDIT_ACTIVITY:
            await query.edit_message_text(
                "🏃  <b>Выбери уровень активности</b>",
                reply_markup=get_activity_keyboard(),
                parse_mode="HTML"
            )
            return STATE_EDIT_ACTIVITY

        if data == CALLBACK_EDIT_GOAL:
            await query.edit_message_text(
                "🎯  <b>Выбери цель</b>",
                reply_markup=get_goal_keyboard(),
                parse_mode="HTML"
            )
            return STATE_EDIT_GOAL

        # 🎯 НОВОЕ: Редактирование темпа
        if data == CALLBACK_EDIT_PACE:
            goal = Goal(context.user_data["edit_profile"]["goal"])
            await query.edit_message_text(
                "⏱️  <b>Выбери темп достижения цели</b>",
                reply_markup=get_pace_keyboard(goal),
                parse_mode="HTML"
            )
            return STATE_EDIT_PACE

        return STATE_EDIT_MENU

    # ================================================================
    # ВВОД НОВЫХ ЗНАЧЕНИЙ
    # ================================================================
    async def process_new_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            weight = float(update.message.text.replace(',', '.'))
            if weight < 30 or weight > 300:
                raise ValueError
        except:
            await update.message.reply_text("❌ Введи корректный вес (30–300 кг).")
            return STATE_EDIT_WEIGHT

        context.user_data["edit_profile"]["weight_kg"] = weight
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def process_new_height(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            height = int(update.message.text)
            if height < 120 or height > 250:
                raise ValueError
        except:
            await update.message.reply_text("❌ Введи корректный рост (120–250 см).")
            return STATE_EDIT_HEIGHT

        context.user_data["edit_profile"]["height_cm"] = height
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def process_new_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            age = int(update.message.text)
            if age < 14 or age > 100:
                raise ValueError
        except:
            await update.message.reply_text("❌ Введи корректный возраст (14–100 лет).")
            return STATE_EDIT_AGE

        context.user_data["edit_profile"]["age"] = age
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def process_new_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        gender_value = query.data.replace("set_gender_", "")
        context.user_data["edit_profile"]["gender"] = gender_value
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def process_new_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        activity_value = query.data.replace("set_activity_", "")
        context.user_data["edit_profile"]["activity_level"] = activity_value
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def process_new_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        goal_value = query.data.replace("set_goal_", "")
        context.user_data["edit_profile"]["goal"] = goal_value

        # 🎯 Если цель "поддерживать", сбрасываем pace (он не нужен)
        if goal_value == "maintain":
            context.user_data["edit_profile"]["pace"] = None

        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    # 🎯 НОВОЕ: Обработка выбора темпа
    async def process_new_pace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        pace_value = query.data.replace("set_pace_", "")
        context.user_data["edit_profile"]["pace"] = pace_value
        await self._show_edit_menu(update, context)
        return STATE_EDIT_MENU

    async def _show_edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обновляет меню редактирования после изменения одного параметра."""
        if update.callback_query:
            query = update.callback_query
            await query.edit_message_text(
                "👤  <b>Редактирование профиля</b>\n\nВыбери, что хочешь изменить:",
                reply_markup=get_profile_edit_keyboard(context.user_data["edit_profile"]),
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "👤  <b>Редактирование профиля</b>\n\nВыбери, что хочешь изменить:",
                reply_markup=get_profile_edit_keyboard(context.user_data["edit_profile"]),
                parse_mode="HTML"
            )

    # ================================================================
    # ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
    # ================================================================
    async def _confirm_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        edited = context.user_data["edit_profile"]
        original = context.user_data["edit_profile_original"]

        changes = []
        if edited["weight_kg"] != original["weight_kg"]:
            changes.append(f"⚖️ Вес: {original['weight_kg']} → {edited['weight_kg']} кг")
        if edited["height_cm"] != original["height_cm"]:
            changes.append(f"📏 Рост: {original['height_cm']} → {edited['height_cm']} см")
        if edited["age"] != original["age"]:
            changes.append(f"🎂 Возраст: {original['age']} → {edited['age']} лет")
        if edited["gender"] != original["gender"]:
            changes.append(f"👤 Пол: {GENDER_NAMES[Gender(original['gender'])]} → {GENDER_NAMES[Gender(edited['gender'])]}")
        if edited["activity_level"] != original["activity_level"]:
            changes.append(f"🏃 Активность: {ACTIVITY_NAMES[ActivityLevel(original['activity_level'])]} → {ACTIVITY_NAMES[ActivityLevel(edited['activity_level'])]}")
        if edited["goal"] != original["goal"]:
            changes.append(f"🎯 Цель: {GOAL_NAMES[Goal(original['goal'])]} → {GOAL_NAMES[Goal(edited['goal'])]}")

        # 🎯 Показываем изменение темпа (если есть и цель не maintain)
        if edited.get("goal") != "maintain" and edited.get("pace") != original.get("pace"):
            goal = Goal(edited["goal"])
            names = PACE_NAMES_GAIN if goal == Goal.GAIN else PACE_NAMES
            
            old_pace_name = "Не выбран"
            new_pace_name = "Не выбран"
            
            if original.get("pace"):
                try:
                    old_pace_name = names[Pace(original["pace"])]
                except:
                    pass
            if edited.get("pace"):
                try:
                    new_pace_name = names[Pace(edited["pace"])]
                except:
                    pass
            
            changes.append(f"⏱️ Темп: {old_pace_name} → {new_pace_name}")

        if not changes:
            await query.edit_message_text("Нет изменений. Возврат в меню.")
            return await self._start_edit_profile(update, context)

        text = "🔄  <b>Подтверди изменения</b>\n\n" + "\n".join(changes) + "\n\nПересчитать нормы КБЖУ?"
        await query.edit_message_text(
            text,
            reply_markup=get_confirm_save_keyboard(),
            parse_mode="HTML"
        )
        return STATE_CONFIRM_SAVE

    async def save_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        user = update.effective_user
        user_id = await self.user_repo.get_user_id(user.id)

        edited = context.user_data["edit_profile"]

        # Сохраняем новый вес как замер
        await self.measurements_repo.add_measurement(user_id, 1, edited["weight_kg"])

        # 🎯 ИСПРАВЛЕНИЕ БАГА: достаём сохранённый pace из редактирования
        # Приоритет: 1) из edit_profile 2) из оригинала (из БД) 3) fallback STEADY
        pace_value = edited.get("pace")
        if pace_value:
            pace = Pace(pace_value)
        else:
            # Если цель maintain, pace может быть None
            goal_enum = Goal(edited["goal"])
            if goal_enum == Goal.MAINTAIN:
                pace = Pace.STEADY  # Не используется, но нужен для расчёта
            else:
                pace = Pace.STEADY  # Fallback

        bmr = calculate_bmr(edited["weight_kg"], edited["height_cm"], edited["age"], Gender(edited["gender"]))
        tdee = calculate_tdee(bmr, ActivityLevel(edited["activity_level"]))
        goal_enum = Goal(edited["goal"])
        
        target_kcal = calculate_target_kcal(tdee, goal_enum, pace)
        macros = calculate_macros(target_kcal, edited["weight_kg"], goal_enum)

        profile_data = {
            "height_cm": edited["height_cm"],
            "age": edited["age"],
            "gender": edited["gender"],
            "activity_level": edited["activity_level"],
            "goal": edited["goal"],
            "pace": pace.value if goal_enum != Goal.MAINTAIN else None,  # 🎯 сохраняем pace
            "bmr": bmr,
            "daily_kcal": target_kcal,
            "daily_protein_g": macros["protein_g"],
            "daily_fat_g": macros["fat_g"],
            "daily_carbs_g": macros["carbs_g"],
        }
        await self.user_repo.save_profile(user_id, profile_data)

        # Формируем отображаемое имя темпа
        if goal_enum != Goal.MAINTAIN and pace:
            names = PACE_NAMES_GAIN if goal_enum == Goal.GAIN else PACE_NAMES
            pace_display = names[pace]
        else:
            pace_display = "—"

        text = (
            "✅  <b>Профиль обновлён!</b>\n\n"
            f"📏 Рост: {edited['height_cm']} см\n"
            f"🎂 Возраст: {edited['age']} лет\n"
            f"👤 Пол: {GENDER_NAMES[Gender(edited['gender'])]}\n"
            f"🏃 Активность: {ACTIVITY_NAMES[ActivityLevel(edited['activity_level'])]}\n"
            f"🎯 Цель: {GOAL_NAMES[Goal(edited['goal'])]}\n"
            f"⏱️ Темп: {pace_display}\n\n"
            f"🔥  <b>Новые нормы:</b>\n"
            f"Калории: {target_kcal} ккал\n"
            f"Белки: {macros['protein_g']} г\n"
            f"Жиры: {macros['fat_g']} г\n"
            f"Углеводы: {macros['carbs_g']} г"
        )
        await query.edit_message_text(
            text,
            reply_markup=get_back_keyboard("settings_menu"),
            parse_mode="HTML"
        )

        context.user_data.pop("edit_profile", None)
        context.user_data.pop("edit_profile_original", None)
        return ConversationHandler.END

    # ================================================================
    # ОТМЕНА И ВОЗВРАТ
    # ================================================================
    async def cancel_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data.pop("edit_profile", None)
        context.user_data.pop("edit_profile_original", None)
        return await self.show_settings_menu(update, context)

    async def _back_to_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        from handlers.start.handlers import show_diary
        await show_diary(update, context)


# ================================================================
# РЕГИСТРАЦИЯ ConversationHandler
# ================================================================
def get_settings_handler(db: Database) -> ConversationHandler:
    handlers = SettingsHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_settings_menu, pattern="^settings_show$"),
        ],
        states={
            STATE_EDIT_MENU: [
                CallbackQueryHandler(handlers.handle_settings_menu, pattern="^settings_"),
                CallbackQueryHandler(handlers.handle_edit_menu, pattern="^(edit_|save_profile|cancel_edit)"),
            ],
            STATE_EDIT_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_new_weight),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_EDIT_HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_new_height),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_EDIT_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_new_age),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_EDIT_GENDER: [
                CallbackQueryHandler(handlers.process_new_gender, pattern="^set_gender_"),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_EDIT_ACTIVITY: [
                CallbackQueryHandler(handlers.process_new_activity, pattern="^set_activity_"),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_EDIT_GOAL: [
                CallbackQueryHandler(handlers.process_new_goal, pattern="^set_goal_"),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            # 🎯 НОВЫЙ СТЕЙТ для темпа
            STATE_EDIT_PACE: [
                CallbackQueryHandler(handlers.process_new_pace, pattern="^set_pace_"),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
            STATE_CONFIRM_SAVE: [
                CallbackQueryHandler(handlers.save_profile, pattern="^save_profile_confirm$"),
                CallbackQueryHandler(handlers._start_edit_profile, pattern="^save_profile_continue$"),
                CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel_edit$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel_edit, pattern="^cancel$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )