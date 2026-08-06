# LoL Accountability Bot

Discord bot that tracks League of Legends losses (via the Riot API) and
assigns accountability tasks (job applications, cold emails, small workouts)
after a loss, with a `/done` command to mark tasks complete.

## Status

Phase 1: bot skeleton + `/ping` only. Riot API polling, `/register`, and
`/done` come next.

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
│   └── main.py          # entry point, bot setup, command registration
├── requirements.txt
├── .env.example          # template - copy to .env, never commit .env
├── .gitignore
└── README.md
```

As we add features, `bot/` will grow into:
- `bot/cogs/` - grouped command modules (registration, tasks, etc.)
- `bot/riot_api.py` - Riot API client wrapper
- `bot/db.py` - database models and session handling
- `bot/polling.py` - the background loss-detection loop
