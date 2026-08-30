# Telegram Button Maker — Multi-User + Own Channels

## What it does

Every Telegram user has a private channel list.

Example:

User A connects:
- @ChannelA
- @ChannelA2

User B connects:
- @ChannelB

User A sees only User A's channels.
User B sees only User B's channels.

After building a post, the user can publish directly to one of their connected channels. The bot copies the source post into that channel and attaches the inline buttons, so the user does not need to manually forward the post.

## Add a channel

1. User runs `/addchannel`.
2. User adds the bot as administrator to their own channel.
3. Bot must have permission to post.
4. User sends `@ChannelUsername`.
5. Bot verifies it is an administrator and stores that channel against the user's Telegram ID.

## Data

Connected channels are stored in SQLite (`bot.db`).

For Railway, attach persistent storage if you want the channel list to survive service/container replacement. Set `DB_PATH` to the mounted volume path, for example `/data/bot.db`.

## Railway

Variables:

`BOT_TOKEN=your_bot_token`

Optional:

`DB_PATH=/data/bot.db`

The included Dockerfile/Procfile are ready for Railway.

## Important

The bot must be added as an administrator to each destination channel. The bot does not use the user's Telegram account to post; it posts using the bot account.

Protected/restricted Telegram source messages may not be copyable.
