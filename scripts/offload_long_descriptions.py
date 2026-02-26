#!/usr/bin/env python3
"""
Sweep Task-Master tasks and subtasks; offload descriptions > DESCRIPTION_PASTE_THRESHOLD
to koda-paste and persist paste URLs in the database.

Run: python3 scripts/offload_long_descriptions.py
"""
import asyncio
import logging
from services.task_service import TaskService
from services.paste_service import offload_description, is_paste_url, DESCRIPTION_PASTE_THRESHOLD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("offload_migration")

async def main():
    ts = TaskService()
    tasks = ts.get_all_tasks()
    total_tasks = len(tasks)
    task_count = 0
    offloaded_tasks = 0
    offloaded_subtasks = 0
    failed = []

    logger.info(f"Found {total_tasks} tasks to scan for long descriptions")

    for task in tasks:
        task_count += 1
        logger.info(f"[{task_count}/{total_tasks}] Scanning task '{task.name}' (uuid={task.uuid})")

        # Task description
        desc = task.description or ""
        if desc and len(desc) > DESCRIPTION_PASTE_THRESHOLD and not is_paste_url(desc):
            logger.info(f"Task '{task.name}' description > {DESCRIPTION_PASTE_THRESHOLD} chars — offloading")
            try:
                new_desc = offload_description(desc, title=f"{task.name} — Description")
                if new_desc != desc:
                    await ts.update_task_description_by_uuid(task.uuid, new_desc)
                    offloaded_tasks += 1
                    logger.info(f"Offloaded task '{task.name}' to {new_desc}")
                else:
                    logger.warning(f"Offload attempt returned original text for task '{task.name}' — paste may be unreachable")
                    failed.append((task.uuid, 'task_description'))
            except Exception as e:
                logger.exception(f"Failed to offload description for task {task.uuid}: {e}")
                failed.append((task.uuid, 'task_description', str(e)))

        # Subtasks
        subtasks = getattr(task, 'subtasks', []) or []
        for st in subtasks:
            st_desc = st.get('description', '') or ''
            st_id = st.get('id')
            if st_desc and len(st_desc) > DESCRIPTION_PASTE_THRESHOLD and not is_paste_url(st_desc):
                logger.info(f"Offloading subtask #{st_id} for task '{task.name}'")
                try:
                    new_st_desc = offload_description(st_desc, title=f"{task.name} — Subtask #{st_id}")
                    if new_st_desc != st_desc:
                        await ts.upsert_subtask_by_id(task.uuid, st_id, st.get('name',''), new_st_desc, st.get('url',''))
                        offloaded_subtasks += 1
                        logger.info(f"Offloaded subtask #{st_id} for task '{task.name}' to {new_st_desc}")
                    else:
                        logger.warning(f"Offload attempt returned original text for subtask #{st_id} in task '{task.name}'")
                        failed.append((task.uuid, f'subtask:{st_id}'))
                except Exception as e:
                    logger.exception(f"Failed to offload subtask #{st_id} for task {task.uuid}: {e}")
                    failed.append((task.uuid, f'subtask:{st_id}', str(e)))

    logger.info(f"Done. Tasks scanned: {total_tasks}. Offloaded tasks: {offloaded_tasks}. Offloaded subtasks: {offloaded_subtasks}.")
    if failed:
        logger.warning(f"Some offloads failed: {failed}")

if __name__ == '__main__':
    asyncio.run(main())
