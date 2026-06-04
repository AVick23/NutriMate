# handlers/measurements/repository.py
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from db.database import Database


class MeasurementsRepository:
    """Репозиторий для работы с замерами тела."""
    
    def __init__(self, db: Database):
        self.db = db

    async def init_tables(self) -> None:
        """Создаёт таблицы для замеров, если их нет."""
        async with self.db.connection() as conn:
            # Таблица типов замеров
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS measurement_types (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            """)
            
            # Таблица замеров
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
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_measurements_user_type_date ON body_measurements(user_id, measurement_type_id, measured_at)")
            
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
            
            await conn.commit()

    async def add_measurement(
        self, 
        user_id: int, 
        measurement_type_id: int, 
        value: float,
        notes: Optional[str] = None
    ) -> int:
        """Добавляет новый замер."""
        async with self.db.transaction() as conn:
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