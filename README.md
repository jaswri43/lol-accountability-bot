# LoL Accountability Bot

Discord bot that tracks League of Legends losses (via the Riot API) and
assigns accountability tasks after a loss, completable via `/done` or by
reacting with ✅ on the task message.

## Status

Phase 6: loss/reminder messages are Discord embeds, and loss announcements
have a tone that escalates with the user's current losing streak.

- `/register` links a Riot ID to a Discord account. A background loop polls
  each registered user's recent **ranked** matches (Solo/Duo + Flex only)
  every 5 minutes; `processed_matches` makes this idempotent across
  restarts, and newly-registered users have their existing match history
  seeded (not retroactively flagged) so only losses from registration
  onward get a task.
- `/addtask <description>`, `/mytasks`, `/removetask <task_id>` manage a
  per-user rotation of custom task descriptions (`task_templates`). On a
  loss, one active template is picked at random; if a user hasn't added
  any, it falls back to a generic default and says so.
- Each task message gets a ✅ reaction from the bot. Reacting with ✅
  completes the task (only for the user it belongs to) via the same
  completion path as `/done`.
- `/status` shows a user's pending tasks; `/stats` shows total/completed/
  pending counts. Both, plus the loss and reminder announcements, are
  Discord embeds now instead of plain text.
- A second background loop (`REMINDER_INTERVAL_HOURS` in `bot/polling.py`,
  currently 3h) reminds users about accountability tasks that have been
  pending for a while (`MIN_TASK_AGE_HOURS`, currently 2h) and haven't been
  reminded about recently, bundling multiple pending tasks for the same
  user into one message.
- `/mute` / `/unmute` pause or resume loss detection, task creation, and
  reminders for the caller only -- the other person is unaffected.
- Loss announcements read the user's current consecutive-loss streak
  (`bot/tone.py`, based on `processed_matches`) and pick wording/embed
  color that escalates at 1, 2-3, and 4+ in a row -- tone only, never
  affects which task gets assigned or how hard it is.

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
│   ├── main.py            # entry point, bot setup, all slash commands, reaction listener
│   ├── db.py               # SQLAlchemy models (users, processed_matches, tasks, task_templates) + init_db()
│   ├── riot_api.py         # thin async Riot API client (americas routing cluster)
│   ├── polling.py          # background loops: match-polling (losses -> tasks) and task reminders
│   ├── accountability.py   # picks a task per-user from task_templates, with a fallback default
│   └── tone.py              # picks loss-message wording/embed color based on losing-streak length
├── requirements.txt
├── .env.example            # template - copy to .env, never commit .env
├── .gitignore
├── bot.db                  # SQLite database file, created on first run (gitignored)
└── README.md
```
