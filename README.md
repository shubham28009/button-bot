# Telegram Button Maker — Railway Ready

A Telegram bot that lets anyone send/forward a post, add clickable URL buttons, and receive the finished post back in the bot chat. Users can then forward it anywhere.

## Railway deployment

1. Create a GitHub repository.
2. Upload all files from this folder.
3. In Railway, create a new project and deploy the GitHub repository.
4. Add a Railway variable:
   - Name: `BOT_TOKEN`
   - Value: your BotFather token
5. Railway can use the included Dockerfile automatically.
6. Deploy. Logs should show `Bot is running...`.

No channel admin permission is required because the bot does not publish to a channel.

## Local test

Set BOT_TOKEN and run:

```bash
pip install -r requirements.txt
python bot.py
```

## Usage

/start → send/forward post → button text → button URL → add more/finish → forward finished post.

## Notes

- Users have separate in-memory sessions.
- A Railway restart clears unfinished drafts.
- Telegram protected-content messages may not be copyable by bots.
- The bot uses polling, so it does not need a public webhook URL.
