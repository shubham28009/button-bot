# Premium Telegram Button Maker — GitHub + Railway

## What this version does

Each Telegram user gets an independent button-building session:

1. User sends or forwards a circle video, video, photo, text post, or other copyable message.
2. Bot asks for button text.
3. Bot asks for the button URL.
4. User chooses a premium emoji style.
5. User can add unlimited buttons.
6. User can choose one button per row or two buttons per row.
7. Bot sends the finished message back to the SAME user.
8. User forwards the result to any channel/group.

The bot does not publish to any channel.

## Telegram styling limitation

Telegram's Bot API does not let a bot set the actual inline keyboard background color, rounded-corner radius, font, gradients, or custom CSS. The bot therefore styles the button labels with premium emoji/symbols and gives a clean 1-row/2-row layout.

## Railway

Deploy these files to GitHub, then deploy the repository on Railway.

Add the environment variable:

`BOT_TOKEN=your_BotFather_token`

Railway can use the included Dockerfile automatically.

The bot uses polling, so no public webhook URL is required.

## Local

```bash
pip install -r requirements.txt
```

Set `BOT_TOKEN`, then:

```bash
python bot.py
```

## Important

Telegram protected-content/restricted messages may not be copyable by bots. If one fails, send the media directly to the bot.
