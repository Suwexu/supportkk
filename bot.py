import asyncio
import html
import logging
import os
import re
from collections import defaultdict

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

CATEGORY_RE = re.compile(r"(?m)^\s*#([A-Za-zА-Яа-яЁё0-9_-]+)\s*$")
PROBLEM_RE = re.compile(r"(?ims)^\s*Проблема\s*:\s*(.*?)\s*(?=^\s*Решение\s*:|\Z)")
SOLUTION_RE = re.compile(r"(?ims)^\s*Решение\s*:\s*(.*?)\s*\Z")

STOP_WORDS = {
    "и", "а", "но", "в", "во", "на", "по", "с", "со", "к", "ко", "у", "от",
    "до", "за", "из", "для", "при", "как", "что", "это", "мне", "уже",
    "почему", "где", "пожалуйста", "помогите", "проблема", "ошибка", "есть",
    "the", "a", "an", "and", "or", "to", "for", "of", "is", "my", "with"
}

# Каждая группа описывает один смысл. Совпадение с любым вариантом помогает найти инструкцию,
# даже если администратор сформулировал проблему иначе.
SYNONYM_GROUPS = {
    "faceit": (
        "faceit", "фейсит", "фейсит античит", "faceit anticheat", "faceit anti cheat",
        "античит фейсит", "античит faceit"
    ),
    "steam": ("steam", "стим", "клиент стим", "клиент steam"),
    "launch_failure": (
        "не запускается", "не стартует", "не открывается", "не работает",
        "не грузится", "не включается", "не стартанул", "не стартанула",
        "не могу запустить", "не запускает", "не запускается игра"
    ),
    "crash": ("вылетает", "вылет", "вылетает при запуске", "краш", "крашится", "crash", "crashes"),
    "freeze": ("зависает", "завис", "зависание", "фризит", "фриз", "freeze", "freezes", "лагает"),
    "service": ("служба", "службу", "службы", "сервис", "service", "services"),
    "internet": ("интернет", "сеть", "подключение", "нет соединения", "не подключается", "connection"),
    "login": ("не входит", "не могу войти", "авторизация", "логин", "вход", "не авторизуется", "login", "sign in"),
    "update": ("обновление", "обновить", "не обновляется", "апдейт", "update", "updating"),
    "sound": ("нет звука", "не работает звук", "звук пропал", "аудио", "микрофон", "headset", "sound"),
    "black_screen": ("чёрный экран", "черный экран", "пустой экран", "black screen"),
    "blue_screen": ("синий экран", "bsod", "blue screen"),
    "low_fps": ("низкий фпс", "мало фпс", "просадки фпс", "фпс падает", "fps drop", "low fps"),
    "install": ("не устанавливается", "установка", "не могу установить", "install", "installation"),
}

ALIAS_TO_CONCEPT = {}
for concept, aliases in SYNONYM_GROUPS.items():
    for alias in aliases:
        ALIAS_TO_CONCEPT[alias] = concept


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


def normalize_text(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def words(text: str):
    return [
        token for token in normalize_text(text).split()
        if len(token) > 1 and token not in STOP_WORDS
    ]


def concepts_in(text: str):
    normalized = normalize_text(text)
    found = set()
    # Longest aliases first so phrase-level variants are recognized clearly.
    for concept, aliases in SYNONYM_GROUPS.items():
        for alias in aliases:
            normalized_alias = normalize_text(alias)
            if normalized_alias and re.search(
                r"(?<![a-zа-я0-9])" + re.escape(normalized_alias) + r"(?![a-zа-я0-9])",
                normalized
            ):
                found.add(concept)
                break
    return found


def token_matches(query_word: str, row_words):
    if query_word in row_words:
        return True
    # Tolerate common endings and small spelling differences without external services.
    if len(query_word) >= 5:
        for row_word in row_words:
            if len(row_word) >= 5 and (
                row_word.startswith(query_word[:5]) or query_word.startswith(row_word[:5])
            ):
                return True
    return False


def rank_results(query: str, rows):
    query_normalized = normalize_text(query)
    query_words = list(dict.fromkeys(words(query)))
    query_concepts = concepts_in(query)
    ranked = []

    for row in rows:
        category = str(row.get("category") or "")
        problem = str(row.get("problem") or "")
        solution = str(row.get("solution") or "")
        combined = f"{category} {problem} {solution}"
        normalized_combined = normalize_text(combined)
        row_words = set(words(combined))
        row_concepts = concepts_in(combined)
        score = 0

        if query_normalized and query_normalized in normalized_combined:
            score += 7

        # Semantic-like synonym group overlap, performed locally with no API.
        shared_concepts = query_concepts & row_concepts
        score += 5 * len(shared_concepts)

        for word in query_words:
            if token_matches(word, row_words):
                score += 2

        # A problem-title match is more useful than a match found only in the solution text.
        title_normalized = normalize_text(f"{category} {problem}")
        for concept in shared_concepts:
            aliases = SYNONYM_GROUPS[concept]
            if any(normalize_text(alias) in title_normalized for alias in aliases):
                score += 2

        if score > 0:
            ranked.append((score, row))

    ranked.sort(key=lambda item: (item[0], item[1].get("id", 0)), reverse=True)
    return [row for _, row in ranked[:5]]


def clean_solution(solution: str) -> str:
    solution = (solution or "").replace("\r\n", "\n").replace("\r", "\n")
    solution = solution.replace("\\n", "\n")
    solution = re.sub(r"\n{3,}", "\n\n", solution)
    return solution.strip()


def format_results(query: str, rows):
    safe_query = html.escape(query)
    if not rows:
        return (
            f"По запросу «{safe_query}» ничего не нашёл.\n\n"
            "Попробуй описать проблему другими словами или указать программу/игру."
        )

    chunks = [f"<b>Нашёл инструкции по запросу «{safe_query}»</b>"]
    for index, row in enumerate(rows, start=1):
        category = html.escape(str(row.get("category") or "Без категории"))
        problem = html.escape(str(row.get("problem") or "Без описания"))
        solution = clean_solution(str(row.get("solution") or ""))
        if len(solution) > 1500:
            solution = solution[:1500].rstrip() + "…"
        chunks.append(
            f"<b>{index}. Инструкция — {category}</b>\n\n"
            f"<b>Проблема:</b> {problem}\n\n"
            f"<b>Решение:</b>\n{html.escape(solution)}"
        )

    output = "\n\n━━━━━━━━━━━━━━\n\n".join(chunks)
    if len(output) > 3900:
        output = output[:3850].rstrip() + "\n\n<i>Вывод сокращён: слишком много текста.</i>"
    return output


async def search_and_reply(message: Message, query: str):
    query = query.strip()
    if not query:
        await message.answer(
            "Напиши, что нужно найти. Например:\n"
            "/search фейсит не стартует\n\n"
            "Можно и просто отправить сообщение с описанием проблемы."
        )
        return
    rows = await get_all_knowledge()
    matches = rank_results(query, rows)
    await message.answer(format_results(query, matches), parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я помощник администратора компьютерного клуба.\n\n"
        "• Отправь описание проблемы или используй /search запрос — я поищу решение в базе.\n"
        "• /count — сколько инструкций сохранено.\n\n"
        "Поиск понимает некоторые синонимы и варианты формулировок: например, "
        "«фейсит не стартует» и «не запускается FACEIT».\n\n"
        "Чтобы добавить инструкцию, отправь сообщение в формате:\n"
        "#Категория\n"
        "Проблема: описание проблемы\n"
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
                "Инструкция сохранена.\n"
                f"Категория: {category}\n"
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
