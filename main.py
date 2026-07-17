import json
from pathlib import Path
import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import FSInputFile


TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("Переменная окружения TOKEN не задана")

bot = Bot(token=TOKEN)
dp = Dispatcher()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HOMEWORKS_DIR = BASE_DIR / "homeworks"

SUPPORTED_EXTENSIONS = [
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".txt",
    ".xlsx",
    ".xls",
    ".ods",
]


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


homeworks = load_json("homeworks.json")
theory_tasks = load_json("theory.json")
probnik_codes = load_json("probniks.json")
materials = load_json("materials.json")
ALLOWED_USERS = set(load_json("allowed_users.json")["users"])

users = {}


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def normalize_homework_folder(hw_id: str, hw_data: dict) -> str:
    if "folder" in hw_data:
        return hw_data["folder"]

    if hw_id.startswith("hw_"):
        return hw_id

    if hw_id.startswith("hw") and hw_id[2:].isdigit():
        return f"hw_{hw_id[2:]}"

    if hw_id.isdigit():
        return f"hw_{hw_id}"

    return hw_id


def find_file(folder: Path, name: str):
    for ext in SUPPORTED_EXTENSIONS:
        path = folder / f"{name}{ext}"
        if path.exists() and path.is_file():
            return path
    return None


def normalize_answer(answer: str) -> str:
    return answer.strip().lower().replace(" ", "")


def answers_to_list(answers):
    if isinstance(answers, dict) and "answers" in answers and isinstance(answers["answers"], (dict, list)):
        answers = answers["answers"]

    if isinstance(answers, dict):
        return [
            str(answers[key])
            for key in sorted(
                answers.keys(),
                key=lambda x: int(x) if str(x).isdigit() else str(x)
            )
        ]

    if isinstance(answers, list):
        return [str(answer) for answer in answers]

    return []


def load_json_file(path: Path):
    raw = path.read_bytes()

    if not raw.strip():
        return None

    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1251"):
        try:
            return json.loads(raw.decode(encoding))
        except Exception as e:
            last_error = e

    print("Не смог прочитать JSON:", path, last_error)
    return None


def get_homework_answers(hw_id: str, hw_data: dict):
    answers = hw_data.get("answers")
    answers_list = answers_to_list(answers)

    if answers_list:
        return answers_list

    folder_name = normalize_homework_folder(hw_id, hw_data)
    answers_path = HOMEWORKS_DIR / folder_name / "answers.json"

    if not answers_path.exists() or not answers_path.is_file():
        return []

    answers = load_json_file(answers_path)
    return answers_to_list(answers)


def get_answers_list(hw_data: dict):
    folder_name = hw_data.get("folder")

    if folder_name:
        answers_path = HOMEWORKS_DIR / folder_name / "answers.json"

        if not answers_path.exists() or not answers_path.is_file():
            return answers_to_list(hw_data.get("answers", []))

        answers = load_json_file(answers_path)
        return answers_to_list(answers)

    return answers_to_list(hw_data.get("answers", []))

def ensure_user(chat_id: int):
    if chat_id not in users:
        users[chat_id] = {
            "hw": None,
            "question_index": 0,
            "score": 0,
            "answers": [],
            "correct_answers": [],
            "wrong_questions": [],
            "repeat_answers": [],
            "repeat_results": [],
            "repeat_wrong_questions_next": [],
            "mode": "menu",
            "last_menu": "main",
            "last_bot_message_id": None,
            "history_message_ids": [],
            "exam": None,
        }


def hw_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="hw_back")
    kb.adjust(1)
    return kb.as_markup()


def homework_result_menu(wrong_questions=None):
    kb = InlineKeyboardBuilder()

    if wrong_questions:
        kb.button(text="🔁 Повторить ошибки", callback_data="repeat_errors")

    kb.button(text="⬅️ Назад", callback_data="hw_back")
    kb.adjust(1)
    return kb.as_markup()


def exam_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📗 ЕГЭ", callback_data="exam:ege")
    kb.button(text="📘 ОГЭ", callback_data="exam:oge")
    kb.adjust(1)
    return kb.as_markup()


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Выбрать ДЗ", callback_data="choose_hw")
    kb.button(text="🧪 Пробники", callback_data="probnik")
    kb.button(text="📂 Полезные материалы", callback_data="materials_menu")
    kb.adjust(1)
    return kb.as_markup()


def back_kb_to_main():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def theory_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="theory_menu")
    kb.adjust(1)
    return kb.as_markup()


def probnik_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def materials_back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="materials_menu")
    kb.adjust(1)
    return kb.as_markup()


def homework_menu(chat_id: int, prefix: str, back_callback: str = "main_menu"):
    exam = users[chat_id].get("exam")
    if not exam:
        return exam_menu()

    # Собираем все кнопки домашних заданий в список
    buttons = []
    for hw_id, hw_data in homeworks.get(exam, {}).items():
        buttons.append(
            InlineKeyboardButton(text=hw_data["title"], callback_data=f"{prefix}:{hw_id}")
        )

    # Разбиваем на строки по 3 кнопки в каждой
    rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]

    # Добавляем кнопку "Назад" отдельной строкой
    back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)
    rows.append([back_button])

    # Создаём клавиатуру
    return InlineKeyboardMarkup(inline_keyboard=rows)


def theory_menu_kb(chat_id: int):
    kb = InlineKeyboardBuilder()
    exam = users[chat_id].get("exam")

    if not exam:
        return exam_menu()

    for t_id, t_data in theory_tasks.get(exam, {}).items():
        kb.button(text=t_data["title"], callback_data=f"theory:{t_id}")

    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def materials_menu_kb(chat_id: int):
    kb = InlineKeyboardBuilder()
    exam = users[chat_id].get("exam")

    if not exam:
        return exam_menu()

    for m_id, m_data in materials.get(exam, {}).items():
        kb.button(text=m_data["title"], callback_data=f"material:{m_id}")

    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


async def delete_message_safe(chat_id: int, message_id):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def delete_last_bot_message(chat_id: int):
    ensure_user(chat_id)
    last_message_id = users[chat_id].get("last_bot_message_id")
    if last_message_id:
        await delete_message_safe(chat_id, last_message_id)
        users[chat_id]["last_bot_message_id"] = None


async def send_and_store(chat_id: int, text: str, reply_markup=None):
    ensure_user(chat_id)

    old_message_id = users[chat_id].get("last_bot_message_id")

    msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    users[chat_id]["last_bot_message_id"] = msg.message_id

    if old_message_id and old_message_id != msg.message_id:
        await delete_message_safe(chat_id, old_message_id)

    return msg


async def send_history_message(chat_id: int, text: str, reply_markup=None):
    ensure_user(chat_id)
    msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    users[chat_id]["history_message_ids"].append(msg.message_id)
    return msg


async def send_history_document(chat_id: int, file_path: Path, caption: str | None = None, reply_markup=None):
    ensure_user(chat_id)
    msg = await bot.send_document(
        chat_id,
        document=FSInputFile(file_path),
        caption=caption,
        reply_markup=reply_markup
    )
    users[chat_id]["history_message_ids"].append(msg.message_id)
    return msg


async def ask_homework_question(chat_id: int):
    ensure_user(chat_id)

    exam = users[chat_id].get("exam")
    hw_id = users[chat_id].get("hw")

    if not exam or not hw_id or hw_id not in homeworks.get(exam, {}):
        await send_history_message(chat_id, "Ошибка: домашняя работа не найдена.", reply_markup=hw_back_menu())
        users[chat_id]["mode"] = "menu"
        return

    hw = homeworks[exam][hw_id]
    answers = users[chat_id].get("correct_answers", [])
    if not answers:
        answers = get_homework_answers(hw_id, hw)
        users[chat_id]["correct_answers"] = answers

    question_index = users[chat_id]["question_index"]

    if question_index >= len(answers):
        await finish_homework(chat_id)
        return

    folder_name = normalize_homework_folder(hw_id, hw)
    folder = HOMEWORKS_DIR / folder_name
    task_number = question_index + 1
    task_file = find_file(folder, str(task_number))

    if task_file:
        await send_history_document(chat_id, task_file, caption=f"Файл к заданию {task_number}")

    reply_markup = hw_back_menu() if question_index == 0 else None

    await send_history_message(
        chat_id,
        f"Напиши ответ на задание {task_number} из {len(answers)}:",
        reply_markup=reply_markup
    )


async def finish_homework(chat_id: int):
    ensure_user(chat_id)

    exam = users[chat_id].get("exam")
    hw_id = users[chat_id].get("hw")

    if not exam or not hw_id or hw_id not in homeworks.get(exam, {}):
        await send_history_message(chat_id, "Ошибка: домашняя работа не найдена.", reply_markup=hw_back_menu())
        users[chat_id]["mode"] = "menu"
        return

    hw = homeworks[exam][hw_id]
    correct_answers = users[chat_id].get("correct_answers", [])
    if not correct_answers:
        correct_answers = get_homework_answers(hw_id, hw)
        users[chat_id]["correct_answers"] = correct_answers

    user_answers = users[chat_id].get("answers", [])

    score = 0
    lines = []
    wrong_questions = []

    for i, correct_answer in enumerate(correct_answers):
        user_answer = user_answers[i] if i < len(user_answers) else ""
        task_number = i + 1

        if normalize_answer(user_answer) == normalize_answer(correct_answer):
            score += 1
            lines.append(f"{task_number}. ✅")
        else:
            lines.append(f"{task_number}. ❌")
            wrong_questions.append(task_number)

    result_text = (
        "📊 Проверка завершена!\n\n"
        f"Результат: {score}/{len(correct_answers)}\n\n"
        + "\n".join(lines)
    )

    if wrong_questions:
        result_text += "\n\nМожно повторить только задания с ошибками."
    else:
        result_text += "\n\n🎉 Отлично! Ошибок нет."

    users[chat_id]["score"] = score
    users[chat_id]["wrong_questions"] = wrong_questions
    users[chat_id]["repeat_answers"] = []
    users[chat_id]["repeat_results"] = []
    users[chat_id]["repeat_wrong_questions_next"] = []
    users[chat_id]["mode"] = "menu"

    await send_history_message(chat_id, result_text, reply_markup=homework_result_menu(wrong_questions))


async def ask_repeat_error_question(chat_id: int):
    ensure_user(chat_id)

    exam = users[chat_id].get("exam")
    hw_id = users[chat_id].get("hw")

    if not exam or not hw_id or hw_id not in homeworks.get(exam, {}):
        await send_history_message(chat_id, "Ошибка: домашняя работа не найдена.", reply_markup=hw_back_menu())
        users[chat_id]["mode"] = "menu"
        return

    hw = homeworks[exam][hw_id]
    correct_answers = users[chat_id].get("correct_answers", [])
    if not correct_answers:
        correct_answers = get_homework_answers(hw_id, hw)
        users[chat_id]["correct_answers"] = correct_answers

    wrong_questions = users[chat_id].get("wrong_questions", [])
    question_index = users[chat_id].get("question_index", 0)

    if not wrong_questions:
        users[chat_id]["mode"] = "menu"
        await send_history_message(
            chat_id,
            "Ошибок для повтора нет ✅",
            reply_markup=hw_back_menu()
        )
        return

    if question_index >= len(wrong_questions):
        await finish_repeat_errors(chat_id)
        return

    task_number = wrong_questions[question_index]

    if task_number < 1 or task_number > len(correct_answers):
        users[chat_id]["repeat_wrong_questions_next"].append(task_number)
        users[chat_id]["question_index"] = question_index + 1
        await ask_repeat_error_question(chat_id)
        return

    folder_name = normalize_homework_folder(hw_id, hw)
    folder = HOMEWORKS_DIR / folder_name
    task_file = find_file(folder, str(task_number))

    if task_file:
        await send_history_document(chat_id, task_file, caption=f"Файл к заданию {task_number}")

    reply_markup = hw_back_menu() if question_index == 0 else None

    await send_history_message(
        chat_id,
        f"🔁 Повтор ошибок\n\nНапиши ответ на задание {task_number} ({question_index + 1} из {len(wrong_questions)}):",
        reply_markup=reply_markup
    )


async def finish_repeat_errors(chat_id: int):
    ensure_user(chat_id)

    wrong_questions = users[chat_id].get("wrong_questions", [])
    repeat_results = users[chat_id].get("repeat_results", [])
    new_wrong_questions = users[chat_id].get("repeat_wrong_questions_next", [])

    total = len(wrong_questions)
    score = sum(1 for _, is_correct in repeat_results if is_correct)

    lines = []
    for task_number, is_correct in repeat_results:
        if is_correct:
            lines.append(f"{task_number}. ✅")
        else:
            lines.append(f"{task_number}. ❌")

    if total == 0:
        result_text = "Ошибок для повтора нет ✅"
    elif new_wrong_questions:
        result_text = (
            "🔁 Повтор ошибок завершён!\n\n"
            f"Результат: {score}/{total}\n\n"
            + "\n".join(lines)
            + "\n\nОстались ошибки. Можно повторить их ещё раз."
        )
    else:
        result_text = (
            "🎉 Повтор ошибок завершён!\n\n"
            f"Результат: {score}/{total}\n\n"
            + "\n".join(lines)
            + "\n\nВсе ошибки исправлены ✅"
        )

    users[chat_id]["wrong_questions"] = new_wrong_questions
    users[chat_id]["repeat_answers"] = []
    users[chat_id]["repeat_results"] = []
    users[chat_id]["repeat_wrong_questions_next"] = []
    users[chat_id]["question_index"] = 0
    users[chat_id]["mode"] = "menu"

    await send_history_message(chat_id, result_text, reply_markup=homework_result_menu(new_wrong_questions))


async def clear_history_messages(chat_id: int):
    ensure_user(chat_id)

    for message_id in users[chat_id]["history_message_ids"]:
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass

    users[chat_id]["history_message_ids"] = []


async def clear_quiz_and_probnik_messages(chat_id: int):
    await clear_history_messages(chat_id)
    await delete_last_bot_message(chat_id)


async def delete_callback_message(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass


@dp.message(CommandStart())
async def start_handler(message: Message):
    if not is_allowed(message.from_user.id):
        try:
            await message.delete()
        except Exception:
            pass
        await bot.send_message(message.chat.id, f"Твой ID: {message.from_user.id}")
        return

    ensure_user(message.chat.id)
    await clear_quiz_and_probnik_messages(message.chat.id)

    users[message.chat.id].update({
        "hw": None,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "correct_answers": [],
        "wrong_questions": [],
        "repeat_answers": [],
        "repeat_results": [],
        "repeat_wrong_questions_next": [],
        "mode": "menu",
        "last_menu": "main",
        "exam": None,
    })

    await send_and_store(
        message.chat.id,
        "Привет! Я бот для проверки домашнего задания😁\n\nВыбери экзамен:",
        reply_markup=exam_menu()
    )

    try:
        await message.delete()
    except Exception:
        pass


@dp.callback_query(F.data.startswith("exam:"))
async def exam_choose_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam_type = callback.data.split(":")[1]
    users[chat_id]["exam"] = exam_type
    users[chat_id]["mode"] = "menu"
    users[chat_id]["last_menu"] = "main"

    exam_name = "ЕГЭ" if exam_type == "ege" else "ОГЭ"

    new_msg = await send_and_store(
        chat_id,
        f"Выбран экзамен: {exam_name}\n\nГлавное меню:",
        reply_markup=main_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id].update({
        "hw": None,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "correct_answers": [],
        "wrong_questions": [],
        "repeat_answers": [],
        "repeat_results": [],
        "repeat_wrong_questions_next": [],
        "mode": "menu",
        "last_menu": "main",
    })

    new_msg = await send_and_store(
        chat_id,
        "Главное меню:",
        reply_markup=main_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "choose_hw")
async def choose_hw_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    users[chat_id]["last_menu"] = "choose_hw"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        "Выбери нужное ДЗ:",
        reply_markup=homework_menu(chat_id, "start_hw", "main_menu")
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "theory_menu")
async def theory_menu_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    users[chat_id]["last_menu"] = "theory_menu"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        "Выбери задание:",
        reply_markup=theory_menu_kb(chat_id)
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data.startswith("theory:"))
async def theory_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    t_id = callback.data.split(":")[1]

    if t_id not in theory_tasks.get(exam, {}):
        await callback.answer("Такого задания нет", show_alert=True)
        return

    users[chat_id]["last_menu"] = "theory_view"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        theory_tasks[exam][t_id]["text"],
        reply_markup=theory_back_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "materials_menu")
async def materials_menu_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    users[chat_id]["last_menu"] = "materials_menu"
    users[chat_id]["mode"] = "menu"

    new_msg = await send_and_store(
        chat_id,
        "Выбери материал:",
        reply_markup=materials_menu_kb(chat_id)
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data.startswith("material:"))
async def material_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    m_id = callback.data.split(":")[1]

    if m_id not in materials.get(exam, {}):
        await callback.answer("Такого материала нет", show_alert=True)
        return

    users[chat_id]["last_menu"] = "material_view"
    users[chat_id]["mode"] = "menu"

    material = materials[exam][m_id]
    text = f"📂 {material['title']}\n\n{material['link']}"

    new_msg = await send_and_store(
        chat_id,
        text,
        reply_markup=materials_back_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data.startswith("start_hw:"))
async def start_hw_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    hw_id = callback.data.split(":")[1]

    if hw_id not in homeworks.get(exam, {}):
        await callback.answer("Такого ДЗ нет", show_alert=True)
        return

    hw = homeworks[exam][hw_id]

    if exam == "oge":
        users[chat_id].update({
            "hw": hw_id,
            "question_index": 0,
            "score": 0,
            "answers": [],
            "correct_answers": [],
            "wrong_questions": [],
            "repeat_answers": [],
            "repeat_results": [],
            "repeat_wrong_questions_next": [],
            "mode": "homework_view",
            "last_menu": "choose_hw",
        })

        await send_history_message(
            chat_id,
            f"📄 {hw['title']}:\n{hw['file_link']}",
            reply_markup=hw_back_menu()
        )

        if callback.message.message_id not in users[chat_id]["history_message_ids"]:
            await delete_callback_message(callback)

        await callback.answer()
        return

    folder_name = normalize_homework_folder(hw_id, hw)
    folder = HOMEWORKS_DIR / folder_name
    main_file = find_file(folder, folder_name)
    answers = get_homework_answers(hw_id, hw)

    users[chat_id].update({
        "hw": hw_id,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "correct_answers": answers,
        "wrong_questions": [],
        "repeat_answers": [],
        "repeat_results": [],
        "repeat_wrong_questions_next": [],
        "mode": "homework_answering" if answers else "homework_view",
        "last_menu": "choose_hw",
    })

    if main_file:
        await send_history_document(chat_id, main_file, caption=f"📄 {hw['title']}")
    elif hw.get("file_link"):
        await send_history_message(
            chat_id,
            f"📄 {hw['title']}:\n{hw['file_link']}",
            reply_markup=hw_back_menu()
        )
    else:
        await send_history_message(
            chat_id,
            f"Файл для {hw['title']} не найден.",
            reply_markup=hw_back_menu()
        )

    if answers:
        await ask_homework_question(chat_id)
    else:
        await send_history_message(
            chat_id,
            "Для этой домашней работы ответы пока не настроены.",
            reply_markup=hw_back_menu()
        )

    if callback.message.message_id not in users[chat_id]["history_message_ids"]:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "repeat_errors")
async def repeat_errors_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)

    wrong_questions = users[chat_id].get("wrong_questions", [])
    correct_answers = users[chat_id].get("correct_answers", [])

    if not wrong_questions:
        await callback.answer("Ошибок для повтора нет", show_alert=True)
        return

    if not correct_answers:
        exam = users[chat_id].get("exam")
        hw_id = users[chat_id].get("hw")
        hw = homeworks.get(exam, {}).get(hw_id, {}) if exam and hw_id else {}
        correct_answers = get_homework_answers(hw_id, hw) if hw_id else []
        users[chat_id]["correct_answers"] = correct_answers

    users[chat_id].update({
        "question_index": 0,
        "repeat_answers": [],
        "repeat_results": [],
        "repeat_wrong_questions_next": [],
        "mode": "repeat_errors",
        "last_menu": "choose_hw",
    })

    await clear_quiz_and_probnik_messages(chat_id)
    await send_history_message(
        chat_id,
        f"Начинаем повтор ошибок. Всего заданий: {len(wrong_questions)}."
    )
    await ask_repeat_error_question(chat_id)

    if callback.message.message_id not in users[chat_id]["history_message_ids"]:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "hw_back")
async def hw_back_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)

    await clear_quiz_and_probnik_messages(chat_id)

    exam = users[chat_id].get("exam")
    if not exam:
        new_msg = await send_and_store(
            chat_id,
            "Сначала выбери экзамен:",
            reply_markup=exam_menu()
        )

        if callback.message.message_id != new_msg.message_id:
            await delete_callback_message(callback)

        await callback.answer()
        return

    users[chat_id].update({
        "hw": None,
        "question_index": 0,
        "score": 0,
        "answers": [],
        "correct_answers": [],
        "wrong_questions": [],
        "repeat_answers": [],
        "repeat_results": [],
        "repeat_wrong_questions_next": [],
        "mode": "menu",
        "last_menu": "choose_hw",
    })

    new_msg = await send_and_store(
        chat_id,
        "Выбери нужное ДЗ:",
        reply_markup=homework_menu(chat_id, "start_hw", "main_menu")
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.callback_query(F.data == "probnik")
async def probnik_handler(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    ensure_user(chat_id)
    await clear_quiz_and_probnik_messages(chat_id)

    users[chat_id]["mode"] = "probnik"
    users[chat_id]["last_menu"] = "main"

    new_msg = await send_and_store(
        chat_id,
        "Введи код варианта:",
        reply_markup=probnik_back_menu()
    )

    if callback.message.message_id != new_msg.message_id:
        await delete_callback_message(callback)

    await callback.answer()


@dp.message()
async def answer_handler(message: Message):
    if message.text and message.text.startswith("/"):
        return

    if not is_allowed(message.from_user.id):
        return

    chat_id = message.chat.id
    ensure_user(chat_id)

    if not message.text:
        try:
            await message.delete()
        except Exception:
            pass
        await send_and_store(chat_id, "Пожалуйста, отправь текст.")
        return

    if users[chat_id].get("mode") == "homework_answering":
        answer = message.text.strip()

        try:
            await message.delete()
        except Exception:
            pass

        correct_answers = users[chat_id].get("correct_answers", [])
        question_index = users[chat_id].get("question_index", 0)

        users[chat_id]["answers"].append(answer)

        if question_index < len(correct_answers):
            correct_answer = correct_answers[question_index]
            task_number = question_index + 1

            if normalize_answer(answer) == normalize_answer(correct_answer):
                await send_history_message(chat_id, f"Задание {task_number}: ✅ Верно")
            else:
                await send_history_message(chat_id, f"Задание {task_number}: ❌ Неверно")

        users[chat_id]["question_index"] = question_index + 1

        if users[chat_id]["question_index"] >= len(correct_answers):
            await finish_homework(chat_id)
        else:
            await ask_homework_question(chat_id)

        return

    if users[chat_id].get("mode") == "repeat_errors":
        answer = message.text.strip()

        try:
            await message.delete()
        except Exception:
            pass

        correct_answers = users[chat_id].get("correct_answers", [])
        wrong_questions = users[chat_id].get("wrong_questions", [])
        question_index = users[chat_id].get("question_index", 0)

        if question_index >= len(wrong_questions):
            await finish_repeat_errors(chat_id)
            return

        task_number = wrong_questions[question_index]
        users[chat_id]["repeat_answers"].append(answer)

        is_correct = False
        if 1 <= task_number <= len(correct_answers):
            correct_answer = correct_answers[task_number - 1]
            is_correct = normalize_answer(answer) == normalize_answer(correct_answer)

        users[chat_id]["repeat_results"].append((task_number, is_correct))

        if is_correct:
            await send_history_message(chat_id, f"Задание {task_number}: ✅ Верно")
        else:
            await send_history_message(chat_id, f"Задание {task_number}: ❌ Неверно")
            users[chat_id]["repeat_wrong_questions_next"].append(task_number)

        users[chat_id]["question_index"] = question_index + 1

        if users[chat_id]["question_index"] >= len(wrong_questions):
            await finish_repeat_errors(chat_id)
        else:
            await ask_repeat_error_question(chat_id)

        return

    if users[chat_id].get("mode") == "probnik":
        code = message.text.strip()

        try:
            await message.delete()
        except Exception:
            pass

        await delete_last_bot_message(chat_id)

        if code in probnik_codes:
            await send_history_message(
                chat_id,
                f"Вот твой вариант:\n{probnik_codes[code]}",
                reply_markup=probnik_back_menu()
            )
        else:
            await send_history_message(
                chat_id,
                "Неверный код❌",
                reply_markup=probnik_back_menu()
            )

        users[chat_id]["mode"] = "menu"
        users[chat_id]["last_bot_message_id"] = None
        return

    try:
        await message.delete()
    except Exception:
        pass


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())