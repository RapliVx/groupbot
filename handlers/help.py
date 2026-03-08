from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
from utils.text import bold, code, italic, underline, link, mono

#menu/help
def help_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Features", callback_data="help:features"),
            InlineKeyboardButton("🤐 AI Chat", callback_data="help:ai"),
        ],
        [
            InlineKeyboardButton("🧠 Utilities", callback_data="help:utils"),
            InlineKeyboardButton("🔐 Privacy", callback_data="help:privacy"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="help:settings"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="help:close"),
        ],
    ])

def help_settings_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍜 Asupan", callback_data="help:asupan"),
            InlineKeyboardButton("🗑️ AutoDel", callback_data="help:autodel"),
        ],
        [
            InlineKeyboardButton("⬇️ AutoDL", callback_data="help:autodl"),
            InlineKeyboardButton("😍 Caca", callback_data="help:cacaa"),
        ],
        [
            InlineKeyboardButton("🔞 NSFW", callback_data="help:nsfw"),
            InlineKeyboardButton("🛖 Welcome", callback_data="help:wlc"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="help:menu"),
            InlineKeyboardButton("❌ Close", callback_data="help:close"),
        ],
    ])

def help_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help:menu")],
        [InlineKeyboardButton("❌ Close", callback_data="help:close")],
    ])

def help_settings_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help:settings")],
        [InlineKeyboardButton("❌ Close", callback_data="help:close")],
    ])
    
HELP_TEXT = {
    "help:menu": (
        "📖 <b>Help Menu</b>\n"
        "Select a category to see available commands."
    ),

    "help:features": (
        "✨ <b>Main Features</b>\n\n"
        "• ⬇️ <code>/dl</code> — Download videos from supported platforms\n"
        "• 🍜 <code>/asupan</code> — Random TikTok content\n"
        "• 🌤️ <code>/weather</code> — Get weather information\n"
        "• 🪉 <code>/music</code> — Search music\n"
        "• 🔎 <code>/gsearch</code> — Search on Google\n"
        "• 🌍 <code>/tr</code> — Translate text between languages\n"
        "• 📃 <code>/trlist</code> — List supported languages\n"
        "• 💝 <code>/ship</code> — Choose a couple\n"
        "• 🧭 <code>/reminder</code> — Schedule a reminder\n"
        "• 💝 <code>/waifu</code> — Get a waifu\n"
        "• 💸 <code>/kurs</code> — Currency conversion\n"
        "• 🖼️ <code>/q</code> — Create quote sticker\n"
        "• 🎴 <code>/kang</code> — Add sticker to your pack\n"
    ),

    "help:ai": (
        "🤐 <b>AI Chat</b>\n\n"
        "• 💬 <code>/ai</code> — Chat with Gemini AI\n"
        "• 🧠 <code>/ask</code> — Chat with ChatGPT\n"
        "• ⚡ <code>/groq</code> — Chat with Groq\n"
        "• 😍 <code>/caca</code> — Caca Chat Bot\n"
    ),

    "help:utils": (
        "🛠️ <b>Utilities</b>\n\n"
        "• 🏓 <code>/ping</code> — Check bot response time\n"
        "• 📊 <code>/stats</code> — Bot & system statistics\n"
        "• 🌐 <code>/ip</code> — IP address lookup\n"
        "• 🏷️ <code>/domain</code> — Domain information\n"
        "• 🔍 <code>/whoisdomain</code> — Detailed domain lookup\n"
    ),

    "help:privacy": (
        "🔐 <b>User Privacy</b>\n\n"
        "By using this bot, users understand and agree that:\n\n"
        "• The bot owner may view and store the command history used by users\n"
        "• The recorded data may include:\n"
        "  - Telegram user ID\n"
        "  - Username (if available)\n"
        "  - Commands used\n"
        "  - Usage time (timestamp)\n\n"
        "This data is used only for:\n"
        "• Development\n"
        "• Maintenance\n"
        "• Service improvement\n\n"
        "<b>❗ Do not send passwords, identification numbers, or other sensitive data.</b>\n\n"
        "By continuing to use this bot, users are considered to have agreed to this policy."
    ),
}

HELP_TEXT.update({
    "help:settings": (
        "⚙️ <b>Bot Settings</b>\n\n"
        "Select a menu below to see detailed options for each feature."
    ),

    "help:asupan": (
        "🍜 <b>Asupan Settings</b>\n\n"
        "• <code>/asupann enable</code> — Enable asupan in the group\n"
        "• <code>/asupann disable</code> — Disable asupan in the group\n"
        "• <code>/asupann status</code> — Check asupan status\n\n"
    ),

    "help:autodel": (
        "🗑️ <b>Auto Delete Asupan</b>\n\n"
        "• <code>/autodel enable</code> — Enable auto-delete for asupan\n"
        "• <code>/autodel disable</code> — Disable auto-delete for asupan\n"
        "• <code>/autodel status</code> — Check auto-delete status\n\n"
    ),

    "help:autodl": (
        "⬇️ <b>Auto Download Link</b>\n\n"
        "• <code>/autodl enable</code> — Enable automatic link detection\n"
        "• <code>/autodl disable</code> — Disable automatic link detection\n"
        "• <code>/autodl status</code> — Check auto-detect status\n\n"
    ),

    "help:cacaa": (
        "😍 <b>Caca Settings</b>\n\n"
        "• <code>/mode</code> — Change Caca persona (Premium Only)\n"
        "• <code>/cacaa enable</code> — Enable Caca in the group\n"
        "• <code>/cacaa disable</code> — Disable Caca in the group\n"
        "• <code>/cacaa status</code> — Check Caca status\n\n"
    ),
    
    "help:nsfw": (
        "🔞 <b>NSFW Settings</b>\n\n"
        "• <code>/nsfw enable</code> — Enable NSFW in the group\n"
        "• <code>/nsfw disable</code> — Disable NSFW in the group\n"
        "• <code>/nsfw status</code> — Check NSFW status\n\n"
    ),
    
    "help:wlc": (
        "🛖 <b>Welcome Settings</b>\n\n"
        "• <code>/wlc enable</code> — Enable welcome messages\n"
        "• <code>/wlc disable</code> — Disable welcome messages\n\n"
    ),
})

#cmd
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT["help:menu"],
        reply_markup=help_main_keyboard(),
        parse_mode="HTML"
    )

#helpcallback
async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return

    data = q.data or ""

    #ack
    try:
        await q.answer()
    except Exception:
        pass

    #close
    if data == "help:close":
        try:
            await q.message.delete()
        except Exception:
            pass
        return

    #menu/helpp
    if data == "help:menu":
        await q.edit_message_text(
            HELP_TEXT["help:menu"],
            reply_markup=help_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    if data == "help:settings":
        await q.edit_message_text(
            HELP_TEXT["help:settings"],
            reply_markup=help_settings_keyboard(),
            parse_mode="HTML"
        )
        return
        
    #category  
    text = HELP_TEXT.get(data)
    if text:
        if data.startswith(("help:asupan", "help:autodel", "help:autodl", "help:cacaa", "help:nsfw","help:wlc")):
            kb = help_settings_back_keyboard()
        else:
            kb = help_back_keyboard()
    
        await q.edit_message_text(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

