
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, Update
from aiogram.enums import ParseMode, UpdateType
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

@dp.update()
async def log_everything(update: Update):
    logging.warning("=" * 60)
    logging.warning("UPDATE RECEIVED")
    logging.warning(str(update.model_dump()))
    logging.warning("=" * 60)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Диагностический режим запущен.")

@dp.message(Command("chatid"))
async def chatid(message: Message):
    await message.answer(f"Chat ID: {message.chat.id}")

@dp.message()
async def echo(message: Message):
    await message.answer("Сообщение получено.")

async def main():
    await dp.start_polling(
        bot,
        allowed_updates=[
            UpdateType.MESSAGE,
            UpdateType.CHANNEL_POST,
            UpdateType.EDITED_CHANNEL_POST
        ]
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
