import discord
from discord.ext import commands
import sqlite3
import logging

from bot import main2
db_path = main2.db_path
logger = logging.getLogger(__name__)
logger.info(" Loading | Cards Cog")


class CardCustomization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Event: Bot is ready and initialized
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cards Cog Loaded!')
        await self.bot.tree.sync()

    @commands.hybrid_group(name='card', invoke_without_command=True, description='Customize Your Level Card!')
    async def card(self, ctx: commands.Context):
        #if ctx.invoked_subcommand is None:
        #    await ctx.send('Please specify a customization option. Available options: Text Color, Background Color, Progress Bar Color, Background Image.', ephemeral=True)
        return
    @card.command(name='text_color', description='Set the text color of your card')
    @discord.app_commands.describe(color='Hex or RGB color')
    async def text_color(self, ctx: commands.Context, color: str):
        # Validate color format
        if color.startswith('#'):
            if len(color) == 7:
                color_format = 'hex'
            else:
                await ctx.send('Invalid hex color format. Use # followed by 6 characters (e.g., #ffffff).', ephemeral=True)
                return
        else:
            rgb_values = color.split(',')
            if len(rgb_values) == 3 and all(0 <= int(value) <= 255 for value in rgb_values):
                color_format = 'rgb'
                # Convert RGB to hex format
                color = '#{:02x}{:02x}{:02x}'.format(int(rgb_values[0]), int(rgb_values[1]), int(rgb_values[2]))
            else:
                await ctx.send('Invalid RGB color format. Use R,G,B format with values between 0-255 (e.g., 255,255,255).', ephemeral=True)
                return

        # Update the user's card_text_color in the database
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET card_text_color = ? WHERE id = ?', (color, user_id))
            conn.commit()

        await ctx.send(f'You used the card command to set text color with {color_format} value: {color}.', ephemeral=True)

    @card.command(name='progress_bar_color', description='Set the progress bar color of your card')
    @discord.app_commands.describe(color='Hex or RGB color')
    async def progress_bar_color(self, ctx: commands.Context, color: str):
        # Validate color format
        if color.startswith('#'):
            if len(color) == 7:
                color_format = 'hex'
            else:
                await ctx.send('Invalid hex color format. Use # followed by 6 characters (e.g., #ffffff).', ephemeral=True)
                return
        else:
            rgb_values = color.split(',')
            if len(rgb_values) == 3 and all(0 <= int(value) <= 255 for value in rgb_values):
                color_format = 'rgb'
                # Convert RGB to hex format
                color = '#{:02x}{:02x}{:02x}'.format(int(rgb_values[0]), int(rgb_values[1]), int(rgb_values[2]))
            else:
                await ctx.send('Invalid RGB color format. Use R,G,B format with values between 0-255 (e.g., 255,255,255).', ephemeral=True)
                return

        # Update the user's card_progress_bar_color in the database
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET card_progress_bar_color = ? WHERE id = ?', (color, user_id))
            conn.commit()

        await ctx.send(f'You used the card command to set progress bar color with {color_format} value: {color}.', ephemeral=True)

    @card.command(name='background_color', description='Set the background color of your card')
    @discord.app_commands.describe(color='Hex or RGB color', opacity='Opacity percentage')
    async def background_color(self, ctx: commands.Context, color: str, opacity: int):
        # Validate color format
        if color.startswith('#'):
            if len(color) == 7:
                color_format = 'hex'
            else:
                await ctx.send('Invalid hex color format. Use # followed by 6 characters (e.g., #ffffff).', ephemeral=True)
                return
        else:
            rgb_values = color.split(',')
            if len(rgb_values) == 3 and all(0 <= int(value) <= 255 for value in rgb_values):
                color_format = 'rgb'
                # Convert RGB to hex format
                color = '#{:02x}{:02x}{:02x}'.format(int(rgb_values[0]), int(rgb_values[1]), int(rgb_values[2]))
            else:
                await ctx.send('Invalid RGB color format. Use R,G,B format with values between 0-255 (e.g., 255,255,255).', ephemeral=True)
                return

        # Validate opacity
        if not (0 <= opacity <= 100):
            await ctx.send('Invalid opacity percentage. Use a value between 0 and 100.', ephemeral=True)
            return

        # Convert opacity to hex format (0-255 range)
        opacity_hex = '{:02x}'.format(int(opacity * 255 / 100))
        color_with_opacity = color + opacity_hex

        # Update the user's card_bg_color in the database
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET card_bg_color = ? WHERE id = ?', (color_with_opacity, user_id))
            conn.commit()

        await ctx.send(f'You used the card command to set the background color with {color_format} value: {color_with_opacity} and opacity: {opacity}%.', ephemeral=True)

    @card.command(name='background_image', description='Set the background image of your card')
    @discord.app_commands.describe(image_url='URL of the background image')
    async def background_image(self, ctx: commands.Context, image_url: str):
        # Validate image URL
        if not (image_url.startswith('http://') or image_url.startswith('https://')):
            await ctx.send('Invalid URL format. Use a valid URL starting with http:// or https://.', ephemeral=True)
            return

        # Update the user's card_bg_img_url in the database
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET card_bg_img_url = ? WHERE id = ?', (image_url, user_id))
            conn.commit()

        await ctx.send(f'You used the card command to set the background image with URL: {image_url}.', ephemeral=True)

    @card.command(name='reset', description='Reset your card to default values')
    async def reset_card(self, ctx: commands.Context):
        # Define the default values
        default_text_color = 'white'
        default_progress_bar_color = '#00f0b4'
        default_background_color = '#2b2b2b55'
        default_background_image = 'http://127.0.0.1:5000/images/background.jpg'

        # Update the user's card to default values in the database
        user_id = ctx.author.id
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET card_text_color = ?, card_progress_bar_color = ?, card_bg_color = ?, card_bg_img_url = ?
                WHERE id = ?
            ''', (default_text_color, default_progress_bar_color, default_background_color, default_background_image, user_id))
            conn.commit()

        await ctx.send('Your card has been reset to the default values.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(CardCustomization(bot))
