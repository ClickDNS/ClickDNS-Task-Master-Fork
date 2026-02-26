"""
Discord channel logging service for human-readable audit logs.

Sends structured embeds to a configurable LOG_CHANNEL whenever a user
performs an action through the bot (task configure, subtask add/edit/
toggle/delete, task rename).
"""
import logging
import discord
from datetime import datetime, timezone
from typing import Optional, Union

from services.paste_service import upload_to_paste

logger = logging.getLogger(__name__)

# Maximum characters shown for description fields in log embeds.
_MAX_DESCRIPTION_PREVIEW = 512
# Discord hard limit for embed field values.
_MAX_FIELD_VALUE = 1024
# Threshold above which we push to koda-paste instead of inline.
_PASTE_THRESHOLD = 500


def _trunc(value: str, limit: int = _MAX_FIELD_VALUE) -> str:
    """Truncate a string to fit within Discord's embed field value limit."""
    if not value:
        return value
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _format_diff_value(old_val: str, new_val: str, field_name: str = "Field", task_name: str = "") -> str:
    """Format a before/after diff. If the combined text exceeds _PASTE_THRESHOLD,
    upload the full diff to koda-paste and return a link; otherwise return inline text."""
    inline = f"**Before:** {old_val}\n**After:** {new_val}"
    if len(inline) <= _PASTE_THRESHOLD:
        return inline

    # Upload full diff to koda-paste
    paste_content = f"Task: {task_name}\nField: {field_name}\n\n--- Before ---\n{old_val}\n\n--- After ---\n{new_val}"
    paste_url = upload_to_paste(paste_content, title=f"{task_name} — {field_name} diff")
    if paste_url:
        preview_old = old_val[:80] + "…" if len(old_val) > 80 else old_val
        preview_new = new_val[:80] + "…" if len(new_val) > 80 else new_val
        return f"**Before:** {preview_old}\n**After:** {preview_new}\n🔗 [Full diff]({paste_url})"
    else:
        return _trunc(inline)


_LOG_COLORS = {
    "create": discord.Color.green(),
    "update": discord.Color.blue(),
    "delete": discord.Color.red(),
    "rename": discord.Color.gold(),
    "toggle": discord.Color.purple(),
}


class LoggingService:
    """Sends human-readable audit-log embeds to a configured Discord channel."""

    def __init__(self):
        self._bot = None

    def set_bot(self, bot):
        self._bot = bot

    async def _send_log(self, embed: discord.Embed):
        from config.settings import Settings
        if not self._bot or not Settings.LOG_CHANNEL:
            return
        try:
            channel = self._bot.get_channel(Settings.LOG_CHANNEL)
            if channel:
                await channel.send(embed=embed)
            else:
                logger.warning(
                    f"LOG_CHANNEL {Settings.LOG_CHANNEL} not found or not cached.")
        except Exception as exc:
            logger.warning(f"Failed to send audit log to channel: {exc}")

    def _make_embed(
        self,
        title: str,
        color: discord.Color,
        actor: Optional[Union[discord.User, discord.Member]] = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        if actor:
            embed.set_footer(
                text=f"{actor.display_name} (@{actor.name})",
                icon_url=str(
                    actor.display_avatar.url) if actor.display_avatar else None,
            )
        return embed

    async def log_task_created(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        task: dict,
    ):
        """Log a new task being created."""
        embed = self._make_embed(
            f"✅ Task Created: **{task_name}**",
            _LOG_COLORS["create"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        if task.get("owner"):
            embed.add_field(name="Owner", value=task["owner"], inline=True)
        if task.get("deadline"):
            embed.add_field(name="Deadline",
                            value=task["deadline"], inline=True)
        if task.get("description"):
            embed.add_field(
                name="Description",
                value=task["description"][:_MAX_DESCRIPTION_PREVIEW],
                inline=False,
            )
        if task.get("url"):
            embed.add_field(name="URL", value=_trunc(
                task["url"]), inline=False)
        await self._send_log(embed)

    async def log_task_configured(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        before: dict,
        after: dict,
    ):
        """Log task field changes with a before/after diff.

        *before* and *after* are dicts with keys:
        status, priority, owner, deadline, description, url.
        Only changed fields are shown.
        """
        field_labels = {
            "status": "Status",
            "priority": "Priority",
            "owner": "Owner",
            "deadline": "Deadline",
            "description": "Description",
            "url": "URL",
        }
        changes = [
            (label, before.get(key) or "*empty*", after.get(key) or "*empty*")
            for key, label in field_labels.items()
            if before.get(key) != after.get(key)
        ]
        if not changes:
            return

        embed = self._make_embed(
            f"⚙️ Task Configured: **{task_name}**",
            _LOG_COLORS["update"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        for label, old_val, new_val in changes:
            embed.add_field(
                name=label,
                value=_format_diff_value(old_val, new_val, label, task_name),
                inline=True,
            )
        await self._send_log(embed)

    async def log_task_renamed(
        self,
        old_name: str,
        new_name: str,
        actor: Optional[Union[discord.User, discord.Member]] = None,
    ):
        """Log a task rename (e.g. from a thread title edit)."""
        embed = self._make_embed(
            "✏️ Task Renamed", _LOG_COLORS["rename"], actor)
        embed.add_field(name="Before", value=_trunc(old_name), inline=True)
        embed.add_field(name="After", value=_trunc(new_name), inline=True)
        if actor:
            embed.add_field(name="By", value=actor.mention, inline=False)
        await self._send_log(embed)

    # ------------------------------------------------------------------
    # External-source logging (events from Web App / Desktop App / etc.)
    # ------------------------------------------------------------------

    def _make_external_embed(
        self,
        title: str,
        color: discord.Color,
        source: str,
    ) -> discord.Embed:
        """Create an embed for an externally-triggered event."""
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"via {source}")
        return embed

    async def log_task_created_externally(
        self,
        source: str,
        task_name: str,
        task_after: dict,
    ):
        """Log a task created outside Discord."""
        embed = self._make_external_embed(
            f"✅ Task Created: **{task_name}**",
            _LOG_COLORS["create"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        if task_after.get("owner"):
            embed.add_field(
                name="Owner", value=task_after["owner"], inline=True)
        if task_after.get("deadline"):
            embed.add_field(name="Deadline",
                            value=task_after["deadline"], inline=True)
        if task_after.get("description"):
            embed.add_field(
                name="Description",
                value=task_after["description"][:_MAX_DESCRIPTION_PREVIEW],
                inline=False,
            )
        if task_after.get("url"):
            embed.add_field(name="URL", value=_trunc(
                task_after["url"]), inline=False)
        await self._send_log(embed)

    async def log_task_updated_externally(
        self,
        source: str,
        task_name: str,
        before: dict,
        after: dict,
    ):
        """Log task field changes from an external source with before/after diff."""
        field_labels = {
            "status": "Status",
            "priority": "Priority",
            "owner": "Owner",
            "deadline": "Deadline",
            "description": "Description",
            "url": "URL",
            "name": "Name",
        }
        changes = [
            (label, before.get(key) or "*empty*", after.get(key) or "*empty*")
            for key, label in field_labels.items()
            if before.get(key) != after.get(key)
        ]
        if not changes:
            return

        embed = self._make_external_embed(
            f"⚙️ Task Configured: **{task_name}**",
            _LOG_COLORS["update"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        for label, old_val, new_val in changes:
            embed.add_field(
                name=label,
                value=_format_diff_value(old_val, new_val, label, task_name),
                inline=True,
            )
        await self._send_log(embed)

    async def log_task_deleted_externally(
        self,
        source: str,
        task_name: str,
    ):
        """Log a task deletion from an external source."""
        embed = self._make_external_embed(
            f"🗑️ Task Deleted: **{task_name}**",
            _LOG_COLORS["delete"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        await self._send_log(embed)

    async def log_subtask_added_externally(
        self,
        source: str,
        task_name: str,
        subtask: dict,
    ):
        """Log a subtask added from an external source."""
        embed = self._make_external_embed(
            f"➕ Sub-task Added to **{task_name}**",
            _LOG_COLORS["create"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        embed.add_field(
            name="Sub-task", value=_trunc(subtask.get("name", "Unnamed")), inline=True)
        if subtask.get("description"):
            embed.add_field(
                name="Description",
                value=subtask["description"][:_MAX_DESCRIPTION_PREVIEW],
                inline=False,
            )
        if subtask.get("url"):
            embed.add_field(name="URL", value=_trunc(
                subtask["url"]), inline=False)
        await self._send_log(embed)

    async def log_subtask_edited_externally(
        self,
        source: str,
        task_name: str,
        subtask_id: int,
        before: dict,
        after: dict,
    ):
        """Log subtask field edits from an external source with before/after diff."""
        field_labels = {
            "name": "Name",
            "description": "Description",
            "url": "URL",
        }
        changes = [
            (label, before.get(key) or "*empty*", after.get(key) or "*empty*")
            for key, label in field_labels.items()
            if before.get(key) != after.get(key)
        ]
        if not changes:
            return

        embed = self._make_external_embed(
            f"✏️ Sub-task #{subtask_id} Edited on **{task_name}**",
            _LOG_COLORS["update"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        for label, old_val, new_val in changes:
            embed.add_field(
                name=label,
                value=_format_diff_value(old_val, new_val, label, task_name),
                inline=True,
            )
        await self._send_log(embed)

    async def log_subtask_toggled_externally(
        self,
        source: str,
        task_name: str,
        subtask_id: int,
        subtask_name: str,
        completed: bool,
    ):
        """Log a subtask completion toggle from an external source."""
        status = "✅ Complete" if completed else "☐ Incomplete"
        embed = self._make_external_embed(
            f"🔄 Sub-task #{subtask_id} Toggled on **{task_name}**",
            _LOG_COLORS["toggle"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        embed.add_field(name="Sub-task",
                        value=_trunc(subtask_name), inline=True)
        embed.add_field(name="New Status", value=status, inline=True)
        await self._send_log(embed)

    async def log_subtask_deleted_externally(
        self,
        source: str,
        task_name: str,
        subtask_id: int,
        subtask_name: str,
    ):
        """Log a subtask deletion from an external source."""
        embed = self._make_external_embed(
            f"🗑️ Sub-task #{subtask_id} Deleted from **{task_name}**",
            _LOG_COLORS["delete"],
            source,
        )
        embed.add_field(name="By", value=source, inline=False)
        embed.add_field(name="Sub-task",
                        value=_trunc(subtask_name), inline=False)
        await self._send_log(embed)

    async def log_subtask_added(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        subtask: dict,
    ):
        """Log a new subtask being added to a task."""
        embed = self._make_embed(
            f"➕ Sub-task Added to **{task_name}**",
            _LOG_COLORS["create"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        embed.add_field(
            name="Sub-task", value=_trunc(subtask.get("name", "Unnamed")), inline=True)
        if subtask.get("description"):
            embed.add_field(
                name="Description",
                value=subtask["description"][:_MAX_DESCRIPTION_PREVIEW],
                inline=False,
            )
        if subtask.get("url"):
            embed.add_field(name="URL", value=_trunc(
                subtask["url"]), inline=False)
        await self._send_log(embed)

    async def log_subtask_edited(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        subtask_id: int,
        before: dict,
        after: dict,
    ):
        """Log subtask field edits with a before/after diff.

        *before* and *after* are dicts with keys: name, description, url.
        """
        field_labels = {
            "name": "Name",
            "description": "Description",
            "url": "URL",
        }
        changes = [
            (label, before.get(key) or "*empty*", after.get(key) or "*empty*")
            for key, label in field_labels.items()
            if before.get(key) != after.get(key)
        ]
        if not changes:
            return

        embed = self._make_embed(
            f"✏️ Sub-task #{subtask_id} Edited on **{task_name}**",
            _LOG_COLORS["update"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        for label, old_val, new_val in changes:
            embed.add_field(
                name=label,
                value=_format_diff_value(old_val, new_val, label, task_name),
                inline=True,
            )
        await self._send_log(embed)

    async def log_subtask_toggled(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        subtask_id: int,
        subtask_name: str,
        completed: bool,
    ):
        """Log a subtask completion toggle."""
        status = "✅ Complete" if completed else "☐ Incomplete"
        embed = self._make_embed(
            f"🔄 Sub-task #{subtask_id} Toggled on **{task_name}**",
            _LOG_COLORS["toggle"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        embed.add_field(name="Sub-task",
                        value=_trunc(subtask_name), inline=True)
        embed.add_field(name="New Status", value=status, inline=True)
        await self._send_log(embed)

    async def log_task_deleted(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
    ):
        """Log a task deletion."""
        embed = self._make_embed(
            f"🗑️ Task Deleted: **{task_name}**",
            _LOG_COLORS["delete"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        await self._send_log(embed)

    async def log_subtask_deleted(
        self,
        actor: Union[discord.User, discord.Member],
        task_name: str,
        subtask_id: int,
        subtask_name: str,
    ):
        """Log a subtask deletion."""
        embed = self._make_embed(
            f"🗑️ Sub-task #{subtask_id} Deleted from **{task_name}**",
            _LOG_COLORS["delete"],
            actor,
        )
        embed.add_field(name="By", value=actor.mention, inline=False)
        embed.add_field(name="Sub-task",
                        value=_trunc(subtask_name), inline=False)
        await self._send_log(embed)


# ---------------------------------------------------------------------------
# Module-level singleton – initialised once and shared across all importers.
# ---------------------------------------------------------------------------

_logging_service: Optional[LoggingService] = None


def get_logging_service() -> LoggingService:
    """Return (creating if necessary) the module-level LoggingService singleton."""
    global _logging_service
    if _logging_service is None:
        _logging_service = LoggingService()
    return _logging_service
