---
name: nba-predict
description: Full NBA game prediction pipeline — fetches live schedules, season stats, standings, and recent form, then computes win probabilities and player prop projections using a calibrated prediction engine.
version: 1.0.0
platforms: [linux, macos, windows]
required_environment_variables:
  - name: BALLDONTLIE_API_KEY
    prompt: BallDontLie API key
    help: Get a free key at https://www.balldontlie.io
    required_for: all NBA data tools
metadata:
  hermes:
    tags: [nba, sports, prediction, analytics, betting]
    category: sports
---

# NBA Prediction

## When to Use
- User asks "who wins tonight?", "predict [Team A] vs [Team B]", "give me a pick for..."
- User asks about player props: "project LeBron's points tonight"
- User wants standings, form, or matchup breakdowns
- User asks for a morning pick sheet or weekly power rankings

## Procedure

### 1. Identify the game
Call `get_todays_games` to fetch game IDs and team IDs.
If `get_todays_games` returns an empty list (no games today or API error), call `get_upcoming_games` instead.
If both return empty, use web search to find the schedule — do NOT create a new skill as a fallback.
If the user named specific teams, match them from the results.

### 2. Pull team context
For both home and away teams:
- Call `get_standings(season=<current>)` — W/L record, streak, conference rank
- Call `get_team_season_stats(team_id, season=<current>)` — full game log for rolling stats

### 3. Build feature vectors
Call `extract_team_features(season_stats, team_id)` for each team.
Then call `compute_matchup_features(home_feats, away_feats)` to get per-metric deltas.

### 4. Estimate win probability
Call `win_probability(matchup_features)` — returns `home_win_prob`, `away_win_prob`, and `confidence`.

### 5. Format and narrate
Call `format_prediction_report(home_team, away_team, home_feats, away_feats, probs)` for the data table.
Add 2-4 sentences of narrative: what's driving the pick, hot/cold streaks, key matchup mismatches.

### 6. Player props (optional)
If the user asks about a specific player:
1. `search_player(name)` → get player ID
2. `get_player_season_averages(player_ids, season)` → season avg
3. `get_player_game_stats(player_ids, seasons)` → last-5 box scores
4. `project_player_stat(season_avg, last5_avg, opponent_def_proxy)` → tonight's projection

## Output Format
Always include:
- Predicted winner + win probability + confidence level (HIGH / MEDIUM / LOW)
- The markdown comparison table from `format_prediction_report`
- A 2-4 sentence narrative explaining the key factors
- Caveats line: *Injury reports, back-to-backs, and travel fatigue are not modelled.*

## Pitfalls
- BallDontLie free tier includes: teams, players, games, season averages, box score stats, standings
- BallDontLie free tier does NOT include: betting odds, player props — inform the user if `get_game_odds` or `get_player_props` fails
- `get_team_season_stats` returns individual player rows, not team totals — `extract_team_features` handles this aggregation correctly
- If fewer than 5 games exist (early season), last-5 and last-10 averages fall back to available games
- If `get_todays_games` returns empty, there may be no games today — try `get_upcoming_games` or web search the schedule
- Never call a skill name as a tool — skills are instructions, not callable functions

## Verification
After delivering the prediction, ask the user:
- Whether they want props for any specific player
- Whether they'd like the same analysis for other games on the slate
After the game, if the user reports the result, use `skill_manage` to log prediction accuracy.
