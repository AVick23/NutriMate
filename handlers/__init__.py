# handlers/__init__.py
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from db.database import Database
from handlers.start import start_command, help_command, show_diary, show_more_menu
from handlers.registration import get_registration_conversation_handler
from handlers.add_food import get_add_food_conversation_handler
from handlers.history_of_add import get_history_conversation_handler  # добавляем импорт


def register_all_handlers(app: Application, db: Database) -> None:
    """Регистрирует все обработчики в приложении."""

    # Команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Callback для показа дневника
    app.add_handler(CallbackQueryHandler(show_diary, pattern="^diary_show$"))
    app.add_handler(CallbackQueryHandler(show_diary, pattern="^diary_back$"))
    
    # Callback для показа меню дополнительных действий
    app.add_handler(CallbackQueryHandler(show_more_menu, pattern="^diary_more$"))

    # ConversationHandler для регистрации
    app.add_handler(get_registration_conversation_handler(db))

    # ConversationHandler для добавления еды
    app.add_handler(get_add_food_conversation_handler(db))
    
    # ConversationHandler для истории записей
    app.add_handler(get_history_conversation_handler(db))