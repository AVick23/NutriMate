# db/database.py
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import os

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

    async def init_tables(self) -> None:
        """Создаёт таблицы, если их нет."""
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

            # Таблица registration_state (временные данные регистрации)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS registration_state (
                    telegram_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.commit()
            
            # db/database.py — добавить в init_tables()

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

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, DATE(eaten_at))")

            # Таблица favorites
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
                    UNIQUE(user_id, food_name, amount_g)
                )
            """)

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

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_water_user_date ON water_logs(user_id, DATE(logged_at))")