from pathlib import Path
from typing import Any

import aiosqlite

from config import DB_PATH


async def init_db() -> None:
    """Создаёт таблицу заявок и индекс."""

    Path(DB_PATH).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'new'
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_user_id
            ON requests(user_id)
        """)

        await db.commit()


async def create_request_if_allowed(
    *,
    user_id: int,
    username: str | None,
    name: str,
    phone: str,
    comment: str,
    cooldown_seconds: int,
) -> tuple[int | None, int]:
    """
    Создаёт заявку, если пользователь не превысил лимит.

    Возвращает:
    (id заявки, 0) — если всё успешно.
    (None, оставшиеся секунды) — если действует ограничение.
    """

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        await db.execute("BEGIN IMMEDIATE")

        try:
            async with db.execute("""
                SELECT
                    CAST(
                        strftime('%s', 'now')
                        - strftime('%s', created_at)
                        AS INTEGER
                    ) AS age_seconds
                FROM requests
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 1
            """, (user_id,)) as cursor:

                last_request = await cursor.fetchone()

            if last_request is not None and cooldown_seconds > 0:
                age_seconds = int(
                    last_request["age_seconds"] or 0
                )

                remaining = cooldown_seconds - age_seconds

                if remaining > 0:
                    await db.rollback()
                    return None, remaining

            cursor = await db.execute("""
                INSERT INTO requests (
                    user_id,
                    username,
                    name,
                    phone,
                    comment
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                username,
                name,
                phone,
                comment
            ))

            request_id = cursor.lastrowid

            await db.commit()

            return int(request_id), 0

        except Exception:
            await db.rollback()
            raise


async def get_recent_requests(
    limit: int = 10
) -> list[dict[str, Any]]:
    """Возвращает последние заявки."""

    safe_limit = max(1, min(limit, 50))

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT
                id,
                user_id,
                username,
                name,
                phone,
                comment,
                created_at,
                status
            FROM requests
            ORDER BY id DESC
            LIMIT ?
        """, (safe_limit,)) as cursor:

            rows = await cursor.fetchall()

            return [dict(row) for row in rows]


async def get_request_by_id(
    request_id: int
) -> dict[str, Any] | None:
    """Находит заявку по её номеру."""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM requests WHERE id = ?",
            (request_id,)
        ) as cursor:

            row = await cursor.fetchone()

            return dict(row) if row else None


async def mark_request_answered(
    request_id: int
) -> None:
    """Меняет статус после ответа администратора."""

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            UPDATE requests
            SET status = 'answered'
            WHERE id = ?
        """, (request_id,))

        await db.commit()