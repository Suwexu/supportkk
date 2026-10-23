import asyncio
import html
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from db import connect_db, create_tables, save_knowledge, get_count, get_all_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CATEGORY_RE = re.compile(r"(?m)^\\s*#([A-Za-zА-Яа-яЁё0-9_-]+)\\s*$")
PROBLEM_RE = re.compile(r"(?ims)^\\s*Проблема\\s*:\\s*(.*?)\\s*(?=^\\s*Решение\\s*:|\\Z)")
SOLUTION_RE = re.compile(r"(?ims)^\\s*Решение\\s*:\\s*(.*?)\\s*\\Z")

STOP_WORDS = {
    "и", "а", "но", "в", "во", "на", "по", "с", "со", "к", "ко", "у", "от",
    "до", "за", "из", "для", "при", "как", "что", "это", "не", "мне", "уже",
    "почему", "где", "пожалуйста", "помогите", "проблема", "ошибка", "есть",
    "the", "a", "an", "and", "or", "to", "for", "of", "is", "my", "with"
}


def parse_instruction(text: str):
    category_match = CATEGORY_RE.search(text)
    problem_match = PROBLEM_RE.search(text)
    solution_match = SOLUTION_RE.search(text)
    if not (category_match and problem_match and solution_match):
        return None
    category = category_match.group(1).strip()
    problem = problem_match.group(1).strip()
    solution = solution_match.group(1).strip()
    if not problem or not solution:
        return None
    return category, problem, solution


def words(text: str):
    return [
        token for token in re.findall(r"[a-zа-яё0-9]+", (text or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def rank_results(query: str, rows):
    query_words = list(dict.fromkeys(words(query)))
    query_lower = query.lower().strip()
    ranked = []
    for row in rows:
        category = row.get("category") or ""
        problem = row.get("problem") or ""
        solution = row.get("solution") or ""
        combined = f"{category} {problem} {solution}".lower()
        score = 5 if query_lower and query_lower in combined else 0
        for word in query_words:
            if word in combined:
                score += 2
            elif len(word) >= 5 and any(
                word[:n] in combined for n in (len(word) - 1, len(word) - 2) if n >= 4
            ):
                score += 1
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (item[0], item[1].get("id", 0)), reverse=True)
    return [row for _, row in ranked[:5]]


def format_results(query: str, rows):
    safe_query = html.escape(query)
    if not rows:
        return (
            f"По запросу «{safe_query}» ничего не нашёл.\\n"
            "Попробуй другое ключевое слово или более короткий запрос."
        )
    chunks = [f"Нашёл инструкции по запросу «{safe_query}»:"]
    for index, row in enumerate(rows, start=1):
        category = html.escape(str(row.get("category") or "Без категории"))
        problem = html.escape(str(row.get("problem") or "Без описания"))
        solution = str(row.get("solution") or "")
        if len(solution) > 1500:
            solution = solution[:1500].rstrip() + "…"
        chunks.append(
            f"\\n{index}. [{category}]\\n"
            f"Проблема: {problem}\\n"
            f"Решение:\\n{html.escape(solution)}"
        )
    output = "\\n".join(chunks)
    if len(output) > 3900:
        output = output[:3850].rstrip() + "\\n\\n(Вывод сокращён: слишком много текста.)"
    return output


async def search_and_reply(message: Message, query: str):
    query = query.strip()
    if not query:
        await message.answer(
            "Напиши, что нужно найти. Например:\\n"
            "/search не запускается Steam\\n\\n"
            "Можно и просто отправить сообщение с описанием проблемы."
        )
        return
    rows = await get_all_knowledge()
    await message.answer(format_results(query, rank_results(query, rows)), parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я помощник администратора компьютерного клуба.\\n\\n"
        "• Отправь описание проблемы или используй /search запрос — я поищу решение в базе.\\n"
        "• /count — сколько инструкций сохранено.\\n\\n"
        "Чтобы добавить инструкцию, отправь сообщение в формате:\\n"
        "#Категория\\n"
        "Проблема: описание проблемы\\n"
        "Решение: пошаговое решение"
    )


@dp.message(Command("count"))
async def cmd_count(message: Message):
    await message.answer(f"В базе сохранено инструкций: {await get_count()}")


@dp.message(Command("search"))
async def cmd_search(message: Message):
    _, _, query = (message.text or "").partition(" ")
    await search_and_reply(message, query)


@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text or ""
    instruction = parse_instruction(text)
    if instruction:
        category, problem, solution = instruction
        inserted = await save_knowledge(category, problem, solution)
        if inserted:
            await message.answer(
                "Инструкция сохранена.\\n"
                f"Категория: {category}\\n"
                f"Всего в базе: {await get_count()}"
            )
        else:
            await message.answer("Похоже, такая инструкция уже есть в базе. Дубликат не добавлял.")
        return
    await search_and_reply(message, text)


async def main():
    await connect_db()
    await create_tables()
    logger.info("Database connected")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
