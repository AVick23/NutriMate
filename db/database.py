"""
Модуль работы с базой данных SQLite через aiosqlite.
Содержит полные схемы всех таблиц, включая новую систему метрик.
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
        """Проверяет, нужна ли миграция таблицы favorites."""
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'"
        )
        if not await cursor.fetchone():
            return False

        cursor = await conn.execute("PRAGMA index_list(favorites)")
        indexes = await cursor.fetchall()

        for idx in indexes:
            if not idx["unique"]:
                continue
            idx_name = idx["name"]
            cursor = await conn.execute(f"PRAGMA index_info({idx_name})")
            idx_cols = await cursor.fetchall()
            col_names = [c["name"] for c in idx_cols]

            if "amount_g" in col_names and "barcode" not in col_names:
                return True

        return False

    async def _migrate_favorites(self, conn: aiosqlite.Connection) -> None:
        """Мигрирует таблицу favorites со старой схемы на новую."""
        logger.info("🔄 Начинаю миграцию таблицы favorites...")

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

        await conn.execute("""
            INSERT INTO favorites_new 
            (user_id, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, 
             barcode, times_used, created_at, updated_at)
            SELECT 
                user_id, food_name, MAX(amount_g) as amount_g,
                MAX(kcal) as kcal, MAX(protein_g) as protein_g,
                MAX(fat_g) as fat_g, MAX(carbs_g) as carbs_g,
                barcode, SUM(times_used) as times_used,
                MIN(created_at) as created_at, MAX(updated_at) as updated_at
            FROM favorites
            GROUP BY user_id, food_name, barcode
        """)

        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM favorites")
        old_count = (await cursor.fetchone())["cnt"]
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM favorites_new")
        new_count = (await cursor.fetchone())["cnt"]

        await conn.execute("DROP TABLE favorites")
        await conn.execute("ALTER TABLE favorites_new RENAME TO favorites")

        duplicates_merged = old_count - new_count
        logger.info(
            f"✅ Миграция favorites завершена: "
            f"было {old_count} записей, стало {new_count} "
            f"(объединено дубликатов: {duplicates_merged})"
        )

    async def init_tables(self) -> None:
        """Создаёт все таблицы, если их нет. Включает миграции."""
        async with self.connection() as conn:
            # ========== ОСНОВНЫЕ ТАБЛИЦЫ (существующие) ==========
            
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

            # Таблица favorites
            needs_migration = await self._check_favorites_needs_migration(conn)
            if needs_migration:
                await self._migrate_favorites(conn)
            else:
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

            # Таблица measurement_types (из модуля замеров)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS measurement_types (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            """)

            # Таблица body_measurements
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS body_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    measurement_type_id INTEGER NOT NULL,
                    value REAL NOT NULL,
                    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (measurement_type_id) REFERENCES measurement_types(id)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_body_measurements_user_type_date ON body_measurements(user_id, measurement_type_id, measured_at)"
            )

            # Вставляем типы замеров, если их нет
            await conn.execute("""
                INSERT OR IGNORE INTO measurement_types (id, name, display_name, unit, sort_order) VALUES
                (1, 'weight', 'Вес', 'кг', 1),
                (2, 'waist', 'Талия', 'см', 2),
                (3, 'hips', 'Бёдра', 'см', 3),
                (4, 'chest', 'Грудь', 'см', 4),
                (5, 'arm', 'Рука (бицепс)', 'см', 5),
                (6, 'thigh', 'Бедро', 'см', 6)
            """)

            # ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ СИСТЕМЫ МЕТРИК И АНАЛИТИКИ ==========

            # 1. Таблица daily_metrics — сырые метрики, вводимые пользователем
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    metric_date DATE NOT NULL,
                    
                    -- Сон
                    sleep_hours REAL,
                    sleep_quality INTEGER,
                    sleep_awakenings INTEGER,
                    
                    -- Энергия
                    energy_morning INTEGER,
                    energy_evening INTEGER,
                    
                    -- Стресс
                    stress_level INTEGER,
                    
                    -- Активность
                    steps INTEGER,
                    hours_on_feet REAL,
                    
                    -- Тренировка
                    workout_type TEXT,
                    workout_duration INTEGER,
                    workout_intensity INTEGER,
                    
                    -- Голод (опционально)
                    hunger_before INTEGER,
                    hunger_after INTEGER,
                    
                    -- Пищеварение (Бристольская шкала)
                    digestion_bristol INTEGER,
                    
                    -- Женский цикл
                    cycle_day INTEGER,
                    
                    -- Метаданные
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, metric_date)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_user_date ON daily_metrics(user_id, metric_date)"
            )

            # 2. Таблица daily_aggregates — рассчитанные агрегаты за день
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_aggregates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    aggregate_date DATE NOT NULL,
                    
                    -- Питание (из meals)
                    total_kcal INTEGER DEFAULT 0,
                    total_protein_g REAL DEFAULT 0,
                    total_fat_g REAL DEFAULT 0,
                    total_carbs_g REAL DEFAULT 0,
                    meal_count INTEGER DEFAULT 0,
                    eating_window_hours REAL,
                    last_meal_hour INTEGER,
                    
                    -- Вода (из water_logs)
                    water_ml INTEGER DEFAULT 0,
                    
                    -- Замеры тела (из body_measurements, последние за день)
                    weight_kg REAL,
                    waist_cm REAL,
                    hips_cm REAL,
                    chest_cm REAL,
                    arm_cm REAL,
                    thigh_cm REAL,
                    
                    -- Сон (из daily_metrics)
                    sleep_hours REAL,
                    sleep_quality INTEGER,
                    sleep_awakenings INTEGER,
                    
                    -- Энергия
                    energy_morning INTEGER,
                    energy_evening INTEGER,
                    avg_energy REAL,
                    
                    -- Стресс
                    stress_level INTEGER,
                    
                    -- Активность
                    steps INTEGER,
                    hours_on_feet REAL,
                    workout_kcal_burned INTEGER,
                    
                    -- Рассчитанные модификаторы TDEE
                    base_tdee INTEGER,
                    sleep_modifier REAL,
                    energy_modifier REAL,
                    stress_modifier REAL,
                    activity_modifier REAL,
                    window_modifier REAL,
                    workout_bonus INTEGER,
                    adjusted_tdee INTEGER,
                    
                    -- Confidence score (0-100)
                    confidence_score INTEGER DEFAULT 100,
                    
                    -- Метаданные
                    recomputed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, aggregate_date)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_aggregates_user_date ON daily_aggregates(user_id, aggregate_date)"
            )

            # 3. Таблица user_patterns — обнаруженные паттерны (корреляции)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    
                    -- Тип паттерна
                    pattern_type TEXT CHECK(pattern_type IN ('correlation', 'conditional')) NOT NULL,
                    
                    -- Метрики
                    metric_x TEXT NOT NULL,
                    metric_y TEXT NOT NULL,
                    condition_metric TEXT,
                    condition_operator TEXT,
                    condition_value REAL,
                    
                    -- Статистика
                    correlation_r REAL,
                    p_value REAL,
                    lag_days INTEGER DEFAULT 0,
                    sample_size INTEGER,
                    
                    -- Эффект
                    effect_text TEXT,
                    effect_direction TEXT CHECK(effect_direction IN ('positive', 'negative', 'neutral')),
                    
                    -- Статус
                    is_active BOOLEAN DEFAULT 1,
                    first_detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmation_count INTEGER DEFAULT 1,
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_user_active ON user_patterns(user_id, is_active)"
            )

            # 4. Таблица modifier_history — история модификаторов для анализа
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS modifier_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    record_date DATE NOT NULL,
                    
                    sleep_modifier REAL,
                    energy_modifier REAL,
                    stress_modifier REAL,
                    activity_modifier REAL,
                    window_modifier REAL,
                    workout_bonus INTEGER,
                    adjusted_tdee INTEGER,
                    
                    metrics_used TEXT,
                    missing_metrics TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_modifier_history_user_date ON modifier_history(user_id, record_date)"
            )

            # 5. Таблица user_settings_analytics — настройки аналитики для пользователя
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_settings_analytics (
                    user_id INTEGER PRIMARY KEY,
                    
                    reminder_morning_enabled BOOLEAN DEFAULT 1,
                    reminder_morning_time TEXT DEFAULT '08:00',
                    reminder_evening_enabled BOOLEAN DEFAULT 1,
                    reminder_evening_time TEXT DEFAULT '21:00',
                    
                    collect_sleep BOOLEAN DEFAULT 1,
                    collect_energy BOOLEAN DEFAULT 1,
                    collect_stress BOOLEAN DEFAULT 1,
                    collect_steps BOOLEAN DEFAULT 1,
                    collect_workout BOOLEAN DEFAULT 1,
                    collect_hunger BOOLEAN DEFAULT 0,
                    collect_digestion BOOLEAN DEFAULT 0,
                    collect_cycle BOOLEAN DEFAULT 0,
                    
                    share_anonymous_stats BOOLEAN DEFAULT 0,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            await conn.commit()
            logger.info("✅ Все таблицы БД готовы (включая систему метрик и аналитики)")