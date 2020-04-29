import logging
import telegram.ext

from telegram.ext import CommandHandler
from telegram.ext import Updater
from devops_client import Client
from devops_client import Task
from datetime import datetime

# fetch updater and job queue
updater = Updater(token='892133286:AAEVE0satdhieizcAlzweHnoFoG1nqj9HqE',
                  use_context=True)
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
    heading = f'{datetime.now()}\n'
    heading += "Welcome to today's Yfrt's Televops Daily Meeting!\n\n"
    heading += 'Here are the current statuses:\n\n'

    body = ""
    tasks = client.get_tasks()
    for owner, tasks in tasks.items():
        if tasks:
            body += owner + ' is working on:\n'
            body += '```\n'
            for task in tasks:
                body += f"{task.id}. {task.name}.\n"
        else:
            body += 'No tasks in progress.\n'
        body += '```' + '\n'

    body += "Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!"

    msg = str(heading + body).replace('-', '\-') \
                             .replace('.', '\.') \
                             .replace('!', '\!')

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg,
                             parse_mode=telegram.ParseMode.MARKDOWN_V2)


daily_handler = CommandHandler('daily', daily)
dispatcher.add_handler(daily_handler)

updater.start_polling()