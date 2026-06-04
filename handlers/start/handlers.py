# handlers/start/handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db.database import Database
from db.models import UserRepository, DailyStatsRepository
from handlers.registration.keyboards import get_start_registration_keyboard
from handlers.start.utils import format_diary_compact, get_main_diary_keyboard
from handlers.water.utils import calculate_water_goal


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    db: Database = context.bot_data["db"]
    user_repo = UserRepository(db)
    stats_repo = DailyStatsRepository(db)

    is_registered = await user_repo.exists(user.id)

    if is_registered:
        user_id = await user_repo.get_user_id(user.id)
        profile = await user_repo.get_profile(user_id)
        today_stats = await stats_repo.get_today_stats(user_id)

        # Рассчитываем норму воды
        water_goal_ml = calculate_water_goal(profile.get("weight_kg", 70), profile["gender"])
        water_current_ml = today_stats.get("water_ml", 0)

        name = user.first_name or "друг"
        greeting = f"🥑 <b>С возвращением, {name}!</b>"

        diary_text = format_diary_compact(
            daily_kcal=profile["daily_kcal"],
            current_kcal=today_stats.get("kcal", 0),
            protein_goal=profile["daily_protein_g"],
            current_protein=today_stats.get("protein", 0),
            fat_goal=profile["daily_fat_g"],
            current_fat=today_stats.get("fat", 0),
            carbs_goal=profile["daily_carbs_g"],
            current_carbs=today_stats.get("carbs", 0),
            water_current_ml=water_current_ml,
            water_goal_ml=water_goal_ml,
        )

        text = f"{greeting}\n\n{diary_text}"

        await update.message.reply_text(
            text,
            reply_markup=get_main_diary_keyboard(),
            parse_mode="HTML"
        )
    else:
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
        "<b>Основные действия:</b>\n\n"
        "• <b>🍽️ Еда</b> — добавь приём пищи: фото, штрихкод, текст или избранное.\n"
        "• <b>💧 Вода</b> — быстрый +1 стакан, счётчик обновится сразу.\n"
        "• <b>⋯</b> — меню дополнительных действий: тренировки, вес, прогресс, избранное, история, настройки.\n\n"
        "<b>Лайфхаки:</b>\n"
        "• Просто пришли <b>фото еды</b> — я попробую распознать.\n"
        "• Напиши <b>текст</b> вида «омлет 200г» — я найду калорийность.\n"
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


async def show_diary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает дневник по callback_data='diary_show'."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    db: Database = context.bot_data["db"]
    user_repo = UserRepository(db)
    stats_repo = DailyStatsRepository(db)

    is_registered = await user_repo.exists(user.id)

    if not is_registered:
        await query.edit_message_text(
            "❌ Сначала нужно пройти регистрацию. Отправь команду /start",
            parse_mode="HTML"
        )
        return

    user_id = await user_repo.get_user_id(user.id)
    profile = await user_repo.get_profile(user_id)
    today_stats = await stats_repo.get_today_stats(user_id)

    # Рассчитываем норму воды
    water_goal_ml = calculate_water_goal(profile.get("weight_kg", 70), profile["gender"])
    water_current_ml = today_stats.get("water_ml", 0)

    name = user.first_name or "друг"
    greeting = f"🥑 <b>С возвращением, {name}!</b>"

    diary_text = format_diary_compact(
        daily_kcal=profile["daily_kcal"],
        current_kcal=today_stats.get("kcal", 0),
        protein_goal=profile["daily_protein_g"],
        current_protein=today_stats.get("protein", 0),
        fat_goal=profile["daily_fat_g"],
        current_fat=today_stats.get("fat", 0),
        carbs_goal=profile["daily_carbs_g"],
        current_carbs=today_stats.get("carbs", 0),
        water_current_ml=water_current_ml,
        water_goal_ml=water_goal_ml,
    )

    text = f"{greeting}\n\n{diary_text}"

    await query.edit_message_text(
        text,
        reply_markup=get_main_diary_keyboard(),
        parse_mode="HTML"
    )


async def show_more_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню дополнительных действий по нажатию на кнопку ⋯
    """
    query = update.callback_query
    await query.answer()

    text = "Что хочешь сделать?"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ Тренировка", callback_data="training_add")],
        [InlineKeyboardButton("📏 Замеры тела", callback_data="measurements_menu")],
        [InlineKeyboardButton("📈 Прогресс", callback_data="progress_show")],
        [InlineKeyboardButton("📜 История", callback_data="history_show")],
        [InlineKeyboardButton("⭐ Избранное", callback_data="favorites_show")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_show")],
        [InlineKeyboardButton("← Назад", callback_data="diary_show")],
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )