"""
NBA Prediction Agent — Hermes Agent runner.

Wires together:
  • Nous Portal (OpenAI-compatible) as the LLM backend
  • BallDontLie NBA API tools (tools/nba_tools.py)
  • Local prediction engine (tools/prediction_engine.py)

Usage:
    python agent.py                          # interactive REPL
    python agent.py "Who wins tonight?"      # single-shot query
"""

from __future__ import annotations

import utils.session
import inspect
import json
import os
import sys
from typing import Any

from openai import OpenAI

from tools import nba_tools, prediction_engine

# ── Config ────────────────────────────────────────────────────────────────────

NOUS_API_KEY   = os.environ["NOUS_API_KEY"]
NOUS_BASE_URL  = os.environ.get("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
MODEL          = os.environ.get("NOUS_MODEL",    "hermes-4-70b")
MAX_TOOL_TURNS = int(os.environ.get("MAX_TOOL_TURNS", "10"))

client = OpenAI(api_key=NOUS_API_KEY, base_url=NOUS_BASE_URL)

# ── Load tool schemas ─────────────────────────────────────────────────────────

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "tools", "schemas.json")
with open(_SCHEMA_PATH) as f:
    TOOLS = json.load(f)

# ── Tool dispatcher ───────────────────────────────────────────────────────────

# Map function names → callables across both modules
_TOOL_MAP: dict[str, Any] = {}
for _mod in (nba_tools, prediction_engine):
    for _name, _fn in inspect.getmembers(_mod, inspect.isfunction):
        _TOOL_MAP[_name] = _fn


def dispatch_tool(name: str, arguments: str) -> str:
    """Call the named tool with JSON-decoded arguments, return JSON string result."""
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        kwargs = json.loads(arguments) if arguments else {}
        result = fn(**kwargs)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are HermesNBA — an expert NBA analyst and prediction agent powered by Nous Research's Hermes 3 model.

You have access to real-time NBA data via the BallDontLie API and a local prediction engine.

Your capabilities:
- Fetch today's and upcoming NBA game schedules
- Pull season averages, recent form (last 5/10 games), standings, and box scores
- Compute win probabilities using a calibrated logistic model (home-court advantage included)
- Project individual player stat lines against specific opponents
- Retrieve betting odds and player props (All-Star API tier required)
- Identify hot/cold streaks, home/away splits, and head-to-head trends

How you work:
1. When asked for a game prediction, ALWAYS call get_todays_games or get_upcoming_games first to get game IDs and team IDs.
2. Then call get_standings and get_team_season_stats for both teams.
3. Use extract_team_features + compute_matchup_features + win_probability from the prediction engine.
4. Present the formatted report using format_prediction_report, then add your own narrative analysis.
5. Always state the confidence level and note key caveats (injuries not tracked, model is heuristic).

Tone: sharp, analytical, confident. Back every claim with data. Avoid vague statements.
"""


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run(user_message: str) -> str:
    """Run one user query through the agentic tool-calling loop."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_message},
    ]

    for turn in range(MAX_TOOL_TURNS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # No tool calls → final answer
        if not msg.tool_calls:
            return msg.content or ""

        # Append assistant message with tool calls
        messages.append(msg.model_dump(exclude_unset=True))

        # Execute every tool call and append results
        for tc in msg.tool_calls:
            result = dispatch_tool(tc.function.name, tc.function.arguments)
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })

    return "[Max tool turns reached — partial analysis above]"


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(run(query))
        return

    print("HermesNBA Agent — type 'exit' to quit\n")
    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if query.lower() in ("exit", "quit", "q"):
            break
        if not query:
            continue
        answer = run(query)
        print(f"\nHermesNBA: {answer}\n")


if __name__ == "__main__":
    main()
