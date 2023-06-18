import os
from discord.ext import commands

from jishaku.cog import Jishaku
from jishaku.codeblocks import codeblock_converter
from jishaku.features.baseclass import Feature

from .utils.jishaku_py_modal import CodeView


os.environ["JISHAKU_RETAIN"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"


class Jishaku(Jishaku):
    __doc__ = Jishaku.__doc__

    @commands.command(
        name="git",
        brief="Shortcut to the jishaku git command.",
        help="Shortcut for 'jsk git' which is a shortcut for 'jsk sh git'. Invokes the system shell.",
    )
    async def _git(self, ctx: commands.Context, *, argument: codeblock_converter):
        jsk_git_command = self.bot.get_command("jishaku git")
        return await ctx.invoke(jsk_git_command, argument=argument)

    @Feature.Command(parent="jsk", name="py_modal")
    async def jsk_py_modal(self, ctx: commands.Context):
        """
        Direct evaluation of python code, uses a modal for input
        """
        view = CodeView(ctx)
        await ctx.send(view=view)

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


async def setup(bot):
    await bot.add_cog(Jishaku(bot=bot))
