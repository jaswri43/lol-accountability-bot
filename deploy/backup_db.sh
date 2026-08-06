#!/usr/bin/env bash
# Backs up bot.db to backups/bot_<timestamp>.db, keeping only the newest
# $KEEP copies. Run manually or via cron (see deploy/README for the line).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="$PROJECT_DIR/bot.db"
BACKUP_DIR="$PROJECT_DIR/backups"
KEEP=7

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "No bot.db found at $DB_FILE, nothing to back up." >&2
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/bot_${TIMESTAMP}.db"

# SQLite's own backup API rather than a plain file copy, so a backup taken
# while the bot is mid-write still comes out consistent.
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Keep only the newest $KEEP backups.
ls -1t "$BACKUP_DIR"/bot_*.db | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "Backed up to $BACKUP_FILE"
