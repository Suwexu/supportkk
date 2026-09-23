
import os
import asyncpg

pool = None

async def connect_db():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

async def create_tables():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                problem TEXT NOT NULL,
                solution TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

async def save_knowledge(category, problem, solution):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO knowledge
            (category, problem, solution)
            VALUES ($1, $2, $3)
            """,
            category,
            problem,
            solution
        )

async def get_count():
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge"
        )
