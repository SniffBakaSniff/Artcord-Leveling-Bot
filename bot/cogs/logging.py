import logging
from discord.ext import commands

class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        self.logger.info(f"Command '{ctx.command}' invoked by user {ctx.author} (ID: {ctx.author.id}) in guild {ctx.guild} (ID: {ctx.guild.id})")

    #@commands.Cog.listener()
    #async def on_command_completion(self, ctx):
    #    self.logger.info(f"Command '{ctx.command}' completed successfully by user {ctx.author} (ID: {ctx.author.id}) in guild {ctx.guild} (ID: {ctx.guild.id})")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            missing_perms = error.missing_permissions
            missing_perms_formatted = ', '.join(missing_perms)
            await ctx.send(f"You do not have the required permissions to use this command. Missing permissions: {missing_perms_formatted}.", ephemeral=True)
            self.logger.warning(f"User {ctx.author.id} tried to execute command {ctx.command} in guild {ctx.guild.id} but is missing permissions: {missing_perms_formatted}")
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send("This command does not exist.")
            self.logger.warning(f"User {ctx.author.id} tried to execute a non-existent command: {ctx.message.content}")
        else:
            await ctx.send("An error occurred while executing the command.")
            self.logger.error(f"An error occurred while executing command {ctx.command}: {error}", exc_info=True)

async def setup(bot):
    await bot.add_cog(ErrorHandlerCog(bot))
    #print("ErrorHandlerCog loaded")  # Debug statement
