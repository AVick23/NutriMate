# main.py
import logging

from telegram.ext import Application

from config import config
from db import Database
from handlers import register_all_handlers

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG if config.DEBUG else logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Асинхронная инициализация после создания приложения."""
    db = Database(config.DB_PATH)
    await db.init_tables()
    logger.info(f"База данных инициализирована: {config.DB_PATH}")

    app.bot_data["db"] = db
    register_all_handlers(app, db)
    logger.info("Обработчики зарегистрированы")


def main() -> None:
    """Точка входа в приложение."""
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    logger.info("Бот запущен")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()