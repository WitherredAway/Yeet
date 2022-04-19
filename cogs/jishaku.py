import os
import sys
import discord
from discord.ext import menus, commands

from jishaku.cog import Jishaku
from jishaku.flags import Flags
from jishaku.codeblocks import Codeblock, codeblock_converter
from jishaku.features.baseclass import Feature


os.environ["JISHAKU_RETAIN"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"


class Jishaku(Jishaku):
    __doc__ = Jishaku.__doc__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = kwargs.pop("bot")
        self.hidden = False

    @commands.command(
        name="git",
        brief="Shortcut to the jishaku git command.",
        help="Shortcut for 'jsk git' which is a shortcut for 'jsk sh git'. Invokes the system shell.",
    )
    async def _git(self, ctx: commands.Context, *, argument: codeblock_converter):
        jsk_git_command = self.bot.get_command("jishaku git")
        return await ctx.invoke(jsk_git_command, argument=argument)

    @Feature.Command(parent="jsk", name="hide")
    async def jsk_hide(self, ctx: commands.Context):
        """
        Hides Jishaku from the help command.
        """

        if self.hidden:
            return await ctx.send("Jishaku is already hidden.")

        self.hidden = True
        await ctx.send("Jishaku is now hidden.")

    @Feature.Command(parent="jsk", name="show")
    async def jsk_show(self, ctx: commands.Context):
        """
        Shows Jishaku in the help command.
        """

        if not self.hidden:
            return await ctx.send("Jishaku is already visible.")

        self.hidden = False
        await ctx.send("Jishaku is now visible.")

    @Feature.Command(parent="jsk", name="restart")
    async def jsk_restart(self, ctx: commands.Context):
        """
        Restarts the bot by killing the process with the 'jsk shell' command, which invokes the system shell.
        """

        main_file = sys.argv[0]
        kill_cmd = f"kill 1"
        restart_cmd = f"python3 {main_file}"

        cmd = f"{kill_cmd} && {restart_cmd}"

        return await ctx.invoke(self.jsk_shell, argument=codeblock_converter(cmd))


async def setup(bot):
    await bot.add_cog(Jishaku(bot=bot))
