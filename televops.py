import json
import logging
import re
import sys
import traceback

import telegram.ext
from telegram.ext import CommandHandler, Updater

from devops_client import Client
from environment import Environment
from message_builder import (build_error, build_header, build_scope,
                             build_tasks, build_waiting)

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
    chat_id = update.message.chat_id
    logging.info("Daily command received from "
                 f"@{update.effective_user['username']} "
                 f"at channel {chat_id}.")

    # validate chat_id
    if not validate_chat_id(chat_id):
        logging.warning(f"Chat ID {chat_id} is not allowed.")
        return

    # prepare heading
    header = build_header()

    # send message to show api is working
    waiting = build_waiting()
    msg = prepare_message(header + waiting)
    message = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode=telegram.ParseMode.MARKDOWN_V2)

    # fetch scope info for body
    effort = {}
    scope = {}
    fetched_tasks = {}
    try:
        logging.info("Fetching data from Azure Devops...")
        effort = client.get_total_effort()
        scope = client.get_current_scope()
        fetched_tasks = client.get_tasks()

        # prepare task and scope message
        scope_msg = build_scope(scope, effort)
        tasks_msg = build_tasks(fetched_tasks)
        msg = prepare_message(header + scope_msg + tasks_msg)

        # edit message with daily contents
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message["message_id"],
            text=msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2)
    except Exception:
        tb = traceback.format_exc()
        logging.error(tb)

        # prepare error message
        error = build_error(tb)
        msg = prepare_message(header + error, hard_parse=True)
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message["message_id"],
            text=msg,
            parse_mode=telegram.ParseMode.MARKDOWN_V2)
        return


daily_handler = CommandHandler("daily", daily)
dispatcher.add_handler(daily_handler)

updater.start_polling()
logging.info("Bot started and listening for commands.")
