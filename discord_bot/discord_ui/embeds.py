"""
Discord embed builders for task display
"""
import discord
from typing import List, Optional
from database.task_model import Task
from datetime import datetime


def create_task_board_embed(tasks: List[Task], owner: Optional[str] = None, filter_status: Optional[str] = None) -> discord.Embed:
    """
    Create a comprehensive task board embed

    Args:
        tasks: List of tasks to display
        owner: Optional owner filter
        filter_status: Optional status filter (To Do, In Progress, Complete, or None for all)
    """
    # Filter tasks
    filtered_tasks = tasks
    if owner:
        filtered_tasks = [t for t in filtered_tasks if t.owner == owner]
    if filter_status and filter_status != "All":
        filtered_tasks = [
            t for t in filtered_tasks if t.status == filter_status]

    # Create embed
    embed = discord.Embed(
        title="📋 Task Master - Task Board",
        description=f"Displaying {len(filtered_tasks)} task(s)",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )

    # Group by importance
    priority_groups = {
        "Important":            [],
        "Moderately Important": [],
        "Low Importance":       [],
        "default":              [],
    }

    for task in filtered_tasks:
        group = task.colour if task.colour in priority_groups else "default"
        priority_groups[group].append(task)

    importance_labels = {
        "Important":            "High Importance",
        "Moderately Important": "Medium Importance",
        "Low Importance":       "Low Importance",
        "default":              "Default",
    }

    # Add fields for each importance group
    for priority, group_tasks in priority_groups.items():
        if not group_tasks:
            continue

        priority_label = importance_labels[priority]
        emoji = {
            "Important":            "🔴",
            "Moderately Important": "🟠",
            "Low Importance":       "🔵",
            "default":              "⚪",
        }.get(priority, "⚪")

        field_value = ""
        for task in group_tasks:
            status_emoji = task.status_emoji
            deadline_str = ""
            if task.deadline:
                deadline_str = f" • 📅 {task.deadline_display}"
                if task.is_overdue:
                    deadline_str = f" • ⚠️ **OVERDUE** {task.deadline_display}"

            owner_str = f" • 👤 {task.owner}" if task.owner else ""
            url_str = f" • [🔗 Link]({task.url})" if task.url else ""

            field_value += (f"{status_emoji} **{task.name}**\n"
                            f"    ↳ Status: {task.status}{deadline_str}{owner_str}{url_str}\n")

            if task.description:
                single_line_description = task.description.replace("\n", " ")
                desc_preview = (single_line_description[:200] + "..."
                                if len(single_line_description) > 200
                                else single_line_description)
                field_value += f"    ↳ 📝 {desc_preview}\n"

            field_value += "\n"

        embed.add_field(
            name=f"{emoji} {priority_label} ({len(group_tasks)})",
            value=field_value or "No tasks",
            inline=False
        )

    if not filtered_tasks:
        embed.add_field(
            name="No Tasks",
            value="No tasks match the current filter. Use the dropdown menu to change filters or add a new task!",
            inline=False
        )

    embed.set_footer(text="Last updated")

    return embed


def create_task_detail_embed(task: Task) -> discord.Embed:
    """Create detailed embed for a single task"""
    color_map = {
        "Important":            discord.Color.red(),
        "Moderately Important": discord.Color.gold(),
        "Low Importance":       discord.Color.blue(),
        "default":              discord.Color.greyple(),
    }

    embed = discord.Embed(
        title=f"{task.status_emoji} {task.name}",
        description=task.description or "*No description*",
        color=color_map.get(task.colour, discord.Color.greyple())
    )

    embed.add_field(name="Status", value=task.status, inline=True)
    importance_label_map = {
        "Important":            "High Importance",
        "Moderately Important": "Medium Importance",
        "Low Importance":       "Low Importance",
        "default":              "Default",
    }
    embed.add_field(
        name="Importance",
        value=importance_label_map.get(task.colour, task.colour),
        inline=True,
    )

    if task.deadline:
        deadline_display = task.deadline_display
        if task.is_overdue:
            deadline_display = f"⚠️ **OVERDUE** {task.deadline_display}"
        embed.add_field(name="Deadline", value=deadline_display, inline=True)

    if task.owner:
        embed.add_field(name="Owner", value=task.owner, inline=True)

    if task.url:
        embed.add_field(
            name="URL", value=f"[Click here]({task.url})", inline=True)

    return embed


def create_reminder_embed(task: Task) -> discord.Embed:
    """Create embed for task deadline reminder"""
    embed = discord.Embed(
        title="⏰ Task Deadline Reminder",
        description="You have a task approaching its deadline!",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )

    embed.add_field(name="Task", value=task.name, inline=False)
    embed.add_field(name="Deadline",
                    value=task.deadline_display or "None", inline=True)
    embed.add_field(name="Status", value=task.status, inline=True)

    if task.description:
        desc_preview = task.description[:100] + \
            "..." if len(task.description) > 100 else task.description
        embed.add_field(name="Description", value=desc_preview, inline=False)

    if task.url:
        embed.add_field(
            name="URL", value=f"[Click here]({task.url})", inline=False)

    return embed
