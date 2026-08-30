# FIXED Premium Custom Emoji Button Maker

This version fixes the duplicate/wrong-emoji problem.

When the user sends a Telegram custom/Premium emoji + button text, the bot:
1. Reads the actual `custom_emoji_id` from the Telegram message entity.
2. Removes that custom emoji from the visible button text.
3. Sends the exact ID as `icon_custom_emoji_id`.
4. The result should therefore show the custom emoji as the button icon, not as a normal emoji after the text.

Example input:
[YOUR CUSTOM EMOJI] FREE VIP

Button text:
FREE VIP

Button icon:
YOUR EXACT TELEGRAM CUSTOM EMOJI

It also supports native Telegram button styles (Primary, Success, Danger) and 1/2 buttons per row.

## Railway

Replace the existing `bot.py`, `requirements.txt`, `Dockerfile`, `Procfile`, and README in GitHub with these files.

Keep the Railway variable:

`BOT_TOKEN=your_bot_token`

Do not put the token in GitHub.

After pushing the update, redeploy/restart the Railway service.
