import os
import logging
import asyncio
from pathlib import Path

import music_tag
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from session_manager import session_mgr
from i18n import get_txt


# =========================================================
# CONFIG
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("kenny-studio")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
REQUIRED_CHANNEL_ID = os.environ.get("REQUIRED_CHANNEL_ID", "")
REQUIRED_CHANNEL_URL = os.environ.get(
    "REQUIRED_CHANNEL_URL",
    "https://t.me/telegram"
)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)

dp = Dispatcher(storage=MemoryStorage())


# =========================================================
# STATES
# =========================================================

class StudioStates(StatesGroup):
    waiting_for_artist = State()
    waiting_for_title = State()
    waiting_for_album = State()
    waiting_for_cover = State()


# =========================================================
# HELPERS
# =========================================================

def safe_lang(session) -> str:
    lang = getattr(session, "lang", "ru")

    if lang not in ("ru", "en", "kz"):
        return "ru"

    return lang


def get_audio_info(file_path: str):
    info = {
        "title": "Unknown",
        "artist": "Unknown",
        "album": "Unknown",
        "year": "Unknown",
        "has_art": False,
    }

    if not file_path or not os.path.exists(file_path):
        return info

    try:
        audio = music_tag.load_file(file_path)

        if audio["title"]:
            info["title"] = str(audio["title"])

        if audio["artist"]:
            info["artist"] = str(audio["artist"])

        if audio["album"]:
            info["album"] = str(audio["album"])

        if audio["year"]:
            info["year"] = str(audio["year"])

        if audio["artwork"]:
            info["has_art"] = True

    except Exception:
        logger.exception("Could not read audio metadata: %s", file_path)

    return info


def track_display_name(file_path: str) -> str:
    info = get_audio_info(file_path)

    artist = info["artist"]
    title = info["title"]

    if artist != "Unknown" and title != "Unknown":
        return f"{artist} â {title}"

    if title != "Unknown":
        return title

    if artist != "Unknown":
        return artist

    return os.path.basename(file_path)


async def check_channel_subscription(user_id: int) -> bool:
    if not REQUIRED_CHANNEL_ID:
        logger.warning(
            "REQUIRED_CHANNEL_ID is empty. Subscription check disabled."
        )
        return True

    try:
        member = await bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL_ID,
            user_id=user_id,
        )

        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )

    except Exception:
        logger.exception("Subscription check failed")
        return False


async def require_subscription(user_id: int, message) -> bool:
    session = session_mgr.get_session(user_id)
    lang = safe_lang(session)

    if await check_channel_subscription(user_id):
        return True

    await message.answer(
        get_txt(lang, "sub_required"),
        reply_markup=get_sub_keyboard(lang),
    )

    return False


async def send_main_menu(message, user_id: int):
    session = session_mgr.get_session(user_id)
    lang = safe_lang(session)

    if not session.has_track():
        await message.answer(
            get_no_track_text(lang)
        )
        return

    title = track_display_name(session.current_file)

    await message.answer(
        get_txt(
            lang,
            "main_menu_title",
            title=title,
        ),
        reply_markup=get_main_keyboard(lang),
    )


async def edit_main_menu(message, user_id: int):
    session = session_mgr.get_session(user_id)
    lang = safe_lang(session)

    if not session.has_track():
        await message.edit_text(
            get_no_track_text(lang)
        )
        return

    title = track_display_name(session.current_file)

    await message.edit_text(
        get_txt(
            lang,
            "main_menu_title",
            title=title,
        ),
        reply_markup=get_main_keyboard(lang),
    )


def get_no_track_text(lang: str):
    if lang == "en":
        return (
            "ð§ *KENNY STUDIO*\n\n"
            "Send an MP3/audio file to start working."
        )

    if lang == "kz":
        return (
            "ð§ *KENNY STUDIO*\n\n"
            "ÐÒ±Ð¼ÑÑÑÑ Ð±Ð°ÑÑÐ°Ñ Ò¯ÑÑÐ½ Ð°ÑÐ´Ð¸Ð¾ ÑÐ°Ð¹Ð» Ð¶ÑÐ±ÐµÑÑÒ£ÑÐ·."
        )

    return (
        "ð§ *KENNY STUDIO*\n\n"
        "ÐÐ°ÑÐ½ÑÐ¼ Ñ ÑÑÐµÐºÐ°.\n"
        "ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ MP3 Ð¸Ð»Ð¸ Ð°ÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð»."
    )


def get_saved_text(lang: str):
    if lang == "en":
        return "â Changes applied."

    if lang == "kz":
        return "â Ó¨Ð·Ð³ÐµÑÑÑÑÐµÑ ÒÐ¾Ð»Ð´Ð°Ð½ÑÐ»Ð´Ñ."

    return "â ÐÐ·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ð¿ÑÐ¸Ð¼ÐµÐ½ÐµÐ½Ñ."


def get_cancelled_text(lang: str):
    if lang == "en":
        return "â Changes cancelled."

    if lang == "kz":
        return "â Ó¨Ð·Ð³ÐµÑÑÑÑÐµÑÐ´ÐµÐ½ Ð±Ð°Ñ ÑÐ°ÑÑÑÐ»Ð´Ñ."

    return "â ÐÐ·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ð¾ÑÐ¼ÐµÐ½ÐµÐ½Ñ."


# =========================================================
# KEYBOARDS
# =========================================================

def get_lang_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ð·ðº Ð ÑÑÑÐºÐ¸Ð¹",
                    callback_data="set_lang_ru",
                ),
                InlineKeyboardButton(
                    text="ð¬ð§ English",
                    callback_data="set_lang_en",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ð°ð¿ ÒÐ°Ð·Ð°ÒÑÐ°",
                    callback_data="set_lang_kz",
                )
            ],
        ]
    )


def get_sub_keyboard(lang: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_txt(lang, "sub_subscribe_btn"),
                    url=REQUIRED_CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_txt(lang, "sub_check_btn"),
                    callback_data="check_subscription",
                )
            ],
        ]
    )


def get_main_keyboard(lang: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ð· Ð¢ÐµÐ³Ð¸", callback_data="menu_tags"),
                InlineKeyboardButton(text="ð Ð­ÑÑÐµÐºÑÑ", callback_data="menu_effects"),
            ],
            [
                InlineKeyboardButton(text="âï¸ ÐÐ°ÑÐµÐ·ÐºÐ°", callback_data="menu_trim"),
                InlineKeyboardButton(text="ð Ð¡ÐºÐ¾ÑÐ¾ÑÑÑ / Ð¢Ð¾Ð½", callback_data="menu_speed"),
            ],
            [
                InlineKeyboardButton(text="ð¤ Ð Ð°Ð·Ð´ÐµÐ»Ð¸ÑÑ", callback_data="menu_stems"),
                InlineKeyboardButton(text="ð¬ ÐÐ¸Ð´ÐµÐ¾", callback_data="menu_video"),
            ],
            [
                InlineKeyboardButton(text="ð§¬ Kenny ID", callback_data="menu_kenny_id"),
                InlineKeyboardButton(text="ð§¹ Ð£Ð»ÑÑÑÐ¸ÑÑ", callback_data="menu_improve"),
            ],
            [
                InlineKeyboardButton(text="ð¥ ÐÐ¾Ð»ÑÑÐ¸ÑÑ ÑÐ°Ð¹Ð»", callback_data="menu_export"),
                InlineKeyboardButton(text="âï¸ ÐÐ°ÑÑÑÐ¾Ð¹ÐºÐ¸", callback_data="menu_settings"),
            ],
        ]
    )


def get_tags_keyboard(lang: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_txt(lang, "btn_edit_artist"), callback_data="edit_tag_artist"),
                InlineKeyboardButton(text=get_txt(lang, "btn_edit_title"), callback_data="edit_tag_title"),
            ],
            [
                InlineKeyboardButton(text=get_txt(lang, "btn_edit_album"), callback_data="edit_tag_album"),
                InlineKeyboardButton(text=get_txt(lang, "btn_edit_cover"), callback_data="edit_tag_cover"),
            ],
            [InlineKeyboardButton(text="â©ï¸ Undo", callback_data="undo_edit")],
            [InlineKeyboardButton(text=get_txt(lang, "btn_main_menu"), callback_data="main_menu")],
        ]
    )


def get_preview_keyboard(lang: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=get_txt(lang, "btn_apply"), callback_data="preview_apply"),
            InlineKeyboardButton(text=get_txt(lang, "btn_cancel"), callback_data="preview_cancel"),
        ]]
    )


# =========================================================
# START / LANGUAGE
# =========================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)

    if not session.lang_selected:
        await message.answer(get_txt("ru", "start_welcome"), reply_markup=get_lang_keyboard())
        return

    if not await require_subscription(message.from_user.id, message):
        return

    if session.has_track():
        await send_main_menu(message, message.from_user.id)
    else:
        await message.answer(get_no_track_text(safe_lang(session)))


@dp.callback_query(F.data.startswith("set_lang_"))
async def process_lang_select(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    lang = callback.data.replace("set_lang_", "")
    if lang not in ("ru", "en", "kz"):
        lang = "ru"
    session.lang = lang
    session.lang_selected = True

    if not await check_channel_subscription(callback.from_user.id):
        await callback.message.edit_text(get_txt(lang, "sub_required"), reply_markup=get_sub_keyboard(lang))
        return
    await callback.message.edit_text(get_no_track_text(lang))


@dp.callback_query(F.data == "check_subscription")
async def process_check_subscription(callback: CallbackQuery):
    session = session_mgr.get_session(callback.from_user.id)
    lang = safe_lang(session)
    subscribed = await check_channel_subscription(callback.from_user.id)
    if not subscribed:
        await callback.answer(get_txt(lang, "sub_fail"), show_alert=True)
        return
    await callback.answer(get_txt(lang, "sub_success"), show_alert=True)
    if session.has_track():
        await edit_main_menu(callback.message, callback.from_user.id)
    else:
        await callback.message.edit_text(get_no_track_text(lang))


# =========================================================
# AUDIO UPLOAD
# =========================================================

@dp.message(F.audio | F.voice | F.document)
async def handle_audio_file(message: types.Message, state: FSMContext):
    await state.clear()
    session = session_mgr.get_session(message.from_user.id)

    if not await require_subscription(message.from_user.id, message):
        return

    target = message.audio or message.voice or message.document

    if message.document:
        mime = message.document.mime_type or ""
        filename = (message.document.file_name or "").lower()
        valid_extension = filename.endswith((".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"))
        if not (mime.startswith("audio/") or valid_extension):
            await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð°ÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð».")
            return

    loading = await message.answer("â³ ÐÐ°Ð³ÑÑÐ¶Ð°Ñ Ð°ÑÐ´Ð¸Ð¾...")

    try:
        if message.audio:
            original_name = message.audio.file_name or "track.mp3"
        elif message.document:
            original_name = message.document.file_name or "track.mp3"
        else:
            original_name = "voice.ogg"

        extension = Path(original_name).suffix.lower() or ".mp3"
        file_path = DOWNLOAD_DIR / f"{message.from_user.id}_original{extension}"

        for old_file in DOWNLOAD_DIR.glob(f"{message.from_user.id}_original.*"):
            try:
                old_file.unlink()
            except OSError:
                pass

        await bot.download(target, destination=str(file_path))
        session.set_new_track(str(file_path))

        try:
            await loading.delete()
        except Exception:
            pass

        await send_main_menu(message, message.from_user.id)

    except Exception:
        logger.exception("Audio upload failed for user %s", message.from_user.id)
        try:
            await loading.edit_text("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¾Ð±ÑÐ°Ð±Ð¾ÑÐ°ÑÑ ÑÐ°Ð¹Ð».")
        except Exception:
            await message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¾Ð±ÑÐ°Ð±Ð¾ÑÐ°ÑÑ ÑÐ°Ð¹Ð».")


# =========================================================
# TAG MENU
# =========================================================

@dp.callback_query(F.data == "menu_tags")
async def process_menu_tags(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    lang = safe_lang(session)
    if not session.has_track():
        await callback.message.answer(get_no_track_text(lang))
        return
    info = get_audio_info(session.current_file)
    await callback.message.edit_text(
        get_txt(lang, "tags_menu_title", artist=info["artist"], title=info["title"], album=info["album"], year=info["year"]),
        reply_markup=get_tags_keyboard(lang),
    )


# =========================================================
# ARTIST / TITLE / ALBUM / COVER
# =========================================================

@dp.callback_query(F.data == "edit_tag_artist")
async def ask_artist(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_artist)
    await callback.message.answer(get_txt(safe_lang(session), "ask_artist"))


@dp.message(StudioStates.waiting_for_artist)
async def process_new_artist(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð¸Ð¼Ñ ÑÐµÐºÑÑÐ¾Ð¼.")
        return
    session = session_mgr.get_session(message.from_user.id)
    preview = session.copy_current_to_preview(".mp3")
    if not preview:
        await state.clear()
        await message.answer("â ÐÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð» Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        return
    try:
        audio = music_tag.load_file(preview)
        audio["artist"] = message.text.strip()
        audio.save()
        await state.clear()
        info = get_audio_info(preview)
        await message.answer_audio(
            audio=FSInputFile(preview), title=info["title"], performer=info["artist"],
            caption=get_txt(safe_lang(session), "preview_audio_title"),
            reply_markup=get_preview_keyboard(safe_lang(session)),
        )
    except Exception:
        logger.exception("Artist editing failed")
        session.cancel_preview()
        await state.clear()
        await message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¸Ð·Ð¼ÐµÐ½Ð¸ÑÑ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ.")


@dp.callback_query(F.data == "edit_tag_title")
async def ask_title(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_title)
    await callback.message.answer(get_txt(safe_lang(session), "ask_title"))


@dp.message(StudioStates.waiting_for_title)
async def process_new_title(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ ÑÐµÐºÑÑÐ¾Ð¼.")
        return
    session = session_mgr.get_session(message.from_user.id)
    preview = session.copy_current_to_preview(".mp3")
    if not preview:
        await state.clear()
        await message.answer("â ÐÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð» Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        return
    try:
        audio = music_tag.load_file(preview)
        audio["title"] = message.text.strip()
        audio.save()
        await state.clear()
        info = get_audio_info(preview)
        await message.answer_audio(
            audio=FSInputFile(preview), title=info["title"], performer=info["artist"],
            caption=get_txt(safe_lang(session), "preview_audio_title"),
            reply_markup=get_preview_keyboard(safe_lang(session)),
        )
    except Exception:
        logger.exception("Title editing failed")
        session.cancel_preview()
        await state.clear()
        await message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¸Ð·Ð¼ÐµÐ½Ð¸ÑÑ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ.")


@dp.callback_query(F.data == "edit_tag_album")
async def ask_album(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_album)
    await callback.message.answer(get_txt(safe_lang(session), "ask_album"))


@dp.message(StudioStates.waiting_for_album)
async def process_new_album(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð°Ð»ÑÐ±Ð¾Ð¼Ð° ÑÐµÐºÑÑÐ¾Ð¼.")
        return
    session = session_mgr.get_session(message.from_user.id)
    preview = session.copy_current_to_preview(".mp3")
    if not preview:
        await state.clear()
        await message.answer("â ÐÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð» Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        return
    try:
        audio = music_tag.load_file(preview)
        audio["album"] = message.text.strip()
        audio.save()
        await state.clear()
        info = get_audio_info(preview)
        await message.answer_audio(
            audio=FSInputFile(preview), title=info["title"], performer=info["artist"],
            caption=get_txt(safe_lang(session), "preview_audio_title"),
            reply_markup=get_preview_keyboard(safe_lang(session)),
        )
    except Exception:
        logger.exception("Album editing failed")
        session.cancel_preview()
        await state.clear()
        await message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¸Ð·Ð¼ÐµÐ½Ð¸ÑÑ Ð°Ð»ÑÐ±Ð¾Ð¼.")


@dp.callback_query(F.data == "edit_tag_cover")
async def ask_cover(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    await state.set_state(StudioStates.waiting_for_cover)
    await callback.message.answer(get_txt(safe_lang(session), "ask_cover"))


@dp.message(StudioStates.waiting_for_cover, F.photo)
async def process_new_cover(message: types.Message, state: FSMContext):
    session = session_mgr.get_session(message.from_user.id)
    preview = session.copy_current_to_preview(".mp3")
    if not preview:
        await state.clear()
        await message.answer("â ÐÑÐ´Ð¸Ð¾ÑÐ°Ð¹Ð» Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        return

    cover_path = DOWNLOAD_DIR / f"{message.from_user.id}_cover.jpg"
    try:
        await bot.download(message.photo[-1], destination=str(cover_path))
        audio = music_tag.load_file(preview)
        with open(cover_path, "rb") as image:
            audio["artwork"] = image.read()
        audio.save()
        await state.clear()
        info = get_audio_info(preview)
        await message.answer_audio(
            audio=FSInputFile(preview), title=info["title"], performer=info["artist"],
            caption=get_txt(safe_lang(session), "preview_audio_title"),
            reply_markup=get_preview_keyboard(safe_lang(session)),
        )
    except Exception:
        logger.exception("Cover editing failed")
        session.cancel_preview()
        await state.clear()
        await message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¸Ð·Ð¼ÐµÐ½Ð¸ÑÑ Ð¾Ð±Ð»Ð¾Ð¶ÐºÑ.")
    finally:
        if cover_path.exists():
            try:
                cover_path.unlink()
            except OSError:
                pass


@dp.message(StudioStates.waiting_for_cover)
async def invalid_cover(message: types.Message):
    await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð¸Ð·Ð¾Ð±ÑÐ°Ð¶ÐµÐ½Ð¸Ðµ ÐºÐ°Ðº ÑÐ¾ÑÐ¾.")


# =========================================================
# PREVIEW
# =========================================================

@dp.callback_query(F.data == "preview_apply")
async def process_preview_apply(callback: CallbackQuery):
    session = session_mgr.get_session(callback.from_user.id)
    lang = safe_lang(session)

    if not session.apply_preview():
        await callback.answer("â Preview Ð±Ð¾Ð»ÑÑÐµ Ð½ÐµÐ´Ð¾ÑÑÑÐ¿ÐµÐ½.", show_alert=True)
        return

    await callback.answer()

    # Ð£Ð±Ð¸ÑÐ°ÐµÐ¼ ÐºÐ½Ð¾Ð¿ÐºÐ¸ Ñ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð½Ð¾Ð³Ð¾ Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Could not remove preview keyboard after apply")

    await callback.message.answer(get_saved_text(lang))
    await send_main_menu(callback.message, callback.from_user.id)


@dp.callback_query(F.data == "preview_cancel")
async def process_preview_cancel(callback: CallbackQuery):
    session = session_mgr.get_session(callback.from_user.id)
    lang = safe_lang(session)

    session.cancel_preview()
    await callback.answer()

    # ÐÐ¾ÑÐ»Ðµ Ð¾ÑÐ¼ÐµÐ½Ñ ÐºÐ½Ð¾Ð¿ÐºÐ¸ Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ° ÑÐ¾Ð¶Ðµ Ð±Ð¾Ð»ÑÑÐµ Ð½Ðµ Ð½ÑÐ¶Ð½Ñ.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Could not remove preview keyboard after cancel")

    await callback.message.answer(get_cancelled_text(lang))
    await send_main_menu(callback.message, callback.from_user.id)


# =========================================================
# UNDO
# =========================================================

@dp.callback_query(F.data == "undo_edit")
async def process_undo(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    if session.undo():
        await callback.message.answer("â©ï¸ ÐÐ¾ÑÐ»ÐµÐ´Ð½ÐµÐµ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ðµ Ð¾ÑÐ¼ÐµÐ½ÐµÐ½Ð¾.")
    else:
        await callback.message.answer("â¹ï¸ ÐÐ¾ÐºÐ° Ð½ÐµÑÐµÐ³Ð¾ Ð¾ÑÐ¼ÐµÐ½ÑÑÑ.")
    await send_main_menu(callback.message, callback.from_user.id)


# =========================================================
# EXPORT
# =========================================================

@dp.callback_query(F.data == "menu_export")
async def process_export(callback: CallbackQuery):
    await callback.answer()
    session = session_mgr.get_session(callback.from_user.id)
    lang = safe_lang(session)
    if not session.has_track():
        await callback.message.answer(get_no_track_text(lang))
        return
    info = get_audio_info(session.current_file)
    artist = info["artist"] if info["artist"] != "Unknown" else "Unknown Artist"
    title = info["title"] if info["title"] != "Unknown" else "Track"
    safe_filename = f"{artist} - {title}.mp3".replace("/", "-").replace("\\", "-")
    try:
        await callback.message.answer_audio(
            audio=FSInputFile(session.current_file, filename=safe_filename),
            title=title, performer=artist, caption=get_txt(lang, "export_ready"),
        )
    except Exception:
        logger.exception("Export failed")
        await callback.message.answer("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¾ÑÐ¿ÑÐ°Ð²Ð¸ÑÑ ÑÐ°Ð¹Ð».")


# =========================================================
# MAIN MENU
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery):
    await callback.answer()
    await edit_main_menu(callback.message, callback.from_user.id)


# =========================================================
# TEMPORARY HANDLERS FOR NEXT MODULES
# =========================================================

@dp.callback_query(F.data.in_({
    "menu_effects", "menu_trim", "menu_speed", "menu_stems",
    "menu_video", "menu_kenny_id", "menu_improve", "menu_settings",
}))
async def module_in_development(callback: CallbackQuery):
    await callback.answer("ð  Ð­ÑÐ¾Ñ Ð¼Ð¾Ð´ÑÐ»Ñ Ð¿Ð¾Ð´ÐºÐ»ÑÑÐ¸Ð¼ ÑÐ»ÐµÐ´ÑÑÑÐ¸Ð¼.", show_alert=True)


# =========================================================
# HEALTH SERVER FOR RENDER
# =========================================================

async def handle_ping(request):
    return web.Response(text="Kenny Studio is online!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server started on port %s", port)
    return runner


# =========================================================
# START
# =========================================================

async def main():
    logger.info("Starting Kenny Studio...")
    runner = await start_web_server()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())



