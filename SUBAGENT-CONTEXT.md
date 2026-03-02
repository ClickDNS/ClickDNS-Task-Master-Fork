# Task-Master — Sub-Agent Context

**ALWAYS read this file before working on the Task-Master codebase.**
*Last updated: 2026-03-02*

---

## What Task-Master Is

Discord bot + web app for internal task management. Syncs tasks between a Flask web UI and Discord forum channels. Used by the ClickDNS team (Kobii + George).

**Repo:** `~/projects/ClickDNS-Task-Master`  
**Branch:** `main` (staging for pending changes)  
**Hosted on:** George's server (NOT Koda's VPS)  
**Web API:** `https://task-master.clickdns.com.au`  
**Discord bot:** Running on George's server

---

## Tech Stack

- **Web app:** Python + Flask (`web_app/app.py`)
- **Discord bot:** Python + discord.py (`discord_bot/`)
- **Database:** Firebase Realtime Database
- **Auth:** Flask-Login (session-based) — `@login_required` decorator
- **Description offload:** koda-paste service (descriptions >500 chars)
- **Deployment:** Docker + Railway/George's server

---

## Architecture

```
Web UI (Flask)
  ↕ Firebase Realtime DB (tasks, subtasks)
Discord Bot (discord.py)
  ↕ Firebase (reads/writes tasks)
  ↕ Discord Forum (forum threads per task)
  
Sync: Discord bot polls Firebase every ~30s, syncs to Discord forum threads
Logging: Web events → Firebase `_pending_log_events` → Discord bot drains to audit channel
Descriptions >500 chars → offloaded to koda-paste, URL stored in Firebase
```

---

## Key Files

| File | Purpose |
|------|---------|
| `web_app/app.py` | Flask routes — ALL web CRUD operations |
| `web_app/templates/` | Jinja2 templates |
| `web_app/static/js/tasks.js` | Frontend JS (auto-refresh, task interactions) |
| `discord_bot/bot.py` | Bot entry point |
| `discord_bot/services/forum_sync_service.py` | Core sync logic |
| `discord_bot/services/logging_service.py` | Audit log events |
| `discord_bot/services/paste_service.py` | koda-paste offload |
| `discord_bot/discord_ui/modals.py` | Discord modal UI |
| `config.ini` | Config file (no secrets — those are in `.env`) |
| `credentials.json` | ⚠️ Firebase service account — committed to git (CLI-55) |

---

## Coding Patterns

### Flask routes — all sensitive routes need @login_required
```python
# CORRECT
@app.route('/api/tasks/<task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    ...

# WRONG — missing auth
@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    ...
```

### Firebase access pattern
```python
# Load tasks
tasks = load_tasks()  # helper in app.py

# Save tasks
save_tasks(tasks)  # always use helpers, not raw Firebase calls
```

### Event logging — use append_log_event
All task mutations (create/update/delete) must call `append_log_event()` so Discord audit log stays in sync:
```python
append_log_event('task_updated', {'task_id': ..., 'before': ..., 'after': ...})
```

### Description offload — use paste_service
Don't truncate descriptions. Offload via `paste_service.offload_description()` for anything >500 chars.

### Error handling
Never use bare `except:`. Use specific exceptions:
```python
# CORRECT
try:
    ...
except discord.NotFound:
    # thread deleted
except Exception as e:
    logger.error(f'Unexpected error: {e}')

# WRONG
except:
    pass
```

---

## Known Issues (Do Not Re-File)

- **CLI-55:** `credentials.json` (Firebase service account) committed to git — needs rotation + history purge
- **CLI-56:** `app.py` has `debug=True` in `app.run()` + hardcoded Flask `secret_key`
- **CLI-57:** Web login (`app.py:537`) accepts any non-empty username — zero authentication — CRITICAL
- **CLI-61/CLI-64/CLI-146:** Service injection refactor (same root cause — three separate issues)
- `credentials.json` in git is a **known** security issue — do NOT re-file it, it's already tracked

---

## What NOT to Flag

- `credentials.json` being present in the repo — already filed (CLI-55), don't duplicate
- Discord bot running synchronous loops — intentional polling architecture
- Firebase rules being permissive — managed externally, not in this repo
- `debug=True` in `app.run()` — already filed (CLI-56), don't duplicate
- Task-Master running on George's server — intentional, this is not Koda's VPS
