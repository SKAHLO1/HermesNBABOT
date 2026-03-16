"""
Prediction Engine — pure-Python analytics layer.
Called by Hermes Agent tools; no LLM involved here.
Produces structured feature vectors and win-probability estimates
that Hermes then reasons over and explains in natural language.
"""

from __future__ import annotations

import math
from typing import Any


# ── Utility ───────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    return val if val is not None else default


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_team_features(season_stats: list[dict], team_id: int) -> dict:
    """
    Given a list of per-game stat dicts from get_team_season_stats,
    compute rolling and cumulative features for a team.
    Returns a feature dict ready for win-probability estimation.
    """
    games = [s for s in season_stats if s.get("team", {}).get("id") == team_id]
    if not games:
        return {}

    # Sort by game date
    games.sort(key=lambda g: g.get("game", {}).get("date", ""))

    pts = [_safe(g.get("pts")) for g in games]
    fgp = [_safe(g.get("fg_pct")) for g in games]
    fg3p = [_safe(g.get("fg3_pct")) for g in games]
    reb = [_safe(g.get("reb")) for g in games]
    ast = [_safe(g.get("ast")) for g in games]
    tov = [_safe(g.get("turnover")) for g in games]
    stl = [_safe(g.get("stl")) for g in games]
    blk = [_safe(g.get("blk")) for g in games]

    n = len(games)
    last5 = slice(max(0, n - 5), n)
    last10 = slice(max(0, n - 10), n)

    def avg(lst, sl=None):
        subset = lst[sl] if sl else lst
        return sum(subset) / len(subset) if subset else 0.0

    return {
        "team_id": team_id,
        "games_played": n,
        # Season averages
        "pts_avg": avg(pts),
        "fg_pct_avg": avg(fgp),
        "fg3_pct_avg": avg(fg3p),
        "reb_avg": avg(reb),
        "ast_avg": avg(ast),
        "tov_avg": avg(tov),
        "stl_avg": avg(stl),
        "blk_avg": avg(blk),
        # Rolling last-5
        "pts_last5": avg(pts, last5),
        "fg_pct_last5": avg(fgp, last5),
        "tov_last5": avg(tov, last5),
        # Rolling last-10
        "pts_last10": avg(pts, last10),
        # Efficiency proxy: points - (turnovers * 1.5)
        "off_efficiency": avg(pts) - avg(tov) * 1.5,
        "def_proxy": avg(stl) + avg(blk),
        # Hot/cold streak: last-5 pts vs season avg
        "recent_form_delta": avg(pts, last5) - avg(pts),
    }


def compute_matchup_features(home_feats: dict, away_feats: dict) -> dict:
    """
    Combine home and away feature dicts into a matchup feature vector.
    Positive deltas favour the home team.
    """
    def delta(key):
        return _safe(home_feats.get(key)) - _safe(away_feats.get(key))

    return {
        "pts_delta": delta("pts_avg"),
        "fg_pct_delta": delta("fg_pct_avg"),
        "fg3_pct_delta": delta("fg3_pct_avg"),
        "reb_delta": delta("reb_avg"),
        "ast_delta": delta("ast_avg"),
        "tov_delta": -delta("tov_avg"),        # fewer turnovers = better
        "def_delta": delta("def_proxy"),
        "off_eff_delta": delta("off_efficiency"),
        "form_delta": delta("recent_form_delta"),
        "pts_last5_delta": delta("pts_last5"),
    }


# ── Win probability model ─────────────────────────────────────────────────────

# Simple logistic model calibrated on NBA home-court advantage (~60 % base rate).
# Weights are heuristic — intended to give Hermes a calibrated prior to reason from.
_WEIGHTS = {
    "pts_delta":       0.040,
    "fg_pct_delta":    4.500,
    "fg3_pct_delta":   2.000,
    "reb_delta":       0.080,
    "ast_delta":       0.060,
    "tov_delta":       0.100,
    "def_delta":       0.150,
    "off_eff_delta":   0.060,
    "form_delta":      0.050,
    "pts_last5_delta": 0.030,
}
_HOME_COURT_BIAS = 0.40   # log-odds boost for home team


def win_probability(matchup_features: dict) -> dict:
    """
    Return estimated win probabilities for home and away team.
    Uses a logistic function over a weighted feature sum.
    """
    log_odds = _HOME_COURT_BIAS
    for feat, w in _WEIGHTS.items():
        log_odds += w * _safe(matchup_features.get(feat))

    prob_home = 1.0 / (1.0 + math.exp(-log_odds))
    prob_away = 1.0 - prob_home

    return {
        "home_win_prob": round(prob_home, 4),
        "away_win_prob": round(prob_away, 4),
        "confidence": _confidence_label(prob_home),
        "log_odds": round(log_odds, 4),
    }


def _confidence_label(p: float) -> str:
    spread = abs(p - 0.5)
    if spread >= 0.20:
        return "HIGH"
    if spread >= 0.10:
        return "MEDIUM"
    return "LOW"


# ── Player prop projection ────────────────────────────────────────────────────

def project_player_stat(
    season_avg: float,
    last5_avg: float,
    opponent_def_proxy: float,
    league_avg_def_proxy: float = 8.0,
) -> dict:
    """
    Project a player's stat line for tonight using a weighted blend of
    season average, recent form, and opponent defensive strength.
    """
    form_weight = 0.40
    season_weight = 0.60
    blended = form_weight * last5_avg + season_weight * season_avg

    # Defensive adjustment: stronger defence suppresses output
    def_factor = 1.0 - 0.015 * (opponent_def_proxy - league_avg_def_proxy)
    def_factor = max(0.75, min(1.25, def_factor))   # cap adjustment at ±25 %

    projection = round(blended * def_factor, 1)
    return {
        "projection": projection,
        "season_avg": round(season_avg, 1),
        "last5_avg": round(last5_avg, 1),
        "def_adjustment_factor": round(def_factor, 3),
    }


# ── Formatted report helper ───────────────────────────────────────────────────

def format_prediction_report(
    home_team: str,
    away_team: str,
    home_feats: dict,
    away_feats: dict,
    probs: dict,
) -> str:
    """Return a compact, human-readable prediction summary for Hermes to embed."""
    winner = home_team if probs["home_win_prob"] >= 0.5 else away_team
    win_pct = max(probs["home_win_prob"], probs["away_win_prob"])

    lines = [
        f"## Prediction: {home_team} vs {away_team}",
        f"**Predicted winner:** {winner}  ({win_pct:.1%}, confidence: {probs['confidence']})",
        "",
        f"| Metric            | {home_team:<20} | {away_team:<20} |",
        f"|-------------------|----------------------|----------------------|",
        f"| PPG (season)      | {home_feats.get('pts_avg', 0):>6.1f}               | {away_feats.get('pts_avg', 0):>6.1f}               |",
        f"| PPG (last 5)      | {home_feats.get('pts_last5', 0):>6.1f}               | {away_feats.get('pts_last5', 0):>6.1f}               |",
        f"| FG% (season)      | {home_feats.get('fg_pct_avg', 0):>6.3f}               | {away_feats.get('fg_pct_avg', 0):>6.3f}               |",
        f"| Off. Efficiency   | {home_feats.get('off_efficiency', 0):>6.1f}               | {away_feats.get('off_efficiency', 0):>6.1f}               |",
        f"| Def. Proxy        | {home_feats.get('def_proxy', 0):>6.1f}               | {away_feats.get('def_proxy', 0):>6.1f}               |",
        f"| Form Δ (last 5)   | {home_feats.get('recent_form_delta', 0):>+6.1f}               | {away_feats.get('recent_form_delta', 0):>+6.1f}               |",
        "",
        f"*Home-court advantage included in model.*",
    ]
    return "\n".join(lines)
