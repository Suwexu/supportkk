import os
import asyncpg

_pool = None


async def connect_db():
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Не задана переменная окружения DATABASE_URL")
    _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)


async def create_tables():
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id BIGSERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                problem TEXT NOT NULL,
                solution TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


async def save_knowledge(category: str, problem: str, solution: str) -> bool:
    async with _pool.acquire() as conn:
        existing = await conn.fetchval(
            """SELECT id FROM knowledge
               WHERE lower(category) = lower($1) AND lower(problem) = lower($2)
               LIMIT 1""",
            category, problem
        )
        if existing is not None:
            return False
        await conn.execute(
            "INSERT INTO knowledge (category, problem, solution) VALUES ($1, $2, $3)",
            category, problem, solution
        )
        return True


async def get_count() -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM knowledge")


async def get_all_knowledge():
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, category, problem, solution, created_at FROM knowledge ORDER BY id DESC"
        )
        return [dict(row) for row in rows]
