import os
import logging
import shutil
import asyncio
import music_tag
import imageio_ffmpeg
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
)

from session_manager import session_mgr
from i18n import get_txt

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8300695982:AAG7t80QBHMZGA041C3IRI2qcuX7CcK4YD8")
REQUIRED_CHANNEL_ID = os.environ.get("REQUIRED_CHANNEL_ID", "")
REQUIRED_CHANNEL_URL = os.environ.get("REQUIRED_CHANNEL_URL", "https://t.me/telegram")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

if not os.path.exists("downloads"):
    os.makedirs("downloads")

class StudioStates(StatesGroup):
    waiting_for_artist = State()
    waiting_for_title = State()
    waiting_for_album = State()
    waiting_for_cover = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_channel_subscription(user_id: int) -> bool:
    if not REQUIRED_CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception as e:
        logging.error(f"Subscription error: {e}")
        return True

def get_audio_info(file_path: str):
    info = {"title": "Unknown", "artist": "Unknown", "album": "Unknown", "year": "Unknown", "has_art": False, "artwork": None}
    try:
        f = music_tag.load_file(file_path)
        if f['title']: info['title'] = str(f['title'])
        if f['artist']: info['artist'] = str(f['artist'])
        if f['album']: info['album'] = str(f['album'])
        if f['year']: info['year'] = str(f['year'])
        if f['artwork']: 
            info['has_art'] = True
            info['artwork'] = f['artwork'].value
    except Exception as e:
        logging.error(f"Error reading tags: {e}")
    return info

# --- КЛАВИАТУРЫ ---

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
        ],
        [InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="set_lang_kz")]
    ])

def get_sub_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_txt(lang, "sub_subscribe_btn"), url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text=get_txt(lang, "sub_check_btn"), callback_data="check_subscription")]
    ])

def get_main_keyboard(lang: str):
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
            InlineKeyboardButton(text="🎤 Разделить", callback_data="menu_stems"),
            InlineKeyboardButton(text="🎬 Видео", callback_data="menu_video")
        ],
        [
            InlineKeyboardButton(text="🧬 Kenny ID", callback_data="menu_kenny_id"),
            InlineKeyboardButton(text="🧹 Улучшить", callback_data="menu_improve")
        ],
        [
            InlineKeyboardButton(text="📥 Получить файл", callback_data="menu_export"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
        ]
    ])

def get_tags_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_txt(lang, "btn_edit_artist"), callback_data="edit_tag_artist"),
            InlineKeyboardButton(text=get_txt(lang, "btn_edit_title"), callback_data="edit_tag_title")
        ],
        [
            InlineKeyboardButton(text=get_txt(lang, "btn_edit_album"), callback_data="edit_tag_album"),
            InlineKeyboardButton(text=get_txt(lang, "btn_edit_cover"), callback_data="edit_tag_cover")
        ],
        [InlineKeyboardButton(text=get_txt(lang, "btn_main_menu"), callback_data="main_menu")]
    ])

def get_preview_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_txt(lang, "btn_apply"), callback_data="preview_apply"),
            InlineKeyboardButton(text=get_txt(lang, "btn_cancel"), callback_data="preview_cancel")
        ]
    ])

# --- ХЭНДЛЕРЫ КОМАНД И ЯЗЫКА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)
    if not getattr(session, 'lang_selected', False):
        await message.answer(get_txt("ru", "start_welcome"), reply_markup=get_lang_keyboard())
        return

    if not await check_channel_subscription(message.from_user.id):
        await message.answer(get_txt(session.lang, "sub_required"), reply_markup=get_sub_keyboard(session.lang))
        return

    if session.current_file and os.path.exists(session.current_file):
        info = get_audio_info(session.current_file)
        await message.answer(
            get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
            reply_markup=get_main_keyboard(session.lang)
        )
    else:
        await message.answer(get_txt(session.lang, "sub_success"))

@dp.callback_query(F.data.startswith("set_lang_"))
async def process_lang_select(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    session.lang = callback.data.replace("set_lang_", "")
    session.lang_selected = True

    if not await check_channel_subscription(callback.from_user.id):
        await callback.message.edit_text(get_txt(session.lang, "sub_required"), reply_markup=get_sub_keyboard(session.lang))
    else:
        if session.current_file and os.path.exists(session.current_file):
            info = get_audio_info(session.current_file)
            await callback.message.edit_text(
                get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
                reply_markup=get_main_keyboard(session.lang)
            )
        else:
            await callback.message.edit_text(get_txt(session.lang, "sub_success"))

# --- ОБРАБОТКА ФАЙЛОВ И ЭКСПОРТА ---

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)
    if not await check_channel_subscription(message.from_user.id):
        await message.answer(get_txt(session.lang, "sub_required"), reply_markup=get_sub_keyboard(session.lang))
        return

    msg = await message.answer("⏳ *Загрузка файла...*")
    target_obj = message.audio or message.voice or message.document
    user_file_path = f"downloads/{message.from_user.id}_orig.mp3"
    
    await bot.download(target_obj, destination=user_file_path)
    session.set_new_track(user_file_path)
    await msg.delete()
    
    info = get_audio_info(session.current_file)
    await message.answer(
        get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
        reply_markup=get_main_keyboard(session.lang)
    )

@dp.callback_query(F.data == "menu_export")
async def process_export(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    if session.current_file and os.path.exists(session.current_file):
        info = get_audio_info(session.current_file)
        audio_file = FSInputFile(session.current_file, filename=f"{info['artist']} - {info['title']}.mp3")
        await callback.message.answer_audio(
            audio=audio_file,
            title=info['title'],
            performer=info['artist'],
            caption=get_txt(session.lang, "export_ready")
        )
    else:
        await callback.message.answer("❌ Сначала отправьте аудиофайл.")

# --- МЕНЮ ТЕГОВ (EDIT TAGS) ---

@dp.callback_query(F.data == "menu_tags")
async def process_menu_tags(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    info = get_audio_info(session.current_file)
    await callback.message.edit_text(
        get_txt(session.lang, "tags_menu_title", artist=info['artist'], title=info['title'], album=info['album'], year=info['year']),
        reply_markup=get_tags_keyboard(session.lang)
    )

@dp.callback_query(F.data == "edit_tag_artist")
async def ask_artist(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_artist)
    await callback.message.answer(get_txt(session.lang, "ask_artist"))

@dp.message(StudioStates.waiting_for_artist)
async def process_new_artist(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)
    
    # Редактирование в preview
    preview_path = f"downloads/{message.from_user.id}_preview.mp3"
    shutil.copy(session.current_file, preview_path)
    
    f = music_tag.load_file(preview_path)
    f['artist'] = message.text
    f.save()
    
    session.set_preview(preview_path)
    info = get_audio_info(preview_path)
    audio = FSInputFile(preview_path)
    
    await message.answer_audio(
        audio=audio,
        title=info['title'],
        performer=info['artist'],
        caption=get_txt(session.lang, "preview_audio_title"),
        reply_markup=get_preview_keyboard(session.lang)
    )

@dp.callback_query(F.data == "edit_tag_title")
async def ask_title(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_title)
    await callback.message.answer(get_txt(session.lang, "ask_title"))

@dp.message(StudioStates.waiting_for_title)
async def process_new_title(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)
    
    preview_path = f"downloads/{message.from_user.id}_preview.mp3"
    shutil.copy(session.current_file, preview_path)
    
    f = music_tag.load_file(preview_path)
    f['title'] = message.text
    f.save()
    
    session.set_preview(preview_path)
    info = get_audio_info(preview_path)
    audio = FSInputFile(preview_path)
    
    await message.answer_audio(
        audio=audio,
        title=info['title'],
        performer=info['artist'],
        caption=get_txt(session.lang, "preview_audio_title"),
        reply_markup=get_preview_keyboard(session.lang)
    )

@dp.callback_query(F.data == "edit_tag_cover")
async def ask_cover(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_cover)
    await callback.message.answer(get_txt(session.lang, "ask_cover"))

@dp.message(StudioStates.waiting_for_cover, F.photo)
async def process_new_cover(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)
    
    photo_path = f"downloads/{message.from_user.id}_cover.jpg"
    await bot.download(message.photo[-1], destination=photo_path)
    
    preview_path = f"downloads/{message.from_user.id}_preview.mp3"
    shutil.copy(session.current_file, preview_path)
    
    f = music_tag.load_file(preview_path)
    with open(photo_path, 'rb') as img_in:
        f['artwork'] = img_in.read()
    f.save()
    
    session.set_preview(preview_path)
    info = get_audio_info(preview_path)
    audio = FSInputFile(preview_path)
    
    await message.answer_audio(
        audio=audio,
        title=info['title'],
        performer=info['artist'],
        caption=get_txt(session.lang, "preview_audio_title"),
        reply_markup=get_preview_keyboard(session.lang)
    )

# --- PREVIEW ЛОГИКА ---

@dp.callback_query(F.data == "preview_apply")
async def process_preview_apply(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    if session.apply_preview():
        info = get_audio_info(session.current_file)
        await callback.message.answer(
            "✅ " + get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
            reply_markup=get_main_keyboard(session.lang)
        )

@dp.callback_query(F.data == "preview_cancel")
async def process_preview_cancel(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    session.cancel_preview()
    info = get_audio_info(session.current_file)
    await callback.message.answer(
        "❌ " + get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
        reply_markup=get_main_keyboard(session.lang)
    )

@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    info = get_audio_info(session.current_file)
    await callback.message.edit_text(
        get_txt(session.lang, "main_menu_title", title=f"{info['artist']} — {info['title']}"),
        reply_markup=get_main_keyboard(session.lang)
    )

# --- SERVER ---
async def handle_ping(request):
    return web.Response(text="Kenny Studio is online!")

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
import os
import logging
import asyncio
import subprocess
import music_tag
import yt_dlp
import imageio_ffmpeg
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
)

from session_manager import session_mgr
from i18n import get_txt

logging.basicConfig(level=logging.INFO)

# Конфигурация
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8300695982:AAG7t80QBHMZGA041C3IRI2qcuX7CcK4YD8")
# Укажите username вашего канала (начинается с @) или его ID
REQUIRED_CHANNEL_ID = os.environ.get("REQUIRED_CHANNEL_ID", "") 
REQUIRED_CHANNEL_URL = os.environ.get("REQUIRED_CHANNEL_URL", "https://t.me/telegram")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_channel_subscription(user_id: int) -> bool:
    """Проверка подписки пользователя на обязательный канал"""
    if not REQUIRED_CHANNEL_ID:
        return True # Если канал не передан, пропускаем проверку
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return True # Чтобы не блокировать бота при ошибке настройки канала

def get_audio_title(file_path: str) -> str:
    """Извлечение названия трека для меню"""
    try:
        f = music_tag.load_file(file_path)
        title = str(f['title']) if f['title'] else ""
        artist = str(f['artist']) if f['artist'] else ""
        if title and artist:
            return f"{artist} — {title}"
        elif title:
            return title
        elif artist:
            return artist
    except Exception:
        pass
    return os.path.basename(file_path)

# --- КЛАВИАТУРЫ ---

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
        ],
        [
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="set_lang_kz")
        ]
    ])

def get_sub_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_txt(lang, "sub_subscribe_btn"), url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text=get_txt(lang, "sub_check_btn"), callback_data="check_subscription")]
    ])

def get_main_keyboard(lang: str):
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
            InlineKeyboardButton(text="🎤 Разделить", callback_data="menu_stems"),
            InlineKeyboardButton(text="🎬 Видео", callback_data="menu_video")
        ],
        [
            InlineKeyboardButton(text="🧬 Kenny ID", callback_data="menu_kenny_id"),
            InlineKeyboardButton(text="🧹 Улучшить", callback_data="menu_improve")
        ],
        [
            InlineKeyboardButton(text="📥 Получить файл", callback_data="menu_export"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
        ]
    ])

def get_preview_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_txt(lang, "btn_apply"), callback_data="preview_apply"),
            InlineKeyboardButton(text=get_txt(lang, "btn_cancel"), callback_data="preview_cancel")
        ]
    ])

# --- ХЭНДЛЕРЫ КОМАНД И ЯЗЫКА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    session = session_mgr.get_session(message.from_user.id)
    
    # 1. Запрос языка при первом входе
    if not getattr(session, 'lang_selected', False):
        await message.answer(
            get_txt("ru", "start_welcome"),
            reply_markup=get_lang_keyboard()
        )
        return

    # 2. Проверка подписки
    is_subbed = await check_channel_subscription(message.from_user.id)
    if not is_subbed:
        await message.answer(
            get_txt(session.lang, "sub_required"),
            reply_markup=get_sub_keyboard(session.lang)
        )
        return

    # 3. Возврат в меню или приветствие
    if session.current_file and os.path.exists(session.current_file):
        title = get_audio_title(session.current_file)
        await message.answer(
            get_txt(session.lang, "main_menu_title", title=title),
            reply_markup=get_main_keyboard(session.lang)
        )
    else:
        await message.answer(get_txt(session.lang, "sub_success"))

@dp.callback_query(F.data.startswith("set_lang_"))
async def process_lang_select(callback: CallbackQuery):
    await callback.answer()
    lang_code = callback.data.replace("set_lang_", "")
    session = session_mgr.get_session(callback.from_user.id)
    session.lang = lang_code
    session.lang_selected = True

    is_subbed = await check_channel_subscription(callback.from_user.id)
    if not is_subbed:
        await callback.message.edit_text(
            get_txt(session.lang, "sub_required"),
            reply_markup=get_sub_keyboard(session.lang)
        )
    else:
        if session.current_file and os.path.exists(session.current_file):
            title = get_audio_title(session.current_file)
            await callback.message.edit_text(
                get_txt(session.lang, "main_menu_title", title=title),
                reply_markup=get_main_keyboard(session.lang)
            )
        else:
            await callback.message.edit_text(
                get_txt(session.lang, "sub_success") + "\n\n" +
                ("Отправьте аудиозапись или ссылку, чтобы начать." if session.lang == "ru" else
                 "Send an audio file or link to start." if session.lang == "en" else
                 "Бастау үшін аудио файлды немесе сілтемені жіберіңіз.")
            )

@dp.callback_query(F.data == "check_subscription")
async def process_check_sub(callback: CallbackQuery):
    session = session_mgr.get_session(callback.from_user.id)
    is_subbed = await check_channel_subscription(callback.from_user.id)
    
    if is_subbed:
        await callback.answer(get_txt(session.lang, "sub_success"), show_alert=True)
        if session.current_file and os.path.exists(session.current_file):
            title = get_audio_title(session.current_file)
            await callback.message.edit_text(
                get_txt(session.lang, "main_menu_title", title=title),
                reply_markup=get_main_keyboard(session.lang)
            )
        else:
            await callback.message.edit_text(get_txt(session.lang, "sub_success"))
    else:
        await callback.answer(get_txt(session.lang, "sub_fail"), show_alert=True)

# --- ПРИЕМ ФАЙЛОВ ---

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message):
    session = session_mgr.get_session(message.from_user.id)
    
    is_subbed = await check_channel_subscription(message.from_user.id)
    if not is_subbed:
        await message.answer(
            get_txt(session.lang, "sub_required"),
            reply_markup=get_sub_keyboard(session.lang)
        )
        return

    msg = await message.answer("⏳ *Загрузка файла...*")
    target_obj = message.audio or message.voice or message.document
    user_file_path = f"downloads/{message.from_user.id}_orig.mp3"
    
    await bot.download(target_obj, destination=user_file_path)
    session.set_new_track(user_file_path)
    await msg.delete()
    
    title = get_audio_title(session.current_file)
    await message.answer(
        get_txt(session.lang, "main_menu_title", title=title),
        reply_markup=get_main_keyboard(session.lang)
    )

# --- ЛОГИКА PREVIEW (APPLY / CANCEL) ---

@dp.callback_query(F.data == "preview_apply")
async def process_preview_apply(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    if session.apply_preview():
        title = get_audio_title(session.current_file)
        await callback.message.answer(
            "✅ Изменения сохранены!\n\n" + get_txt(session.lang, "main_menu_title", title=title),
            reply_markup=get_main_keyboard(session.lang)
        )
    else:
        await callback.message.answer("❌ Ошибка сохранения изменения.")

@dp.callback_query(F.data == "preview_cancel")
async def process_preview_cancel(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    session.cancel_preview()
    title = get_audio_title(session.current_file)
    await callback.message.answer(
        "❌ Изменение отменено.\n\n" + get_txt(session.lang, "main_menu_title", title=title),
        reply_markup=get_main_keyboard(session.lang)
    )

@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    if session.current_file and os.path.exists(session.current_file):
        title = get_audio_title(session.current_file)
        await callback.message.edit_text(
            get_txt(session.lang, "main_menu_title", title=title),
            reply_markup=get_main_keyboard(session.lang)
        )
    else:
        await callback.message.edit_text("Отправьте аудиозапись для начала работы.")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Kenny Studio is online!")

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



