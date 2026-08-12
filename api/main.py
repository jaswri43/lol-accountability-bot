"""
LoL Accountability API - entry point.

FastAPI backend that will eventually back a web dashboard. Runs as its own
process alongside bot/main.py (see deploy/lol-accountability-api.service),
sharing the same bot.db SQLite file via api/bot_bridge.py -- no bot logic is
duplicated here, it's all imported from bot/.

Must be run with the project root as the working directory, same as the
bot: db.py's sqlite path ("bot.db") is relative and resolves against the
process's cwd, not the script's location. Run with:
    python api/main.py
from the repo root.
"""

import logging
import logging.handlers
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from bot_bridge import init_db
from routes import router as api_router

API_PORT = int(os.getenv("API_PORT", "8001"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "api.log"), maxBytes=5 * 1024 * 1024, backupCount=3
)
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
log = logging.getLogger("api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("Database initialized")
    yield


app = FastAPI(title="LoL Accountability API", lifespan=lifespan)

# In both dev (Vite's proxy) and prod (nginx), the frontend calls this API
# through a same-origin `/api/*` proxy, so the browser never actually makes
# a cross-origin request during normal use -- this is just a safety net for
# anything that talks to the API directly (e.g. hitting port 8001 without
# going through the proxy). The extra localhost origins only make sense
# when FRONTEND_URL itself is local dev -- leaving them allowed in
# production would let a page running on someone's own local dev server
# make credentialed requests against the live API.
_is_local_dev = "localhost" in FRONTEND_URL or "127.0.0.1" in FRONTEND_URL
_cors_origins = [FRONTEND_URL]
if _is_local_dev:
    _cors_origins += ["http://localhost:5173", "http://localhost:3000"]
_cors_origins = list(dict.fromkeys(_cors_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn

    log.info(f"Starting API on port {API_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


if __name__ == "__main__":
    main()
