# HermesNBA — NBA Prediction Agent powered by Hermes Agent

> **Hermes Agent Hackathon submission** — a fully agentic NBA prediction system that
> combines Nous Research's Hermes 3 model (via Nous Portal) with real-time NBA data
> to produce game predictions, player prop projections, and scheduled pick sheets.

---

## How It Works — Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  USER / TELEGRAM / DISCORD                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │  natural language query
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 HERMES AGENT  (hermes CLI / gateway)            │
│  • ~/.hermes/SOUL.md persona        • Memory across sessions    │
│  • ~/.hermes/skills/nba-predict/    • Cron via natural language │
│    SKILL.md  (auto-loaded skill)    • Telegram/Discord gateway  │
└──────────────────────────────┬──────────────────────────────────┘
                               │  MCP (Model Context Protocol)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│            mcp_server.py  (stdio MCP server)                    │
│   Hermes spawns this process automatically via config.yaml      │
└──────────┬──────────────────────────────────────┬──────────────┘
           │                                      │
           ▼                                      ▼
┌──────────────────────┐           ┌─────────────────────────────┐
│  BallDontLie NBA API │           │  Local Prediction Engine    │
│  tools/nba_tools.py  │           │  tools/prediction_engine.py │
│  • Teams & players   │           │  • extract_team_features()  │
│  • Game schedules    │           │  • compute_matchup_features │
│  • Season averages   │           │  • win_probability()        │
│  • Box score stats   │           │  • project_player_stat()    │
│  • Standings         │           │  • format_prediction_report │
│  • Betting odds*     │           └─────────────────────────────┘
│  • Player props*     │
│  (* All-Star tier)   │           Also usable standalone:
└──────────────────────┘           agent.py (OpenAI loop, no Hermes needed)
```

---

## Why Hermes Agent is Perfect for This

| Hermes Agent Feature | How HermesNBA Uses It |
|---|---|
| **MCP integration** | `mcp_server.py` exposes all 12 NBA tools via stdio MCP — Hermes spawns it automatically from `config.yaml` |
| **Skills system (`SKILL.md`)** | `skills/nba-predict/SKILL.md` is a reusable, step-by-step prediction playbook the agent loads and follows |
| **SOUL.md persona** | `~/.hermes/SOUL.md` defines the analyst voice, guardrails, and memory nudges globally for the instance |
| **Memory across sessions** | `memory.memory_enabled` + `user_profile_enabled` — agent remembers favourite teams, betting preferences, and its own accuracy |
| **Cron via natural language** | Tell Hermes "every morning at 9 AM send me a pick sheet on Telegram" — it sets up the cron job itself |
| **Messaging gateway** | `hermes gateway setup` — Telegram, Discord, Slack, WhatsApp, Signal supported out of the box |
| **Self-improving skills** | After a prediction, the agent can call `skill_manage` to update `SKILL.md` based on what worked |
| **Any model / any endpoint** | Switch from Nous Portal to OpenRouter or a local model with `hermes model` — zero code changes |
| **`/nba-predict` slash command** | Every installed skill becomes a slash command automatically — type `/nba-predict` in any chat |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Linux, macOS, or **WSL2** (required on Windows — native Windows not supported by Hermes Agent)
- A [Nous Portal](https://portal.nousresearch.com) account — API key (for `agent.py` standalone) or OAuth via `hermes model` (for Hermes Agent CLI)
- A [BallDontLie](https://www.balldontlie.io) API key (free tier works for all core features)

---

### 1. Install Hermes Agent

```bash
# Linux / macOS / WSL2
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
```

### 2. Connect to Nous Portal

```bash
hermes model
# → Select "Nous Portal" → follow the OAuth flow in your browser
```

### 3. Clone this project and install Python deps

```bash
# From WSL2 — the project is accessible via the /mnt/c mount
cp -r /mnt/c/Users/USER/CascadeProjects/nba-hermes-agent ~/nba-hermes-agent
cd ~/nba-hermes-agent
pip install -r requirements.txt
```

Add your BallDontLie API key to Hermes's secrets store:

```bash
hermes config set BALLDONTLIE_API_KEY your_key_here
# This saves it to ~/.hermes/.env automatically
```

### 4. Install the NBA prediction skill

```bash
# Skills live at ~/.hermes/skills/<skill-name>/SKILL.md
cp -r skills/nba-predict ~/.hermes/skills/nba-predict
```

### 5. Set the SOUL.md persona

```bash
cp SOUL.md ~/.hermes/SOUL.md
```

### 6. Apply the config (memory, MCP server, compression)

```bash
# Merge into your existing config, or copy if starting fresh
cp hermes_config.yaml ~/.hermes/config.yaml
```

### 7. Start Hermes — it auto-connects the MCP server

```bash
hermes
```

Hermes will spawn `mcp_server.py` automatically (as defined in `config.yaml` under `mcp_servers`),
loading all 12 NBA tools. You'll see `nba-tools` listed in the tools banner on startup.

---

## Usage

### Interactive predictions
```
❯ Who wins tonight?
❯ Predict Warriors vs Nuggets
❯ Project Stephen Curry's points against the Clippers
❯ Give me your top 3 picks for this week's slate
❯ Show me current NBA standings
```

### Slash command (from any platform)
```
/nba-predict Warriors vs Nuggets
```

### Schedule a daily pick sheet (natural language cron)
```
❯ Every morning at 9 AM, pull today's NBA games, run predictions for
  all matchups, and send me a pick sheet on Telegram.
```
Hermes sets up the cron job automatically. Manage it later with `hermes cron list`.

### Set up Telegram delivery
```bash
hermes gateway setup
# → Follow the interactive wizard to connect your Telegram bot
```

---

## Standalone Mode (no Hermes Agent install required)

`agent.py` is a self-contained agentic loop using the OpenAI SDK directly against Nous Portal:

```bash
# Set keys in .env (copy from .env.example)
cp .env.example .env
# Fill in NOUS_API_KEY and BALLDONTLIE_API_KEY

export $(cat .env | xargs)

# Interactive REPL
python agent.py

# Single-shot
python agent.py "Who wins Lakers vs Celtics tonight?"
python agent.py "Project LeBron James's points tonight vs the Bucks"
```

---

## Example Output

```
❯ Who wins Celtics vs Knicks tonight?

[Calling get_todays_games...]
[Calling get_standings(season=2024)...]
[Calling get_team_season_stats(team_id=2, season=2024)...]
[Calling get_team_season_stats(team_id=20, season=2024)...]
[Calling extract_team_features + compute_matchup_features + win_probability...]

## Prediction: Boston Celtics vs New York Knicks

**Predicted winner:** Boston Celtics  (67.3%, confidence: HIGH)

| Metric            | Boston Celtics       | New York Knicks      |
|-------------------|----------------------|----------------------|
| PPG (season)      |  119.4               |  112.8               |
| PPG (last 5)      |  123.1               |  109.4               |
| FG% (season)      |  0.482               |  0.461               |
| Off. Efficiency   |  103.2               |   96.7               |
| Def. Proxy        |    9.1               |    8.3               |
| Form Δ (last 5)   |  +3.7                |   -3.4               |

*Home-court advantage included in model.*

Boston has been on a tear over the last 5 games (+3.7 PPG above their season
average) while New York has cooled off significantly. The Celtics' shooting
efficiency edge (FG% +2.1%) combined with superior defensive proxies makes this
a comfortable lean. Look for Tatum to exploit the Knicks' perimeter defence.

⚠️ *Injury reports, back-to-backs, and travel fatigue are not modelled.*
```

---

## Project Structure

```
nba-hermes-agent/
├── agent.py                       # Standalone agentic loop (OpenAI SDK, no Hermes needed)
├── mcp_server.py                  # MCP stdio server — Hermes spawns this automatically
├── hermes_config.yaml             # Drop into ~/.hermes/config.yaml
├── SOUL.md                        # Drop into ~/.hermes/SOUL.md
├── .env.example                   # Keys template for standalone mode
├── requirements.txt               # openai, requests, python-dotenv, mcp
├── skills/
│   └── nba-predict/
│       └── SKILL.md               # Copy to ~/.hermes/skills/nba-predict/SKILL.md
└── tools/
    ├── __init__.py
    ├── schemas.json               # OpenAI-format tool schemas (12 tools)
    ├── nba_tools.py               # BallDontLie NBA API wrappers
    └── prediction_engine.py       # Feature extraction + logistic win-probability model
```

---

## Tool Reference

| Tool | Description |
|---|---|
| `get_all_teams` | All 30 NBA teams |
| `get_team` | Single team by ID |
| `search_player` | Search players by name |
| `get_player_season_averages` | PTS/REB/AST/FG% season averages |
| `get_player_game_stats` | Per-game box scores |
| `get_todays_games` | Today's game schedule + live scores |
| `get_upcoming_games` | Games in the next N days |
| `get_games` | Filtered game query |
| `get_team_season_stats` | Full season game log for rolling stats |
| `get_standings` | Conference/division standings |
| `get_game_odds` | Moneyline/spread/OU odds *(All-Star tier)* |
| `get_player_props` | Player prop lines *(All-Star tier)* |

---

## Prediction Model

Win probability uses a **logistic model** over 10 feature deltas:

```
P(home win) = σ( home_court_bias + Σ wᵢ · featureᵢ )
```

Features: PPG Δ, FG% Δ, 3P% Δ, rebound Δ, assist Δ, turnover Δ (inverted),
defensive proxy Δ, offensive efficiency Δ, recent form Δ (last-5 vs season), last-5 PPG Δ.

Home-court bias is calibrated to the NBA's historical ~60% home win rate.
Weights are heuristic — for production, replace with a gradient-boosted model trained on historical seasons.

---

## Extending

- **Trained ML model** — replace `win_probability()` in `prediction_engine.py` with a `joblib`-serialised sklearn/XGBoost model; the MCP interface is unchanged
- **Injury tracking** — add a tool to `nba_tools.py` + a schema entry in `schemas.json`; Hermes picks it up automatically
- **Prediction accuracy log** — add `log_prediction()` + `get_accuracy_report()` tools; reference them in `SKILL.md`'s Verification section so the agent self-improves
- **Additional sports** — BallDontLie covers NFL, MLB, NHL, EPL, WNBA — duplicate the tools pattern for any league

---

## API Keys

| Service | Where to get it | Cost |
|---|---|---|
| Nous Portal | [portal.nousresearch.com](https://portal.nousresearch.com) | Subscription / pay-per-token |
| BallDontLie | [balldontlie.io](https://www.balldontlie.io) | Free / $9.99/mo All-Star (for odds + props) |
| Telegram Bot | [@BotFather](https://t.me/botfather) on Telegram | Free |

---

## Disclaimer

For educational and entertainment purposes only. Not financial or gambling advice.
Always gamble responsibly and within your local laws.
