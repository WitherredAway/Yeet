from __future__ import annotations
from discord.ext import commands, menus
from .utils import checks, formats, time
from .utils.paginator import BotPages
from collections import OrderedDict, deque, Counter
from typing import Any, Dict, List, Optional, Union
from .utils.source import source

import discord
import os, datetime
import asyncio
import copy
import unicodedata
import inspect
import itertools


class FrontPageSource(menus.PageSource):
    new_line = "\n"

    def is_paginating(self) -> bool:
        return True

    def get_max_pages(self) -> Optional[int]:
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page):
        embed = self.bot.Embed(
            title="Help Interface",
            description=f"**[Invite the bot here!](https://discord.com/api/oauth2/authorize?client_id=634409171114262538&permissions=8&scope=bot)**\n——————————————————————————————\nDo `,help <command>` for more info on a command.\nDo `,help <category>` (case sensitive) for more info on a category.\n——————————————————————————————",
        )

        if self.index == 0:
            cog_names = sorted(self.bot.cogs.keys())
            for cog_name in cog_names:
                cog = self.bot.cogs[cog_name]
                cog_commands = sorted(
                    cog.get_commands(), key=lambda x: x.qualified_name
                )
                if any((getattr(cog, "hidden", False), len(cog_commands) == 0)):
                    continue
                description = (
                    cog.description.split("\n", 1)[0] or "No description found."
                )
                emoji = getattr(cog, "display_emoji", "🟡")
                category_commands = []
                for command in cog_commands:
                    if not command.hidden:
                        com = command.qualified_name
                        com_src = source(self, command=com)
                        category_commands.append(
                            f"**[{com}]({com_src})**{(' (' + str(len(command.commands)) + ')') if isinstance(command, commands.Group) else ''}: {command.brief or command.description or 'No description found.'}"
                        )

                embed.add_field(
                    name=f"{emoji} **{cog.qualified_name}**: {description}",
                    value=f"{self.new_line.join(category_commands)}",
                )

        elif self.index == 1:
            entries = (
                ("<argument>", "This means the argument is __**required**__."),
                ("[argument]", "This means the argument is __**optional**__."),
                (
                    "[A|B]",
                    "This means that it can be __**either A or B**__. If one is **bold**, that means that it is the **main option**.",
                ),
                (
                    "[argument=value]",
                    "This means that the argument defaults to **value** if nothing is passed.",
                ),
                (
                    "[argument...]",
                    "This means you can have multiple arguments.\n"
                    "__**Remember not to include the brackets (<> or [])!**__",
                ),
            )

            embed.add_field(
                name="How do I use this bot?",
                value="Reading the bot signature is pretty simple.",
            )

            for name, value in entries:
                embed.add_field(name=name, value=value, inline=False)

        return embed


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        ctx,
        group: Union[commands.Group, commands.Cog],
        _commands: List[commands.Command],
        *,
        prefix: str,
    ):
        super().__init__(entries=_commands, per_page=8)
        self.entries = _commands
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.group = group
        self.prefix = prefix

    def is_paginating(self) -> bool:
        return len(self.entries) > self.per_page

    async def format_page(self, menu, _commands):
        embed = self.bot.Embed()
        maximum = self.get_max_pages()

        if isinstance(self.group, commands.Group):
            self.title = (
                f"`{self.prefix}`"
                + PaginatedHelpCommand.get_command_signature(self.group)
            )
            bs = "\_"
            self.description = f"""
**Category**
`{self.group.cog_name if self.group.cog else 'None'}`

**Description**
{self.group.description if self.group.description else 'No description found.'}

**Help**
{self.group.help if self.group.help else 'No help found.'}
            """
            embed.set_footer(
                text=f"Do {self.ctx.clean_prefix}help <command> for more info on a command."
                f'\nPage {menu.current_page + 1}/{maximum} ({(no_commands := len(self.entries))} {"subcommand" if no_commands <= 1 else "subcommands"})'
            )
        if isinstance(self.group, commands.Cog):
            self.title = f"{self.group.qualified_name} Commands"
            self.description = (
                self.group.description
                if self.group.description
                else self.group.help
                if getattr(self.group, "help", None)
                else "No description found."
            )
            embed.set_footer(
                text=f"Do {self.ctx.clean_prefix}help <command> for more info on a command."
                f'\nPage {menu.current_page + 1}/{maximum} ({(no_commands := len(self.entries))} {"command" if no_commands <= 1 else "commands"})'
            )

        embed.title = self.title
        embed.description = self.description

        value = []
        for command in _commands:
            # signature = f"{self.prefix}{PaginatedHelpCommand.get_command_signature(self, command)}"
            # value = f">>> **Category**: `{command.cog_name if command.cog else 'None'}`\n\n**Description**: {command.description if command.description else 'No description found.'}\n\n**Help**: {command.help if command.help else 'No help found.'}"
            signature = (
                f"`{self.prefix}`{PaginatedHelpCommand.get_command_signature(command)}"
            )
            desc = (
                command.brief
                if command.brief
                else command.description.split("\n")[0]
                if command.description
                else command.help.split("\n")[0]
                if command.help
                else "No brief description found."
            )
            if isinstance(command, commands.Group):
                com_names = sorted([com.name for com in command.commands])
                desc += "\n⌙ **subcommands**: `" + "` - `".join(com_names) + "`"
            # embed.add_field(name=signature, value=value, inline=False)
            value.append(f"• {signature} - {desc}")

        embed.add_field(
            name="Commands" if isinstance(self.group, commands.Cog) else "Subcommands",
            value="\u200b"+"\n\n".join(value),
            inline=False,
        )
        return embed


class CommandSelectMenu(discord.ui.Select):
    def __init__(
        self,
        ctx,
        commands: List[commands.Command],
    ):
        super().__init__(
            custom_id="cmd_select",
            placeholder="Select a command...",
            min_values=1,
            max_values=1,
        )
        self.commands = list(commands)[:25]
        self.ctx = ctx
        self.context = self.ctx
        self.bot = self.ctx.bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Index",
            emoji="⭕",
            value="__command_index",
            description="Initial page of the parent command.",
        )

        for command in self.commands:
            description = f"{command.description[:50] or command.help[:50] or None}..."
            emoji = getattr(command.cog, "display_emoji", "🟡")
            self.add_option(
                label=command.qualified_name,
                value=command.qualified_name,
                description=description,
                emoji=emoji,
            )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == "__command_index":
            await self.view.rebind(self.view.initial_source, interaction)
        else:
            command = self.bot.get_command(value)
            if command is None:
                await interaction.response.send_message(
                    "Somehow this command does not exist?", ephemeral=True
                )
                return

            if isinstance(command, commands.Group):
                source = GroupHelpPageSource(
                    self.ctx,
                    command,
                    list(command.commands),
                    prefix=self.view.ctx.clean_prefix,
                )
                await self.view.rebind(source, interaction)
            else:
                embed = self.bot.Embed()
                PaginatedHelpCommand.common_command_formatting(self, embed, command)
                await interaction.response.edit_message(embed=embed, view=self.view)


class HelpSelectMenu(discord.ui.Select["HelpMenu"]):
    def __init__(
        self,
        ctx,
        commands: Dict[commands.Cog, List[commands.Command]],
        cmd_select: bool = False,
    ):
        super().__init__(
            custom_id="cat_select",
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands = commands
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.cmd_select = cmd_select
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Index",
            emoji="\N{WAVING HAND SIGN}",
            value="__index",
            description="The help page showing how to use the bot.",
        )

        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split("\n", 1)[0] or None
            emoji = getattr(cog, "display_emoji", "🟡")
            self.add_option(
                label=cog.qualified_name,
                value=cog.qualified_name,
                description=description,
                emoji=emoji,
            )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == "__index":
            index = FrontPageSource()
            index.bot = self.bot
            for idx, item in enumerate(self.view.children):
                if isinstance(item, CommandSelectMenu):
                    self.view.remove_item(item)
            await self.view.rebind(index, interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message(
                    "Somehow this category does not exist?", ephemeral=True
                )
                return

            commands = [
                command for command in self.commands[cog]
                if not command.hidden
            ]
            if not commands:
                await interaction.response.send_message(
                    "This category has no commands for you", ephemeral=True
                )
                return

            for idx, item in enumerate(self.view.children):
                if isinstance(item, CommandSelectMenu):
                    self.view.remove_item(item)
                    self.view.add_item(CommandSelectMenu(self.view.ctx, commands))
                    break
            else:
                self.view.add_categories_and_commands(self.commands, commands)

            source = GroupHelpPageSource(
                self.ctx, cog, commands, prefix=self.view.ctx.clean_prefix
            )
            self.view.initial_source = source
            await self.view.rebind(source, interaction)


class HelpMenu(BotPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context):
        super().__init__(source, ctx=ctx)
        self.initial_source = source

    def add_categories(
        self, commands: Dict[commands.Cog, List[commands.Command]]
    ) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(self.ctx, commands))
        self.fill_items()

    def add_commands(self, commands: List[commands.Command]) -> None:
        self.clear_items()
        self.add_item(CommandSelectMenu(self.ctx, commands))
        self.fill_items()

    def add_categories_and_commands(
        self,
        cogs_and_commands: Dict[commands.Cog, List[commands.Command]],
        commands: List[commands.Command],
    ) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(self.ctx, cogs_and_commands, cmd_select=True))
        self.add_item(CommandSelectMenu(self.ctx, commands))
        self.fill_items()

    async def rebind(
        self, source: menus.PageSource, interaction: discord.Interaction
    ) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "brief": "Shows help about the bot, a command, or a category",
                "description": """
                Shows help about the bot, a command, or a category
                
                Code taken and modified from [Robodanny](https://github.com/Rapptz/RoboDanny).
                """,
                "help": """
                Shows this message.
                
                Do `help <command>` to view the help of a specific command
                Do `help <category/cog>` (case-sensitive) to view help of a specific category or cog.
                """,
            }
        )

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if (
                isinstance(error.original, discord.HTTPException)
                and error.original.code == 50013
            ):
                return

            await ctx.send(str(error.original))

    @staticmethod
    def get_command_signature(command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = "/".join(command.aliases)
            fmt = f"[**{command.name}**/{aliases}]"
            if parent:
                fmt = f"{parent} {fmt}"
            alias = fmt
        else:
            alias = command.name if not parent else f"{parent} {command.name}"
        return (f"{alias} `{command.signature}`") if command.signature else (f"{alias}")

    async def send_bot_help(self, mapping):
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else "\U0010ffff"

        entries: List[commands.Command] = await self.filter_commands(
            bot.commands, sort=True, key=key
        )

        all_commands: Dict[commands.Cog, List[commands.Command]] = {}
        for name, children in itertools.groupby(entries, key=key):
            children = sorted(children, key=lambda c: c.qualified_name)
            if any((name == "\U0010ffff", len(children) == 0)):
                continue

            cog = bot.get_cog(name)
            all_commands[cog] = children

        initial = FrontPageSource()
        initial.bot = self.context.bot
        menu = HelpMenu(initial, ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start()

    async def send_cog_help(self, cog):
        # cog help
        cog_commands = await self.filter_commands(cog.get_commands(), sort=True)
        source = GroupHelpPageSource(
            self.context, cog, cog_commands, prefix=self.context.clean_prefix
        )
        menu = HelpMenu(source, ctx=self.context)
        menu.initial_source = source

        # for the selectmenu
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else "\U0010ffff"

        all_commands_list: List[commands.Command] = await self.filter_commands(
            bot.commands, sort=True, key=key
        )

        all_commands_dict: Dict[commands.Cog, List[commands.Command]] = {}
        for name, children in itertools.groupby(all_commands_list, key=key):
            children = sorted(children, key=lambda c: c.qualified_name)
            if any((name == "\U0010ffff", len(children) == 0)):
                continue

            cog = bot.get_cog(name)
            all_commands_dict[cog] = children

        menu.add_categories_and_commands(all_commands_dict, cog_commands)
        # start the menu
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = f"`{self.context.prefix}`{PaginatedHelpCommand.get_command_signature(command)}"
        embed_like.add_field(
            name="Help",
            value=f"{command.help if command.help else 'No help found.'}",
            inline=False,
        )
        embed_like.add_field(
            name="Description",
            value=f"{command.description if command.description else 'No description found.'}",
            inline=False,
        )
        embed_like.add_field(
            name="Category",
            value=f"`{command.cog_name if command.cog else 'None'}`",
            inline=False,
        )

    async def send_command_help(self, command):
        embed = self.context.bot.Embed()
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(
            self.context, group, entries, prefix=self.context.clean_prefix
        )
        # self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        # menu.initial_source = source
        menu.add_commands(entries)
        await menu.start()


class Help(commands.Cog):
    """Commands for utilities related to Discord or the Bot itself."""

    def __init__(self, bot):
        self.bot = bot
        self.old_help_command = bot.help_command
        bot.help_command = PaginatedHelpCommand()
        bot.help_command.cog = self

    display_emoji = "❔"

    def cog_unload(self):
        self.bot.help_command = self.old_help_command

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    @commands.command(aliases=("whois",), brief="Shows info about an user, role, etc")
    async def info(
        self, ctx, *, id: Union[discord.Member, discord.User, discord.Role] = None
    ):
        """Shows info about an ID."""

        def format_date(dt):
            if dt is None:
                return "N/A"
            return f'{time.format_dt(dt, "F")} ({time.format_relative(dt)})'

        e = self.bot.Embed()

        if isinstance(id, (discord.Member, discord.User, type(None))):
            user = id or ctx.author
            roles = [
                role.name.replace("@", "@\u200b") for role in getattr(user, "roles", [])
            ]
            title = str(user)
            if user.bot:
                if user.public_flags.verified_bot:
                    title += " **[✓BOT]**"
                else:
                    title += " **[BOT]**"
            e.title = title

            e.add_field(name="ID", value=user.id, inline=False)
            e.add_field(name="Avatar", value=f"[Link]({user.avatar.url})", inline=False)
            e.add_field(
                name="Joined",
                value=format_date(getattr(user, "joined_at", None)),
                inline=False,
            )
            e.add_field(
                name="Created", value=format_date(user.created_at), inline=False
            )

            voice = getattr(user, "voice", None)
            if voice is not None:
                vc = voice.channel
                other_people = len(vc.members) - 1
                voice = (
                    f"{vc.name} with {other_people} others"
                    if other_people
                    else f"{vc.name} by themselves"
                )
                e.add_field(name="Voice", value=voice, inline=False)

            if roles:
                e.add_field(
                    name="Roles",
                    value=", ".join(roles)
                    if len(roles) < 10
                    else f"{len(roles)} roles",
                    inline=False,
                )

            e.colour = user.colour

            e.set_thumbnail(url=user.display_avatar.url)

            if isinstance(user, discord.User):
                e.set_footer(text="This member is not in this server.")

        elif isinstance(id, discord.Role):
            role = id
            members = [str(member) for member in role.members]
            permissions = (
                ["administrator"]
                if role.permissions.administrator
                else [name for name, value in role.permissions if value]
            )
            title = str(role)

            e.title = title

            if role.colour.value:
                colour = role.colour
                e.colour = colour
            else:
                colour = None

            e.add_field(name="ID", value=role.id, inline=False)
            e.add_field(name="Color", value=colour, inline=False)
            e.add_field(
                name="Created", value=format_date(role.created_at), inline=False
            )
            e.add_field(name="Permissions", value=", ".join(permissions), inline=False)

            if members:
                e.add_field(
                    name="Members",
                    value=", ".join(members)
                    if len(members) < 20
                    else f"{len(members)} members.",
                    inline=False,
                )

        await ctx.send(embed=e)

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = self.bot.Embed(colour=member.colour)
        avatar = member.display_avatar.with_static_format("png")
        e.set_author(name=str(member), url=avatar)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace("_", " ").replace("guild", "server").title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name="Allowed", value="\n".join(allowed))
        e.add_field(name="Denied", value="\n".join(denied))
        await ctx.send(embed=e)

    @commands.command(
        brief="Shows a member's permissions in a channel",
        help="""Shows a member's permissions in a specific channel.

        If no channel is given then it uses the current one.

        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """,
    )
    @commands.guild_only()
    async def permissions(
        self, ctx, member: discord.Member = None, channel: discord.TextChannel = None
    ):
        channel = channel or ctx.channel
        if member is None:
            member = ctx.author

        await self.say_permissions(ctx, member, channel)

    @commands.command(
        name="source",
        aliases=("src",),
        brief="Displays the source code of a command.",
        description="""
        Displays the full source code or for a specific command of the bot.

        Code taken from [Robodanny](https://github.com/Rapptz/RoboDanny).
        """,
    )
    async def source(self, ctx, *, command: str = None):
        """
        To display the source code of a subcommand you can separate it by periods, e.g. timer.start for the start subcommand of the timer command or by spaces.
        """

        # use the imported source function from utils/source.py
        final_url = source(self, command=command)
        await ctx.send(final_url)


def setup(bot):
    bot.add_cog(Help(bot))
