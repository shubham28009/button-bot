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


def get_session(uid: int) -> Session:
    return sessions.setdefault(uid, Session())


def clear_session(uid: int) -> None:
    sessions.pop(uid, None)


def valid_url(url: str) -> bool:
    return url.startswith(("https://", "http://", "tg://"))


def utf16_slice(text: str, start_units: int, length_units: int) -> str:
    """Telegram entity offsets use UTF-16 code units."""
    raw = text.encode("utf-16-le")
    start = start_units * 2
    end = start + length_units * 2
    return raw[start:end].decode("utf-16-le")


def remove_custom_emoji_from_text(message) -> tuple[str, str | None]:
    """
    Find the exact Telegram custom emoji entity and remove ONLY that emoji
    from the visible button text. Return (clean_text, custom_emoji_id).
    """
    text = message.text or ""
    entities = message.entities or []

    custom_entities = [
        e for e in entities
        if e.type == "custom_emoji" and e.custom_emoji_id
    ]

    if not custom_entities:
        return text.strip(), None

    # Use the first custom emoji as the button icon.
    icon_entity = custom_entities[0]
    custom_emoji_id = icon_entity.custom_emoji_id

    # Remove all custom emoji entities from the visible text.
    # Work backwards so offsets remain valid.
    clean = text
    for entity in sorted(
        custom_entities,
        key=lambda e: e.offset,
        reverse=True,
    ):
        start = entity.offset * 2
        end = (entity.offset + entity.length) * 2
        raw = clean.encode("utf-16-le")
        clean = (raw[:start] + raw[end:]).decode("utf-16-le")

    return " ".join(clean.split()), custom_emoji_id


def style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔵 Blue / Primary", callback_data="style:primary"
                ),
                InlineKeyboardButton(
                    "🟢 Green / Success", callback_data="style:success"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔴 Red / Danger", callback_data="style:danger"
                ),
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
            [InlineKeyboardButton("🗑 Cancel", callback_data="action:cancel")],
        ]
    )


def build_markup(buttons: list[Button], per_row: int) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(buttons), per_row):
        row = []
        for b in buttons[i:i + per_row]:
            # IMPORTANT:
            # b.text contains NO custom emoji.
            # The exact Telegram custom emoji is supplied separately as
            # icon_custom_emoji_id, so Telegram renders it as the button icon.
            row.append(
                InlineKeyboardButton(
                    text=b.text,
                    url=b.url,
                    style=b.style,
                    icon_custom_emoji_id=b.custom_emoji_id,
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    clear_session(uid)

    await update.message.reply_text(
        "👑 <b>PREMIUM BUTTON MAKER</b>\n\n"
        "1️⃣ Send/forward your post.\n"
        "2️⃣ Send your Telegram Premium/custom emoji + button text "
        "in the SAME message.\n"
        "3️⃣ Send the URL.\n"
        "4️⃣ Choose the native Telegram button colour.\n\n"
        "Your custom emoji will be placed as the <b>actual button icon</b> — "
        "it will NOT remain at the end of the button text.",
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
        "Now send your <b>Telegram Premium/custom emoji + button text</b> "
        "in one message.\n\n"
        "Example: [YOUR CUSTOM EMOJI] FREE VIP\n\n"
        "I will remove the emoji from the text and use that exact emoji "
        "as the button icon.",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_TEXT


async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text, custom_emoji_id = remove_custom_emoji_from_text(message)

    if not custom_emoji_id:
        await message.reply_text(
            "❌ I didn't detect a Telegram custom/Premium emoji.\n\n"
            "Send your actual Telegram custom emoji followed by the button text."
        )
        return WAIT_BUTTON_TEXT

    if not text:
        await message.reply_text(
            "❌ Button text is empty. Send your custom emoji + text again."
        )
        return WAIT_BUTTON_TEXT

    if len(text) > 64:
        await message.reply_text("Keep the button text under 64 characters.")
        return WAIT_BUTTON_TEXT

    s = get_session(update.effective_user.id)
    s.current_text = text
    s.current_custom_emoji_id = custom_emoji_id

    await message.reply_text(
        "✅ <b>EXACT CUSTOM EMOJI DETECTED</b>\n\n"
        "The emoji will be used as the button icon.\n"
        "It will NOT be included in the button text.\n\n"
        "Now send the button URL.",
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
        await update.message.reply_text(
            "Button data is missing. Send the custom emoji + button text again."
        )
        return WAIT_BUTTON_TEXT

    s.current_url = url

    await update.message.reply_text(
        "🎨 <b>CHOOSE BUTTON COLOUR</b>\n\n"
        "These are native Telegram button styles.",
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
        clear_session(uid)
        await query.edit_message_text(
            "❌ Button data expired. Send /start and try again."
        )
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
    s.current_custom_emoji_id = None
    s.current_url = None

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
    action_name = query.data.split(":", 1)[1]

    if action_name == "cancel":
        clear_session(uid)
        await query.edit_message_text(
            "🗑 <b>Cancelled.</b>\n\nSend /start for a new post.",
            parse_mode="HTML",
        )
        return WAIT_POST

    if action_name == "add":
        await query.edit_message_text(
            "➕ <b>ADD ANOTHER BUTTON</b>\n\n"
            "Send your own Telegram custom/Premium emoji + button text "
            "in the SAME message.",
            parse_mode="HTML",
        )
        return WAIT_BUTTON_TEXT

    if action_name == "two":
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

    if action_name == "preview":
        if not s.buttons:
            await query.edit_message_text(
                "No buttons yet.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "👁 <b>BUTTON PREVIEW</b>\n\n"
                "The custom emoji is passed as the Telegram button icon."
            ),
            parse_mode="HTML",
            reply_markup=build_markup(s.buttons, s.per_row),
        )
        return WAIT_ACTION

    if action_name == "finish":
        if not s.source_chat_id or not s.source_message_id:
            clear_session(uid)
            await query.edit_message_text(
                "❌ Session expired. Send the post again."
            )
            return WAIT_POST

        if not s.buttons:
            await query.edit_message_text(
                "Add at least one button first.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=s.source_chat_id,
                message_id=s.source_message_id,
                reply_markup=build_markup(s.buttons, s.per_row),
            )

            await query.edit_message_text(
                "✅ <b>POST READY</b>\n\n"
                "Your exact custom emoji is used as the button icon.\n"
                "The emoji is no longer duplicated inside the button text.\n\n"
                "Forward the finished post anywhere.",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to create custom-emoji buttons")
            await query.edit_message_text(
                "❌ Telegram rejected the custom emoji button.\n\n"
                "Make sure the bot is running on the updated code and that "
                "the custom emoji is a valid Telegram custom emoji.",
                parse_mode="HTML",
            )

        clear_session(uid)
        return WAIT_POST

    return WAIT_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_session(update.effective_user.id)
    await update.message.reply_text(
        "🗑 Cancelled. Send /start for a new post."
    )
    return WAIT_POST


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 <b>HOW TO USE</b>\n\n"
        "1. Send/forward the post.\n"
        "2. Send YOUR Telegram custom emoji + button text together.\n"
        "3. Send URL.\n"
        "4. Choose button colour.\n"
        "5. Add more buttons if needed.\n"
        "6. Finish.\n\n"
        "The custom emoji is extracted from the Telegram entity and used "
        "as the actual button icon. It is removed from the visible text.",
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

    logger.info("Custom Premium Emoji Button Maker is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
