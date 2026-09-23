
import os
import re
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from db import connect_db, create_tables, save_knowledge, get_count

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Отправь инструкцию в формате:\n\n"
        "#FACEIT\n\n"
        "Проблема:\n...\n\n"
        "Решение:\n..."
    )

@dp.message(Command("count"))
async def count_cmd(message: Message):
    count = await get_count()
    await message.answer(f"В базе {count} инструкций.")

@dp.message()
async def save_instruction(message: Message):
    text = message.text or ""

    category_match = re.search(r"#([A-Za-zА-Яа-я0-9_]+)", text)
    problem_match = re.search(r"Проблема:\s*(.*?)(?:\n\s*Решение:)", text, re.S)
    solution_match = re.search(r"Решение:\s*(.*)", text, re.S)

    if not (category_match and problem_match and solution_match):
        await message.answer(
            "Формат не распознан.\n\n"
            "Пример:\n"
            "#FACEIT\n\n"
            "Проблема:\nНе запускается FACEIT\n\n"
            "Решение:\nПерезапустить службу"
        )
        return

    category = category_match.group(1).strip()
    problem = problem_match.group(1).strip()
    solution = solution_match.group(1).strip()

    await save_knowledge(
        category=category,
        problem=problem,
        solution=solution
    )

    await message.answer(
        f"✅ Инструкция сохранена\n\n"
        f"Категория: {category}\n"
        f"Проблема: {problem}"
    )

async def main():
    await connect_db()
    await create_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
