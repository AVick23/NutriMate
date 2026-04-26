# handlers/__init__.py
from telegram.ext import Application, CommandHandler

from db.database import Database
from start import start_command, help_command
from handlers.registration import get_registration_conversation_handler
from handlers.add_food import get_add_food_conversation_handler


def register_all_handlers(app: Application, db: Database) -> None:
    """Регистрирует все обработчики в приложении."""

    # Команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # ConversationHandler для регистрации
    app.add_handler(get_registration_conversation_handler(db))

    # ConversationHandler для добавления еды
    app.add_handler(get_add_food_conversation_handler(db))

    # TODO: Добавить остальные обработчики