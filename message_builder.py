from datetime import datetime


def build_header():
    # prepare heading
    heading = f"{datetime.now()}\n"
    heading += "Welcome to today's Yfrit's Televops Daily Meeting!\n\n"

    return heading


def build_waiting():
    working_text = "Working on daily request..."

    return working_text


def build_scope(scope, effort):
    # send scope and effort info
    completed = "{:.2f}".format(100 * scope["completed"])
    sprint_percentage = "{:.2f}".format(100 *
                                        effort["sprint_percentage_effort"])
    epic_percentage = "{:.2f}".format(100 * effort["epic_percentage_effort"])
    capacity_percentage = "{:.2f}".format(100 *
                                          effort["epic_velocity_percentage"])
    blocked_effort = effort["blocked_effort"]

    # present body
    body = "Current iteration:\n"
    body += "```\n"
    body += f"├── Sprint Stories/Bugs: {scope['done']}/{scope['total']} ({completed}%)\n"  # noqa
    body += "├── Effort\n"
    body += f"│   ├── Sprint Progress: {effort['sprint_completed_effort']}/{effort['sprint_total_effort']} work days completed ({sprint_percentage}%)\n"  # noqa
    body += f"│   ├── Epic Progress: {effort['epic_completed_effort']}/{effort['epic_total_effort']} work days completed ({epic_percentage}%)\n"  # noqa
    body += f"│   ├── Epic Velocity: {effort['epic_remaining_effort']}/{effort['remaining_work_days']} work days remaining ({capacity_percentage}%)\n"  # noqa
    body += f"│   ├── Blocked: {blocked_effort} work days\n"
    body += f"│   ├── Work Days Per Week: {effort['work_days_per_week']}\n"
    body += f"│   ├── Developers: {effort['num_developers']}\n"
    body += f"│   ├── Sprint Capacity: {effort['sprint_capacity']}\n"
    body += f"├── Increased Scope: {scope['increased_scope']}\n"
    body += f"├── Projected Date: {scope['projected_date']}/{scope['release_date']}\n"  # noqa
    body += "```" + "\n"

    return body


def build_tasks(fetched_tasks):
    task_map = {}
    for owner, tasks in fetched_tasks.items():
        if owner not in task_map:
            task_map[owner] = {}
        for task in tasks:
            parent = task.parent.id
            if parent not in task_map[owner]:
                task_map[owner][parent] = [task]
            else:
                task_map[owner][parent].append(task)

    # sort parents by id
    for owner, work_items in task_map.items():
        task_map[owner] = dict(sorted(work_items.items()))

    # sort tasks by id
    for owner, work_items in task_map.items():
        for parent, tasks in work_items.items():
            task_map[owner][parent] = sorted(tasks, key=lambda x: x.id)

    # sort owners by name
    task_map = dict(sorted(task_map.items()))

    # present body tasks info
    body = ""
    for owner, work_items in task_map.items():
        body += owner + " is working on:\n"
        body += "```\n"
        if work_items:
            for parent_id, tasks in work_items.items():
                parent = tasks[0].parent  # all tasks have the same parent
                parent_effort = f'- ({parent.effort} days)' if parent.effort else ''  # noqa
                blocked = '[BLOCKED] ' if parent.blocked else ''
                body += f"├── {blocked}{parent_id}. {parent.name} {parent_effort}"  # noqa
                body += "\n"
                for task in tasks:
                    body += f"│   ├── {task.id}. {task.name} - ({task.state})"  # noqa
                    body += "\n"
        else:
            body += "No tasks in progress.\n"
        body += "```" + "\n"
    body += "Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!"  # noqa

    return body


def build_error(traceback):
    body = "Could not fetch content from Azure Devops. Error trace: \n"
    body += "```" + "\n"
    body += traceback
    body += "```" + "\n"
    body += "Check the Yfrit Televops environment for more information."

    return body
