import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv
import requests
import sys
from datetime import datetime
import logging
from aiohttp import web
from aiohttp_cors import setup

sys.path.append('../')
from Utils import db_initializer as db
from Utils import message_db_initializer as mdb


load_dotenv(dotenv_path='../.env')

TOKEN = os.getenv('token')

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'database.db')
message_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'messages.db')
quests_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'quests.json')

print(db_path, "| Main Bot File")
base_api_url = 'http://localhost:5000/artcordlv/api/'

app = web.Application()
cors = setup(app)

api_key = os.getenv('api_key')
headers = {'Authorization': api_key}
response = requests.get('http://127.0.0.1:5000/', headers=headers)


def setup_logging():
    # Create the logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Get the current date
    today = datetime.now()
    date_str = today.strftime("%m-%d-%Y")  # Format the date as MM-DD-YYYY

    # Create the log file name
    log_file_name = f'logs/{date_str}.log'

    # Set up logging configuration
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
                        handlers=[logging.FileHandler(log_file_name, encoding='utf-8'),
                                  logging.StreamHandler()])

    logger = logging.getLogger(__name__)
    logger.info("Logging setup complete")


setup_logging()
logger = logging.getLogger(__name__)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        missing_perms = error.missing_permissions
        missing_perms_formatted = ', '.join(missing_perms)
        await ctx.send(f"You do not have the required permissions to use this command. Missing permissions: {missing_perms_formatted}.", ephemeral=True)
        logger.warning(f"User {ctx.author.id} tried to execute command {ctx.command} in guild {ctx.guild.id} but is missing permissions: {missing_perms_formatted}")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("This command does not exist.")
        logger.warning(f"User {ctx.author.id} tried to execute a non-existent command: {ctx.message.content}")
    else:
        await ctx.send("An error occurred while executing the command.")
        logger.error(f"An error occurred while executing command {ctx.command}: {error}", exc_info=True)


# Function to load cogs
async def load_cogs():
    await bot.load_extension('cogs.logging')
    await bot.load_extension('cogs.guild_data')
    await bot.load_extension('cogs.cards')
    await bot.load_extension('cogs.leveling')
    await bot.load_extension('cogs.quests')
    await bot.load_extension('cogs.stats_tracker')

# Main function to run the bot
async def main():
    db.init_db()
    mdb.init_db()
    await load_cogs()
    await bot.start(TOKEN)

# Start the bot
if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
