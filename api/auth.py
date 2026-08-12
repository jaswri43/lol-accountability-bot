"""Discord OAuth2 login and our own JWT session tokens.

Setup on Discord's side: https://discord.com/developers/applications -> the
bot's application (OAuth2 client id/secret are separate from the bot token,
same application is fine to reuse) -> OAuth2 tab:
  - Copy "Client ID" and generate/copy "Client Secret".
  - Under Redirects, add a URL that exactly matches DISCORD_REDIRECT_URI.
    This must be the URL as the *browser* sees it, which goes through the
    frontend's dev-server/nginx proxy (see web/vite.config.ts and
    deploy/nginx.conf) rather than hitting this API's own port directly --
    e.g. http://localhost:5173/api/auth/callback for local dev, or
    http://<host>/api/auth/callback in production. That's also what makes
    the session cookie set below land on the frontend's own origin instead
    of a different one the browser would refuse to send it back to.
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
from fastapi import APIRouter, Cookie, Header, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Where to send the browser once login succeeds. Configurable because this
# differs between local dev (the Vite dev server) and production (wherever
# nginx serves the built frontend from).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
# The frontend and API are same-origin behind a proxy in both dev and prod
# (see the module docstring), so SameSite=Lax is enough -- no cross-site
# cookie needed. `Secure` requires HTTPS though, so it's off by default for
# plain-HTTP local dev / a VM without a TLS cert yet; flip it on once the
# site is served over https.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = "lol_bot_session"

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"

router = APIRouter(prefix="/auth", tags=["auth"])


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


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=JWT_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def get_current_user(
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """Dependency for protected routes: validates the session and returns
    the caller's Discord identity. Prefers the httpOnly cookie the frontend
    relies on; falls back to a Bearer token for curl/script testing. Always
    raises 401 (not FastAPI's HTTPBearer-default 403) so the frontend's
    "401 means log in again" handling works uniformly.
    """
    token = session_cookie
    if token is None and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")

    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
    Exchanges it for a Discord access token, fetches their identity, sets
    our own session JWT as an httpOnly cookie, and sends the browser back
    to the frontend -- there's no frontend page at this URL to show a JSON
    response to.
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
    response = RedirectResponse(url=FRONTEND_URL)
    _set_session_cookie(response, session_token)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse({"ok": True})
    # Attributes should match _set_session_cookie's -- deletion works
    # regardless in practice, but mismatched Secure/SameSite on the
    # clearing cookie is the kind of thing that's only inconsistent
    # cross-browser, not obviously broken, so just match them.
    response.delete_cookie(COOKIE_NAME, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    return response
