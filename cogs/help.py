from __future__ import annotations

import discord
import itertools

from discord.ext import commands, menus

from constants import NL
from .utils.paginator import BotPages
from .utils import time
from .utils.source import source


if typing.TYPE_CHECKING:
    from main import Bot


class FrontPageSource(menus.ListPageSource):
    def __init__(
        self,
        cogs_and_commands: Dict[commands.Cog, List[commands.Command]],
        *,
        per_page: Optional[int] = 8,
    ):
        self.cogs_and_commands: List[
            Tuple[commands.Cog, List[commands.Command]]
        ] = list(cogs_and_commands.items())
        super().__init__(self.cogs_and_commands, per_page=per_page)

    def is_paginating(self) -> bool:
        return True

    async def format_page(
        self, menu: HelpMenu, entries: List[Tuple[commands.Cog, List[commands.Command]]]
    ):
        embed = self.bot.Embed(
            title="Help Interface",
            description=f"**[Invite the bot here!](https://discord.com/api/oauth2/authorize?client_id=634409171114262538&permissions=8&scope=bot)**\n——————————————————————————————\nDo `,help <command>` for more info on a command.\nDo `,help <category>` (case sensitive) for more info on a category.\n——————————————————————————————",
        )
        for cog, _commands in entries:
            description = cog.description.split("\n", 1)[0] or "No description found."
            emoji = getattr(cog, "display_emoji", "🟡")
            command_texts = []
            for command in _commands:
                name = command.qualified_name
                src = source(self.bot, command=name)
                command_texts.append(
                    f"**[{name}]({src})**{(' (' + str(len(command.commands)) + ')') if isinstance(command, commands.Group) else ''}: {command.brief or command.description or 'No description found.'}"
                )
            embed.add_field(
                name=f"{emoji} **{cog.qualified_name}**: {description}",
                value=f"{NEW_LINE.join(command_texts)}",
            )

        return embed


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        ctx,
        group: Union[commands.Group, commands.Cog],
        _commands: List[commands.Command],
        *,
        per_page: Optional[int] = 8,
    ):
        super().__init__(entries=_commands, per_page=per_page)
        self.entries = _commands
        self.per_page = per_page
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.group = group
        self.prefix = self.ctx.clean_prefix

    def is_paginating(self) -> bool:
        return True

    async def format_page(self, menu, entries):
        embed = self.bot.Embed()
        maximum = self.get_max_pages()

        if isinstance(self.group, commands.Group):
            group_command = self.group
            bs = "\_"

            PaginatedHelpCommand.common_command_formatting(
                self.ctx, embed, group_command
            )

            embed.set_footer(
                text=f"Do {self.ctx.clean_prefix}help <command> for more info on a command."
                f'\nPage {menu.current_page + 1}/{maximum} ({(no_commands := len(self.entries))} {"subcommand" if no_commands == 1 else "subcommands"})'
            )
        elif isinstance(self.group, commands.Cog):
            group_cog = self.group
            embed.title = f"{group_cog.qualified_name} Commands"
            embed.description = (
                group_cog.description
                if group_cog.description
                else group_cog.help
                if getattr(group_cog, "help", None)
                else "No description found."
            )
            embed.set_footer(
                text=f"Do {self.ctx.clean_prefix}help <command> for more info on a command."
                f'\nPage {menu.current_page + 1}/{maximum} ({(no_commands := len(self.entries))} {"command" if no_commands == 1 else "commands"})'
            )

        if not len(entries) > 0:
            return embed

        menu.command_select_menu.commands = entries
        value = []
        for command in entries:
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
            value="\u200b" + "\n\n".join(value),
            inline=False,
        )
        return embed


class CommandSelectMenu(discord.ui.Select):
    def __init__(
        self,
        ctx,
        commands: List[commands.Command],
        *,
        help_command: commands.HelpCommand,
    ):
        super().__init__(
            custom_id="cmd_select",
            placeholder="Select a command...",
            min_values=1,
            max_values=1,
        )
        self._commands = commands
        self.ctx = ctx
        self.context = self.ctx
        self.bot = self.ctx.bot
        self.help_command = help_command

        self.__fill_options()

    @property
    def commands(self):
        return self._commands

    @commands.setter
    def commands(self, value: List[commands.command]):
        self._commands = value
        self.__fill_options()

    def clear_options(self):
        self._underlying.options.clear()
        return self

    def __fill_options(self) -> None:
        if not self.commands:
            return

        self.clear_options()
        self.add_option(
            label="Index",
            emoji="⭕",
            value="__command_index",
            description="Initial page of the parent command.",
        )

        for command in self.commands:
            description = f"{command.description[:50] if command.description else command.help[:50] if command.help else None}..."
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
                subcommands = await self.help_command.filter_commands(
                    command.commands, sort=True
                )

                source = GroupHelpPageSource(
                    self.ctx,
                    command,
                    subcommands,
                )
                await self.view.rebind(source, interaction)
            else:
                embed = self.bot.Embed()
                PaginatedHelpCommand.common_command_formatting(self.ctx, embed, command)
                await interaction.response.edit_message(embed=embed, view=self.view)


class HelpSelectMenu(discord.ui.Select["HelpMenu"]):
    def __init__(
        self,
        ctx,
        commands: Dict[commands.Cog, List[commands.Command]],
        *,
        help_command: commands.HelpCommand,
    ):
        super().__init__(
            custom_id="cat_select",
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0,
        )
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.commands = commands
        self.help_command = help_command
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Index",
            emoji="⭕",
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
            index = FrontPageSource(self.commands)
            index.bot = self.bot

            self.view.remove_item(self.view.command_select_menu)
            del self.view.command_select_menu

            await self.view.rebind(index, interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message(
                    "Somehow this category does not exist?", ephemeral=True
                )
                return

            commands = await self.help_command.filter_commands(
                self.commands[cog], sort=True
            )
            if not commands:
                await interaction.response.send_message(
                    "This category has no commands for you", ephemeral=True
                )
                return

            self.view.add_categories_and_commands(
                self.commands, commands, help_command=self.help_command
            )

            source = GroupHelpPageSource(self.ctx, cog, commands)
            self.view.initial_source = source
            await self.view.rebind(source, interaction)


class HelpMenu(BotPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context):
        super().__init__(source, ctx=ctx)
        self.initial_source = source

    def add_categories(
        self,
        all_commands: Dict[commands.Cog, List[commands.Command]],
        *,
        help_command: commands.HelpCommand,
    ) -> None:
        self.clear_items()
        if len(all_commands) > 0:
            self.add_item(
                HelpSelectMenu(self.ctx, all_commands, help_command=help_command)
            )
        self.fill_items()

    def add_commands(
        self,
        all_commands: List[commands.Command],
        *,
        help_command: commands.HelpCommand,
    ) -> None:
        self.clear_items()
        if len(all_commands) > 0:
            self.command_select_menu = CommandSelectMenu(
                self.ctx, None, help_command=help_command
            )
            self.add_item(self.command_select_menu)
        self.fill_items()

    def add_categories_and_commands(
        self,
        cogs_and_commands: Dict[commands.Cog, List[commands.Command]],
        commands: List[commands.Command],
        *,
        help_command: commands.HelpCommand,
    ) -> None:
        self.clear_items()
        if len(cogs_and_commands.keys()) > 0:
            self.add_item(
                HelpSelectMenu(self.ctx, cogs_and_commands, help_command=help_command)
            )
        if len(commands) > 0:
            self.command_select_menu = CommandSelectMenu(
                self.ctx, None, help_command=help_command
            )
            self.add_item(self.command_select_menu)
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
            alias = (
                f"**{command.name}**" if not parent else f"{parent} **{command.name}**"
            )
        return (f"{alias} `{command.signature}`") if command.signature else alias

    @staticmethod
    def common_command_formatting(ctx, embed_like, command):
        bot = ctx.bot
        embed_like.title = (
            f"`{ctx.clean_prefix}`{PaginatedHelpCommand.get_command_signature(command)}"
        )
        embed_like.url = source(bot, command=command.qualified_name)
        if command.help:
            embed_like.add_field(
                name="Help",
                value=command.help,
                inline=False,
            )
        if command.description:
            embed_like.add_field(
                name="Description",
                value=command.description,
                inline=False,
            )
        embed_like.add_field(
            name="Category",
            value=f"`{command.cog_name if command.cog else 'None'}`",
            inline=False,
        )

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

        initial = FrontPageSource(all_commands)
        initial.bot = self.context.bot
        menu = HelpMenu(initial, ctx=self.context)
        menu.add_categories(all_commands, help_command=self)
        await menu.start()

    async def send_cog_help(self, cog):
        # For the cog help
        cog_commands = await self.filter_commands(cog.get_commands(), sort=True)
        source = GroupHelpPageSource(self.context, cog, cog_commands)
        menu = HelpMenu(source, ctx=self.context)
        menu.initial_source = source

        # For the selectmenu
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

        menu.add_categories_and_commands(
            all_commands_dict, cog_commands, help_command=self
        )
        await menu.start()

    async def send_command_help(self, command):
        embed = self.context.bot.Embed()
        self.common_command_formatting(self.context, embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)

        source = GroupHelpPageSource(self.context, group, entries)
        menu = HelpMenu(source, ctx=self.context)
        menu.add_commands(entries, help_command=self)
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


async def setup(bot):
    await bot.add_cog(Help(bot))
