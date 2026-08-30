import os
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
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
DB_PATH = os.getenv("DB_PATH", "bot.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("multiuser_button_maker")

WAIT_POST, WAIT_BUTTON_TEXT, WAIT_BUTTON_URL, WAIT_STYLE, WAIT_ACTION = range(5)


@dataclass
class Button:
    text: str
    url: str
    custom_emoji_id: str | None
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


SESSIONS: dict[int, Session] = {}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            username TEXT,
            title TEXT NOT NULL,
            UNIQUE(owner_user_id, chat_id)
        )
    """)
    conn.commit()
    conn.close()


def save_channel(owner_user_id: int, chat_id: int, username: str | None, title: str):
    conn = db()
    conn.execute("""
        INSERT INTO channels(owner_user_id, chat_id, username, title)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(owner_user_id, chat_id) DO UPDATE SET
            username=excluded.username,
            title=excluded.title
    """, (owner_user_id, chat_id, username, title))
    conn.commit()
    conn.close()


def delete_channel(owner_user_id: int, chat_id: int):
    conn = db()
    conn.execute(
        "DELETE FROM channels WHERE owner_user_id=? AND chat_id=?",
        (owner_user_id, chat_id),
    )
    conn.commit()
    conn.close()


def get_user_channels(owner_user_id: int):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM channels WHERE owner_user_id=? ORDER BY title",
        (owner_user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_session(uid: int) -> Session:
    return SESSIONS.setdefault(uid, Session())


def clear_session(uid: int):
    SESSIONS.pop(uid, None)


def valid_url(url: str) -> bool:
    return url.startswith(("https://", "http://", "tg://"))


def remove_custom_emoji_from_text(message):
    """Return (visible_text_without_custom_emoji, exact_custom_emoji_id)."""
    text = message.text or ""
    entities = message.entities or []
    custom_entities = [
        e for e in entities
        if e.type == "custom_emoji" and e.custom_emoji_id
    ]

    if not custom_entities:
        return text.strip(), None

    custom_emoji_id = custom_entities[0].custom_emoji_id

    # Telegram offsets are UTF-16 code units.
    raw = text.encode("utf-16-le")
    for entity in sorted(custom_entities, key=lambda e: e.offset, reverse=True):
        start = entity.offset * 2
        end = (entity.offset + entity.length) * 2
        raw = raw[:start] + raw[end:]

    clean = raw.decode("utf-16-le")
    return " ".join(clean.split()), custom_emoji_id


def style_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔵 Blue", callback_data="style:primary"),
            InlineKeyboardButton("🟢 Green", callback_data="style:success"),
        ],
        [
            InlineKeyboardButton("🔴 Red", callback_data="style:danger"),
        ],
    ])


def control_keyboard():
    return InlineKeyboardMarkup([
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
    ])


def build_markup(buttons: list[Button], per_row: int):
    rows = []
    for i in range(0, len(buttons), per_row):
        rows.append([
            InlineKeyboardButton(
                text=b.text,
                url=b.url,
                style=b.style,
                icon_custom_emoji_id=b.custom_emoji_id,
            )
            for b in buttons[i:i + per_row]
        ])
    return InlineKeyboardMarkup(rows)


def channels_keyboard(owner_user_id: int):
    channels = get_user_channels(owner_user_id)
    rows = []

    for c in channels:
        label = c["title"]
        if c["username"]:
            label += f"  @{c['username'].lstrip('@')}"
        rows.append([
            InlineKeyboardButton(
                f"📤 {label}"[:64],
                callback_data=f"channel:{c['chat_id']}"
            )
        ])

    rows.append([
        InlineKeyboardButton("➕ Add Channel", callback_data="channel:add")
    ])

    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    clear_session(uid)

    await update.message.reply_text(
        "👑 <b>BUTTON MAKER</b>\n\n"
        "Send or forward a post first.\n\n"
        "After you finish it, I'll let you:\n"
        "📤 Post directly to your own channels\n"
        "📋 Keep channels separate for every user\n\n"
        "Your channels are private to your Telegram account.",
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
        "Send your Telegram custom/Premium emoji + button text "
        "in the SAME message.\n\n"
        "I will use the exact emoji you sent as the button icon.",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_TEXT


async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text, emoji_id = remove_custom_emoji_from_text(msg)

    if not emoji_id:
        await msg.reply_text(
            "❌ No Telegram custom emoji detected.\n\n"
            "Send your actual custom/Premium emoji + button text."
        )
        return WAIT_BUTTON_TEXT

    if not text:
        await msg.reply_text("❌ Button text is empty. Send it again.")
        return WAIT_BUTTON_TEXT

    if len(text) > 64:
        await msg.reply_text("Keep button text under 64 characters.")
        return WAIT_BUTTON_TEXT

    s = get_session(update.effective_user.id)
    s.current_text = text
    s.current_custom_emoji_id = emoji_id

    await msg.reply_text(
        "✅ <b>Custom emoji detected</b>\n\n"
        "Now send the button URL.",
        parse_mode="HTML",
    )
    return WAIT_BUTTON_URL


async def receive_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL. Use https://, http:// or tg://"
        )
        return WAIT_BUTTON_URL

    s = get_session(update.effective_user.id)

    if not s.current_text or not s.current_custom_emoji_id:
        await update.message.reply_text("Button data missing. Send it again.")
        return WAIT_BUTTON_TEXT

    s.current_url = url

    await update.message.reply_text(
        "🎨 <b>CHOOSE BUTTON STYLE</b>\n\n"
        "These are Telegram's native button styles.",
        parse_mode="HTML",
        reply_markup=style_keyboard(),
    )
    return WAIT_STYLE


async def choose_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    s = get_session(uid)
    style = q.data.split(":", 1)[1]

    if style not in {"primary", "success", "danger"}:
        return WAIT_STYLE

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

    await q.edit_message_text(
        f"✅ <b>Button saved</b>\n\n"
        f"Total buttons: <b>{len(s.buttons)}</b>\n\n"
        "Add more, preview, choose 2 per row, or finish.",
        parse_mode="HTML",
        reply_markup=control_keyboard(),
    )
    return WAIT_ACTION


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    s = get_session(uid)
    action_name = q.data.split(":", 1)[1]

    if action_name == "cancel":
        clear_session(uid)
        await q.edit_message_text("🗑 Cancelled. Send /start to begin again.")
        return WAIT_POST

    if action_name == "add":
        await q.edit_message_text(
            "➕ <b>ADD ANOTHER BUTTON</b>\n\n"
            "Send your custom/Premium emoji + button text.",
            parse_mode="HTML",
        )
        return WAIT_BUTTON_TEXT

    if action_name == "two":
        if len(s.buttons) < 2:
            await q.edit_message_text(
                "Add at least 2 buttons first.",
                reply_markup=control_keyboard(),
            )
            return WAIT_ACTION

        s.per_row = 2
        await q.edit_message_text(
            "🧩 <b>2 BUTTONS PER ROW</b> selected.",
            parse_mode="HTML",
            reply_markup=control_keyboard(),
        )
        return WAIT_ACTION

    if action_name == "preview":
        if not s.buttons:
            return WAIT_ACTION

        await context.bot.send_message(
            chat_id=uid,
            text="👁 <b>BUTTON PREVIEW</b>",
            parse_mode="HTML",
            reply_markup=build_markup(s.buttons, s.per_row),
        )
        return WAIT_ACTION

    if action_name == "finish":
        if not s.source_chat_id or not s.source_message_id or not s.buttons:
            await q.edit_message_text(
                "❌ Nothing to publish. Start again with /start."
            )
            clear_session(uid)
            return WAIT_POST

        # First return the finished post to the user.
        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=s.source_chat_id,
                message_id=s.source_message_id,
                reply_markup=build_markup(s.buttons, s.per_row),
            )
        except TelegramError:
            logger.exception("Failed to create finished post")
            await q.edit_message_text(
                "❌ Telegram couldn't create the finished post."
            )
            clear_session(uid)
            return WAIT_POST

        # Show ONLY this user's channels.
        channels = get_user_channels(uid)
        clear_session(uid)

        if not channels:
            await q.edit_message_text(
                "✅ <b>POST READY</b>\n\n"
                "The finished post is above.\n\n"
                "You have no channels connected yet. "
                "Use /addchannel to connect one.",
                parse_mode="HTML",
            )
            return WAIT_POST

        # Save a short publishing payload in user_data so the user can
        # choose a channel after the finished post is created.
        context.user_data["publish_buttons"] = [
            {
                "text": b.text,
                "url": b.url,
                "custom_emoji_id": b.custom_emoji_id,
                "style": b.style,
            }
            for b in s.buttons
        ]
        context.user_data["publish_source_chat_id"] = s.source_chat_id
        context.user_data["publish_source_message_id"] = s.source_message_id
        context.user_data["publish_per_row"] = s.per_row

        await q.edit_message_text(
            "✅ <b>POST READY</b>\n\n"
            "Choose where YOU want to publish it:",
            parse_mode="HTML",
            reply_markup=channels_keyboard(uid),
        )
        return WAIT_ACTION

    if action_name == "addchannel":
        pass

    return WAIT_ACTION


async def publish_channel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    data = q.data

    if data == "channel:add":
        await q.edit_message_text(
            "➕ <b>ADD YOUR CHANNEL</b>\n\n"
            "1. Add this bot as an administrator in your channel.\n"
            "2. Give it permission to post messages.\n"
            "3. Send me the channel @username here.\n\n"
            "Example: <code>@MyChannel</code>",
            parse_mode="HTML",
        )
        context.user_data["adding_channel"] = True
        return WAIT_ACTION

    if not data.startswith("channel:"):
        return WAIT_ACTION

    chat_id = int(data.split(":", 1)[1])

    # Verify that the channel belongs to this user via our database.
    channels = get_user_channels(uid)
    channel = next((c for c in channels if int(c["chat_id"]) == chat_id), None)

    if not channel:
        await q.edit_message_text(
            "❌ That channel is not connected to your account."
        )
        return WAIT_POST

    source_chat_id = context.user_data.get("publish_source_chat_id")
    source_message_id = context.user_data.get("publish_source_message_id")
    buttons_raw = context.user_data.get("publish_buttons", [])
    per_row = context.user_data.get("publish_per_row", 1)

    if not source_chat_id or not source_message_id or not buttons_raw:
        await q.edit_message_text(
            "❌ Publish session expired. Create the post again."
        )
        return WAIT_POST

    buttons = [
        Button(
            text=b["text"],
            url=b["url"],
            custom_emoji_id=b["custom_emoji_id"],
            style=b["style"],
        )
        for b in buttons_raw
    ]

    # Publishing is done by copy_message from the user's original source
    # message, with the constructed keyboard attached.
    try:
        await context.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
            reply_markup=build_markup(buttons, per_row),
        )

        title = channel["title"]
        await q.edit_message_text(
            f"🚀 <b>POST PUBLISHED</b>\n\n"
            f"Channel: <b>{title}</b>\n\n"
            "Your clickable buttons were attached to the post.",
            parse_mode="HTML",
        )

    except TelegramError as exc:
        logger.exception("Channel publish failed: %s", exc)
        await q.edit_message_text(
            "❌ <b>Couldn't post to this channel.</b>\n\n"
            "Check that:\n"
            "• The bot is an administrator there\n"
            "• It has permission to post messages\n"
            "• The channel still exists and is accessible",
            parse_mode="HTML",
        )

    for key in (
        "publish_source_chat_id",
        "publish_source_message_id",
        "publish_buttons",
        "publish_per_row",
        "adding_channel",
    ):
        context.user_data.pop(key, None)

    return WAIT_POST


async def receive_channel_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("adding_channel"):
        return WAIT_ACTION

    username = (update.message.text or "").strip()

    if not username.startswith("@"):
        await update.message.reply_text(
            "Please send the channel username like <code>@MyChannel</code>.",
            parse_mode="HTML",
        )
        return WAIT_ACTION

    try:
        chat = await context.bot.get_chat(username)
        member = await context.bot.get_chat_member(chat.id, context.bot.id)

        # Bot must be channel administrator.
        status = getattr(member, "status", "")
        if status not in {"administrator", "creator"}:
            await update.message.reply_text(
                "❌ I am not an administrator of that channel.\n\n"
                "Add me as an admin with permission to post, then send the username again."
            )
            return WAIT_ACTION

        can_post = getattr(member, "can_post_messages", None)
        if can_post is False:
            await update.message.reply_text(
                "❌ I'm an admin but I don't have permission to post messages.\n\n"
                "Enable posting permission for this bot."
            )
            return WAIT_ACTION

        save_channel(
            owner_user_id=update.effective_user.id,
            chat_id=chat.id,
            username=chat.username,
            title=chat.title or username,
        )

        context.user_data.pop("adding_channel", None)

        await update.message.reply_text(
            f"✅ <b>Channel connected</b>\n\n"
            f"{chat.title or username}\n"
            f"@{chat.username if chat.username else username.lstrip('@')}\n\n"
            "Only YOU will see and use this channel in your posting menu.",
            parse_mode="HTML",
            reply_markup=channels_keyboard(update.effective_user.id),
        )

    except TelegramError:
        await update.message.reply_text(
            "❌ I couldn't access that channel.\n\n"
            "Make sure:\n"
            "• The @username is correct\n"
            "• The bot is already an administrator\n"
            "• The channel is accessible by username"
        )

    return WAIT_ACTION


async def addchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["adding_channel"] = True
    await update.message.reply_text(
        "➕ <b>ADD YOUR CHANNEL</b>\n\n"
        "1. Add this bot as administrator in your channel.\n"
        "2. Give it permission to post.\n"
        "3. Send the channel username, e.g. <code>@MyChannel</code>.",
        parse_mode="HTML",
    )
    return WAIT_ACTION


async def mychannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    channels = get_user_channels(uid)

    if not channels:
        await update.message.reply_text(
            "📭 You have no channels connected.\n\n"
            "Use /addchannel to connect one."
        )
        return

    rows = []
    for c in channels:
        label = c["title"]
        if c["username"]:
            label += f"  @{c['username'].lstrip('@')}"
        rows.append([
            InlineKeyboardButton(
                f"❌ Remove {label}"[:64],
                callback_data=f"remove:{c['chat_id']}"
            )
        ])

    await update.message.reply_text(
        "📋 <b>YOUR CONNECTED CHANNELS</b>\n\n"
        "Only channels connected to your Telegram account appear here.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def remove_channel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    if not q.data.startswith("remove:"):
        return WAIT_ACTION

    chat_id = int(q.data.split(":", 1)[1])

    # Ownership check prevents one user deleting another user's channel.
    channels = get_user_channels(uid)
    owned = any(int(c["chat_id"]) == chat_id for c in channels)

    if not owned:
        await q.edit_message_text("❌ That channel is not connected to your account.")
        return WAIT_POST

    delete_channel(uid, chat_id)
    await q.edit_message_text("✅ Channel removed from your account.")
    return WAIT_POST


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 <b>COMMANDS</b>\n\n"
        "/start — create a post\n"
        "/addchannel — connect your own channel\n"
        "/mychannels — manage your channels\n"
        "/cancel — cancel current operation\n\n"
        "Each Telegram user has their own private channel list.",
        parse_mode="HTML",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_session(update.effective_user.id)
    for key in (
        "publish_source_chat_id",
        "publish_source_message_id",
        "publish_buttons",
        "publish_per_row",
        "adding_channel",
    ):
        context.user_data.pop(key, None)

    await update.message.reply_text("🗑 Cancelled. Use /start to begin again.")
    return WAIT_POST


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_POST: [
                CommandHandler("addchannel", addchannel_command),
                CommandHandler("mychannels", mychannels),
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_post),
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
                CallbackQueryHandler(publish_channel_action, pattern=r"^channel:"),
                CallbackQueryHandler(remove_channel_action, pattern=r"^remove:"),
                CallbackQueryHandler(action, pattern=r"^action:"),
                CommandHandler("addchannel", addchannel_command),
                CommandHandler("mychannels", mychannels),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_channel_username,
                ),
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
    app.add_handler(CommandHandler("addchannel", addchannel_command))
    app.add_handler(CommandHandler("mychannels", mychannels))

    logger.info("Multi-user channel Button Maker is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
