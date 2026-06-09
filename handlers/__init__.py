from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from db import Database
from handlers.start import start_command, help_command, show_diary, show_more_menu
from handlers.registration import get_registration_conversation_handler
from handlers.add_food import get_add_food_conversation_handler
from handlers.history_of_add import get_history_conversation_handler
from handlers.water import get_water_handler
from handlers.measurements import get_measurements_handler
from handlers.settings import get_settings_handler
from handlers.favorites import get_favorites_handler
from handlers.metrics import get_metrics_conversation_handler
from handlers.training import get_training_handler  # 🎯 ДОБАВЬ ЭТУ СТРОКУ


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

    # ConversationHandler для воды
    app.add_handler(get_water_handler(db))

    # ConversationHandler для замеров тела
    app.add_handler(get_measurements_handler(db))

    # ConversationHandler для настроек
    app.add_handler(get_settings_handler(db))

    # ConversationHandler для избранного
    app.add_handler(get_favorites_handler(db))

    # ConversationHandler для метрик
    app.add_handler(get_metrics_conversation_handler(db))
    
    # 🎯 НОВЫЙ: ConversationHandler для тренировок
    app.add_handler(get_training_handler(db))  # ДОБАВЬ ЭТУ СТРОКУ