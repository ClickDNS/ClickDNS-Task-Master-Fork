"""
Service to sync tasks with Discord forum threads
"""
import logging
import discord
from config.settings import Settings

logger = logging.getLogger(__name__)


class ForumSyncService:
    """Synchronize DB tasks to forum threads and back"""

    PRIORITY_EMOJIS = {
        "Important": "🔴",
        "Moderately Important": "🟠",
        "Not Important": "⚪",
        "default": "⚪",
    }

    def __init__(self):
        self._bot = None
        self._db = None
        self.task_to_thread = {}
        self.thread_to_task = {}

    def _priority_emoji(self, priority: str) -> str:
        return self.PRIORITY_EMOJIS.get(priority, "⚪")

    def set_bot(self, bot):
        self._bot = bot

    def set_database(self, db):
        self._db = db
        self._load_mappings()

    def _load_mappings(self):
        if not self._db:
            return
        try:
            mappings = self._db.get_task_thread_mappings()
            self.task_to_thread = mappings.get("task_to_thread", {})
            self.thread_to_task = mappings.get("thread_to_task", {})
        except Exception as e:
            logger.error(f"Failed to load forum mappings: {e}")

    def _save_mappings(self):
        if not self._db:
            return
        try:
            self._db.save_task_thread_mappings(
                self.task_to_thread, self.thread_to_task)
        except Exception as e:
            logger.error(f"Failed to save forum mappings: {e}")

    def get_task_uuid_for_thread(self, thread_id: int):
        return self.thread_to_task.get(str(thread_id))

    def _task_content(self, task):
        priority_emoji = self._priority_emoji(task.colour)
        lines = [
            f"**Status:** {task.status}",
            f"**Priority:** {priority_emoji} {task.colour}",
            f"**Owner:** {task.owner or 'Unassigned'}",
            f"**Deadline:** {task.deadline_display or 'None'}",
            "",
            f"**Description:** {task.description or '*No description*'}",
        ]
        if task.url:
            lines.append(f"**URL:** {task.url}")

        # Add subtasks section with progress bar
        if task.subtasks:
            lines.append("")
            lines.append(f"**Progress:** {task.progress_bar()}")
            lines.append("")
            lines.append("**Sub-tasks:**")
            for idx, subtask in enumerate(task.subtasks, 1):
                checkbox = "✅" if subtask.get('completed', False) else "☐"
                subtask_id = subtask.get('id', idx)
                lines.append(
                    f"{checkbox} {subtask_id}. {subtask.get('name', 'Unnamed subtask')}")
                if subtask.get('description'):
                    lines.append(f"   📝 {subtask.get('description')}")
                if subtask.get('url'):
                    lines.append(f"   🔗 {subtask.get('url')}")

        return "\n".join(lines)

    def _get_thread_name(self, task):
        """Generate forum thread name with priority emoji prefix for search filtering."""
        return f"{self._priority_emoji(task.colour)} {task.name}"

    def _task_sort_key(self, task):
        """Sort key for forum sync ordering without priority/status weighting."""
        return (task.order, task.name.lower())

    async def sync_from_database(self):
        if not self._bot or Settings.TASK_FORUM_CHANNEL is None:
            return

        # Reload mappings from database to avoid race conditions when multiple
        # service instances (modal/button handlers) create threads concurrently
        self._load_mappings()

        forum_channel = self._bot.get_channel(Settings.TASK_FORUM_CHANNEL)
        if not isinstance(forum_channel, discord.ForumChannel):
            logger.warning(
                f"Channel {Settings.TASK_FORUM_CHANNEL} is not a forum channel")
            return

        from services.task_service import TaskService
        from discord_ui.buttons import TaskView
        task_service = TaskService()
        tasks = task_service.get_all_tasks()
        tasks = sorted(tasks, key=self._task_sort_key)

        # Build a lookup of all active forum threads keyed by thread id for fast access.
        # This avoids relying solely on get_channel (which skips uncached threads).
        live_threads: dict[int, discord.Thread] = {
            t.id: t for t in forum_channel.threads
        }

        # Also pull threads visible from the guild's active-thread list.
        # fetch_active_threads exists in discord.py 2.x but is absent from Pylance stubs;
        # use getattr to avoid a false-positive reportAttributeAccessIssue.
        try:
            _fetch = getattr(forum_channel.guild, "fetch_active_threads", None)
            active_threads = await _fetch() if _fetch else []
            for t in active_threads:
                if t.parent_id == forum_channel.id:
                    live_threads[t.id] = t
        except Exception as e:
            logger.warning(f"Could not enumerate active guild threads: {e}")

        # Build a fast uuid->task lookup for the reverse-scan step below.
        uuid_to_task = {(t.uuid or t.id or t.name): t for t in tasks}

        mappings_changed = False

        for task in tasks:
            # Keep migration-safe fallback for legacy tasks while UUID backfill propagates.
            task_uuid = task.uuid or task.id or task.name
            if not task.uuid:
                logger.warning(
                    f"Task '{task.name}' missing UUID during forum sync; using legacy fallback key.")
            thread = None
            thread_id = self.task_to_thread.get(task_uuid)

            # Migrate old mapping keys (name/id) to UUID to avoid duplicate thread creation.
            if not thread_id:
                for legacy_key in [task.id, task.name]:
                    if legacy_key and legacy_key in self.task_to_thread:
                        thread_id = self.task_to_thread.pop(legacy_key)
                        self.task_to_thread[task_uuid] = thread_id
                        self.thread_to_task[str(thread_id)] = task_uuid
                        mappings_changed = True
                        break

            if thread_id:
                thread = live_threads.get(int(thread_id))
                if not isinstance(thread, discord.Thread):
                    # Fall back to a direct API fetch for uncached threads.
                    try:
                        thread = await self._bot.fetch_channel(int(thread_id))
                    except Exception as e:
                        logger.warning(
                            f"Could not fetch thread {thread_id} for task '{task.name}': {e}")
                        thread = None

            # If the task is complete, hide its forum thread and skip it.
            if task.status == "Complete":
                removed = False
                if isinstance(thread, discord.Thread):
                    try:
                        await thread.delete()
                        logger.info(
                            f"Deleted forum thread for completed task '{task.name}' ({task_uuid})")
                        removed = True
                    except discord.Forbidden:
                        # Fall back to archiving + locking so the thread disappears
                        # from the default forum view even without Manage Threads.
                        try:
                            await thread.edit(archived=True, locked=True)
                            logger.info(
                                f"Archived forum thread for completed task '{task.name}' ({task_uuid})")
                            removed = True
                        except Exception as archive_err:
                            logger.warning(
                                f"Could not delete or archive thread for completed task '{task.name}': "
                                f"{archive_err}. Grant Manage Threads to the bot.")
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete thread for completed task '{task.name}': {e}")
                elif thread_id:
                    # Mapping existed but thread could not be found (deleted externally?).
                    # Treat as successfully removed so we clean up the stale mapping.
                    removed = True
                    logger.debug(
                        f"Thread {thread_id} for completed task '{task.name}' no longer exists; "
                        "cleaning stale mapping.")
                # else: no mapping and no thread — nothing to do.

                # Only clear the mapping when the thread was actually removed.
                if removed:
                    self.task_to_thread.pop(task_uuid, None)
                    if thread_id:
                        self.thread_to_task.pop(str(thread_id), None)
                    mappings_changed = True
                continue

            # Build a persistent TaskView for this task and register it so button
            # interactions survive bot restarts.
            task_view = TaskView(task_uuid=task_uuid,
                                 subtasks=task.subtasks or [])
            self._bot.add_view(task_view)

            if not isinstance(thread, discord.Thread):
                thread_name = self._get_thread_name(task)
                created = await forum_channel.create_thread(
                    name=thread_name,
                    content=self._task_content(task),
                    view=task_view,
                )
                thread = created.thread
                self.task_to_thread[task_uuid] = str(thread.id)
                self.thread_to_task[str(thread.id)] = task_uuid
                mappings_changed = True
                logger.info(
                    f"Created forum thread for task '{task.name}' ({task_uuid})")
                continue

            thread_name = self._get_thread_name(task)
            if thread.name != thread_name:
                try:
                    await thread.edit(name=thread_name)
                except discord.Forbidden:
                    logger.warning(
                        "Missing permission to rename forum posts. Grant Manage Threads to keep names synced.")
                except Exception as e:
                    logger.warning(
                        f"Failed to update thread metadata for {thread.id}: {e}")

            # Keep latest task snapshot in thread starter message where possible
            content = self._task_content(task)
            try:
                starter_message = await thread.fetch_message(thread.id)
                has_components = bool(starter_message.components)

                # Detect view layout changes (e.g. new buttons added) by
                # comparing expected custom_ids against those on the message.
                expected_ids = {
                    item.custom_id
                    for item in task_view.children
                    if hasattr(item, 'custom_id') and item.custom_id
                }
                actual_ids = set()
                for row in starter_message.components:
                    for child in row.children:
                        if hasattr(child, 'custom_id') and child.custom_id:
                            actual_ids.add(child.custom_id)
                view_changed = expected_ids != actual_ids

                if starter_message.content != content or not has_components or view_changed:
                    await starter_message.edit(content=content, view=task_view)
            except Exception:
                # Fallback: post one sync snapshot if starter message isn't accessible
                await thread.send(content, view=task_view)

        # Reverse-scan: delete any live forum threads whose mapped task is now Complete
        # (catches threads that slipped through the main loop due to missing/stale mappings).
        for thread_id_int, thread in list(live_threads.items()):
            mapped_uuid = self.thread_to_task.get(str(thread_id_int))
            if not mapped_uuid:
                continue
            mapped_task = uuid_to_task.get(mapped_uuid)
            if mapped_task and mapped_task.status == "Complete":
                removed = False
                try:
                    await thread.delete()
                    logger.info(
                        f"Reverse-scan: deleted forum thread {thread_id_int} "
                        f"for completed task '{mapped_task.name}'")
                    removed = True
                except discord.Forbidden:
                    try:
                        await thread.edit(archived=True, locked=True)
                        logger.info(
                            f"Reverse-scan: archived forum thread {thread_id_int} "
                            f"for completed task '{mapped_task.name}'")
                        removed = True
                    except Exception as archive_err:
                        logger.warning(
                            f"Reverse-scan: could not delete or archive thread {thread_id_int}: "
                            f"{archive_err}")
                except Exception as e:
                    logger.warning(
                        f"Reverse-scan: failed to delete thread {thread_id_int}: {e}")
                if removed:
                    self.task_to_thread.pop(mapped_uuid, None)
                    self.thread_to_task.pop(str(thread_id_int), None)
                    mappings_changed = True

        # Orphan cleanup: remove threads for tasks that were deleted externally
        # (e.g. via the web app). These tasks no longer appear in the DB at all,
        # so the main loop above never touches their threads.
        task_uuids_in_db = set(uuid_to_task.keys())
        for mapped_uuid, mapped_thread_id in list(self.task_to_thread.items()):
            if mapped_uuid in task_uuids_in_db:
                continue
            # This mapped task no longer exists in the DB — clean up its thread.
            orphan_thread = live_threads.get(int(mapped_thread_id))
            if not orphan_thread:
                try:
                    orphan_thread = await self._bot.fetch_channel(int(mapped_thread_id))
                except Exception:
                    orphan_thread = None

            removed = False
            if isinstance(orphan_thread, discord.Thread):
                try:
                    await orphan_thread.delete()
                    logger.info(
                        f"Orphan cleanup: deleted thread {mapped_thread_id} "
                        f"for externally-removed task '{mapped_uuid}'")
                    removed = True
                except discord.Forbidden:
                    try:
                        await orphan_thread.edit(archived=True, locked=True)
                        logger.info(
                            f"Orphan cleanup: archived thread {mapped_thread_id} "
                            f"for externally-removed task '{mapped_uuid}'")
                        removed = True
                    except Exception as archive_err:
                        logger.warning(
                            f"Orphan cleanup: could not delete/archive thread "
                            f"{mapped_thread_id}: {archive_err}")
                except Exception as e:
                    logger.warning(
                        f"Orphan cleanup: failed to delete thread "
                        f"{mapped_thread_id}: {e}")
            else:
                # Thread already gone — just clean up the stale mapping.
                removed = True
                logger.debug(
                    f"Orphan cleanup: thread {mapped_thread_id} for task "
                    f"'{mapped_uuid}' no longer exists; removing stale mapping.")

            if removed:
                self.task_to_thread.pop(mapped_uuid, None)
                self.thread_to_task.pop(str(mapped_thread_id), None)
                mappings_changed = True

        # Persist mapping changes once at the end to avoid redundant writes.
        if mappings_changed:
            self._save_mappings()

    async def drain_log_events(self, username: str):
        """Drain pending log events from the database and dispatch to logging service."""
        if not self._db:
            return
        try:
            events = self._db.get_pending_log_events(username)
            if not events:
                return

            from services.logging_service import get_logging_service
            log_svc = get_logging_service()

            for event in events:
                try:
                    etype = event.get("event_type", "")
                    source = event.get("source", "External")
                    task_name = event.get("task_name", "Unknown")

                    if etype == "task_created":
                        await log_svc.log_task_created_externally(
                            source=source,
                            task_name=task_name,
                            task_after=event.get("after", {}),
                        )
                    elif etype == "task_updated":
                        await log_svc.log_task_updated_externally(
                            source=source,
                            task_name=task_name,
                            before=event.get("before", {}),
                            after=event.get("after", {}),
                        )
                    elif etype == "task_deleted":
                        await log_svc.log_task_deleted_externally(
                            source=source,
                            task_name=task_name,
                        )
                    elif etype == "subtask_added":
                        await log_svc.log_subtask_added_externally(
                            source=source,
                            task_name=task_name,
                            subtask=event.get("subtask", {}),
                        )
                    elif etype == "subtask_edited":
                        await log_svc.log_subtask_edited_externally(
                            source=source,
                            task_name=task_name,
                            subtask_id=event.get("subtask_id", 0),
                            before=event.get("before", {}),
                            after=event.get("after", {}),
                        )
                    elif etype == "subtask_toggled":
                        await log_svc.log_subtask_toggled_externally(
                            source=source,
                            task_name=task_name,
                            subtask_id=event.get("subtask_id", 0),
                            subtask_name=event.get("subtask", {}).get("name", "Unknown"),
                            completed=event.get("subtask", {}).get("completed", False),
                        )
                    elif etype == "subtask_deleted":
                        await log_svc.log_subtask_deleted_externally(
                            source=source,
                            task_name=task_name,
                            subtask_id=event.get("subtask_id", 0),
                            subtask_name=event.get("subtask", {}).get("name", "Unknown"),
                        )
                    else:
                        logger.warning(f"Unknown log event type: {etype}")
                except Exception as exc:
                    logger.warning(f"Failed to process log event {event.get('id', '?')}: {exc}")

            self._db.clear_pending_log_events(username)
            logger.debug(f"Drained {len(events)} pending log event(s) for user {username}")
        except Exception as e:
            logger.warning(f"Error draining log events: {e}")

    async def handle_thread_rename(self, thread: discord.Thread):
        """Sync thread title changes back to database task name"""
        task_uuid = self.get_task_uuid_for_thread(thread.id)
        if not task_uuid:
            return
        thread_name = thread.name
        for emoji in set(self.PRIORITY_EMOJIS.values()):
            prefix = f"{emoji} "
            if thread_name.startswith(prefix):
                thread_name = thread_name[len(prefix):]
                break
        from services.task_service import TaskService
        from services.logging_service import get_logging_service
        task_service = TaskService()
        old_task = await task_service.get_task_by_uuid(task_uuid)
        old_name = old_task.name if old_task else task_uuid
        await task_service.update_task_name_by_uuid(task_uuid, thread_name)
        if old_name != thread_name:
            await get_logging_service().log_task_renamed(
                old_name=old_name,
                new_name=thread_name,
            )

    async def update_description_for_thread(self, thread_id: int, description: str):
        task_uuid = self.get_task_uuid_for_thread(thread_id)
        if not task_uuid:
            raise ValueError("This thread is not linked to a task")
        from services.task_service import TaskService
        task_service = TaskService()
        await task_service.update_task_description_by_uuid(task_uuid, description)
