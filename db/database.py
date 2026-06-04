"""
Модуль работы с базой данных SQLite через aiosqlite.
"""
import aiosqlite
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Создаёт директорию для БД, если её нет."""
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Получить соединение с БД."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = aiosqlite.Row
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Транзакция с автоматическим коммитом/откатом."""
        async with self.connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def _check_favorites_needs_migration(self, conn: aiosqlite.Connection) -> bool:
        """
        Проверяет, нужна ли миграция таблицы favorites.
        Возвращает True, если таблица существует со старой схемой
        (UNIQUE по user_id, food_name, amount_g).
        """
        # Проверяем существование таблицы
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'"
        )
        if not await cursor.fetchone():
            return False  # таблицы нет — просто создадим новую

        # Проверяем индексы таблицы
        cursor = await conn.execute("PRAGMA index_list(favorites)")
        indexes = await cursor.fetchall()

        for idx in indexes:
            if not idx["unique"]:
                continue
            idx_name = idx["name"]
            # Получаем колонки этого индекса
            cursor = await conn.execute(f"PRAGMA index_info({idx_name})")
            idx_cols = await cursor.fetchall()
            col_names = [c["name"] for c in idx_cols]

            # Старая схема: amount_g в UNIQUE, barcode — нет
            if "amount_g" in col_names and "barcode" not in col_names:
                return True

        return False

    async def _migrate_favorites(self, conn: aiosqlite.Connection) -> None:
        """
        Мигрирует таблицу favorites со старой схемы на новую.
        Объединяет дубликаты (user_id, food_name) — суммирует times_used.
        """
        logger.info("🔄 Начинаю миграцию таблицы favorites...")

        # 1. Создаём новую таблицу с правильной схемой
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                food_name TEXT NOT NULL,
                amount_g REAL NOT NULL,
                kcal INTEGER NOT NULL,
                protein_g REAL NOT NULL,
                fat_g REAL NOT NULL,
                carbs_g REAL NOT NULL,
                barcode TEXT,
                times_used INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, food_name, barcode)
            )
        """)

        # 2. Переносим данные, объединяя дубликаты
        # Для каждого (user_id, food_name, barcode):
        # - times_used = SUM
        # - amount_g, kcal, ... = MAX (последнее использованное значение)
        # - created_at = MIN (самая старая запись)
        # - updated_at = MAX (самая новая)
        await conn.execute("""
            INSERT INTO favorites_new 
            (user_id, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, 
             barcode, times_used, created_at, updated_at)
            SELECT 
                user_id, 
                food_name, 
                MAX(amount_g) as amount_g,
                MAX(kcal) as kcal,
                MAX(protein_g) as protein_g,
                MAX(fat_g) as fat_g,
                MAX(carbs_g) as carbs_g,
                barcode,
                SUM(times_used) as times_used,
                MIN(created_at) as created_at,
                MAX(updated_at) as updated_at
            FROM favorites
            GROUP BY user_id, food_name, barcode
        """)

        # 3. Считаем, сколько было дубликатов
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM favorites")
        old_count = (await cursor.fetchone())["cnt"]

        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM favorites_new")
        new_count = (await cursor.fetchone())["cnt"]

        # 4. Удаляем старую таблицу
        await conn.execute("DROP TABLE favorites")

        # 5. Переименовываем новую
        await conn.execute("ALTER TABLE favorites_new RENAME TO favorites")

        duplicates_merged = old_count - new_count
        logger.info(
            f"✅ Миграция favorites завершена: "
            f"было {old_count} записей, стало {new_count} "
            f"(объединено дубликатов: {duplicates_merged})"
        )

    async def init_tables(self) -> None:
        """Создаёт таблицы, если их нет. Включает миграцию favorites."""
        async with self.connection() as conn:
            # Таблица users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица user_profiles
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    age INTEGER NOT NULL,
                    height_cm INTEGER NOT NULL,
                    gender TEXT CHECK(gender IN ('male', 'female')) NOT NULL,
                    activity_level TEXT CHECK(activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')) NOT NULL,
                    goal TEXT CHECK(goal IN ('lose', 'maintain', 'gain')) NOT NULL,
                    pace TEXT CHECK(pace IN ('slow', 'steady', 'fast')),
                    bmr INTEGER NOT NULL,
                    daily_kcal INTEGER NOT NULL,
                    daily_protein_g INTEGER NOT NULL,
                    daily_fat_g INTEGER NOT NULL,
                    daily_carbs_g INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Таблица registration_state
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS registration_state (
                    telegram_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 🎯 Проверяем, нужна ли миграция favorites
            needs_migration = await self._check_favorites_needs_migration(conn)
            if needs_migration:
                await self._migrate_favorites(conn)
            else:
                # Таблицы нет или она уже с новой схемой — просто создаём
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        food_name TEXT NOT NULL,
                        amount_g REAL NOT NULL,
                        kcal INTEGER NOT NULL,
                        protein_g REAL NOT NULL,
                        fat_g REAL NOT NULL,
                        carbs_g REAL NOT NULL,
                        barcode TEXT,
                        times_used INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        UNIQUE(user_id, food_name, barcode)
                    )
                """)

            # Таблица meals
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    meal_type TEXT CHECK(meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')) NOT NULL,
                    food_name TEXT NOT NULL,
                    amount_g REAL NOT NULL,
                    kcal INTEGER NOT NULL,
                    protein_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    barcode TEXT,
                    eaten_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, DATE(eaten_at))"
            )

            # Таблица water_logs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS water_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount_ml INTEGER NOT NULL DEFAULT 250,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_water_user_date ON water_logs(user_id, DATE(logged_at))"
            )

            await conn.commit()
            logger.info("✅ Таблицы БД готовы")