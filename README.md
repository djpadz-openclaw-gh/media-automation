# media-automation

Automated notifications for media server events (Sonarr, Radarr, etc.).

## Scripts

### notify_sonarr.py

Polls Sonarr for newly imported episodes and sends Telegram notifications.

**Features:**
- Tracks last-seen history ID to avoid duplicate notifications
- Batches API calls for efficiency (single series lookup, bulk episode lookups)
- Groups episodes by series for cleaner messages
- Respects Telegram's 4096-character message limit
- Fetches API credentials from 1Password

**Setup:**

1. Ensure 1Password CLI is installed and authenticated
2. Create a `.op-service-account` file in the parent directory with your service account token
3. Verify these 1Password items exist in the OpenClaw vault:
   - `Sonarr API key` (field: "API Key")
   - `Telegram API: openclaw_djpadz_bot` (field: "password")

**Run manually:**
```bash
python3 notify_sonarr.py
```

**Run via cron (every 15 minutes):**
```bash
*/15 * * * * cd /path/to/media-automation && python3 notify_sonarr.py
```

**Docker:**
```bash
docker build -t media-automation:latest .
docker run --rm \
  -v /path/to/.op-service-account:/app/.op-service-account:ro \
  -v /path/to/state:/app/state \
  media-automation:latest
```

## State Files

- `sonarr_notified.json` — Tracks the last Sonarr history ID processed
- `radarr_notified.json` — (Future) Tracks the last Radarr history ID processed

These files are created automatically on first run and should be persisted between runs.

## Future Scripts

- `notify_radarr.py` — Movie imports
- `notify_lidarr.py` — Music/comedy imports
- `notify_bazarr.py` — Subtitle updates

## License

MIT
