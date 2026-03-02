#!/usr/bin/env python3
"""
One-time migration: rename "Not Important" → "Low Importance" in Firebase / local JSON.

This is the only stored-value rename required. "Important" and "Moderately Important"
remain unchanged — only their display labels were updated in the UI.

Usage:
  python scripts/migrate-importance.py           # dry run (no writes)
  python scripts/migrate-importance.py --apply   # apply changes

Works with both Firebase Realtime Database and local JSON storage.
Reads credentials/config from the same env-vars as the bot.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# The only rename
OLD_VALUE = "Not Important"
NEW_VALUE = "Low Importance"


def migrate_task(task: dict, dry_run: bool) -> tuple[dict, bool]:
    """Return (task, changed) — applies rename if needed."""
    if task.get("colour") != OLD_VALUE:
        return task, False
    if dry_run:
        return task, True
    updated = dict(task)
    updated["colour"] = NEW_VALUE
    return updated, True


# ---------------------------------------------------------------------------
# Firebase
# ---------------------------------------------------------------------------
def migrate_firebase(username: str, dry_run: bool) -> int:
    try:
        from firebase_admin import db
    except ImportError:
        logger.error("firebase_admin not installed.")
        sys.exit(1)

    ref = db.reference(f"users/{username}/tasks")
    raw = ref.get()
    if not raw:
        return 0

    changed = 0

    if isinstance(raw, list):
        new_tasks = []
        for task in raw:
            if not isinstance(task, dict):
                new_tasks.append(task)
                continue
            updated, did_change = migrate_task(task, dry_run)
            if did_change:
                changed += 1
                prefix = "[DRY RUN] " if dry_run else ""
                logger.info(f"  {prefix}Task '{task.get('name', '?')}': "
                            f"{OLD_VALUE!r} → {NEW_VALUE!r}")
            new_tasks.append(updated)
        if not dry_run and changed:
            ref.set(new_tasks)

    elif isinstance(raw, dict):
        updates = {}
        for key, task in raw.items():
            if not isinstance(task, dict):
                continue
            updated, did_change = migrate_task(task, dry_run)
            if did_change:
                changed += 1
                prefix = "[DRY RUN] " if dry_run else ""
                logger.info(f"  {prefix}Task '{task.get('name', '?')}': "
                            f"{OLD_VALUE!r} → {NEW_VALUE!r}")
                updates[key] = updated
        if not dry_run and updates:
            ref.update(updates)

    return changed


# ---------------------------------------------------------------------------
# Local JSON
# ---------------------------------------------------------------------------
def migrate_local_json(data_dir: str, dry_run: bool) -> int:
    data_path = Path(data_dir)
    if not data_path.exists():
        logger.warning(f"Local data directory not found: {data_dir}")
        return 0

    total = 0
    for json_file in sorted(data_path.glob("*.json")):
        if json_file.name == "bot_metadata.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"  Skipping {json_file.name}: {e}")
            continue

        tasks = data if isinstance(data, list) else data.get("tasks", [])
        changed = 0
        new_tasks = []
        for task in tasks:
            if not isinstance(task, dict):
                new_tasks.append(task)
                continue
            updated, did_change = migrate_task(task, dry_run)
            if did_change:
                changed += 1
                prefix = "[DRY RUN] " if dry_run else ""
                logger.info(f"  {prefix}{json_file.name} / "
                            f"Task '{task.get('name', '?')}': "
                            f"{OLD_VALUE!r} → {NEW_VALUE!r}")
            new_tasks.append(updated)

        if not dry_run and changed:
            if isinstance(data, list):
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(new_tasks, f, indent=2, ensure_ascii=False)
            else:
                data["tasks"] = new_tasks
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

        total += changed

    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Rename "Not Important" → "Low Importance" in task database.'
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default: dry-run — shows what would change without writing)",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    if dry_run:
        logger.info("=== DRY RUN — no changes will be written ===")
        logger.info("Pass --apply to commit the migration.\n")
    else:
        logger.info("=== APPLYING MIGRATION ===\n")

    # Load .env from the discord_bot directory
    env_file = Path(__file__).parent.parent / "discord_bot" / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass

    use_local = os.getenv("USE_LOCAL_STORAGE", "false").lower() in ("true", "1", "yes")
    total_changed = 0

    if not use_local:
        firebase_url = os.getenv("FIREBASE_DATABASE_URL")
        if not firebase_url:
            logger.error("FIREBASE_DATABASE_URL not set and USE_LOCAL_STORAGE is not enabled.")
            sys.exit(1)

        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            firebase_creds = {
                "type": "service_account",
                "project_id":    os.getenv("FIREBASE_PROJECT_ID"),
                "private_key":   (os.getenv("FIREBASE_PRIVATE_KEY") or "").replace("\\n", "\n"),
                "client_email":  os.getenv("FIREBASE_CLIENT_EMAIL"),
            }
            if all(firebase_creds.values()):
                cred = credentials.Certificate(firebase_creds)
            else:
                for candidate in [
                    Path(__file__).parent.parent / "discord_bot" / "credentials.json",
                    Path(__file__).parent.parent / "credentials.json",
                ]:
                    if candidate.exists():
                        cred = credentials.Certificate(str(candidate))
                        break
                else:
                    logger.error("No Firebase credentials found.")
                    sys.exit(1)
            firebase_admin.initialize_app(cred, {"databaseURL": firebase_url})

        from firebase_admin import db as firebase_db
        users_data = firebase_db.reference("users").get()

        if not users_data:
            logger.info("No users found in Firebase.")
        else:
            usernames = list(users_data.keys())
            logger.info(f"Found {len(usernames)} user(s): {', '.join(usernames)}\n")
            for username in usernames:
                logger.info(f"--- Migrating user: {username} ---")
                count = migrate_firebase(username, dry_run)
                total_changed += count
                if count == 0:
                    logger.info("  (no tasks need migration)")
    else:
        data_dir = os.getenv(
            "LOCAL_DATA_DIR",
            str(Path(__file__).parent.parent / "discord_bot" / "data"),
        )
        logger.info(f"Using local storage: {data_dir}\n")
        total_changed = migrate_local_json(data_dir, dry_run)

    action = "Would rename" if dry_run else "Renamed"
    logger.info(f"\n{action} {total_changed} task(s) from {OLD_VALUE!r} → {NEW_VALUE!r}.")
    if dry_run and total_changed > 0:
        logger.info("Run with --apply to commit these changes.")
    elif total_changed == 0:
        logger.info("Nothing to migrate — database is already up to date.")


if __name__ == "__main__":
    main()
