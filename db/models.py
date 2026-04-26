# db/models.py
from typing import Optional, Dict, Any
from db.database import Database
import json
from typing import List


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

    async def create(self, telegram_id: int, username: Optional[str] = None,
                     first_name: Optional[str] = None, last_name: Optional[str] = None) -> int:
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

    async def get(self, telegram_id: int) -> Optional[tuple[str, Dict[str, Any]]]:
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
            
            
# db/models.py — добавить в конец файла

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

    async def get_favorites(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
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
                   ON CONFLICT(user_id, food_name, amount_g) DO UPDATE SET
                   times_used = times_used + 1,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, food_name, amount_g, kcal, protein_g, fat_g, carbs_g, barcode)
            )

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

            # Вода
            cursor = await conn.execute(
                """SELECT COUNT(*) as water_count
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
                "water": water_stats["water_count"] or 0,
            }