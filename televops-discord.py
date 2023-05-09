import json
import logging
import traceback

import discord
from discord.ext import commands

from devops_client import Client
from environment import Environment
from message_builder import (build_error, build_header, build_scope,
                             build_tasks, build_waiting)

# load env
env = Environment()

# fetch bot token
bot_token = env.discord_bot_token

# set the collaborators and get the devops client
collaborators = []
try:
    with open('collaborators.json') as f:
        collaborators = json.load(f)
except FileNotFoundError:
    print("Collaborators file not found.")
    exit(1)

client = Client(collaborators)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.command(name='daily')
async def daily(ctx):
    # prepare heading
    header = build_header()

    # send message to show api is working
    waiting = build_waiting()
    msg = header + waiting
    msg_obj = await ctx.send(msg)

    # fetch scope info for body
    effort = {}
    scope = {}
    fetched_tasks = {}
    try:
        logging.info("Fetching data from Azure Devops...")
        effort = client.get_total_effort()
        scope = client.get_current_scope()
        fetched_tasks = client.get_tasks()
    except Exception:
        tb = traceback.format_exc()
        logging.error(tb)

        # prepare error message
        error = build_error(tb)
        await msg_obj.edit(content=error)
        return

    # send scope and effort info
    scope_msg = build_scope(scope, effort)
    msg = header + scope_msg
    await msg_obj.edit(content=msg)

    # send tasks info
    msg = build_tasks(fetched_tasks)
    await ctx.send(msg)


@bot.event
async def on_ready():
    logging.info(f'{bot.user.name} has connected to Discord!')


# run bot
bot.run(bot_token)
