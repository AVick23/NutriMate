"""
Репозитории для работы с базой данных.
Содержит все классы для доступа к данным.
"""
import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple

from db.database import Database

logger = logging.getLogger(__name__)


# ============================================================
# ОСНОВНЫЕ РЕПОЗИТОРИИ (существующие)
# ============================================================

class UserRepository:
    """Репозиторий для работы с пользователями и их профилями."""
    
    def __init__(self, db: Database):
        self.db = db

    async def exists(self, telegram_id: int) -> bool:
        """Проверяет, существует ли пользователь."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def get_user_id(self, telegram_id: int) -> Optional[int]:
        """Получает user_id по telegram_id."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            return row["id"] if row else None

    async def create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> int:
        """Создаёт пользователя и возвращает его id."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """INSERT INTO users (telegram_id, username, first_name, last_name)
                   VALUES (?, ?, ?, ?)""",
                (telegram_id, username, first_name, last_name)
            )
            return cursor.lastrowid

    async def get_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает профиль пользователя по user_id."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def save_profile(self, user_id: int, profile_data: Dict[str, Any]) -> None:
        """Сохраняет или обновляет профиль пользователя."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "SELECT id FROM user_profiles WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()

            if exists:
                fields = ", ".join(f"{k} = ?" for k in profile_data.keys())
                values = list(profile_data.values()) + [user_id]
                await conn.execute(
                    f"UPDATE user_profiles SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    values
                )
            else:
                fields = ", ".join(profile_data.keys())
                placeholders = ", ".join("?" * len(profile_data))
                await conn.execute(
                    f"INSERT INTO user_profiles (user_id, {fields}) VALUES (?, {placeholders})",
                    [user_id] + list(profile_data.values())
                )


class RegistrationStateRepository:
    """Репозиторий для временного хранения состояния регистрации."""
    
    def __init__(self, db: Database):
        self.db = db

    async def save(self, telegram_id: int, state: str, data: Dict[str, Any]) -> None:
        """Сохраняет состояние регистрации."""
        async with self.db.transaction() as conn:
            await conn.execute(
                """INSERT INTO registration_state (telegram_id, state, data)
                   VALUES (?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                   state = excluded.state,
                   data = excluded.data,
                   updated_at = CURRENT_TIMESTAMP""",
                (telegram_id, state, json.dumps(data))
            )

    async def get(self, telegram_id: int) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Получает состояние и данные регистрации."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT state, data FROM registration_state WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return row["state"], json.loads(row["data"])
            return None

    async def delete(self, telegram_id: int) -> None:
        """Удаляет состояние регистрации."""
        async with self.db.transaction() as conn:
            await conn.execute(
                "DELETE FROM registration_state WHERE telegram_id = ?",
                (telegram_id,)
            )


class MealRepository:
    """Репозиторий для работы с приёмами пищи."""
    
    def __init__(self, db: Database):
        self.db = db

    async def add_meal(
        self,
        user_id: int,
        meal_type: str,
        food_name: str,
        amount_g: float,
        kcal: int,
        protein_g: float,
        fat_g: float,
        carbs_g: float,
        barcode: Optional[str] = None
    ) -> int:
        """Добавляет приём пищи."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """INSERT INTO meals 
                   (user_id, meal_type, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, barcode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, meal_type, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, barcode)
            )
            return cursor.lastrowid


class FavoritesRepository:
    """Репозиторий для работы с избранным."""
    
    def __init__(self, db: Database):
        self.db = db

    async def get_favorites(self, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        """Получает список избранных продуктов."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM favorites 
                   WHERE user_id = ? 
                   ORDER BY times_used DESC, updated_at DESC 
                   LIMIT ?""",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_favorite_by_id(
        self,
        user_id: int,
        favorite_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получает одно избранное блюдо по ID."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_favorite(
        self,
        user_id: int,
        food_name: str,
        amount_g: float,
        kcal: int,
        protein_g: float,
        fat_g: float,
        carbs_g: float,
        barcode: Optional[str] = None
    ) -> None:
        """Добавляет или обновляет избранный продукт."""
        async with self.db.transaction() as conn:
            await conn.execute(
                """INSERT INTO favorites 
                   (user_id, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, barcode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, food_name, barcode) DO UPDATE SET
                   amount_g = excluded.amount_g,
                   kcal = excluded.kcal,
                   protein_g = excluded.protein_g,
                   fat_g = excluded.fat_g,
                   carbs_g = excluded.carbs_g,
                   times_used = times_used + 1,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, barcode)
            )

    async def delete_favorite(self, user_id: int, favorite_id: int) -> bool:
        """Удаляет блюдо из избранного."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id)
            )
            return cursor.rowcount > 0

    async def clear_all(self, user_id: int) -> int:
        """Удаляет всё избранное пользователя."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM favorites WHERE user_id = ?",
                (user_id,)
            )
            return cursor.rowcount

    async def increment_usage(self, favorite_id: int) -> None:
        """Увеличивает счётчик использования."""
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE favorites SET times_used = times_used + 1 WHERE id = ?",
                (favorite_id,)
            )


class WaterRepository:
    """Репозиторий для работы с водой."""
    
    def __init__(self, db: Database):
        self.db = db

    async def add_water(self, user_id: int, amount_ml: int = 250) -> None:
        """Добавляет запись о воде."""
        async with self.db.transaction() as conn:
            await conn.execute(
                """INSERT INTO water_logs (user_id, amount_ml, logged_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (user_id, amount_ml)
            )

    async def get_today_count(self, user_id: int) -> int:
        """Возвращает количество выпитых стаканов за сегодня (250 мл = 1 стакан)."""
        today = datetime.now().strftime("%Y-%m-%d")
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT COALESCE(SUM(amount_ml), 0) as total_ml
                   FROM water_logs 
                   WHERE user_id = ? AND DATE(logged_at) = ?""",
                (user_id, today)
            )
            row = await cursor.fetchone()
            total_ml = row["total_ml"] if row else 0
            return int(total_ml / 250)


class HistoryRepository:
    """Репозиторий для работы с историей записей (еда и вода)."""
    
    def __init__(self, db: Database):
        self.db = db

    async def get_meals_for_date(
        self,
        user_id: int,
        date_str: str
    ) -> List[Dict[str, Any]]:
        """Получает все приёмы пищи за указанную дату."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT id, meal_type, food_name, amount_g, kcal, 
                          protein_g, fat_g, carbs_g, eaten_at
                   FROM meals 
                   WHERE user_id = ? AND DATE(eaten_at) = ?
                   ORDER BY eaten_at ASC""",
                (user_id, date_str)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_water_for_date(
        self,
        user_id: int,
        date_str: str
    ) -> List[Dict[str, Any]]:
        """Получает все записи о воде за указанную дату."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT id, amount_ml, logged_at
                   FROM water_logs 
                   WHERE user_id = ? AND DATE(logged_at) = ?
                   ORDER BY logged_at ASC""",
                (user_id, date_str)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_dates_with_entries(
        self,
        user_id: int,
        limit: int = 30
    ) -> List[str]:
        """Возвращает список дат (YYYY-MM-DD), за которые есть записи."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT DISTINCT DATE(eaten_at) as date
                   FROM meals 
                   WHERE user_id = ?
                   ORDER BY date DESC
                   LIMIT ?""",
                (user_id, limit)
            )
            meal_dates = await cursor.fetchall()

            cursor = await conn.execute(
                """SELECT DISTINCT DATE(logged_at) as date
                   FROM water_logs 
                   WHERE user_id = ?
                   ORDER BY date DESC
                   LIMIT ?""",
                (user_id, limit)
            )
            water_dates = await cursor.fetchall()

            dates = set()
            for row in meal_dates:
                dates.add(row["date"])
            for row in water_dates:
                dates.add(row["date"])

            return sorted(list(dates), reverse=True)


class DailyStatsRepository:
    """Репозиторий для получения статистики за день (существующий)."""
    
    def __init__(self, db: Database):
        self.db = db

    async def get_today_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику за сегодня."""
        today = datetime.now().strftime("%Y-%m-%d")

        async with self.db.connection() as conn:
            # Калории и макросы
            cursor = await conn.execute(
                """SELECT 
                   SUM(kcal) as kcal,
                   SUM(protein_g) as protein,
                   SUM(fat_g) as fat,
                   SUM(carbs_g) as carbs
                   FROM meals 
                   WHERE user_id = ? AND DATE(eaten_at) = ?""",
                (user_id, today)
            )
            meal_stats = await cursor.fetchone()

            # Вода
            cursor = await conn.execute(
                """SELECT COALESCE(SUM(amount_ml), 0) as water_ml
                   FROM water_logs 
                   WHERE user_id = ? AND DATE(logged_at) = ?""",
                (user_id, today)
            )
            water_stats = await cursor.fetchone()

            return {
                "kcal": meal_stats["kcal"] or 0,
                "protein": meal_stats["protein"] or 0,
                "fat": meal_stats["fat"] or 0,
                "carbs": meal_stats["carbs"] or 0,
                "water_ml": water_stats["water_ml"] or 0,
            }


# ============================================================
# РЕПОЗИТОРИИ ДЛЯ СИСТЕМЫ МЕТРИК И АНАЛИТИКИ
# ============================================================

class DailyMetricsRepository:
    """
    Репозиторий для работы с ежедневными метриками.
    Таблица: daily_metrics
    """
    
    def __init__(self, db: Database):
        self.db = db

    async def save_metrics(
        self,
        user_id: int,
        metric_date: date,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Сохраняет или обновляет метрики за день.
        
        metrics может содержать любые поля из таблицы daily_metrics:
        - sleep_hours, sleep_quality, sleep_awakenings
        - energy_morning, energy_evening
        - stress_level
        - steps, hours_on_feet
        - workout_type, workout_duration, workout_intensity
        - hunger_before, hunger_after
        - digestion_bristol
        - cycle_day
        - notes
        """
        if not metrics:
            logger.warning(f"No metrics to save for user {user_id} on {metric_date}")
            return

        fields = []
        placeholders = []
        values = []
        
        for key, value in metrics.items():
            if value is not None:
                fields.append(key)
                placeholders.append("?")
                values.append(value)
        
        if not fields:
            logger.warning(f"No valid metrics to save for user {user_id} on {metric_date}")
            return
        
        # Добавляем обновление updated_at
        fields.append("updated_at")
        placeholders.append("CURRENT_TIMESTAMP")
        
        values.extend([user_id, metric_date.isoformat()])
        
        query = f"""
            INSERT INTO daily_metrics 
            ({', '.join(fields)}, user_id, metric_date)
            VALUES ({', '.join(placeholders)}, ?, ?)
            ON CONFLICT(user_id, metric_date) DO UPDATE SET
            {', '.join(f"{f} = excluded.{f}" for f in fields if f != 'updated_at')},
            updated_at = CURRENT_TIMESTAMP
        """
        
        async with self.db.transaction() as conn:
            await conn.execute(query, values)
            logger.debug(f"Saved metrics for user {user_id} on {metric_date}")

    async def get_metrics(
        self,
        user_id: int,
        metric_date: date
    ) -> Optional[Dict[str, Any]]:
        """Получает все метрики за указанный день."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM daily_metrics WHERE user_id = ? AND metric_date = ?",
                (user_id, metric_date.isoformat())
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_metrics_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Получает метрики за диапазон дат."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM daily_metrics 
                   WHERE user_id = ? AND metric_date BETWEEN ? AND ?
                   ORDER BY metric_date ASC""",
                (user_id, start_date.isoformat(), end_date.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_last_metrics(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Получает метрики за последние N дней."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM daily_metrics 
                   WHERE user_id = ? 
                   ORDER BY metric_date DESC 
                   LIMIT ?""",
                (user_id, days)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class DailyAggregatesRepository:
    """
    Репозиторий для работы с агрегированными данными за день.
    Таблица: daily_aggregates
    """
    
    def __init__(self, db: Database):
        self.db = db

    async def save_aggregate(
        self,
        user_id: int,
        aggregate_date: date,
        data: Dict[str, Any]
    ) -> None:
        """Сохраняет или обновляет агрегат за день."""
        if not data:
            return

        fields = []
        placeholders = []
        values = []
        
        for key, value in data.items():
            if value is not None:
                fields.append(key)
                placeholders.append("?")
                values.append(value)
        
        if not fields:
            return
        
        values.extend([user_id, aggregate_date.isoformat()])
        
        # Добавляем recomputed_at
        query = f"""
            INSERT INTO daily_aggregates 
            ({', '.join(fields)}, user_id, aggregate_date, recomputed_at)
            VALUES ({', '.join(placeholders)}, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, aggregate_date) DO UPDATE SET
            {', '.join(f"{f} = excluded.{f}" for f in fields)},
            recomputed_at = CURRENT_TIMESTAMP
        """
        
        async with self.db.transaction() as conn:
            await conn.execute(query, values)

    async def get_aggregate(
        self,
        user_id: int,
        aggregate_date: date
    ) -> Optional[Dict[str, Any]]:
        """Получает агрегат за указанный день."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM daily_aggregates WHERE user_id = ? AND aggregate_date = ?",
                (user_id, aggregate_date.isoformat())
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_aggregates_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Получает агрегаты за диапазон дат."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM daily_aggregates 
                   WHERE user_id = ? AND aggregate_date BETWEEN ? AND ?
                   ORDER BY aggregate_date ASC""",
                (user_id, start_date.isoformat(), end_date.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class PatternsRepository:
    """
    Репозиторий для работы с обнаруженными паттернами.
    Таблица: user_patterns
    """
    
    def __init__(self, db: Database):
        self.db = db

    async def init_tables(self) -> None:
        """Создаёт таблицу для паттернов, если её нет."""
        async with self.db.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    metric_x TEXT NOT NULL,
                    metric_y TEXT NOT NULL,
                    correlation_r REAL,
                    p_value REAL,
                    lag_days INTEGER DEFAULT 0,
                    sample_size INTEGER,
                    effect_text TEXT,
                    effect_direction TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    first_detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmation_count INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_user_active 
                ON user_patterns(user_id, is_active)
            """)

    async def save_pattern(self, user_id: int, pattern_data: Dict[str, Any]) -> int:
        """Сохраняет или обновляет паттерн."""
        async with self.db.transaction() as conn:
            # Проверяем, существует ли уже такой паттерн
            cursor = await conn.execute("""
                SELECT id, confirmation_count FROM user_patterns
                WHERE user_id = ? AND metric_x = ? AND metric_y = ? AND lag_days = ?
            """, (
                user_id, 
                pattern_data.get("metric_x"), 
                pattern_data.get("metric_y"), 
                pattern_data.get("lag_days", 0)
            ))
            existing = await cursor.fetchone()
            
            if existing:
                # Обновляем существующий
                await conn.execute("""
                    UPDATE user_patterns 
                    SET correlation_r = ?,
                        p_value = ?,
                        sample_size = ?,
                        effect_text = ?,
                        effect_direction = ?,
                        last_confirmed_at = CURRENT_TIMESTAMP,
                        confirmation_count = confirmation_count + 1,
                        is_active = 1
                    WHERE id = ?
                """, (
                    pattern_data.get("correlation_r"),
                    pattern_data.get("p_value"),
                    pattern_data.get("sample_size"),
                    pattern_data.get("effect_text"),
                    pattern_data.get("effect_direction"),
                    existing["id"]
                ))
                return existing["id"]
            else:
                # Вставляем новый
                cursor = await conn.execute("""
                    INSERT INTO user_patterns 
                    (user_id, pattern_type, metric_x, metric_y, correlation_r, 
                     p_value, lag_days, sample_size, effect_text, effect_direction)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    pattern_data.get("pattern_type"),
                    pattern_data.get("metric_x"),
                    pattern_data.get("metric_y"),
                    pattern_data.get("correlation_r"),
                    pattern_data.get("p_value"),
                    pattern_data.get("lag_days", 0),
                    pattern_data.get("sample_size"),
                    pattern_data.get("effect_text"),
                    pattern_data.get("effect_direction")
                ))
                return cursor.lastrowid

    async def get_active_patterns(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает активные паттерны пользователя."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM user_patterns
                WHERE user_id = ? AND is_active = 1
                ORDER BY ABS(correlation_r) DESC, confirmation_count DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_pattern_by_id(self, pattern_id: int) -> Optional[Dict[str, Any]]:
        """Получает паттерн по ID."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM user_patterns WHERE id = ?",
                (pattern_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def deactivate_pattern(self, pattern_id: int) -> None:
        """Деактивирует паттерн."""
        async with self.db.transaction() as conn:
            await conn.execute("""
                UPDATE user_patterns SET is_active = 0 WHERE id = ?
            """, (pattern_id,))

    async def confirm_pattern(self, pattern_id: int) -> None:
        """Подтверждает паттерн (увеличивает счётчик)."""
        async with self.db.transaction() as conn:
            await conn.execute("""
                UPDATE user_patterns 
                SET confirmation_count = confirmation_count + 1,
                    last_confirmed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (pattern_id,))


class ModifierHistoryRepository:
    """
    Репозиторий для истории модификаторов TDEE.
    Таблица: modifier_history
    """
    
    def __init__(self, db: Database):
        self.db = db

    async def init_tables(self) -> None:
        """Создаёт таблицу для истории модификаторов, если её нет."""
        async with self.db.connection() as conn:
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
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_modifier_history_user_date 
                ON modifier_history(user_id, record_date)
            """)

    async def save_modifier_history(
        self,
        user_id: int,
        record_date: date,
        data: Dict[str, Any]
    ) -> None:
        """Сохраняет историю модификаторов за день."""
        async with self.db.transaction() as conn:
            await conn.execute("""
                INSERT INTO modifier_history (
                    user_id, record_date, sleep_modifier, energy_modifier,
                    stress_modifier, activity_modifier, window_modifier,
                    workout_bonus, adjusted_tdee, metrics_used, missing_metrics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                record_date.isoformat(),
                data.get("sleep_modifier"),
                data.get("energy_modifier"),
                data.get("stress_modifier"),
                data.get("activity_modifier"),
                data.get("window_modifier"),
                data.get("workout_bonus"),
                data.get("adjusted_tdee"),
                json.dumps(data.get("metrics_used", [])),
                json.dumps(data.get("missing_metrics", [])),
            ))

    async def get_modifier_history(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Получает историю модификаторов за период."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM modifier_history
                WHERE user_id = ? AND record_date BETWEEN ? AND ?
                ORDER BY record_date ASC
            """, (user_id, start_date.isoformat(), end_date.isoformat()))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class AnalyticsSettingsRepository:
    """
    Репозиторий для настроек аналитики пользователя.
    Таблица: user_settings_analytics
    """
    
    def __init__(self, db: Database):
        self.db = db

    async def init_tables(self) -> None:
        """Создаёт таблицу для настроек аналитики, если её нет."""
        async with self.db.connection() as conn:
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

    async def get_settings(self, user_id: int) -> Dict[str, Any]:
        """Получает настройки аналитики для пользователя."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM user_settings_analytics WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            
            # Возвращаем настройки по умолчанию
            return {
                "user_id": user_id,
                "reminder_morning_enabled": True,
                "reminder_morning_time": "08:00",
                "reminder_evening_enabled": True,
                "reminder_evening_time": "21:00",
                "collect_sleep": True,
                "collect_energy": True,
                "collect_stress": True,
                "collect_steps": True,
                "collect_workout": True,
                "collect_hunger": False,
                "collect_digestion": False,
                "collect_cycle": False,
                "share_anonymous_stats": False,
            }

    async def update_settings(self, user_id: int, settings: Dict[str, Any]) -> None:
        """Обновляет настройки аналитики."""
        if not settings:
            return

        fields = []
        values = []
        
        for key, value in settings.items():
            if key != "user_id" and value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return
        
        values.append(user_id)
        
        async with self.db.transaction() as conn:
            # Проверяем, существует ли запись
            cursor = await conn.execute(
                "SELECT 1 FROM user_settings_analytics WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                await conn.execute(
                    f"UPDATE user_settings_analytics SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    values
                )
            else:
                # Вставляем новую запись
                all_settings = await self.get_settings(user_id)
                all_settings.update(settings)
                fields_list = list(all_settings.keys())
                placeholders = ", ".join("?" * len(fields_list))
                values_list = [all_settings[k] for k in fields_list]
                
                await conn.execute(
                    f"INSERT INTO user_settings_analytics ({', '.join(fields_list)}) VALUES ({placeholders})",
                    values_list
                )
                
class MeasurementsRepository:
    """Репозиторий для работы с замерами тела."""
    def __init__(self, db: Database):
        self.db = db

    async def add_measurement(
        self, 
        user_id: int, 
        measurement_type_id: int, 
        value: float,
        notes: Optional[str] = None,
        measured_at: Optional[str] = None
    ) -> int:
        """Добавляет новый замер."""
        async with self.db.transaction() as conn:
            if measured_at:
                cursor = await conn.execute(
                    """INSERT INTO body_measurements (user_id, measurement_type_id, value, notes, measured_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, measurement_type_id, value, notes, measured_at)
                )
            else:
                cursor = await conn.execute(
                    """INSERT INTO body_measurements (user_id, measurement_type_id, value, notes, measured_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (user_id, measurement_type_id, value, notes)
                )
            return cursor.lastrowid

    async def get_last_measurement(
        self, 
        user_id: int, 
        measurement_type_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получает последний замер указанного типа."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT id, user_id, measurement_type_id, value, measured_at, notes
                   FROM body_measurements 
                   WHERE user_id = ? AND measurement_type_id = ?
                   ORDER BY measured_at DESC
                   LIMIT 1""",
                (user_id, measurement_type_id)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_measurements_history(
        self, 
        user_id: int, 
        measurement_type_id: int, 
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Получает историю замеров указанного типа."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT id, value, measured_at, notes
                   FROM body_measurements 
                   WHERE user_id = ? AND measurement_type_id = ?
                   ORDER BY measured_at DESC
                   LIMIT ?""",
                (user_id, measurement_type_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_recent_measurements(
        self, 
        user_id: int, 
        days: int = 30
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Получает все замеры пользователя за последние N дней, сгруппированные по типу."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """SELECT measurement_type_id, value, measured_at
                   FROM body_measurements 
                   WHERE user_id = ? AND measured_at >= datetime('now', ?)
                   ORDER BY measured_at ASC""",
                (user_id, f'-{days} days')
            )
            rows = await cursor.fetchall()
            
            result = {}
            for row in rows:
                type_id = row["measurement_type_id"]
                if type_id not in result:
                    result[type_id] = []
                result[type_id].append({
                    "value": row["value"],
                    "date": row["measured_at"]
                })
            return result

    async def delete_measurement(self, measurement_id: int) -> bool:
        """Удаляет замер по ID."""
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM body_measurements WHERE id = ?",
                (measurement_id,)
            )
            return cursor.rowcount > 0