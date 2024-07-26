import sqlite3
import logging
from discord.ext import commands, tasks
from discord.ext.commands import CheckFailure

from bot import main2
db_path = main2.db_path
logger = logging.getLogger(__name__)
logger.info("Loading | Guild Data Cog")

class GuildDataCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop_started = False

    # Define the needs_perms decorator with error handling
    def needs_perms(**perms):
        async def predicate(ctx):
            user_perms = ctx.channel.permissions_for(ctx.author)
            missing_perms = [perm for perm, value in perms.items() if getattr(user_perms, perm, None) != value]
            if missing_perms:
                missing_perms_formatted = ', '.join(missing_perms)
                await ctx.send(f"You do not have the required permissions to use this command. Missing permissions: {missing_perms_formatted}.", delete_after=10)
                return False
            return True
        return commands.check(predicate)

    def update_guild_data(self):
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Ensure the table exists with the correct schema
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS guild_data (
                        guild_id TEXT PRIMARY KEY,
                        guild_name TEXT NOT NULL,
                        channel_ids TEXT,
                        channel_names TEXT,
                        role_ids TEXT,
                        role_names TEXT
                    );
                ''')

                # Fetch all guilds the bot is a part of
                for guild in self.bot.guilds:
                    guild_id = str(guild.id)
                    guild_name = guild.name

                    # Gather channel and role data
                    channel_ids = ','.join(str(channel.id) for channel in guild.channels)
                    channel_names = ','.join(channel.name for channel in guild.channels)
                    role_ids = ','.join(str(role.id) for role in guild.roles)
                    role_names = ','.join(role.name for role in guild.roles)

                    # Check if the guild already exists in the database
                    cursor.execute("SELECT COUNT(*) FROM guild_data WHERE guild_id = ?", (guild_id,))
                    exists = cursor.fetchone()[0]

                    if exists:
                        # Update existing guild data
                        cursor.execute(
                            """
                            UPDATE guild_data
                            SET guild_name = ?, channel_ids = ?, channel_names = ?, role_ids = ?, role_names = ?
                            WHERE guild_id = ?
                            """,
                            (guild_name, channel_ids, channel_names, role_ids, role_names, guild_id)
                        )
                    else:
                        # Insert new guild data
                        cursor.execute(
                            """
                            INSERT INTO guild_data (guild_id, guild_name, channel_ids, channel_names, role_ids, role_names)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (guild_id, guild_name, channel_ids, channel_names, role_ids, role_names)
                        )

                conn.commit()
                logger.info("Guild data updated successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database error updating guild data: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating guild data: {e}")

    @tasks.loop(minutes=30)
    async def scheduled_update_guild_data(self):
        self.update_guild_data()

    @commands.hybrid_command(name='update', description="Updates guild channel and role data.")
    @needs_perms(administrator=True)
    async def update_guild_data_command(self, ctx):
        self.update_guild_data()
        await ctx.send("Guild data updated.", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.scheduled_update_guild_data.start()
            self.loop_started = True

async def setup(bot):
    await bot.add_cog(GuildDataCog(bot))
