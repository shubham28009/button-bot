import os
import logging
from dataclasses import dataclass, field
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.environ["BOT_TOKEN"]

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WAIT_POST, WAIT_BUTTON_TEXT, WAIT_BUTTON_URL, WAIT_NEXT = range(4)

@dataclass
class Session:
    source_chat_id: int | None = None
    source_message_id: int | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    current_text: str | None = None

sessions: dict[int, Session] = {}

def session_for(user_id: int) -> Session:
    return sessions.setdefault(user_id, Session())

def reset(user_id: int):
    sessions.pop(user_id, None)

def is_url(value: str) -> bool:
    return value.startswith(("https://", "http://", "tg://"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset(update.effective_user.id)
    await update.message.reply_text(
        "👋 <b>Button Maker</b>\n\n"
        "Send or forward me your post, video, circle video, photo or text.\n\n"
        "I'll ask you for clickable buttons and then send the finished post back here.\n"
        "You can forward the finished message to any channel/group.",
        parse_mode="HTML",
    )
    return WAIT_POST

async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return WAIT_POST

    uid = update.effective_user.id
    s = session_for(uid)
    s.source_chat_id = update.message.chat_id
    s.source_message_id = update.message.message_id
    s.buttons.clear()
    s.current_text = None

    await update.message.reply_text(
        "✅ Post received!\n\n"
        "Send the <b>button text</b>.\n"
        "Example: <code>🔥 Join VIP</code>",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_TEXT

async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not text:
        await update.message.reply_text("Please send the button text.")
        return WAIT_BUTTON_TEXT

    if len(text) > 64:
        await update.message.reply_text("Keep button text under 64 characters.")
        return WAIT_BUTTON_TEXT

    session_for(update.effective_user.id).current_text = text
    await update.message.reply_text(
        "🔗 Now send the button URL.\n"
        "Example: <code>https://t.me/yourchannel</code>",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_URL

async def receive_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not is_url(url):
        await update.message.reply_text(
            "❌ Invalid URL.\nUse https://, http:// or tg://"
        )
        return WAIT_BUTTON_URL

    uid = update.effective_user.id
    s = session_for(uid)

    if not s.current_text:
        await update.message.reply_text("Button text is missing. Send it again.")
        return WAIT_BUTTON_TEXT

    s.buttons.append((s.current_text, url))
    s.current_text = None

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add another", callback_data="add"),
            InlineKeyboardButton("✅ Finish", callback_data="finish"),
        ],
        [InlineKeyboardButton("🗑 Cancel", callback_data="cancel")],
    ])

    await update.message.reply_text(
        f"✅ Added: <b>{s.buttons[-1][0]}</b>\n"
        f"Buttons: {len(s.buttons)}\n\n"
        "Add another button or finish.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return WAIT_NEXT

async def button_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    s = session_for(uid)

    if query.data == "cancel":
        reset(uid)
        await query.edit_message_text("🗑 Cancelled. Send a new post anytime.")
        return WAIT_POST

    if query.data == "add":
        await query.edit_message_text(
            "Send the <b>next button text</b>.\n"
            "Example: <code>👉 Click Here</code>",
            parse_mode="HTML",
        )
        return WAIT_BUTTON_TEXT

    if query.data == "finish":
        if not s.source_chat_id or not s.source_message_id:
            reset(uid)
            await query.edit_message_text("❌ Session expired. Send the post again.")
            return WAIT_POST

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text, url=url)]
            for text, url in s.buttons
        ])

        try:
            # Copies the user's original Telegram message and attaches
            # the inline keyboard. The result is sent back to the user.
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=s.source_chat_id,
                message_id=s.source_message_id,
                reply_markup=keyboard,
            )
            await query.edit_message_text(
                "✅ <b>Done!</b>\n\n"
                "Forward the finished message above to any channel or group.",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to copy message")
            await query.edit_message_text(
                "❌ Telegram couldn't recreate this post with buttons.\n\n"
                "If it was a protected/restricted post, send the media directly "
                "to the bot instead."
            )

        reset(uid)
        return WAIT_POST

    return WAIT_NEXT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset(update.effective_user.id)
    await update.message.reply_text("🗑 Cancelled. Send a new post anytime.")
    return WAIT_POST

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "1️⃣ Send/forward a post.\n"
        "2️⃣ Enter button text.\n"
        "3️⃣ Enter button URL.\n"
        "4️⃣ Add more or Finish.\n"
        "5️⃣ Forward the finished post anywhere.\n\n"
        "/start — new post\n"
        "/cancel — cancel"
    )

def main():
    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_POST: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_post)
            ],
            WAIT_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_text)
            ],
            WAIT_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_url)
            ],
            WAIT_NEXT: [
                CallbackQueryHandler(button_action)
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )

    app.add_handler(conversation)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
