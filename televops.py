import json
import logging
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


def prepare_message(msg):
    return msg.replace("-", "\-") \
              .replace(".", "\.") \
              .replace("(", "\(") \
              .replace(")", "\)") \
              .replace("!", "\!") # noqa


# set the function command callback for the daily
def daily(update, context):
    # prepare heading
    heading = f"{datetime.now()}\n"
    heading += "Welcome to today's Yfrt's Televops Daily Meeting!\n\n"
    working_text = "Working on daily request..."
    msg = prepare_message(str(heading + working_text))

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
            100 * effort["capacity_percentage_effort"])

        # present heading
        heading += "Current iteration:\n"
        heading += "```\n"
        heading += f"├── Sprint Stories/Bugs: {scope['done']}/{scope['total']} ({completed}%)\n"  # noqa
        heading += f"├── Effort\n"  # noqa
        heading += f"│   ├── Sprint Progress: {effort['sprint_completed_effort']}/{effort['sprint_total_effort']} work days completed ({sprint_percentage}%)\n"  # noqa
        heading += f"│   ├── Epic Progress: {effort['epic_completed_effort']}/{effort['epic_total_effort']} work days completed ({epic_percentage}%)\n"  # noqa
        heading += f"│   ├── Capacity: {effort['remaining_work_days']}/{effort['total_work_days']} work days remaining ({capacity_percentage}%)\n"  # noqa
        heading += f"│   ├── Work Days Per Week: {effort['work_days_per_week']}\n"  # noqa
        heading += f"├── Increased Scope: {scope['increased_scope']}\n"
        heading += f"├── Projected Date: {scope['projected_date']}/{scope['release_date']}\n"  # noqa
        heading += "```" + "\n"

        # fetch and present body info
        tasks = client.get_tasks()
        body = ""

        for owner, tasks in tasks.items():
            body += owner + " is working on:\n"
            body += "```\n"

            if tasks:
                last_parent = 0
                for task in tasks:
                    parent = task.parent
                    if last_parent != parent.id:
                        last_parent = parent.id
                        parent_effort = f'- ({parent.effort} days)' if parent.effort else ''  # noqa
                        body += f"├── {parent.id}. {parent.name} {parent_effort}"  # noqa
                        body += "\n"

                    body += f"│   ├── {task.id}. {task.name} - ({task.state})"
                    body += "\n"
            else:
                body += "No tasks in progress.\n"
            body += "```" + "\n"

        body += "Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!"  # noqa

    except Exception:
        tb = traceback.format_exc()
        logging.error(tb)

        body = "Could not fetch content from Azure Devops. Error trace: \n"
        body += "```" + "\n"
        body += tb
        body += "```" + "\n"
        body += "Check the Yfrit Televops environment for more information."

    # parse command characters
    msg = prepare_message(str(heading + body))

    # edit message with daily contents
    context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                  message_id=message["message_id"],
                                  text=msg,
                                  parse_mode=telegram.ParseMode.MARKDOWN_V2)


daily_handler = CommandHandler("daily", daily)
dispatcher.add_handler(daily_handler)

updater.start_polling()
logging.info("Bot started and listening for commands.")
