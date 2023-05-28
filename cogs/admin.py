import asyncio
import time

import discord
from discord.ext import commands
from cogs.utils.utils import enumerate_list

from helpers.context import CustomContext


class RepeatView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = self.ctx.bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        await self.message.edit(view=None)

    @discord.ui.button(label="Run again", style=discord.ButtonStyle.blurple)
    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.ctx.bot.process_commands(self.ctx.message)


NOT_FOUND_MSG = "❌ Extension not found"


class Developer(commands.Cog):
    """Developer only category."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.hidden = True

    display_emoji: discord.PartialEmoji = "⚒️"

    @commands.command(
        name="togglecommand",
        aliases=("tc",),
        description="Enable or disable a command.",
    )
    @commands.is_owner()
    async def toggle(self, ctx: commands.Context, *, command: str):
        command = self.bot.get_command(command)

        if command is None:
            return await ctx.send(f":x: Command `{command}` not found.")

        elif command == ctx.command:
            return await ctx.send(f":x: This command cannot be disabled.")

        else:
            command.enabled = not command.enabled
            await ctx.send(
                f'{"↪️ Enabled" if command.enabled else "↩️ Disabled"} command `{command.qualified_name}`.'
            )

    # Cog related commands group
    @commands.is_owner()
    @commands.group(
        name="cog",
        aliases=("c", "ext", "extension"),
        invoke_without_command=True,
        case_insensitive=True,
        brief="Cog related commands.",
        help="Commands related to cogs, dev only command.",
    )
    async def cog(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    # Cog load command for loading cogs
    @commands.is_owner()
    @cog.command(
        name="load",
        aliases=("l",),
        brief="Load an extension",
        help="Loads an extension by name. Dev only command.",
    )
    async def _load(self, ctx: commands.Context, ext: str):
        async with ctx.typing():
            start = time.time()
            try:
                ext = self.bot.COGS[ext]
                ext = f"cogs.{ext}"
                await self.bot.load_extension(ext)
            except (KeyError, commands.ExtensionNotFound):
                title = NOT_FOUND_MSG
            except commands.ExtensionAlreadyLoaded:
                title = f"Extension already loaded"
            else:
                title = f"📥 Loaded extension"

            desc = f"`{ext}`"

            view = RepeatView(ctx)
            embed = self.bot.Embed(title=title, description=desc)
            embed.set_footer(text=f"Completed in {round(time.time() - start, 2)}s")
            view.message = await ctx.send(embed=embed, view=view)

    # Cog unload command for unloading cogs
    @commands.is_owner()
    @cog.command(
        name="unload",
        aliases=("u",),
        brief="Unloads an extension",
        help="Unloads an extension by name. Dev only command.",
    )
    async def _unload(self, ctx: commands.Context, ext: str):
        async with ctx.typing():
            start = time.time()
            try:
                ext = self.bot.COGS[ext]
                ext = f"cogs.{ext}"
                if ext == __name__:
                    title = "❌ Cannot unload extension"
                else:
                    await self.bot.unload_extension(ext)
            except (KeyError, commands.ExtensionNotFound):
                title = NOT_FOUND_MSG
            else:
                title = f"📤 Unloaded extension"

            desc = f"`{ext}`"

            view = RepeatView(ctx)
            embed = self.bot.Embed(title=title, description=desc)
            embed.set_footer(text=f"Completed in {round(time.time() - start, 2)}s")
            view.message = await ctx.send(embed=embed, view=view)

    # Cog reload command for reloading cogs
    @commands.is_owner()
    @cog.command(
        name="reload",
        aliases=("r",),
        brief="Reloads one or `all` extensions",
        help="Reloads an extension by name. Pass `all` to reload all extensions. Dev only command.",
    )
    async def _reload(self, ctx: CustomContext, *, ext: str):
        async with ctx.typing():
            start = time.time()
            title = desc = None
            if ext == "all":
                exts = []
                for ext in list(self.bot.extensions):
                    await self.bot.reload_extension(ext)
                    exts.append(f"`{ext}`")
                title = f"🔁 Reloaded {len(exts)} extensions"
                desc = "\n".join(enumerate_list(exts))
            else:
                try:
                    ext = self.bot.COGS[ext]
                    ext = f"cogs.{ext}"
                    await self.bot.reload_extension(ext)
                except (KeyError, commands.ExtensionNotLoaded):
                    title = NOT_FOUND_MSG
                else:
                    title = f"🔁 Reloaded extension"

                desc = f"`{ext}`"

            view = RepeatView(ctx)
            embed = self.bot.Embed(title=title, description=desc)
            embed.set_footer(text=f"Completed in {round(time.time() - start, 2)}s")
            view.message = await ctx.send(embed=embed, view=view)

    # cog all
    @commands.is_owner()
    @cog.command(
        name="all",
        aliases=["a"],
        hidden=True,
        brief="All cogs",
        help="Lists all cogs, dev only command.",
    )
    async def _all(self, ctx):
        exts = []
        for ext in self.bot.extensions:
            extn = ext.split(".")[-1].capitalize()
            exts.append(f"**{extn}** - `{str(ext)}`")

        embed = self.bot.Embed(title=f"All loaded extensions ({len(exts)})", description="\n".join(enumerate_list(exts)))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Developer(bot))
