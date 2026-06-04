"""
Репозитории для работы с БД.
"""
from typing import Optional, Dict, Any, List
from db.database import Database
import json
import logging

logger = logging.getLogger(__name__)


class UserRepository:
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

    async def get(self, telegram_id: int) -> Optional[tuple]:
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
    def __init__(self, db: Database):
        self.db = db

    async def get_favorites(self, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Получает список избранных продуктов.
        Лимит увеличен до 200 (было 10).
        """
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
        """
        Получает одно избранное блюдо по ID.
        Проверяет, что блюдо принадлежит указанному пользователю.
        """
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
        """
        Добавляет или обновляет избранный продукт.
        
        🎯 Уникальность по (user_id, food_name, barcode) — НЕ по весу.
        
        При повторном сохранении:
        - Обновляет amount_g (последний использованный вес)
        - Обновляет КБЖУ
        - Увеличивает times_used
        - Обновляет updated_at
        """
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
        """
        Удаляет блюдо из избранного.
        Проверяет, что блюдо принадлежит пользователю.
        Возвращает True, если удалено.
        """
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id)
            )
            return cursor.rowcount > 0

    async def clear_all(self, user_id: int) -> int:
        """
        Удаляет всё избранное пользователя.
        Возвращает количество удалённых записей.
        """
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


class DailyStatsRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get_today_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику за сегодня."""
        from datetime import datetime
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

            # Вода (в миллилитрах)
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
        from datetime import datetime
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