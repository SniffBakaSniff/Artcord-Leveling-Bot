import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import logging

from bot import main2
message_db_path = main2.message_db_path
logger = logging.getLogger(__name__)
logger.info(" Loading | Stats Tracking Cog")

class MessageLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.create_table()
    
    def create_table(self):
        try:
            with sqlite3.connect(message_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    user_id INTEGER,
                                    timestamp DATETIME
                                )''')
                conn.commit()
                logger.info("Messages table created or already exists.")
        except sqlite3.Error as e:
            logger.error(f"Error creating table: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        timestamp = datetime.utcnow().isoformat()
        
        logger.info(f"Received message from {message.author.id} at {timestamp}")
        
        try:
            with sqlite3.connect(message_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO messages (user_id, timestamp) VALUES (?, ?)', (message.author.id, timestamp))
                conn.commit()
                logger.info(f"Inserted message from {message.author.id} at {timestamp} into the database.")
        except sqlite3.Error as e:
            logger.error(f"Error inserting message into database: {e}")

async def setup(bot):
    await bot.add_cog(MessageLogger(bot))

