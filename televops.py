import logging
import os
import telegram.ext

from telegram.ext import CommandHandler
from telegram.ext import Updater
from devops_client import Client
from devops_client import Task
from datetime import datetime
from datetime import timezone
from dotenv import load_dotenv

# load env file
load_dotenv()

# fetch updater and job queue
print("Starting bot...")
updater = Updater(token=os.getenv("TELEGRAM_TOKEN"),
                  use_context=True)
dispatcher = updater.dispatcher

# set the logging stuff
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

# set the collaborators and get the devops client
colaborators = ['Matheus Pinheiro', 'Lucas Pinheiro', 'Matheus Gomes']
client = Client(colaborators)


# set the function command callback for the daily
def daily(update, context):
    heading = f'{datetime.now()}\n'
    heading += "Welcome to today's Yfrt's Televops Daily Meeting!\n\n"
    heading += 'Here are the current statuses:\n\n'

    body = ""
    tasks = client.get_tasks(include_completed=True)
    
    for owner, tasks in tasks.items():
        body += owner + ' is working on:\n'
        body += '```\n'
        if tasks:
            for task in tasks:
                body += f"{task.id}. {task.name} ({task.state})."
                body += "\n"
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
print("Bot started and listening for commands.")