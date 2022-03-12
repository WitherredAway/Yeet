import discord

from discord.ext import menus, commands
from jishaku.cog import Jishaku
from jishaku.codeblocks import codeblock_converter

class Jishaku(Jishaku):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = kwargs.pop('bot')

    @commands.command(
        name="git",
        brief="Shortcut to the jishaku git command.",
        help="Shortcut for 'jsk git' which is a shortcut for 'jsk sh git'. Invokes the system shell."
    )
    async def _git(self, ctx: commands.Context, *, argument: codeblock_converter):
        jsk_git_command = self.bot.get_command('jishaku git')
        return await ctx.invoke(jsk_git_command, argument=argument)


def setup(bot):
    bot.add_cog(Jishaku(bot=bot))