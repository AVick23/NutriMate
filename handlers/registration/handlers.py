# handlers/registration/handlers.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from db.database import Database
from db.models import UserRepository, RegistrationStateRepository
from handlers.registration.utils import (
    Gender, ActivityLevel, Goal, Pace,
    STATE_AGE_HEIGHT_WEIGHT, STATE_ACTIVITY, STATE_GOAL, STATE_PACE, STATE_GENDER,
    parse_physical_data, calculate_bmr, calculate_tdee, calculate_target_kcal, calculate_macros,
    ACTIVITY_NAMES, GOAL_NAMES, PACE_NAMES, PACE_NAMES_GAIN, GENDER_NAMES
)
from handlers.registration.keyboards import (
    get_cancel_keyboard, get_confirm_retry_keyboard, get_activity_keyboard,
    get_goal_keyboard, get_pace_keyboard, get_gender_keyboard, get_complete_keyboard
)


class RegistrationHandlers:
    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.state_repo = RegistrationStateRepository(db)

    # ========== ШАГ 1: Возраст, рост, вес ==========

    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало регистрации по кнопке 'Начать знакомство'."""
        query = update.callback_query
        await query.answer()

        text = (
            "📏 <b>Шаг 1 из 5 — Твои данные</b>\n\n"
            "Напиши в ответ одним сообщением:\n"
            "<b>Возраст Рост Вес</b>\n\n"
            "Например:\n"
            "<code>30 180 85</code>\n"
            "<i>(30 лет, 180 см, 85 кг)</i>"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return STATE_AGE_HEIGHT_WEIGHT

    async def process_age_height_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ввода возраста, роста и веса."""
        user_input = update.message.text.strip()
        parsed = parse_physical_data(user_input)

        if not parsed:
            await update.message.reply_text(
                "❌ Нужно три числа через пробел. Попробуй ещё раз.\n"
                "<i>Например: 30 180 85</i>",
                parse_mode="HTML"
            )
            return STATE_AGE_HEIGHT_WEIGHT

        age, height, weight = parsed

        # Валидация
        if age < 14 or age > 100:
            await update.message.reply_text("❌ Возраст должен быть от 14 до 100 лет.")
            return STATE_AGE_HEIGHT_WEIGHT
        if height < 120 or height > 250:
            await update.message.reply_text("❌ Рост должен быть от 120 до 250 см.")
            return STATE_AGE_HEIGHT_WEIGHT
        if weight < 30 or weight > 300:
            await update.message.reply_text("❌ Вес должен быть от 30 до 300 кг.")
            return STATE_AGE_HEIGHT_WEIGHT

        # Сохраняем в context.user_data
        context.user_data["reg_age"] = age
        context.user_data["reg_height"] = height
        context.user_data["reg_weight"] = weight

        text = (
            f"✅ <b>Данные приняты</b>\n\n"
            f"Возраст: <b>{age} лет</b>\n"
            f"Рост: <b>{height} см</b>\n"
            f"Вес: <b>{weight} кг</b>\n\n"
            f"Всё верно?"
        )

        await update.message.reply_text(
            text,
            reply_markup=get_confirm_retry_keyboard(),
            parse_mode="HTML"
        )
        return STATE_AGE_HEIGHT_WEIGHT

    async def confirm_physical(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение физических данных, переход к активности."""
        query = update.callback_query
        await query.answer()

        text = (
            "🏃 <b>Шаг 2 из 5 — Активность</b>\n\n"
            "Оцени свою повседневную активность (без учёта тренировок)."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_activity_keyboard(),
            parse_mode="HTML"
        )
        return STATE_ACTIVITY

    async def retry_physical(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Повторный ввод физических данных."""
        query = update.callback_query
        await query.answer()

        text = (
            "📏 <b>Шаг 1 из 5 — Твои данные</b>\n\n"
            "Напиши в ответ одним сообщением:\n"
            "<b>Возраст Рост Вес</b>\n\n"
            "Например:\n"
            "<code>30 180 85</code>"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return STATE_AGE_HEIGHT_WEIGHT

    # ========== ШАГ 2: Активность ==========

    async def process_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора уровня активности."""
        query = update.callback_query
        await query.answer()

        activity_value = query.data.replace("reg_activity_", "")
        activity = ActivityLevel(activity_value)
        context.user_data["reg_activity"] = activity

        text = (
            f"✅ <b>Активность выбрана</b>\n\n"
            f"Уровень: <b>{ACTIVITY_NAMES[activity]}</b>\n\n"
            f"Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_retry_keyboard(),
            parse_mode="HTML"
        )
        return STATE_ACTIVITY

    async def confirm_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение активности, переход к цели."""
        query = update.callback_query
        await query.answer()

        text = (
            "🎯 <b>Шаг 3 из 5 — Твоя цель</b>\n\n"
            "К чему стремимся в ближайшие месяцы?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_goal_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GOAL

    async def retry_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Повторный выбор активности."""
        query = update.callback_query
        await query.answer()

        text = (
            "🏃 <b>Шаг 2 из 5 — Активность</b>\n\n"
            "Оцени свою повседневную активность (без учёта тренировок)."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_activity_keyboard(),
            parse_mode="HTML"
        )
        return STATE_ACTIVITY

    # ========== ШАГ 3: Цель ==========

    async def process_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора цели."""
        query = update.callback_query
        await query.answer()

        goal_value = query.data.replace("reg_goal_", "")
        goal = Goal(goal_value)
        context.user_data["reg_goal"] = goal

        text = (
            f"✅ <b>Цель выбрана</b>\n\n"
            f"Цель: <b>{GOAL_NAMES[goal]}</b>\n\n"
            f"Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_retry_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GOAL

    async def confirm_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение цели, переход к темпу или полу."""
        query = update.callback_query
        await query.answer()

        goal = context.user_data["reg_goal"]

        if goal == Goal.MAINTAIN:
            # Для поддержания веса темп не нужен, сразу к полу
            text = (
                "👤 <b>Шаг 4 из 4 — Пол</b>\n\n"
                "Нужно для более точного расчёта калорий."
            )
            await query.edit_message_text(
                text,
                reply_markup=get_gender_keyboard(),
                parse_mode="HTML"
            )
            return STATE_GENDER
        else:
            # Для похудения/набора нужен темп
            text = (
                "⏱️ <b>Шаг 4 из 5 — Скорость</b>\n\n"
                "Как быстро хочешь двигаться к цели?"
            )
            await query.edit_message_text(
                text,
                reply_markup=get_pace_keyboard(goal),
                parse_mode="HTML"
            )
            return STATE_PACE

    async def retry_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Повторный выбор цели."""
        query = update.callback_query
        await query.answer()

        text = (
            "🎯 <b>Шаг 3 из 5 — Твоя цель</b>\n\n"
            "К чему стремимся в ближайшие месяцы?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_goal_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GOAL

    # ========== ШАГ 4: Темп (только для Lose/Gain) ==========

    async def process_pace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора темпа."""
        query = update.callback_query
        await query.answer()

        pace_value = query.data.replace("reg_pace_", "")
        pace = Pace(pace_value)
        context.user_data["reg_pace"] = pace

        goal = context.user_data["reg_goal"]
        names = PACE_NAMES_GAIN if goal == Goal.GAIN else PACE_NAMES

        text = (
            f"✅ <b>Темп выбран</b>\n\n"
            f"Скорость: <b>{names[pace]}</b>\n\n"
            f"Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_retry_keyboard(),
            parse_mode="HTML"
        )
        return STATE_PACE

    async def confirm_pace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение темпа, переход к полу."""
        query = update.callback_query
        await query.answer()

        text = (
            "👤 <b>Шаг 5 из 5 — Пол</b>\n\n"
            "Нужно для более точного расчёта калорий."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_gender_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GENDER

    async def retry_pace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Повторный выбор темпа."""
        query = update.callback_query
        await query.answer()

        goal = context.user_data["reg_goal"]

        text = (
            "⏱️ <b>Шаг 4 из 5 — Скорость</b>\n\n"
            "Как быстро хочешь двигаться к цели?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_pace_keyboard(goal),
            parse_mode="HTML"
        )
        return STATE_PACE

    # ========== ШАГ 5: Пол ==========

    async def process_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора пола."""
        query = update.callback_query
        await query.answer()

        gender_value = query.data.replace("reg_gender_", "")
        gender = Gender(gender_value)
        context.user_data["reg_gender"] = gender

        text = (
            f"✅ <b>Пол выбран</b>\n\n"
            f"Пол: <b>{GENDER_NAMES[gender]}</b>\n\n"
            f"Всё верно?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_confirm_retry_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GENDER

    async def confirm_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение пола и завершение регистрации."""
        query = update.callback_query
        await query.answer()

        return await self._complete_registration(update, context)

    async def retry_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Повторный выбор пола."""
        query = update.callback_query
        await query.answer()

        text = (
            "👤 <b>Шаг 5 из 5 — Пол</b>\n\n"
            "Нужно для более точного расчёта калорий."
        )

        await query.edit_message_text(
            text,
            reply_markup=get_gender_keyboard(),
            parse_mode="HTML"
        )
        return STATE_GENDER

    # ========== Завершение ==========

    async def _complete_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Завершение регистрации, сохранение в БД, показ результата."""
        query = update.callback_query

        user = update.effective_user

        # Собираем данные
        age = context.user_data["reg_age"]
        height = context.user_data["reg_height"]
        weight = context.user_data["reg_weight"]
        activity = context.user_data["reg_activity"]
        goal = context.user_data["reg_goal"]
        pace = context.user_data.get("reg_pace")
        gender = context.user_data["reg_gender"]

        # Расчёт КБЖУ
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        target_kcal = calculate_target_kcal(tdee, goal, pace)
        macros = calculate_macros(target_kcal, weight, goal)

        # Сохраняем пользователя
        user_id = await self.user_repo.create(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Сохраняем профиль
        profile_data = {
            "age": age,
            "height_cm": height,
            "gender": gender.value,
            "activity_level": activity.value,
            "goal": goal.value,
            "pace": pace.value if pace else None,
            "bmr": bmr,
            "daily_kcal": target_kcal,
            "daily_protein_g": macros["protein_g"],
            "daily_fat_g": macros["fat_g"],
            "daily_carbs_g": macros["carbs_g"],
        }
        await self.user_repo.save_profile(user_id, profile_data)

        # Сохраняем в контекст для быстрого доступа
        context.user_data["user_id"] = user_id
        context.user_data["daily_kcal"] = target_kcal
        context.user_data["macros"] = macros

        # Удаляем состояние регистрации
        await self.state_repo.delete(user.id)

        # Очищаем временные данные
        for key in ["reg_age", "reg_height", "reg_weight", "reg_activity",
                    "reg_goal", "reg_pace", "reg_gender"]:
            context.user_data.pop(key, None)

        # handlers/registration/handlers.py - в _complete_registration

        text = (
            "🎉 <b>Профиль создан! Спасибо!</b>\n\n"
            "Я рассчитал твою суточную норму калорий и нутриентов специально под твою цель.\n\n"
            "Вот твои ориентиры на каждый день:\n\n"
            "─────────────────\n"
            f"🔥 <b>Калории: {target_kcal} ккал</b>\n"
            f"🍗 <b>Белки: {macros['protein_g']} г</b>\n"
            f"🥑 <b>Жиры: {macros['fat_g']} г</b>\n"
            f"🍚 <b>Углеводы: {macros['carbs_g']} г</b>\n"
            "─────────────────\n\n"
            "<i>⚠️ Важно: любые формулы расчёта имеют погрешность ±10%.\n"
            "Рекомендуется отслеживать динамику 2-3 недели и при необходимости\n"
            "скорректировать нормы в настройках.</i>\n\n"
            "Эти цифры будут плавно корректироваться вместе с изменением твоего веса.\n\n"
            "Теперь просто нажимай кнопки и рассказывай мне, что ты ел и как тренировался.\n\n"
            "Готов начать?"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_complete_keyboard(),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    # ========== Отмена ==========

    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена регистрации."""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(
                "❌ Регистрация отменена.\n"
                "Ты можешь начать заново в любой момент — просто напиши /start."
            )
        else:
            await update.message.reply_text(
                "❌ Регистрация отменена.\n"
                "Ты можешь начать заново в любой момент — просто напиши /start."
            )

        # Очищаем временные данные
        for key in list(context.user_data.keys()):
            if key.startswith("reg_"):
                context.user_data.pop(key, None)

        user = update.effective_user
        await self.state_repo.delete(user.id)

        return ConversationHandler.END


# handlers/registration/handlers.py — в конце файла

def get_registration_conversation_handler(db: Database) -> ConversationHandler:
    """Создаёт ConversationHandler для регистрации."""
    handlers = RegistrationHandlers(db)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.start_registration, pattern="^reg_start$")
        ],
        states={
            STATE_AGE_HEIGHT_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_age_height_weight),
                CallbackQueryHandler(handlers.confirm_physical, pattern="^reg_confirm$"),
                CallbackQueryHandler(handlers.retry_physical, pattern="^reg_retry$"),
            ],
            STATE_ACTIVITY: [
                CallbackQueryHandler(handlers.process_activity, pattern="^reg_activity_"),
                CallbackQueryHandler(handlers.confirm_activity, pattern="^reg_confirm$"),
                CallbackQueryHandler(handlers.retry_activity, pattern="^reg_retry$"),
            ],
            STATE_GOAL: [
                CallbackQueryHandler(handlers.process_goal, pattern="^reg_goal_"),
                CallbackQueryHandler(handlers.confirm_goal, pattern="^reg_confirm$"),
                CallbackQueryHandler(handlers.retry_goal, pattern="^reg_retry$"),
            ],
            STATE_PACE: [
                CallbackQueryHandler(handlers.process_pace, pattern="^reg_pace_"),
                CallbackQueryHandler(handlers.confirm_pace, pattern="^reg_confirm$"),
                CallbackQueryHandler(handlers.retry_pace, pattern="^reg_retry$"),
            ],
            STATE_GENDER: [
                CallbackQueryHandler(handlers.process_gender, pattern="^reg_gender_"),
                CallbackQueryHandler(handlers.confirm_gender, pattern="^reg_confirm$"),
                CallbackQueryHandler(handlers.retry_gender, pattern="^reg_retry$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.cancel_registration, pattern="^reg_cancel$"),
            MessageHandler(filters.COMMAND, handlers.cancel_registration),
        ],
        allow_reentry=False,
        per_chat=True,
        per_user=True,
        per_message=False,  # <-- Добавить эту строку
    )