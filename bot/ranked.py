"""Pure logic for comparing two ranked-stats snapshots (from
riot_api.get_ranked_stats) and formatting them for display. No DB or
Discord API calls here -- that orchestration lives in polling.py.
"""

TIER_ORDER = [
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD",
    "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER",
]
RANK_ORDER = {"IV": 0, "III": 1, "II": 2, "I": 3}
APEX_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}


def _tier_rank_value(tier: str, rank: str) -> tuple[int, int]:
    """Sortable (tier_index, rank_index) pair for comparing two ranks."""
    tier_index = TIER_ORDER.index(tier)
    rank_index = 0 if tier in APEX_TIERS else RANK_ORDER.get(rank, 0)
    return tier_index, rank_index


def format_tier_rank(entry: dict) -> str:
    """e.g. 'Gold IV' or 'Master' (apex tiers have no sub-ranks)."""
    tier = entry["tier"].title()
    if entry["tier"] in APEX_TIERS:
        return tier
    return f"{tier} {entry['rank']}"


def format_rank(entry: dict) -> str:
    """e.g. 'Gold IV (37 LP)'."""
    return f"{format_tier_rank(entry)} ({entry['leaguePoints']} LP)"


def describe_change(old_entry: dict | None, new_entry: dict) -> tuple[int | None, bool, str | None]:
    """Compare an old and new ranked-stats entry for the same queue.

    Returns (lp_change, tier_or_rank_changed, direction):
    - lp_change is a plain LP delta, only meaningful (non-None) when the
      tier and rank are unchanged between snapshots -- it doesn't mean much
      across a tier boundary.
    - tier_or_rank_changed + direction ("up"/"down") flag a promotion or
      demotion instead.

    old_entry=None (no prior snapshot -- first time tracking this queue)
    always returns (None, False, None).
    """
    if old_entry is None:
        return None, False, None

    old_value = _tier_rank_value(old_entry["tier"], old_entry["rank"])
    new_value = _tier_rank_value(new_entry["tier"], new_entry["rank"])

    if old_value == new_value:
        return new_entry["leaguePoints"] - old_entry["leaguePoints"], False, None

    return None, True, "up" if new_value > old_value else "down"
