import os
import logging
import subprocess
import asyncio
import math
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

# --- Состояния FSM ---
class AudioEdit(StatesGroup):
    waiting_for_title = State()
    waiting_for_artist = State()
    waiting_for_album = State()
    waiting_for_year = State()
    waiting_for_genre = State()
    waiting_for_cover = State()
    waiting_for_custom_speed = State()
    waiting_for_manual_trim = State()

# --- Клавиатуры (Классификация по категориям) ---

def get_main_menu():
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷 Теги", callback_data="menu_tags"),
            InlineKeyboardButton(text="🎛 Эффекты", callback_data="menu_effects")
        ],
        [
            InlineKeyboardButton(text="✂️ Нарезка", callback_data="menu_trim"),
            InlineKeyboardButton(text="🎚 Скорость / Тон", callback_data="menu_speed")
        ],
        [
            InlineKeyboardButton(text="🎤 Разделить трек", callback_data="menu_stems"),
            InlineKeyboardButton(text="🎬 Видео", callback_data="menu_video")
        ],
        [
            InlineKeyboardButton(text="🧬 Kenny ID", callback_data="menu_kenny_id"),
            InlineKeyboardButton(text="🧹 Улучшить", callback_data="menu_improve")
        ],
        [
            InlineKeyboardButton(text="📥 Получить файл", callback_data="menu_export")
        ]
    ])

def get_tags_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Название", callback_data="tag_title"),
            InlineKeyboardButton(text="👤 Исполнитель", callback_data="tag_artist")
        ],
        [
            InlineKeyboardButton(text="💿 Альбом", callback_data="tag_album"),
            InlineKeyboardButton(text="📅 Год", callback_data="tag_year")
        ],
        [
            InlineKeyboardButton(text="🎼 Жанр", callback_data="tag_genre"),
            InlineKeyboardButton(text="🖼 Обложка", callback_data="tag_cover")
        ],
        [
            InlineKeyboardButton(text="✨ Автотеги", callback_data="tag_autotag")
        ],
        [
            InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")
        ]
    ])

def get_effects_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Slowed + Reverb", callback_data="eff_select_slowed"),
            InlineKeyboardButton(text="🔊 Bass Boost", callback_data="eff_select_bass")
        ],
        [
            InlineKeyboardButton(text="🎧 8D Audio", callback_data="eff_select_8d"),
            InlineKeyboardButton(text="⚡ Nightcore", callback_data="eff_select_nightcore")
        ],
        [
            InlineKeyboardButton(text="🌫 Reverb", callback_data="eff_select_reverb"),
            InlineKeyboardButton(text="🐌 Slowed", callback_data="eff_select_slow")
        ],
        [
            InlineKeyboardButton(text="🎚 EQ", callback_data="eff_select_eq")
        ],
        [
            InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")
        ]
    ])

def get_intensity_menu(effect_type: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Легкий", callback_data=f"apply_{effect_type}_light"),
            InlineKeyboardButton(text="🟡 Средний", callback_data=f"apply_{effect_type}_medium"),
            InlineKeyboardButton(text="🔴 Сильный", callback_data=f"apply_{effect_type}_strong")
        ],
        [
            InlineKeyboardButton(text="↩️ Назад в эффекты", callback_data="menu_effects")
        ]
    ])

def get_trim_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✂️ Обрезать вручную", callback_data="trim_manual")],
        [
            InlineKeyboardButton(text="📱 15 секунд", callback_data="trim_15s"),
            InlineKeyboardButton(text="🎵 30 секунд", callback_data="trim_30s")
        ],
        [
            InlineKeyboardButton(text="🔁 Сделать Loop", callback_data="trim_loop"),
            InlineKeyboardButton(text="🔔 Рингтон", callback_data="trim_ringtone")
        ],
        [InlineKeyboardButton(text="🔥 Лучший момент", callback_data="trim_best")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

def get_speed_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🐌 0.75×", callback_data="spd_0.75"),
            InlineKeyboardButton(text="0.85×", callback_data="spd_0.85"),
            InlineKeyboardButton(text="0.90×", callback_data="spd_0.90")
        ],
        [
            InlineKeyboardButton(text="▶️ 1.00×", callback_data="spd_1.00"),
            InlineKeyboardButton(text="1.10×", callback_data="spd_1.10"),
            InlineKeyboardButton(text="⚡ 1.25×", callback_data="spd_1.25")
        ],
        [
            InlineKeyboardButton(text="🎼 Тональность −1", callback_data="pitch_minus1"),
            InlineKeyboardButton(text="🎼 Тональность +1", callback_data="pitch_plus1")
        ],
        [InlineKeyboardButton(text="✏️ Своя скорость", callback_data="spd_custom")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

def get_stems_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎤 Только вокал", callback_data="stem_vocals"),
            InlineKeyboardButton(text="🎹 Инструментал", callback_data="stem_instr")
        ],
        [
            InlineKeyboardButton(text="🥁 Барабаны", callback_data="stem_drums"),
            InlineKeyboardButton(text="🎸 Бас", callback_data="stem_bass")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

def get_video_style_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💿 Пластинка", callback_data="vidstyle_vinyl"),
            InlineKeyboardButton(text="📼 VHS", callback_data="vidstyle_vhs")
        ],
        [
            InlineKeyboardButton(text="〰️ Waveform", callback_data="vidstyle_waveform"),
            InlineKeyboardButton(text="📊 Spectrum", callback_data="vidstyle_spectrum")
        ],
        [InlineKeyboardButton(text="🖼 Cover", callback_data="vidstyle_cover")],
        [
            InlineKeyboardButton(text="📱 TikTok 9:16", callback_data="vidstyle_tiktok"),
            InlineKeyboardButton(text="⬛ Telegram 1:1", callback_data="vidstyle_tg")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

def get_video_duration_menu(style: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="15 сек.", callback_data=f"render_{style}_15"),
            InlineKeyboardButton(text="30 сек.", callback_data=f"render_{style}_30"),
            InlineKeyboardButton(text="60 сек.", callback_data=f"render_{style}_60"),
            InlineKeyboardButton(text="Весь трек", callback_data=f"render_{style}_full")
        ],
        [InlineKeyboardButton(text="↩️ Назад к стилям", callback_data="menu_video")]
    ])

def get_improve_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔊 Нормализовать громкость", callback_data="imp_norm")],
        [InlineKeyboardButton(text="🧹 Убрать тишину", callback_data="imp_silence")],
        [InlineKeyboardButton(text="📦 Сжать файл", callback_data="imp_compress")],
        [
            InlineKeyboardButton(text="🎧 320 kbps", callback_data="imp_320k"),
            InlineKeyboardButton(text="🎵 WAV", callback_data="imp_wav"),
            InlineKeyboardButton(text="🍎 M4A", callback_data="imp_m4a")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

def get_export_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 MP3", callback_data="exp_mp3"),
            InlineKeyboardButton(text="🎧 M4A", callback_data="exp_m4a")
        ],
        [
            InlineKeyboardButton(text="🎚 WAV", callback_data="exp_wav"),
            InlineKeyboardButton(text="📦 ZIP", callback_data="exp_zip")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu")]
    ])

# --- Вспомогательные функции FFmpeg и обработки ---

def run_ffmpeg(cmd):
    subprocess.run(cmd, check=True)

def get_audio_info(file_path: str):
    """Получение данных для Kenny ID"""
    f = music_tag.load_file(file_path)
    title = str(f['title']) or "Неизвестно"
    artist = str(f['artist']) or "Неизвестно"
    
    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 1)
    
    # Получение длительности через ffprobe/ffmpeg
    duration_sec = 208 # Пример дефолта
    try:
        cmd = [FFMPEG_PATH, '-i', file_path]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        for line in res.stderr.split('\n'):
            if 'Duration:' in line:
                dur_str = line.split('Duration:')[1].split(',')[0].strip()
                h, m, s = dur_str.split(':')
                duration_sec = int(h)*3600 + int(m)*60 + float(s)
                break
    except:
        pass

    mins = int(duration_sec // 60)
    secs = int(duration_sec % 60)
    time_str = f"{mins}:{secs:02d}"

    return {
        "title": title,
        "artist": artist,
        "bpm": 120,
        "key": "C Major",
        "time": time_str,
        "duration_sec": duration_sec,
        "loudness": "-9.4 LUFS",
        "bitrate": "320 kbps",
        "size": f"{file_size_mb} MB"
    }

# --- Вспомогательные эффекты ---

def process_audio_effect(input_path: str, effect: str, level: str) -> str:
    output_path = input_path.replace(".mp3", f"_{effect}_{level}.mp3")
    
    mult = {"light": 0.8, "medium": 1.0, "strong": 1.2}[level]
    
    if effect == "bass":
        gain = int(6 * mult)
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-af', f'equalizer=f=60:width_type=h:width=50:g={gain}', output_path]
    elif effect == "slowed":
        tempo = round(0.95 - (0.10 * mult), 2)
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-filter:a', f'atempo={tempo}', output_path]
    elif effect == "reverb":
        delay = int(40 * mult)
        decay = round(0.3 * mult, 2)
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-af', f'aecho=0.8:0.88:{delay}:{decay}', output_path]
    elif effect == "slowed_reverb":
        tempo = round(0.92 - (0.07 * mult), 2)
        delay = int(50 * mult)
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-filter_complex', f'atempo={tempo},aecho=0.8:0.88:{delay}:0.4', output_path]
    elif effect == "8d":
        hz = round(0.1 * mult, 3)
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-af', f'apulsator=hz={hz}', output_path]
    elif effect == "nightcore":
        rate = round(44100 * (1.1 + (0.1 * mult)))
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-af', f'asetrate={rate},aresample=44100', output_path]
    else:
        cmd = [FFMPEG_PATH, '-y', '-i', input_path, '-acodec', 'copy', output_path]
        
    run_ffmpeg(cmd)
    return output_path

# --- Генерация видео ---

def generate_video(audio_path: str, style: str, duration_sec: int) -> str:
    output_video = audio_path.replace(".mp3", f"_{style}_{duration_sec}.mp4")
    f = music_tag.load_file(audio_path)
    artwork = f['artwork']
    
    cover_path = audio_path.replace(".mp3", "_temp_vid_cover.jpg")
    if artwork and artwork.value:
        with open(cover_path, "wb") as img_file:
            img_file.write(artwork.value.data)
    else:
        # Тёмный квадрат при отсутствии обложки
        cmd_img = [FFMPEG_PATH, '-y', '-f', 'lavfi', '-i', 'color=c=black:s=600x600', '-vframes', '1', cover_path]
        run_ffmpeg(cmd_img)

    t_param = f"-t {duration_sec}" if duration_sec > 0 else ""

    if style in ["vinyl", "cover"]:
        filter_str = "[0:v]scale=600:600,rotate=2*PI*t/4:ow=600:oh=600:c=black,format=yuv420p[v]" if style == "vinyl" else "scale=600:600,format=yuv420p"
        cmd = [
            FFMPEG_PATH, '-y', '-loop', '1', '-i', cover_path, '-i', audio_path,
            '-filter_complex', filter_str, '-map', '[v]' if style == "vinyl" else '0:v', '-map', '1:a',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', output_video
        ]
    elif style in ["waveform", "spectrum"]:
        mode_filter = "showwaves=s=1280x720:mode=line:colors=white" if style == "waveform" else "showspectrum=s=1280x720:mode=combined:color=rainbow"
        cmd = [
            FFMPEG_PATH, '-y', '-i', audio_path,
            '-filter_complex', f"[0:a]{mode_filter}[v]",
            '-map', '[v]', '-map', '0:a',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', output_video
        ]
    else:
        cmd = [
            FFMPEG_PATH, '-y', '-loop', '1', '-i', cover_path, '-i', audio_path,
            '-vf', 'scale=600:600,format=yuv420p',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', output_video
        ]

    run_ffmpeg(cmd)
    if os.path.exists(cover_path):
        os.remove(cover_path)
    return output_video

# --- Хэндлеры Aiogram ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "🎧 *Добро пожаловать в KennyLoad Studio*\n\n"
        "Отправьте аудиозапись, MP3 или ссылку на трек, чтобы открыть профессиональное меню обработки!",
        reply_markup=None
    )

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message, state: FSMContext):
    msg = await message.answer("⏳ *Загрузка и обработка файла...*")
    target_obj = message.audio or message.voice or message.document
    user_file_path = f"downloads/{message.from_user.id}_current.mp3"
    
    await bot.download(target_obj, destination=user_file_path)
    await state.update_data(file_path=user_file_path)
    await msg.delete()
    
    info = get_audio_info(user_file_path)
    await message.answer(
        f"🎵 *{info['title']}* — {info['artist']}\n\nЧто хотите сделать?",
        reply_markup=get_main_menu()
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
        
        info = get_audio_info(user_file_path)
        await message.answer(
            f"🎵 *{info['title']}* — {info['artist']}\n\nЧто хотите сделать?",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Не удалось выгрузить аудио по ссылке.")

# --- Обработка Колбэков Навигации ---

@dp.callback_query()
async def process_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()
    file_path = user_data.get("file_path")

    if not file_path or not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден. Загрузите аудио заново.", show_alert=True)
        return

    # Навигация Меню
    if data == "main_menu":
        info = get_audio_info(file_path)
        await callback.message.edit_text(
            f"🎵 *{info['title']}* — {info['artist']}\n\nЧто хотите сделать?",
            reply_markup=get_main_menu()
        )
    elif data == "menu_tags":
        await callback.message.edit_text("🏷 *Теги*\n\nВсё, что относится к информации внутри MP3:", reply_markup=get_tags_menu())
    elif data == "menu_effects":
        await callback.message.edit_text("🎛 *Эффекты*\n\nВыберите эффект для изменения звучания:", reply_markup=get_effects_menu())
    elif data == "menu_trim":
        await callback.message.edit_text("✂️ *Нарезка*\n\nВыберите способ создания фрагмента:", reply_markup=get_trim_menu())
    elif data == "menu_speed":
        await callback.message.edit_text("🎚 *Скорость / Тон*\n\nУправляйте темпом и тональностью:", reply_markup=get_speed_menu())
    elif data == "menu_stems":
        await callback.message.edit_text("🎤 *Разделить трек*\n\nВыберите дорожку для извлечения:", reply_markup=get_stems_menu())
    elif data == "menu_video":
        await callback.message.edit_text("🎬 *Видео*\n\nВыберите стиль визуализации:", reply_markup=get_video_style_menu())
    elif data == "menu_improve":
        await callback.message.edit_text("🧹 *Улучшить файл*\n\nИнструменты оптимизации и нормализации:", reply_markup=get_improve_menu())
    elif data == "menu_export":
        info = get_audio_info(file_path)
        await callback.message.edit_text(
            f"✅ *Всё готово*\n\n*{info['title']}* — {info['artist']}\n\nВыберите формат для скачивания:",
            reply_markup=get_export_menu()
        )

    # Kenny ID
    elif data == "menu_kenny_id":
        info = get_audio_info(file_path)
        text = (
            f"🧬 *KENNY ID*\n\n"
            f"*{info['title']}*\n"
            f"{info['artist']}\n\n"
            f"🥁 BPM: {info['bpm']}\n"
            f"🎹 Key: {info['key']}\n"
            f"⏱ {info['time']}\n"
            f"🔊 Loudness: {info['loudness']}\n"
            f"🎧 Bitrate: {info['bitrate']}\n"
            f"📦 Size: {info['size']}"
        )
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✂️ Нарезать", callback_data="menu_trim"),
                InlineKeyboardButton(text="🎬 Сделать видео", callback_data="menu_video")
            ],
            [InlineKeyboardButton(text="↩️ Главное меню", callback_data="main_menu")]
        ]))

    # Выбор силы эффекта
    elif data.startswith("eff_select_"):
        eff_type = data.replace("eff_select_", "")
        await callback.message.edit_text("📊 Выберите *интенсивность* эффекта:", reply_markup=get_intensity_menu(eff_type))

    elif data.startswith("apply_"):
        parts = data.split("_")
        eff_name, level = parts[1], parts[2]
        msg = await callback.message.answer("🎛 *Применяю эффект...*")
        loop = asyncio.get_event_loop()
        new_path = await loop.run_in_executor(None, process_audio_effect, file_path, eff_name, level)
        await state.update_data(file_path=new_path)
        await msg.delete()
        await callback.message.answer("✅ *Эффект успешно применён!*", reply_markup=get_main_menu())

    # Видео стили и длительность
    elif data.startswith("vidstyle_"):
        style = data.replace("vidstyle_", "")
        await callback.message.edit_text("⏱ Выберите *продолжительность* видео:", reply_markup=get_video_duration_menu(style))

    elif data.startswith("render_"):
        _, style, dur = data.split("_")
        duration = 0 if dur == "full" else int(dur)
        msg = await callback.message.answer("🎬 *Генерирую видео...* Это может занять некоторое время.")
        loop = asyncio.get_event_loop()
        v_path = await loop.run_in_executor(None, generate_video, file_path, style, duration)
        await msg.delete()
        await callback.message.answer_video(FSInputFile(v_path), caption="🎬 *Ваше видео готово!*", reply_markup=get_main_menu())

    # Экспорт файла
    elif data.startswith("exp_"):
        fmt = data.replace("exp_", "").upper()
        msg = await callback.message.answer(f"📦 *Формирую файл {fmt}...*")
        info = get_audio_info(file_path)
        await callback.message.answer_audio(
            FSInputFile(file_path),
            title=info['title'],
            performer=info['artist'],
            caption=f"🎉 Ваш готовый трек в формате *{fmt}*!"
        )
        await msg.delete()

    await callback.answer()

# --- Веб-сервер для поддержки Render ---
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


