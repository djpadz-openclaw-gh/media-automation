#!/usr/bin/env python3
"""
monitor_utr.py — Monitor Ubiquiti Travel Router availability on store.ui.com
Sends Telegram alert if product is available (not sold out).
Tracks last-seen state to avoid duplicate alerts.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
PRODUCT_URL = "https://store.ui.com/us/en/category/wifi-special-devices/products/utr"
STATE_FILE = Path("/app/state/utr_state.json")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8623402151")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ── Helpers ───────────────────────────────────────────────────────────────────


def load_state() -> dict[str, Any]:
    """Load last-seen state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_status": None}


def save_state(state: dict[str, Any]) -> None:
    """Save state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def check_availability() -> bool:
    """
    Check if UTR is available (not sold out).
    Returns True if available, False if sold out.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(PRODUCT_URL, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for "Sold Out" or "Out of Stock" indicators
        # Common patterns: button text, badge text, or data attributes
        page_text = soup.get_text().lower()

        # Check for sold out indicators
        if "sold out" in page_text or "out of stock" in page_text:
            return False

        # If we find an "Add to Cart" button or similar, it's available
        if "add to cart" in page_text or "buy now" in page_text:
            return True

        # Default: assume available if we can't determine
        print("Warning: Could not determine availability status, assuming available")
        return True

    except Exception as e:
        print(f"Error checking availability: {e}", file=sys.stderr)
        return False


def send_telegram_alert(message: str) -> bool:
    """Send alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending Telegram alert: {e}", file=sys.stderr)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Monitor UTR availability and send alerts."""
    state = load_state()
    last_status = state.get("last_status")

    print("Checking UTR availability...")
    is_available = check_availability()

    if is_available:
        status = "available"
        if last_status != "available":
            message = "🚨 *Ubiquiti Travel Router is AVAILABLE!*\n\n"
            message += f"Check it out: {PRODUCT_URL}"
            print(f"Status changed to available, sending alert...")
            send_telegram_alert(message)
        else:
            print("Still available (no change)")
    else:
        status = "sold_out"
        if last_status == "available":
            message = "❌ Ubiquiti Travel Router is now SOLD OUT"
            print(f"Status changed to sold out, sending alert...")
            send_telegram_alert(message)
        else:
            print("Still sold out (no change)")

    state["last_status"] = status
    save_state(state)


if __name__ == "__main__":
    main()
