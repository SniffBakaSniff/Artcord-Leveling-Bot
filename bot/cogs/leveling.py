import sqlite3
import re
import datetime
import random
import requests
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Cog, Bot, CheckFailure
import io
import logging


from bot import main2
db_path = main2.db_path
logger = logging.getLogger(__name__)
logger.info(" Loading | Leveling Cog")

class LevelingCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.vc_sessions = {}
        logger.info("LevelingCog initialized")
        guild_id = "1219490918235901962"

    # Define the needs_perms decorator with error handling
    def needs_perms(**perms):
        async def predicate(ctx):
            try:
                user_perms = ctx.channel.permissions_for(ctx.author)
                missing_perms = [perm for perm, value in perms.items() if getattr(user_perms, perm, None) != value]
                if missing_perms:
                    missing_perms_formatted = ', '.join(missing_perms)
                    await ctx.send(f"You do not have the required permissions to use this command. Missing permissions: {missing_perms_formatted}.", ephemeral=True)
                    return False
                return True
            except CheckFailure:
                return False
        return commands.check(predicate)

    # Function to calculate the level based on XP
    def calculate_level(self, xp): 
        return int(xp / 100)

    # Function to calculate XP needed for the next level
    def calculate_xp_needed_for_next_level(self, level):
        return (level + 1) * 100

    # Function to calculate the total XP needed to reach a certain level
    def calculate_total_xp_for_level(self, level):
        return level * 100

    # Async function to add XP to a user
    async def add_xp(self, user_id, xp, username, nickname, avatar_url):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT xp, level, xp_needed, total_xp FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                current_xp, current_level, xp_needed, total_xp = row
                new_xp = current_xp + xp
                new_level = self.calculate_level(new_xp)

                if new_level > current_level:
                    new_total_xp = total_xp + new_xp
                    new_xp_needed = self.calculate_xp_needed_for_next_level(new_level)

                    cursor.execute('UPDATE users SET xp = ?, level = ?, username = ?, nickname = ?, avatar_url = ?, xp_needed = ?, total_xp = ? WHERE id = ?', 
                                   (0, new_level, username, nickname, avatar_url, new_xp_needed, new_total_xp, user_id))
                    await self.assign_role(user_id, new_level)

                    level_notif_id = self.get_level_notif_id()
                    if level_notif_id:
                        await self.send_level_up_message(level_notif_id, user_id, new_level)
                else:
                    new_xp_needed = self.calculate_xp_needed_for_next_level(current_level)
                    new_total_xp = total_xp + xp

                    cursor.execute('UPDATE users SET xp = ?, username = ?, nickname = ?, avatar_url = ?, xp_needed = ?, total_xp = ? WHERE id = ?', 
                                   (new_xp, username, nickname, avatar_url, new_xp_needed, new_total_xp, user_id))
            else:
                new_level = self.calculate_level(xp)
                new_xp_needed = self.calculate_xp_needed_for_next_level(new_level)
                cursor.execute('INSERT INTO users (id, username, nickname, xp, level, avatar_url, xp_needed, total_xp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                               (user_id, username, nickname, xp, new_level, avatar_url, new_xp_needed, xp))
                if new_level > 0:
                    await self.assign_role(user_id, new_level)

                    level_notif_id = self.get_level_notif_id()
                    if level_notif_id:
                        await self.send_level_up_message(level_notif_id, user_id, new_level)

    # Function to get the level notification channel ID
    def get_level_notif_id(self):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT level_notif_id FROM settings LIMIT 1')
            row = cursor.fetchone()
            if row:
                return int(row[0])
            return None
        
    def get_role_id_from_mention(self, role_mention: str) -> int:

        match = re.match(r'<@&(\d+)>', role_mention)
        if match:
            return int(match.group(1))
        else:
            try:
                return int(role_mention)
            except ValueError:
                return None

    async def send_level_up_message(self, level_notif_id, user_id, new_level):
        channel = self.bot.get_channel(level_notif_id)
        if channel:
            await channel.send(f'Congratulations <@{user_id}>! You have leveled up to level {new_level}!')

        guild = channel.guild
        member = guild.get_member(user_id)
        if not member:
            logger.error(f"Member with ID {user_id} not found in guild {guild.id}.")
            return

        role_id = self.get_role_rewards_for_level(new_level)
        logger.info(f"Role reward for level {new_level}: {role_id}")

        if not role_id:
            logger.warning(f"No role reward configured for level {new_level}.")
            return

        role = guild.get_role(role_id)
        available_role_ids = [role.id for role in guild.roles]
        logger.info(f"Available roles in guild {guild.id}: {available_role_ids}")
        if role:
            try:
                await member.add_roles(role)
                logger.info(f"Added role {role.name} ({role.id}) to member {member.name}.")
            except Exception as e:
                logger.error(f"Failed to add role {role_id} to member {user_id}: {e}")
        else:
            logger.warning(f"Role with ID {role_id} not found in guild {guild.id}.")



    def get_role_rewards_for_level(self, level):
        role_id = None
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role_id FROM config WHERE level = ?', (level,))
                result = cursor.fetchone()
                if result:
                    role_id = int(result[0])
                    logger.debug(f"Fetched role ID for level {level}: {role_id}")
        except sqlite3.Error as e:
            logger.error(f'Error fetching role rewards: {e}')
        return role_id


    async def log_roles_in_guild(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild with ID {guild_id} not found.")
            return

        roles = guild.roles
        logger.info(f"Roles in guild {guild_id}: {[role.name for role in roles]}")


    async def resolve_user_id(self, ctx, username_or_id):
        if re.match(r'<@!?\d+>', username_or_id):
            user_id = int(re.findall(r'\d+', username_or_id)[0])
        else:
            try:
                user_id = int(username_or_id)
            except ValueError:
                await ctx.send(f'{ctx.author.mention}, please provide a valid user ID or mention.', ephemeral=True)
                return None
        return user_id

    # Function to retrieve user's level and XP
    def get_user_level(self, user_id):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT xp, level FROM users WHERE id = ?', (user_id,))
            return cursor.fetchone()
        
    @commands.hybrid_group(name="manage", description="Managment Commands!")
    @commands.has_permissions(administrator=True)
    async def manage(self, ctx: commands.Context):
        print("Demo WTF")
        #if ctx.invoked_subcommand is None:
        #    await ctx.send("Please specify a subcommand.", ephemeral=True)
        
    @manage.command(name="reset", description="Reset Your Profile")
    async def reset_profile(self, ctx):
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        await ctx.send(f'{ctx.author.mention}, your profile has been reset.', ephemeral=True)

    @manage.command(name="add_role_rewards")
    async def add_role_rewards(self, ctx, role: str, level: int):
        """
        Adds a role reward entry to the database.

        Args:
            role (str): The mention or ID of the role to be rewarded.
            level (int): The level required to earn the role.
        """
        # Extract the role ID from a mention if provided
        role_id = self.get_role_id_from_mention(role)

        # Check if role_id and level are valid before inserting
        if role_id is None or level <= 0:
            await ctx.send("Invalid role mention or level. Please provide a valid role mention and a positive level.", ephemeral=True)
            return

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO config (role_id, level) VALUES (?, ?)', 
                                (role_id, level))
                conn.commit()
            await ctx.send(f'{ctx.author.mention}, role reward has been added: Role ID {role_id} at level {level}.', ephemeral=True)
        except sqlite3.Error as e:
            await ctx.send(f'Error adding role reward: {e}', ephemeral=True)


    @manage.command(name="remove_role_rewards")
    async def remove_role_rewards(self, ctx, role: str):
        """
        Removes all role reward attached to a role.

        Args:
            role (str): The mention or ID of the role to be removed.
        """
        # Extract the role ID from a mention if provided
        role_id = self.get_role_id_from_mention(role)

        # Check if role_id is valid before deleting
        if role_id is None:
            await ctx.send("Invalid role mention or ID. Please provide a valid role mention or ID.", ephemeral=True)
            return

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM config WHERE role_id = ?', (role_id,))
                if cursor.rowcount == 0:
                    await ctx.send(f'{ctx.author.mention}, no role reward found for Role ID {role_id}.', ephemeral=True)
                else:
                    conn.commit()
                    await ctx.send(f'{ctx.author.mention}, role reward has been removed for Role ID {role_id}.', ephemeral=True)
        except sqlite3.Error as e:
            await ctx.send(f'Error removing role reward: {e}', ephemeral=True)



    @manage.command(name="inactive")
    async def set_inactive(self, ctx, channel_id=None):
        """
        Sets a channel as inactive.
        :param ctx: The context of the command.
        :param channel_id: The ID of the channel to set as inactive.
        """
        if channel_id is None:
            afk_channel = ctx.guild.afk_channel
            if afk_channel is None:
                await ctx.send("This server does not have an AFK channel set. Please provide a channel ID.", ephemeral=True)
                return
            channel = afk_channel
        else:
            try:
                # Ensure the channel ID is valid and fetch the channel
                channel_id = int(channel_id)
                channel = self.bot.get_channel(channel_id)
                if not isinstance(channel, discord.VoiceChannel):
                    raise ValueError("Invalid channel ID or channel is not a voice channel.")
            except (ValueError, TypeError):
                await ctx.send("Invalid channel ID. Please provide a valid voice channel ID.", ephemeral=True)
                return

        channel_id = str(channel.id)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE settings SET inactive_channel_id = ?', (channel_id,))
            conn.commit()

        await ctx.send(f"The channel {channel.mention} with ID {channel_id} has been set as inactive.", ephemeral=True)



    @manage.command(name="levelnotif")
    @commands.has_permissions(administrator=True)
    async def set_level_notif(self, ctx, channel = None):
        """
        Sets a channel to be the notification channel.
        :param channel: The channel to set as the notification channel.
        """
        if channel is None:
            await ctx.send("Please mention a text channel or provide its ID.")
            return

        if isinstance(channel, discord.TextChannel):
            channel_id = str(channel.id)
        else:
            try:
                # Check if the channel is mentioned using <#channel_id>
                mention_match = re.match(r'<#(\d+)>', str(channel))
                if mention_match:
                    channel_id = int(mention_match.group(1))
                else:
                    channel_id = int(channel)
                
                # Fetch the channel to make sure it exists and is a TextChannel
                channel = self.bot.get_channel(channel_id)
                if not isinstance(channel, discord.TextChannel):
                    raise ValueError("Invalid channel ID or channel is not a text channel.", ephemeral=True)
                channel_id = str(channel.id)
            except (ValueError, TypeError):
                await ctx.send("Invalid channel or channel ID.", ephemeral=True)
                return

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE settings SET level_notif_id = ?', (channel_id,))
            conn.commit()

        await ctx.send(f"The channel {channel.mention} with ID {channel_id} has been set as the notification channel.", ephemeral=True)


    # Command: Profile command to show user's level and XP 
    @commands.hybrid_command(name="level", description="Get Your Level")
    async def level(self, ctx, *, username_or_id=None):
        if username_or_id is None:
            user_id = ctx.author.id
        else:
            user_id = await self.resolve_user_id(ctx, username_or_id)
            if user_id is None:
                return

        user_data = self.get_user_level(user_id)
        if user_data:
            xp, level = user_data
            next_level_xp = self.calculate_xp_needed_for_next_level(level)
            xp_percentage = (xp / next_level_xp) * 100

            card_api_url = f'http://127.0.0.1:5000/card?user_id={user_id}'
            response = requests.get(card_api_url)

            if response.status_code == 200:
                await ctx.send(file=discord.File(io.BytesIO(response.content), 'card.png'))
            else:
                await ctx.send(f'{ctx.author.mention}, failed to fetch level card.')
        else:
            await ctx.send(f'{ctx.author.mention}, user not found or no XP yet.', ephemeral=True)

    # Event: Bot is ready and initialized
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Leveling Cog Loaded!')
        self.ensure_nickname_not_null()
        await self.log_roles_in_guild(1219490918235901962)
        await self.bot.tree.sync()

    # Event: Process message to add XP and assign roles
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        sender = message.author.id
        user = message.author
        userNick = message.author.nick or message.author.name
        user_id = user.id
        username = str(user)
        nickname = str(userNick)
        avatar_url = str(user.avatar.url)
        min_xp, max_xp = await self.get_xp_settings()
        xp_from_message = random.randint(min_xp, max_xp)
        await self.add_xp(user_id, xp_from_message, username, nickname, avatar_url)
        await self.bot.process_commands(message)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        userNick = member.nick or member.name
        user_id = member.id
        username = str(member.name)
        nickname = str(userNick)
        avatar_url = str(member.avatar.url)
        min_xp, max_xp = await self.get_xp_settings()

        # Fetch the inactive channel ID from the database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT inactive_channel_id FROM settings')
            result = cursor.fetchone()
            inactive_channel_id = int(result[0]) if result else None
            logger.info(f"The Inactive channel is: {inactive_channel_id}")

        logger.info('VC EVENT: %s %s %s %s %s', userNick, user_id, username, nickname, avatar_url)
        logger.info('Before Channel: %s', before.channel)
        logger.info('After Channel: %s', after.channel)

        # Check if the member joined a voice channel
        if after.channel and after.channel.type == discord.ChannelType.voice:
            # If joined the inactive channel, do not start tracking
            if after.channel.id == inactive_channel_id:
                logger.info(f"Joined inactive channel {after.channel.id}. Not tracking time.")
                return

            self.vc_sessions[member.id] = datetime.datetime.now(datetime.timezone.utc)

        # Check if the member left a voice channel
        elif before.channel and before.channel.type == discord.ChannelType.voice:
            # If left the inactive channel, do not calculate XP
            if before.channel.id == inactive_channel_id:
                logger.info(f"Left inactive channel {before.channel.id}. No XP calculation.")
                return

            start_time = self.vc_sessions.pop(member.id, None)
            if start_time:
                duration = datetime.datetime.now(datetime.timezone.utc) - start_time
                minutes_spent = int(duration.total_seconds() / 60)
                logger.info(f"Time Spent in VC: {minutes_spent}")

                # Add XP for each minute spent in the voice channel
                for _ in range(minutes_spent):
                    xp_from_message = random.randint(min_xp * 5, max_xp * 5)
                    logger.info(f"Xp Earned: {xp_from_message}")
                    await self.add_xp(user_id, xp_from_message, username, nickname, avatar_url)



    # Command: Leaderboard command to show top users by XP
    @commands.hybrid_command(name="leaderboard", description="Get the leaderboard")
    async def leaderboard(self, ctx):
        leaderboard_url = 'http://127.0.0.1:5000/img/leaderboard'
        response = requests.get(leaderboard_url)

        if response.status_code == 200:
            image_bytes = io.BytesIO(response.content)
            await ctx.send(file=discord.File(image_bytes, 'leaderboard.png'))
            image_bytes.close()
        else:
            await ctx.send(f"Failed to fetch leaderboard image: HTTP status code {response.status_code}")

    @commands.hybrid_command(name="lb", description="Get the leaderboard")
    async def lb(self, ctx):
        await self.leaderboard(ctx)

    # Command: Slash command to set level for a user
    @manage.command(name="setlevel", description="Set Level for a user")
    async def set_level(self, ctx, username_or_id: str, level: int): #Documented
        user_id = await self.resolve_user_id(ctx, username_or_id)
        if user_id is None:
            return

        new_total_xp = self.calculate_total_xp_for_level(level)
        xp_needed = self.calculate_xp_needed_for_next_level(level)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT xp, total_xp FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                cursor.execute('UPDATE users SET level = ?, xp = 0, xp_needed = ?, total_xp = ? WHERE id = ?', 
                            (level, xp_needed, new_total_xp, user_id))
            else:
                cursor.execute('INSERT INTO users (id, level, xp, xp_needed, total_xp) VALUES (?, ?, ?, ?, ?)', 
                            (user_id, level, 0, xp_needed, new_total_xp))

        await ctx.send(f"Level set to {level} for user <@{user_id}>", ephemeral=True)
        await self.assign_role(user_id, level)

    @manage.command(name="xp", description="Manage XP for a user")
    async def manage_xp(self, ctx, action: str, amount: int, username_or_id: str): #Documented
        """
        Manage XP for a user.

        Args:
            action (str): Action to perform. Options are "set", "give", "take".
            username_or_id (str): Username or ID of the user.
            amount (int): Amount of XP to set, give, or take.
        """
        user_id = await self.resolve_user_id(ctx, username_or_id)
        if user_id is None:
            await ctx.send("User not found.", ephemeral=True)
            return

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT xp, level, total_xp FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                current_xp, level, total_xp = row

                if action == "set" or action == "1":
                    if amount < 0:
                        await ctx.send("Amount cannot be less than 0 when setting XP.", ephemeral=True)
                        return
                    elif amount > (level+1)*100:
                        await ctx.send(f"Amount cannot be greater then {(level+1)*100}.", ephemeral=True)
                    new_xp = amount
                    new_total_xp = (level * 100) + amount
                elif action == "give" or action == "2":
                    new_xp = current_xp + amount
                    new_total_xp = total_xp + amount
                    await ctx.send(f"{amount} XP was givin to <@{user_id}>", ephemeral=True)
                elif action == "take" or action == "3":
                    new_xp = max(0, current_xp - amount)
                    new_total_xp = max(0, total_xp - amount)
                    await ctx.send(f"{amount} XP has been removed from <@{user_id}>", ephemeral=True)
                else:
                    await ctx.send("Invalid action. Use 'set', 'give', or 'take'.", ephemeral=True)
                    return

                xp_needed = self.calculate_xp_needed_for_next_level(level)
                cursor.execute('UPDATE users SET xp = ?, xp_needed = ?, total_xp = ? WHERE id = ?', 
                            (new_xp, xp_needed, new_total_xp, user_id))
            else:
                if action == "set":
                    new_xp = amount
                    new_total_xp = amount
                    level = self.calculate_level(new_xp)
                    xp_needed = self.calculate_xp_needed_for_next_level(level)
                    cursor.execute('INSERT INTO users (id, xp, xp_needed, total_xp) VALUES (?, ?, ?, ?)', 
                                (user_id, new_xp, xp_needed, new_total_xp))
                else:
                    await ctx.send("User does not exist and action is not 'set'. Cannot give or take XP.", ephemeral=True)
                    return

    @manage.command(name="xprange", description="Set XP range for users")
    async def set_xp_range(ctx, min_xp: int, max_xp: int): #Documented
        if min_xp < 0 or max_xp < 0 or min_xp > max_xp:
            await ctx.send(f'{ctx.author.mention}, please provide valid XP range values. The minimum XP must be less than or equal to the maximum XP, and both must be non-negative.', ephemeral=True)
            return

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Update the settings table with the new min_xp and max_xp values
            cursor.execute('''
                UPDATE settings 
                SET min_xp = ?, max_xp = ?
            ''', (min_xp, max_xp))
            
            conn.commit()
        
        await ctx.send(f'{ctx.author.mention}, the XP range has been set to {min_xp} - {max_xp}.', ephemeral=True)

    @commands.hybrid_command(name='rewards', description='Show leveling rewards')
    async def reward(self, ctx):#Documented
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT level, role_id FROM config')
                rewards = cursor.fetchall()

            embed = discord.Embed(title='Leveling Rewards', color=discord.Color.blue())
            
            levels = []
            roles = []

            for level, role_id in rewards:
                levels.append(f"**{level}**")
                roles.append(f"<@&{role_id}>")

            embed.add_field(name='Level', value='\n'.join(levels), inline=True)
            embed.add_field(name='Role', value='\n'.join(roles), inline=True)

            await ctx.send(embed=embed)

        except sqlite3.Error as e:
            await ctx.send(f'An error occurred while fetching rewards: {e}')


    async def get_xp_settings(self):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT min_xp, max_xp FROM settings')
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
            return 15, 25

    async def assign_role(self, user_id, new_level):
        guild = self.bot.get_guild(1219490918235901962)
        member = guild.get_member(user_id)
        if not member:
            return
        roles = []
        for role in guild.roles:
            match = re.match(r'Level (\d+)', role.name)
            if match and int(match.group(1)) <= new_level:
                roles.append(role)
        if roles:
            await member.add_roles(*roles)

    def ensure_nickname_not_null(self):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET nickname = username WHERE nickname IS NULL')


    @manage.error
    async def admin_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            if isinstance(ctx, discord.ApplicationContext):
                await ctx.respond("You do not have the required role to use these commands.", ephemeral=True)
            else:
                await ctx.send("You do not have the required role to use these commands.", delete_after=10)
        elif isinstance(error, commands.MissingPermissions):
            if isinstance(ctx, discord.ApplicationContext):
                await ctx.respond("You do not have the required permissions to use this command.", ephemeral=True)
            else:
                await ctx.send("You do not have the required permissions to use this command.", delete_after=10)
        else:
            if isinstance(ctx, discord.ApplicationContext):
                await ctx.respond("An error occurred.", ephemeral=True)
            else:
                await ctx.send("An error occurred.")
            raise error

# Function to set up the bot
async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
