# ClickDNS Task Master

Internal task management system with Desktop GUI, Discord bot, and Flask web interface. All three UIs share state via Firebase Realtime Database.

## Quick Reference
- **Stack:** Python 3.11, Flask, Discord.py, Tkinter, Firebase Realtime Database
- **Branch:** `main`
- **Deploy:** Discord bot runs as systemd service on VPS

## Entry Points

| Interface | Entry | Run |
|-----------|-------|-----|
| Desktop GUI | `Task-Master.py` | `python Task-Master.py` |
| Web App | `web_app/app.py` | `python web_app/app.py` |
| Discord Bot | `discord_bot/bot.py` | `systemctl --user restart task-master-web.service` |

## Project Structure

```
├── Task-Master.py           # Desktop GUI (Tkinter)
├── config.ini               # User config (username persistence)
├── credentials.json         # Firebase service account (DO NOT COMMIT)
├── .env                     # FIREBASE_DATABASE_URL, OWNERS
├── requirements.txt         # firebase-admin, tkcalendar, python-dotenv, pytest
├── discord_bot/
│   ├── bot.py               # Bot entry point
│   ├── services/            # reminder, dashboard, forum_sync, task, logging, paste
│   ├── database/            # firebase_manager, task_model
│   ├── discord_ui/          # buttons, embeds, modals
│   ├── config/              # settings.py
│   └── utils/               # validators, logger
├── web_app/
│   ├── app.py               # Flask app
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JS, FontAwesome
└── scripts/
    └── offload_long_descriptions.py  # Offloads long descriptions to koda-paste
```

## Key Patterns

- **Firebase optional:** Falls back to local storage if `credentials.json` missing
- **Discord deadline format:** `DD-MM-YYYY hh:mm AM/PM` (e.g., `16-02-2026 09:30 PM`)
- **koda-paste integration:** Long descriptions (>500 chars) auto-offload to koda-paste server
- **Forum sync:** Tasks stay in sync between Desktop/Web/Discord via Firebase Realtime DB
- **Subtasks:** Stable numeric IDs; created/edited via `/subtask <id>` in Discord thread
- **Task priorities:** Filtered in Discord forum via emoji (red = Important, orange = Moderate, white = Not Important)

## Environment Variables

See `discord_bot/.env.example` for full list. Key vars:
- `DISCORD_BOT_TOKEN` — Bot token
- `TASK_FORUM_CHANNEL` — Discord forum channel ID for tasks
- `REMINDER_CHANNEL` — Channel for deadline notifications
- `TASKMASTER_USERNAME` — Username for task ownership
- `FIREBASE_DATABASE_URL` — Firebase Realtime Database URL

## Discord Bot Services

| Service | Purpose |
|---------|---------|
| `ReminderService` | Deadline notifications |
| `DashboardService` | Read-only stats dashboard |
| `ForumSyncService` | Keeps forum posts in sync with tasks |
| `TaskService` | Task CRUD operations |
| `LoggingService` | Audit logs to Discord channel (optional) |
| `PasteService` | koda-paste integration for long content |

## Gotchas

- `credentials.json` contains Firebase service account key — never commit
- Discord bot requires `TASK_FORUM_CHANNEL` to be a Forum channel type
- Web app and desktop GUI share the same Firebase path — changes are real-time
- Task Master CLI (`task-master-cli`) uses `curl -4` because Cloudflare blocks IPv6
