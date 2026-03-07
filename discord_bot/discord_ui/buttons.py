"""
Discord button components for task interactions
"""
import asyncio
import logging
import discord
from discord.ui import Button, View
from config.settings import Settings


logger = logging.getLogger(__name__)


async def _auto_delete(msg, delay: float):
    """Delete a message after a delay (background task)."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception as e:
        logger.warning("Failed to auto-delete ephemeral button message: %s", e)


class ConfirmationButtons(View):
    """Generic confirmation buttons"""

    def __init__(self, timeout=60, requester_id: int = None):
        super().__init__(timeout=timeout)
        self.value = None
        self.requester_id = requester_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.requester_id is not None and interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the user who requested this action can confirm it.",
                ephemeral=True,
                delete_after=Settings.EPHEMERAL_DELETE_AFTER,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.value = False
        await interaction.response.defer()
        self.stop()


class ConfigureTaskButton(discord.ui.Button):
    """Button that opens the Configure Task modal for the thread's task."""

    def __init__(self, task_uuid: str):
        super().__init__(
            label="⚙️ Configure Task",
            style=discord.ButtonStyle.primary,
            custom_id=f"tm:configure:{task_uuid}",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from services.task_service import TaskService
        from discord_ui.modals import ConfigureTaskModal

        task_service = TaskService()
        task = await task_service.get_task_by_uuid(self.view.task_uuid)
        if not task:
            await interaction.response.send_message(
                "❌ Task not found.",
                ephemeral=True,
                delete_after=Settings.EPHEMERAL_DELETE_AFTER,
            )
            return

        await interaction.response.send_modal(ConfigureTaskModal(
            task_uuid=self.view.task_uuid,
            task_name=task.name,
            current_status=task.status,
            current_priority=task.colour,
            current_owner=task.owner or "",
            current_deadline=task.deadline or "",
            current_description=task.description or "",
            current_url=task.url or "",
        ))


class AddSubtaskButton(discord.ui.Button):
    """Button that opens the Add Sub-task modal."""

    def __init__(self, task_uuid: str):
        super().__init__(
            label="➕ Add Sub-task",
            style=discord.ButtonStyle.secondary,
            custom_id=f"tm:add_subtask:{task_uuid}",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from discord_ui.modals import AddSubtaskModal
        await interaction.response.send_modal(AddSubtaskModal(self.view.task_uuid))


class SubtaskSelect(discord.ui.Select):
    """Dropdown listing all sub-tasks for the task; selecting one opens management options."""

    def __init__(self, task_uuid: str, subtasks: list):
        options = []
        for st in subtasks[:25]:
            status_emoji = "✅" if st.get("completed") else "⬜"
            label = f"#{st.get('id', '?')} {st.get('name', 'Unnamed')}"[:100]
            options.append(discord.SelectOption(
                label=label,
                value=str(st.get("id")),
                emoji=status_emoji,
            ))
        super().__init__(
            placeholder="Select a sub-task to manage…",
            options=options,
            custom_id=f"tm:subtask_select:{task_uuid}",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        subtask_id = int(self.values[0])
        task_uuid = self.view.task_uuid

        from services.task_service import TaskService
        task_service = TaskService()
        subtask = await task_service.get_subtask_by_id(task_uuid, subtask_id)

        if not subtask:
            msg = await interaction.followup.send(
                "❌ Sub-task not found.",
                ephemeral=True,
            )
            if Settings.EPHEMERAL_DELETE_AFTER:
                asyncio.create_task(_auto_delete(
                    msg, Settings.EPHEMERAL_DELETE_AFTER))
            return

        status = "✅ complete" if subtask.get("completed") else "☐ incomplete"
        view = SubtaskActionView(task_uuid, subtask_id, subtask)
        msg = await interaction.followup.send(
            f"Managing sub-task **#{subtask_id}: {subtask.get('name', 'Unnamed')}** — {status}",
            view=view,
            ephemeral=True,
        )
        if Settings.EPHEMERAL_DELETE_AFTER:
            asyncio.create_task(_auto_delete(
                msg, Settings.EPHEMERAL_DELETE_AFTER))


class SubtaskActionView(discord.ui.View):
    """Ephemeral view for managing an individual sub-task (edit / toggle / delete)."""

    def __init__(self, task_uuid: str, subtask_id: int, subtask: dict = None):
        super().__init__(timeout=60)
        self.task_uuid = task_uuid
        self.subtask_id = subtask_id
        self._subtask = subtask or {}

    async def _ensure_deferred(self, interaction: discord.Interaction):
        """Acknowledge interaction before long-running work."""
        if not interaction.response.is_done():
            await interaction.response.defer()

    async def _safe_edit_message(self, interaction: discord.Interaction, *, content: str, view=None):
        """Safely update the ephemeral interaction message regardless of response state."""
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(content=content, view=view)
            else:
                await interaction.response.edit_message(content=content, view=view)
        except discord.NotFound:
            try:
                msg = await interaction.followup.send(
                    content,
                    ephemeral=True,
                )
                if Settings.EPHEMERAL_DELETE_AFTER:
                    asyncio.create_task(_auto_delete(
                        msg, Settings.EPHEMERAL_DELETE_AFTER))
            except (discord.NotFound, discord.HTTPException) as exc:
                logger.warning(
                    "Unable to send fallback follow-up interaction message: %s", exc)
        except discord.HTTPException as exc:
            logger.warning("Failed to edit interaction message: %s", exc)

    async def _sync(self, interaction: discord.Interaction):
        """Trigger forum and dashboard sync after a change."""
        from config.settings import Settings
        from database.firebase_manager import DatabaseManager
        from services.forum_sync_service import ForumSyncService
        from services.dashboard_service import DashboardService

        if Settings.TASK_FORUM_CHANNEL:
            db_manager = DatabaseManager(
                use_firebase=not Settings.USE_LOCAL_STORAGE)
            forum_service = ForumSyncService()
            forum_service.set_bot(interaction.client)
            forum_service.set_database(db_manager)
            await forum_service.sync_from_database()

            dashboard_service = DashboardService()
            dashboard_service.set_bot(interaction.client)
            dashboard_service.set_database(db_manager)
            await dashboard_service.update_dashboard()

    @discord.ui.button(label="✏️ Edit Sub-task", style=discord.ButtonStyle.primary)
    async def edit_subtask(self, interaction: discord.Interaction, button: Button):
        from discord_ui.modals import ConfigureSubtaskModal
        await interaction.response.send_modal(ConfigureSubtaskModal(
            task_uuid=self.task_uuid,
            subtask_id=self.subtask_id,
            existing_subtask=self._subtask,
        ))

    @discord.ui.button(label="✅ Toggle Completion", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: Button):
        from services.task_service import TaskService
        from services.logging_service import get_logging_service
        task_service = TaskService()
        try:
            await self._ensure_deferred(interaction)
            subtask = await task_service.toggle_subtask_by_id(self.task_uuid, self.subtask_id)
            await self._sync(interaction)
            status = "complete" if subtask.get("completed") else "incomplete"

            # Audit log
            task = await task_service.get_task_by_uuid(self.task_uuid)
            task_name = task.name if task else self.task_uuid
            await get_logging_service().log_subtask_toggled(
                actor=interaction.user,
                task_name=task_name,
                subtask_id=self.subtask_id,
                subtask_name=subtask.get("name", "Unnamed"),
                completed=bool(subtask.get("completed")),
            )

            await self._safe_edit_message(
                interaction,
                content=f"✅ Sub-task #{self.subtask_id} marked {status}.",
                view=None,
            )
        except ValueError as e:
            await self._safe_edit_message(interaction, content=f"❌ {str(e)}", view=None)
        except Exception as e:
            logger.error("Failed toggling sub-task #%s: %s", self.subtask_id, e, exc_info=True)
            await self._safe_edit_message(
                interaction,
                content="❌ Something went wrong. Please try again or contact an admin.",
                view=None,
            )

    @discord.ui.button(label="🗑️ Delete Sub-task", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: Button):
        subtask_name = self._subtask.get("name", "Unnamed sub-task")
        confirm_view = ConfirmationButtons(
            timeout=45, requester_id=interaction.user.id)
        await self._safe_edit_message(
            interaction,
            content=f"⚠️ Confirm delete for sub-task #{self.subtask_id}: **{subtask_name}**?",
            view=confirm_view,
        )

        timed_out = await confirm_view.wait()
        if timed_out or confirm_view.value is None:
            await self._safe_edit_message(
                interaction,
                content="⌛ Delete request timed out.", view=None
            )
            return

        if not confirm_view.value:
            await self._safe_edit_message(interaction, content="❎ Delete cancelled.", view=None)
            return

        from services.task_service import TaskService
        from services.logging_service import get_logging_service
        task_service = TaskService()
        try:
            removed = await task_service.delete_subtask_by_id(self.task_uuid, self.subtask_id)
            await self._sync(interaction)

            # Audit log
            task = await task_service.get_task_by_uuid(self.task_uuid)
            task_name = task.name if task else self.task_uuid
            await get_logging_service().log_subtask_deleted(
                actor=interaction.user,
                task_name=task_name,
                subtask_id=self.subtask_id,
                subtask_name=removed.get("name", "Unnamed sub-task"),
            )

            await self._safe_edit_message(
                interaction,
                content=f"✅ Deleted sub-task #{self.subtask_id}: {removed.get('name', 'Unnamed sub-task')}.",
                view=None,
            )
        except Exception as e:
            logger.error("Failed deleting sub-task #%s: %s", self.subtask_id, e, exc_info=True)
            await self._safe_edit_message(
                interaction,
                content="❌ Something went wrong. Please try again or contact an admin.", view=None
            )


class DeleteTaskButton(discord.ui.Button):
    """Button that prompts for confirmation then deletes the task."""

    def __init__(self, task_uuid: str):
        super().__init__(
            label="🗑️ Delete Task",
            style=discord.ButtonStyle.danger,
            custom_id=f"tm:delete_task:{task_uuid}",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from services.task_service import TaskService
        from services.logging_service import get_logging_service

        task_service = TaskService()
        task = await task_service.get_task_by_uuid(self.view.task_uuid)
        if not task:
            await interaction.response.send_message(
                "❌ Task not found.",
                ephemeral=True,
                delete_after=Settings.EPHEMERAL_DELETE_AFTER,
            )
            return

        confirm_view = ConfirmationButtons(timeout=45, requester_id=interaction.user.id)
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete task **{task.name}**? This cannot be undone.",
            view=confirm_view,
            ephemeral=True,
        )

        timed_out = await confirm_view.wait()
        if timed_out or confirm_view.value is None:
            await interaction.edit_original_response(
                content="⌛ Delete request timed out.", view=None
            )
            return

        if not confirm_view.value:
            await interaction.edit_original_response(
                content="❎ Delete cancelled.", view=None
            )
            return

        task_name = task.name
        try:
            await task_service.delete_task_by_uuid(self.view.task_uuid)

            # Trigger forum and dashboard sync
            from config.settings import Settings as _Settings
            from database.firebase_manager import DatabaseManager
            from services.forum_sync_service import ForumSyncService
            from services.dashboard_service import DashboardService

            if _Settings.TASK_FORUM_CHANNEL:
                db_manager = DatabaseManager(use_firebase=not _Settings.USE_LOCAL_STORAGE)
                forum_service = ForumSyncService()
                forum_service.set_bot(interaction.client)
                forum_service.set_database(db_manager)
                await forum_service.sync_from_database()

                dashboard_service = DashboardService()
                dashboard_service.set_bot(interaction.client)
                dashboard_service.set_database(db_manager)
                await dashboard_service.update_dashboard()

            # Audit log
            await get_logging_service().log_task_deleted(
                actor=interaction.user,
                task_name=task_name,
            )

            await interaction.edit_original_response(
                content=f"✅ Task **{task_name}** has been deleted.",
                view=None,
            )
        except Exception as e:
            logger.error("Failed deleting task %s: %s", self.view.task_uuid, e, exc_info=True)
            await interaction.edit_original_response(
                content="❌ Something went wrong. Please try again or contact an admin.",
                view=None,
            )


class TaskView(discord.ui.View):
    """Persistent task-management view attached to a forum thread's starter message.

    Contains buttons for configuring the task and managing sub-tasks.
    Registered with ``bot.add_view()`` so interactions survive bot restarts.
    """

    def __init__(self, task_uuid: str, subtasks: list = None):
        super().__init__(timeout=None)
        self.task_uuid = task_uuid
        self.add_item(ConfigureTaskButton(task_uuid))
        self.add_item(AddSubtaskButton(task_uuid))
        self.add_item(DeleteTaskButton(task_uuid))
        if subtasks:
            self.add_item(SubtaskSelect(task_uuid, subtasks))


class CreateTaskButton(discord.ui.Button):
    """Button on the central dashboard that opens the Create Task modal."""

    def __init__(self):
        super().__init__(
            label="➕ Create Task",
            style=discord.ButtonStyle.success,
            custom_id="tm:create_task",
        )

    async def callback(self, interaction: discord.Interaction):
        from discord_ui.modals import CreateTaskModal
        await interaction.response.send_modal(CreateTaskModal())


class DashboardView(discord.ui.View):
    """Persistent view attached to the central dashboard message.

    Contains a button to create new tasks directly from Discord.
    Registered with ``bot.add_view()`` so interactions survive bot restarts.
    """

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CreateTaskButton())
