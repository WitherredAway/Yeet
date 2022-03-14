import discord
import aiohttp
import typing
import urllib
import asyncio

from discord.ext import commands, menus
from .utils.paginator import BotPages
from typing import Type, TypeVar


T = TypeVar("T", bound="Term")


class TermSelectMenu(discord.ui.Select):
    def __init__(self, entries, bot: commands.Bot):
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
    def __init__(self, source, ctx, compact):
        super().__init__(source, ctx=ctx, compact=compact)
        if source.is_paginating():
            self.add_select(source.entries)

    def add_select(self, entries) -> None:
        self.clear_items()
        self.add_item(TermSelectMenu(entries, self.ctx.bot))
        self.fill_items()


class TermPageSource(menus.ListPageSource):
    def __init__(self, term_obj: T, *, ctx: commands.Context, per_page: int = 1):
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.embed = self.bot.Embed()

        self.term = term_obj
        self.entries = self.term.meanings
        self.per_page = per_page
        self.phonetics = [self.term.phonetic]
        for phonetic in self.term.phonetics:
            if phonetic.get("text", "") != "" and phonetic.get("audio", "") != "":
                self.phonetics.append(f"[{phonetic['text']}]({phonetic['audio']})")
        super().__init__(self.entries, per_page=per_page)

    def is_paginating(self) -> bool:
        return len(self.entries) > self.per_page

    async def format_page(self, menu, entry):
        self.embed.clear_fields()
        self.embed.title = f"{self.term.word}"

        self.embed.description = f"""*`{entry['part_of_speech']}`*\n{", ".join(self.phonetics)}\n\n{entry['definition']}
        """

        if (example := entry.get("example", "")) != "":
            self.embed.add_field(name="example", value=example, inline=True)

        if len((antonyms := entry["antonyms"])) > 0:
            self.embed.add_field(
                name="antonyms", value=", ".join(antonyms), inline=True
            )

        if len((synonyms := entry["synonyms"])) > 0:
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
        self.meanings: typing.List = self.clean_meanings()
        self.src_urls: typing.List = self.data.get("sourceUrls", None)

    async def get_data(self, term: str) -> typing.Dict:
        """Get data from the dictionary api."""
        term = urllib.parse.quote(term)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.API}{term}") as resp:
                return (await resp.json())[0]

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

    def __init__(self, bot):
        self.bot = bot

    display_emoji: discord.PartialEmoji = "🔍"

    @commands.command(
        name="define",
        aliases=("definition", "definitions", "df"),
        description=("Show all kinds of information about a term; word or phrase."),
    )
    async def define(self, ctx, *, term):
        try:
            term = await Term(term)
        except KeyError:
            return await ctx.send("Could not find anything. Sorry.")
        formatter = TermPageSource(term, ctx=ctx, per_page=1)
        menu = TermPages(formatter, ctx=ctx, compact=True)
        await menu.start()


async def setup(bot):
    await bot.add_cog(Define(bot))
