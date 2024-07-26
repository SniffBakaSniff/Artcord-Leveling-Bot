import json
import os
import sqlite3
import datetime
from datetime import timedelta
import logging
import discord
import aiosqlite
from discord.ext import commands

from bot import main2
db_path = main2.db_path
quests_path = main2.quests_path
logger = logging.getLogger(__name__)

logger.info(" Loading | Quests Cog")



class QuestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vc_sessions = {}


    # Event: Bot is ready and initialized
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Quests Cog Loaded!')
        await self.bot.tree.sync()

    def load_quests(self): #Documented
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            with open(quests_path) as f:
                quests_data = json.load(f)

            # Insert daily quests if they do not already exist
            for quest in quests_data['daily']:
                cursor.execute('''
                    INSERT OR IGNORE INTO quests (id, type, description, task_type, goal, xp_reward)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (quest['id'], 'daily', quest['description'], quest['type'], quest['goal'], quest['xp_reward']))

            # Insert weekly quests if they do not already exist or need updating
            for quest in quests_data['weekly']:
                cursor.execute('''
                    INSERT OR IGNORE INTO quests (id, type, description, task_type, goal, xp_reward)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (quest['id'], 'weekly', quest['description'], quest['type'], quest['goal'], quest['xp_reward']))

            conn.commit()
    
    """def load_quests(self):
        with open('quests.json', 'r') as f:
            quests_data = f.read()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM quests')
            cursor.executemany('INSERT INTO quests (id, description, type, goal, xp_reward) VALUES (?, ?, ?, ?, ?)', quests_data)
        print('Quests loaded.')"""

    async def update_user_progress(self, user_id, task_type): 
        try:
            async with aiosqlite.connect(db_path) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('''
                        SELECT q.id, q.task_type, q.goal, uq.progress 
                        FROM quests q
                        JOIN user_quests uq ON q.id = uq.quest_id
                        WHERE uq.user_id = ? AND uq.completed = 0 AND q.task_type = ?
                    ''', (user_id, task_type))

                    active_quests = await cursor.fetchall()

                    for quest_id, quest_task_type, goal, progress in active_quests:
                        if quest_task_type == task_type:
                            new_progress = progress + 1
                            completed = new_progress >= goal
                            await cursor.execute('UPDATE user_quests SET progress = ?, completed = ? WHERE user_id = ? AND quest_id = ?', 
                                        (new_progress, completed, user_id, quest_id))

                            if completed:
                                await cursor.execute('SELECT xp_reward FROM quests WHERE id = ?', (quest_id,))
                                xp_reward = await cursor.fetchone()
                                await cursor.execute('UPDATE users SET xp = xp + ? WHERE id = ?', (xp_reward[0], user_id))

                    await conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"Database operation failed: {e}")


    async def update_user_quests(self, user_id, num_daily=5, num_weekly=5):
        try:
            async with aiosqlite.connect(db_path) as conn:
                async with conn.cursor() as cursor:
                    # Check if user has any active quests
                    await cursor.execute('SELECT COUNT(*) FROM user_quests WHERE user_id = ? AND completed = 0', (user_id,))
                    count = await cursor.fetchone()
                    count = count[0]

                    if count == 0:
                        # Fetch random daily quests and assign
                        await cursor.execute('''
                            SELECT id FROM quests WHERE type = "daily" ORDER BY RANDOM() LIMIT ?
                        ''', (num_daily,))
                        daily_quest_ids = await cursor.fetchall()

                        for quest_id in daily_quest_ids:
                            await cursor.execute('''
                                INSERT INTO user_quests (user_id, quest_id, progress, last_updated, completed)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (user_id, quest_id[0], 0, datetime.datetime.now(datetime.timezone.utc).isoformat(), 0))

                        # Fetch random weekly quests and assign
                        await cursor.execute('''
                            SELECT id FROM quests WHERE type = "weekly" ORDER BY RANDOM() LIMIT ?
                        ''', (num_weekly,))
                        weekly_quest_ids = await cursor.fetchall()

                        for quest_id in weekly_quest_ids:
                            await cursor.execute('''
                                INSERT INTO user_quests (user_id, quest_id, progress, last_updated, completed)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (user_id, quest_id[0], 0, datetime.datetime.now(datetime.timezone.utc).isoformat(), 0))

                        await conn.commit()

                    # Fetch user's active quests
                    await cursor.execute('''
                        SELECT q.id, q.description, uq.progress, q.goal, q.type, uq.last_updated
                        FROM quests q
                        JOIN user_quests uq ON q.id = uq.quest_id
                        WHERE uq.user_id = ? AND uq.completed = 0
                    ''', (user_id,))
                    user_quests = await cursor.fetchall()

                    # Update quests if necessary
                    for quest_id, description, progress, goal, quest_type, last_updated in user_quests:
                        last_updated_time = datetime.datetime.fromisoformat(last_updated)
                        current_time = datetime.datetime.now(datetime.timezone.utc)

                        if quest_type == 'daily':
                            if (current_time - last_updated_time) >= timedelta(days=1):
                                await cursor.execute('UPDATE user_quests SET progress = 0, last_updated = ? WHERE quest_id = ? AND user_id = ?', (current_time.isoformat(), quest_id, user_id))

                        elif quest_type == 'weekly':
                            if (current_time - last_updated_time) >= timedelta(days=7):
                                await cursor.execute('UPDATE user_quests SET progress = 0, last_updated = ? WHERE quest_id = ? AND user_id = ?', (current_time.isoformat(), quest_id, user_id))

                    await conn.commit()

        except aiosqlite.Error as e:
            print(f'Error updating quests for user {user_id}: {e}')

    @commands.hybrid_command(name='quests', description='View your current quests')
    async def quests(self, ctx): #Documented
        user_id = ctx.author.id

        try:
            # Connect to the SQLite database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Fetch user's active quests with task description, task type, progress, reward, and time left
                cursor.execute('''
                    SELECT q.description, q.type, uq.progress, uq.last_updated, q.goal, q.xp_reward
                    FROM user_quests uq
                    JOIN quests q ON uq.quest_id = q.id
                    WHERE uq.user_id = ? AND uq.completed = 0
                ''', (user_id,))
                user_quests = cursor.fetchall()

                if not user_quests:
                    await ctx.send("You don't have any active quests.", ephemeral=True)
                else:
                    # Prepare two separate lists for daily and weekly quests
                    daily_quests = []
                    weekly_quests = []

                    current_time = datetime.datetime.now(datetime.timezone.utc)

                    for description, quest_type, progress, last_updated, goal, xp_reward in user_quests:
                        # Parse ISO formatted datetime string
                        last_updated_time = datetime.datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%S.%f%z")

                        if quest_type == 'daily':
                            quest_duration = datetime.timedelta(days=1)
                            time_elapsed = current_time - last_updated_time
                            time_left = quest_duration - time_elapsed
                            hours_left = time_left.days * 24 + time_left.seconds // 3600
                            time_left_str = f'{hours_left} hours'
                        elif quest_type == 'weekly':
                            quest_duration = datetime.timedelta(days=7)
                            time_elapsed = current_time - last_updated_time
                            time_left = quest_duration - time_elapsed
                            days_left = time_left.days
                            time_left_str = f'{days_left} days'

                        progress_percent = (progress / goal) * 100
                        progress_str = f'{progress}/{goal} ({progress_percent:.1f}%)'

                        if quest_type == 'daily':
                            daily_quests.append((description, time_left_str, progress_str, xp_reward))
                        elif quest_type == 'weekly':
                            weekly_quests.append((description, time_left_str, progress_str, xp_reward))

                    # Create an embed with two columns for daily and weekly quests
                    embed = discord.Embed(title='Current Quests', color=discord.Color.blue())
                    if daily_quests:
                        daily_field_value = '\n'.join(f'**{desc}** \n- Time Left: {time_left} \n- Progress: {progress} \n- Reward: {xp_reward} XP' for desc, time_left, progress, xp_reward in daily_quests)
                        embed.add_field(name='Daily Quests', value=daily_field_value, inline=True)
                    if weekly_quests:
                        weekly_field_value = '\n'.join(f'**{desc}** \n- Time Left: {time_left} \n- Progress: {progress} \n- Reward: {xp_reward} XP' for desc, time_left, progress, xp_reward in weekly_quests)
                        embed.add_field(name='Weekly Quests', value=weekly_field_value, inline=True)

                    await ctx.send(embed=embed, ephemeral=True)

        except sqlite3.Error as e:
            await ctx.send(f'An error occurred while fetching quests: {e}')

    #Placeholder function (Not Used)
    def reset_quests(self, quest_type): #Documented
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM quests WHERE type = ?', (quest_type,))
            conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Loading Quests | Quests Cog")
        self.load_quests()

    # Event: Process message to add XP and assign roles
    @commands.Cog.listener()
    async def on_message(self, message):    
        if message.author.bot:
            return
        sender = message.author.id
        await self.update_user_quests(sender)
        await self.update_user_progress(sender, 'message_count')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        self.update_user_progress(user.id, 'reaction')


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Fetch the inactive channel ID from the database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT inactive_channel_id FROM settings')
            result = cursor.fetchone()
            inactive_channel_id = int(result[0]) if result else None
            logger.info(f"The Inactive channel is: {inactive_channel_id}")

        if after.channel and after.channel.type == discord.ChannelType.voice:
            if after.channel.id == inactive_channel_id:
                logger.info(f"Joined inactive channel {after.channel.id}. Not tracking time.")
                return

            
            self.vc_sessions[member.id] = datetime.datetime.now(datetime.timezone.utc)

        elif before.channel and before.channel.type == discord.ChannelType.voice:
            if before.channel.id == inactive_channel_id:
                logger.info(f"Left inactive channel {before.channel.id}. No quests updated.")
                return

            start_time = self.vc_sessions.pop(member.id, None)
            if start_time:
                duration = datetime.datetime.now(datetime.timezone.utc) - start_time
                minutes_spent = int(duration.total_seconds() / 60)
                
                # Update progress for each minute spent in voice channel
                for _ in range(minutes_spent):
                    await self.update_user_progress(member.id, 'vc_time')


async def setup(bot):
    await bot.add_cog(QuestCog(bot))
