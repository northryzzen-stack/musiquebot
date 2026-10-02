import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
import yt_dlp 
import static_ffmpeg

static_ffmpeg.add_paths()




# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8927203299:AAFedVj-MRXlD7W-v4ti71NUd3uM9dkpnpc"
CHANNEL_ID = "@musique_mp3"
CHANNEL_LINK = "https://t.me/musique_mp3"
MAX_DURATION_SEC = 600
# ===================================================
 
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- Заглушка для бесплатного тарифа Render ---
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Логика проверки подписки ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def get_subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])

def download_audio_sync(url: str, user_id: int) -> dict:
    output_template = f"downloads/{user_id}_%(id)s.%(ext)s"
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        # Заголовок браузера, чтобы TikTok и YouTube не блокировали сервер Render
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        mp3_filename = os.path.splitext(filename)[0] + ".mp3"
        return {
            'filepath': mp3_filename,
            'title': info.get('title', 'Аудиотрек'),
            'performer': info.get('uploader', 'Music Bot')
        }


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Привет! Я бот для скачивания MP3 из TikTok, Reels, Shorts и YouTube.**\n\n"
        "Пришли мне ссылку на видео, и я вырежу из него аудиодорожку!",
        parse_mode="Markdown"
    )

@dp.message(F.text.startswith("http://") | F.text.startswith("https://"))
async def handle_link(message: types.Message):
    user_id = message.from_user.id

    if not await check_subscription(user_id):
        await message.answer(
            "🔒 **Чтобы скачивать аудио, подпишитесь на наш канал!**\n\n"
            "После подписки нажмите кнопку «Я подписался» или отправьте ссылку повторно.",
            reply_markup=get_subscribe_keyboard(),
            parse_mode="Markdown"
        )
        return

    status_msg = await message.answer("⏳ **Загружаю и обрабатываю трек...**", parse_mode="Markdown")
    
    try:
        res = await asyncio.to_thread(download_audio_sync, message.text.strip(), user_id)
        
        if res['status'] == 'error':
            await status_msg.edit_text(f"❌ {res['message']}")
            return
            
        filepath = res['filepath']
        
        if os.path.exists(filepath):
            await status_msg.edit_text("📤 **Отправляю MP3...**", parse_mode="Markdown")
            audio_file = FSInputFile(filepath)
            await message.answer_audio(
                audio=audio_file,
                title=res['title'],
                performer=res['performer'],
                caption="🎵 Скачано через нашего бота!"
            )
            await status_msg.delete()
            os.remove(filepath)
        else:
            await status_msg.edit_text("❌ Не удалось обработать аудио. Попробуйте другую ссылку.")
            
    except Exception as e:
        logging.error(f"Ошибка при обработке ссылки: {e}")
        await status_msg.edit_text("❌ Произошла ошибка. Проверьте правильность ссылки.")

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text(
            "✅ **Подписка подтверждена!**\n\n"
            "Теперь отправьте мне ссылку на видео из TikTok, Shorts, Reels или VK.",
            parse_mode="Markdown"
        )
        await callback.answer()
    else:
        await callback.answer("❌ Вы всё ещё не подписались на канал!", show_alert=True)

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    print("Бот-скачиватель MP3 запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
 
