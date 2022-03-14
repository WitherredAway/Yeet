import discord
from discord.ext import commands
import asyncio


class Dev(commands.Cog):
    """Developer only category."""
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

    display_emoji = "⚒️"

    @commands.command(
        name="togglecommand",
        aliases=["tc"],
        description="Enable or disable a command."
    )
    @commands.is_owner()
    async def toggle(self, ctx, *, command):
        command = self.bot.get_command(command)

        if command is None:
            return await ctx.send(f":x: Command `{command}` not found.")

        elif ctx.command == command:
            return await ctx.send(f":x: This command cannot be disabled.")

        else:
            command.enabled = not command.enabled
            await ctx.send(
                f'{"↪️ Enabled" if command.enabled else "↩️ Disabled"} command `{command.qualified_name}`.'
            )

    # cog
    @commands.is_owner()
    @commands.group(
        name="cog",
        aliases=["c"],
        invoke_without_command=True,
        case_insensitive=True,
        help="Commands related to cogs, dev only command.",
    )
    async def cog(self, ctx):
        await ctx.send_help(ctx.command)

    # cog load
    @commands.is_owner()
    @cog.command(
        name="load",
        aliases=["l"],
        brief="Load a cog",
        help="Loads a cog with the name, dev only command.",
    )
    async def _load(self, ctx, cog):
        try:
            await bot.load_extension(f"cogs.{cog}")
        except commands.ExtensionNotFound:
            await ctx.send(f":x: Cog `{cog}` not found.")
        except commands.ExtensionAlreadyLoaded:
            await ctx.send(f"Cog `{cog}` is already loaded.")
        except Exception as e:
            raise e
        else:
            await ctx.send(f":inbox_tray: Loaded cog `{cog}`")

    # cog unload
    @commands.is_owner()
    @cog.command(
        name="unload",
        aliases=["u"],
        brief="Unloads a cog",
        help="Unloads a cog with the name, dev only command.",
    )
    async def _unload(self, ctx, cog):
        if cog.lower() == "admin":
            await ctx.send(":x: Cannot unload this cog")
        else:
            try:
                await bot.unload_extension(f"cogs.{cog}")
            except commands.ExtensionNotLoaded:
                await ctx.send(f":x: Cog `{cog}` not found.")
            except Exception as e:
                raise e
            else:
                await ctx.send(f":outbox_tray: Unloaded cog `{cog}`")

    # cog reload
    @commands.is_owner()
    @cog.command(
        name="reload",
        aliases=["r"],
        brief="Reloads a cog",
        help="Reloads a cog with the name, dev only command.",
    )
    async def _reload(self, ctx, cog):
        try:
            if cog == "all":
                try:
                    cogs = []
                    for cog_ext in list(self.bot.extensions):
                        await self.bot.reload_extension(cog_ext)
                        cog_name = (
                            cog_ext[5:] if cog_ext.startswith("cogs.") else cog_ext
                        )
                        cogs.append(f"\n🔁 Reloaded cog `{cog_name}`")
                    await ctx.send(", ".join(cogs))
                except Exception as e:
                    raise e
            else:
                try:
                    await self.bot.reload_extension(f"cogs.{cog}")
                except commands.ExtensionNotLoaded:
                    await ctx.send(f":x: Cog `{cog}` not found.")
                else:
                    await ctx.send(f":repeat: Reloaded cog `{cog}`")
        except Exception as e:
            raise e

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
        extlist = self.bot.Embed(title="Cogs", description="List of all enabled cogs")

        for ext in self.bot.extensions:
            extn = (
                ext.split(".")[1].capitalize()
                if ext.startswith("cogs")
                else ext.capitalize()
            )
            extlist.add_field(name=extn, value=str(ext), inline=False)
        await ctx.send(embed=extlist)


async def setup(bot):
   await bot.add_cog(Dev(bot))
