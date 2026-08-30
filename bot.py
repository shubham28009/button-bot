import os
import logging
from dataclasses import dataclass, field

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

TOKEN = os.environ["BOT_TOKEN"]

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("premium_button_maker")

WAIT_POST, WAIT_BUTTON_TEXT, WAIT_BUTTON_URL, WAIT_STYLE, WAIT_ACTION = range(5)

# Telegram controls the actual inline-keyboard colors, corner radius and font.
# These presets style the visible label using premium emoji/symbols.
STYLES = {
    "luxury": ("💎", "Luxury"),
    "royal": ("👑", "Royal"),
    "fire": ("🔥", "Fire"),
    "energy": ("⚡", "Energy"),
    "money": ("💰", "Money"),
    "rocket": ("🚀", "Rocket"),
    "elite": ("🔱", "Elite"),
    "vip": ("💠", "VIP"),
    "target": ("🎯", "Target"),
    "premium": ("✨", "Premium"),
    "crown": ("♛", "Crown"),
    "diamond": ("❖", "Diamond"),
}

@dataclass
class Session:
    source_chat_id: int | None = None
    source_message_id: int | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    current_text: str | None = None
    current_url: str | None = None
    selected_emoji: str = "✨"
    per_row: int = 1

sessions: dict[int, Session] = {}


def get_session(user_id: int) -> Session:
    return sessions.setdefault(user_id, Session())


def clear_session(user_id: int) -> None:
    sessions.pop(user_id, None)


def valid_url(url: str) -> bool:
    return url.startswith(("https://", "http://", "tg://"))


def control_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Add Button", callback_data="action:add"),
                InlineKeyboardButton("🧩 2 Per Row", callback_data="action:two"),
            ],
            [
                InlineKeyboardButton("👁 Preview", callback_data="action:preview"),
                InlineKeyboardButton("✅ Finish", callback_data="action:finish"),
            ],
            [InlineKeyboardButton("🗑 Cancel", callback_data="action:cancel")],
        ]
    )


def style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💎 Luxury", callback_data="style:luxury"),
                InlineKeyboardButton("👑 Royal", callback_data="style:royal"),
            ],
            [
                InlineKeyboardButton("🔥 Fire", callback_data="style:fire"),
                InlineKeyboardButton("⚡ Energy", callback_data="style:energy"),
            ],
            [
                InlineKeyboardButton("💰 Money", callback_data="style:money"),
                InlineKeyboardButton("🚀 Rocket", callback_data="style:rocket"),
            ],
            [
                InlineKeyboardButton("🔱 Elite", callback_data="style:elite"),
                InlineKeyboardButton("💠 VIP", callback_data="style:vip"),
            ],
            [
                InlineKeyboardButton("🎯 Target", callback_data="style:target"),
                InlineKeyboardButton("✨ Premium", callback_data="style:premium"),
            ],
            [
                InlineKeyboardButton("♛ Crown", callback_data="style:crown"),
                InlineKeyboardButton("❖ Diamond", callback_data="style:diamond"),
            ],
        ]
    )


def result_keyboard(buttons: list[tuple[str, str]], per_row: int) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(buttons), per_row):
        rows.append(
            [
                InlineKeyboardButton(text, url=url)
                for text, url in buttons[i : i + per_row]
            ]
        )
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_session(user_id)

    await update.message.reply_text(
        "👑 <b>PREMIUM BUTTON MAKER</b>\n\n"
        "Send or forward your:\n"
        "🎥 Circle video\n"
        "🎬 Video\n"
        "🖼 Photo\n"
        "📝 Text post\n"
        "📦 Forwarded post\n\n"
        "I'll add stylish clickable buttons and send the finished post back to you.\n\n"
        "⚠️ Telegram itself controls button colors and rounded corners, "
        "so I use premium emoji styling + clean layouts instead.",
        parse_mode="HTML",
    )
    return WAIT_POST


async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return WAIT_POST

    uid = update.effective_user.id
    s = get_session(uid)

    s.source_chat_id = update.message.chat_id
    s.source_message_id = update.message.message_id
    s.buttons.clear()
    s.current_text = None
    s.current_url = None
    s.selected_emoji = "✨"
    s.per_row = 1

    await update.message.reply_text(
        "✅ <b>POST RECEIVED</b>\n\n"
        "Send the text for your first button.\n\n"
        "Example:\n"
        "<code>Join VIP Now</code>",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_TEXT


async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not text:
        await update.message.reply_text("Please send the button text.")
        return WAIT_BUTTON_TEXT

    if len(text) > 64:
        await update.message.reply_text(
            "⚠️ Keep the button text under 64 characters."
        )
        return WAIT_BUTTON_TEXT

    s = get_session(update.effective_user.id)
    s.current_text = text

    await update.message.reply_text(
        "🔗 <b>BUTTON LINK</b>\n\n"
        "Send the URL for this button.\n\n"
        "Example:\n"
        "<code>https://t.me/yourchannel</code>",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_URL


async def receive_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL.\n\n"
            "Use a link beginning with https://, http:// or tg://"
        )
        return WAIT_BUTTON_URL

    s = get_session(update.effective_user.id)

    if not s.current_text:
        await update.message.reply_text("Button text is missing. Please send it again.")
        return WAIT_BUTTON_TEXT

    s.current_url = url

    await update.message.reply_text(
        "🎨 <b>CHOOSE BUTTON STYLE</b>\n\n"
        "Pick a premium emoji style for the clickable button.\n"
        "The selected emoji will appear directly in the button label.",
        parse_mode="HTML",
        reply_markup=style_keyboard(),
    )
    return WAIT_STYLE


async def choose_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("style:"):
        return WAIT_STYLE

    uid = update.effective_user.id
    s = get_session(uid)

    style_key = query.data.split(":", 1)[1]
    emoji, style_name = STYLES.get(style_key, ("✨", "Premium"))

    # Avoid stacking duplicate emojis if the same text is used repeatedly.
    text = s.current_text.strip()
    styled_text = f"{emoji} {text}"

    s.buttons.append((styled_text, s.current_url))
    s.selected_emoji = emoji
    s.current_text = None
    s.current_url = None

    await query.edit_message_text(
        f"✅ <b>{style_name} style applied</b>\n\n"
        f"Button: <b>{styled_text}</b>\n"
        f"Total buttons: <b>{len(s.buttons)}</b>\n\n"
        "Choose your next action:",
        parse_mode="HTML",
        reply_markup=control_keyboard(),
    )
    return WAIT_ACTION


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    s = get_session(uid)
    action_name = query.data.split(":", 1)[1] if ":" in query.data else query.data

    if action_name == "cancel":
        clear_session(uid)
        await query.edit_message_text(
            "🗑 <b>Cancelled.</b>\n\nSend /start when you want to make another post.",
            parse_mode="HTML",
        )
        return WAIT_POST

    if action_name == "add":
        await query.edit_message_text(
            "➕ <b>ADD ANOTHER BUTTON</b>\n\n"
            "Send the next button text.",
            parse_mode="HTML",
        )
        return WAIT_BUTTON_TEXT

    if action_name == "two":
        if len(s.buttons) < 2:
            await query.edit_message_text(
                "🧩 <b>2-per-row needs at least 2 buttons.</b>\n\n"
                "Add another button first.",
                parse_mode="HTML",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        s.per_row = 2
        await query.edit_message_text(
            "🧩 <b>2-PER-ROW ENABLED</b>\n\n"
            "Your finished post will use two buttons per row.",
            parse_mode="HTML",
            reply_markup=control_keyboard(),
        )
        return WAIT_ACTION

    if action_name == "preview":
        if not s.buttons:
            await query.edit_message_text(
                "Nothing to preview yet.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        preview = result_keyboard(s.buttons, s.per_row)
        await context.bot.send_message(
            chat_id=uid,
            text="👁 <b>BUTTON PREVIEW</b>\n"
                 "This is how the clickable button layout will look.",
            parse_mode="HTML",
            reply_markup=preview,
        )
        return WAIT_ACTION

    if action_name == "finish":
        if not s.source_chat_id or not s.source_message_id:
            clear_session(uid)
            await query.edit_message_text("❌ Session expired. Send the post again.")
            return WAIT_POST

        if not s.buttons:
            await query.edit_message_text(
                "Add at least one button first.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        keyboard = result_keyboard(s.buttons, s.per_row)

        try:
            # Copy the original message and attach the inline keyboard.
            # The copied result is sent back to the SAME user, never to a channel.
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=s.source_chat_id,
                message_id=s.source_message_id,
                reply_markup=keyboard,
            )

            await query.edit_message_text(
                "✅ <b>POST READY</b>\n\n"
                "Your finished post is above.\n"
                "You can now forward it to any Telegram channel or group.",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to copy source message")
            await query.edit_message_text(
                "❌ <b>Telegram couldn't copy this post with buttons.</b>\n\n"
                "Protected/restricted posts may prevent copying. "
                "Try sending the media directly to the bot.",
                parse_mode="HTML",
            )

        clear_session(uid)
        return WAIT_POST

    return WAIT_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_session(update.effective_user.id)
    await update.message.reply_text(
        "🗑 Cancelled.\n\nSend /start to make a new post."
    )
    return WAIT_POST


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 <b>PREMIUM BUTTON MAKER</b>\n\n"
        "1. Send/forward your post.\n"
        "2. Enter button text.\n"
        "3. Enter button URL.\n"
        "4. Choose premium emoji style.\n"
        "5. Add more buttons or use 2-per-row.\n"
        "6. Finish.\n"
        "7. Forward the completed message anywhere.\n\n"
        "⚠️ Telegram doesn't expose custom keyboard colors, "
        "corner radius or CSS to bots. Emoji + layout are the styling options used here.",
        parse_mode="HTML",
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
            WAIT_STYLE: [
                CallbackQueryHandler(choose_style, pattern=r"^style:")
            ],
            WAIT_ACTION: [
                CallbackQueryHandler(action, pattern=r"^action:")
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

    logger.info("Premium Button Maker is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
