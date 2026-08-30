# Premium Custom-Emoji Telegram Button Maker

This version uses Telegram's current native inline-button features.

## User workflow

1. User sends or forwards a post/video/circle video/photo/text to the bot.
2. User sends the button text together with their own Telegram custom/Premium emoji.
3. Bot detects the exact custom emoji ID.
4. User sends the URL.
5. User chooses a native Telegram button style:
   - Primary (blue)
   - Success (green)
   - Danger (red)
6. User can add more buttons and choose 1 or 2 buttons per row.
7. Bot sends the finished post back to the same user.
8. User forwards it to any channel/group.

The bot does NOT publish to channels.

## Important Telegram limitation / requirement

The Bot API now supports `style` and `icon_custom_emoji_id` on inline keyboard buttons. Custom emoji icons require the bot owner to have Telegram Premium (or the bot to qualify under Telegram's Fragment additional-username condition). Button appearance is ultimately rendered by Telegram clients.

Telegram clients released after February 9, 2026 support the new button styles; older clients may fall back to the normal button appearance.

## Railway

Deploy the files to GitHub and deploy the repository on Railway.

Set:

`BOT_TOKEN=your_BotFather_token`

The included Dockerfile and Procfile are Railway-ready.

## Important

Do not paste the BotFather token into GitHub. Store it only in Railway Variables.

Protected/restricted Telegram content may not be copyable by bots.
