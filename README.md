# LoL Accountability Bot

Discord bot that tracks League of Legends losses (via the Riot API) and
assigns accountability tasks after a loss, completable via `/done` or the
**Mark Done** button on the task message.

## Status

**Live**, running unattended on an Oracle Cloud VM under systemd (see
Deployment below).

Phase 9: pity-based task severity, always on -- no toggle command. A user
opts in purely by tagging a task Medium or High; until they do, everything
behaves exactly as it did before this feature existed.

- `/addtask description [tier]` tags a task Low/Medium/High, defaulting to
  Low if omitted (`task_templates.tier`; existing untagged rows were
  backfilled to Low too). `severity.has_opted_into_severity()` is the entire
  opt-in mechanism: true iff the user has at least one active Medium/High
  task. No separate flag to flip.
- Not opted in -> a ranked loss picks randomly among the user's active
  templates exactly like pre-severity code did (which, since everything's
  tagged Low by default, just means their Low tasks), pity stays frozen at
  0, and the loss embed keeps its original streak-based tone/color. Opted
  in -> each **counted** loss draws a Low/Medium/High tier and assigns a
  task tagged with it, falling back to any active template -- with a note
  in the task message -- if none are tagged for the drawn tier yet.
- The draw is weighted by a per-user `pity` float (`users.pity`) that rises
  by `LOSS_STEP` (8.0) on a counted loss and falls by `WIN_STEP` (7.2,
  floored at 0) on a counted win. Odds are computed fresh each time by
  linearly interpolating between a DEFAULT distribution (pity 0: Low 60% /
  Medium 30% / High 10%) and a MAX distribution (pity >= `PITY_CAP` of 60:
  Low 20% / Medium 40% / High 40%) -- all named constants in
  `bot/severity.py`. A High draw soft-resets pity to 60% of its post-loss
  value (`RETAIN_FACTOR`) so hitting High doesn't just keep compounding.
  Remakes (`riot_api.is_remake`, Riot's early-surrender flag) are fully
  excluded from pity and the tier draw either way; forfeits/short games that
  actually change LP still count.
- The raw pity number, odds, and tier draw are never shown in the loss/task
  message itself -- only the tone (`bot/tone.py`'s tier-based intro/color
  variants, light for Low up to emphatic for High) hints at severity, and
  only for opted-in users. `/status` shows an opted-in user's current
  approximate odds (e.g. "Low 48% / Medium 34% / High 18%") without
  exposing the raw pity value.

Phase 8: match context, rank tracking, and persistent buttons.

- Each loss embed now shows the champion played, KDA, and queue type
  (Solo/Duo vs Flex), pulled straight from the match-v5 details already
  being fetched -- no extra API calls.
- Ranked stats (`league-v4`, platform-routed via `bot/riot_api.py`'s
  `PLATFORM_ROUTE`, separate from the region-routed match/account APIs) are
  tracked per queue on the `users` table. Each loss shows the LP change
  since the last tracked value; a tier/rank change (promotion or demotion)
  instead posts a separate announcement embed, since a plain LP delta
  doesn't mean much across a tier boundary (`bot/ranked.py`). Unranked/
  not-yet-placed queues are skipped gracefully, no error.
- Reactions are gone. Task completion is now a persistent button
  (`bot/views.py`'s `TaskCompletionView`, registered via `bot.add_view()`
  in `on_ready`) that keeps responding correctly to clicks on messages
  posted before a bot restart -- verified by restarting mid-test and
  clicking a pre-restart message's button. Wrong-user clicks are rejected
  ephemerally without completing the task; on success it calls the same
  `complete_task()` helper `/done` uses, then edits the message in place
  (disabled button, completion note) instead of a separate reply.

Phase 7: production-readiness and deployment. Logging goes to stdout and a
rotating file (`bot/logs/bot.log`, 5MB x 3 backups); both background loops
(`bot/polling.py`) catch and log unexpected exceptions instead of dying
silently, so a bug in one poll cycle doesn't permanently kill the loop.

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

## Deployment (Linux VM, systemd)

For running unattended long-term (e.g. an Oracle Cloud VM). See
`deploy/lol-accountability-bot.service` (systemd unit -- auto-restarts on
failure, starts on boot) and `deploy/backup_db.sh` (daily `bot.db` backup,
keeps the last 7). Logs go to both stdout (captured by `journalctl`) and a
rotating file at `bot/logs/bot.log` (5MB x 3 backups).

**You need**: the VM's SSH private key and public IP, and SSH access
(`ssh -i <key> ubuntu@<vm-ip>`). The repo is cloned on the VM at
`~/lol-accountability-bot`, and GitHub access there is via a read-only
deploy key already registered on the repo -- `git pull` on the VM needs no
credentials.

1. Clone the repo onto the VM and repeat the local-dev setup steps above
   (venv, `pip install -r requirements.txt`, `.env`) inside it.
2. Edit `deploy/lol-accountability-bot.service`: adjust `User=`/`Group=`
   and the two `/home/ubuntu/lol-accountability-bot` paths to match your
   actual username and clone location.
3. Install and start the service:
   ```bash
   sudo cp deploy/lol-accountability-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable lol-accountability-bot
   sudo systemctl start lol-accountability-bot
   ```
4. Check it's running:
   ```bash
   sudo systemctl status lol-accountability-bot
   journalctl -u lol-accountability-bot -f
   ```
5. Schedule daily backups:
   ```bash
   chmod +x deploy/backup_db.sh
   crontab -e
   # add:
   0 3 * * * /home/ubuntu/lol-accountability-bot/deploy/backup_db.sh >> /home/ubuntu/lol-accountability-bot/backups/backup.log 2>&1
   ```

### Deploying an update (after the first-time setup above)

The above is one-time. To ship a code change to the already-running bot:

1. **Get the change onto GitHub first.** If it's a local commit that hasn't
   been pushed (`git status`/`git log` will show it), review it, then
   `git push`. The VM pulls from GitHub -- it never sees your local
   filesystem directly.
2. **Test locally before touching the VM, if practical** -- but stop the
   VM's service first: `ssh ... "sudo systemctl stop lol-accountability-bot"`.
   The bot uses one Discord token; running a local copy *and* the VM's copy
   at the same time means Discord routes interactions and events to
   whichever one happens to catch them, causing confusing intermittent
   failures that look like bugs but aren't. Never run both at once.
3. **Deploy:**
   ```bash
   ssh -i <key> ubuntu@<vm-ip>
   cd lol-accountability-bot
   git pull
   ./venv/bin/pip install -r requirements.txt   # only needed if requirements.txt changed
   sudo systemctl restart lol-accountability-bot   # or `start` if you stopped it in step 2
   ```
4. **Verify it actually came back up**, don't just assume:
   ```bash
   sudo systemctl status lol-accountability-bot   # should say "active (running)"
   journalctl -u lol-accountability-bot -n 20      # should show a fresh login + command sync, no tracebacks
   ```
   If the change added new database columns, `db.py`'s `init_db()` adds
   them automatically via `ALTER TABLE` on startup -- no manual migration
   step, but worth spot-checking with
   `sqlite3 bot.db "PRAGMA table_info(users);"` on the VM if you want to be
   sure.

## Project layout

```
lol-accountability-bot/
├── bot/
│   ├── main.py            # entry point, bot setup, all slash commands, persistent-view registration
│   ├── db.py               # SQLAlchemy models (users incl. pity/severity_mode, processed_matches, tasks, task_templates incl. tier) + init_db(), complete_task()
│   ├── riot_api.py         # thin async Riot API client (americas region + na1 platform routing)
│   ├── polling.py          # background loops: match-polling (losses -> tasks, rank tracking) and task reminders
│   ├── ranked.py            # tier/rank comparison + formatting (LP delta, promotion/demotion detection)
│   ├── views.py             # persistent Mark Done button (TaskCompletionView)
│   ├── accountability.py   # picks a task per-user from task_templates (tier-aware), with a fallback default
│   ├── severity.py          # pity-based severity odds/tier-draw logic for /severity mode
│   ├── tone.py              # picks loss-message wording/embed color from losing-streak length or severity tier
│   └── logs/                # rotating log files, created on first run (gitignored)
├── deploy/
│   ├── lol-accountability-bot.service   # systemd unit for running unattended on a VM
│   └── backup_db.sh                      # daily bot.db backup script (cron this)
├── requirements.txt
├── .env.example            # template - copy to .env, never commit .env
├── .gitignore
├── bot.db                  # SQLite database file, created on first run (gitignored)
├── backups/                 # daily bot.db backups from deploy/backup_db.sh (gitignored)
└── README.md
```
