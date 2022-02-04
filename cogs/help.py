from __future__ import annotations
from main import *
from discord.ext import commands, menus
from .utils import checks, formats, time
from .utils.paginator import BotPages
import discord
from collections import OrderedDict, deque, Counter
import os, datetime
import asyncio
import copy
import unicodedata
import inspect
import itertools
from typing import Any, Dict, List, Optional, Union


class Prefix(commands.Converter):
    async def convert(self, ctx, argument):
        user_id = ctx.bot.user.id
        if argument.startswith((f'<@{user_id}>', f'<@!{user_id}>')):
            raise commands.BadArgument('That is a reserved prefix already in use.')
        return argument


class GroupHelpPageSource(menus.ListPageSource):
    def is_paginating(self) -> bool:
        return True
    def __init__(self, group: Union[commands.Group, commands.Cog], commands: List[commands.Command], *, prefix: str):
        super().__init__(entries=commands, per_page=6)
        self.group = group
        self.prefix = prefix
        self.title = f'{self.group.qualified_name} Commands'
        self.description = self.group.description

    async def format_page(self, menu, commandz):
        embed = discord.Embed(title=self.title, description=self.description, colour=embed_colour)
        for command in commandz:
            #signature = f"{self.prefix}{PaginatedHelpCommand.get_command_signature(self, command)}"
            #value = f">>> **Category**: `{command.cog_name if command.cog else 'None'}`\n\n**Description**: {command.description if command.description else 'No description found.'}\n\n**Help**: {command.help if command.help else 'No help found.'}"
            signature = f"> `{self.prefix}`" + PaginatedHelpCommand.get_command_signature(self, command)
            value = f"{command.description if command.description else command.help if command.help else 'No description found.'}"
            if isinstance(command, commands.Group):
                com_names = sorted([com.name for com in command.commands])
                value += '\n**Subcommands**: `' + '` • `'.join(com_names) + '`'
            embed.add_field(name=signature, value=value, inline=False)

        maximum = self.get_max_pages()
        embed.set_author(name=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)\n——————————————————————————————')

        embed.set_footer(text=f'Use "{self.prefix}help command" for more info on a command.')
        return embed


class HelpSelectMenu(discord.ui.Select['HelpMenu']):
    def __init__(self, commands: Dict[commands.Cog, List[commands.Command]], bot: commands.AutoShardedBot):
        super().__init__(
            placeholder='Select a category...',
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands = commands
        self.bot = bot
        self.__fill_options()
        
    
    def __fill_options(self) -> None:
        self.add_option(
            label='Index',
            emoji='\N{WAVING HAND SIGN}',
            value='__index',
            description='The help page showing how to use the bot.',
        )
        
        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split('\n', 1)[0] or None
            emoji = getattr(cog, 'display_emoji', "🟡")
            self.add_option(label=cog.qualified_name, value=cog.qualified_name, description=description, emoji=emoji)
        
    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == '__index':
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message('Somehow this category does not exist?', ephemeral=True)
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message('This category has no commands for you', ephemeral=True)
                return

            source = GroupHelpPageSource(cog, commands, prefix=self.view.ctx.clean_prefix)
            await self.view.rebind(source, interaction)


class FrontPageSource(menus.PageSource):
    def __init__(self, ctx):
        self.context = ctx
    def is_paginating(self) -> bool:
        return True

    def get_max_pages(self) -> Optional[int]:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page):
        embed = discord.Embed(title='Help Interface', description=f"**[Invite the bot here!](https://discord.com/api/oauth2/authorize?client_id=634409171114262538&permissions=8&scope=bot)**\n——————————————————————————————\nDo `{self.context.prefix}help <command>` for more info on a command.\nDo `{self.context.prefix}help <category>` (case sensitive) for more info on a category.\n——————————————————————————————", color=embed_colour)
        cog_names = sorted(bot.cogs.keys())
        for cog_name in cog_names:
            cog = bot.cogs[cog_name]
            description = cog.description.split('\n', 1)[0] or "No description found."
            emoji = getattr(cog, 'display_emoji', "🟡")
            commandz = []
            for command in cog.get_commands():
                if not command.hidden:
                    com = command.qualified_name
                    if isinstance(command, commands.Group):
                        com += f" - {len(command.commands)}"
                    commandz.append(com)
                
            embed.add_field(name=f"{emoji} **{cog.qualified_name}** - *{description}*", value=f"`{'` • `'.join(commandz) or 'No commands found.'}`")
        return embed

class HelpMenu(BotPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context):
        super().__init__(source, ctx=ctx, compact=True)

    def add_categories(self, commands: Dict[commands.Cog, List[commands.Command]]) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(self, source: menus.PageSource, interaction: discord.Interaction) -> None:
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
                'help': 'Shows help about the bot, a command, or a category',
            }
        )

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if isinstance(error.original, discord.HTTPException) and error.original.code == 50013:
                return

            await ctx.send(str(error.original))

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '/'.join(command.aliases)
            fmt = f'[**{command.name}**/{aliases}]'
            if parent:
                fmt = f'{parent} {fmt}'
            alias = fmt
        else:
            alias = command.name if not parent else f'{parent} {command.name}'
        return (f'{alias} `{command.signature}`') if command.signature else (f'{alias}')

    async def send_bot_help(self, mapping):
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else '\U0010ffff'

        entries: List[commands.Command] = await self.filter_commands(bot.commands, sort=True, key=key)

        all_commands: Dict[commands.Cog, List[commands.Command]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == '\U0010ffff':
                continue

            cog = bot.get_cog(name)
            all_commands[cog] = sorted(children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(ctx=self.context), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix), ctx=self.context)
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = f"`{self.context.prefix}`{self.get_command_signature(command)}"
        embed_like.description = f"**Category**: `{command.cog_name if command.cog else 'None'}`\n\n**Description**: {command.description if command.description else 'No description found.'}\n\n**Help**: {command.help if command.help else 'No help found.'}"

    async def send_command_help(self, command):
        embed = discord.Embed(colour=embed_colour)
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        #await self.context.release()
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

    @commands.command(aliases=("whois",))
    async def info(self, ctx, *, id: Union[discord.Member, discord.User, discord.Role] = None):
        """Shows info about an ID."""

        def format_date(dt):
            if dt is None:
                return 'N/A'
            return f'{time.format_dt(dt, "F")} ({time.format_relative(dt)})'

        e = discord.Embed()
        
        if isinstance(id, (discord.Member, discord.User, type(None))):
            user = id or ctx.author
            roles = [role.name.replace("@", "@\u200b") for role in getattr(user, 'roles', [])]
            title = str(user)
            if user.bot:
                if user.public_flags.verified_bot:
                    title += " **[✓BOT]**"
                else:
                    title += " **[BOT]**"
            e.title = title

            e.add_field(name='ID', value=user.id, inline=False)
            e.add_field(name="Avatar", value=f"[Link]({user.avatar.url})", inline=False)
            e.add_field(name='Joined', value=format_date(getattr(user, 'joined_at', None)), inline=False)
            e.add_field(name='Created', value=format_date(user.created_at), inline=False)

            voice = getattr(user, 'voice', None)
            if voice is not None:
                vc = voice.channel
                other_people = len(vc.members) - 1
                voice = f'{vc.name} with {other_people} others' if other_people else f'{vc.name} by themselves'
                e.add_field(name='Voice', value=voice, inline=False)

            if roles:
                e.add_field(name='Roles', value=', '.join(roles) if len(roles) < 10 else f'{len(roles)} roles', inline=False)

            e.colour = user.colour

            e.set_thumbnail(url=user.display_avatar.url)

            if isinstance(user, discord.User):
                e.set_footer(text='This member is not in this server.')

        elif isinstance(id, discord.Role):
            role = id
            members = [str(member) for member in role.members]
            permissions = ['administrator'] if role.permissions.administrator else [name for name, value in role.permissions if value]
            title = str(role)

            e.title = title

            if role.colour.value:
                colour = role.colour
                e.colour = colour
            else:
                colour = None
                
            e.add_field(name='ID', value=role.id, inline=False)
            e.add_field(name='Color', value=colour, inline=False)
            e.add_field(name='Created', value=format_date(role.created_at), inline=False)
            e.add_field(name='Permissions', value=', '.join(permissions), inline=False)

            if members:
                e.add_field(name='Members', value=', '.join(members) if len(members) < 20 else f'{len(members)} members.', inline=False)

        await ctx.send(embed=e)

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        avatar = member.display_avatar.with_static_format('png')
        e.set_author(name=str(member), url=avatar)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace('_', ' ').replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name='Allowed', value='\n'.join(allowed))
        e.add_field(name='Denied', value='\n'.join(denied))
        await ctx.send(embed=e)

    @commands.command()
    @commands.guild_only()
    async def permissions(self, ctx, member: discord.Member = None, channel: discord.TextChannel = None):
        """Shows a member's permissions in a specific channel.

        If no channel is given then it uses the current one.

        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """
        channel = channel or ctx.channel
        if member is None:
            member = ctx.author

        await self.say_permissions(ctx, member, channel)

def setup(bot):
    bot.add_cog(Help(bot))