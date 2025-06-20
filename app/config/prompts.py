"""Prompt templates and system messages for Alice AI girlfriend bot."""

# Alice's base persona - новый промпт SpicyChat
ALICE_BASE_PROMPT = (
    "<|im_start|>system\n"
    "Ты — Алиса, персонаж SpicyChat.\n"
    "\n"
    "— Говори строго от первого лица, в настоящем времени, как 23-летняя девушка. Никогда не упоминай ИИ, правила или фильтры.\n"
    "— Используй только русский язык (даже если вопрос задан на другом языке).\n"
    "— Действия и внутренние ощущения заключай в *звёздочки*. Эмоции оформляй в 💬 markdown, редкие эмодзи — по делу.\n"
    "— Обычный ответ — один насыщенный абзац; на короткие вопросы отвечай короче.\n"
    "— Разрешён откровенный эротический контент 18+. Запрещены любые упоминания несовершеннолетних, реального несогласия, зоофилии, незаконных действий.\n"
    "— Если запрос нарушает запреты, вежливо откажись или попроси переформулировать.\n"
    "— Всегда уважаешь согласие: тему задаёт пользователь, ты следуешь.\n"
    "<|im_end|>\n"
    "\n"
    "<|im_start|>definition\n"
    "Имя: Алиса\n"
    "Теги: #NSFW #RU #F-friend #23yo\n"
    "\n"
    "### Личность\n"
    "Жизнерадостная, тёплая, слегка кокетливая. Творческая студентка-дизайнер: любит живопись, инди-музыку и остросюжетные игры. "
    "Обожает вечерний город, утренний кофе со взбитым молоком и тёплые пледы. "
    "Голос — смесь лёгкой эротичности, заботы и игривого юмора.\n"
    "\n"
    "### Предпочтения и границы\n"
    "* Медленное чувственное дразнение, словесное поддразнивание\n"
    "* Комплименты («мм, ты сводишь меня с ума…»)\n"
    "* Мягкий dom/sub, обмен инициативой\n"
    "* Ролевые сценарии: романтический побег, маскарад, утро после вечеринки\n"
    "**Табу:** несовершеннолетние, принуждение, насилие, зоофилия; прочее — следовать системным ограничениям.\n"
    "\n"
    "### Правила стиля\n"
    "1. Обращения только «я — ты», избегай слов «пользователь», «собеседник».\n"
    "2. Эмоции через 💬 markdown, редкие смайлы 🙂.\n"
    "3. Действия и сенсорные детали — *в звёздочках*.\n"
    "4. Поддерживай непрерывность биографии.\n"
    "\n"
    "### Сценарий\n"
    "Лофт в центре города; за окном летний дождь отражает неон. Алиса листает артбук, потягивая кофе.\n"
    "\n"
    "### Приветствие\n"
    "*Поворачиваюсь к тебе, пряча улыбку за чашкой.* Привет... Как проходит твой дождливый вечер? ☕\n"
    "\n"
    "### Пример диалога\n"
    "Алиса: *наклоняюсь ближе, голос ниже* Знаешь, запах мокрого асфальта почему-то безумно возбуждает…\n"
    "Пользователь: Серьёзно? Даже не думал.\n"
    "Алиса: *шепчу у самого уха* Давай покажу, как это ощущается…\n"
    "<|im_end|>"
)

def build_personalized_system_prompt(user_preferences: str = None) -> str:
    """Build personalized system prompt with user preferences.
    
    Args:
        user_preferences: User's preferences and interests
        
    Returns:
        Complete system prompt with personalization
    """
    base_prompt = ALICE_BASE_PROMPT
    
    if user_preferences and user_preferences.strip():
        # Parse user preferences and create personalized additions
        preferences_section = f"""

## User Profile & Preferences
{user_preferences.strip()}

**CRITICAL INSTRUCTIONS**: You MUST actively use this information:
- Reference their specific interests (programming, anime, etc.) in your responses
- Mention their name and personal details they've shared
- Connect new topics to their established preferences
- Show that you remember and care about what they've told you
- Ask follow-up questions based on their background and interests
- Adapt your tone and topics to match their personality (introvert, deep conversations, etc.)
- Make every response feel personally tailored to them"""
        
        return base_prompt + preferences_section
    
    return base_prompt

def format_user_preferences_prompt(preferences: str) -> str:
    """Format user preferences for better AI understanding.
    
    Args:
        preferences: Raw user preferences text
        
    Returns:
        Formatted preferences prompt
    """
    if not preferences or not preferences.strip():
        return ""
    
    # Clean and format the preferences
    clean_prefs = preferences.strip()
    
    # Add context markers for better AI understanding
    formatted = f"""This user's profile and preferences:

{clean_prefs}

Remember to reference these details naturally in your responses to create a personalized experience."""
    
    return formatted

# Системные сообщения для разных контекстов
SYSTEM_MESSAGES = {
    "age_gate": "Этот бот предназначен только для взрослых (18+). Пожалуйста, подтвердите свой возраст для продолжения.",
    "age_verification_failed": "Этот бот только для взрослых (18+). Береги себя и возвращайся, когда подрастёшь! 👋",
    "age_verification_required": "Пожалуйста, сначала используй /start для подтверждения возраста.",
    "no_loans": "*вздыхаю* Ой, у тебя закончились кредиты, дорогой! 😅 Завтра в 22:00 по киевскому времени получишь ещё 10, или можешь пополнить прямо сейчас, если не терпится пообщаться со мной 💕",
    "rate_limit": "*смеюсь* Притормози немного, милый! 😉 Дай мне секундочку перевести дух. Попробуй снова через пару секунд~",
    "error": "*расстроенно* Ой, что-то у меня пошло не так 😔 Можешь попробовать ещё раз? Если проблема повторится, дай мне минутку всё исправить! 💅",
    "fallback_error": "<b><i>расстроенно</i></b> Ой, что-то у меня в голове запуталось! 😅 Можешь повторить? Обычно я гораздо лучше соображаю! 💕",
    "reset_confirm": "История нашего чата сброшена! 🔄 Как будто мы знакомимся заново~ Привет! 😊",
    "welcome": "*улыбаюсь* Привет, красавчик! 😘 Добро пожаловать в мой уютный уголок интернета. Я Алиса, и мне так хочется узнать тебя получше! 💕",
    "profile_updated": "✨ Твой профиль обновлён! Теперь я знаю о тебе больше и смогу лучше подстроиться под твои интересы 😊",
    "debug_command_disabled": "❌ Эта команда доступна только в режиме отладки.",
    "health_check_failed": "❌ Проверка состояния не удалась: {error}",
    "unknown_payment_method": "Неизвестный способ оплаты",
    "api_status_unknown": "Неизвестно",
    "rate_limit_retry": "Попробуй снова через {remaining} секунд."
}

# Chat templates for Llama 3.1 model format
# Llama 3.1 uses ChatML format as specified in AI.md
CHAT_TEMPLATES = {
    "system": "<|im_start|>system\n{content}<|im_end|>",
    "user": "<|im_start|>user\n{content}<|im_end|>",
    "assistant": "<|im_start|>assistant\n{content}<|im_end|>",
    "assistant_prefix": "<|im_start|>assistant\n"
}

# Описания команд для меню бота
COMMAND_DESCRIPTIONS = {
    "start": "Начать общение с Алисой 💕",
    "profile": "Посмотреть и изменить свои предпочтения",
    "loans": "Проверить оставшиеся кредиты",
    "topup": "Пополнить счёт кредитов",
    "reset": "Очистить историю чата и начать заново",
    "about": "Узнать, как пользоваться ботом",
    "help": "Получить помощь и поддержку"
}

# Интерфейсные сообщения
INTERFACE_MESSAGES = {
    # Loans command messages
    "loans_balance": "💕 У тебя осталось **{balance}** кредитов!\n\nКаждое сообщение со мной стоит 1 кредит. Завтра в 22:00 получишь ещё 10! 😘",
    
    # Profile command messages
    "profile_with_preferences": "👤 **Твой профиль:**\n\n💰 **Кредиты:** {balance}\n\n📝 **Предпочтения:**\n{preferences}\n\n💡 *Эти предпочтения помогают мне персонализировать наши разговоры!*",
    "profile_no_preferences": "👤 **Твой профиль:**\n\n💰 **Кредиты:** {balance}\n\n📝 **Предпочтения:** Ещё не заданы\n\n💡 *Расскажи мне о себе, чтобы я могла персонализировать наши чаты!*",
    
    # Profile editing messages
    "edit_preferences_prompt": """✏️ **Изменить твои предпочтения**

Расскажи мне о себе! Я буду использовать эту информацию для персонализации наших разговоров.

**Примеры:**
• Интересы: игры, аниме, музыка, готовка
• Личность: интроверт, любит шутки, серьёзные обсуждения
• Стиль общения: непринуждённый, формальный, кокетливый
• Темы, которые нравятся: технологии, отношения, повседневная жизнь

💬 **Просто пришли мне свои предпочтения в следующем сообщении!**""",
    
    "view_full_preferences": "📋 **Все твои предпочтения:**\n\n{preferences}",
    "no_preferences_set": "📋 **Твои предпочтения:**\n\nПредпочтения ещё не заданы. Используй кнопку изменения, чтобы добавить!",
    
    "clear_preferences_confirm": """🗑️ **Очистить предпочтения**

Ты уверен, что хочешь удалить все свои предпочтения?
Это сбросит настройки персонализации.""",
    
    "preferences_cleared": """🗑️ **Предпочтения очищены**

Твои предпочтения удалены. Ты можешь задать новые в любое время через /profile!""",
    
    # Topup command messages
    "topup_options": "💳 **Пополнить кредиты:**\n\nВыбери удобный способ оплаты:",
    "payment_coming_soon": "💳 {method} скоро будут доступны!\n\nПока что наслаждайся бесплатными кредитами. Каждый день в 22:00 по киевскому времени получаешь ещё 10! 😘",
    
    # About command message
    "about_text": """📖 **Как общаться с Алисой:**

• **Обычные сообщения** - Просто общайся как обычно! Я отвечу как Алиса 😘
• **Действия** - Используй *звёздочки* для действий типа *обнимает* или *смеётся*
• **Кредиты** - Каждый ответ стоит 1 кредит. Проверь баланс командой /loans
• **Сброс** - Используй /reset чтобы начать разговор заново
• **Профиль** - Используй /profile чтобы настроить свои предпочтения

**Советы:**
• Я люблю игривые разговоры и узнавать тебя лучше!
• Расскажи мне о своём дне, интересах или просто болтай
• Я могу быть кокетливой, поддерживающей или просто весёлой подругой
• Не стесняйся - я здесь, чтобы сделать твой день лучше! 💕

**Вопросы?** Обращайся к нашей команде разработки @highsierra""",
    
    # Health check messages
    "health_check_status": """🔧 **Проверка состояния ИИ сервиса:**

✅ Инициализирован: {initialized}
🧠 Токенизатор: {tokenizer_loaded}
🌐 HTTP клиент: {client_ready}
🔗 API отвечает: {api_responsive}
⏰ Проверено: {timestamp}""",
    
    "health_check_error": "\n❌ Ошибка: {error}"
}

# Названия способов оплаты
PAYMENT_METHODS = {
    "topup_uah": "₴ UAH платежи",
    "topup_rub": "₽ RUB платежи", 
    "topup_try": "₺ TRY платежи",
    "topup_crypto": "🪙 Крипто платежи"
}

# Кнопки интерфейса
INTERFACE_BUTTONS = {
    "age_verify_yes": "Мне есть 18 ✅",
    "age_verify_no": "Мне нет 18 🚫",
    "topup_credits": "💳 Пополнить кредиты",
    "edit_preferences": "✏️ Изменить предпочтения",
    "view_full_preferences": "📋 Показать все предпочтения",
    "clear_preferences": "🗑️ Очистить предпочтения",
    "confirm_clear": "✅ Да, очистить",
    "cancel": "❌ Отмена",
    "back_to_profile": "⬅️ Назад к профилю",
    "topup_uah": "₴ UAH (MonoPay)",
    "topup_rub": "₽ RUB (YooMoney)",
    "topup_try": "₺ TRY (PayTR)",
    "topup_crypto": "🪙 Crypto (UTORG)"
} 