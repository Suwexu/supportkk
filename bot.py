import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from db import connect_db, create_tables

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Помощник администратора клуба готов к работе. PostgreSQL подключен.")

@dp.message()
async def echo(message: Message):
    await message.answer("Бот работает.")

async def main():
    await connect_db()
    await create_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
