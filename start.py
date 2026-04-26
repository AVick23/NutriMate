# start.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db.database import Database
from db.models import UserRepository
from handlers.registration.keyboards import get_start_registration_keyboard


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    db: Database = context.bot_data["db"]
    user_repo = UserRepository(db)

    # Проверяем, зарегистрирован ли пользователь
    is_registered = await user_repo.exists(user.id)

    if is_registered:
        # Пользователь уже зарегистрирован — показываем дневник
        user_id = await user_repo.get_user_id(user.id)
        profile = await user_repo.get_profile(user_id)

        # TODO: Показывать реальные данные из БД (за день)
        daily_kcal = profile["daily_kcal"]
        protein = profile["daily_protein_g"]
        fat = profile["daily_fat_g"]
        carbs = profile["daily_carbs_g"]

        text = (
            f"🥑 <b>С возвращением, {user.first_name or 'друг'}!</b>\n\n"
            f"📅 <b>Сегодня</b>\n\n"
            f"─────────────────\n"
            f"🔥 <b>Калории</b>\n"
            f"<b>0 / {daily_kcal} ккал</b>\n"
            f"▱▱▱▱▱▱▱▱▱▱ <b>0%</b>\n\n"
            f"🍗 <b>Белки</b>\n"
            f"<b>0 / {protein} г</b>\n"
            f"▱▱▱▱▱▱▱▱▱▱ <b>0%</b>\n\n"
            f"🥑 <b>Жиры</b>\n"
            f"<b>0 / {fat} г</b>\n"
            f"▱▱▱▱▱▱▱▱▱▱ <b>0%</b>\n\n"
            f"🍚 <b>Углеводы</b>\n"
            f"<b>0 / {carbs} г</b>\n"
            f"▱▱▱▱▱▱▱▱▱▱ <b>0%</b>\n\n"
            f"💧 <b>Вода</b>\n"
            f"<b>0 / 8 стаканов</b>\n"
            f"▱▱▱▱▱▱▱▱ <b>0%</b>\n"
            f"─────────────────"
        )

        # start.py — в клавиатуре дневника

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍽️ Добавить еду", callback_data="food_select_method")],  # <-- Изменить здесь
            [InlineKeyboardButton("🏋️ Записать тренировку", callback_data="training_add")],
            [
                InlineKeyboardButton("⚖️ Записать вес", callback_data="weight_add"),
                InlineKeyboardButton("💧 + Стакан воды", callback_data="water_add")
            ],
            [
                InlineKeyboardButton("📊 Прогресс", callback_data="progress_show"),
                InlineKeyboardButton("⭐️ Избранное", callback_data="favorites_show")
            ],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_show")],
        ])

        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    else:
        # Пользователь не зарегистрирован — начинаем регистрацию
        text = (
            "🥑 <b>Добро пожаловать в NutriMate!</b>\n\n"
            "Привет! Я — простой и удобный дневник питания и тренировок.\n\n"
            "Здесь нет ничего лишнего:\n"
            "• Не нужно заполнять сложные формы\n"
            "• Не будет запутанных графиков\n"
            "• Только кнопки и понятные подсказки\n\n"
            "Давай настроим всё под тебя. Это займёт меньше минуты."
        )

        await update.message.reply_text(
            text,
            reply_markup=get_start_registration_keyboard(),
            parse_mode="HTML"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    text = (
        "📖 <b>Как пользоваться NutriMate</b>\n\n"
        "Я работаю через кнопки. Тебе не нужно запоминать команды — "
        "просто нажимай на варианты под сообщениями.\n\n"
        "<b>Основные сценарии:</b>\n\n"
        "• <b>Еда</b> — нажми «Добавить еду» и выбери способ: фото, штрихкод, текст или избранное.\n"
        "• <b>Тренировка</b> — нажми «Записать тренировку» и укажи тип и интенсивность.\n"
        "• <b>Вес</b> — нажми «Записать вес» и просто введи цифру.\n"
        "• <b>Вода</b> — нажми «+ Стакан воды», счётчик обновится сразу.\n\n"
        "<b>Дополнительно:</b>\n"
        "• Ты можешь просто прислать мне <b>фото еды</b> — я попробую распознать.\n"
        "• Ты можешь написать <b>текст</b> вида «омлет 200г» — я найду калорийность.\n\n"
        "<b>Настройки и прогресс:</b>\n"
        "• «Прогресс» — динамика веса и график.\n"
        "• «Избранное» — быстрый доступ к частым блюдам.\n"
        "• «Настройки» — изменить цель, данные или уведомления."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📔 Открыть дневник", callback_data="diary_show")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_show")],
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )