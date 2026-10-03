TEXTS = {
    "ru": {
        "start_welcome": "🎧 **Добро пожаловать в Kenny Studio!**\n\nВыберите язык / Choose language / Тілді таңдаңыз:",
        "lang_set": "✅ Язык установлен: Русский",
        "sub_required": "🔒 **Kenny Studio**\nДля использования Studio подпишитесь на наш канал.\nПосле подписки нажмите «Проверить подписку».",
        "sub_check_btn": "✅ Проверить подписку",
        "sub_subscribe_btn": "📢 Подписаться на канал",
        "sub_success": "✅ Подписка подтверждена!\nДобро пожаловать в Kenny Studio 🎧",
        "sub_fail": "❌ Подписка не найдена. Подпишитесь на канал и попробуйте ещё раз.",
        "main_menu_title": "🎧 **KENNY STUDIO**\n🎵 Сейчас работаем с: *{title}*\n\nЧто хотите сделать?",
        "btn_apply": "✅ Применить",
        "btn_cancel": "❌ Отменить",
        "btn_back": "↩️ Назад",
        "btn_main_menu": "🏠 Главное меню",
        "preview_audio_title": "👁 **Предпросмотр**\nПослушайте результат перед применением."
    },
    "en": {
        "start_welcome": "🎧 **Welcome to Kenny Studio!**\n\nChoose language:",
        "lang_set": "✅ Language set: English",
        "sub_required": "🔒 **Kenny Studio**\nPlease subscribe to our channel to use Studio.\nThen click 'Check subscription'.",
        "sub_check_btn": "✅ Check subscription",
        "sub_subscribe_btn": "📢 Subscribe to channel",
        "sub_success": "✅ Subscription confirmed!\nWelcome to Kenny Studio 🎧",
        "sub_fail": "❌ Subscription not found. Please subscribe and try again.",
        "main_menu_title": "🎧 **KENNY STUDIO**\n🎵 Currently working on: *{title}*\n\nWhat would you like to do?",
        "btn_apply": "✅ Apply",
        "btn_cancel": "❌ Cancel",
        "btn_back": "↩️ Back",
        "btn_main_menu": "🏠 Main Menu",
        "preview_audio_title": "👁 **Preview**\nListen to the result before applying."
    },
    "kz": {
        "start_welcome": "🎧 **Kenny Studio-ға кош келдіңіз!**\n\nТілді таңдаңыз:",
        "lang_set": "✅ Тіл таңдалды: Қазақша",
        "sub_required": "🔒 **Kenny Studio**\nStudio-ны пайдалану үшін арнамызға жазылыңыз.\nЖазылған соң «Жазылымды тексеру» түймесін басыңыз.",
        "sub_check_btn": "✅ Жазылымды тексеру",
        "sub_subscribe_btn": "📢 Арнаға жазылу",
        "sub_success": "✅ Жазылым расталды!\nKenny Studio-ға кош келдіңіз 🎧",
        "sub_fail": "❌ Жазылым табылмады. Арнаға жазылып, қайталап көрiңiз.",
        "main_menu_title": "🎧 **KENNY STUDIO**\n🎵 Қазіргі трек: *{title}*\n\nНе істегіңіз келеді?",
        "btn_apply": "✅ Қолдану",
        "btn_cancel": "❌ Бас тарту",
        "btn_back": "↩️ Артқа",
        "btn_main_menu": "🏠 Басты мәзір",
        "preview_audio_title": "👁 **Алдын ала қарау**\nҚолданбас бұрын нәтижені тыңдаңыз."
    }
}

def get_txt(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"].get(key, key))
    return text.format(**kwargs) if kwargs else text
