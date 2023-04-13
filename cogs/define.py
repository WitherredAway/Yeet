from __future__ import annotations

import urllib
import typing
from typing import Optional, Type, TypeVar

import discord
from discord.ext import commands, menus
import aiohttp
import aiowiki

from .RDanny.utils.paginator import BotPages
from constants import MESSAGE_CHAR_LIMIT, NL
from .utils.utils import UrlView

if typing.TYPE_CHECKING:
    from main import Bot


class TermSelectMenu(discord.ui.Select):
    """The select menu for different words and their information."""

    def __init__(self, entries: typing.List, bot: commands.Bot):
        super().__init__(placeholder="Jump to definition", row=0)
        self.entries = entries[:25]
        self.bot = bot
        self.__fill_options()

    def __fill_options(self):
        for page, entry in enumerate(self.entries):
            description = entry["definition"]
            self.add_option(
                label=f'{page+1}. {entry["part_of_speech"]}',
                value=page,
                description=f"{description[:50]}...",
            )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.view.show_checked_page(interaction, int(self.values[0]))


class TermPages(BotPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context, compact: bool):
        super().__init__(source, ctx=ctx, compact=compact)
        if source.is_paginating():
            self.add_select(source.entries)

    def add_select(self, entries: typing.List) -> None:
        self.clear_items()
        self.add_item(TermSelectMenu(entries, self.ctx.bot))
        self.fill_items()


class TermPageSource(menus.ListPageSource):
    def __init__(self, term_obj: Term, *, ctx: commands.Context, per_page: int = 1):
        self.ctx = ctx
        self.bot: discord.Bot = self.ctx.bot
        self.embed = self.bot.Embed()

        self.term: Term = term_obj
        self.entries: typing.List = self.term.meanings
        self.per_page = per_page
        self.phonetics: typing.List = [self.term.phonetic]
        for phonetic in self.term.phonetics:
            if phonetic.get("text", "") != "" and phonetic.get("audio", "") != "":
                self.phonetics.append(f"[{phonetic['text']}]({phonetic['audio']})")
        super().__init__(self.entries, per_page=per_page)

    def is_paginating(self) -> bool:
        return len(self.entries) > self.per_page

    async def format_page(self, menu, entry) -> discord.Embed:
        self.embed.clear_fields()
        self.embed.title = f"{self.term.word}"

        self.embed.description = f"""*`{entry['part_of_speech']}`*\n{", ".join(self.phonetics)}\n\n{entry['definition']}
        """

        if (example := entry.get("example", "")) != "":
            self.embed.add_field(name="example", value=example, inline=True)

        if antonyms := entry["antonyms"]:
            self.embed.add_field(
                name="antonyms", value=", ".join(antonyms), inline=True
            )

        if synonyms := entry["synonyms"]:
            self.embed.add_field(
                name="synonyms", value=", ".join(synonyms), inline=True
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            text = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            self.embed.set_footer(text=text)

        return self.embed


class Term:
    """Object for a term for information and pagination."""

    async def __new__(cls, *args, **kwargs):
        """Makes the __init__ function asynchronous."""

        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance

    async def __init__(self, term: str):
        self.TERM: str = term
        self.API: str = "https://api.dictionaryapi.dev/api/v2/entries/en/"

        self.data: typing.Dict = await self.get_data(self.TERM)
        self.word: str = self.data.get("word", None)
        self.phonetic: typing.Dict = self.data.get("phonetic", "")
        self.phonetics: typing.Dict = self.data.get("phonetics", None)
        self.raw_meanings: typing.List = self.data.get("meanings", None)
        self.meanings: typing.List = self.clean_meanings
        self.src_urls: typing.List = self.data.get("sourceUrls", None)

    async def get_data(self, term: str) -> typing.Dict:
        """Get data from the dictionary api."""
        term = urllib.parse.quote(term)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.API}{term}") as resp:
                return (await resp.json())[0]

    @property
    def clean_meanings(
        self,
    ) -> typing.List:
        """Return a list of meanings, in a cleaner, formattable way."""

        clean_list = []
        for meaning in self.raw_meanings:
            part_of_speech = meaning.get("partOfSpeech", None)
            for definition in meaning["definitions"]:
                definition["part_of_speech"] = part_of_speech
                clean_list.append(definition)
        return clean_list


class Define(commands.Cog):
    """Command(s) for all kinds of information of a term; word or phrase."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.wiki_client = aiowiki.Wiki.wikipedia("en")

    display_emoji: discord.PartialEmoji = "🔍"

    async def cog_unload(self) -> None:
        await self.wiki_client.close()

    @commands.command(
        name="define",
        aliases=("definition", "definitions", "df"),
        description=("Show definitions and other info about a term."),
    )
    async def define(self, ctx: commands.Context, *, term: str):
        try:
            term = await Term(term)
        except KeyError:
            return await ctx.send("Could not find anything. Sorry.")
        formatter = TermPageSource(term, ctx=ctx, per_page=1)
        menu = TermPages(formatter, ctx=ctx, compact=True)
        await menu.start()

    @commands.command(
        name="wiki",
        aliases=["wikipedia"],
        brief="Searches wikipedia for info.",
        help="Use this command to look up anything on wikipedia. Sends the first 10 sentences from wikipedia.",
    )
    async def wiki(self, ctx: commands.Context, *, query: str = None):
        await ctx.typing()
        pages = await self.wiki_client.opensearch(query)
        try:
            page = pages[0]
        except IndexError:
            return await ctx.reply("Not found, sorry!")
        summary = await page.summary() or "No summary found, please visit the page instead:"
        text = summary[:MESSAGE_CHAR_LIMIT] + ('...' if len(summary) >= MESSAGE_CHAR_LIMIT else '')
        url = (await page.urls()).view
        images = await page.media()

        embed = self.bot.Embed(title=page.title, description=(NL*2).join(text.split(NL)))
        if images:
            embed.set_image(url=images[0])
        await ctx.reply(
            embed=embed,
            view=UrlView({'Wikipedia URL': (url, 0)})
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Define(bot))
