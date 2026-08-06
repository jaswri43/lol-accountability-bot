# LoL Accountability Bot

Discord bot that tracks League of Legends losses (via the Riot API) and
assigns accountability tasks (job applications, cold emails, small workouts)
after a loss, with a `/done` command to mark tasks complete.

## Status

Phase 2: `/ping`, `/register`, and the SQLite database (users, processed
matches, tasks) are built. `/register` resolves a Riot ID via the Riot API
and links it to your Discord account. Match polling and `/done` come next.

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
   for fast command syncing during dev). Never commit `.env` — it's
   already in `.gitignore`.

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
│   ├── main.py           # entry point, bot setup, command registration
│   ├── db.py              # SQLAlchemy models (users, processed_matches, tasks) + init_db()
│   └── riot_api.py        # thin async Riot API client (americas routing cluster)
├── requirements.txt
├── .env.example           # template - copy to .env, never commit .env
├── .gitignore
├── bot.db                 # SQLite database file, created on first run (gitignored)
└── README.md
```

Still to come:
- `bot/polling.py` - the background loss-detection loop
- `/done` command to mark a task complete
