import json
import logging
import re
import sys
import traceback
from datetime import datetime

import telegram.ext
from telegram.ext import CommandHandler, Updater

from devops_client import Client
from environment import Environment

# load env
env = Environment()

# fetch updater and job queue
logging.info("Starting bot...")
updater = Updater(token=env.telegram_token, use_context=True)
dispatcher = updater.dispatcher

# set the collaborators and get the devops client
collaborators = []
try:
    with open('collaborators.json') as f:
        collaborators = json.load(f)
except FileNotFoundError:
    logging.error("Collaborators file not found.")
    sys.exit(1)

client = Client(collaborators)


def prepare_message(msg, hard_parse=False):
    if hard_parse:
        # hard parse is used for error messages
        msg = re.sub(r'([^\\])', r'\\\1', msg)

        # ignore markdown monospace character
        return msg.replace("\\`", "`")
    else:
        return msg.replace("-", "\-") \
                  .replace(".", "\.") \
                  .replace("(", "\(") \
                  .replace(")", "\)") \
                  .replace("!", "\!") # noqa


def validate_chat_id(chat_id):
    chat_id = str(chat_id)
    allowed_chat_ids = env.telegram_allowed_chat_ids
    if allowed_chat_ids:
        # if user set allowed chat ids, return True if chat_id is in the list
        return chat_id in allowed_chat_ids
    else:
        # if user didn't set allowed chat ids, return True (allow all)
        return True


# set the function command callback for the daily
def daily(update, context):
    # validate chat_id
    chat_id = update.message.chat_id
    if not validate_chat_id(chat_id):
        logging.warning(f"Chat ID {chat_id} is not allowed.")
        return

    # prepare heading
    heading = f"{datetime.now()}\n"
    heading += "Welcome to today's Yfrt's Televops Daily Meeting!\n\n"
    working_text = "Working on daily request..."
    msg = prepare_message(str(heading + working_text))

    hard_parse = False
    try:
        # send message to show api is working
        message = context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2)

        # fetch scope info for heading
        scope = client.get_current_scope()
        completed = "{:.2f}".format(100 * scope["completed"])
        effort = client.get_total_effort()
        sprint_percentage = "{:.2f}".format(100 *
                                            effort["sprint_percentage_effort"])
        epic_percentage = "{:.2f}".format(100 *
                                          effort["epic_percentage_effort"])
        capacity_percentage = "{:.2f}".format(
            100 * effort["epic_velocity_percentage"])

        # present heading
        body = "Current iteration:\n"
        body += "```\n"
        body += f"├── Sprint Stories/Bugs: {scope['done']}/{scope['total']} ({completed}%)\n"  # noqa
        body += f"├── Effort\n"  # noqa
        body += f"│   ├── Sprint Progress: {effort['sprint_completed_effort']}/{effort['sprint_total_effort']} work days completed ({sprint_percentage}%)\n"  # noqa
        body += f"│   ├── Epic Progress: {effort['epic_completed_effort']}/{effort['epic_total_effort']} work days completed ({epic_percentage}%)\n"  # noqa
        body += f"│   ├── Epic Velocity: {effort['epic_remaining_effort']}/{effort['remaining_work_days']} work days remaining ({capacity_percentage}%)\n"  # noqa
        body += f"│   ├── Work Days Per Week: {effort['work_days_per_week']}\n"  # noqa
        body += f"│   ├── Developers: {effort['num_developers']}\n"  # noqa
        body += f"│   ├── Sprint Capacity: {effort['sprint_capacity']}\n"  # noqa
        body += f"├── Increased Scope: {scope['increased_scope']}\n"
        body += f"├── Projected Date: {scope['projected_date']}/{scope['release_date']}\n"  # noqa
        body += "```" + "\n"

        # fetch and format tasks
        fetched_tasks = client.get_tasks()
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

        # present body info
        for owner, work_items in task_map.items():
            body += owner + " is working on:\n"
            body += "```\n"
            if work_items:
                for parent_id, tasks in work_items.items():
                    parent = tasks[0].parent  # all tasks have the same parent
                    parent_effort = f'- ({parent.effort} days)' if parent.effort else ''  # noqa
                    body += f"├── {parent_id}. {parent.name} {parent_effort}"  # noqa
                    body += "\n"
                    for task in tasks:
                        body += f"│   ├── {task.id}. {task.name} - ({task.state})"  # noqa
                        body += "\n"
            else:
                body += "No tasks in progress.\n"
            body += "```" + "\n"

        body += "Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!"  # noqa

    except Exception:
        hard_parse = True
        tb = traceback.format_exc()
        logging.error(tb)

        body = "Could not fetch content from Azure Devops. Error trace: \n"
        body += "```" + "\n"
        body += tb
        body += "```" + "\n"
        body += "Check the Yfrit Televops environment for more information."

    # parse command characters
    msg = prepare_message(str(heading + body), hard_parse)

    # edit message with daily contents
    context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                  message_id=message["message_id"],
                                  text=msg,
                                  parse_mode=telegram.ParseMode.MARKDOWN_V2)


daily_handler = CommandHandler("daily", daily)
dispatcher.add_handler(daily_handler)

updater.start_polling()
logging.info("Bot started and listening for commands.")
