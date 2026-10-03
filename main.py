import os
import logging
import subprocess
import asyncio
import music_tag
import yt_dlp
import imageio_ffmpeg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8300695982:AAG7t80QBHMZGA041C3IRI2qcuX7CcK4YD8")
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

if not os.path.exists("downloads"):
    os.makedirs("downloads")

class AudioEdit(StatesGroup):
    waiting_for_title = State()
    waiting_for_artist = State()
    waiting_for_album = State()
    waiting_for_year = State()
    waiting_for_genre = State()
    waiting_for_cover = State()
    waiting_for_speed = State()
    waiting_for_trim = State()

def get_editor_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷 Название", callback_data="edit_title"),
            InlineKeyboardButton(text="👤 Исполнитель", callback_data="edit_artist")
        ],
        [
            InlineKeyboardButton(text="💿 Альбом", callback_data="edit_album"),
            InlineKeyboardButton(text="📅 Год / Жанр", callback_data="edit_meta_extra")
        ],
        [
            InlineKeyboardButton(text="🖼 Обложка", callback_data="edit_cover"),
            InlineKeyboardButton(text="✂️ Рингтон (30с)", callback_data="edit_trim")
        ],
        [
            InlineKeyboardButton(text="✨ Slowed + Reverb", callback_data="effect_slowed"),
            InlineKeyboardButton(text="🔊 Bass Boost", callback_data="effect_bass")
        ],
        [
            InlineKeyboardButton(text="🎧 8D Audio", callback_data="effect_8d"),
            InlineKeyboardButton(text="⚡ Nightcore", callback_data="effect_nightcore")
        ],
        [
            InlineKeyboardButton(text="🚀 Изменить скорость", callback_data="edit_speed"),
            InlineKeyboardButton(text="📀 Видео с пластинкой", callback_data="effect_vinyl")
        ],
        [
            InlineKeyboardButton(text="📥 Скачать готовый MP3", callback_data="send_final")
        ]
    ])

def run_ffmpeg(cmd):
    subprocess.run(cmd, check=True)

def apply_slowed_reverb(input_path: str) -> str:
    output_path = input_path.replace(".mp3", "_slowed.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-filter_complex', 'atempo=0.85,aecho=0.8:0.88:60:0.4',
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def apply_bass_boost(input_path: str) -> str:
    output_path = input_path.replace(".mp3", "_bass.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-af', 'equalizer=f=60:width_type=h:width=50:g=10',
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def apply_8d_audio(input_path: str) -> str:
    output_path = input_path.replace(".mp3", "_8d.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-af', 'apulsator=hz=0.125',
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def apply_nightcore(input_path: str) -> str:
    output_path = input_path.replace(".mp3", "_nightcore.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-af', 'asetrate=44100*1.25,aresample=44100',
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def change_speed(input_path: str, speed: float) -> str:
    output_path = input_path.replace(".mp3", f"_{speed}.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-filter:a', f'atempo={speed}',
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def trim_audio(input_path: str, start_sec: int, duration_sec: int = 30) -> str:
    output_path = input_path.replace(".mp3", "_ringtone.mp3")
    cmd = [
        FFMPEG_PATH, '-y', '-ss', str(start_sec), '-i', input_path,
        '-t', str(duration_sec), '-c', 'copy', output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def make_vinyl_video(audio_path: str) -> str:
    output_video = audio_path.replace(".mp3", "_vinyl.mp4")
    f = music_tag.load_file(audio_path)
    artwork = f['artwork']
    
    cover_path = audio_path.replace(".mp3", "_temp_cover.jpg")
    has_cover = False
    
    if artwork and artwork.value:
        with open(cover_path, "wb") as img_file:
            img_file.write(artwork.value.data)
        has_cover = True
    
    if not has_cover:
        cmd_img = [
            FFMPEG_PATH, '-y', '-f', 'lavfi', '-i', 'color=c=0x1a1a1a:s=600x600',
            '-vframes', '1', cover_path
        ]
        run_ffmpeg(cmd_img)

    cmd = [
        FFMPEG_PATH, '-y',
        '-loop', '1', '-i', cover_path,
        '-i', audio_path,
        '-filter_complex',
        "[0:v]scale=600:600,format=qtrgb,rotate=2*PI*t/4:c=black@0:ow=rotw(iw):oh=roth(ih),format=yuv420p[v]",
        '-map', '[v]', '-map', '1:a',
        '-c:v', 'libx264', '-shortest', '-pix_fmt', 'yuv420p',
        output_video
    ]
    run_ffmpeg(cmd)

    if os.path.exists(cover_path):
        os.remove(cover_path)

    return output_video

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "🎧 *Добро пожаловать в KennyLoad Studio*\n\n"
        "Скачивайте аудио и редактируйте его прямо в боте.\n\n"
        "📥 *Отправьте ссылку*\n"
        "TikTok • Pinterest • VK • YouTube\n\n"
        "Или загрузите MP3 / голосовое сообщение.\n\n"
        "✨ *Возможности*\n\n"
        "• Обложка и теги - артист, название, альбом\n"
        "• Slowed + Reverb\n"
        "• Bass Boost\n"
        "• 8D Audio\n"
        "• Nightcore\n"
        "• Изменение скорости\n"
        "• Нарезка 30-секундных рингтонов\n"
        "• 📀 Видео с вращающейся пластинкой\n\n"
        "Отправьте ссылку или аудиофайл, чтобы начать 🎵"
    )

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message, state: FSMContext):
    msg = await message.answer("⏳ *Загрузка файла...* Пожалуйста, подождите.")
    target_obj = message.audio or message.voice or message.document
    user_file_path = f"downloads/{message.from_user.id}_current.mp3"
    
    await bot.download(target_obj, destination=user_file_path)
    await state.update_data(file_path=user_file_path)
    await msg.delete()
    await message.answer(
        "🎵 *Файл успешно загружен!*\n\nВыберите действие в меню ниже:",
        reply_markup=get_editor_keyboard()
    )

@dp.message(F.text.startswith("http"))
async def handle_links(message: types.Message, state: FSMContext):
    msg = await message.answer("🔍 *Извлекаю аудио по ссылке...*")
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
        await message.answer(
            "✅ *Аудиозапись успешно выгружена!*\n\nЧто хотите сделать с треком?",
            reply_markup=get_editor_keyboard()
        )
    except Exception as e:
        logging.error(f"Error downloading: {e}")
        await msg.edit_text("❌ *Не удалось скачать аудио.* Убедитесь, что ссылка корректна.")

@dp.callback_query()
async def process_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()
    file_path = user_data.get("file_path")

    if not file_path or not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден. Отправьте аудиозапись заново.", show_alert=True)
        return

    if data == "edit_title":
        await state.set_state(AudioEdit.waiting_for_title)
        await callback.message.answer("✏️ Введите новое *название* трека:")
    elif data == "edit_artist":
        await state.set_state(AudioEdit.waiting_for_artist)
        await callback.message.answer("👤 Введите имя *исполнителя (артиста)*:")
    elif data == "edit_album":
        await state.set_state(AudioEdit.waiting_for_album)
        await callback.message.answer("💿 Введите название *альбома*:")
    elif data == "edit_meta_extra":
        await state.set_state(AudioEdit.waiting_for_year)
        await callback.message.answer("📅 Введите *год релиза* (например `2024`):")
    elif data == "edit_cover":
        await state.set_state(AudioEdit.waiting_for_cover)
        await callback.message.answer("🖼 Пришлите *фотографию/картинку* для обложки:")
    elif data == "edit_speed":
        await state.set_state(AudioEdit.waiting_for_speed)
        await callback.message.answer("🚀 Введите коэффициент скорости (например: `1.2` для ускорения или `0.85` для замедления):")
    elif data == "edit_trim":
        await state.set_state(AudioEdit.waiting_for_trim)
        await callback.message.answer("✂️ Введите *секунду начала* нарезки (например `30`):")
    
    elif data in ["effect_slowed", "effect_bass", "effect_8d", "effect_nightcore"]:
        msg = await callback.message.answer("🎛 *Применяю звуковой эффект...*")
        loop = asyncio.get_event_loop()
        
        if data == "effect_slowed":
            new_path = await loop.run_in_executor(None, apply_slowed_reverb, file_path)
            eff_name = "Slowed + Reverb"
        elif data == "effect_bass":
            new_path = await loop.run_in_executor(None, apply_bass_boost, file_path)
            eff_name = "Bass Boost"
        elif data == "effect_8d":
            new_path = await loop.run_in_executor(None, apply_8d_audio, file_path)
            eff_name = "8D Audio"
        elif data == "effect_nightcore":
            new_path = await loop.run_in_executor(None, apply_nightcore, file_path)
            eff_name = "Nightcore"
            
        await state.update_data(file_path=new_path)
        await msg.delete()
        
        f = music_tag.load_file(new_path)
        title = str(f['title']) or "Аудиотрек"
        artist = str(f['artist']) or "Kenny Studio"

        await callback.message.answer_audio(
            FSInputFile(new_path),
            title=title,
            performer=artist,
            caption=f"✨ *Эффект {eff_name} успешно применён!*",
            reply_markup=get_editor_keyboard()
        )

    elif data == "effect_vinyl":
        msg = await callback.message.answer("🎬 *Генерирую видео с вращающейся пластинкой...* Это займет немного времени.")
        loop = asyncio.get_event_loop()
        try:
            video_path = await loop.run_in_executor(None, make_vinyl_video, file_path)
            await msg.delete()
            await callback.message.answer_video(
                FSInputFile(video_path),
                caption="📀 *Ваше видео с пластинкой готово!*",
                reply_markup=get_editor_keyboard()
            )
        except Exception as e:
            logging.error(f"Vinyl error: {e}")
            await msg.edit_text("❌ Не удалось создать видео с пластинкой.")

    elif data == "send_final":
        msg = await callback.message.answer("📦 *Формирую итоговый файл...*")
        f = music_tag.load_file(file_path)
        title = str(f['title']) or "Аудиотрек"
        artist = str(f['artist']) or "Kenny Studio"
        
        await callback.message.answer_audio(
            FSInputFile(file_path),
            title=title,
            performer=artist,
            caption="🎉 *Ваш готовый трек!*"
        )
        await msg.delete()

    await callback.answer()

@dp.message(AudioEdit.waiting_for_title)
async def set_title(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['title'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Название изменено на: *{message.text}*", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_artist)
async def set_artist(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['artist'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Артист изменён на: *{message.text}*", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_album)
async def set_album(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['album'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Альбом изменён на: *{message.text}*", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_year)
async def set_year(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    try:
        f['year'] = int(message.text)
        f.save()
        await state.set_state(AudioEdit.waiting_for_genre)
        await message.answer("🎸 Теперь введите *жанр* трека (например `Hip-Hop` или `Phonk`):")
    except:
        await message.answer("❌ Введите год числом, например `2024`")

@dp.message(AudioEdit.waiting_for_genre)
async def set_genre(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    f = music_tag.load_file(user_data['file_path'])
    f['genre'] = message.text
    f.save()
    await state.set_state(None)
    await message.answer(f"✅ Жанр изменён на: *{message.text}*", reply_markup=get_editor_keyboard())

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
    await message.answer("✅ *Обложка успешно вшита в MP3!*", reply_markup=get_editor_keyboard())

@dp.message(AudioEdit.waiting_for_speed)
async def set_speed(message: types.Message, state: FSMContext):
    try:
        speed = float(message.text.replace(',', '.'))
        user_data = await state.get_data()
        loop = asyncio.get_event_loop()
        msg = await message.answer("⚡ *Изменяю скорость...*")
        new_path = await loop.run_in_executor(None, change_speed, user_data['file_path'], speed)
        await state.update_data(file_path=new_path)
        await state.set_state(None)
        await msg.delete()

        f = music_tag.load_file(new_path)
        title = str(f['title']) or "Аудиотрек"
        artist = str(f['artist']) or "Kenny Studio"

        await message.answer_audio(
            FSInputFile(new_path),
            title=title,
            performer=artist,
            caption=f"🚀 *Скорость `x{speed}` успешно применена!*",
            reply_markup=get_editor_keyboard()
        )
    except:
        await message.answer("❌ Введите число, например `1.2` или `0.85`")

@dp.message(AudioEdit.waiting_for_trim)
async def set_trim(message: types.Message, state: FSMContext):
    try:
        start_sec = int(message.text)
        user_data = await state.get_data()
        loop = asyncio.get_event_loop()
        msg = await message.answer("✂️ *Нарезаю рингтон...*")
        new_path = await loop.run_in_executor(None, trim_audio, user_data['file_path'], start_sec, 30)
        await state.update_data(file_path=new_path)
        await state.set_state(None)
        await msg.delete()

        f = music_tag.load_file(new_path)
        title = str(f['title']) or "Аудиотрек"
        artist = str(f['artist']) or "Kenny Studio"

        await message.answer_audio(
            FSInputFile(new_path),
            title=title,
            performer=artist,
            caption="✂️ *Рингтон (30 секунд) успешно создан!*",
            reply_markup=get_editor_keyboard()
        )
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

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

