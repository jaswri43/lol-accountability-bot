# LoL Accountability Bot

Discord bot that tracks League of Legends losses (via the Riot API) and
assigns accountability tasks (job applications, cold emails, small workouts)
after a loss, with a `/done` command to mark tasks complete.

## Status

Phase 3: the full accountability loop is built. `/register` links a Riot ID
to a Discord account; a background loop polls each registered user's recent
**ranked** matches (Solo/Duo + Flex only) every 5 minutes, and on a new loss
posts an accountability task to `ANNOUNCE_CHANNEL_ID`. `/done` marks a task
complete. `processed_matches` makes polling idempotent across restarts.

## Setup (local dev, VS Code)

1. **Clone/open this folder in VS Code.**

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   ```
   In VS Code, once the venv exists, open the Command Palette
   (Cmd/Ctrl+Shift+P) -> "Python: Select Interpreter" -> pick the one
   inside `./venv`. This makes VS Code use the venv for linting/running.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your environment variables:**
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and fill in your real `DISCORD_TOKEN` (and `GUILD_ID`
   for fast command syncing during dev), `RIOT_API_KEY` (from the
   [Riot Developer Portal](https://developer.riotgames.com/) — dev keys
   expire every 24h, just regenerate as needed), and `ANNOUNCE_CHANNEL_ID`
   (the channel loss/task messages get posted to — right-click it in
   Discord with Developer Mode on -> Copy Channel ID). Without
   `ANNOUNCE_CHANNEL_ID` set, the bot still runs but match polling won't
   start. Never commit `.env` — it's already in `.gitignore`.

5. **Run the bot:**
   ```bash
   python bot/main.py
   ```
   You should see a "Logged in as ..." log line. In your Discord server,
   try `/ping` — the bot should reply "Pong! Bot is up and running."

## Project layout

```
lol-accountability-bot/
├── bot/
│   ├── main.py            # entry point, bot setup, command registration (/ping, /register, /done)
│   ├── db.py               # SQLAlchemy models (users, processed_matches, tasks) + init_db()
│   ├── riot_api.py         # thin async Riot API client (americas routing cluster)
│   ├── polling.py          # background loop: polls ranked matches, flags losses, assigns tasks
│   └── accountability.py   # pool of accountability task descriptions
├── requirements.txt
├── .env.example            # template - copy to .env, never commit .env
├── .gitignore
├── bot.db                  # SQLite database file, created on first run (gitignored)
└── README.md
```
