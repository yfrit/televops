import logging
import os
import traceback
from datetime import datetime

import telegram.ext
from telegram.ext import CommandHandler, Updater

from devops_client import Client

# fetch updater and job queue
print("Starting bot...")
updater = Updater(token=os.getenv("TELEGRAM_TOKEN"), use_context=True)
dispatcher = updater.dispatcher

# set the logging stuff
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)

# set the collaborators and get the devops client
colaborators = ["***REMOVED***", "***REMOVED***", "***REMOVED***"]
client = Client(colaborators)


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

        # present heading
        heading += "Current iteration:\n"
        heading += "```\n"
        heading += f"├── Stories/Bugs: {scope['done']}/{scope['total']} ({completed}%)\n"  # noqa
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
                        body += f"├── {parent.id}. {parent.name}"
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
print("Bot started and listening for commands.")
