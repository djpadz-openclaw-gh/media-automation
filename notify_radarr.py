#!/usr/bin/env python3
"""
notify_radarr.py — Alert via Telegram when new movies are imported into Radarr.
Tracks last-seen history ID in a state file to avoid re-alerting.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────────────────
RADARR_URL = os.environ.get("RADARR_URL", "http://dindjarin.tail1916d.ts.net:7878")
STATE_FILE = Path("/app/state/radarr_notified.json")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8623402151")

# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_history_id": 0}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Radarr ────────────────────────────────────────────────────────────────────

def radarr_get(path: str, api_key: str, params: dict[str, Any] | None = None) -> Any:
    resp = requests.get(
        f"{RADARR_URL}/api/v3/{path}",
        headers={"X-Api-Key": api_key},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_new_imports(api_key: str, since_id: int) -> list[dict[str, Any]]:
    """Return downloadFolderImported records with id > since_id, oldest-first."""
    page = 1
    page_size = 50
    new_records: list[dict[str, Any]] = []

    while True:
        data = radarr_get("history", api_key, {
            "page": page,
            "pageSize": page_size,
            "sortKey": "date",
            "sortDirection": "descending",
            "eventType": 3,   # downloadFolderImported
        })
        records: list[dict[str, Any]] = data.get("records", [])
        if not records:
            break

        done = False
        for rec in records:
            if rec["id"] <= since_id:
                done = True
                break
            new_records.append(rec)

        if done or page * page_size >= data.get("totalRecords", 0):
            break
        page += 1

    # Return oldest-first so notifications are chronological
    return list(reversed(new_records))


def enrich_records(records: list[dict[str, Any]], api_key: str) -> list[dict[str, Any]]:
    """Add movie title + year to all records, batching movie lookups."""
    # Fetch all movies once (single API call)
    try:
        all_movies: list[dict[str, Any]] = radarr_get("movie", api_key)
        movie_map: dict[int, dict[str, Any]] = {m["id"]: m for m in all_movies}
    except Exception:
        movie_map = {}

    for rec in records:
        movie = movie_map.get(rec["movieId"], {})
        rec["_title"] = movie.get("title", f"Movie #{rec['movieId']}")
        rec["_year"]  = movie.get("year")
        rec["_imdbId"] = movie.get("imdbId", "")

    return records


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    print(f"DEBUG: Sending message to chat_id={chat_id} (type: {type(chat_id).__name__})")
    print(f"DEBUG: Message length: {len(text)} chars")
    print(f"DEBUG: Message preview: {text[:200]}...")
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": int(chat_id), "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    resp.raise_for_status()


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text


def format_movie(rec: dict[str, Any]) -> str:
    title  = escape_markdown(rec["_title"])
    year   = rec["_year"]
    quality = rec.get("quality", {}).get("quality", {}).get("name", "")

    line = f"🎬 *{title}*"
    if year:
        line += f" ({year})"
    if quality:
        line += f" _{quality}_"
    return line


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("RADARR_API_KEY")
    if not api_key:
        raise ValueError("RADARR_API_KEY environment variable not set")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    state   = load_state()
    since   = state["last_history_id"]
    records = get_new_imports(api_key, since)

    if not records:
        print("No new imports since last check.")
        return

    print(f"Found {len(records)} new import(s).")

    # Enrich all records at once (batched movie lookups)
    records = enrich_records(records, api_key)

    # Build message — keep under Telegram's 4096-char limit
    lines: list[str] = ["🎥 *New in Radarr*"]
    for rec in records:
        lines.append(format_movie(rec))

    message = "\n".join(lines)
    if len(message) > 4000:
        # Truncate gracefully without breaking HTML tags
        message = message[:3950]
        # Remove any incomplete HTML tags at the end
        last_tag_start = message.rfind('<')
        last_tag_end = message.rfind('>')
        if last_tag_start > last_tag_end:
            # There's an unclosed tag, remove it
            message = message[:last_tag_start]
        message = message.rstrip() + "\n…(truncated)"

    send_telegram(bot_token, TELEGRAM_CHAT_ID, message)
    print(f"Sent notification for {len(records)} movie(s).")

    # Save highest ID seen
    max_id = max(r["id"] for r in records)
    state["last_history_id"] = max_id
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
