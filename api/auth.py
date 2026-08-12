"""Discord OAuth2 login and our own JWT session tokens.

Setup on Discord's side: https://discord.com/developers/applications -> the
bot's application (OAuth2 client id/secret are separate from the bot token,
same application is fine to reuse) -> OAuth2 tab:
  - Copy "Client ID" and generate/copy "Client Secret".
  - Under Redirects, add a URL that exactly matches DISCORD_REDIRECT_URI
    (e.g. http://localhost:8001/auth/callback for local dev; add the
    production URL too once the API is deployed).
Scope requested here is just "identify" (Discord user id + username) --
enough for a JWT keyed on discord_id, no email or guild access needed.
"""

import os
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer()


def _httpx_verify() -> ssl.SSLContext | bool:
    """Some Windows dev machines (Norton Antivirus) intercept outbound HTTPS
    and re-sign it with a local root cert (SSL_CERT_FILE in .env). httpx can
    pick that up automatically via trust_env, but only if the env var is
    already set in-process at the moment the client is constructed -- build
    the SSL context explicitly instead so it doesn't depend on that timing.
    """
    cert_file = os.environ.get("SSL_CERT_FILE")
    if cert_file:
        return ssl.create_default_context(cafile=cert_file)
    return True


@dataclass
class CurrentUser:
    discord_id: int
    username: str


def _create_session_jwt(discord_id: int, username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(discord_id),
        "username": username,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
    """Dependency for protected routes: validates the bearer JWT and returns
    the caller's Discord identity. Raises 401 if missing/invalid/expired."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session token")
    return CurrentUser(discord_id=int(payload["sub"]), username=payload["username"])


@router.get("/login")
async def login():
    """Redirects to Discord's OAuth consent screen."""
    if not (DISCORD_CLIENT_ID and DISCORD_REDIRECT_URI):
        raise HTTPException(500, "Discord OAuth is not configured on the server")
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    return RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str):
    """Discord redirects here with ?code=... after the user approves.
    Exchanges it for a Discord access token, fetches their identity, and
    issues our own session JWT.

    No frontend exists yet, so this returns the JWT directly as JSON for
    testing. Once there's a frontend, swap this for a redirect to it with
    the token attached (query param or fragment) instead of returning raw
    JSON from what the browser sees as the OAuth redirect target.
    """
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and DISCORD_REDIRECT_URI):
        raise HTTPException(500, "Discord OAuth is not configured on the server")

    async with httpx.AsyncClient(verify=_httpx_verify()) as client:
        token_resp = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, f"Discord token exchange failed: {token_resp.text}")
        access_token = token_resp.json()["access_token"]

        user_resp = await client.get(
            DISCORD_USER_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(400, f"Failed to fetch Discord identity: {user_resp.text}")
        discord_user = user_resp.json()

    session_token = _create_session_jwt(int(discord_user["id"]), discord_user["username"])
    return {"access_token": session_token, "token_type": "bearer"}
