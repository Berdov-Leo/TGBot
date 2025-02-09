import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.types import File
from aiogram.types import BufferedInputFile
import os
import time

from config import BOT_TOKEN, CATEGORIES, QUESTIONS, ADMIN_ID

# Настройка логирования ответов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot_logs")
handler = logging.FileHandler("user_answers.log", mode="a", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Путь для сохранения медиафайлов
MEDIA_DIR = "media_files"

if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Состояния
class Form(StatesGroup):
    category = State()
    answering = State()
    media = State()  # Для обработки фото/видео

# Клавиатура для выбора категории
def get_category_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=category)] for category in CATEGORIES],
        resize_keyboard=True,
    )
    return keyboard

# Функция для загрузки медиафайлов
async def download_media(file: File, file_type: str) -> str:
    """Загружает медиафайл и возвращает путь к файлу."""
    timestamp = int(time.time())  # Текущее время в секундах
    file_extension = file.file_path.split(".")[-1]  # Получаем расширение файла
    file_name = f"{timestamp}_{file_type}.{file_extension}"  # Генерируем новое имя
    destination = os.path.join(MEDIA_DIR, file_name)

    # Скачиваем файл
    await bot.download_file(file.file_path, destination=destination)
    return destination

# Старт
@dp.message(Command('start'))
async def start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Выбери категорию:", reply_markup=get_category_keyboard())
    await state.set_state(Form.category)

from aiogram.types import InputFile

from aiogram.types import BufferedInputFile

# Команда для администратора: получить все медиафайлы
@dp.message(lambda message: message.text == "/get_media")  # Обработка вне состояний
async def get_media(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для этой команды.")
        return

    media_files = [f for f in os.listdir(MEDIA_DIR) if os.path.isfile(os.path.join(MEDIA_DIR, f))]
    if not media_files:
        await message.answer("Нет загруженных медиафайлов.")
        return

    await message.answer("Список загруженных медиафайлов:")
    for file_name in media_files:
        file_path = os.path.join(MEDIA_DIR, file_name)
        try:
            with open(file_path, 'rb') as file:
                input_file = BufferedInputFile(file.read(), filename=file_name)
                if file_name.endswith((".jpg", ".png")):
                    await message.answer_photo(photo=input_file, caption=f"Файл: {file_name}")
                elif file_name.endswith(".mp4"):
                    await message.answer_video(video=input_file, caption=f"Файл: {file_name}")
                else:
                    await message.answer_document(document=input_file, caption=f"Файл: {file_name}")
        except Exception as e:
            await message.answer(f"Не удалось отправить файл {file_name}: {e}")

# Команда для администратора: получить файл логов
@dp.message(lambda message: message.text == "/get_logs")  # Обработка вне состояний
async def get_logs(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для этой команды.")
        return

    log_file_path = "user_answers.log"  # Путь к файлу логов

    if not os.path.exists(log_file_path):
        await message.answer("Файл логов пуст или не существует.")
        return

    try:
        with open(log_file_path, 'rb') as log_file:
            input_file = BufferedInputFile(log_file.read(), filename="user_answers.log")
            await message.answer_document(document=input_file, caption="Вот файл логов:")
    except Exception as e:
        await message.answer(f"Произошла ошибка при отправке файла логов: {e}")

# Выбор категории
@dp.message(Form.category)
async def choose_category(message: types.Message, state: FSMContext):
    if message.text not in CATEGORIES:
        await message.answer("Пожалуйста, выбери категорию из списка.")
        return

    await state.update_data(category=message.text, question_index=0, answers={})
    questions = QUESTIONS.get(message.text, [])
    if not questions:
        await message.answer("К сожалению, для этой категории нет вопросов.")
        await state.clear()
        return

    await ask_question(message, state)

# Задать вопрос
async def ask_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    question_index = data.get('question_index', 0)
    questions = QUESTIONS.get(category, [])

    if question_index >= len(questions):
        await generate_report(message, state)
        return

    current_question = questions[question_index]
    is_media_question = question_index >= len(questions) - 2  # Проверяем, является ли это медиа-вопросом

    if is_media_question:
        await message.answer(f"Вопрос {question_index + 1}: {current_question}\nОтправьте фото или видео.")
        await state.set_state(Form.media)
    else:
        await message.answer(f"Вопрос {question_index + 1}: {current_question}")
        await state.set_state(Form.answering)

# Обработка текстового ответа
@dp.message(Form.answering)
async def process_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    question_index = data.get('question_index', 0)
    answers = data.get('answers', {})

    questions = QUESTIONS.get(category, [])
    current_question = questions[question_index]

    # Сохраняем ответ
    answers[current_question] = message.text
    await state.update_data(answers=answers, question_index=question_index + 1)

    # Переходим к следующему вопросу
    await ask_question(message, state)

# Обработка фото/видео
@dp.message(Form.media)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo or message.video:
        data = await state.get_data()
        category = data.get('category')
        question_index = data.get('question_index', 0)
        answers = data.get('answers', {})

        questions = QUESTIONS.get(category, [])
        current_question = questions[question_index]

        # Сохраняем медиафайл
        if message.photo:
            file_id = message.photo[-1].file_id  # Берем последний элемент (лучшее качество)
            file_type = "photo"
        elif message.video:
            file_id = message.video.file_id
            file_type = "video"

        file: File = await bot.get_file(file_id)
        file_path = await download_media(file, file_type)

        # Сохраняем путь к файлу в ответах
        answers[current_question] = f"Media: {file_path}"
        await state.update_data(answers=answers, question_index=question_index + 1)

        # Логируем путь к файлу
        logger.info(f"User ID: {message.from_user.id}, Media saved: {file_path}")

        # Переходим к следующему вопросу
        await ask_question(message, state)
    else:
        await message.answer("Пожалуйста, отправьте фото или видео.")

# Генерация отчета
async def generate_report(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    answers = data.get('answers', {})

    report = f"Отчет по категории: {category}\n\n"
    for question, answer in answers.items():
        report += f"Вопрос: {question}\nОтвет: {answer}\n\n"

    # Отправляем отчет пользователю
    await message.answer(report)

    # Логируем ответы
    logger.info(f"User ID: {message.from_user.id}, Category: {category}, Answers: {answers}")

    # Возвращаемся к выбору категории
    await message.answer("Опрос завершен. Выберите новую категорию:", reply_markup=get_category_keyboard())
    await state.set_state(Form.category)

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())