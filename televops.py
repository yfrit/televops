import logging
import os
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

# set the collaborators and get the devops client
colaborators = ['***REMOVED***', '***REMOVED***', '***REMOVED***']
client = Client(colaborators)


# set the function command callback for the daily
def daily(update, context):
    scope = client.get_current_scope()
    completed = int(100 * scope['completed'])

    heading = f'{datetime.now()}\n'
    heading += "Welcome to today's Yfrt's Televops Daily Meeting!\n\n"
    heading += f"We are currently sitting at {scope['done']}/{scope['total']} ({completed}%) work items completed.\n\n"  # noqa

    body = ""
    tasks = client.get_tasks()

    for owner, tasks in tasks.items():
        body += owner + ' is working on:\n'
        body += '```\n'

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
            body += 'No tasks in progress.\n'
        body += '```' + '\n'

    body += "Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!"  # noqa

    msg = str(heading + body).replace('-', '\-') \
                             .replace('.', '\.') \
                             .replace('(', '\(') \
                             .replace(')', '\)') \
                             .replace('!', '\!') # noqa

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg,
                             parse_mode=telegram.ParseMode.MARKDOWN_V2)


daily_handler = CommandHandler('daily', daily)
dispatcher.add_handler(daily_handler)

updater.start_polling()
print("Bot started and listening for commands.")
