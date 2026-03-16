"""
NBA Tools — callable by Hermes Agent via function-calling.
Each function maps 1-to-1 to a JSON tool schema defined in tools/schemas.json.
Data source: BallDontLie NBA API (https://nba.balldontlie.io)
"""

import os
import requests
from datetime import date, timedelta
from typing import Optional

BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"


def _get(path: str, params: dict = None) -> dict:
    api_key = os.environ.get("BALLDONTLIE_API_KEY", "")
    headers = {"Authorization": api_key}
    url = f"{BALLDONTLIE_BASE}{path}"
    resp = requests.get(url, headers=headers, params=params or {}, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── Team helpers ──────────────────────────────────────────────────────────────

def get_all_teams() -> dict:
    """Return all 30 NBA teams."""
    return _get("/teams")


def get_team(team_id: int) -> dict:
    """Return a single team by ID."""
    return _get(f"/teams/{team_id}")


# ── Player helpers ────────────────────────────────────────────────────────────

def search_player(name: str) -> dict:
    """Search for players by name."""
    return _get("/players", {"search": name, "per_page": 10})


def get_player(player_id: int) -> dict:
    """Return a single player by ID."""
    return _get(f"/players/{player_id}")


# ── Game helpers ──────────────────────────────────────────────────────────────

def get_games(
    date_str: Optional[str] = None,
    team_ids: Optional[list[int]] = None,
    seasons: Optional[list[int]] = None,
    per_page: int = 25,
) -> dict:
    """
    Fetch NBA games with optional filters.
    date_str: YYYY-MM-DD
    team_ids: list of team IDs
    seasons: list of season years (e.g. [2024])
    """
    params: dict = {"per_page": per_page}
    if date_str:
        params["dates[]"] = date_str
    if team_ids:
        params["team_ids[]"] = team_ids
    if seasons:
        params["seasons[]"] = seasons
    return _get("/games", params)


def get_todays_games() -> dict:
    """Return all NBA games scheduled for today."""
    today = date.today().isoformat()
    return get_games(date_str=today)


def get_upcoming_games(days_ahead: int = 7) -> dict:
    """Return games in the next N days."""
    results = []
    for i in range(1, days_ahead + 1):
        d = (date.today() + timedelta(days=i)).isoformat()
        data = get_games(date_str=d)
        results.extend(data.get("data", []))
    return {"data": results}


def get_game(game_id: int) -> dict:
    """Return a single game by ID."""
    return _get(f"/games/{game_id}")


# ── Stats helpers ─────────────────────────────────────────────────────────────

def get_player_season_averages(player_ids: list[int], season: int) -> dict:
    """
    Return season averages for a list of player IDs.
    season: e.g. 2024 for the 2024-25 season.
    NOTE: /season_averages requires a paid BallDontLie tier.
    Use compute_player_averages() instead on the free tier.
    """
    try:
        return _get("/season_averages", {
            "season": season,
            "player_ids[]": player_ids,
        })
    except Exception:
        return {
            "error": "season_averages endpoint requires a paid BallDontLie tier. "
                     "Use compute_player_averages(player_ids, season) instead — "
                     "it calculates averages from raw game stats which are free."
        }


def compute_player_averages(player_ids: list[int], season: int, last_n: int = 0) -> dict:
    """
    Compute per-game averages from raw box score stats (free tier alternative to season_averages).
    last_n: if > 0, only average the last N games (e.g. last_n=5 for recent form).
    Returns averaged pts, reb, ast, stl, blk, fg_pct, fg3_pct, ft_pct, min per player.
    """
    import math
    raw = get_player_game_stats(player_ids=player_ids, seasons=[season], per_page=100)
    games_by_player: dict[int, list] = {}
    for row in raw.get("data", []):
        pid = row.get("player", {}).get("id") or row.get("player_id")
        if pid not in games_by_player:
            games_by_player[pid] = []
        games_by_player[pid].append(row)

    results = []
    for pid, games in games_by_player.items():
        if last_n > 0:
            games = games[-last_n:]
        if not games:
            continue
        n = len(games)
        def avg(key):
            vals = [g.get(key) or 0 for g in games]
            return round(sum(vals) / n, 3)
        def pct(made_key, att_key):
            made = sum(g.get(made_key) or 0 for g in games)
            att = sum(g.get(att_key) or 0 for g in games)
            return round(made / att, 3) if att else 0.0
        results.append({
            "player_id": pid,
            "games": n,
            "pts": avg("pts"),
            "reb": avg("reb"),
            "ast": avg("ast"),
            "stl": avg("stl"),
            "blk": avg("blk"),
            "min": avg("min"),
            "fg_pct": pct("fgm", "fga"),
            "fg3_pct": pct("fg3m", "fg3a"),
            "ft_pct": pct("ftm", "fta"),
        })
    return {"data": results}


def get_player_game_stats(
    player_ids: list[int],
    seasons: Optional[list[int]] = None,
    game_ids: Optional[list[int]] = None,
    per_page: int = 25,
) -> dict:
    """Return per-game stats for specific players, optionally filtered by season or game."""
    params: dict = {"per_page": per_page}
    params["player_ids[]"] = player_ids
    if seasons:
        params["seasons[]"] = seasons
    if game_ids:
        params["game_ids[]"] = game_ids
    return _get("/stats", params)


def get_team_season_stats(team_id: int, season: int, per_page: int = 82) -> dict:
    """Return all game stats for a team in a given season (for rolling averages)."""
    params = {
        "team_ids[]": [team_id],
        "seasons[]": [season],
        "per_page": per_page,
    }
    return _get("/stats", params)


# ── Standings helpers ─────────────────────────────────────────────────────────

def get_standings(season: int) -> dict:
    """Return conference/division standings for a season."""
    return _get("/standings", {"season": season})


# ── Betting / odds helpers ────────────────────────────────────────────────────

def get_game_odds(game_id: int) -> dict:
    """Return betting odds for a specific game (requires All-Star tier or above)."""
    return _get(f"/games/{game_id}/odds")


def get_player_props(game_id: int, player_id: int) -> dict:
    """Return player prop odds for a game/player combo."""
    return _get("/player_props", {
        "game_id": game_id,
        "player_id": player_id,
    })
