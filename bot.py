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
logger = logging.getLogger("button_maker")

WAIT_POST, WAIT_BUTTON_TEXT, WAIT_BUTTON_URL, WAIT_STYLE, WAIT_ACTION = range(5)


@dataclass
class Button:
    text: str
    url: str
    custom_emoji_id: str | None = None
    style: str = "primary"


@dataclass
class Session:
    source_chat_id: int | None = None
    source_message_id: int | None = None
    buttons: list[Button] = field(default_factory=list)
    current_text: str | None = None
    current_custom_emoji_id: str | None = None
    current_url: str | None = None
    per_row: int = 1


sessions: dict[int, Session] = {}


def get_session(user_id: int) -> Session:
    return sessions.setdefault(user_id, Session())


def clear_session(user_id: int) -> None:
    sessions.pop(user_id, None)


def valid_url(url: str) -> bool:
    return url.startswith(("https://", "http://", "tg://"))


def extract_custom_emoji_id(message) -> str | None:
    """Return the first custom emoji document id in the user's message."""
    entities = message.entities or []
    for entity in entities:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            return entity.custom_emoji_id
    return None


def style_keyboard() -> InlineKeyboardMarkup:
    # Native Telegram button styles. Colors are controlled by Telegram clients.
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔵 Blue / Primary", callback_data="style:primary"),
                InlineKeyboardButton("🟢 Green / Success", callback_data="style:success"),
            ],
            [
                InlineKeyboardButton("🔴 Red / Danger", callback_data="style:danger"),
            ],
        ]
    )


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
            [
                InlineKeyboardButton("🗑 Cancel", callback_data="action:cancel"),
            ],
        ]
    )


def build_markup(buttons: list[Button], per_row: int) -> InlineKeyboardMarkup:
    rows = []

    for i in range(0, len(buttons), per_row):
        row = []
        for button in buttons[i : i + per_row]:
            row.append(
                InlineKeyboardButton(
                    text=button.text,
                    url=button.url,
                    style=button.style,
                    icon_custom_emoji_id=button.custom_emoji_id,
                )
            )
        rows.append(row)

    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    clear_session(uid)

    await update.message.reply_text(
        "👑 <b>PREMIUM BUTTON MAKER</b>\n\n"
        "Send or forward your post first.\n\n"
        "Then, for each button, you will send the <b>button text "
        "+ your own Telegram custom emoji</b>. I will use that exact "
        "custom emoji as the button icon — I will NOT add my own emoji.\n\n"
        "After that you can choose:\n"
        "🔵 Blue / Primary\n"
        "🟢 Green / Success\n"
        "🔴 Red / Danger\n\n"
        "Telegram renders the native rounded button shape.",
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
    s.current_custom_emoji_id = None
    s.current_url = None
    s.per_row = 1

    await update.message.reply_text(
        "✅ <b>POST RECEIVED</b>\n\n"
        "Now send the <b>button text</b> and put your Telegram "
        "<b>Premium/custom emoji</b> before it.\n\n"
        "For example, send your own custom emoji +:\n"
        "<code>Want 1000$ Giveaway?</code>\n\n"
        "I will use only the custom emoji you send.",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_TEXT


async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = (message.text or "").strip()

    if not text:
        await message.reply_text(
            "Please send text together with your Telegram custom emoji."
        )
        return WAIT_BUTTON_TEXT

    if len(text) > 64:
        await message.reply_text("Keep the button text under 64 characters.")
        return WAIT_BUTTON_TEXT

    custom_emoji_id = extract_custom_emoji_id(message)

    if not custom_emoji_id:
        await message.reply_text(
            "❌ I didn't detect a Telegram custom emoji in that message.\n\n"
            "Please use one of your Telegram custom/Premium emojis in the "
            "button text and send it again."
        )
        return WAIT_BUTTON_TEXT

    s = get_session(update.effective_user.id)
    s.current_text = text
    s.current_custom_emoji_id = custom_emoji_id

    await message.reply_text(
        "✅ <b>Your custom emoji was detected.</b>\n\n"
        "Now send the button URL.\n"
        "Example:\n"
        "<code>https://t.me/yourchannel</code>",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_URL


async def receive_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL.\nUse https://, http:// or tg://"
        )
        return WAIT_BUTTON_URL

    s = get_session(update.effective_user.id)

    if not s.current_text or not s.current_custom_emoji_id:
        await update.message.reply_text("Button data is missing. Send the button text again.")
        return WAIT_BUTTON_TEXT

    s.current_url = url

    await update.message.reply_text(
        "🎨 <b>CHOOSE BUTTON COLOUR</b>\n\n"
        "These are Telegram's native button styles.",
        parse_mode="HTML",
        reply_markup=style_keyboard(),
    )
    return WAIT_STYLE


async def choose_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    s = get_session(uid)

    style = query.data.split(":", 1)[1]
    if style not in {"primary", "success", "danger"}:
        return WAIT_STYLE

    if not s.current_text or not s.current_url or not s.current_custom_emoji_id:
        await query.edit_message_text(
            "❌ Button data expired. Send the post again with /start."
        )
        clear_session(uid)
        return WAIT_POST

    s.buttons.append(
        Button(
            text=s.current_text,
            url=s.current_url,
            custom_emoji_id=s.current_custom_emoji_id,
            style=style,
        )
    )

    s.current_text = None
    s.current_url = None
    s.current_custom_emoji_id = None

    await query.edit_message_text(
        f"✅ <b>Button saved</b>\n\n"
        f"Style: <b>{style.title()}</b>\n"
        f"Total buttons: <b>{len(s.buttons)}</b>\n\n"
        "Add another, preview, change layout, or finish.",
        parse_mode="HTML",
        reply_markup=control_keyboard(),
    )
    return WAIT_ACTION


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    s = get_session(uid)
    name = query.data.split(":", 1)[1]

    if name == "cancel":
        clear_session(uid)
        await query.edit_message_text("🗑 Cancelled. Send /start for a new post.")
        return WAIT_POST

    if name == "add":
        await query.edit_message_text(
            "➕ <b>ADD ANOTHER BUTTON</b>\n\n"
            "Send your own Telegram custom emoji + the button text.\n"
            "I will use only the emoji you send.",
            parse_mode="HTML",
        )
        return WAIT_BUTTON_TEXT

    if name == "two":
        if len(s.buttons) < 2:
            await query.edit_message_text(
                "Add at least 2 buttons first.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        s.per_row = 2
        await query.edit_message_text(
            "🧩 <b>2 BUTTONS PER ROW</b> selected.",
            parse_mode="HTML",
            reply_markup=control_keyboard(),
        )
        return WAIT_ACTION

    if name == "preview":
        if not s.buttons:
            await query.edit_message_text(
                "No buttons yet.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "👁 <b>BUTTON PREVIEW</b>\n"
                "These are Telegram-native styled buttons with the custom "
                "emoji IDs you supplied."
            ),
            parse_mode="HTML",
            reply_markup=build_markup(s.buttons, s.per_row),
        )
        return WAIT_ACTION

    if name == "finish":
        if not s.source_chat_id or not s.source_message_id:
            clear_session(uid)
            await query.edit_message_text("❌ Session expired. Send the post again.")
            return WAIT_POST

        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=s.source_chat_id,
                message_id=s.source_message_id,
                reply_markup=build_markup(s.buttons, s.per_row),
            )

            await query.edit_message_text(
                "✅ <b>POST READY</b>\n\n"
                "The finished post is above.\n"
                "Forward it to your channel/group.",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.exception("Unable to send styled custom-emoji buttons: %s", exc)

            await query.edit_message_text(
                "❌ Telegram rejected the custom emoji button.\n\n"
                "Make sure the bot owner has Telegram Premium, "
                "and use a valid Telegram custom emoji. "
                "Older Telegram clients may also not show the new button styling.",
                parse_mode="HTML",
            )

        clear_session(uid)
        return WAIT_POST

    return WAIT_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_session(update.effective_user.id)
    await update.message.reply_text("🗑 Cancelled. Send /start for a new post.")
    return WAIT_POST


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 <b>HOW IT WORKS</b>\n\n"
        "1. Send/forward your post.\n"
        "2. Send your own Telegram custom emoji + button text.\n"
        "3. Send the URL.\n"
        "4. Choose Blue, Green or Red native Telegram button style.\n"
        "5. Add more buttons or choose 2-per-row.\n"
        "6. Finish.\n"
        "7. Forward the completed post anywhere.\n\n"
        "I do not add my own emoji.",
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

    logger.info("Premium Custom-Emoji Button Maker is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
