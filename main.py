import os
import logging
import subprocess
import asyncio
import music_tag
import yt_dlp
import imageio_ffmpeg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN") 

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

if not os.path.exists("downloads"):
    os.makedirs("downloads")

class AudioEdit(StatesGroup):
    waiting_for_title = State()
    waiting_for_artist = State()
    waiting_for_album = State()
    waiting_for_cover = State()
    waiting_for_speed = State()
    waiting_for_trim = State()

def get_editor_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷 Название", callback_data="edit_title"),
            InlineKeyboardButton(text="👤 Артист", callback_data="edit_artist")
        ],
        [
            InlineKeyboardButton(text="💿 Альбом", callback_data="edit_album"),
            InlineKeyboardButton(text="🖼 Обложка", callback_data="edit_cover")
        ],
        [
            InlineKeyboardButton(text="⚡ Скорость", callback_data="edit_speed"),
            InlineKeyboardButton(text="✨ Slowed + Reverb", callback_data="effect_slowed")
        ],
        [
            InlineKeyboardButton(text="✂️ Нарезать рингтон", callback_data="edit_trim")
        ],
        [
            InlineKeyboardButton(text="📥 Скачать готовый MP3", callback_data="send_final")
        ]
    ])

def apply_slowed_reverb(input_path: str) -> str:
    output_path = input_path.replace(".mp3", "_slowed.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-filter_complex', 'atempo=0.85,aecho=0.8:0.88:60:0.4',
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

def change_speed(input_path: str, speed: float) -> str:
    output_path = input_path.replace(".mp3", f"_{speed}.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-filter:a', f'atempo={speed}',
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

def trim_audio(input_path: str, start_sec: int, duration_sec: int = 30) -> str:
    output_path = input_path.replace(".mp3", "_ringtone.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-ss', str(start_sec), '-i', input_path,
        '-t', str(duration_sec), '-c', 'copy', output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 **Привет! Я универсальный Аудио Редактор.**\n\n"
        "Пришли мне:\n"
        "1. **Любой MP3 или Голосовое сообщение** — для обработки и изменения метаданных.\n"
        "2. **Ссылку на TikTok / Pinterest / VK** — чтобы выгрузить аудиозапись!"
    )

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message, state: FSMContext):
    msg = await message.answer("⏳ Загружаю и подготавливаю файл...")
    target_obj = message.audio or message.voice or message.document
    user_file_path = f"downloads/{message.from_user.id}_current.mp3"
    
    await bot.download(target_obj, destination=user_file_path)
    await state.update_data(file_path=user_file_path)
    await msg.delete()
    await message.answer("🎵 **Файл загружен!** Выберите действие в меню ниже:", reply_markup=get_editor_keyboard())

@dp.message(F.text.startswith("http"))
async def handle_links(message: types.Message, state: FSMContext):
    msg = await message.answer("⏳ Извлекаю аудио из ссылки...")
    user_file_path = f"downloads/{message.from_user.id}_current.mp3"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'ffmpeg_location': FFMPEG_PATH,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': user_file_path.replace('.mp3', ''),
        'quiet': True
    }
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([message.text]))
        await state.update_data(file_path=user_file_path)
        await msg.delete()
        await message.answer("✅ **Аудио извлечено!** Что с ним сделать?", reply_markup=get_editor_keyboard())
    except Exception as e:
        logging.error(f"Error downloading: {e}")
        await msg.edit_text("❌ Ошибка при скачивании по ссылке. Убедитесь, что ссылка ведет на TikTok, Pinterest или SoundCloud.")

@dp.callback_query()
async def process_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()
    file_path = user_data.get("file_path")

    if not file_path or not os.path.exists(file_path):
        await callback.answer("❌ Загрузите файл заново.", show_alert=True)
        return

    if data == "edit_title":
        await state.set_state(AudioEdit.waiting_for_title)
        await callback.message.answer("Введите новое **название** трека:")
    elif data == "edit_artist":
        await state.set_state(AudioEdit.waiting_for_artist)
        await callback.message.answer("Введите имя **исполнителя (артиста)**:")
    elif data == "edit_album":
        await state.set_state(AudioEdit.waiting_for_album)
        await callback.message.answer("Введите название **альбома**:")
    elif data == "edit_cover":
        await state.set_state(AudioEdit.waiting_for_cover)
        await callback.message.answer("Пришлите **картинку/фотографию** для обложки:")
    elif data == "edit_speed":
        await state.set_state(AudioEdit.waiting_for_speed)
        await callback.message.answer("Введите коэффициент скорости (например: `1.2` для ускорения или `0.8` для замедления):")
    elif data == "edit_trim":
        await state.set_state(AudioEdit.waiting_for_trim)
        await callback.message.answer("Введите **секунду начала** нарезки (например `30` чтобы нарезать с 30-й секунды):")
    elif data == "effect_slowed":
        await callback.message.answer("⏳ Применяю эффект Slowed + Reverb...")
        new_path = apply_slowed_reverb(file_path)
        await state.update_data(file_path=new_path)
        await callback.message.answer("✨ Эффект применен!", reply_markup=get_editor_keyboard())
    elif data == "send_final":
        f = music_tag.load_file(file_path)
        title = str(f['title']) or "Аудиотрек"
        artist = str(f['artist']) or "Редактор"
        
        await callback.message.answer_audio(
            FSInputFile(file_path),
            title=title,
            performer=artist,
            caption="✅ Ваш обработанный трек готов!"
        )
    await callback.answer()

@dp.message(AudioEdit.waiting_for_title)
async def set_title(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['title'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Название изменено на: **{message.text}**", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_artist)
async def set_artist(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['artist'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Артист изменен на: **{message.text}**", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_album)
async def set_album(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['album'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Альбом изменен на: **{message.text}**", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_cover, F.photo)
async def set_cover(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    photo_path = f"downloads/{message.from_user.id}_cover.jpg"
    await bot.download(message.photo[-1], destination=photo_path)
    
    f = music_tag.load_file(user_data['file_path'])
    with open(photo_path, 'rb') as img:
        f['artwork'] = img.read()
    f.save()
    
    if os.path.exists(photo_path):
        os.remove(photo_path)
        
    await state.set_state(None)
    await message.answer("✅ **Обложка вшита в MP3!**", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_speed)
async def set_speed(message: types.Message, state: FSMContext):
    try:
        speed = float(message.text.replace(',', '.'))
        user_data = await state.get_data()
        new_path = change_speed(user_data['file_path'], speed)
        await state.update_data(file_path=new_path)
        await state.set_state(None)
        await message.answer(f"⚡ Скорость изменена x{speed}!", reply_markup=get_editor_keyboard())
    except:
        await message.answer("❌ Введите число, например `1.2` или `0.8`")

@dp.message(AudioEdit.waiting_for_trim)
async def set_trim(message: types.Message, state: FSMContext):
    try:
        start_sec = int(message.text)
        user_data = await state.get_data()
        new_path = trim_audio(user_data['file_path'], start_sec=start_sec, duration_sec=30)
        await state.update_data(file_path=new_path)
        await state.set_state(None)
        await message.answer("✂️ 30-секундный рингтон успешно нарезан!", reply_markup=get_editor_keyboard())
    except:
        await message.answer("❌ Введите целое число секунд (например `30`)")

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Сброс прошлых зависших сессий
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
