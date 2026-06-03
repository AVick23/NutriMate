# handlers/__init__.py
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from db.database import Database
from handlers.start import start_command, help_command, show_diary
from handlers.start import get_diary_more_keyboard  # если нужно где-то использовать
from handlers.registration import get_registration_conversation_handler
from handlers.add_food import get_add_food_conversation_handler


def register_all_handlers(app: Application, db: Database) -> None:
    """Регистрирует все обработчики в приложении."""

    # Команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Callback для показа дневника
    app.add_handler(CallbackQueryHandler(show_diary, pattern="^diary_show$"))
    app.add_handler(CallbackQueryHandler(show_diary, pattern="^diary_back$"))

    # ConversationHandler для регистрации
    app.add_handler(get_registration_conversation_handler(db))

    # ConversationHandler для добавления еды
    app.add_handler(get_add_food_conversation_handler(db))

    # TODO: Добавить остальные обработчики (вода, тренировки, вес и т.д.)