"""Thin async wrapper around the Riot Games API.

Uses the "americas" regional routing cluster directly (not a per-platform
routing value like "na1") -- account-v1 and match-v5 are both routed by
region, not platform. See:
https://developer.riotgames.com/apis#account-v1
https://developer.riotgames.com/apis#match-v5
"""

import os
from urllib.parse import quote

import httpx

REGIONAL_ROUTE = "https://americas.api.riotgames.com"


class RiotAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Riot API error {status_code}: {message}")


def _headers() -> dict:
    api_key = os.getenv("RIOT_API_KEY")
    if not api_key:
        raise RuntimeError("RIOT_API_KEY is not set. Check your .env file.")
    return {"X-Riot-Token": api_key}


async def _get(url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=_headers(), params=params)

    if response.status_code == 404:
        raise RiotAPIError(404, "Not found")
    if response.status_code != 200:
        raise RiotAPIError(response.status_code, response.text)

    return response.json()


async def get_account_by_riot_id(game_name: str, tag_line: str) -> dict:
    """Resolve a Riot ID (game name + tag line) to account info, including puuid."""
    url = f"{REGIONAL_ROUTE}/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
    return await _get(url)


async def get_match_ids_by_puuid(puuid: str, count: int = 5) -> list[str]:
    """Return the player's most recent match IDs, newest first."""
    url = f"{REGIONAL_ROUTE}/lol/match/v5/matches/by-puuid/{puuid}/ids"
    return await _get(url, params={"count": count})


async def get_match_details(match_id: str) -> dict:
    url = f"{REGIONAL_ROUTE}/lol/match/v5/matches/{match_id}"
    return await _get(url)


def did_player_lose(match_details: dict, puuid: str) -> bool:
    """Check the given participant's "win" field in a match-v5 response."""
    for participant in match_details["info"]["participants"]:
        if participant["puuid"] == puuid:
            return not participant["win"]
    raise ValueError(f"puuid {puuid} not found among match participants")
