
import os
import asyncpg

pool = None

async def connect_db():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

async def create_tables():
    async with pool.acquire() as conn:
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS knowledge (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            problem TEXT NOT NULL,
            solution TEXT NOT NULL,
            source_message_id BIGINT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
